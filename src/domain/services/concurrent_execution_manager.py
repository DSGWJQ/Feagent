"""并发执行管理器 - 管理多工作流的并行执行

支持：
- 并发任务执行
- 任务队列和优先级
- 依赖关系处理
- 资源锁机制
- 任务状态跟踪
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionLock:
    """执行锁 - 保护共享资源"""

    resource_id: str
    _is_locked: bool = False
    _acquired_at: datetime | None = None

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        """获取锁

        参数：
            blocking: 是否阻塞等待
            timeout: 超时时间

        返回：
            True 如果成功获取，False 否则
        """
        if not self._is_locked:
            self._is_locked = True
            self._acquired_at = datetime.now(UTC)
            return True

        if not blocking:
            return False

        # 简化实现：只支持非阻塞模式
        # 生产环境应该使用threading.Lock或asyncio.Lock
        return False

    def release(self) -> None:
        """释放锁"""
        self._is_locked = False
        self._acquired_at = None

    def is_locked(self) -> bool:
        """检查锁是否被持有"""
        return self._is_locked

    def __enter__(self):
        """上下文管理器 - 进入"""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器 - 退出"""
        self.release()


@dataclass
class Task:
    """执行任务包装器"""

    task_id: str
    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: int = 5
    status: TaskStatus = TaskStatus.PENDING
    result: Any | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dependencies: list[str] = field(default_factory=list)

    async def execute(self) -> Any:
        """执行任务

        返回：
            任务结果
        """
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now(UTC)

        try:
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(*self.args, **self.kwargs)
            else:
                result = self.func(*self.args, **self.kwargs)

            self.result = result
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now(UTC)
            return result
        except Exception as e:
            self.error = str(e)
            self.status = TaskStatus.FAILED
            self.completed_at = datetime.now(UTC)
            raise


class ConcurrentExecutionManager:
    """并发执行管理器

    职责：
    - 管理并发任务的执行
    - 维护任务队列和优先级
    - 跟踪任务状态
    - 处理依赖关系
    - 提供资源锁保护
    """

    def __init__(self, max_concurrent_tasks: int = 5):
        """初始化管理器

        参数：
            max_concurrent_tasks: 最大并发任务数
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.running_tasks: dict[str, Task] = {}
        self.pending_queue: list[Task] = []
        self.completed_tasks: dict[str, Task] = {}
        self.locks: dict[str, ExecutionLock] = {}
        self.event_loop: asyncio.AbstractEventLoop | None = None

    def submit_task(
        self,
        task_name: str,
        func: Callable,
        *args,
        priority: int = 5,
        **kwargs,
    ) -> str:
        """提交任务执行

        参数：
            task_name: 任务名称
            func: 可调用对象或协程函数
            priority: 优先级（1-10，10最高）
            args: 位置参数
            kwargs: 关键字参数

        返回：
            任务ID
        """
        task_id = f"task_{uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            name=task_name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
        )

        # 检查是否有空闲的执行槽位
        if len(self.running_tasks) < self.max_concurrent_tasks:
            self.running_tasks[task_id] = task
            # 异步执行任务
            self._schedule_task(task)
        else:
            # 添加到待执行队列
            task.status = TaskStatus.QUEUED
            self.pending_queue.append(task)
            # 按优先级排序
            self.pending_queue.sort(key=lambda t: t.priority, reverse=True)

        return task_id

    def submit_task_with_dependency(
        self,
        task_name: str,
        func: Callable,
        depends_on: list[str],
        *args,
        **kwargs,
    ) -> str:
        """提交有依赖关系的任务

        参数：
            task_name: 任务名称
            func: 可调用对象或协程函数
            depends_on: 依赖的任务ID列表
            args: 位置参数
            kwargs: 关键字参数

        返回：
            任务ID
        """
        task_id = f"task_{uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            name=task_name,
            func=func,
            args=args,
            kwargs=kwargs,
            dependencies=depends_on,
        )

        # 等待依赖任务完成
        task.status = TaskStatus.QUEUED
        self.pending_queue.append(task)

        return task_id

    def get_task_status(self, task_id: str) -> str | None:
        """获取任务状态

        参数：
            task_id: 任务ID

        返回：
            任务状态字符串
        """
        # 检查运行中的任务
        if task_id in self.running_tasks:
            return self.running_tasks[task_id].status.value

        # 检查已完成的任务
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id].status.value

        # 检查待执行队列
        for task in self.pending_queue:
            if task.task_id == task_id:
                return task.status.value

        return None

    def get_task_result(self, task_id: str, timeout: float | None = None) -> Any | None:
        """获取任务执行结果

        参数：
            task_id: 任务ID
            timeout: 等待超时时间（秒）

        返回：
            任务结果或None
        """
        import time

        start_time = time.time()

        while True:
            if task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
                if task.status == TaskStatus.COMPLETED:
                    return task.result
                elif task.status == TaskStatus.FAILED:
                    raise RuntimeError(f"任务失败：{task.error}")

            if timeout is not None:
                if time.time() - start_time > timeout:
                    return None

            time.sleep(0.01)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务

        参数：
            task_id: 任务ID

        返回：
            True 如果成功取消
        """
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.status = TaskStatus.CANCELLED
            del self.running_tasks[task_id]
            self.completed_tasks[task_id] = task
            return True

        # 从待执行队列中移除
        self.pending_queue = [t for t in self.pending_queue if t.task_id != task_id]

        return False

    def wait_all(self, timeout: float | None = None) -> bool:
        """等待所有任务完成

        参数：
            timeout: 超时时间（秒）

        返回：
            True 如果所有任务都完成，False 如果超时
        """
        import time

        start_time = time.time()

        while len(self.running_tasks) > 0 or len(self.pending_queue) > 0:
            if timeout is not None:
                if time.time() - start_time > timeout:
                    return False

            # 处理待执行队列中的任务
            self._process_pending_queue()

            time.sleep(0.01)

        return True

    def get_lock(self, resource_id: str) -> ExecutionLock:
        """获取或创建资源锁

        参数：
            resource_id: 资源ID

        返回：
            ExecutionLock 实例
        """
        if resource_id not in self.locks:
            self.locks[resource_id] = ExecutionLock(resource_id=resource_id)

        return self.locks[resource_id]

    def _schedule_task(self, task: Task) -> None:
        """调度任务执行（异步）

        参数：
            task: 任务对象
        """

        # 创建后台任务
        async def run_and_cleanup():
            try:
                await task.execute()
            finally:
                # 任务完成后，从运行中的任务中移除
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]

                # 添加到已完成的任务
                self.completed_tasks[task.task_id] = task

                # 处理待执行队列
                self._process_pending_queue()

        # 尝试获取或创建事件循环
        try:
            loop = asyncio.get_running_loop()
            # 如果有运行中的事件循环，创建任务
            asyncio.ensure_future(run_and_cleanup())
        except RuntimeError:
            # 没有运行中的事件循环，直接运行任务
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # 运行任务到完成，捕获任务内部的异常
            try:
                loop.run_until_complete(run_and_cleanup())
            except Exception:
                # 任务内的异常已经被捕获并存储在task.error中
                # 这里只是防止异常传播到调用者
                pass

    def _process_pending_queue(self) -> None:
        """处理待执行队列中的任务"""
        while len(self.pending_queue) > 0 and len(self.running_tasks) < self.max_concurrent_tasks:
            # 获取优先级最高的任务
            task = self.pending_queue.pop(0)

            # 检查依赖是否完成
            if task.dependencies:
                all_deps_done = all(dep_id in self.completed_tasks for dep_id in task.dependencies)
                if not all_deps_done:
                    # 依赖未完成，重新添加到队列
                    self.pending_queue.append(task)
                    continue

            # 执行任务
            task.status = TaskStatus.PENDING
            self.running_tasks[task.task_id] = task
            self._schedule_task(task)

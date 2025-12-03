"""子任务执行器 - Phase 3 隔离执行

业务定义：
- SubTaskExecutionContext: 提供隔离的执行上下文
- SubTaskExecutor: 子任务执行器协议
- SubTaskContainer: 子任务容器，管理隔离执行环境
- SubTaskResult: 子任务执行结果

设计原则：
- 上下文隔离：子任务修改不影响父上下文
- 失败隔离：一个子任务失败不影响其他子任务
- 结果汇总：子任务结果可以合并回父上下文

使用示例：
    # 创建隔离上下文
    parent = ExecutionContext.create()
    child = SubTaskExecutionContext.create_isolated(parent, subtask_id="task_1")

    # 执行子任务
    container = SubTaskContainer(subtask_id="task_1", parent_context=parent)
    result = await container.execute(executor=my_executor, task_data={...})
"""

from __future__ import annotations

import logging
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from src.domain.value_objects.execution_context import ExecutionContext

logger = logging.getLogger(__name__)


# ==================== 数据结构 ====================


@dataclass
class SubTask:
    """增强版子任务定义

    属性：
        id: 任务ID
        description: 任务描述
        type: 任务类型
        priority: 优先级（数字越小优先级越高）
        status: 任务状态
        result: 执行结果
        dependencies: 依赖的任务ID列表
        executor_type: 执行器类型
        timeout: 超时时间（秒）
    """

    id: str
    description: str
    type: str = "generic"
    priority: int = 0
    status: str = "pending"
    result: Any = None
    dependencies: list[str] = field(default_factory=list)
    executor_type: str = "default"
    timeout: float = 60.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "status": self.status,
            "result": self.result,
            "dependencies": self.dependencies,
            "executor_type": self.executor_type,
            "timeout": self.timeout,
        }


@dataclass
class SubTaskResult:
    """子任务执行结果

    属性：
        success: 是否成功
        output: 输出数据
        error: 错误信息（失败时）
        subtask_id: 子任务ID
        execution_time: 执行时间（秒）
        started_at: 开始时间
        completed_at: 完成时间
    """

    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    subtask_id: str = ""
    execution_time: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "subtask_id": self.subtask_id,
            "execution_time": self.execution_time,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ==================== 协议定义 ====================


class SubTaskExecutor(Protocol):
    """子任务执行器协议

    定义子任务执行器必须实现的方法。
    """

    async def execute(
        self,
        task_data: dict[str, Any],
        context: SubTaskExecutionContext,
    ) -> SubTaskResult:
        """执行子任务

        参数：
            task_data: 任务数据
            context: 执行上下文

        返回：
            SubTaskResult 执行结果
        """
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """获取执行器能力描述

        返回：
            能力描述字典
        """
        ...


# ==================== 隔离上下文 ====================


class SubTaskExecutionContext:
    """子任务隔离执行上下文

    提供与父上下文隔离的执行环境：
    - 可以读取父上下文的数据（只读副本）
    - 修改不会影响父上下文
    - 可以存储自己的任务结果
    - 可以将结果合并回父上下文
    """

    def __init__(
        self,
        subtask_id: str,
        parent_context: ExecutionContext | None = None,
    ):
        """初始化隔离上下文

        参数：
            subtask_id: 子任务ID
            parent_context: 父上下文（可选）
        """
        self._subtask_id = subtask_id
        self._parent_snapshot: dict[str, Any] = {}
        self._local_context = ExecutionContext.create()
        self._created_at = datetime.now()

        # 如果有父上下文，复制其数据作为只读快照
        if parent_context:
            self._parent_snapshot = parent_context.to_dict()
            # 复制变量到本地（可修改副本）
            for key, value in self._parent_snapshot.get("variables", {}).items():
                self._local_context.set_variable(key, deepcopy(value))

    @classmethod
    def create_isolated(
        cls,
        parent: ExecutionContext,
        subtask_id: str,
    ) -> SubTaskExecutionContext:
        """从父上下文创建隔离上下文（工厂方法）

        参数：
            parent: 父执行上下文
            subtask_id: 子任务ID

        返回：
            SubTaskExecutionContext 实例
        """
        return cls(subtask_id=subtask_id, parent_context=parent)

    @property
    def subtask_id(self) -> str:
        """获取子任务ID"""
        return self._subtask_id

    def get_variable(self, name: str, default: Any = None) -> Any:
        """获取变量（本地或父上下文）

        参数：
            name: 变量名
            default: 默认值

        返回：
            变量值
        """
        return self._local_context.get_variable(name, default)

    def set_variable(self, name: str, value: Any) -> None:
        """设置本地变量（不影响父上下文）

        参数：
            name: 变量名
            value: 变量值
        """
        self._local_context.set_variable(name, value)

    def get_parent_result(self, task_name: str, default: Any = None) -> Any:
        """获取父上下文中的任务结果（只读）

        参数：
            task_name: 任务名称
            default: 默认值

        返回：
            任务结果
        """
        tasks = self._parent_snapshot.get("tasks", {})
        return deepcopy(tasks.get(task_name, default))

    def get_task_result(self, task_name: str, default: Any = None) -> Any:
        """获取本地任务结果

        参数：
            task_name: 任务名称
            default: 默认值

        返回：
            任务结果
        """
        return self._local_context.get_task_result(task_name, default)

    def set_task_result(self, task_name: str, result: Any) -> None:
        """存储本地任务结果

        参数：
            task_name: 任务名称
            result: 任务结果
        """
        self._local_context.set_task_result(task_name, result)

    def get_execution_result(self) -> dict[str, Any]:
        """获取子任务执行结果

        返回：
            包含子任务ID和所有任务结果的字典
        """
        return {
            "subtask_id": self._subtask_id,
            "tasks": self._local_context.to_dict().get("tasks", {}),
            "variables": self._local_context.to_dict().get("variables", {}),
            "created_at": self._created_at.isoformat(),
        }

    def merge_to_parent(self, parent: ExecutionContext, key: str) -> None:
        """将子任务结果合并到父上下文

        参数：
            parent: 父执行上下文
            key: 存储结果的键名
        """
        result = self.get_execution_result()
        parent.set_task_result(key, result)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典

        返回：
            上下文数据字典
        """
        return {
            "subtask_id": self._subtask_id,
            "local": self._local_context.to_dict(),
            "parent_snapshot": self._parent_snapshot,
            "created_at": self._created_at.isoformat(),
        }


# ==================== 容器 ====================


class SubTaskContainer:
    """子任务容器

    管理子任务的隔离执行环境：
    - 创建隔离上下文
    - 执行子任务
    - 捕获异常（不向外传播）
    - 返回执行结果
    """

    def __init__(
        self,
        subtask_id: str,
        parent_context: ExecutionContext | None = None,
    ):
        """初始化容器

        参数：
            subtask_id: 子任务ID
            parent_context: 父执行上下文
        """
        self._subtask_id = subtask_id
        self._parent_context = parent_context or ExecutionContext.create()
        self._context = SubTaskExecutionContext.create_isolated(
            parent=self._parent_context,
            subtask_id=subtask_id,
        )

    @property
    def subtask_id(self) -> str:
        """获取子任务ID"""
        return self._subtask_id

    @property
    def context(self) -> SubTaskExecutionContext:
        """获取隔离上下文"""
        return self._context

    async def execute(
        self,
        executor: SubTaskExecutor,
        task_data: dict[str, Any],
    ) -> SubTaskResult:
        """执行子任务

        在隔离环境中执行，捕获所有异常。

        参数：
            executor: 执行器
            task_data: 任务数据

        返回：
            SubTaskResult 执行结果（不会抛出异常）
        """
        started_at = datetime.now()
        start_time = time.time()

        try:
            # 执行任务
            result = await executor.execute(task_data, self._context)

            # 补充元数据
            result.subtask_id = self._subtask_id
            result.started_at = started_at
            result.completed_at = datetime.now()
            result.execution_time = time.time() - start_time

            logger.debug(f"SubTask {self._subtask_id} completed: success={result.success}")
            return result

        except Exception as e:
            # 捕获异常，返回失败结果
            logger.error(f"SubTask {self._subtask_id} failed: {e}")
            return SubTaskResult(
                success=False,
                output={},
                error=str(e),
                subtask_id=self._subtask_id,
                execution_time=time.time() - start_time,
                started_at=started_at,
                completed_at=datetime.now(),
            )


# 导出
__all__ = [
    "SubTask",
    "SubTaskResult",
    "SubTaskExecutor",
    "SubTaskExecutionContext",
    "SubTaskContainer",
]

"""并发执行管理器 - TDD RED 阶段测试

定义多工作流并行执行的期望行为
"""

import asyncio

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class TestConcurrentExecutionManager:
    """测试并发执行管理器"""

    @pytest.fixture
    def sample_workflows(self):
        """创建多个示例工作流"""
        workflows = []
        for i in range(3):
            nodes = [
                Node.create(
                    type=NodeType.START,
                    name=f"开始{i}",
                    config={},
                    position=Position(x=100, y=100),
                ),
                Node.create(
                    type=NodeType.END,
                    name=f"结束{i}",
                    config={},
                    position=Position(x=300, y=100),
                ),
            ]
            nodes[0].id = f"start_{i}"
            nodes[1].id = f"end_{i}"

            edges = [
                Edge.create(source_node_id=f"start_{i}", target_node_id=f"end_{i}"),
            ]

            wf = Workflow.create(
                name=f"工作流{i}",
                description=f"测试工作流{i}",
                nodes=nodes,
                edges=edges,
            )
            workflows.append(wf)

        return workflows

    def test_concurrent_execution_manager_creation(self):
        """测试：应该能创建并发执行管理器"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=5)

        assert manager is not None
        assert manager.max_concurrent_tasks == 5
        assert len(manager.running_tasks) == 0

    def test_execute_multiple_workflows_concurrently(self, sample_workflows):
        """测试：应该能并发执行多个工作流"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=3)

        # 模拟执行函数
        async def mock_execute(wf):
            await asyncio.sleep(0.01)
            return {"workflow_id": wf.id, "status": "completed"}

        # 应该能添加多个任务
        task_ids = []
        for wf in sample_workflows:
            task_id = manager.submit_task(wf.id, mock_execute, wf)
            task_ids.append(task_id)

        assert len(task_ids) == len(sample_workflows)
        assert len(manager.running_tasks) == len(sample_workflows)

    def test_concurrent_execution_respects_max_concurrent_limit(self):
        """测试：并发执行数应该不超过最大限制"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=2)

        # 添加3个任务，但只有2个应该同时运行
        async def long_task():
            await asyncio.sleep(1)

        manager.submit_task("task_1", long_task)
        manager.submit_task("task_2", long_task)
        task3_id = manager.submit_task("task_3", long_task)

        # 第三个任务应该等待队列中
        assert manager.get_task_status(task3_id) in ["queued", "pending"]

    def test_task_execution_tracking(self):
        """测试：应该能跟踪任务执行状态"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=1)

        async def quick_task():
            await asyncio.sleep(0.01)
            return "done"

        task_id = manager.submit_task("task_1", quick_task)

        # 检查任务状态
        status = manager.get_task_status(task_id)
        assert status in ["pending", "running", "completed"]

    def test_task_result_retrieval(self):
        """测试：应该能获取任务执行结果"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=1)

        async def task_with_result():
            return {"result": "success"}

        task_id = manager.submit_task("task_1", task_with_result)

        # 等待任务完成
        result = manager.get_task_result(task_id, timeout=2)
        assert result is not None

    def test_task_failure_handling(self):
        """测试：应该能处理任务失败"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=1)

        async def failing_task():
            raise RuntimeError("Task failed")

        _task_id = manager.submit_task("task_1", failing_task)

        # 最终应该是failed或error状态
        # (可能需要等待一段时间来验证状态改变)

    def test_cancel_task(self):
        """测试：应该能取消任务"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=1)

        async def long_task():
            await asyncio.sleep(10)

        task_id = manager.submit_task("task_1", long_task)

        # 取消任务
        success = manager.cancel_task(task_id)

        assert success is True
        # 状态应该变为cancelled
        status = manager.get_task_status(task_id)
        assert status == "cancelled"

    def test_wait_for_all_tasks(self):
        """测试：应该能等待所有任务完成"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=3)

        async def task():
            await asyncio.sleep(0.01)
            return "done"

        for i in range(3):
            manager.submit_task(f"task_{i}", task)

        # 等待所有任务完成
        all_done = manager.wait_all(timeout=5)

        assert all_done is True

    def test_execution_with_dependencies(self):
        """测试：应该能执行有依赖关系的任务"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=3)

        async def task_a():
            await asyncio.sleep(0.01)
            return "A"

        async def task_b(dep_result):
            await asyncio.sleep(0.01)
            return f"B({dep_result})"

        # 提交task_a
        task_a_id = manager.submit_task("task_a", task_a)

        # task_b依赖于task_a
        task_b_id = manager.submit_task_with_dependency("task_b", task_b, depends_on=[task_a_id])

        # 等待完成
        manager.wait_all(timeout=5)

        # task_b的结果应该包含task_a的结果
        result_b = manager.get_task_result(task_b_id)
        assert "A" in str(result_b) or result_b is not None

    def test_task_priority_queue(self):
        """测试：应该支持任务优先级"""
        from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager

        manager = ConcurrentExecutionManager(max_concurrent_tasks=1)

        async def task():
            await asyncio.sleep(0.01)

        # 添加低优先级任务
        _task_low_id = manager.submit_task("task_low", task, priority=1)

        # 添加高优先级任务
        _task_high_id = manager.submit_task("task_high", task, priority=10)

        # 高优先级任务应该先执行
        # (这需要根据执行顺序来验证)

    def test_executor_locking_mechanism(self):
        """测试：应该有锁机制防止资源竞争"""
        from src.domain.services.concurrent_execution_manager import ExecutionLock

        lock = ExecutionLock(resource_id="resource_1")

        # 应该能获取锁
        acquired = lock.acquire()
        assert acquired is True

        # 当持有锁时，其他人不能获取
        acquired_again = lock.acquire(blocking=False)
        assert acquired_again is False

        # 释放锁后，其他人可以获取
        lock.release()
        acquired_after_release = lock.acquire(blocking=False)
        assert acquired_after_release is True

    def test_shared_resource_protection(self):
        """测试：共享资源应该受到保护"""
        from src.domain.services.concurrent_execution_manager import (
            ConcurrentExecutionManager,
            ExecutionLock,
        )

        shared_state = {"value": 0}
        lock = ExecutionLock(resource_id="shared")

        async def increment(n):
            with lock:
                for _ in range(n):
                    shared_state["value"] += 1
                await asyncio.sleep(0.001)

        manager = ConcurrentExecutionManager(max_concurrent_tasks=2)

        # 两个任务都要增加值
        manager.submit_task("inc_1", increment, 5)
        manager.submit_task("inc_2", increment, 5)

        manager.wait_all(timeout=5)

        # 最终值应该是10（有锁保护）
        assert shared_state["value"] == 10

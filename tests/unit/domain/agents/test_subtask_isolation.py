"""子任务调度与隔离单元测试 - Phase 3

测试目标：
1. SubTaskExecutionContext 创建和隔离
2. SubTaskExecutor 协议和接口
3. spawn_subtask 创建隔离环境
4. 子任务执行结果汇总
5. 失败隔离验证（一个失败不影响其他）

运行命令：
    pytest tests/unit/domain/agents/test_subtask_isolation.py -v --tb=short
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.value_objects.execution_context import ExecutionContext

# === 测试：SubTaskExecutionContext ===


class TestSubTaskExecutionContext:
    """子任务执行上下文测试"""

    def test_create_isolated_context_from_parent(self):
        """测试：从父上下文创建隔离上下文"""
        # 导入待实现的类
        from src.domain.agents.subtask_executor import SubTaskExecutionContext

        parent = ExecutionContext.create()
        parent.set_variable("shared_key", "shared_value")
        parent.set_task_result("parent_task", {"data": "parent_data"})

        # 创建隔离子上下文
        child = SubTaskExecutionContext.create_isolated(parent, subtask_id="subtask_1")

        # 验证子上下文可以访问父数据（只读副本）
        assert child.get_variable("shared_key") == "shared_value"
        assert child.get_parent_result("parent_task") == {"data": "parent_data"}

        # 验证子上下文有独立标识
        assert child.subtask_id == "subtask_1"

    def test_child_modifications_do_not_affect_parent(self):
        """测试：子上下文修改不影响父上下文"""
        from src.domain.agents.subtask_executor import SubTaskExecutionContext

        parent = ExecutionContext.create()
        parent.set_variable("shared_key", "original_value")

        child = SubTaskExecutionContext.create_isolated(parent, subtask_id="subtask_1")

        # 子上下文修改变量
        child.set_variable("shared_key", "modified_value")
        child.set_variable("child_only", "child_value")

        # 验证父上下文不受影响
        assert parent.get_variable("shared_key") == "original_value"
        assert parent.get_variable("child_only") is None

    def test_child_stores_own_task_results(self):
        """测试：子上下文存储自己的任务结果"""
        from src.domain.agents.subtask_executor import SubTaskExecutionContext

        parent = ExecutionContext.create()
        child = SubTaskExecutionContext.create_isolated(parent, subtask_id="subtask_1")

        # 子上下文存储结果
        child.set_task_result("child_task", {"result": "child_result"})

        # 验证父上下文没有这个结果
        assert parent.get_task_result("child_task") is None
        assert child.get_task_result("child_task") == {"result": "child_result"}

    def test_get_execution_result_returns_child_data(self):
        """测试：获取子任务执行结果"""
        from src.domain.agents.subtask_executor import SubTaskExecutionContext

        parent = ExecutionContext.create()
        child = SubTaskExecutionContext.create_isolated(parent, subtask_id="subtask_1")

        child.set_task_result("step_1", {"output": "data1"})
        child.set_task_result("step_2", {"output": "data2"})

        result = child.get_execution_result()

        assert result["subtask_id"] == "subtask_1"
        assert "step_1" in result["tasks"]
        assert "step_2" in result["tasks"]

    def test_merge_result_to_parent(self):
        """测试：将子结果合并回父上下文"""
        from src.domain.agents.subtask_executor import SubTaskExecutionContext

        parent = ExecutionContext.create()
        child = SubTaskExecutionContext.create_isolated(parent, subtask_id="subtask_1")

        child.set_task_result("child_task", {"data": "child_data"})

        # 合并到父上下文
        child.merge_to_parent(parent, key="subtask_1_result")

        # 验证父上下文收到了子任务结果
        merged = parent.get_task_result("subtask_1_result")
        assert merged is not None
        assert merged["subtask_id"] == "subtask_1"


# === 测试：SubTaskExecutor Protocol ===


class TestSubTaskExecutorProtocol:
    """子任务执行器协议测试"""

    def test_executor_protocol_defines_execute_method(self):
        """测试：执行器协议定义 execute 方法"""
        from src.domain.agents.subtask_executor import SubTaskExecutor

        # 验证协议有 execute 方法
        assert hasattr(SubTaskExecutor, "execute")

    def test_executor_protocol_defines_get_capabilities(self):
        """测试：执行器协议定义 get_capabilities 方法"""
        from src.domain.agents.subtask_executor import SubTaskExecutor

        assert hasattr(SubTaskExecutor, "get_capabilities")


# === 测试：SubTaskContainer ===


class TestSubTaskContainer:
    """子任务容器测试"""

    def test_container_creates_isolated_environment(self):
        """测试：容器创建隔离执行环境"""
        from src.domain.agents.subtask_executor import SubTaskContainer

        parent = ExecutionContext.create()
        parent.set_variable("api_key", "secret")

        container = SubTaskContainer(subtask_id="container_1", parent_context=parent)

        # 验证容器有隔离上下文
        assert container.context is not None
        assert container.context.get_variable("api_key") == "secret"
        assert container.subtask_id == "container_1"

    @pytest.mark.asyncio
    async def test_container_execute_returns_result(self):
        """测试：容器执行返回结果"""
        from src.domain.agents.subtask_executor import (
            SubTaskContainer,
            SubTaskExecutor,
            SubTaskResult,
        )

        # Mock 执行器
        mock_executor = MagicMock(spec=SubTaskExecutor)
        mock_executor.execute = AsyncMock(
            return_value=SubTaskResult(
                success=True,
                output={"message": "done"},
                error=None,
            )
        )

        parent = ExecutionContext.create()
        container = SubTaskContainer(subtask_id="task_1", parent_context=parent)

        result = await container.execute(
            executor=mock_executor,
            task_data={"action": "process"},
        )

        assert result.success is True
        assert result.output == {"message": "done"}

    @pytest.mark.asyncio
    async def test_container_captures_failure_without_propagation(self):
        """测试：容器捕获失败，不向外传播异常"""
        from src.domain.agents.subtask_executor import (
            SubTaskContainer,
            SubTaskExecutor,
        )

        # Mock 执行器抛出异常
        mock_executor = MagicMock(spec=SubTaskExecutor)
        mock_executor.execute = AsyncMock(side_effect=Exception("Executor failed"))

        parent = ExecutionContext.create()
        container = SubTaskContainer(subtask_id="failing_task", parent_context=parent)

        # 执行不应抛出异常
        result = await container.execute(
            executor=mock_executor,
            task_data={},
        )

        # 验证结果标记为失败
        assert result.success is False
        assert "Executor failed" in result.error


# === 测试：ConversationEngine spawn_subtask ===


class TestEngineSpawnSubtask:
    """ConversationEngine spawn_subtask 测试"""

    @pytest.fixture
    def mock_executor(self):
        """模拟执行器"""
        from src.domain.agents.subtask_executor import SubTaskExecutor, SubTaskResult

        executor = MagicMock(spec=SubTaskExecutor)
        executor.execute = AsyncMock(
            return_value=SubTaskResult(
                success=True,
                output={"processed": True},
                error=None,
            )
        )
        return executor

    @pytest.mark.asyncio
    async def test_spawn_subtask_creates_isolated_context(self, mock_executor):
        """测试：spawn_subtask 创建隔离上下文"""
        from src.domain.agents.conversation_engine import ConversationEngine
        from src.domain.agents.subtask_executor import SubTask

        engine = ConversationEngine()
        engine._context = ExecutionContext.create()
        engine._context.set_variable("global_setting", "value")

        subtask = SubTask(
            id="subtask_1",
            description="处理数据",
            type="process",
        )

        result = await engine.spawn_subtask(
            subtask=subtask,
            executor=mock_executor,
        )

        # 验证执行器被调用
        mock_executor.execute.assert_called_once()

        # 验证结果
        assert result.success is True
        assert result.subtask_id == "subtask_1"

    @pytest.mark.asyncio
    async def test_spawn_subtask_result_contains_subtask_id(self, mock_executor):
        """测试：spawn_subtask 结果包含子任务ID"""
        from src.domain.agents.conversation_engine import ConversationEngine
        from src.domain.agents.subtask_executor import SubTask

        engine = ConversationEngine()

        subtask = SubTask(
            id="identified_task",
            description="任务",
        )

        result = await engine.spawn_subtask(
            subtask=subtask,
            executor=mock_executor,
        )

        assert result.subtask_id == "identified_task"


# === 测试：多子任务执行与汇总 ===


class TestMultipleSubtaskExecution:
    """多子任务执行与汇总测试"""

    @pytest.mark.asyncio
    async def test_execute_multiple_subtasks_aggregates_results(self):
        """测试：执行多个子任务并汇总结果"""
        from src.domain.agents.conversation_engine import ConversationEngine
        from src.domain.agents.subtask_executor import (
            SubTask,
            SubTaskExecutor,
            SubTaskResult,
        )

        # 创建多个执行器
        def create_executor(output_value: str):
            executor = MagicMock(spec=SubTaskExecutor)
            executor.execute = AsyncMock(
                return_value=SubTaskResult(
                    success=True,
                    output={"value": output_value},
                    error=None,
                )
            )
            return executor

        executor_1 = create_executor("result_1")
        executor_2 = create_executor("result_2")
        executor_3 = create_executor("result_3")

        engine = ConversationEngine()

        subtasks = [
            SubTask(id="task_1", description="任务1"),
            SubTask(id="task_2", description="任务2"),
            SubTask(id="task_3", description="任务3"),
        ]
        executors = [executor_1, executor_2, executor_3]

        # 执行所有子任务
        results = await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
        )

        # 验证所有结果
        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].output == {"value": "result_1"}
        assert results[1].output == {"value": "result_2"}
        assert results[2].output == {"value": "result_3"}

    @pytest.mark.asyncio
    async def test_aggregate_results_merges_to_engine_context(self):
        """测试：汇总结果合并到引擎上下文"""
        from src.domain.agents.conversation_engine import ConversationEngine
        from src.domain.agents.subtask_executor import (
            SubTask,
            SubTaskExecutor,
            SubTaskResult,
        )

        def create_executor(output: dict):
            executor = MagicMock(spec=SubTaskExecutor)
            executor.execute = AsyncMock(
                return_value=SubTaskResult(success=True, output=output, error=None)
            )
            return executor

        engine = ConversationEngine()
        engine._context = ExecutionContext.create()

        subtasks = [
            SubTask(id="fetch", description="获取数据"),
            SubTask(id="process", description="处理数据"),
        ]
        executors = [
            create_executor({"data": [1, 2, 3]}),
            create_executor({"processed": True}),
        ]

        await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
        )

        # 验证结果被合并到引擎上下文
        fetch_result = engine._context.get_task_result("fetch")
        process_result = engine._context.get_task_result("process")

        assert fetch_result is not None
        assert process_result is not None


# === 测试：失败隔离 ===


class TestFailureIsolation:
    """失败隔离测试"""

    @pytest.mark.asyncio
    async def test_one_subtask_failure_does_not_affect_others(self):
        """测试：一个子任务失败不影响其他子任务"""
        from src.domain.agents.conversation_engine import ConversationEngine
        from src.domain.agents.subtask_executor import (
            SubTask,
            SubTaskExecutor,
            SubTaskResult,
        )

        def create_success_executor(value: str):
            executor = MagicMock(spec=SubTaskExecutor)
            executor.execute = AsyncMock(
                return_value=SubTaskResult(success=True, output={"value": value}, error=None)
            )
            return executor

        def create_failing_executor():
            executor = MagicMock(spec=SubTaskExecutor)
            executor.execute = AsyncMock(side_effect=Exception("Task failed intentionally"))
            return executor

        engine = ConversationEngine()

        subtasks = [
            SubTask(id="task_1", description="成功任务1"),
            SubTask(id="task_2", description="失败任务"),
            SubTask(id="task_3", description="成功任务2"),
        ]
        executors = [
            create_success_executor("success_1"),
            create_failing_executor(),
            create_success_executor("success_3"),
        ]

        results = await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
        )

        # 验证第一个和第三个成功
        assert results[0].success is True
        assert results[0].output == {"value": "success_1"}

        assert results[2].success is True
        assert results[2].output == {"value": "success_3"}

        # 验证第二个失败
        assert results[1].success is False
        assert "Task failed intentionally" in results[1].error

    @pytest.mark.asyncio
    async def test_failed_subtask_context_does_not_pollute_others(self):
        """测试：失败子任务的上下文不污染其他任务"""
        from src.domain.agents.subtask_executor import (
            SubTaskContainer,
            SubTaskExecutor,
        )

        parent = ExecutionContext.create()
        parent.set_variable("clean_value", "original")

        # 创建会修改上下文并失败的执行器
        def create_polluting_executor():
            async def pollute_and_fail(task_data, context):
                # 尝试污染上下文
                context.set_variable("polluted_key", "polluted_value")
                context.set_variable("clean_value", "polluted")
                raise Exception("Intentional failure")

            executor = MagicMock(spec=SubTaskExecutor)
            executor.execute = pollute_and_fail
            return executor

        # 执行失败的子任务
        container = SubTaskContainer(subtask_id="failing", parent_context=parent)
        polluting_executor = create_polluting_executor()

        await container.execute(executor=polluting_executor, task_data={})

        # 验证父上下文未被污染
        assert parent.get_variable("clean_value") == "original"
        assert parent.get_variable("polluted_key") is None

    @pytest.mark.asyncio
    async def test_parallel_execution_maintains_isolation(self):
        """测试：并行执行保持隔离"""
        from src.domain.agents.conversation_engine import ConversationEngine
        from src.domain.agents.subtask_executor import (
            SubTask,
            SubTaskExecutor,
            SubTaskResult,
        )

        results_order = []

        def create_delayed_executor(task_id: str, delay: float, value: str):
            async def execute_with_delay(task_data, context):
                await asyncio.sleep(delay)
                results_order.append(task_id)
                # 每个执行器修改自己的上下文
                context.set_variable(f"{task_id}_marker", value)
                return SubTaskResult(
                    success=True,
                    output={"task_id": task_id, "value": value},
                    error=None,
                )

            executor = MagicMock(spec=SubTaskExecutor)
            executor.execute = execute_with_delay
            return executor

        engine = ConversationEngine()

        subtasks = [
            SubTask(id="slow_task", description="慢任务"),
            SubTask(id="fast_task", description="快任务"),
        ]
        executors = [
            create_delayed_executor("slow_task", 0.1, "slow_value"),
            create_delayed_executor("fast_task", 0.01, "fast_value"),
        ]

        results = await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
            parallel=True,
        )

        # 验证两个任务都成功
        assert len(results) == 2
        assert all(r.success for r in results)

        # 验证快任务先完成（并行执行）
        assert results_order == ["fast_task", "slow_task"]


# === 测试：SubTaskResult 数据结构 ===


class TestSubTaskResult:
    """SubTaskResult 数据结构测试"""

    def test_subtask_result_has_required_fields(self):
        """测试：SubTaskResult 有必需字段"""
        from src.domain.agents.subtask_executor import SubTaskResult

        result = SubTaskResult(
            success=True,
            output={"data": "value"},
            error=None,
            subtask_id="task_1",
        )

        assert result.success is True
        assert result.output == {"data": "value"}
        assert result.error is None
        assert result.subtask_id == "task_1"

    def test_subtask_result_to_dict(self):
        """测试：SubTaskResult 可序列化"""
        from src.domain.agents.subtask_executor import SubTaskResult

        result = SubTaskResult(
            success=False,
            output={},
            error="Something went wrong",
            subtask_id="failed_task",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["error"] == "Something went wrong"
        assert data["subtask_id"] == "failed_task"


# === 测试：SubTask 增强 ===


class TestSubTaskEnhancement:
    """SubTask 增强测试"""

    def test_subtask_has_executor_type_field(self):
        """测试：SubTask 有执行器类型字段"""
        from src.domain.agents.subtask_executor import SubTask

        subtask = SubTask(
            id="task_1",
            description="处理任务",
            executor_type="python",
        )

        assert subtask.executor_type == "python"

    def test_subtask_has_timeout_field(self):
        """测试：SubTask 有超时字段"""
        from src.domain.agents.subtask_executor import SubTask

        subtask = SubTask(
            id="task_1",
            description="长任务",
            timeout=30.0,
        )

        assert subtask.timeout == 30.0


# 导出
__all__ = [
    "TestSubTaskExecutionContext",
    "TestSubTaskExecutorProtocol",
    "TestSubTaskContainer",
    "TestEngineSpawnSubtask",
    "TestMultipleSubtaskExecution",
    "TestFailureIsolation",
    "TestSubTaskResult",
    "TestSubTaskEnhancement",
]

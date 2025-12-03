"""子任务调度与隔离集成测试 - Phase 3

测试目标：
1. 主任务分解为多个子任务，分别执行并汇总结果
2. 确保一个子任务失败不会污染其他任务的上下文
3. 真实场景端到端验证

运行命令：
    pytest tests/integration/test_subtask_isolation_e2e.py -v -s
"""

import asyncio
from typing import Any

import pytest

from src.domain.agents.conversation_engine import ConversationEngine
from src.domain.agents.subtask_executor import (
    SubTask,
    SubTaskContainer,
    SubTaskExecutionContext,
    SubTaskResult,
)
from src.domain.value_objects.execution_context import ExecutionContext

# === Mock 执行器实现 ===


class DataFetchExecutor:
    """数据获取执行器"""

    def __init__(self, data: list[dict]):
        self._data = data

    async def execute(
        self, task_data: dict[str, Any], context: SubTaskExecutionContext
    ) -> SubTaskResult:
        # 模拟数据获取
        await asyncio.sleep(0.01)

        # 存储到上下文
        context.set_task_result("fetched_data", self._data)

        return SubTaskResult(
            success=True,
            output={"records": len(self._data), "data": self._data},
            error=None,
        )

    def get_capabilities(self) -> dict[str, Any]:
        return {"type": "data_fetch", "supports": ["json", "csv"]}


class DataProcessExecutor:
    """数据处理执行器"""

    def __init__(self, transform_fn=None):
        self._transform = transform_fn or (lambda x: x)

    async def execute(
        self, task_data: dict[str, Any], context: SubTaskExecutionContext
    ) -> SubTaskResult:
        await asyncio.sleep(0.01)

        # 尝试从父上下文获取数据
        parent_data = context.get_parent_result("fetch_task")
        if parent_data:
            processed = self._transform(parent_data)
        else:
            processed = {"transformed": True}

        context.set_task_result("processed_data", processed)

        return SubTaskResult(
            success=True,
            output={"processed": True, "result": processed},
            error=None,
        )

    def get_capabilities(self) -> dict[str, Any]:
        return {"type": "data_process", "supports": ["transform", "aggregate"]}


class FailingExecutor:
    """故意失败的执行器"""

    def __init__(self, error_message: str = "Intentional failure"):
        self._error = error_message

    async def execute(
        self, task_data: dict[str, Any], context: SubTaskExecutionContext
    ) -> SubTaskResult:
        # 在失败前尝试污染上下文
        context.set_variable("polluted_by_failure", True)
        context.set_task_result("partial_work", {"incomplete": True})

        raise Exception(self._error)

    def get_capabilities(self) -> dict[str, Any]:
        return {"type": "failing", "supports": []}


class ContextModifyingExecutor:
    """会修改上下文的执行器"""

    def __init__(self, key: str, value: Any):
        self._key = key
        self._value = value

    async def execute(
        self, task_data: dict[str, Any], context: SubTaskExecutionContext
    ) -> SubTaskResult:
        # 修改上下文
        context.set_variable(self._key, self._value)
        context.set_task_result(f"{self._key}_result", {"modified": True})

        return SubTaskResult(
            success=True,
            output={"key": self._key, "value": self._value},
            error=None,
        )

    def get_capabilities(self) -> dict[str, Any]:
        return {"type": "context_modifier"}


# === 集成测试类 ===


class TestSubtaskDecompositionAndAggregation:
    """主任务分解与结果汇总集成测试"""

    @pytest.mark.asyncio
    async def test_decompose_execute_aggregate_workflow(self):
        """测试：完整的分解-执行-汇总工作流"""
        engine = ConversationEngine()

        # 创建三个子任务
        subtasks = [
            SubTask(id="fetch", description="获取数据", type="io"),
            SubTask(id="process", description="处理数据", type="compute"),
            SubTask(id="store", description="存储结果", type="io"),
        ]

        # 创建对应的执行器
        executors = [
            DataFetchExecutor(data=[{"id": 1}, {"id": 2}, {"id": 3}]),
            DataProcessExecutor(
                transform_fn=lambda x: {"count": len(x) if isinstance(x, list) else 0}
            ),
            ContextModifyingExecutor(key="stored", value=True),
        ]

        # 执行所有子任务
        results = await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
        )

        # 验证所有任务成功
        assert len(results) == 3
        assert all(r.success for r in results)

        # 验证结果被正确汇总
        assert results[0].output["records"] == 3
        assert results[1].output["processed"] is True
        assert results[2].output["key"] == "stored"

    @pytest.mark.asyncio
    async def test_results_merged_to_engine_context(self):
        """测试：结果正确合并到引擎上下文"""
        engine = ConversationEngine()
        engine._context = ExecutionContext.create()
        engine._context.set_variable("global_config", "test_value")

        subtasks = [
            SubTask(id="task_a", description="任务A"),
            SubTask(id="task_b", description="任务B"),
        ]

        executors = [
            DataFetchExecutor(data=[{"x": 1}]),
            DataProcessExecutor(),
        ]

        await engine.execute_subtasks_isolated(subtasks, executors)

        # 验证引擎上下文包含子任务结果
        result_a = engine._context.get_task_result("task_a")
        result_b = engine._context.get_task_result("task_b")

        assert result_a is not None
        assert result_a["success"] is True
        assert result_b is not None
        assert result_b["success"] is True

    @pytest.mark.asyncio
    async def test_parallel_execution_aggregates_correctly(self):
        """测试：并行执行正确汇总结果"""
        engine = ConversationEngine()

        # 创建多个任务
        subtasks = [SubTask(id=f"parallel_{i}", description=f"并行任务{i}") for i in range(5)]

        executors = [ContextModifyingExecutor(key=f"key_{i}", value=f"value_{i}") for i in range(5)]

        results = await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
            parallel=True,
        )

        # 验证所有任务完成
        assert len(results) == 5
        assert all(r.success for r in results)

        # 验证每个任务有独立的结果
        for i, result in enumerate(results):
            assert result.subtask_id == f"parallel_{i}"
            assert result.output["key"] == f"key_{i}"


class TestFailureIsolationE2E:
    """失败隔离端到端测试"""

    @pytest.mark.asyncio
    async def test_one_failure_does_not_affect_others(self):
        """测试：一个子任务失败不影响其他子任务执行"""
        engine = ConversationEngine()

        subtasks = [
            SubTask(id="success_1", description="成功任务1"),
            SubTask(id="failing", description="失败任务"),
            SubTask(id="success_2", description="成功任务2"),
        ]

        executors = [
            DataFetchExecutor(data=[{"ok": True}]),
            FailingExecutor("Database connection failed"),
            DataProcessExecutor(),
        ]

        results = await engine.execute_subtasks_isolated(subtasks, executors)

        # 验证第一个和第三个成功
        assert results[0].success is True
        assert results[0].subtask_id == "success_1"

        assert results[2].success is True
        assert results[2].subtask_id == "success_2"

        # 验证第二个失败
        assert results[1].success is False
        assert "Database connection failed" in results[1].error

    @pytest.mark.asyncio
    async def test_failed_task_context_isolated_from_parent(self):
        """测试：失败任务的上下文修改不影响父上下文"""
        parent = ExecutionContext.create()
        parent.set_variable("clean_data", "original_value")

        container = SubTaskContainer(
            subtask_id="polluting_task",
            parent_context=parent,
        )

        failing_executor = FailingExecutor("Crash!")

        # 执行失败的任务
        result = await container.execute(
            executor=failing_executor,
            task_data={},
        )

        # 验证父上下文未被污染
        assert parent.get_variable("clean_data") == "original_value"
        assert parent.get_variable("polluted_by_failure") is None
        assert parent.get_task_result("partial_work") is None

        # 验证失败被记录
        assert result.success is False

    @pytest.mark.asyncio
    async def test_parallel_failure_isolation(self):
        """测试：并行执行时失败隔离"""
        engine = ConversationEngine()
        engine._context = ExecutionContext.create()
        engine._context.set_variable("shared_config", "protected")

        subtasks = [
            SubTask(id="fast_fail", description="快速失败"),
            SubTask(id="slow_success", description="慢速成功"),
            SubTask(id="fast_success", description="快速成功"),
        ]

        class SlowSuccessExecutor:
            async def execute(self, task_data, context):
                await asyncio.sleep(0.05)  # 较慢
                return SubTaskResult(success=True, output={"slow": True}, error=None)

            def get_capabilities(self):
                return {}

        class FastSuccessExecutor:
            async def execute(self, task_data, context):
                await asyncio.sleep(0.01)
                return SubTaskResult(success=True, output={"fast": True}, error=None)

            def get_capabilities(self):
                return {}

        executors = [
            FailingExecutor("Fast failure"),
            SlowSuccessExecutor(),
            FastSuccessExecutor(),
        ]

        results = await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
            parallel=True,
        )

        # 验证失败和成功任务
        assert results[0].success is False
        assert results[1].success is True
        assert results[2].success is True

        # 验证引擎上下文仍然干净
        assert engine._context.get_variable("shared_config") == "protected"


class TestContextIsolationE2E:
    """上下文隔离端到端测试"""

    @pytest.mark.asyncio
    async def test_subtasks_cannot_see_each_other_modifications(self):
        """测试：子任务不能看到其他子任务的修改"""
        engine = ConversationEngine()
        engine._context = ExecutionContext.create()

        # 用于记录每个任务看到的上下文状态
        observed_states = []

        class ObservingExecutor:
            def __init__(self, task_id: str):
                self._task_id = task_id

            async def execute(self, task_data, context):
                # 记录当前能看到的变量
                state = {
                    "task_id": self._task_id,
                    "can_see_task1_mark": context.get_variable("task1_mark") is not None,
                    "can_see_task2_mark": context.get_variable("task2_mark") is not None,
                    "can_see_task3_mark": context.get_variable("task3_mark") is not None,
                }
                observed_states.append(state)

                # 设置自己的标记
                context.set_variable(f"{self._task_id}_mark", True)

                return SubTaskResult(success=True, output=state, error=None)

            def get_capabilities(self):
                return {}

        subtasks = [
            SubTask(id="task1", description="任务1"),
            SubTask(id="task2", description="任务2"),
            SubTask(id="task3", description="任务3"),
        ]

        executors = [
            ObservingExecutor("task1"),
            ObservingExecutor("task2"),
            ObservingExecutor("task3"),
        ]

        # 顺序执行
        await engine.execute_subtasks_isolated(subtasks, executors, parallel=False)

        # 验证每个任务都看不到其他任务的修改（因为是隔离的）
        for state in observed_states:
            # 由于隔离，每个任务都看不到其他任务的标记
            assert state["can_see_task1_mark"] is False
            assert state["can_see_task2_mark"] is False
            assert state["can_see_task3_mark"] is False

    @pytest.mark.asyncio
    async def test_subtask_can_read_parent_context(self):
        """测试：子任务可以读取父上下文"""
        engine = ConversationEngine()
        engine._context = ExecutionContext.create()
        engine._context.set_variable("parent_api_key", "secret-key-123")
        engine._context.set_task_result("previous_step", {"data": "from_parent"})

        class ReadingExecutor:
            async def execute(self, task_data, context):
                api_key = context.get_variable("parent_api_key")
                parent_data = context.get_parent_result("previous_step")

                return SubTaskResult(
                    success=True,
                    output={
                        "read_api_key": api_key,
                        "read_parent_data": parent_data,
                    },
                    error=None,
                )

            def get_capabilities(self):
                return {}

        subtasks = [SubTask(id="reader", description="读取父上下文")]
        executors = [ReadingExecutor()]

        results = await engine.execute_subtasks_isolated(subtasks, executors)

        # 验证子任务能读取父上下文
        assert results[0].output["read_api_key"] == "secret-key-123"
        assert results[0].output["read_parent_data"] == {"data": "from_parent"}


class TestRealWorldScenario:
    """真实场景测试"""

    @pytest.mark.asyncio
    async def test_data_pipeline_with_failure_recovery(self):
        """测试：数据管道场景，包含失败恢复"""
        engine = ConversationEngine()

        # 模拟数据管道：获取 -> 验证 -> 转换 -> 存储
        subtasks = [
            SubTask(id="fetch", description="获取原始数据", priority=1),
            SubTask(id="validate", description="验证数据格式", priority=2),
            SubTask(id="transform", description="转换数据", priority=3),
            SubTask(id="store", description="存储结果", priority=4),
        ]

        # 验证步骤会失败
        class ValidateExecutor:
            async def execute(self, task_data, context):
                # 模拟验证失败
                raise ValueError("Data validation failed: missing required field")

            def get_capabilities(self):
                return {}

        executors = [
            DataFetchExecutor(data=[{"name": "test"}]),
            ValidateExecutor(),
            DataProcessExecutor(),
            ContextModifyingExecutor(key="stored", value=True),
        ]

        results = await engine.execute_subtasks_isolated(subtasks, executors)

        # 验证失败被正确隔离
        assert results[0].success is True  # fetch 成功
        assert results[1].success is False  # validate 失败
        assert "validation failed" in results[1].error.lower()
        assert results[2].success is True  # transform 仍然成功
        assert results[3].success is True  # store 仍然成功

    @pytest.mark.asyncio
    async def test_concurrent_api_calls_scenario(self):
        """测试：并发 API 调用场景"""
        engine = ConversationEngine()

        call_times = []

        class APICallExecutor:
            def __init__(self, api_name: str, delay: float):
                self._api_name = api_name
                self._delay = delay

            async def execute(self, task_data, context):
                start = asyncio.get_event_loop().time()
                await asyncio.sleep(self._delay)
                end = asyncio.get_event_loop().time()

                call_times.append(
                    {
                        "api": self._api_name,
                        "duration": end - start,
                    }
                )

                return SubTaskResult(
                    success=True,
                    output={"api": self._api_name, "response": f"data_from_{self._api_name}"},
                    error=None,
                )

            def get_capabilities(self):
                return {}

        subtasks = [
            SubTask(id="api_users", description="获取用户API"),
            SubTask(id="api_orders", description="获取订单API"),
            SubTask(id="api_products", description="获取产品API"),
        ]

        executors = [
            APICallExecutor("users", 0.05),
            APICallExecutor("orders", 0.03),
            APICallExecutor("products", 0.04),
        ]

        import time

        start_time = time.time()
        results = await engine.execute_subtasks_isolated(
            subtasks=subtasks,
            executors=executors,
            parallel=True,
        )
        total_time = time.time() - start_time

        # 验证所有调用成功
        assert all(r.success for r in results)
        assert len(results) == 3

        # 验证并行执行（总时间应该接近最长单个任务的时间，而不是所有任务时间之和）
        # 串行: ~0.12s, 并行: ~0.05s
        assert total_time < 0.1  # 并行执行应该很快


# 导出
__all__ = [
    "TestSubtaskDecompositionAndAggregation",
    "TestFailureIsolationE2E",
    "TestContextIsolationE2E",
    "TestRealWorldScenario",
]

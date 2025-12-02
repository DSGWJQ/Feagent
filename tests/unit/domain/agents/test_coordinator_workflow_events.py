"""Phase 12: 协调者订阅 workflow 事件 - TDD 测试

测试 CoordinatorAgent 监听工作流事件并根据策略处理失败：
1. 失败处理策略（retry/skip/abort/replan）
2. 重试机制（通过 WorkflowAgent）
3. 跳过/终止策略
4. 发布 WorkflowAdjustmentRequestedEvent
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.agents.coordinator_agent import CoordinatorAgent
from src.domain.services.event_bus import Event, EventBus

# ==================== Phase 12.1: 失败处理策略定义 ====================


class TestFailureHandlingStrategy:
    """测试失败处理策略枚举"""

    def test_strategy_enum_has_retry(self):
        """测试：策略枚举应包含 RETRY"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        assert hasattr(FailureHandlingStrategy, "RETRY")
        assert FailureHandlingStrategy.RETRY.value == "retry"

    def test_strategy_enum_has_skip(self):
        """测试：策略枚举应包含 SKIP"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        assert hasattr(FailureHandlingStrategy, "SKIP")
        assert FailureHandlingStrategy.SKIP.value == "skip"

    def test_strategy_enum_has_abort(self):
        """测试：策略枚举应包含 ABORT"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        assert hasattr(FailureHandlingStrategy, "ABORT")
        assert FailureHandlingStrategy.ABORT.value == "abort"

    def test_strategy_enum_has_replan(self):
        """测试：策略枚举应包含 REPLAN"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        assert hasattr(FailureHandlingStrategy, "REPLAN")
        assert FailureHandlingStrategy.REPLAN.value == "replan"


class TestWorkflowAdjustmentRequestedEvent:
    """测试工作流调整请求事件"""

    def test_event_creation(self):
        """测试：应能创建 WorkflowAdjustmentRequestedEvent"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        event = WorkflowAdjustmentRequestedEvent(
            source="coordinator_agent",
            workflow_id="wf_1",
            failed_node_id="node_1",
            failure_reason="Timeout",
            suggested_action="replan",
        )

        assert event.workflow_id == "wf_1"
        assert event.failed_node_id == "node_1"
        assert event.failure_reason == "Timeout"
        assert event.suggested_action == "replan"

    def test_event_inherits_from_base_event(self):
        """测试：事件应继承自 Event 基类"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        event = WorkflowAdjustmentRequestedEvent(
            workflow_id="wf_1",
            failed_node_id="node_1",
            failure_reason="Error",
            suggested_action="retry",
        )

        assert isinstance(event, Event)
        assert hasattr(event, "id")
        assert hasattr(event, "timestamp")


class TestNodeFailureHandledEvent:
    """测试节点失败处理完成事件"""

    def test_event_creation(self):
        """测试：应能创建 NodeFailureHandledEvent"""
        from src.domain.agents.coordinator_agent import NodeFailureHandledEvent

        event = NodeFailureHandledEvent(
            source="coordinator_agent",
            workflow_id="wf_1",
            node_id="node_1",
            strategy="retry",
            success=True,
            retry_count=2,
        )

        assert event.workflow_id == "wf_1"
        assert event.node_id == "node_1"
        assert event.strategy == "retry"
        assert event.success is True
        assert event.retry_count == 2


# ==================== Phase 12.2: 失败处理策略配置 ====================


class TestFailureStrategyConfiguration:
    """测试失败策略配置"""

    def test_coordinator_accepts_failure_strategy_config(self):
        """测试：CoordinatorAgent 应接受失败策略配置"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        config = {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": 3,
            "retry_delay": 1.0,
        }

        agent = CoordinatorAgent(failure_strategy_config=config)

        assert agent.failure_strategy_config is not None
        assert agent.failure_strategy_config["default_strategy"] == FailureHandlingStrategy.RETRY

    def test_coordinator_has_default_failure_config(self):
        """测试：CoordinatorAgent 应有默认失败策略配置"""
        agent = CoordinatorAgent()

        assert agent.failure_strategy_config is not None
        assert "default_strategy" in agent.failure_strategy_config

    def test_set_node_failure_strategy(self):
        """测试：应能为特定节点设置失败策略"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        agent = CoordinatorAgent()
        agent.set_node_failure_strategy("node_1", FailureHandlingStrategy.SKIP)

        strategy = agent.get_node_failure_strategy("node_1")
        assert strategy == FailureHandlingStrategy.SKIP

    def test_get_node_failure_strategy_returns_default(self):
        """测试：未配置的节点应返回默认策略"""

        agent = CoordinatorAgent()

        strategy = agent.get_node_failure_strategy("unknown_node")
        assert strategy == agent.failure_strategy_config["default_strategy"]


# ==================== Phase 12.3: 节点失败时重试 ====================


class TestNodeFailureRetry:
    """测试节点失败重试机制"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        config = {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": 3,
            "retry_delay": 0.01,  # 快速测试
        }
        return CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

    @pytest.fixture
    def mock_workflow_agent(self):
        agent = MagicMock()
        agent.execute_node_with_result = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_handle_node_failure_triggers_retry(self, coordinator, mock_workflow_agent):
        """测试：节点失败时应触发重试"""
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        # 设置 mock：第一次失败，第二次成功
        mock_workflow_agent.execute_node_with_result.side_effect = [
            ExecutionResult.failure(ErrorCode.TIMEOUT, "Timeout"),
            ExecutionResult.ok({"result": "success"}),
        ]

        coordinator.register_workflow_agent("wf_1", mock_workflow_agent)

        result = await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.TIMEOUT,
            error_message="Timeout",
        )

        assert result.success is True
        assert mock_workflow_agent.execute_node_with_result.call_count >= 1

    @pytest.mark.asyncio
    async def test_retry_respects_max_retries(self, coordinator, mock_workflow_agent):
        """测试：重试应遵守最大重试次数"""
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        # 所有尝试都失败
        mock_workflow_agent.execute_node_with_result.return_value = ExecutionResult.failure(
            ErrorCode.TIMEOUT, "Always timeout"
        )

        coordinator.register_workflow_agent("wf_1", mock_workflow_agent)

        result = await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.TIMEOUT,
            error_message="Timeout",
        )

        assert result.success is False
        # 应该尝试 max_retries 次
        assert mock_workflow_agent.execute_node_with_result.call_count <= 3

    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self, coordinator, mock_workflow_agent):
        """测试：不可重试的错误不应重试"""
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        mock_workflow_agent.execute_node_with_result.return_value = ExecutionResult.failure(
            ErrorCode.VALIDATION_FAILED, "Invalid input"
        )

        coordinator.register_workflow_agent("wf_1", mock_workflow_agent)

        result = await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.VALIDATION_FAILED,
            error_message="Invalid input",
        )

        # 不可重试的错误应该立即返回失败
        assert result.success is False
        # 不应该调用重试
        assert mock_workflow_agent.execute_node_with_result.call_count == 0


# ==================== Phase 12.4: 跳过和终止策略 ====================


class TestSkipAndAbortStrategy:
    """测试跳过和终止策略"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        config = {
            "default_strategy": FailureHandlingStrategy.ABORT,
            "max_retries": 3,
        }
        return CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

    @pytest.mark.asyncio
    async def test_skip_strategy_marks_node_skipped(self, coordinator):
        """测试：SKIP 策略应标记节点为已跳过"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy
        from src.domain.services.execution_result import ErrorCode

        coordinator.set_node_failure_strategy("node_1", FailureHandlingStrategy.SKIP)

        result = await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.TIMEOUT,
            error_message="Timeout",
        )

        # SKIP 策略返回特殊的"跳过"结果
        assert result.skipped is True
        assert result.success is True  # 跳过视为成功继续

    @pytest.mark.asyncio
    async def test_abort_strategy_stops_workflow(self, coordinator):
        """测试：ABORT 策略应停止工作流"""
        from src.domain.services.execution_result import ErrorCode

        result = await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message="Fatal error",
        )

        assert result.success is False
        assert result.aborted is True

    @pytest.mark.asyncio
    async def test_abort_publishes_workflow_aborted_event(self, coordinator, event_bus):
        """测试：ABORT 策略应发布工作流终止事件"""
        from src.domain.agents.coordinator_agent import WorkflowAbortedEvent
        from src.domain.services.execution_result import ErrorCode

        events_received = []

        async def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(WorkflowAbortedEvent, capture_event)

        await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message="Fatal error",
        )

        assert len(events_received) == 1
        assert events_received[0].workflow_id == "wf_1"


# ==================== Phase 12.5: 重新规划事件发布 ====================


class TestReplanStrategy:
    """测试重新规划策略"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        config = {
            "default_strategy": FailureHandlingStrategy.REPLAN,
            "max_retries": 3,
        }
        return CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

    @pytest.mark.asyncio
    async def test_replan_publishes_adjustment_event(self, coordinator, event_bus):
        """测试：REPLAN 策略应发布 WorkflowAdjustmentRequestedEvent"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent
        from src.domain.services.execution_result import ErrorCode

        events_received = []

        async def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(WorkflowAdjustmentRequestedEvent, capture_event)

        await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.DEPENDENCY_FAILED,
            error_message="Upstream failed",
        )

        assert len(events_received) == 1
        event = events_received[0]
        assert event.workflow_id == "wf_1"
        assert event.failed_node_id == "node_1"
        assert event.suggested_action == "replan"

    @pytest.mark.asyncio
    async def test_replan_includes_execution_context(self, coordinator, event_bus):
        """测试：REPLAN 事件应包含执行上下文"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent
        from src.domain.services.execution_result import ErrorCode

        # 先设置一些执行上下文
        coordinator.workflow_states["wf_1"] = {
            "workflow_id": "wf_1",
            "status": "running",
            "executed_nodes": ["node_0"],
            "node_outputs": {"node_0": {"result": "step1_done"}},
        }

        events_received = []

        async def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(WorkflowAdjustmentRequestedEvent, capture_event)

        await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.DEPENDENCY_FAILED,
            error_message="Upstream failed",
        )

        event = events_received[0]
        assert event.execution_context is not None
        assert "executed_nodes" in event.execution_context
        assert "node_0" in event.execution_context["executed_nodes"]


# ==================== Phase 12.6: 自动失败处理集成 ====================


class TestAutomaticFailureHandling:
    """测试自动失败处理（通过事件监听）"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        config = {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": 2,
            "retry_delay": 0.01,
        }
        agent = CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)
        agent.start_monitoring()
        return agent

    @pytest.mark.asyncio
    async def test_node_failure_event_triggers_handling(self, coordinator, event_bus):
        """测试：节点失败应能通过 handle_node_failure 处理"""
        from src.domain.agents.coordinator_agent import NodeFailureHandledEvent
        from src.domain.services.execution_result import ErrorCode

        # 记录接收的事件
        events_received = []

        async def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(NodeFailureHandledEvent, capture_event)

        # 模拟 WorkflowAgent
        mock_agent = MagicMock()
        mock_agent.execute_node_with_result = AsyncMock(
            return_value=MagicMock(success=True, output={"result": "ok"})
        )
        coordinator.register_workflow_agent("wf_1", mock_agent)

        # 初始化工作流状态
        coordinator.workflow_states["wf_1"] = {
            "workflow_id": "wf_1",
            "status": "running",
            "executed_nodes": [],
            "running_nodes": [],
            "failed_nodes": [],
            "node_inputs": {},
            "node_outputs": {},
            "node_errors": {},
        }

        # 直接调用失败处理（模拟事件触发后的处理）
        result = await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.TIMEOUT,
            error_message="Timeout error",
        )

        # 等待异步处理
        await asyncio.sleep(0.05)

        # 验证处理成功
        assert result.success is True
        # 验证发布了处理结果事件
        assert len(events_received) >= 1


# ==================== Phase 12.7: 真实场景集成测试 ====================


class TestRealWorldScenarios:
    """真实场景集成测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.asyncio
    async def test_scenario_api_timeout_with_retry_success(self, event_bus):
        """场景：API 超时后重试成功"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
        )
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        config = {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": 3,
            "retry_delay": 0.01,
        }

        coordinator = CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

        # 模拟 WorkflowAgent：前2次超时，第3次成功
        mock_agent = MagicMock()
        call_count = 0

        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return ExecutionResult.failure(ErrorCode.TIMEOUT, f"Timeout #{call_count}")
            return ExecutionResult.ok({"api_response": "success"})

        mock_agent.execute_node_with_result = mock_execute
        coordinator.register_workflow_agent("wf_api", mock_agent)

        # 处理失败
        result = await coordinator.handle_node_failure(
            workflow_id="wf_api",
            node_id="api_call_node",
            error_code=ErrorCode.TIMEOUT,
            error_message="Initial timeout",
        )

        assert result.success is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_scenario_validation_error_triggers_replan(self, event_bus):
        """场景：校验错误触发重新规划"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
            WorkflowAdjustmentRequestedEvent,
        )
        from src.domain.services.execution_result import ErrorCode

        config = {
            "default_strategy": FailureHandlingStrategy.REPLAN,
            "max_retries": 1,
        }

        coordinator = CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

        # 设置执行上下文
        coordinator.workflow_states["wf_data"] = {
            "workflow_id": "wf_data",
            "status": "running",
            "executed_nodes": ["fetch_data", "transform_data"],
            "node_outputs": {
                "fetch_data": {"rows": 100},
                "transform_data": {"processed": 95},
            },
        }

        events_received = []

        async def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(WorkflowAdjustmentRequestedEvent, capture_event)

        # 校验节点失败
        await coordinator.handle_node_failure(
            workflow_id="wf_data",
            node_id="validate_data",
            error_code=ErrorCode.VALIDATION_FAILED,
            error_message="Data quality check failed: 5 rows have null values",
        )

        # 验证发布了重新规划事件
        assert len(events_received) == 1
        event = events_received[0]
        assert event.workflow_id == "wf_data"
        assert event.failed_node_id == "validate_data"
        assert "transform_data" in event.execution_context["executed_nodes"]

    @pytest.mark.asyncio
    async def test_scenario_critical_error_aborts_workflow(self, event_bus):
        """场景：严重错误终止工作流"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
            WorkflowAbortedEvent,
        )
        from src.domain.services.execution_result import ErrorCode

        config = {
            "default_strategy": FailureHandlingStrategy.ABORT,
            "max_retries": 0,
        }

        coordinator = CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

        events_received = []

        async def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(WorkflowAbortedEvent, capture_event)

        # 严重错误
        result = await coordinator.handle_node_failure(
            workflow_id="wf_critical",
            node_id="auth_node",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message="Authentication service unavailable",
        )

        assert result.success is False
        assert result.aborted is True
        assert len(events_received) == 1
        assert events_received[0].reason == "Authentication service unavailable"

    @pytest.mark.asyncio
    async def test_scenario_optional_node_skipped(self, event_bus):
        """场景：可选节点失败后跳过"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
        )
        from src.domain.services.execution_result import ErrorCode

        config = {
            "default_strategy": FailureHandlingStrategy.ABORT,
            "max_retries": 1,
        }

        coordinator = CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

        # 为可选节点设置 SKIP 策略
        coordinator.set_node_failure_strategy("optional_notification", FailureHandlingStrategy.SKIP)

        # 可选通知节点失败
        result = await coordinator.handle_node_failure(
            workflow_id="wf_order",
            node_id="optional_notification",
            error_code=ErrorCode.NETWORK_ERROR,
            error_message="Email service unavailable",
        )

        assert result.success is True
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_scenario_complex_workflow_with_mixed_strategies(self, event_bus):
        """场景：复杂工作流使用混合策略"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
        )
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        config = {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": 2,
            "retry_delay": 0.01,
        }

        coordinator = CoordinatorAgent(event_bus=event_bus, failure_strategy_config=config)

        # 设置不同节点的策略
        coordinator.set_node_failure_strategy("critical_db", FailureHandlingStrategy.ABORT)
        coordinator.set_node_failure_strategy("optional_cache", FailureHandlingStrategy.SKIP)
        coordinator.set_node_failure_strategy("complex_transform", FailureHandlingStrategy.REPLAN)

        # 模拟 WorkflowAgent
        mock_agent = MagicMock()
        mock_agent.execute_node_with_result = AsyncMock(
            return_value=ExecutionResult.ok({"result": "success"})
        )
        coordinator.register_workflow_agent("wf_complex", mock_agent)

        # 测试各节点的策略
        # 1. 默认策略（重试）
        result1 = await coordinator.handle_node_failure(
            workflow_id="wf_complex",
            node_id="api_call",
            error_code=ErrorCode.TIMEOUT,
            error_message="Timeout",
        )
        assert result1.success is True  # 重试成功

        # 2. SKIP 策略
        result2 = await coordinator.handle_node_failure(
            workflow_id="wf_complex",
            node_id="optional_cache",
            error_code=ErrorCode.NETWORK_ERROR,
            error_message="Cache unavailable",
        )
        assert result2.skipped is True

        # 3. ABORT 策略
        result3 = await coordinator.handle_node_failure(
            workflow_id="wf_complex",
            node_id="critical_db",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message="DB connection lost",
        )
        assert result3.aborted is True


# ==================== Phase 12.8: 执行上下文维护 ====================


class TestExecutionContextMaintenance:
    """测试执行上下文维护"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        agent = CoordinatorAgent(event_bus=event_bus)
        agent.start_monitoring()
        return agent

    @pytest.mark.asyncio
    async def test_context_updated_after_retry_success(self, coordinator, event_bus):
        """测试：重试成功后更新执行上下文"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        coordinator.failure_strategy_config = {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": 2,
            "retry_delay": 0.01,
        }

        # 初始化工作流状态
        coordinator.workflow_states["wf_1"] = {
            "workflow_id": "wf_1",
            "status": "running",
            "executed_nodes": ["node_0"],
            "running_nodes": [],
            "failed_nodes": ["node_1"],
            "node_inputs": {},
            "node_outputs": {"node_0": {"data": "initial"}},
            "node_errors": {"node_1": "First failure"},
        }

        # 模拟重试成功
        mock_agent = MagicMock()
        mock_agent.execute_node_with_result = AsyncMock(
            return_value=ExecutionResult.ok({"result": "retry_success"})
        )
        coordinator.register_workflow_agent("wf_1", mock_agent)

        await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.TIMEOUT,
            error_message="Timeout",
        )

        # 验证上下文更新
        state = coordinator.get_workflow_state("wf_1")
        assert "node_1" in state["executed_nodes"]
        assert "node_1" not in state["failed_nodes"]

    @pytest.mark.asyncio
    async def test_context_preserved_after_skip(self, coordinator):
        """测试：跳过后保留执行上下文"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy
        from src.domain.services.execution_result import ErrorCode

        coordinator.failure_strategy_config = {
            "default_strategy": FailureHandlingStrategy.SKIP,
            "max_retries": 0,
        }

        # 初始化工作流状态
        coordinator.workflow_states["wf_1"] = {
            "workflow_id": "wf_1",
            "status": "running",
            "executed_nodes": ["node_0"],
            "running_nodes": [],
            "failed_nodes": [],
            "skipped_nodes": [],
            "node_inputs": {},
            "node_outputs": {"node_0": {"data": "preserved"}},
            "node_errors": {},
        }

        await coordinator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_1",
            error_code=ErrorCode.NETWORK_ERROR,
            error_message="Network error",
        )

        # 验证上下文保留
        state = coordinator.get_workflow_state("wf_1")
        assert state["node_outputs"]["node_0"]["data"] == "preserved"
        assert "node_1" in state.get("skipped_nodes", [])

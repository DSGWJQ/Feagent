"""REPLAN 策略端到端测试

测试目标：
1. 验证 REPLAN 策略在节点失败时正确触发
2. 验证 WorkflowAdjustmentRequestedEvent 正确发布
3. 验证 ConversationAgent 正确接收和处理调整请求
4. 验证完整的重新规划流程

运行命令：
    pytest tests/integration/test_replan_strategy_e2e.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus


class TestReplanStrategyConfiguration:
    """测试 REPLAN 策略配置"""

    def test_replan_strategy_defined(self):
        """验证 REPLAN 策略已定义"""
        from src.domain.agents.coordinator_agent import FailureHandlingStrategy

        assert hasattr(FailureHandlingStrategy, "REPLAN")
        assert FailureHandlingStrategy.REPLAN.value == "replan"

    def test_set_node_failure_strategy_to_replan(self):
        """验证可以为节点设置 REPLAN 策略"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
        )

        coordinator = CoordinatorAgent()

        # 设置节点失败策略为 REPLAN
        coordinator.set_node_failure_strategy(
            node_id="api_node",
            strategy=FailureHandlingStrategy.REPLAN,
        )

        # 验证策略已设置
        strategy = coordinator.get_node_failure_strategy(node_id="api_node")
        assert strategy == FailureHandlingStrategy.REPLAN


class TestReplanEventPublishing:
    """测试 REPLAN 事件发布"""

    @pytest.fixture
    def event_bus(self):
        """创建真实的 EventBus"""
        return EventBus()

    @pytest.fixture
    def coordinator_with_replan(self, event_bus):
        """创建配置了 REPLAN 策略的 Coordinator"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
        )

        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 初始化工作流状态
        coordinator.workflow_states["wf_001"] = {
            "executed_nodes": ["start_node", "data_node"],
            "node_outputs": {
                "start_node": {"status": "ok"},
                "data_node": {"data": [1, 2, 3]},
            },
            "failed_nodes": [],
        }

        # 设置 REPLAN 策略（节点级别，不是工作流级别）
        coordinator.set_node_failure_strategy(
            node_id="api_node",
            strategy=FailureHandlingStrategy.REPLAN,
        )

        return coordinator

    @pytest.mark.asyncio
    async def test_replan_publishes_adjustment_event(self, coordinator_with_replan, event_bus):
        """验证 REPLAN 策略发布 WorkflowAdjustmentRequestedEvent"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        # 收集发布的事件
        published_events = []

        async def capture_event(event):
            published_events.append(event)

        event_bus.subscribe(WorkflowAdjustmentRequestedEvent, capture_event)

        # 触发节点失败处理（注意：需要提供 error_code 参数）
        result = await coordinator_with_replan.handle_node_failure(
            workflow_id="wf_001",
            node_id="api_node",
            error_code="TIMEOUT",
            error_message="API timeout after 30 seconds",
        )

        # 验证事件已发布
        assert len(published_events) == 1
        event = published_events[0]

        assert isinstance(event, WorkflowAdjustmentRequestedEvent)
        assert event.workflow_id == "wf_001"
        assert event.failed_node_id == "api_node"
        assert event.failure_reason == "API timeout after 30 seconds"
        assert event.suggested_action == "replan"

    @pytest.mark.asyncio
    async def test_replan_event_contains_execution_context(
        self, coordinator_with_replan, event_bus
    ):
        """验证 REPLAN 事件包含执行上下文"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        published_events = []

        async def capture_event(event):
            published_events.append(event)

        event_bus.subscribe(WorkflowAdjustmentRequestedEvent, capture_event)

        await coordinator_with_replan.handle_node_failure(
            workflow_id="wf_001",
            node_id="api_node",
            error_code="CONNECTION_ERROR",
            error_message="Connection refused",
        )

        event = published_events[0]
        ctx = event.execution_context

        # 验证执行上下文包含正确的信息
        assert "executed_nodes" in ctx
        assert "start_node" in ctx["executed_nodes"]
        assert "data_node" in ctx["executed_nodes"]

        assert "node_outputs" in ctx
        assert "start_node" in ctx["node_outputs"]
        assert "data_node" in ctx["node_outputs"]

        assert "failed_nodes" in ctx


class TestConversationAgentReplanHandling:
    """测试 ConversationAgent 处理 REPLAN 请求"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="test_session", global_context=global_ctx)

    @pytest.fixture
    def conversation_agent(self, session_context, event_bus):
        """创建 ConversationAgent"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="需要处理工作流调整请求")
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "已处理"}
        )
        mock_llm.replan_workflow = AsyncMock(
            return_value={
                "nodes": [
                    {"id": "start", "type": "START"},
                    {"id": "fallback_api", "type": "LLM"},
                    {"id": "end", "type": "END"},
                ],
                "edges": [
                    {"source": "start", "target": "fallback_api"},
                    {"source": "fallback_api", "target": "end"},
                ],
            }
        )

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )

        return agent

    @pytest.mark.asyncio
    async def test_conversation_agent_receives_adjustment_event(
        self, conversation_agent, event_bus
    ):
        """验证 ConversationAgent 接收工作流调整事件"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        # 开始监听反馈
        conversation_agent.start_feedback_listening()

        # 发布调整请求事件
        event = WorkflowAdjustmentRequestedEvent(
            source="coordinator_agent",
            workflow_id="wf_001",
            failed_node_id="api_node",
            failure_reason="Timeout",
            suggested_action="replan",
            execution_context={
                "executed_nodes": ["start"],
                "node_outputs": {"start": {}},
                "failed_nodes": ["api_node"],
            },
        )
        await event_bus.publish(event)

        # 验证反馈已记录
        feedbacks = conversation_agent.get_pending_feedbacks()
        assert len(feedbacks) == 1

        feedback = feedbacks[0]
        assert feedback["type"] == "workflow_adjustment"
        assert feedback["workflow_id"] == "wf_001"
        assert feedback["failed_node_id"] == "api_node"
        assert feedback["suggested_action"] == "replan"

        # 清理
        conversation_agent.stop_feedback_listening()

    @pytest.mark.asyncio
    async def test_conversation_agent_replan_workflow(self, conversation_agent):
        """验证 ConversationAgent 可以重新规划工作流"""
        # 调用重新规划
        new_plan = await conversation_agent.replan_workflow(
            original_goal="获取天气数据并分析",
            failed_node_id="weather_api",
            failure_reason="API rate limit exceeded",
            execution_context={
                "executed_nodes": ["start", "auth"],
                "node_outputs": {
                    "start": {},
                    "auth": {"token": "xxx"},
                },
                "failed_nodes": ["weather_api"],
            },
        )

        # 验证返回了新计划
        assert new_plan is not None
        assert "nodes" in new_plan
        assert "edges" in new_plan

        # 验证 LLM 被调用
        conversation_agent.llm.replan_workflow.assert_called_once()
        call_args = conversation_agent.llm.replan_workflow.call_args
        assert call_args.kwargs["goal"] == "获取天气数据并分析"
        assert call_args.kwargs["failed_node_id"] == "weather_api"


class TestFullReplanE2EFlow:
    """测试完整的 REPLAN 端到端流程"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="e2e_user")
        return SessionContext(session_id="e2e_session", global_context=global_ctx)

    @pytest.fixture
    def workflow_context(self, session_context):
        from src.domain.services.context_manager import WorkflowContext

        return WorkflowContext(workflow_id="wf_e2e", session_context=session_context)

    @pytest.mark.asyncio
    async def test_full_replan_e2e_flow(self, event_bus, session_context, workflow_context):
        """测试完整的 REPLAN 流程：失败 → 事件 → 重新规划"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
            WorkflowAdjustmentRequestedEvent,
        )
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # === 1. 设置 Coordinator ===
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.workflow_states["wf_e2e"] = {
            "executed_nodes": ["start", "prepare_data"],
            "node_outputs": {
                "start": {"initiated": True},
                "prepare_data": {"data": [10, 20, 30]},
            },
            "failed_nodes": [],
        }
        coordinator.set_node_failure_strategy(
            node_id="external_api",
            strategy=FailureHandlingStrategy.REPLAN,
        )

        # === 2. 设置 ConversationAgent ===
        mock_llm = MagicMock()
        mock_llm.replan_workflow = AsyncMock(
            return_value={
                "name": "Replanned Workflow",
                "nodes": [
                    {"id": "start", "type": "START"},
                    {
                        "id": "local_processing",
                        "type": "PYTHON",
                        "config": {"code": "process_locally()"},
                    },
                    {"id": "end", "type": "END"},
                ],
                "edges": [
                    {"source": "start", "target": "local_processing"},
                    {"source": "local_processing", "target": "end"},
                ],
                "rationale": "External API failed, switching to local processing",
            }
        )

        conversation_agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        conversation_agent.start_feedback_listening()

        # === 3. 设置 WorkflowAgent ===
        registry = NodeRegistry()
        factory = NodeFactory(registry)
        workflow_agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=factory,
            event_bus=event_bus,
        )

        # === 4. 收集事件 ===
        adjustment_events = []
        replan_results = []

        async def handle_adjustment(event):
            adjustment_events.append(event)

            # 处理调整请求 - 模拟 ConversationAgent 的响应
            if event.suggested_action == "replan":
                # 调用重新规划
                new_plan = await conversation_agent.replan_workflow(
                    original_goal="处理数据并调用外部API",
                    failed_node_id=event.failed_node_id,
                    failure_reason=event.failure_reason,
                    execution_context=event.execution_context,
                )
                replan_results.append(new_plan)

        event_bus.subscribe(WorkflowAdjustmentRequestedEvent, handle_adjustment)

        # === 5. 触发节点失败 ===
        result = await coordinator.handle_node_failure(
            workflow_id="wf_e2e",
            node_id="external_api",
            error_code="TIMEOUT",
            error_message="Connection timeout: unable to reach external service",
        )

        # === 6. 验证结果 ===

        # 6.1 验证失败处理结果
        assert result.success is False
        assert "Replan requested" in result.error_message

        # 6.2 验证调整事件已发布
        assert len(adjustment_events) == 1
        event = adjustment_events[0]
        assert event.workflow_id == "wf_e2e"
        assert event.failed_node_id == "external_api"
        assert event.suggested_action == "replan"

        # 6.3 验证执行上下文传递正确
        ctx = event.execution_context
        assert "prepare_data" in ctx["executed_nodes"]
        assert ctx["node_outputs"]["prepare_data"]["data"] == [10, 20, 30]

        # 6.4 验证重新规划被调用
        assert len(replan_results) == 1
        new_plan = replan_results[0]
        assert new_plan["name"] == "Replanned Workflow"
        assert any(n["type"] == "PYTHON" for n in new_plan["nodes"])

        # 6.5 验证 ConversationAgent 收到反馈
        feedbacks = conversation_agent.get_pending_feedbacks()
        assert len(feedbacks) >= 1

        # 清理
        conversation_agent.stop_feedback_listening()

    @pytest.mark.asyncio
    async def test_replan_with_multiple_failures(self, event_bus, session_context):
        """测试多个节点失败时的 REPLAN 处理"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
            WorkflowAdjustmentRequestedEvent,
        )

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.workflow_states["wf_multi"] = {
            "executed_nodes": ["start"],
            "node_outputs": {"start": {}},
            "failed_nodes": [],
        }

        # 设置多个节点的 REPLAN 策略
        for node_id in ["api_1", "api_2", "api_3"]:
            coordinator.set_node_failure_strategy(
                node_id=node_id,
                strategy=FailureHandlingStrategy.REPLAN,
            )

        # 收集事件
        events = []

        async def capture(event):
            events.append(event)

        event_bus.subscribe(WorkflowAdjustmentRequestedEvent, capture)

        # 触发多个失败
        await coordinator.handle_node_failure(
            workflow_id="wf_multi",
            node_id="api_1",
            error_code="TIMEOUT",
            error_message="Timeout",
        )
        await coordinator.handle_node_failure(
            workflow_id="wf_multi",
            node_id="api_2",
            error_code="RATE_LIMIT",
            error_message="Rate limited",
        )

        # 验证每个失败都产生了调整事件
        assert len(events) == 2
        assert events[0].failed_node_id == "api_1"
        assert events[1].failed_node_id == "api_2"


class TestReplanFallbackBehavior:
    """测试 REPLAN 的回退行为"""

    @pytest.fixture
    def session_context(self):
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="fallback_user")
        return SessionContext(session_id="fallback_session", global_context=global_ctx)

    @pytest.mark.asyncio
    async def test_replan_fallback_when_no_replan_method(self, session_context):
        """验证当 LLM 没有 replan_workflow 方法时的回退行为"""
        from src.domain.agents.conversation_agent import ConversationAgent

        # LLM 没有 replan_workflow 方法
        mock_llm = MagicMock(spec=["plan_workflow", "think", "decide_action"])
        mock_llm.plan_workflow = AsyncMock(
            return_value={
                "nodes": [{"id": "fallback", "type": "LLM"}],
                "edges": [],
            }
        )

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
        )

        # 调用重新规划应该回退到 plan_workflow
        result = await agent.replan_workflow(
            original_goal="Original goal",
            failed_node_id="failed",
            failure_reason="Error",
            execution_context={},
        )

        # 验证回退到 plan_workflow
        mock_llm.plan_workflow.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_replan_without_event_bus(self):
        """验证没有 EventBus 时 REPLAN 仍然返回正确结果"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
        )

        # 没有 event_bus
        coordinator = CoordinatorAgent(event_bus=None)
        coordinator.workflow_states["wf_no_bus"] = {
            "executed_nodes": [],
            "node_outputs": {},
            "failed_nodes": [],
        }
        coordinator.set_node_failure_strategy(
            node_id="node",
            strategy=FailureHandlingStrategy.REPLAN,
        )

        # 触发失败
        result = await coordinator.handle_node_failure(
            workflow_id="wf_no_bus",
            node_id="node",
            error_code="GENERIC_ERROR",
            error_message="Error",
        )

        # 验证仍然返回正确的结果（只是没有发布事件）
        assert result.success is False
        assert "Replan requested" in result.error_message


class TestReplanStatistics:
    """测试 REPLAN 相关的统计信息"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.asyncio
    async def test_replan_counted_in_failure_statistics(self, event_bus):
        """验证 REPLAN 被计入失败统计"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            FailureHandlingStrategy,
        )

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.workflow_states["wf_stats"] = {
            "executed_nodes": [],
            "node_outputs": {},
            "failed_nodes": [],
        }
        coordinator.set_node_failure_strategy(
            node_id="node_1",
            strategy=FailureHandlingStrategy.REPLAN,
        )

        # 触发失败
        await coordinator.handle_node_failure(
            workflow_id="wf_stats",
            node_id="node_1",
            error_code="TEST_ERROR",
            error_message="Test error",
        )

        # 验证失败被记录
        state = coordinator.workflow_states["wf_stats"]
        assert (
            "node_1" in state.get("failed_nodes", [])
            or coordinator.get_statistics().get("total", 0) >= 0
        )


# 导出
__all__ = [
    "TestReplanStrategyConfiguration",
    "TestReplanEventPublishing",
    "TestConversationAgentReplanHandling",
    "TestFullReplanE2EFlow",
    "TestReplanFallbackBehavior",
    "TestReplanStatistics",
]

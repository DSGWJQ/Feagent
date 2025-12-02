"""Phase 13: 对话Agent接收反馈 - TDD 测试

测试 ConversationAgent 订阅协调者反馈事件并重新规划：
1. 订阅 WorkflowAdjustmentRequestedEvent
2. 订阅 NodeFailureHandledEvent
3. 生成 error_recovery 决策
4. 在 ReAct 循环中利用反馈信息
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.agents.conversation_agent import ConversationAgent, DecisionType
from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus

# ==================== Phase 13.1: 错误恢复决策类型 ====================


class TestErrorRecoveryDecisionType:
    """测试错误恢复决策类型"""

    def test_decision_type_has_error_recovery(self):
        """测试：DecisionType 应包含 ERROR_RECOVERY"""
        assert hasattr(DecisionType, "ERROR_RECOVERY")
        assert DecisionType.ERROR_RECOVERY.value == "error_recovery"

    def test_decision_type_has_replan_workflow(self):
        """测试：DecisionType 应包含 REPLAN_WORKFLOW"""
        assert hasattr(DecisionType, "REPLAN_WORKFLOW")
        assert DecisionType.REPLAN_WORKFLOW.value == "replan_workflow"


# ==================== Phase 13.2: 反馈事件订阅 ====================


class TestFeedbackEventSubscription:
    """测试反馈事件订阅"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考中...")
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    def test_conversation_agent_has_start_feedback_listening(
        self, session_context, mock_llm, event_bus
    ):
        """测试：ConversationAgent 应有 start_feedback_listening 方法"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        assert hasattr(agent, "start_feedback_listening")

    def test_conversation_agent_has_stop_feedback_listening(
        self, session_context, mock_llm, event_bus
    ):
        """测试：ConversationAgent 应有 stop_feedback_listening 方法"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        assert hasattr(agent, "stop_feedback_listening")

    def test_start_feedback_listening_subscribes_to_events(
        self, session_context, mock_llm, event_bus
    ):
        """测试：start_feedback_listening 应订阅反馈事件"""
        from src.domain.agents.coordinator_agent import (
            NodeFailureHandledEvent,
            WorkflowAdjustmentRequestedEvent,
        )

        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        agent.start_feedback_listening()

        # 验证订阅了事件
        assert WorkflowAdjustmentRequestedEvent in event_bus._subscribers
        assert NodeFailureHandledEvent in event_bus._subscribers


# ==================== Phase 13.3: 反馈存储和访问 ====================


class TestFeedbackStorage:
    """测试反馈存储"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考中...")
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    def test_conversation_agent_has_pending_feedbacks(self, session_context, mock_llm, event_bus):
        """测试：ConversationAgent 应有 pending_feedbacks 属性"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        assert hasattr(agent, "pending_feedbacks")
        assert isinstance(agent.pending_feedbacks, list)

    def test_conversation_agent_has_get_pending_feedbacks(
        self, session_context, mock_llm, event_bus
    ):
        """测试：ConversationAgent 应有 get_pending_feedbacks 方法"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        assert hasattr(agent, "get_pending_feedbacks")

    def test_conversation_agent_has_clear_feedbacks(self, session_context, mock_llm, event_bus):
        """测试：ConversationAgent 应有 clear_feedbacks 方法"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        assert hasattr(agent, "clear_feedbacks")

    @pytest.mark.asyncio
    async def test_feedback_event_stored_in_pending(self, session_context, mock_llm, event_bus):
        """测试：收到反馈事件后应存储到 pending_feedbacks"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )
        agent.start_feedback_listening()

        # 发布反馈事件
        event = WorkflowAdjustmentRequestedEvent(
            source="coordinator_agent",
            workflow_id="wf_1",
            failed_node_id="node_1",
            failure_reason="Timeout",
            suggested_action="replan",
            execution_context={"executed_nodes": ["node_0"]},
        )

        await event_bus.publish(event)

        # 验证存储
        assert len(agent.pending_feedbacks) == 1
        assert agent.pending_feedbacks[0]["type"] == "workflow_adjustment"
        assert agent.pending_feedbacks[0]["workflow_id"] == "wf_1"


# ==================== Phase 13.4: 错误恢复决策生成 ====================


class TestErrorRecoveryDecision:
    """测试错误恢复决策生成"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="分析失败原因...")
        llm.decide_action = AsyncMock(
            return_value={"action_type": "error_recovery", "recovery_plan": {}}
        )
        llm.should_continue = AsyncMock(return_value=False)
        llm.plan_error_recovery = AsyncMock(
            return_value={
                "recovery_type": "retry_with_modification",
                "modified_nodes": [{"node_id": "node_1", "changes": {"timeout": 60}}],
            }
        )
        return llm

    @pytest.mark.asyncio
    async def test_generate_error_recovery_decision(self, session_context, mock_llm, event_bus):
        """测试：应能生成错误恢复决策"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        # 添加反馈
        agent.pending_feedbacks.append(
            {
                "type": "workflow_adjustment",
                "workflow_id": "wf_1",
                "failed_node_id": "node_1",
                "failure_reason": "Timeout",
                "execution_context": {"executed_nodes": ["node_0"]},
            }
        )

        # 生成恢复决策
        decision = await agent.generate_error_recovery_decision()

        assert decision is not None
        assert decision.type == DecisionType.ERROR_RECOVERY

    @pytest.mark.asyncio
    async def test_error_recovery_includes_failed_node_info(
        self, session_context, mock_llm, event_bus
    ):
        """测试：错误恢复决策应包含失败节点信息"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        agent.pending_feedbacks.append(
            {
                "type": "workflow_adjustment",
                "workflow_id": "wf_1",
                "failed_node_id": "node_1",
                "failure_reason": "Validation failed",
                "execution_context": {},
            }
        )

        decision = await agent.generate_error_recovery_decision()

        assert "failed_node_id" in decision.payload
        assert decision.payload["failed_node_id"] == "node_1"

    @pytest.mark.asyncio
    async def test_no_recovery_when_no_feedbacks(self, session_context, mock_llm, event_bus):
        """测试：没有反馈时不生成恢复决策"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        decision = await agent.generate_error_recovery_decision()

        assert decision is None


# ==================== Phase 13.5: ReAct 循环集成 ====================


class TestReActIntegration:
    """测试 ReAct 循环集成"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="检查是否有待处理的反馈...")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond", "response": "完成"})
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    @pytest.mark.asyncio
    async def test_react_loop_checks_feedbacks(self, session_context, mock_llm, event_bus):
        """测试：ReAct 循环应检查待处理的反馈"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            max_iterations=3,
        )

        # 添加反馈
        agent.pending_feedbacks.append(
            {
                "type": "workflow_adjustment",
                "workflow_id": "wf_1",
                "failed_node_id": "node_1",
                "failure_reason": "Error",
            }
        )

        await agent.run_async("继续处理")

        # 验证上下文包含反馈信息
        context = agent.get_context_for_reasoning()
        assert "pending_feedbacks" in context

    @pytest.mark.asyncio
    async def test_react_loop_includes_feedback_in_context(
        self, session_context, mock_llm, event_bus
    ):
        """测试：ReAct 循环应在上下文中包含反馈信息"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        agent.pending_feedbacks.append(
            {
                "type": "node_failure_handled",
                "workflow_id": "wf_1",
                "node_id": "node_1",
                "strategy": "skip",
                "success": True,
            }
        )

        context = agent.get_context_for_reasoning()

        assert "pending_feedbacks" in context
        assert len(context["pending_feedbacks"]) == 1


# ==================== Phase 13.6: 重新规划工作流 ====================


class TestWorkflowReplanning:
    """测试工作流重新规划"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="需要重新规划...")
        llm.decide_action = AsyncMock(return_value={"action_type": "replan_workflow"})
        llm.should_continue = AsyncMock(return_value=False)
        llm.plan_workflow = AsyncMock(
            return_value={
                "name": "Recovery Plan",
                "nodes": [{"name": "alternative_node", "type": "code", "code": "pass"}],
                "edges": [],
            }
        )
        llm.replan_workflow = AsyncMock(
            return_value={
                "name": "Recovery Plan",
                "nodes": [{"name": "retry_node", "type": "code", "code": "retry()"}],
                "edges": [],
                "recovery_strategy": "retry_with_backoff",
            }
        )
        return llm

    @pytest.mark.asyncio
    async def test_replan_workflow_with_context(self, session_context, mock_llm, event_bus):
        """测试：应能根据执行上下文重新规划工作流"""
        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        execution_context = {
            "executed_nodes": ["node_0", "node_1"],
            "node_outputs": {"node_0": {"result": "ok"}, "node_1": {"result": "partial"}},
            "failed_nodes": ["node_2"],
        }

        plan = await agent.replan_workflow(
            original_goal="处理数据",
            failed_node_id="node_2",
            failure_reason="Timeout",
            execution_context=execution_context,
        )

        assert plan is not None
        assert mock_llm.replan_workflow.called

    @pytest.mark.asyncio
    async def test_replan_preserves_successful_nodes(self, session_context, mock_llm, event_bus):
        """测试：重新规划应保留成功执行的节点结果"""
        mock_llm.replan_workflow = AsyncMock(
            return_value={
                "name": "Recovery Plan",
                "preserve_outputs": ["node_0", "node_1"],
                "nodes": [{"name": "new_node", "type": "code", "code": "new()"}],
                "edges": [],
            }
        )

        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )

        execution_context = {
            "executed_nodes": ["node_0", "node_1"],
            "node_outputs": {"node_0": {"data": "important"}, "node_1": {"result": "keep"}},
        }

        plan = await agent.replan_workflow(
            original_goal="处理数据",
            failed_node_id="node_2",
            failure_reason="Error",
            execution_context=execution_context,
        )

        # 验证调用时包含了执行上下文
        call_args = mock_llm.replan_workflow.call_args
        assert "execution_context" in call_args.kwargs
        assert plan is not None  # 使用 plan 变量


# ==================== Phase 13.7: 真实场景测试 ====================


class TestRealWorldScenarios:
    """真实场景测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.mark.asyncio
    async def test_scenario_receive_timeout_feedback_and_replan(self, session_context, event_bus):
        """场景：收到超时反馈后重新规划"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="收到超时反馈，需要调整策略...")
        mock_llm.decide_action = AsyncMock(
            return_value={
                "action_type": "error_recovery",
                "recovery_type": "increase_timeout",
            }
        )
        mock_llm.should_continue = AsyncMock(return_value=False)
        mock_llm.plan_error_recovery = AsyncMock(
            return_value={
                "recovery_type": "retry_with_modification",
                "modifications": {"timeout": 120},
            }
        )

        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )
        agent.start_feedback_listening()

        # 模拟收到反馈事件
        feedback_event = WorkflowAdjustmentRequestedEvent(
            source="coordinator_agent",
            workflow_id="wf_api",
            failed_node_id="api_call",
            failure_reason="Request timeout after 30 seconds",
            suggested_action="replan",
            execution_context={
                "executed_nodes": ["prepare_data"],
                "node_outputs": {"prepare_data": {"payload": {"user_id": 123}}},
            },
        )

        await event_bus.publish(feedback_event)

        # 验证反馈已存储
        assert len(agent.pending_feedbacks) == 1

        # 生成恢复决策
        decision = await agent.generate_error_recovery_decision()

        assert decision is not None
        assert decision.type == DecisionType.ERROR_RECOVERY

    @pytest.mark.asyncio
    async def test_scenario_validation_failure_triggers_replan(self, session_context, event_bus):
        """场景：校验失败触发重新规划"""
        from src.domain.agents.coordinator_agent import WorkflowAdjustmentRequestedEvent

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="数据校验失败，需要修改处理逻辑...")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "replan_workflow"})
        mock_llm.should_continue = AsyncMock(return_value=False)
        mock_llm.replan_workflow = AsyncMock(
            return_value={
                "name": "Validation Recovery Plan",
                "nodes": [
                    {"name": "data_cleanup", "type": "code", "code": "clean()"},
                    {"name": "validate_again", "type": "code", "code": "validate()"},
                ],
                "edges": [{"source": "data_cleanup", "target": "validate_again"}],
            }
        )

        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )
        agent.start_feedback_listening()

        # 收到校验失败反馈
        feedback_event = WorkflowAdjustmentRequestedEvent(
            source="coordinator_agent",
            workflow_id="wf_data",
            failed_node_id="validate_data",
            failure_reason="5 rows have null values",
            suggested_action="replan",
            execution_context={
                "executed_nodes": ["fetch_data", "transform_data"],
                "node_outputs": {
                    "fetch_data": {"rows": 100},
                    "transform_data": {"processed": 95, "errors": 5},
                },
            },
        )

        await event_bus.publish(feedback_event)

        # 重新规划
        plan = await agent.replan_workflow(
            original_goal="处理和验证数据",
            failed_node_id="validate_data",
            failure_reason="5 rows have null values",
            execution_context=feedback_event.execution_context,
        )

        assert plan is not None
        assert mock_llm.replan_workflow.called

    @pytest.mark.asyncio
    async def test_scenario_multiple_feedbacks_handled_sequentially(
        self, session_context, event_bus
    ):
        """场景：多个反馈按顺序处理"""
        from src.domain.agents.coordinator_agent import (
            NodeFailureHandledEvent,
            WorkflowAdjustmentRequestedEvent,
        )

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="处理多个反馈...")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "error_recovery"})
        mock_llm.should_continue = AsyncMock(return_value=False)
        mock_llm.plan_error_recovery = AsyncMock(return_value={"recovery_type": "batch"})

        agent = ConversationAgent(
            session_context=session_context, llm=mock_llm, event_bus=event_bus
        )
        agent.start_feedback_listening()

        # 发送多个反馈
        await event_bus.publish(
            WorkflowAdjustmentRequestedEvent(
                workflow_id="wf_1",
                failed_node_id="node_1",
                failure_reason="Error 1",
            )
        )

        await event_bus.publish(
            NodeFailureHandledEvent(
                workflow_id="wf_1",
                node_id="node_2",
                strategy="skip",
                success=True,
            )
        )

        # 验证两个反馈都被存储
        assert len(agent.pending_feedbacks) == 2

        # 获取并清空
        feedbacks = agent.get_pending_feedbacks()
        assert len(feedbacks) == 2

        agent.clear_feedbacks()
        assert len(agent.pending_feedbacks) == 0

    @pytest.mark.asyncio
    async def test_scenario_react_loop_with_feedback_context(self, session_context, event_bus):
        """场景：ReAct 循环中使用反馈上下文"""
        mock_llm = MagicMock()

        # 第一次迭代：检测到反馈，生成恢复决策
        # 第二次迭代：执行恢复，完成
        mock_llm.think = AsyncMock(
            side_effect=[
                "检测到失败反馈，分析原因...",
                "恢复策略已执行，任务完成",
            ]
        )
        mock_llm.decide_action = AsyncMock(
            side_effect=[
                {"action_type": "error_recovery", "recovery_plan": {"retry": True}},
                {"action_type": "respond", "response": "已恢复并完成"},
            ]
        )
        mock_llm.should_continue = AsyncMock(side_effect=[True, False])

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            max_iterations=5,
        )

        # 添加反馈
        agent.pending_feedbacks.append(
            {
                "type": "workflow_adjustment",
                "workflow_id": "wf_1",
                "failed_node_id": "node_1",
                "failure_reason": "Network error",
            }
        )

        result = await agent.run_async("继续处理工作流")

        assert result.completed is True
        assert result.iterations == 2

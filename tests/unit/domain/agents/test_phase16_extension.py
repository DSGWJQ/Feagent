"""Phase 16 补充测试 - TDD

测试功能：
1. CoordinatorAgent 订阅反思事件并记录到上下文
2. ConversationAgent 通过新执行链路运行
3. 完整的三 Agent 协作流程
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus

# ==================== Phase 16.7: CoordinatorAgent 反思上下文记录 ====================


class TestCoordinatorReflectionContext:
    """测试 CoordinatorAgent 接收反思输出并记录到上下文"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    def test_coordinator_has_reflection_context_storage(self, event_bus):
        """测试：CoordinatorAgent 应有反思上下文存储"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 应该有反思上下文存储
        assert hasattr(coordinator, "reflection_contexts")
        assert isinstance(coordinator.reflection_contexts, dict)

    def test_coordinator_has_start_reflection_listening(self, event_bus):
        """测试：CoordinatorAgent 应有 start_reflection_listening 方法"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=event_bus)

        assert hasattr(coordinator, "start_reflection_listening")

    @pytest.mark.asyncio
    async def test_coordinator_receives_reflection_event(self, event_bus):
        """测试：CoordinatorAgent 订阅后应接收反思事件"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_reflection_listening()

        # 发布反思事件
        event = WorkflowReflectionCompletedEvent(
            source="workflow_agent",
            workflow_id="wf_1",
            assessment="执行成功，所有节点正常完成",
            should_retry=False,
            confidence=0.95,
        )
        await event_bus.publish(event)

        # 验证已记录
        assert "wf_1" in coordinator.reflection_contexts

    @pytest.mark.asyncio
    async def test_coordinator_records_reflection_details(self, event_bus):
        """测试：CoordinatorAgent 应记录反思详情（目标、规则、错误、建议）"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_reflection_listening()

        event = WorkflowReflectionCompletedEvent(
            source="workflow_agent",
            workflow_id="wf_1",
            assessment="数据处理失败，需要重试",
            should_retry=True,
            confidence=0.75,
        )
        await event_bus.publish(event)

        context = coordinator.reflection_contexts["wf_1"]

        # 应该记录关键信息
        assert "assessment" in context
        assert "should_retry" in context
        assert "confidence" in context
        assert "timestamp" in context

    @pytest.mark.asyncio
    async def test_coordinator_accumulates_reflection_history(self, event_bus):
        """测试：CoordinatorAgent 应累积反思历史"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_reflection_listening()

        # 第一次反思
        await event_bus.publish(
            WorkflowReflectionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_1",
                assessment="第一次尝试失败",
                should_retry=True,
                confidence=0.6,
            )
        )

        # 第二次反思
        await event_bus.publish(
            WorkflowReflectionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_1",
                assessment="重试成功",
                should_retry=False,
                confidence=0.95,
            )
        )

        context = coordinator.reflection_contexts["wf_1"]

        # 应该有历史记录
        assert "history" in context
        assert len(context["history"]) == 2

    def test_coordinator_stop_reflection_listening(self, event_bus):
        """测试：CoordinatorAgent 应能停止反思监听"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_reflection_listening()
        coordinator.stop_reflection_listening()

        # 验证已取消订阅
        assert coordinator._is_listening_reflections is False

    def test_coordinator_get_reflection_summary(self, event_bus):
        """测试：CoordinatorAgent 应提供反思摘要"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=event_bus)

        assert hasattr(coordinator, "get_reflection_summary")


# ==================== Phase 16.8: ConversationAgent 新执行链路 ====================


class TestConversationAgentExecutionChain:
    """测试 ConversationAgent 通过新执行链路运行"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def mock_session_context(self):
        """模拟会话上下文"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="test_session", global_context=global_ctx)

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="好的，我来帮你处理")
        llm.classify_intent = AsyncMock(
            return_value={
                "intent": "workflow_modification",
                "confidence": 0.9,
            }
        )
        return llm

    def test_conversation_agent_has_execute_workflow_method(
        self, event_bus, mock_llm, mock_session_context
    ):
        """测试：ConversationAgent 应有 execute_workflow 方法"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=mock_session_context,
            event_bus=event_bus,
            llm=mock_llm,
        )

        assert hasattr(agent, "execute_workflow")

    @pytest.mark.asyncio
    async def test_conversation_agent_execute_workflow_returns_result(
        self, event_bus, mock_llm, mock_session_context
    ):
        """测试：ConversationAgent.execute_workflow 应返回执行结果"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import WorkflowExecutionResult

        mock_workflow_agent = MagicMock()
        mock_workflow_agent.execute = AsyncMock(
            return_value=WorkflowExecutionResult(
                success=True,
                summary="工作流执行成功",
                workflow_id="wf_1",
            )
        )
        mock_workflow_agent.reflect = AsyncMock(
            return_value=MagicMock(
                assessment="执行成功",
                should_retry=False,
            )
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            event_bus=event_bus,
            llm=mock_llm,
        )
        agent.workflow_agent = mock_workflow_agent

        result = await agent.execute_workflow({"id": "wf_1", "nodes": []})

        assert isinstance(result, WorkflowExecutionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_conversation_agent_execute_workflow_triggers_reflect(
        self, event_bus, mock_llm, mock_session_context
    ):
        """测试：ConversationAgent.execute_workflow 应触发反思"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import WorkflowExecutionResult

        mock_workflow_agent = MagicMock()
        mock_workflow_agent.execute = AsyncMock(
            return_value=WorkflowExecutionResult(
                success=True,
                summary="完成",
                workflow_id="wf_1",
            )
        )
        mock_workflow_agent.reflect = AsyncMock(
            return_value=MagicMock(
                assessment="执行成功",
                should_retry=False,
            )
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            event_bus=event_bus,
            llm=mock_llm,
        )
        agent.workflow_agent = mock_workflow_agent

        await agent.execute_workflow({"id": "wf_1", "nodes": []})

        # reflect 应该被调用
        mock_workflow_agent.reflect.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_agent_no_sub_agent_creation(
        self, event_bus, mock_llm, mock_session_context
    ):
        """测试：ConversationAgent 不应创建子 Agent"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=mock_session_context,
            event_bus=event_bus,
            llm=mock_llm,
        )

        # 确保没有子 Agent 创建逻辑
        assert not hasattr(agent, "sub_agents")


# ==================== Phase 16.9: 三 Agent 完整协作流程 ====================


class TestThreeAgentCollaboration:
    """测试完整的三 Agent 协作流程"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def mock_session_context(self):
        """模拟会话上下文"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="test_session", global_context=global_ctx)

    @pytest.mark.asyncio
    async def test_full_execution_chain_success(self, event_bus, mock_session_context):
        """场景：成功的完整执行链路"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
        )

        # 创建模拟组件
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": True,
                "outputs": {"result": "处理完成"},
                "executed_nodes": ["node_1", "node_2"],
            }
        )

        mock_reflect_llm = MagicMock()
        mock_reflect_llm.reflect = AsyncMock(
            return_value={
                "assessment": "所有节点执行成功",
                "issues": [],
                "recommendations": [],
                "confidence": 0.95,
                "should_retry": False,
            }
        )

        mock_conversation_llm = MagicMock()
        mock_conversation_llm.generate_response = AsyncMock(return_value="已完成")

        # 创建 Agent
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_reflection_listening()

        workflow_agent = WorkflowAgent(
            event_bus=event_bus,
            executor=mock_executor,
            llm=mock_reflect_llm,
        )

        conversation_agent = ConversationAgent(
            session_context=mock_session_context,
            event_bus=event_bus,
            llm=mock_conversation_llm,
        )
        conversation_agent.workflow_agent = workflow_agent

        # 执行工作流
        workflow = {"id": "wf_test", "nodes": [], "edges": []}
        result = await conversation_agent.execute_workflow(workflow)

        # 验证执行成功
        assert result.success is True
        assert result.workflow_id == "wf_test"

        # 验证 CoordinatorAgent 接收到反思
        assert "wf_test" in coordinator.reflection_contexts

    @pytest.mark.asyncio
    async def test_full_execution_chain_failure_with_retry(self, event_bus, mock_session_context):
        """场景：失败后建议重试的执行链路"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowAgent

        # 创建模拟组件 - 失败场景
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": False,
                "error": "API 超时",
                "failed_node": "node_1",
                "executed_nodes": [],
            }
        )

        mock_reflect_llm = MagicMock()
        mock_reflect_llm.reflect = AsyncMock(
            return_value={
                "assessment": "执行失败，网络问题",
                "issues": ["API 超时"],
                "recommendations": ["增加超时时间", "添加重试"],
                "confidence": 0.8,
                "should_retry": True,
                "suggested_modifications": {"node_1": {"timeout": 60}},
            }
        )

        mock_conversation_llm = MagicMock()

        # 创建 Agent
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_reflection_listening()

        workflow_agent = WorkflowAgent(
            event_bus=event_bus,
            executor=mock_executor,
            llm=mock_reflect_llm,
        )

        conversation_agent = ConversationAgent(
            session_context=mock_session_context,
            event_bus=event_bus,
            llm=mock_conversation_llm,
        )
        conversation_agent.workflow_agent = workflow_agent

        # 执行工作流
        result = await conversation_agent.execute_workflow({"id": "wf_fail", "nodes": []})

        # 验证执行失败
        assert result.success is False
        assert result.failed_node == "node_1"

        # 验证 CoordinatorAgent 记录了反思
        assert "wf_fail" in coordinator.reflection_contexts
        context = coordinator.reflection_contexts["wf_fail"]
        assert context["should_retry"] is True

    @pytest.mark.asyncio
    async def test_coordinator_provides_feedback_to_conversation(
        self, event_bus, mock_session_context
    ):
        """场景：CoordinatorAgent 向 ConversationAgent 提供反馈"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowAgent

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": True,
                "outputs": {},
                "executed_nodes": ["n1"],
            }
        )

        mock_reflect_llm = MagicMock()
        mock_reflect_llm.reflect = AsyncMock(
            return_value={
                "assessment": "完成",
                "issues": [],
                "recommendations": ["优化性能"],
                "confidence": 0.9,
                "should_retry": False,
            }
        )

        mock_conversation_llm = MagicMock()

        # 创建 Agent
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_reflection_listening()

        workflow_agent = WorkflowAgent(
            event_bus=event_bus,
            executor=mock_executor,
            llm=mock_reflect_llm,
        )

        conversation_agent = ConversationAgent(
            session_context=mock_session_context,
            event_bus=event_bus,
            llm=mock_conversation_llm,
        )
        conversation_agent.workflow_agent = workflow_agent

        # 执行
        await conversation_agent.execute_workflow({"id": "wf_feedback", "nodes": []})

        # 获取 Coordinator 的反思摘要
        summary = coordinator.get_reflection_summary("wf_feedback")

        assert summary is not None
        assert "assessment" in summary

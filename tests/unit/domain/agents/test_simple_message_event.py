"""Phase 15: 简单对话记录与 ReAct 桥接 - TDD 测试

测试功能：
1. SimpleMessageEvent 事件定义
2. CoordinatorAgent 订阅并记录简单消息
3. ConversationAgent 发送简单消息事件
4. 工作流修改走 ReAct 后 DecisionMadeEvent 交给协调者校验
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus

# ==================== Phase 15.1: SimpleMessageEvent 定义 ====================


class TestSimpleMessageEvent:
    """测试 SimpleMessageEvent 事件"""

    def test_simple_message_event_exists(self):
        """测试：SimpleMessageEvent 应存在"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        assert SimpleMessageEvent is not None

    def test_simple_message_event_inherits_from_event(self):
        """测试：SimpleMessageEvent 应继承自 Event"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent
        from src.domain.services.event_bus import Event

        event = SimpleMessageEvent(
            source="conversation_agent",
            user_input="你好",
            response="你好！有什么可以帮你的吗？",
            intent="conversation",
        )

        assert isinstance(event, Event)

    def test_simple_message_event_has_required_fields(self):
        """测试：SimpleMessageEvent 应包含必要字段"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        event = SimpleMessageEvent(
            source="conversation_agent",
            user_input="今天天气怎么样？",
            response="今天天气晴朗。",
            intent="conversation",
            confidence=0.95,
            session_id="session_1",
        )

        assert event.user_input == "今天天气怎么样？"
        assert event.response == "今天天气晴朗。"
        assert event.intent == "conversation"
        assert event.confidence == 0.95
        assert event.session_id == "session_1"

    def test_simple_message_event_has_timestamp(self):
        """测试：SimpleMessageEvent 应有时间戳"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        event = SimpleMessageEvent(
            source="test",
            user_input="test",
            response="test",
            intent="conversation",
        )

        assert event.timestamp is not None


# ==================== Phase 15.2: CoordinatorAgent 订阅 SimpleMessageEvent ====================


class TestCoordinatorSimpleMessageSubscription:
    """测试 CoordinatorAgent 订阅 SimpleMessageEvent"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        return CoordinatorAgent(event_bus=event_bus)

    def test_coordinator_has_message_log(self, coordinator):
        """测试：Coordinator 应有 message_log 属性"""
        assert hasattr(coordinator, "message_log")
        assert isinstance(coordinator.message_log, list)

    def test_coordinator_can_subscribe_to_simple_message(self, coordinator, event_bus):
        """测试：Coordinator 应能订阅 SimpleMessageEvent"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        # 订阅事件
        coordinator.start_simple_message_listening()

        # 验证订阅
        assert SimpleMessageEvent in event_bus._subscribers

    @pytest.mark.asyncio
    async def test_coordinator_logs_simple_message(self, coordinator, event_bus):
        """测试：Coordinator 应记录收到的简单消息"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        coordinator.start_simple_message_listening()

        # 发布事件
        event = SimpleMessageEvent(
            source="conversation_agent",
            user_input="你好",
            response="你好！",
            intent="conversation",
            session_id="session_1",
        )
        await event_bus.publish(event)

        # 验证记录
        assert len(coordinator.message_log) == 1
        assert coordinator.message_log[0]["user_input"] == "你好"
        assert coordinator.message_log[0]["response"] == "你好！"

    @pytest.mark.asyncio
    async def test_coordinator_logs_multiple_messages(self, coordinator, event_bus):
        """测试：Coordinator 应能记录多条消息"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        coordinator.start_simple_message_listening()

        # 发布多个事件
        for i in range(3):
            event = SimpleMessageEvent(
                source="conversation_agent",
                user_input=f"消息 {i}",
                response=f"回复 {i}",
                intent="conversation",
            )
            await event_bus.publish(event)

        assert len(coordinator.message_log) == 3

    def test_coordinator_can_stop_listening(self, coordinator, event_bus):
        """测试：Coordinator 应能停止监听"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        coordinator.start_simple_message_listening()
        coordinator.stop_simple_message_listening()

        # 验证取消订阅
        assert (
            SimpleMessageEvent not in event_bus._subscribers
            or len(event_bus._subscribers.get(SimpleMessageEvent, [])) == 0
        )

    def test_coordinator_get_message_statistics(self, coordinator):
        """测试：Coordinator 应能获取消息统计"""
        # 手动添加一些消息记录
        coordinator.message_log.append(
            {"user_input": "你好", "intent": "conversation", "response": "你好！"}
        )
        coordinator.message_log.append(
            {"user_input": "创建工作流", "intent": "workflow_modification", "response": ""}
        )
        coordinator.message_log.append(
            {"user_input": "天气", "intent": "conversation", "response": "晴天"}
        )

        stats = coordinator.get_message_statistics()

        assert stats["total_messages"] == 3
        assert stats["by_intent"]["conversation"] == 2
        assert stats["by_intent"]["workflow_modification"] == 1


# ==================== Phase 15.3: ConversationAgent 发送 SimpleMessageEvent ====================


class TestConversationAgentSendsSimpleMessage:
    """测试 ConversationAgent 发送 SimpleMessageEvent"""

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
        llm.think = AsyncMock(return_value="")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond", "response": "完成"})
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(return_value={"intent": "conversation", "confidence": 0.95})
        llm.generate_response = AsyncMock(return_value="你好！我是AI助手。")
        return llm

    @pytest.mark.asyncio
    async def test_conversation_publishes_simple_message_event(
        self, session_context, mock_llm, event_bus
    ):
        """测试：普通对话应发布 SimpleMessageEvent"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            SimpleMessageEvent,
        )

        received_events = []

        async def capture_event(event):
            received_events.append(event)

        event_bus.subscribe(SimpleMessageEvent, capture_event)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            enable_intent_classification=True,
        )

        await agent.process_with_intent("你好")

        # 验证发布了事件
        assert len(received_events) == 1
        assert received_events[0].user_input == "你好"
        assert received_events[0].response == "你好！我是AI助手。"
        assert received_events[0].intent == "conversation"

    @pytest.mark.asyncio
    async def test_workflow_query_publishes_simple_message_event(
        self, session_context, mock_llm, event_bus
    ):
        """测试：工作流查询应发布 SimpleMessageEvent"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            SimpleMessageEvent,
        )

        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "workflow_query",
                "confidence": 0.9,
                "extracted_entities": {"workflow_id": "wf_1"},
            }
        )
        mock_llm.generate_response = AsyncMock(return_value="工作流正在执行中。")
        # 确保 generate_workflow_status 也是 AsyncMock
        mock_llm.generate_workflow_status = AsyncMock(return_value="工作流正在执行中。")

        received_events = []

        async def capture_event(event):
            received_events.append(event)

        event_bus.subscribe(SimpleMessageEvent, capture_event)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            enable_intent_classification=True,
        )

        await agent.process_with_intent("工作流状态如何？")

        assert len(received_events) == 1
        assert received_events[0].intent == "workflow_query"

    @pytest.mark.asyncio
    async def test_workflow_modification_does_not_publish_simple_message(
        self, session_context, mock_llm, event_bus
    ):
        """测试：工作流修改不应发布 SimpleMessageEvent（走 ReAct）"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            SimpleMessageEvent,
        )

        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "workflow_modification", "confidence": 0.95}
        )

        received_simple_events = []

        async def capture_simple_event(event):
            received_simple_events.append(event)

        event_bus.subscribe(SimpleMessageEvent, capture_simple_event)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            enable_intent_classification=True,
            max_iterations=2,
        )

        await agent.process_with_intent("创建一个工作流")

        # 工作流修改走 ReAct，不应发布 SimpleMessageEvent
        assert len(received_simple_events) == 0


# ==================== Phase 15.4: ReAct 桥接 - DecisionMadeEvent 交给协调者 ====================


class TestReActBridgeDecisionValidation:
    """测试 ReAct 桥接 - DecisionMadeEvent 校验"""

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
        llm.think = AsyncMock(return_value="需要创建工作流节点...")
        llm.decide_action = AsyncMock(
            return_value={
                "action_type": "create_node",
                "node_type": "llm",
                "name": "数据处理节点",
            }
        )
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(
            return_value={"intent": "workflow_modification", "confidence": 0.95}
        )
        return llm

    @pytest.mark.asyncio
    async def test_workflow_modification_publishes_decision_event(
        self, session_context, mock_llm, event_bus
    ):
        """测试：工作流修改应发布 DecisionMadeEvent"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            DecisionMadeEvent,
        )

        received_decisions = []

        async def capture_decision(event):
            received_decisions.append(event)

        event_bus.subscribe(DecisionMadeEvent, capture_decision)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            enable_intent_classification=True,
            max_iterations=2,
        )

        await agent.process_with_intent("创建一个数据处理节点")

        # 应该发布了 DecisionMadeEvent
        assert len(received_decisions) >= 1
        assert received_decisions[0].decision_type == "create_node"

    @pytest.mark.asyncio
    async def test_coordinator_validates_decision_from_react(
        self, session_context, mock_llm, event_bus
    ):
        """测试：Coordinator 应能接收来自 ReAct 的决策事件"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            DecisionMadeEvent,
        )

        received_decisions = []

        async def capture_decision(event):
            received_decisions.append(event)

        event_bus.subscribe(DecisionMadeEvent, capture_decision)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            enable_intent_classification=True,
            max_iterations=2,
        )

        await agent.process_with_intent("添加一个节点")

        # 验证 DecisionMadeEvent 被发布
        # ReAct 循环中的 create_node 决策应该发布事件
        assert len(received_decisions) >= 1


# ==================== Phase 15.5: 真实场景集成测试 ====================


class TestRealWorldIntegrationScenarios:
    """真实场景集成测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.mark.asyncio
    async def test_scenario_full_conversation_flow(self, session_context, event_bus):
        """场景：完整对话流程 - 普通对话 + 工作流修改"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
        )
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        # 设置协调者
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_simple_message_listening()

        # 设置对话代理
        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="分析用户意图...")
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "完成"}
        )
        mock_llm.should_continue = AsyncMock(return_value=False)
        mock_llm.generate_response = AsyncMock(return_value="你好！")

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            enable_intent_classification=True,
            max_iterations=3,
        )

        # 第一轮：普通对话
        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "conversation", "confidence": 0.98}
        )
        await agent.process_with_intent("你好")

        # 验证 SimpleMessageEvent 被记录
        assert len(coordinator.message_log) == 1
        assert coordinator.message_log[0]["intent"] == "conversation"

        # 第二轮：工作流修改
        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "workflow_modification", "confidence": 0.95}
        )
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "create_node", "name": "节点1"}
        )

        await agent.process_with_intent("创建一个节点")

        # 普通对话仍然只有 1 条（工作流修改不记录 SimpleMessage）
        assert len(coordinator.message_log) == 1

    @pytest.mark.asyncio
    async def test_scenario_coordinator_statistics_after_mixed_interactions(
        self, session_context, event_bus
    ):
        """场景：混合交互后的统计"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_simple_message_listening()

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "完成"}
        )
        mock_llm.should_continue = AsyncMock(return_value=False)
        mock_llm.generate_response = AsyncMock(return_value="回复")
        # 确保 workflow_query 也能正常工作
        mock_llm.generate_workflow_status = AsyncMock(return_value="状态回复")

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
            enable_intent_classification=True,
        )

        # 3 次普通对话
        for _ in range(3):
            mock_llm.classify_intent = AsyncMock(
                return_value={"intent": "conversation", "confidence": 0.9}
            )
            await agent.process_with_intent("聊天")

        # 2 次工作流查询
        for _ in range(2):
            mock_llm.classify_intent = AsyncMock(
                return_value={"intent": "workflow_query", "confidence": 0.85}
            )
            await agent.process_with_intent("状态")

        # 获取统计
        stats = coordinator.get_message_statistics()

        assert stats["total_messages"] == 5
        assert stats["by_intent"]["conversation"] == 3
        assert stats["by_intent"]["workflow_query"] == 2

    @pytest.mark.asyncio
    async def test_scenario_event_flow_without_event_bus(self, session_context):
        """场景：无 EventBus 时应正常工作（不发送事件）"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "conversation", "confidence": 0.9}
        )
        mock_llm.generate_response = AsyncMock(return_value="你好！")
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        mock_llm.should_continue = AsyncMock(return_value=False)

        # 不传入 event_bus
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
        )

        # 应该正常工作，不抛异常
        result = await agent.process_with_intent("你好")
        assert result.final_response == "你好！"

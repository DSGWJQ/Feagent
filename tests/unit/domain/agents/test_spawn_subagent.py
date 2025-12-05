"""测试：spawn_agent 动作生成

测试目标：
1. DecisionType.SPAWN_SUBAGENT 决策类型
2. SpawnSubAgentEvent 事件定义
3. ConversationAgent 生成 spawn 决策
4. 决策负载结构验证

完成标准：
- DecisionType 包含 SPAWN_SUBAGENT
- Event 结构正确
- ConversationAgent 可以生成 spawn 决策
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import GlobalContext, SessionContext


def create_test_session_context(session_id: str = "test_session") -> SessionContext:
    """创建测试用的 SessionContext"""
    global_ctx = GlobalContext(user_id="test_user")
    return SessionContext(session_id=session_id, global_context=global_ctx)


# ==================== 测试1：DecisionType 扩展 ====================


class TestDecisionTypeSpawnSubagent:
    """测试 DecisionType 扩展"""

    def test_spawn_subagent_decision_type_exists(self):
        """SPAWN_SUBAGENT 决策类型应存在"""
        from src.domain.agents.conversation_agent import DecisionType

        assert DecisionType.SPAWN_SUBAGENT is not None
        assert DecisionType.SPAWN_SUBAGENT.value == "spawn_subagent"


# ==================== 测试2：SpawnSubAgentEvent 事件 ====================


class TestSpawnSubAgentEvent:
    """测试 SpawnSubAgentEvent 事件"""

    def test_event_class_exists(self):
        """SpawnSubAgentEvent 应存在"""
        from src.domain.agents.conversation_agent import SpawnSubAgentEvent

        assert SpawnSubAgentEvent is not None

    def test_event_has_required_fields(self):
        """事件应有必需字段"""
        from src.domain.agents.conversation_agent import SpawnSubAgentEvent

        event = SpawnSubAgentEvent(
            subagent_type="search",
            task_payload={"query": "测试搜索"},
            priority=1,
            session_id="session_001",
        )

        assert event.subagent_type == "search"
        assert event.task_payload["query"] == "测试搜索"
        assert event.priority == 1
        assert event.session_id == "session_001"

    def test_event_has_event_type_property(self):
        """事件应有 event_type 属性"""
        from src.domain.agents.conversation_agent import SpawnSubAgentEvent

        event = SpawnSubAgentEvent(
            subagent_type="search",
            task_payload={},
        )

        assert event.event_type == "spawn_subagent_requested"

    def test_event_default_priority(self):
        """事件应有默认优先级"""
        from src.domain.agents.conversation_agent import SpawnSubAgentEvent

        event = SpawnSubAgentEvent(
            subagent_type="python_executor",
            task_payload={"code": "print('hello')"},
        )

        assert event.priority == 0  # 默认优先级


# ==================== 测试3：Decision 创建 ====================


class TestSpawnSubAgentDecision:
    """测试 spawn_subagent 决策创建"""

    def test_create_spawn_decision(self):
        """可以创建 spawn 决策"""
        from src.domain.agents.conversation_agent import Decision, DecisionType

        decision = Decision(
            type=DecisionType.SPAWN_SUBAGENT,
            payload={
                "subagent_type": "search",
                "task_payload": {"query": "搜索内容"},
                "priority": 1,
            },
            confidence=0.9,
        )

        assert decision.type == DecisionType.SPAWN_SUBAGENT
        assert decision.payload["subagent_type"] == "search"
        assert decision.confidence == 0.9

    def test_decision_payload_structure(self):
        """决策负载结构应正确"""
        from src.domain.agents.conversation_agent import Decision, DecisionType

        decision = Decision(
            type=DecisionType.SPAWN_SUBAGENT,
            payload={
                "subagent_type": "python_executor",
                "task_payload": {
                    "code": "import pandas as pd\nprint(pd.__version__)",
                    "timeout": 30,
                },
                "priority": 2,
                "context_snapshot": {"current_step": 3},
            },
        )

        payload = decision.payload
        assert "subagent_type" in payload
        assert "task_payload" in payload
        assert "priority" in payload
        assert payload["task_payload"]["timeout"] == 30


# ==================== 测试4：ConversationAgent 生成 spawn 决策 ====================


class TestConversationAgentSpawnDecision:
    """测试 ConversationAgent 生成 spawn 决策"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="需要搜索相关信息")
        llm.decide_action = AsyncMock(
            return_value={
                "action_type": "spawn_subagent",
                "subagent_type": "search",
                "task_payload": {"query": "最新的天气预报"},
            }
        )
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        return create_test_session_context()

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        from unittest.mock import AsyncMock  # Import AsyncMock

        event_bus = MagicMock()
        event_bus.publish = AsyncMock()  # Changed: Use AsyncMock for async method
        return event_bus

    def test_agent_can_create_spawn_decision(self, mock_session_context, mock_llm, mock_event_bus):
        """Agent 可以创建 spawn 决策"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            DecisionType,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        # 创建 spawn 决策
        decision = agent.create_spawn_subagent_decision(
            subagent_type="search",
            task_payload={"query": "测试查询"},
            context_snapshot={"step": 1},
        )

        assert decision.type == DecisionType.SPAWN_SUBAGENT
        assert decision.payload["subagent_type"] == "search"

    @pytest.mark.asyncio  # Added: Make test async
    async def test_spawn_decision_publishes_event(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """生成 spawn 决策应发布事件"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
            SpawnSubAgentEvent,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        # 先转换到处理状态
        agent.transition_to(ConversationAgentState.PROCESSING)

        # Give asyncio.create_task() a chance to run
        import asyncio

        await asyncio.sleep(0.01)  # Allow task to complete

        # 创建 spawn 决策并发布
        agent.request_subagent_spawn(
            subagent_type="search",
            task_payload={"query": "测试"},
        )

        # Give asyncio.create_task() a chance to run
        await asyncio.sleep(0.01)  # Allow task to complete

        # 验证事件发布（至少发布两次：状态变化 + spawn 请求）
        assert mock_event_bus.publish.call_count >= 2

        # 获取所有发布的事件
        events = [call[0][0] for call in mock_event_bus.publish.call_args_list]

        # 应包含 SpawnSubAgentEvent
        spawn_events = [e for e in events if isinstance(e, SpawnSubAgentEvent)]
        assert len(spawn_events) >= 1
        assert spawn_events[0].subagent_type == "search"


# ==================== 测试5：spawn 决策与状态机集成 ====================


class TestSpawnDecisionStateMachineIntegration:
    """测试 spawn 决策与状态机的集成"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        return create_test_session_context()

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        from unittest.mock import AsyncMock  # Import AsyncMock

        event_bus = MagicMock()
        event_bus.publish = AsyncMock()  # Changed: Use AsyncMock for async method
        return event_bus

    @pytest.mark.asyncio  # Added: Make test async
    async def test_spawn_request_transitions_to_waiting(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """请求 spawn 应转换为等待状态"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        # 开始处理
        agent.transition_to(ConversationAgentState.PROCESSING)

        # Give asyncio.create_task() a chance to run
        import asyncio

        await asyncio.sleep(0.01)  # Allow task to complete

        # 请求 spawn 子Agent
        agent.request_subagent_spawn(
            subagent_type="search",
            task_payload={"query": "测试"},
            wait_for_result=True,
        )

        # Give asyncio.create_task() a chance to run
        await asyncio.sleep(0.01)  # Allow task to complete

        # 应进入等待状态
        assert agent.state == ConversationAgentState.WAITING_FOR_SUBAGENT
        assert agent.pending_subagent_id is not None

    @pytest.mark.asyncio  # Added: Make test async
    async def test_spawn_without_waiting_stays_processing(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """不等待结果的 spawn 应保持处理状态"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        # 开始处理
        agent.transition_to(ConversationAgentState.PROCESSING)

        # Give asyncio.create_task() a chance to run
        import asyncio

        await asyncio.sleep(0.01)  # Allow task to complete

        # 请求 spawn 子Agent（不等待）
        agent.request_subagent_spawn(
            subagent_type="data_processor",
            task_payload={"action": "process"},
            wait_for_result=False,
        )

        # Give asyncio.create_task() a chance to run
        await asyncio.sleep(0.01)  # Allow task to complete

        # 应保持处理状态
        assert agent.state == ConversationAgentState.PROCESSING


# 导出
__all__ = [
    "TestDecisionTypeSpawnSubagent",
    "TestSpawnSubAgentEvent",
    "TestSpawnSubAgentDecision",
    "TestConversationAgentSpawnDecision",
    "TestSpawnDecisionStateMachineIntegration",
]

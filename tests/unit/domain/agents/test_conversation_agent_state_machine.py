"""测试：ConversationAgent 状态机

测试目标：
1. ConversationAgentState 枚举定义
2. 状态转换验证
3. 子Agent等待暂停/恢复流程
4. 状态事件发布

完成标准：
- 状态枚举完整
- 转换规则正确
- 暂停/恢复语义清晰
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import GlobalContext, SessionContext


def create_test_session_context(session_id: str = "test_session") -> SessionContext:
    """创建测试用的 SessionContext"""
    global_ctx = GlobalContext(user_id="test_user")
    return SessionContext(session_id=session_id, global_context=global_ctx)


# ==================== 测试1：状态枚举定义 ====================


class TestConversationAgentState:
    """测试 ConversationAgent 状态枚举"""

    def test_state_enum_exists(self):
        """状态枚举应存在"""
        from src.domain.agents.conversation_agent import ConversationAgentState

        # 验证基础状态
        assert ConversationAgentState.IDLE is not None
        assert ConversationAgentState.PROCESSING is not None
        assert ConversationAgentState.WAITING_FOR_SUBAGENT is not None
        assert ConversationAgentState.COMPLETED is not None
        assert ConversationAgentState.ERROR is not None

    def test_state_values(self):
        """状态值应正确"""
        from src.domain.agents.conversation_agent import ConversationAgentState

        assert ConversationAgentState.IDLE.value == "idle"
        assert ConversationAgentState.PROCESSING.value == "processing"
        assert ConversationAgentState.WAITING_FOR_SUBAGENT.value == "waiting_for_subagent"
        assert ConversationAgentState.COMPLETED.value == "completed"
        assert ConversationAgentState.ERROR.value == "error"


# ==================== 测试2：状态机初始化 ====================


class TestStateMachineInitialization:
    """测试状态机初始化"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.9,
                "reasoning": "普通对话",
            }
        )
        llm.generate_response = AsyncMock(return_value="回复内容")
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        return create_test_session_context()

    def test_agent_initial_state_is_idle(self, mock_session_context, mock_llm):
        """Agent 初始状态应为 IDLE"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        assert agent.state == ConversationAgentState.IDLE

    def test_agent_has_state_property(self, mock_session_context, mock_llm):
        """Agent 应有 state 属性"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        assert hasattr(agent, "state")
        assert hasattr(agent, "_state")


# ==================== 测试3：状态转换 ====================


class TestStateTransitions:
    """测试状态转换"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.9,
                "reasoning": "普通对话",
            }
        )
        llm.generate_response = AsyncMock(return_value="回复内容")
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        return create_test_session_context()

    def test_transition_idle_to_processing(self, mock_session_context, mock_llm):
        """IDLE -> PROCESSING 转换"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        # 开始处理
        agent.transition_to(ConversationAgentState.PROCESSING)

        assert agent.state == ConversationAgentState.PROCESSING

    def test_transition_processing_to_waiting(self, mock_session_context, mock_llm):
        """PROCESSING -> WAITING_FOR_SUBAGENT 转换"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)
        agent.transition_to(ConversationAgentState.WAITING_FOR_SUBAGENT)

        assert agent.state == ConversationAgentState.WAITING_FOR_SUBAGENT

    def test_transition_waiting_to_processing(self, mock_session_context, mock_llm):
        """WAITING_FOR_SUBAGENT -> PROCESSING 转换（收到子Agent结果后恢复）"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)
        agent.transition_to(ConversationAgentState.WAITING_FOR_SUBAGENT)
        agent.transition_to(ConversationAgentState.PROCESSING)

        assert agent.state == ConversationAgentState.PROCESSING

    def test_transition_processing_to_completed(self, mock_session_context, mock_llm):
        """PROCESSING -> COMPLETED 转换"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)
        agent.transition_to(ConversationAgentState.COMPLETED)

        assert agent.state == ConversationAgentState.COMPLETED

    def test_invalid_transition_raises_error(self, mock_session_context, mock_llm):
        """无效转换应抛出异常"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )
        from src.domain.exceptions import DomainError

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        # IDLE 不能直接转到 COMPLETED
        with pytest.raises(DomainError, match="Invalid state transition"):
            agent.transition_to(ConversationAgentState.COMPLETED)


# ==================== 测试4：子Agent等待管理 ====================


class TestSubAgentWaiting:
    """测试子Agent等待管理"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.9,
                "reasoning": "普通对话",
            }
        )
        llm.generate_response = AsyncMock(return_value="回复内容")
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        return create_test_session_context()

    def test_wait_for_subagent_stores_context(self, mock_session_context, mock_llm):
        """等待子Agent时应保存上下文"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)

        # 等待子Agent
        agent.wait_for_subagent(
            subagent_id="subagent_001",
            task_id="task_001",
            context={"current_step": 3, "user_input": "测试"},
        )

        assert agent.state == ConversationAgentState.WAITING_FOR_SUBAGENT
        assert agent.pending_subagent_id == "subagent_001"
        assert agent.pending_task_id == "task_001"
        assert agent.suspended_context is not None
        assert agent.suspended_context["current_step"] == 3

    def test_resume_from_subagent_restores_context(self, mock_session_context, mock_llm):
        """恢复执行时应还原上下文"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)
        agent.wait_for_subagent(
            subagent_id="subagent_001",
            task_id="task_001",
            context={"current_step": 3},
        )

        # 模拟子Agent返回结果
        subagent_result = {
            "success": True,
            "output": {"data": "搜索结果"},
        }

        context = agent.resume_from_subagent(subagent_result)

        assert agent.state == ConversationAgentState.PROCESSING
        assert agent.pending_subagent_id is None
        assert agent.pending_task_id is None
        assert context["current_step"] == 3
        assert context["subagent_result"] == subagent_result

    def test_resume_clears_pending_state(self, mock_session_context, mock_llm):
        """恢复后应清除待处理状态"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)
        agent.wait_for_subagent(
            subagent_id="subagent_001",
            task_id="task_001",
            context={},
        )

        agent.resume_from_subagent({"success": True, "output": {}})

        assert agent.suspended_context is None


# ==================== 测试5：状态查询方法 ====================


class TestStateQueryMethods:
    """测试状态查询方法"""

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

    def test_is_waiting_for_subagent(self, mock_session_context, mock_llm):
        """is_waiting_for_subagent 方法"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        assert agent.is_waiting_for_subagent() is False

        agent.transition_to(ConversationAgentState.PROCESSING)
        agent.wait_for_subagent(subagent_id="s1", task_id="t1", context={})

        assert agent.is_waiting_for_subagent() is True

    def test_is_processing(self, mock_session_context, mock_llm):
        """is_processing 方法"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        assert agent.is_processing() is False

        agent.transition_to(ConversationAgentState.PROCESSING)

        assert agent.is_processing() is True

    def test_is_idle(self, mock_session_context, mock_llm):
        """is_idle 方法"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
        )

        assert agent.is_idle() is True

        agent.transition_to(ConversationAgentState.PROCESSING)

        assert agent.is_idle() is False


# ==================== 测试6：状态转换事件 ====================


class TestStateTransitionEvents:
    """测试状态转换事件发布"""

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

    @pytest.mark.asyncio  # Added: Make test async to handle asyncio.create_task()
    async def test_transition_publishes_event(self, mock_session_context, mock_llm, mock_event_bus):
        """状态转换应发布事件"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
            StateChangedEvent,
        )

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)

        # Give asyncio.create_task() a chance to run
        import asyncio

        await asyncio.sleep(0.01)  # Allow task to complete

        # 验证事件发布
        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        event = call_args[0][0]

        assert isinstance(event, StateChangedEvent)
        assert event.event_type == "conversation_agent_state_changed"
        assert event.from_state == "idle"
        assert event.to_state == "processing"


# ==================== 测试7：有效转换矩阵 ====================


class TestValidTransitionMatrix:
    """测试有效转换矩阵"""

    def test_valid_transitions_defined(self):
        """有效转换矩阵应被定义"""
        from src.domain.agents.conversation_agent import (
            VALID_STATE_TRANSITIONS,
            ConversationAgentState,
        )

        # IDLE 可转到 PROCESSING
        assert (
            ConversationAgentState.PROCESSING
            in VALID_STATE_TRANSITIONS[ConversationAgentState.IDLE]
        )

        # PROCESSING 可转到 WAITING, COMPLETED, ERROR
        assert (
            ConversationAgentState.WAITING_FOR_SUBAGENT
            in VALID_STATE_TRANSITIONS[ConversationAgentState.PROCESSING]
        )
        assert (
            ConversationAgentState.COMPLETED
            in VALID_STATE_TRANSITIONS[ConversationAgentState.PROCESSING]
        )
        assert (
            ConversationAgentState.ERROR
            in VALID_STATE_TRANSITIONS[ConversationAgentState.PROCESSING]
        )

        # WAITING 可转到 PROCESSING, ERROR
        assert (
            ConversationAgentState.PROCESSING
            in VALID_STATE_TRANSITIONS[ConversationAgentState.WAITING_FOR_SUBAGENT]
        )

    def test_completed_is_terminal(self):
        """COMPLETED 应为终态"""
        from src.domain.agents.conversation_agent import (
            VALID_STATE_TRANSITIONS,
            ConversationAgentState,
        )

        # COMPLETED 只能转到 IDLE（重新开始）
        valid = VALID_STATE_TRANSITIONS.get(ConversationAgentState.COMPLETED, [])
        assert ConversationAgentState.IDLE in valid or len(valid) == 0


# 导出
__all__ = [
    "TestConversationAgentState",
    "TestStateMachineInitialization",
    "TestStateTransitions",
    "TestSubAgentWaiting",
    "TestStateQueryMethods",
    "TestStateTransitionEvents",
    "TestValidTransitionMatrix",
]

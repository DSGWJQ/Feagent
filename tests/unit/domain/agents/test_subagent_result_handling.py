"""测试：子Agent结果回传和上下文写入

测试目标：
1. ConversationAgent 订阅 SubAgentCompletedEvent
2. 收到结果后恢复执行
3. 子Agent结果写入压缩上下文
4. 端到端流程验证

完成标准：
- ConversationAgent 能接收子Agent结果
- 状态正确恢复
- 结果写入上下文
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import GlobalContext, SessionContext


def create_test_session_context(session_id: str = "test_session") -> SessionContext:
    """创建测试用的 SessionContext"""
    global_ctx = GlobalContext(user_id="test_user")
    return SessionContext(session_id=session_id, global_context=global_ctx)


# ==================== 测试1：ConversationAgent 订阅完成事件 ====================


class TestConversationAgentSubscribeCompletionEvent:
    """测试 ConversationAgent 订阅完成事件"""

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
        from src.domain.services.event_bus import EventBus

        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    def test_can_start_completion_listener(self, mock_session_context, mock_llm, mock_event_bus):
        """可以启动完成事件监听器"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        agent.start_subagent_completion_listener()

        # 验证订阅
        mock_event_bus.subscribe.assert_called()


# ==================== 测试2：处理 SubAgentCompletedEvent ====================


class TestHandleSubAgentCompletedEvent:
    """测试处理 SubAgentCompletedEvent"""

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
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()  # Changed: Use AsyncMock for async method
        return event_bus

    @pytest.mark.asyncio  # Added: Make test async
    async def test_handle_completion_resumes_agent(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """处理完成事件应恢复Agent状态"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )
        from src.domain.agents.coordinator_agent import SubAgentCompletedEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        # 设置等待状态
        agent.transition_to(ConversationAgentState.PROCESSING)

        # Give asyncio.create_task() a chance to run
        import asyncio

        await asyncio.sleep(0.01)  # Allow task to complete

        agent.wait_for_subagent(
            subagent_id="subagent_001",
            task_id="task_001",
            context={"step": 3},
        )

        assert agent.state == ConversationAgentState.WAITING_FOR_SUBAGENT

        # 创建完成事件
        event = SubAgentCompletedEvent(
            subagent_id="subagent_001",
            subagent_type="search",
            session_id=mock_session_context.session_id,
            success=True,
            result={"data": "搜索结果"},
        )

        # 处理事件
        agent.handle_subagent_completed(event)

        # 应恢复到处理状态
        assert agent.state == ConversationAgentState.PROCESSING

    @pytest.mark.asyncio  # Added: Make test async
    async def test_handle_completion_stores_result(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """处理完成事件应存储结果"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )
        from src.domain.agents.coordinator_agent import SubAgentCompletedEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)

        # Give asyncio.create_task() a chance to run
        import asyncio

        await asyncio.sleep(0.01)  # Allow task to complete

        agent.wait_for_subagent(
            subagent_id="subagent_001",
            task_id="task_001",
            context={"step": 3},
        )

        event = SubAgentCompletedEvent(
            subagent_id="subagent_001",
            subagent_type="search",
            session_id=mock_session_context.session_id,
            success=True,
            result={"data": "搜索结果"},
        )

        agent.handle_subagent_completed(event)

        # 应存储最近的子Agent结果
        assert agent.last_subagent_result is not None
        assert agent.last_subagent_result["success"] is True
        assert agent.last_subagent_result["data"] == "搜索结果"


# ==================== 测试3：子Agent结果记录 ====================


class TestSubAgentResultHistory:
    """测试子Agent结果历史记录"""

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
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()  # Changed: Use AsyncMock for async method
        return event_bus

    def test_agent_has_subagent_result_history(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """Agent 应有子Agent结果历史"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        assert hasattr(agent, "subagent_result_history")
        assert isinstance(agent.subagent_result_history, list)

    @pytest.mark.asyncio  # Added: Make test async
    async def test_completion_adds_to_history(self, mock_session_context, mock_llm, mock_event_bus):
        """完成事件应添加到历史"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            ConversationAgentState,
        )
        from src.domain.agents.coordinator_agent import SubAgentCompletedEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        agent.transition_to(ConversationAgentState.PROCESSING)

        # Give asyncio.create_task() a chance to run
        import asyncio

        await asyncio.sleep(0.01)  # Allow task to complete

        agent.wait_for_subagent(
            subagent_id="subagent_001",
            task_id="task_001",
            context={},
        )

        event = SubAgentCompletedEvent(
            subagent_id="subagent_001",
            subagent_type="search",
            success=True,
            result={"data": "result1"},
        )

        agent.handle_subagent_completed(event)

        assert len(agent.subagent_result_history) == 1
        assert agent.subagent_result_history[0]["subagent_id"] == "subagent_001"


# ==================== 测试4：Coordinator 上下文写入 ====================


class TestCoordinatorContextWriting:
    """测试 Coordinator 写入子Agent结果到上下文"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    def test_coordinator_has_subagent_result_storage(self, mock_event_bus):
        """Coordinator 应有子Agent结果存储"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        assert hasattr(coordinator, "subagent_results")
        assert isinstance(coordinator.subagent_results, dict)

    @pytest.mark.asyncio
    async def test_execute_subagent_stores_result(self, mock_event_bus):
        """执行子Agent应存储结果"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        class SimpleAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(self, task, context):
                return {"result": "success"}

            def get_capabilities(self):
                return {}

        coordinator.register_subagent_type(SubAgentType.SEARCH, SimpleAgent)

        _result = await coordinator.execute_subagent(
            subagent_type="search",
            task_payload={},
            context={},
            session_id="session_001",
        )

        # 结果应被记录
        assert "session_001" in coordinator.subagent_results
        assert len(coordinator.subagent_results["session_001"]) == 1


# ==================== 测试5：获取会话的子Agent结果 ====================


class TestGetSessionSubAgentResults:
    """测试获取会话的子Agent结果"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    def test_can_get_session_results(self, mock_event_bus):
        """可以获取会话的子Agent结果"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        # 添加一些测试数据
        coordinator.subagent_results["session_001"] = [
            {"subagent_id": "s1", "success": True, "result": {"data": "r1"}},
            {"subagent_id": "s2", "success": True, "result": {"data": "r2"}},
        ]

        results = coordinator.get_session_subagent_results("session_001")

        assert len(results) == 2
        assert results[0]["subagent_id"] == "s1"

    def test_get_empty_for_unknown_session(self, mock_event_bus):
        """未知会话应返回空列表"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        results = coordinator.get_session_subagent_results("unknown_session")

        assert results == []


# 导出
__all__ = [
    "TestConversationAgentSubscribeCompletionEvent",
    "TestHandleSubAgentCompletedEvent",
    "TestSubAgentResultHistory",
    "TestCoordinatorContextWriting",
    "TestGetSessionSubAgentResults",
]

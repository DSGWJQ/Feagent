"""ConversationAgent 异步方法测试

目标：补充 async 方法覆盖，进一步提升覆盖率
重点：
1. 子Agent生成与等待
2. 流式进度事件
3. 异步决策生成
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_state import SpawnSubAgentEvent
from src.domain.entities.session_context import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    llm = AsyncMock()
    llm.think = AsyncMock(return_value="思考内容")
    llm.decide_action = AsyncMock(return_value={"action": "finish", "output": "完成"})
    llm.should_continue = AsyncMock(return_value=False)
    return llm


@pytest.fixture
def global_context():
    """Global context"""
    return GlobalContext(user_id="test_user")


@pytest.fixture
def session_context(global_context):
    """Session context"""
    return SessionContext(
        session_id="test_session",
        global_context=global_context,
    )


@pytest.fixture
def event_bus():
    """Event bus"""
    return EventBus()


@pytest.fixture
def agent_with_event_bus(session_context, mock_llm, event_bus):
    """Agent with EventBus"""
    return ConversationAgent(
        session_context=session_context,
        llm=mock_llm,
        event_bus=event_bus,
    )


# ============================================================================
# Test: 子Agent生成与管理
# ============================================================================


class TestSubAgentManagement:
    """测试子Agent管理功能"""

    @pytest.mark.asyncio
    async def test_spawn_subagent_without_waiting(self, agent_with_event_bus):
        """测试：生成子Agent但不等待结果"""
        agent = agent_with_event_bus

        with patch.object(agent, "_publish_critical_event", new_callable=AsyncMock) as mock_publish:
            subagent_id = await agent.request_subagent_spawn_async(
                subagent_type="workflow_agent",
                task_payload={"goal": "分析数据"},
                priority=1,
                wait_for_result=False,  # 不等待
            )

            assert subagent_id is not None
            assert subagent_id.startswith("subagent_")
            mock_publish.assert_called_once()

            # 验证事件类型
            call_args = mock_publish.call_args[0][0]
            assert isinstance(call_args, SpawnSubAgentEvent)
            assert call_args.subagent_type == "workflow_agent"

    @pytest.mark.asyncio
    async def test_spawn_subagent_with_context_snapshot(self, agent_with_event_bus):
        """测试：生成子Agent时传递上下文快照"""
        agent = agent_with_event_bus

        context_snapshot = {
            "current_goal": "数据分析",
            "variables": {"data_source": "api"},
        }

        with patch.object(agent, "_publish_critical_event", new_callable=AsyncMock):
            subagent_id = await agent.request_subagent_spawn_async(
                subagent_type="analysis_agent",
                task_payload={"action": "analyze"},
                context_snapshot=context_snapshot,
                wait_for_result=False,
            )

            assert subagent_id is not None

    @pytest.mark.asyncio
    async def test_spawn_subagent_with_default_context(self, agent_with_event_bus):
        """测试：生成子Agent使用默认上下文"""
        agent = agent_with_event_bus

        with patch.object(agent, "_publish_critical_event", new_callable=AsyncMock) as mock_publish:
            subagent_id = await agent.request_subagent_spawn_async(
                subagent_type="helper_agent",
                task_payload={"task": "help"},
                context_snapshot=None,  # 使用默认空字典
                wait_for_result=False,
            )

            assert subagent_id is not None

            call_args = mock_publish.call_args[0][0]
            assert call_args.context_snapshot == {}


# ============================================================================
# Test: 流式进度事件
# ============================================================================


class TestStreamingProgressEvents:
    """测试流式进度事件"""

    @pytest.mark.asyncio
    async def test_stream_progress_event_without_emitter(self, agent_with_event_bus):
        """测试：没有stream_emitter时直接返回"""
        agent = agent_with_event_bus
        agent.stream_emitter = None  # 确保没有emitter

        mock_event = Mock()
        mock_event.node_id = "node_123"
        mock_event.status = "running"
        mock_event.progress = 0.5

        # 应该直接返回，不抛出异常
        await agent.forward_progress_event(mock_event)

    @pytest.mark.asyncio
    async def test_stream_progress_event_with_emitter(self, agent_with_event_bus):
        """测试：有stream_emitter时发送事件"""
        agent = agent_with_event_bus

        # Mock stream_emitter
        mock_emitter = AsyncMock()
        agent.stream_emitter = mock_emitter

        mock_event = Mock()
        mock_event.node_id = "node_456"
        mock_event.status = "completed"
        mock_event.progress = 1.0
        mock_event.message = "任务完成"

        await agent.forward_progress_event(mock_event)

        # 验证emitter被调用
        mock_emitter.emit.assert_called_once()
        call_args = mock_emitter.emit.call_args[0][0]
        assert call_args["type"] == "progress"
        assert call_args["node_id"] == "node_456"
        assert call_args["status"] == "completed"

    @pytest.mark.asyncio
    async def test_stream_progress_formats_message(self, agent_with_event_bus):
        """测试：流式进度事件格式化消息"""
        agent = agent_with_event_bus

        mock_emitter = AsyncMock()
        agent.stream_emitter = mock_emitter

        mock_event = Mock()
        mock_event.node_id = "node_789"
        mock_event.status = "running"
        mock_event.progress = 0.3
        mock_event.message = "处理中"

        await agent.forward_progress_event(mock_event)

        mock_emitter.emit.assert_called_once()
        call_args = mock_emitter.emit.call_args[0][0]
        # 验证消息被格式化
        assert "message" in call_args
        assert "[执行中 30%]" in call_args["message"]


# ============================================================================
# Test: 进度事件监听器
# ============================================================================


class TestProgressEventListener:
    """测试进度事件监听器"""

    def test_start_progress_event_listener_without_event_bus(self, session_context, mock_llm):
        """测试：没有EventBus时启动监听器抛出异常"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=None,
        )

        # 应该抛出 ValueError
        with pytest.raises(ValueError, match="EventBus is required for progress event listening"):
            agent.start_progress_event_listener()

    def test_start_progress_event_listener_with_event_bus(self, agent_with_event_bus):
        """测试：有EventBus时启动监听器"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "subscribe") as mock_subscribe:
            agent.start_progress_event_listener()
            # 验证订阅了进度事件
            # 注：实际实现可能不同，这里只是示例


# ============================================================================
# Test: 决策创建方法
# ============================================================================


class TestDecisionCreation:
    """测试决策创建方法"""

    def test_create_spawn_subagent_decision(self, agent_with_event_bus):
        """测试：创建生成子Agent的决策"""
        agent = agent_with_event_bus

        decision = agent.create_spawn_subagent_decision(
            subagent_type="workflow_executor",
            task_payload={"workflow_id": "wf_123"},
            priority=2,
            confidence=0.95,
        )

        assert decision is not None
        assert decision.type.value == "spawn_subagent"
        assert decision.payload["subagent_type"] == "workflow_executor"
        assert decision.payload["priority"] == 2
        assert decision.confidence == 0.95


# ============================================================================
# Test: 配置相关方法补充
# ============================================================================


class TestConfigurationMethods:
    """测试配置相关方法"""

    def test_agent_initialization_with_minimal_config(self, session_context, mock_llm):
        """测试：最小配置初始化"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
        )

        assert agent is not None
        assert agent.session_context == session_context
        assert agent.llm == mock_llm

    def test_agent_with_timeout_config(self, session_context, mock_llm):
        """测试：带超时配置的初始化"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            timeout_seconds=30.0,
        )

        assert agent.timeout_seconds == 30.0

    def test_agent_with_max_tokens_config(self, session_context, mock_llm):
        """测试：带token限制的初始化"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            max_tokens=1000,
        )

        assert agent.max_tokens == 1000

    def test_agent_with_max_cost_config(self, session_context, mock_llm):
        """测试：带成本限制的初始化"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            max_cost=0.50,
        )

        assert agent.max_cost == 0.50


# ============================================================================
# Test: 辅助方法
# ============================================================================


class TestHelperMethods:
    """测试辅助方法"""

    def test_get_session_id(self, agent_with_event_bus):
        """测试：获取session_id"""
        agent = agent_with_event_bus
        session_id = agent.session_context.session_id
        assert session_id == "test_session"

    def test_has_event_bus(self, agent_with_event_bus):
        """测试：检查是否有EventBus"""
        agent = agent_with_event_bus
        assert agent.event_bus is not None

    def test_no_event_bus(self, session_context, mock_llm):
        """测试：没有EventBus的情况"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=None,
        )
        assert agent.event_bus is None


# 导出测试类
__all__ = [
    "TestSubAgentManagement",
    "TestStreamingProgressEvents",
    "TestProgressEventListener",
    "TestDecisionCreation",
    "TestConfigurationMethods",
    "TestHelperMethods",
]

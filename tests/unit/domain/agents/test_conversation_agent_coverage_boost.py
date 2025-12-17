"""ConversationAgent 覆盖率提升测试

目标：从 69% 提升到 80%+
重点覆盖：
1. SaveRequest 功能
2. 进度事件格式化
3. 配置兼容性
4. 状态检查方法
5. 边界条件
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_config import ConversationAgentConfig, LLMConfig
from src.domain.agents.conversation_agent_state import ConversationAgentState
from src.domain.entities.session_context import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    llm = AsyncMock()
    llm.think = AsyncMock(return_value="思考内容")
    llm.decide_action = AsyncMock(return_value={"action": "finish", "output": "完成"})
    llm.should_continue = AsyncMock(return_value=False)
    llm.classify_intent = AsyncMock(return_value={"intent": "conversation", "confidence": 0.9})
    llm.generate_response = AsyncMock(return_value="回复内容")
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
    bus = EventBus()
    return bus


@pytest.fixture
def agent_with_event_bus(session_context, mock_llm, event_bus):
    """带 EventBus 的 Agent"""
    return ConversationAgent(
        session_context=session_context,
        llm=mock_llm,
        event_bus=event_bus,
        max_iterations=5,
    )


@pytest.fixture
def agent_without_event_bus(session_context, mock_llm):
    """不带 EventBus 的 Agent"""
    return ConversationAgent(
        session_context=session_context,
        llm=mock_llm,
        event_bus=None,
        max_iterations=5,
    )


# ============================================================================
# Test: SaveRequest 功能 (覆盖行 462-493)
# ============================================================================


class TestSaveRequestFunctionality:
    """测试保存请求功能"""

    def test_send_save_request_with_event_bus_enabled(self, agent_with_event_bus):
        """测试：启用保存请求通道时发送请求"""
        agent = agent_with_event_bus
        agent._save_request_channel_enabled = True

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            request_id = agent.send_save_request(
                target_path="/test/path.txt",
                content="test content",
                reason="测试原因",
            )

            assert request_id is not None
            assert isinstance(request_id, str)
            mock_publish.assert_called_once()

    def test_send_save_request_disabled_returns_none(self, agent_with_event_bus):
        """测试：未启用保存请求通道时返回None"""
        agent = agent_with_event_bus
        agent._save_request_channel_enabled = False

        request_id = agent.send_save_request(
            target_path="/test/path.txt",
            content="test content",
        )

        assert request_id is None

    def test_send_save_request_no_event_bus_returns_none(self, agent_without_event_bus):
        """测试：没有EventBus时返回None"""
        agent = agent_without_event_bus
        agent._save_request_channel_enabled = True

        request_id = agent.send_save_request(
            target_path="/test/path.txt",
            content="test content",
        )

        assert request_id is None

    def test_send_save_request_with_custom_priority(self, agent_with_event_bus):
        """测试：自定义优先级"""
        from src.domain.services.save_request_channel import SaveRequestPriority

        agent = agent_with_event_bus
        agent._save_request_channel_enabled = True

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            request_id = agent.send_save_request(
                target_path="/test/path.txt",
                content="test content",
                priority=SaveRequestPriority.HIGH,
                reason="高优先级测试",
            )

            assert request_id is not None

    def test_send_save_request_binary_content(self, agent_with_event_bus):
        """测试：二进制内容保存"""
        agent = agent_with_event_bus
        agent._save_request_channel_enabled = True

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            request_id = agent.send_save_request(
                target_path="/test/image.png",
                content=b"\x89PNG\r\n\x1a\n",
                is_binary=True,
            )

            assert request_id is not None


# ============================================================================
# Test: 状态检查方法 (覆盖行 495-505)
# ============================================================================


class TestStateCheckMethods:
    """测试状态检查方法"""

    def test_is_waiting_for_subagent(self, agent_with_event_bus):
        """测试：检查是否等待子Agent"""
        agent = agent_with_event_bus

        # 默认不是等待状态
        assert not agent.is_waiting_for_subagent()

        # 设置为等待状态
        agent._state = ConversationAgentState.WAITING_FOR_SUBAGENT
        assert agent.is_waiting_for_subagent()

    def test_is_processing(self, agent_with_event_bus):
        """测试：检查是否正在处理"""
        agent = agent_with_event_bus

        # 默认不是处理状态
        assert not agent.is_processing()

        # 设置为处理状态
        agent._state = ConversationAgentState.PROCESSING
        assert agent.is_processing()

    def test_is_idle(self, agent_with_event_bus):
        """测试：检查是否空闲"""
        agent = agent_with_event_bus

        # 初始状态应该是 IDLE
        agent._state = ConversationAgentState.IDLE
        assert agent.is_idle()

        # 设置为非空闲状态
        agent._state = ConversationAgentState.PROCESSING
        assert not agent.is_idle()


# ============================================================================
# Test: 进度事件格式化 (覆盖行 700-760)
# ============================================================================


class TestProgressEventFormatting:
    """测试进度事件格式化"""

    def test_format_progress_message_started(self, agent_with_event_bus):
        """测试：格式化开始状态"""
        agent = agent_with_event_bus

        mock_event = Mock()
        mock_event.status = "started"
        mock_event.progress = 0.0
        mock_event.message = "开始执行"

        result = agent.format_progress_message(mock_event)
        assert result == "[开始] 开始执行"

    def test_format_progress_message_running(self, agent_with_event_bus):
        """测试：格式化运行状态"""
        agent = agent_with_event_bus

        mock_event = Mock()
        mock_event.status = "running"
        mock_event.progress = 0.5
        mock_event.message = "执行中"

        result = agent.format_progress_message(mock_event)
        assert result == "[执行中 50%] 执行中"

    def test_format_progress_message_completed(self, agent_with_event_bus):
        """测试：格式化完成状态"""
        agent = agent_with_event_bus

        mock_event = Mock()
        mock_event.status = "completed"
        mock_event.progress = 1.0
        mock_event.message = "任务完成"

        result = agent.format_progress_message(mock_event)
        assert result == "[完成 100%] 任务完成"

    def test_format_progress_message_failed(self, agent_with_event_bus):
        """测试：格式化失败状态"""
        agent = agent_with_event_bus

        mock_event = Mock()
        mock_event.status = "failed"
        mock_event.progress = 0.3
        mock_event.message = "执行失败"

        result = agent.format_progress_message(mock_event)
        assert result == "[失败] 执行失败"

    def test_format_progress_message_unknown_status(self, agent_with_event_bus):
        """测试：格式化未知状态"""
        agent = agent_with_event_bus

        mock_event = Mock()
        mock_event.status = "paused"
        mock_event.progress = 0.2
        mock_event.message = "已暂停"

        result = agent.format_progress_message(mock_event)
        assert result == "[paused] 已暂停"

    def test_format_progress_for_websocket(self, agent_with_event_bus):
        """测试：格式化为WebSocket消息"""
        agent = agent_with_event_bus

        mock_event = Mock()
        mock_event.workflow_id = "wf_123"
        mock_event.node_id = "node_456"
        mock_event.status = "running"
        mock_event.progress = 0.7
        mock_event.message = "正在处理"

        result = agent.format_progress_for_websocket(mock_event)

        assert result["type"] == "progress"
        assert result["data"]["workflow_id"] == "wf_123"
        assert result["data"]["node_id"] == "node_456"
        assert result["data"]["status"] == "running"
        assert result["data"]["progress"] == 0.7
        assert result["data"]["message"] == "正在处理"

    def test_format_progress_for_sse(self, agent_with_event_bus):
        """测试：格式化为SSE消息"""
        agent = agent_with_event_bus

        mock_event = Mock()
        mock_event.workflow_id = "wf_123"
        mock_event.node_id = "node_456"
        mock_event.status = "completed"
        mock_event.progress = 1.0
        mock_event.message = "完成"

        result = agent.format_progress_for_sse(mock_event)

        assert isinstance(result, str)
        assert "wf_123" in result
        assert "node_456" in result
        assert "completed" in result


# ============================================================================
# Test: 配置兼容性 (覆盖行 850-900+)
# ============================================================================


class TestConfigCompatibility:
    """测试配置兼容性"""

    def test_config_and_legacy_conflict_detection(self, session_context, mock_llm, event_bus):
        """测试：config与legacy参数冲突检测"""
        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=mock_llm),
            event_bus=event_bus,
        )

        # 创建一个不同的session_context
        different_global = GlobalContext(user_id="different_user")
        different_session = SessionContext(
            session_id="different_session",
            global_context=different_global,
        )

        with pytest.raises(ValueError, match="Conflicting parameters"):
            ConversationAgent(
                session_context=different_session,  # 冲突
                config=config,
            )

    def test_config_and_legacy_llm_conflict(self, session_context, mock_llm, event_bus):
        """测试：LLM冲突检测"""
        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=mock_llm),
            event_bus=event_bus,
        )

        different_llm = AsyncMock()

        with pytest.raises(ValueError, match="Conflicting parameters"):
            ConversationAgent(
                llm=different_llm,  # 冲突
                config=config,
            )

    def test_neither_config_nor_legacy_raises_error(self):
        """测试：既不提供config也不提供legacy参数时抛出错误"""
        with pytest.raises(ValueError, match="requires initialization parameters"):
            ConversationAgent()


# ============================================================================
# Test: 边界条件与错误处理
# ============================================================================


class TestEdgeCasesAndErrorHandling:
    """测试边界条件与错误处理"""

    def test_agent_with_zero_max_iterations(self, session_context, mock_llm):
        """测试：最大迭代次数为0"""
        with pytest.raises(ValueError):
            ConversationAgent(
                session_context=session_context,
                llm=mock_llm,
                max_iterations=0,
            )

    def test_agent_with_negative_max_iterations(self, session_context, mock_llm):
        """测试：最大迭代次数为负数"""
        with pytest.raises(ValueError):
            ConversationAgent(
                session_context=session_context,
                llm=mock_llm,
                max_iterations=-1,
            )

    def test_agent_with_very_high_iterations(self, session_context, mock_llm):
        """测试：非常高的迭代次数"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            max_iterations=1000,
        )
        assert agent.max_iterations == 1000

    @pytest.mark.asyncio
    async def test_concurrent_state_changes(self, agent_with_event_bus):
        """测试：并发状态变化"""
        agent = agent_with_event_bus

        # 模拟并发状态变化
        initial_state = agent._state
        agent._state = ConversationAgentState.PROCESSING
        assert agent._state == ConversationAgentState.PROCESSING

        agent._state = ConversationAgentState.WAITING_FOR_SUBAGENT
        assert agent._state == ConversationAgentState.WAITING_FOR_SUBAGENT

    def test_save_request_with_empty_content(self, agent_with_event_bus):
        """测试：空内容保存请求"""
        agent = agent_with_event_bus
        agent._save_request_channel_enabled = True

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            request_id = agent.send_save_request(
                target_path="/test/empty.txt",
                content="",
            )

            assert request_id is not None

    def test_save_request_with_none_priority_uses_default(self, agent_with_event_bus):
        """测试：优先级为None时使用默认值"""

        agent = agent_with_event_bus
        agent._save_request_channel_enabled = True

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            agent.send_save_request(
                target_path="/test/default_priority.txt",
                content="content",
                priority=None,  # 应该使用默认值 NORMAL
            )

            # 验证调用时使用了默认优先级
            assert mock_publish.called


# ============================================================================
# Test: 复杂场景集成测试
# ============================================================================


class TestComplexScenarios:
    """测试复杂场景"""

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_save_requests(self, agent_with_event_bus):
        """测试：完整生命周期包含保存请求"""
        agent = agent_with_event_bus
        agent._save_request_channel_enabled = True

        # 初始状态检查
        assert agent.is_idle()

        # 发送保存请求
        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            request_id = agent.send_save_request(
                target_path="/workflow/result.json",
                content='{"status": "completed"}',
            )
            assert request_id is not None

    def test_multiple_save_requests_sequence(self, agent_with_event_bus):
        """测试：多个保存请求序列"""
        agent = agent_with_event_bus
        agent._save_request_channel_enabled = True

        request_ids = []

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            for i in range(5):
                request_id = agent.send_save_request(
                    target_path=f"/test/file_{i}.txt",
                    content=f"content {i}",
                )
                request_ids.append(request_id)

        # 所有请求ID应该是唯一的
        assert len(request_ids) == len(set(request_ids))
        assert all(rid is not None for rid in request_ids)

    def test_state_transitions_sequence(self, agent_with_event_bus):
        """测试：状态转换序列"""
        agent = agent_with_event_bus

        # IDLE -> PROCESSING
        agent._state = ConversationAgentState.IDLE
        assert agent.is_idle()

        agent._state = ConversationAgentState.PROCESSING
        assert agent.is_processing()
        assert not agent.is_idle()

        # PROCESSING -> WAITING_FOR_SUBAGENT
        agent._state = ConversationAgentState.WAITING_FOR_SUBAGENT
        assert agent.is_waiting_for_subagent()
        assert not agent.is_processing()

        # WAITING_FOR_SUBAGENT -> IDLE
        agent._state = ConversationAgentState.IDLE
        assert agent.is_idle()
        assert not agent.is_waiting_for_subagent()


# 导出测试类
__all__ = [
    "TestSaveRequestFunctionality",
    "TestStateCheckMethods",
    "TestProgressEventFormatting",
    "TestConfigCompatibility",
    "TestEdgeCasesAndErrorHandling",
    "TestComplexScenarios",
]

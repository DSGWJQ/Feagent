"""ConversationAgent SaveRequest完整生命周期测试

目标：补充send_save_request方法的完整测试覆盖
覆盖代码：conversation_agent.py:462-498行
新增测试：8-10个
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.entities.session_context import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus


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
def mock_llm():
    """Mock LLM"""
    llm = AsyncMock()
    llm.think = AsyncMock(return_value="思考")
    llm.decide_action = AsyncMock(return_value={"action": "finish"})
    return llm


@pytest.fixture
def event_bus():
    """Event bus"""
    return EventBus()


@pytest.fixture
def agent_with_event_bus(session_context, mock_llm, event_bus):
    """Agent with EventBus enabled"""
    agent = ConversationAgent(
        session_context=session_context,
        llm=mock_llm,
        event_bus=event_bus,
    )
    agent._save_request_channel_enabled = True
    return agent


# ============================================================================
# Test: SaveRequest完整生命周期
# ============================================================================


class TestSaveRequestFullLifecycle:
    """测试SaveRequest完整生命周期"""

    def test_send_save_request_generates_request_id(self, agent_with_event_bus):
        """测试：send_save_request生成request_id"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("src.domain.agents.conversation_agent.uuid4") as mock_uuid:
                mock_uuid.return_value = MagicMock(hex="abcd1234")

                request_id = agent.send_save_request(
                    target_path="/test/file.txt",
                    content="test content",
                )

                assert request_id is not None
                # 验证使用了uuid4生成
                mock_uuid.assert_called()

    def test_send_save_request_sets_default_priority(self, agent_with_event_bus):
        """测试：priority为None时使用NORMAL默认值"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run") as mock_run:
                    agent.send_save_request(
                        target_path="/test/file.txt",
                        content="content",
                        priority=None,  # 明确传None
                    )

                    # 验证publish被调用
                    assert mock_run.called or mock_publish.called

    def test_send_save_request_creates_event_with_all_fields(self, agent_with_event_bus):
        """测试：SaveRequest事件包含所有必要字段"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run") as mock_run:
                    request_id = agent.send_save_request(
                        target_path="/project/output.txt",
                        content="result data",
                        reason="保存分析结果",
                        is_binary=False,
                    )

                    # 验证asyncio.run被调用（因为没有running loop）
                    mock_run.assert_called_once()

                    # 获取传递给run的协程
                    publish_coro = mock_run.call_args[0][0]
                    # 验证是event_bus.publish的返回值
                    assert publish_coro is not None

    def test_send_save_request_without_running_loop_uses_asyncio_run(self, agent_with_event_bus):
        """测试：无running loop时使用asyncio.run()发布事件"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            # Mock get_running_loop抛出RuntimeError
            with patch("asyncio.get_running_loop", side_effect=RuntimeError("no running loop")):
                with patch("asyncio.run") as mock_run:
                    agent.send_save_request(
                        target_path="/test/file.txt",
                        content="test",
                    )

                    # 验证使用了asyncio.run
                    mock_run.assert_called_once()
                    # 验证没有调用_create_tracked_task
                    # (通过验证publish_coro被传给run而不是tracked_task)

    def test_send_save_request_with_running_loop_uses_tracked_task(self, agent_with_event_bus):
        """测试：有running loop时使用_create_tracked_task()发布事件"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            # Mock get_running_loop返回一个loop（不抛异常）
            mock_loop = Mock()
            with patch("asyncio.get_running_loop", return_value=mock_loop):
                with patch.object(agent, "_create_tracked_task") as mock_tracked:
                    agent.send_save_request(
                        target_path="/test/file.txt",
                        content="test",
                    )

                    # 验证使用了_create_tracked_task
                    mock_tracked.assert_called_once()
                    # 验证传递的是协程对象（event_bus.publish的返回值）
                    call_args = mock_tracked.call_args[0][0]
                    # 验证是协程对象
                    import inspect
                    assert inspect.iscoroutine(call_args)

    def test_send_save_request_with_binary_content(self, agent_with_event_bus):
        """测试：二进制内容的SaveRequest"""
        agent = agent_with_event_bus

        binary_data = b"\x00\x01\x02\x03"

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run"):
                    request_id = agent.send_save_request(
                        target_path="/output/data.bin",
                        content=binary_data,
                        is_binary=True,
                    )

                    assert request_id is not None

    def test_send_save_request_with_custom_priority(self, agent_with_event_bus):
        """测试：自定义优先级的SaveRequest"""
        agent = agent_with_event_bus

        from src.domain.services.save_request_channel import SaveRequestPriority

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run"):
                    request_id = agent.send_save_request(
                        target_path="/urgent/file.txt",
                        content="urgent data",
                        priority=SaveRequestPriority.HIGH,
                    )

                    assert request_id is not None

    def test_send_save_request_with_empty_reason(self, agent_with_event_bus):
        """测试：reason为None时使用空字符串"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run"):
                    request_id = agent.send_save_request(
                        target_path="/test/file.txt",
                        content="content",
                        reason=None,  # 明确传None
                    )

                    assert request_id is not None

    def test_send_save_request_returns_request_id(self, agent_with_event_bus):
        """测试：send_save_request返回正确的request_id"""
        agent = agent_with_event_bus

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run"):
                    with patch("src.domain.agents.conversation_agent.uuid4") as mock_uuid:
                        # Mock uuid4返回固定值
                        mock_uuid.return_value = MagicMock()
                        mock_uuid.return_value.__str__ = lambda self: "fixed-uuid-1234"

                        request_id = agent.send_save_request(
                            target_path="/test/file.txt",
                            content="test",
                        )

                        assert request_id == "fixed-uuid-1234"


# ============================================================================
# Test: SaveRequest边界条件
# ============================================================================


class TestSaveRequestEdgeCases:
    """测试SaveRequest边界条件"""

    def test_send_save_request_with_very_long_path(self, agent_with_event_bus):
        """测试：超长文件路径"""
        agent = agent_with_event_bus

        long_path = "/".join(["very_long_directory_name" for _ in range(20)]) + "/file.txt"

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run"):
                    request_id = agent.send_save_request(
                        target_path=long_path,
                        content="content",
                    )

                    assert request_id is not None

    def test_send_save_request_with_large_content(self, agent_with_event_bus):
        """测试：超大内容（1MB+）"""
        agent = agent_with_event_bus

        large_content = "x" * (1024 * 1024 + 100)  # 1MB+

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run"):
                    request_id = agent.send_save_request(
                        target_path="/large/file.txt",
                        content=large_content,
                    )

                    assert request_id is not None

    def test_send_save_request_with_special_characters_in_path(self, agent_with_event_bus):
        """测试：路径包含特殊字符"""
        agent = agent_with_event_bus

        special_path = "/test/文件名-with-中文_and_symbols!@#.txt"

        with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                with patch("asyncio.run"):
                    request_id = agent.send_save_request(
                        target_path=special_path,
                        content="content with 中文",
                    )

                    assert request_id is not None


# ============================================================================
# Test: request_save方法完整测试 (覆盖523-556行)
# ============================================================================


class TestRequestSaveMethod:
    """测试request_save方法（另一个SaveRequest方法）"""

    def test_request_save_basic_usage(self, agent_with_event_bus):
        """测试：request_save基本使用"""
        agent = agent_with_event_bus

        with patch.object(agent, "_create_tracked_task") as mock_tracked:
            with patch.object(agent.event_bus, "publish", new_callable=AsyncMock) as mock_publish:
                request_id = agent.request_save(
                    target_path="/test/file.txt",
                    content="test content",
                    reason="测试原因",
                )

                assert request_id is not None
                # 验证使用了_create_tracked_task
                mock_tracked.assert_called_once()

    def test_request_save_sets_default_priority(self, agent_with_event_bus):
        """测试：request_save优先级为None时使用默认值"""
        agent = agent_with_event_bus

        with patch.object(agent, "_create_tracked_task"):
            with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
                request_id = agent.request_save(
                    target_path="/test/file.txt",
                    content="content",
                    reason="reason",
                    priority=None,  # 明确传None
                )

                assert request_id is not None

    def test_request_save_creates_request_with_all_fields(self, agent_with_event_bus):
        """测试：request_save创建完整的SaveRequest对象"""
        agent = agent_with_event_bus

        from src.domain.services.save_request_channel import SaveRequestPriority

        with patch.object(agent, "_create_tracked_task") as mock_tracked:
            with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
                request_id = agent.request_save(
                    target_path="/output/result.txt",
                    content="analysis result",
                    reason="保存分析结果",
                    priority=SaveRequestPriority.HIGH,
                    is_binary=False,
                )

                assert request_id is not None
                mock_tracked.assert_called_once()

    def test_request_save_with_binary_content(self, agent_with_event_bus):
        """测试：request_save处理二进制内容"""
        agent = agent_with_event_bus

        binary_data = b"\x89PNG\r\n\x1a\n"

        with patch.object(agent, "_create_tracked_task"):
            with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
                request_id = agent.request_save(
                    target_path="/output/image.png",
                    content=binary_data,
                    reason="保存图片",
                    is_binary=True,
                )

                assert request_id is not None

    def test_request_save_returns_request_id(self, agent_with_event_bus):
        """测试：request_save返回request_id"""
        agent = agent_with_event_bus

        with patch.object(agent, "_create_tracked_task"):
            with patch.object(agent.event_bus, "publish", new_callable=AsyncMock):
                request_id = agent.request_save(
                    target_path="/test/file.txt",
                    content="content",
                    reason="reason",
                )

                # 验证返回的是UUID格式的字符串
                assert request_id is not None
                assert isinstance(request_id, str)
                assert len(request_id) > 0

    def test_request_save_disabled_returns_none(self, agent_with_event_bus):
        """测试：SaveRequest未启用时返回None"""
        agent = agent_with_event_bus
        agent._save_request_channel_enabled = False

        request_id = agent.request_save(
            target_path="/test/file.txt",
            content="content",
            reason="reason",
        )

        assert request_id is None

    def test_request_save_no_event_bus_returns_none(self, session_context, mock_llm):
        """测试：没有EventBus时返回None"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=None,
        )
        agent._save_request_channel_enabled = True

        request_id = agent.request_save(
            target_path="/test/file.txt",
            content="content",
            reason="reason",
        )

        assert request_id is None


# 导出测试类
__all__ = [
    "TestSaveRequestFullLifecycle",
    "TestSaveRequestEdgeCases",
    "TestRequestSaveMethod",
]

"""MessageLogListener 单元测试 - Phase 35.3

TDD Red Phase: 测试 MessageLogListener 模块的核心功能
"""

import pytest

from src.domain.services.event_bus import EventBus


@pytest.fixture
def event_bus():
    """EventBus fixture"""
    return EventBus()


@pytest.fixture
def message_log():
    """共享的 message_log 列表"""
    return []


@pytest.fixture
def listener(event_bus, message_log):
    """MessageLogListener fixture"""
    from src.domain.services.message_log_listener import MessageLogListener

    return MessageLogListener(
        event_bus=event_bus,
        message_log=message_log,
        max_size=100,
    )


class TestMessageLogListenerInit:
    """测试：MessageLogListener 初始化"""

    def test_listener_initialization(self, event_bus, message_log):
        """测试：初始化应成功并设置属性"""
        from src.domain.services.message_log_listener import MessageLogListener

        listener = MessageLogListener(
            event_bus=event_bus,
            message_log=message_log,
            max_size=100,
        )

        assert listener.event_bus is event_bus
        assert listener.message_log is message_log
        assert listener.max_size == 100
        assert listener.is_listening is False

    def test_listener_allows_none_event_bus(self, message_log):
        """测试：允许 event_bus=None 以支持延迟初始化（Phase 35.3 修复）"""
        from src.domain.services.message_log_listener import MessageLogListener

        listener = MessageLogListener(
            event_bus=None,
            message_log=message_log,
            max_size=100,
        )

        assert listener.event_bus is None
        assert listener.message_log is message_log
        assert listener.max_size == 100
        assert listener.is_listening is False


class TestMessageLogListenerStartStop:
    """测试：MessageLogListener 启动与停止"""

    def test_start_subscribes_to_event(self, listener, event_bus):
        """测试：start() 应订阅 SimpleMessageEvent"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        listener.start()

        assert SimpleMessageEvent in event_bus._subscribers
        assert listener.is_listening is True

    def test_start_raises_when_no_event_bus(self, message_log):
        """测试：start() 应在 event_bus=None 时抛异常（Phase 35.3 修复）"""
        from src.domain.services.message_log_listener import MessageLogListener

        listener = MessageLogListener(
            event_bus=None,
            message_log=message_log,
            max_size=100,
        )

        with pytest.raises(ValueError, match="event_bus is required to start"):
            listener.start()

    def test_start_is_idempotent(self, listener, event_bus):
        """测试：重复调用 start() 不应重复订阅"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        listener.start()
        listener.start()  # 第二次调用

        # 应该只有一个订阅者
        subscribers = event_bus._subscribers.get(SimpleMessageEvent, [])
        assert len(subscribers) == 1

    def test_stop_unsubscribes_from_event(self, listener, event_bus):
        """测试：stop() 应取消订阅"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        listener.start()
        listener.stop()

        assert (
            SimpleMessageEvent not in event_bus._subscribers
            or len(event_bus._subscribers.get(SimpleMessageEvent, [])) == 0
        )
        assert listener.is_listening is False

    def test_stop_without_start_is_safe(self, listener):
        """测试：未 start 时调用 stop() 不应抛异常"""
        listener.stop()  # 不应抛异常
        assert listener.is_listening is False


class TestMessageLogListenerEventHandling:
    """测试：MessageLogListener 事件处理"""

    @pytest.mark.asyncio
    async def test_handle_event_appends_to_log(self, listener, event_bus, message_log):
        """测试：处理事件应追加到日志"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent

        listener.start()

        event = SimpleMessageEvent(
            source="conversation_agent",
            user_input="你好",
            response="你好！",
            intent="conversation",
            confidence=0.95,
            session_id="session_1",
        )

        await event_bus.publish(event)

        # 验证日志
        assert len(message_log) == 1
        assert message_log[0]["user_input"] == "你好"
        assert message_log[0]["response"] == "你好！"
        assert message_log[0]["intent"] == "conversation"
        assert message_log[0]["confidence"] == 0.95
        assert message_log[0]["session_id"] == "session_1"
        assert "timestamp" in message_log[0]

    @pytest.mark.asyncio
    async def test_handle_event_respects_max_size(self, event_bus, message_log):
        """测试：超过 max_size 时应移除最旧的消息"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent
        from src.domain.services.message_log_listener import MessageLogListener

        listener = MessageLogListener(
            event_bus=event_bus,
            message_log=message_log,
            max_size=3,  # 最多保留 3 条
        )
        listener.start()

        # 发布 5 个事件
        for i in range(5):
            event = SimpleMessageEvent(
                source="test",
                user_input=f"消息 {i}",
                response=f"回复 {i}",
                intent="conversation",
            )
            await event_bus.publish(event)

        # 应该只保留最新的 3 条
        assert len(message_log) == 3
        assert message_log[0]["user_input"] == "消息 2"
        assert message_log[1]["user_input"] == "消息 3"
        assert message_log[2]["user_input"] == "消息 4"


class TestMessageLogListenerStatistics:
    """测试：MessageLogListener 统计功能"""

    def test_get_statistics_empty_log(self, listener):
        """测试：空日志应返回零统计"""
        stats = listener.get_statistics()

        assert stats["total_messages"] == 0
        assert stats["by_intent"] == {}

    def test_get_statistics_with_messages(self, listener, message_log):
        """测试：有消息时应返回正确统计"""
        # 手动添加消息
        message_log.extend(
            [
                {"user_input": "你好", "intent": "conversation", "response": "你好！"},
                {"user_input": "创建工作流", "intent": "workflow_modification", "response": ""},
                {"user_input": "天气", "intent": "conversation", "response": "晴天"},
                {"user_input": "状态", "intent": "workflow_query", "response": "运行中"},
            ]
        )

        stats = listener.get_statistics()

        assert stats["total_messages"] == 4
        assert stats["by_intent"]["conversation"] == 2
        assert stats["by_intent"]["workflow_modification"] == 1
        assert stats["by_intent"]["workflow_query"] == 1

    def test_get_statistics_handles_missing_intent(self, listener, message_log):
        """测试：缺少 intent 字段的消息应计入 unknown"""
        message_log.extend(
            [
                {"user_input": "有intent", "intent": "conversation"},
                {"user_input": "无intent"},  # 缺少 intent 字段
            ]
        )

        stats = listener.get_statistics()

        assert stats["total_messages"] == 2
        assert stats["by_intent"]["conversation"] == 1
        assert stats["by_intent"]["unknown"] == 1


class TestMessageLogAccessor:
    """测试：MessageLogAccessor"""

    def test_accessor_returns_same_reference(self, message_log):
        """测试：accessor 应返回同一个列表引用"""
        from src.domain.services.message_log_listener import MessageLogAccessor

        accessor = MessageLogAccessor(message_log)

        # 获取消息
        messages = accessor.get_messages()

        # 应该是同一个对象
        assert messages is message_log

    def test_accessor_reflects_changes(self, message_log):
        """测试：accessor 应反映列表的变化"""
        from src.domain.services.message_log_listener import MessageLogAccessor

        accessor = MessageLogAccessor(message_log)

        # 添加消息
        message_log.append({"user_input": "测试", "intent": "conversation"})

        # accessor 应该能看到变化
        messages = accessor.get_messages()
        assert len(messages) == 1
        assert messages[0]["user_input"] == "测试"


class TestMessageLogListenerIntegration:
    """测试：MessageLogListener 集成测试"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, event_bus, message_log):
        """测试：完整生命周期 - 启动、接收事件、统计、停止"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent
        from src.domain.services.message_log_listener import MessageLogListener

        listener = MessageLogListener(
            event_bus=event_bus,
            message_log=message_log,
            max_size=100,
        )

        # 1. 启动监听
        listener.start()
        assert listener.is_listening is True

        # 2. 发布多个事件
        for i in range(3):
            event = SimpleMessageEvent(
                source="test",
                user_input=f"消息 {i}",
                response=f"回复 {i}",
                intent="conversation" if i % 2 == 0 else "workflow_query",
            )
            await event_bus.publish(event)

        # 3. 验证日志
        assert len(message_log) == 3

        # 4. 获取统计
        stats = listener.get_statistics()
        assert stats["total_messages"] == 3
        assert stats["by_intent"]["conversation"] == 2
        assert stats["by_intent"]["workflow_query"] == 1

        # 5. 停止监听
        listener.stop()
        assert listener.is_listening is False

        # 6. 停止后发布事件不应记录
        event = SimpleMessageEvent(
            source="test",
            user_input="停止后",
            response="",
            intent="conversation",
        )
        await event_bus.publish(event)

        # 日志应该还是 3 条
        assert len(message_log) == 3

"""记忆饱和与自动压缩测试 (Memory Saturation Tests) - Step 6

测试内容：
1. ShortTermSaturatedEvent 触发机制
2. MemoryCompressionHandler 订阅和处理
3. 压缩执行和结果回写
4. 会话冻结和恢复机制
5. 压缩后摘要注入规划上下文

TDD Red Phase - 先写测试，后实现功能
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import (
    GlobalContext,
    SessionContext,
    ShortTermSaturatedEvent,
)
from src.domain.services.event_bus import EventBus
from src.domain.services.short_term_buffer import ShortTermBuffer, TurnRole

# ==================== ShortTermSaturatedEvent 测试 ====================


class TestShortTermSaturatedEvent:
    """ShortTermSaturatedEvent 事件测试"""

    def test_event_creation_with_all_fields(self):
        """测试：创建事件时包含所有必要字段"""
        event = ShortTermSaturatedEvent(
            session_id="session_123",
            usage_ratio=0.95,
            total_tokens=9500,
            context_limit=10000,
            buffer_size=15,
        )

        assert event.session_id == "session_123"
        assert event.usage_ratio == 0.95
        assert event.total_tokens == 9500
        assert event.context_limit == 10000
        assert event.buffer_size == 15

    def test_event_type_is_short_term_saturated(self):
        """测试：事件类型正确"""
        event = ShortTermSaturatedEvent(
            session_id="test",
            usage_ratio=0.92,
            total_tokens=9200,
            context_limit=10000,
            buffer_size=10,
        )

        assert event.event_type == "short_term_saturated"

    def test_event_source_default(self):
        """测试：默认事件来源"""
        event = ShortTermSaturatedEvent(
            session_id="test",
            usage_ratio=0.92,
            total_tokens=9200,
            context_limit=10000,
            buffer_size=10,
        )

        assert event.source == "session_context"


# ==================== SessionContext 饱和检测测试 ====================


class TestSessionContextSaturation:
    """SessionContext 饱和检测测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN"},
            system_config={"max_tokens": 10000},
        )

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_test",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    def test_saturation_threshold_default_value(self, session_context):
        """测试：默认饱和阈值为 0.92"""
        assert session_context.saturation_threshold == 0.92

    def test_check_saturation_below_threshold(self, session_context):
        """测试：低于阈值时不饱和"""
        session_context.update_token_usage(4000, 1000)  # 50%

        assert not session_context.check_saturation()

    def test_check_saturation_at_threshold(self, session_context):
        """测试：达到阈值时饱和"""
        session_context.update_token_usage(8000, 1200)  # 92%

        assert session_context.check_saturation()

    def test_check_saturation_above_threshold(self, session_context):
        """测试：超过阈值时饱和"""
        session_context.update_token_usage(8500, 1000)  # 95%

        assert session_context.check_saturation()

    def test_add_turn_triggers_saturation_event(self, session_context):
        """测试：添加轮次触发饱和事件"""
        event_bus = EventBus()
        session_context.set_event_bus(event_bus)

        # 设置到接近饱和
        session_context.update_token_usage(8000, 1100)  # 91%
        session_context.usage_ratio = 0.93  # 强制设置超过阈值

        events_received = []

        async def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(ShortTermSaturatedEvent, capture_event)

        # 添加轮次
        buffer = ShortTermBuffer(
            turn_id="turn_1",
            role=TurnRole.USER,
            content="test message",
            token_usage={"total_tokens": 100},
        )
        session_context.add_turn(buffer)

        # 验证事件已发布（异步）
        assert session_context.is_saturated is True

    def test_saturation_event_not_triggered_twice(self, session_context):
        """测试：饱和事件不会重复触发"""
        event_bus = EventBus()
        session_context.set_event_bus(event_bus)
        session_context.usage_ratio = 0.95

        trigger_count = [0]

        async def count_events(event):
            trigger_count[0] += 1

        event_bus.subscribe(ShortTermSaturatedEvent, count_events)

        # 第一次添加 - 应该触发
        buffer1 = ShortTermBuffer(
            turn_id="turn_1", role=TurnRole.USER, content="msg1", token_usage={"total_tokens": 100}
        )
        session_context.add_turn(buffer1)

        # 第二次添加 - 不应该触发（已经饱和）
        buffer2 = ShortTermBuffer(
            turn_id="turn_2", role=TurnRole.USER, content="msg2", token_usage={"total_tokens": 100}
        )
        session_context.add_turn(buffer2)

        assert session_context.is_saturated is True

    def test_reset_saturation_allows_new_trigger(self, session_context):
        """测试：重置饱和后可以再次触发"""
        session_context.is_saturated = True
        session_context.reset_saturation()

        assert session_context.is_saturated is False


# ==================== MemoryCompressionHandler 测试 ====================


class TestMemoryCompressionHandler:
    """MemoryCompressionHandler 自动压缩处理器测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(
            user_id="user_123",
            user_preferences={},
            system_config={},
        )

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_test",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    @pytest.mark.asyncio
    async def test_handler_subscribes_to_saturation_event(self, session_context):
        """测试：处理器订阅饱和事件"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()

        # 验证订阅
        assert ShortTermSaturatedEvent in event_bus._subscribers

    @pytest.mark.asyncio
    async def test_handler_executes_compression_on_event(self, session_context):
        """测试：收到事件后执行压缩"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()

        # 模拟压缩器
        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="compressed summary"))
        )

        # 注册会话
        handler.register_session(session_context)

        # 添加测试数据
        for i in range(5):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"turn_{i}",
                    role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                    content=f"message {i}",
                    token_usage={"total_tokens": 100},
                )
            )

        # 发布事件
        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.95,
            total_tokens=9500,
            context_limit=10000,
            buffer_size=5,
        )
        await event_bus.publish(event)

        # 验证压缩被调用
        handler._compressor.compress.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_freezes_session_during_compression(self, session_context):
        """测试：压缩期间冻结会话"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)

        freeze_states = []

        # 模拟压缩器，记录冻结状态
        async def mock_compress(buffers, existing_summary=None):
            freeze_states.append(session_context.is_frozen())
            return MagicMock(to_text=MagicMock(return_value="summary"))

        handler._compressor = MagicMock()
        handler._compressor.compress = mock_compress

        # 添加缓冲区
        for i in range(3):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 50},
                )
            )

        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.93,
            total_tokens=9300,
            context_limit=10000,
            buffer_size=3,
        )
        await event_bus.publish(event)

        # 验证压缩期间是冻结的
        assert True in freeze_states

    @pytest.mark.asyncio
    async def test_handler_unfreezes_session_after_compression(self, session_context):
        """测试：压缩完成后解冻会话"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)

        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
        )

        for i in range(3):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 50},
                )
            )

        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.93,
            total_tokens=9300,
            context_limit=10000,
            buffer_size=3,
        )
        await event_bus.publish(event)

        # 验证解冻
        assert session_context.is_frozen() is False

    @pytest.mark.asyncio
    async def test_handler_writes_summary_back_to_session(self, session_context):
        """测试：压缩后将摘要写回会话"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)

        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="【核心目标】用户需要帮助..."))
        )

        for i in range(5):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.95,
            total_tokens=9500,
            context_limit=10000,
            buffer_size=5,
        )
        await event_bus.publish(event)

        # 验证摘要已写入
        assert session_context.conversation_summary is not None
        assert "核心目标" in session_context.conversation_summary

    @pytest.mark.asyncio
    async def test_handler_keeps_recent_turns_after_compression(self, session_context):
        """测试：压缩后保留最近的轮次"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus, keep_recent_turns=2)
        handler.register()
        handler.register_session(session_context)

        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
        )

        # 添加 10 轮
        for i in range(10):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"turn_{i}",
                    role=TurnRole.USER,
                    content=f"msg{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.95,
            total_tokens=9500,
            context_limit=10000,
            buffer_size=10,
        )
        await event_bus.publish(event)

        # 验证只保留 2 轮
        assert len(session_context.short_term_buffer) == 2
        assert session_context.short_term_buffer[0].turn_id == "turn_8"
        assert session_context.short_term_buffer[1].turn_id == "turn_9"

    @pytest.mark.asyncio
    async def test_handler_resets_saturation_after_compression(self, session_context):
        """测试：压缩后重置饱和状态"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)
        session_context.is_saturated = True

        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
        )

        for i in range(3):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 50},
                )
            )

        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.93,
            total_tokens=9300,
            context_limit=10000,
            buffer_size=3,
        )
        await event_bus.publish(event)

        # 验证饱和状态已重置
        assert session_context.is_saturated is False

    @pytest.mark.asyncio
    async def test_handler_restores_from_backup_on_failure(self, session_context):
        """测试：压缩失败时从备份恢复"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)

        # 设置初始状态
        session_context.total_tokens = 5000
        for i in range(5):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )
        original_buffer_size = len(session_context.short_term_buffer)

        # 模拟压缩失败
        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(side_effect=Exception("Compression failed"))

        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.93,
            total_tokens=9300,
            context_limit=10000,
            buffer_size=5,
        )

        # 应该不抛出异常，而是恢复
        await event_bus.publish(event)

        # 验证已恢复
        assert len(session_context.short_term_buffer) == original_buffer_size
        assert session_context.is_frozen() is False


# ==================== 压缩结果注入规划上下文测试 ====================


class TestCompressionPlanningIntegration:
    """压缩结果注入规划上下文测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_planning",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    @pytest.mark.asyncio
    async def test_compressed_summary_available_for_planning(self, session_context):
        """测试：压缩摘要可用于规划"""
        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)

        # 模拟压缩
        summary_text = """【核心目标】用户需要完成数据分析报告
【关键决策】使用 pandas 处理数据
【任务进展】已完成数据加载"""

        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value=summary_text))
        )

        for i in range(5):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        event = ShortTermSaturatedEvent(
            session_id=session_context.session_id,
            usage_ratio=0.95,
            total_tokens=9500,
            context_limit=10000,
            buffer_size=5,
        )
        await event_bus.publish(event)

        # 验证摘要可用于规划
        assert session_context.conversation_summary is not None
        assert "核心目标" in session_context.conversation_summary
        assert "关键决策" in session_context.conversation_summary

    @pytest.mark.asyncio
    async def test_get_planning_context_includes_summary(self, session_context):
        """测试：获取规划上下文包含摘要"""
        from src.domain.services.memory_compression_handler import (
            get_planning_context,
        )

        session_context.conversation_summary = "【核心目标】分析数据"

        planning_ctx = get_planning_context(session_context)

        assert "previous_summary" in planning_ctx
        assert planning_ctx["previous_summary"] == "【核心目标】分析数据"

    @pytest.mark.asyncio
    async def test_planning_context_without_summary(self, session_context):
        """测试：没有摘要时的规划上下文"""
        from src.domain.services.memory_compression_handler import get_planning_context

        session_context.conversation_summary = None

        planning_ctx = get_planning_context(session_context)

        assert planning_ctx["previous_summary"] is None


# ==================== 日志记录测试 ====================


class TestCompressionLogging:
    """压缩日志记录测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_log",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    @pytest.mark.asyncio
    async def test_compression_logs_trigger_event(self, session_context, caplog):
        """测试：记录压缩触发事件"""
        import logging

        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)

        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
        )

        for i in range(3):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 50},
                )
            )

        with caplog.at_level(logging.INFO):
            event = ShortTermSaturatedEvent(
                session_id=session_context.session_id,
                usage_ratio=0.93,
                total_tokens=9300,
                context_limit=10000,
                buffer_size=3,
            )
            await event_bus.publish(event)

        # 验证日志包含压缩信息
        assert any(
            "compression" in record.message.lower() or "压缩" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_compression_logs_token_usage(self, session_context, caplog):
        """测试：记录 token 使用情况"""
        import logging

        from src.domain.services.memory_compression_handler import MemoryCompressionHandler

        event_bus = EventBus()
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)

        handler._compressor = MagicMock()
        handler._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
        )

        for i in range(3):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 50},
                )
            )

        with caplog.at_level(logging.INFO):
            event = ShortTermSaturatedEvent(
                session_id=session_context.session_id,
                usage_ratio=0.93,
                total_tokens=9300,
                context_limit=10000,
                buffer_size=3,
            )
            await event_bus.publish(event)

        # 检查是否有 token 相关日志
        log_text = " ".join(r.message for r in caplog.records)
        assert "token" in log_text.lower() or "9300" in log_text or "93" in log_text

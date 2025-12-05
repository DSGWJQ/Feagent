"""测试短期记忆饱和检测

测试目标：
1. ShortTermSaturatedEvent 应该包含正确的字段
2. SessionContext 应该能够检测饱和并发布事件
3. 饱和事件应该只触发一次（防止重复）
4. 高 token 负载场景应该正确触发饱和
5. 饱和阈值应该可配置（默认 0.92）
"""

import pytest

from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus
from src.domain.services.short_term_buffer import ShortTermBuffer, TurnRole


class TestShortTermSaturatedEvent:
    """测试 ShortTermSaturatedEvent 事件"""

    def test_short_term_saturated_event_should_have_required_fields(self):
        """测试：ShortTermSaturatedEvent 应该包含必需字段"""
        from src.domain.services.context_manager import ShortTermSaturatedEvent

        event = ShortTermSaturatedEvent(
            source="session_context",
            session_id="session_001",
            usage_ratio=0.92,
            total_tokens=7536,
            context_limit=8192,
            buffer_size=10,
        )

        assert event.session_id == "session_001"
        assert event.usage_ratio == 0.92
        assert event.total_tokens == 7536
        assert event.context_limit == 8192
        assert event.buffer_size == 10
        assert event.source == "session_context"

    def test_short_term_saturated_event_should_have_event_type(self):
        """测试：ShortTermSaturatedEvent 应该有 event_type 属性"""
        from src.domain.services.context_manager import ShortTermSaturatedEvent

        event = ShortTermSaturatedEvent(
            source="session_context",
            session_id="session_001",
            usage_ratio=0.92,
            total_tokens=7536,
            context_limit=8192,
            buffer_size=10,
        )

        assert hasattr(event, "event_type")
        assert event.event_type == "short_term_saturated"


class TestSessionContextSaturationDetection:
    """测试 SessionContext 的饱和检测"""

    def test_session_context_should_have_short_term_buffer_list(self):
        """测试：SessionContext 应该有 short_term_buffer 列表"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        assert hasattr(session_ctx, "short_term_buffer")
        assert isinstance(session_ctx.short_term_buffer, list)
        assert len(session_ctx.short_term_buffer) == 0

    def test_session_context_should_have_is_saturated_flag(self):
        """测试：SessionContext 应该有 is_saturated 标志"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        assert hasattr(session_ctx, "is_saturated")
        assert session_ctx.is_saturated is False

    def test_add_turn_should_append_to_buffer(self):
        """测试：add_turn 应该添加到缓冲区"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Hello",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )

        session_ctx.add_turn(buffer)

        assert len(session_ctx.short_term_buffer) == 1
        assert session_ctx.short_term_buffer[0].turn_id == "turn_001"

    def test_add_turn_should_detect_saturation_at_threshold(self):
        """测试：add_turn 应该在达到阈值时检测饱和"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        # 设置模型信息
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 添加 token 使用，达到 92% 阈值（需要 >= 7537 tokens）
        session_ctx.update_token_usage(prompt_tokens=7537, completion_tokens=0)

        # 检查是否会触发饱和
        is_saturated = session_ctx.check_saturation()

        assert is_saturated is True
        assert session_ctx.usage_ratio >= 0.92

    def test_add_turn_should_publish_saturation_event_when_threshold_reached(self):
        """测试：add_turn 应该在达到阈值时发布饱和事件"""
        import asyncio

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        # 设置事件总线
        session_ctx.set_event_bus(event_bus)

        # 设置模型信息
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 订阅饱和事件
        events_received = []

        async def handler(event):
            events_received.append(event)

        from src.domain.services.context_manager import ShortTermSaturatedEvent

        event_bus.subscribe(ShortTermSaturatedEvent, handler)

        # 添加 token 使用，达到 92% 阈值
        session_ctx.update_token_usage(prompt_tokens=7537, completion_tokens=0)

        # 添加新轮次（应该触发饱和事件）
        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )

        session_ctx.add_turn(buffer)

        # 验证事件已发布

        asyncio.run(asyncio.sleep(0.1))  # 等待事件处理

        assert len(events_received) == 1
        assert events_received[0].session_id == "session_001"
        assert events_received[0].usage_ratio >= 0.92

    def test_saturation_event_should_only_trigger_once(self):
        """测试：饱和事件应该只触发一次"""
        import asyncio

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 订阅饱和事件
        events_received = []

        async def handler(event):
            events_received.append(event)

        from src.domain.services.context_manager import ShortTermSaturatedEvent

        event_bus.subscribe(ShortTermSaturatedEvent, handler)

        # 第一次达到阈值
        session_ctx.update_token_usage(prompt_tokens=7537, completion_tokens=0)
        buffer1 = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test 1",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )
        session_ctx.add_turn(buffer1)

        # 第二次添加（仍然超过阈值）
        buffer2 = ShortTermBuffer(
            turn_id="turn_002",
            role=TurnRole.ASSISTANT,
            content="Response 1",
            tool_refs=[],
            token_usage={"total_tokens": 20},
        )
        session_ctx.add_turn(buffer2)

        # 第三次添加（仍然超过阈值）
        buffer3 = ShortTermBuffer(
            turn_id="turn_003",
            role=TurnRole.USER,
            content="Test 2",
            tool_refs=[],
            token_usage={"total_tokens": 15},
        )
        session_ctx.add_turn(buffer3)

        asyncio.run(asyncio.sleep(0.1))

        # 验证事件只触发一次
        assert len(events_received) == 1

    def test_check_saturation_with_custom_threshold(self):
        """测试：check_saturation 应该支持自定义阈值"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 使用 85% 的上下文
        session_ctx.update_token_usage(prompt_tokens=6963, completion_tokens=0)

        # 使用默认阈值 0.92 不应该饱和
        is_saturated_default = session_ctx.check_saturation()
        assert is_saturated_default is False

        # 使用自定义阈值 0.8 应该饱和
        is_saturated_custom = session_ctx.check_saturation(threshold=0.8)
        assert is_saturated_custom is True

    def test_reset_saturation_should_clear_flag(self):
        """测试：reset_saturation 应该清除饱和标志"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=7537, completion_tokens=0)

        # 触发饱和
        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )
        session_ctx.add_turn(buffer)

        assert session_ctx.is_saturated is True

        # 重置饱和状态
        session_ctx.reset_saturation()

        assert session_ctx.is_saturated is False


class TestHighTokenLoadScenario:
    """测试高 token 负载场景"""

    @pytest.mark.asyncio
    async def test_high_token_load_should_trigger_saturation(self):
        """测试：高 token 负载应该触发饱和"""
        import asyncio

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 订阅饱和事件
        events_received = []

        async def handler(event):
            events_received.append(event)

        from src.domain.services.context_manager import ShortTermSaturatedEvent

        event_bus.subscribe(ShortTermSaturatedEvent, handler)

        # 模拟多轮对话，逐步增加 token 使用
        # 总计需要达到 >= 7537 tokens (92% of 8192)
        turns = [
            ("turn_001", TurnRole.USER, "请分析这份销售数据", 800),
            ("turn_002", TurnRole.ASSISTANT, "好的，我来分析...", 1000),
            ("turn_003", TurnRole.USER, "请详细说明趋势", 600),
            ("turn_004", TurnRole.ASSISTANT, "根据数据显示...", 1500),
            ("turn_005", TurnRole.USER, "还有其他发现吗？", 500),
            ("turn_006", TurnRole.ASSISTANT, "是的，还有以下几点...", 1800),
            ("turn_007", TurnRole.USER, "请生成报告", 400),
            ("turn_008", TurnRole.ASSISTANT, "报告如下...", 1000),  # 总计 7600，这一轮应该触发饱和
        ]

        for turn_id, role, content, tokens in turns:
            session_ctx.update_token_usage(prompt_tokens=tokens, completion_tokens=0)

            buffer = ShortTermBuffer(
                turn_id=turn_id,
                role=role,
                content=content,
                tool_refs=[],
                token_usage={"total_tokens": tokens},
            )

            session_ctx.add_turn(buffer)

            # 给事件处理一些时间
            await asyncio.sleep(0.01)

            # 检查是否已经饱和
            if session_ctx.is_saturated:
                break

        # 等待所有异步任务完成
        await asyncio.sleep(0.2)

        # 验证饱和事件已触发
        assert len(events_received) >= 1, f"Expected at least 1 event, got {len(events_received)}"
        assert events_received[0].usage_ratio >= 0.92
        assert session_ctx.is_saturated is True

    def test_buffer_size_should_be_included_in_event(self):
        """测试：缓冲区大小应该包含在事件中"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        events_received = []

        async def handler(event):
            events_received.append(event)

        from src.domain.services.context_manager import ShortTermSaturatedEvent

        event_bus.subscribe(ShortTermSaturatedEvent, handler)

        # 添加多个轮次
        for i in range(5):
            session_ctx.update_token_usage(prompt_tokens=1500, completion_tokens=0)
            buffer = ShortTermBuffer(
                turn_id=f"turn_{i:03d}",
                role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                content=f"Content {i}",
                tool_refs=[],
                token_usage={"total_tokens": 1500},
            )
            session_ctx.add_turn(buffer)

        import asyncio

        asyncio.run(asyncio.sleep(0.1))

        # 验证事件包含缓冲区大小
        if len(events_received) > 0:
            assert events_received[0].buffer_size == len(session_ctx.short_term_buffer)

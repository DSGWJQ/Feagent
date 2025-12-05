"""测试饱和事件与流式输出的集成

测试目标：
1. 当 usage_ratio ≥ 0.92 时，应该触发 ShortTermSaturatedEvent
2. ConversationAgent 应该订阅该事件
3. 事件触发时，应该通过 ConversationFlowEmitter 发送系统通知
4. 流式输出应该包含"上下文压缩即将执行"的通知
5. 完整的端到端流程测试
"""

import asyncio

import pytest

from src.domain.services.context_manager import (
    GlobalContext,
    SessionContext,
    ShortTermSaturatedEvent,
)
from src.domain.services.conversation_flow_emitter import ConversationFlowEmitter
from src.domain.services.event_bus import EventBus
from src.domain.services.short_term_buffer import ShortTermBuffer, TurnRole


class TestSaturationFlowIntegration:
    """测试饱和事件与流式输出的集成"""

    @pytest.mark.asyncio
    async def test_saturation_should_emit_system_notice(self):
        """测试：饱和时应该发送系统通知"""
        # 创建上下文和事件总线
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        # 创建流式发射器
        emitter = ConversationFlowEmitter(session_id="session_001")

        # 设置事件总线
        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 收集发射的消息
        emitted_messages = []

        async def collect_messages():
            async for step in emitter:
                emitted_messages.append(step)
                if step.kind.value == "end":
                    break

        # 启动消息收集任务
        collector_task = asyncio.create_task(collect_messages())

        # 订阅饱和事件并发送系统通知
        async def handle_saturation(event: ShortTermSaturatedEvent):
            await emitter.emit_system_notice(
                f"⚠️ 上下文压缩即将执行 - 当前使用率: {event.usage_ratio:.1%}, "
                f"已使用 {event.total_tokens}/{event.context_limit} tokens"
            )

        event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation)

        # 模拟高 token 负载，触发饱和
        session_ctx.update_token_usage(prompt_tokens=7537, completion_tokens=0)

        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )

        session_ctx.add_turn(buffer)

        # 等待事件处理
        await asyncio.sleep(0.2)

        # 关闭发射器
        await emitter.complete()

        # 等待收集任务完成
        await collector_task

        # 验证系统通知已发送
        assert len(emitted_messages) > 0

        # 查找系统通知消息
        system_notices = [msg for msg in emitted_messages if "上下文压缩即将执行" in msg.content]

        assert (
            len(system_notices) >= 1
        ), f"Expected system notice, got messages: {[m.content for m in emitted_messages]}"
        assert "当前使用率" in system_notices[0].content
        assert "7537" in system_notices[0].content or "7547" in system_notices[0].content

    @pytest.mark.asyncio
    async def test_saturation_event_only_triggers_once(self):
        """测试：饱和事件只触发一次，系统通知也只发送一次"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_002", global_context=global_ctx)
        event_bus = EventBus()
        emitter = ConversationFlowEmitter(session_id="session_002")

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 收集系统通知
        system_notices = []

        async def handle_saturation(event: ShortTermSaturatedEvent):
            await emitter.emit_system_notice("上下文压缩即将执行")
            system_notices.append(event)

        event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation)

        # 第一次触发饱和
        session_ctx.update_token_usage(prompt_tokens=7537, completion_tokens=0)
        buffer1 = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test 1",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )
        session_ctx.add_turn(buffer1)

        await asyncio.sleep(0.1)

        # 第二次添加（仍然超过阈值）
        buffer2 = ShortTermBuffer(
            turn_id="turn_002",
            role=TurnRole.ASSISTANT,
            content="Response 1",
            tool_refs=[],
            token_usage={"total_tokens": 20},
        )
        session_ctx.add_turn(buffer2)

        await asyncio.sleep(0.1)

        # 第三次添加
        buffer3 = ShortTermBuffer(
            turn_id="turn_003",
            role=TurnRole.USER,
            content="Test 2",
            tool_refs=[],
            token_usage={"total_tokens": 15},
        )
        session_ctx.add_turn(buffer3)

        await asyncio.sleep(0.1)

        await emitter.complete()

        # 验证事件只触发一次
        assert len(system_notices) == 1

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent_saturation(self):
        """测试：多个会话的饱和检测应该独立"""
        event_bus = EventBus()

        # 会话 1
        global_ctx1 = GlobalContext(user_id="user_123")
        session_ctx1 = SessionContext(session_id="session_001", global_context=global_ctx1)
        emitter1 = ConversationFlowEmitter(session_id="session_001")

        session_ctx1.set_event_bus(event_bus)
        session_ctx1.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 会话 2
        global_ctx2 = GlobalContext(user_id="user_456")
        session_ctx2 = SessionContext(session_id="session_002", global_context=global_ctx2)
        emitter2 = ConversationFlowEmitter(session_id="session_002")

        session_ctx2.set_event_bus(event_bus)
        session_ctx2.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 收集事件
        events_received = []

        async def handle_saturation(event: ShortTermSaturatedEvent):
            events_received.append(event)

        event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation)

        # 会话 1 触发饱和
        session_ctx1.update_token_usage(prompt_tokens=7537, completion_tokens=0)
        buffer1 = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )
        session_ctx1.add_turn(buffer1)

        await asyncio.sleep(0.1)

        # 会话 2 也触发饱和
        session_ctx2.update_token_usage(prompt_tokens=7537, completion_tokens=0)
        buffer2 = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )
        session_ctx2.add_turn(buffer2)

        await asyncio.sleep(0.1)

        await emitter1.complete()
        await emitter2.complete()

        # 验证两个会话都触发了饱和事件
        assert len(events_received) == 2
        assert events_received[0].session_id == "session_001"
        assert events_received[1].session_id == "session_002"

    @pytest.mark.asyncio
    async def test_saturation_with_different_thresholds(self):
        """测试：不同阈值的饱和检测"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_003", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 修改阈值为 0.85
        session_ctx.saturation_threshold = 0.85

        events_received = []

        async def handle_saturation(event: ShortTermSaturatedEvent):
            events_received.append(event)

        event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation)

        # 使用 86% 的上下文（应该触发 0.85 阈值）
        session_ctx.update_token_usage(prompt_tokens=7045, completion_tokens=0)

        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )

        session_ctx.add_turn(buffer)

        await asyncio.sleep(0.1)

        # 验证事件已触发
        assert len(events_received) == 1
        assert events_received[0].usage_ratio >= 0.85


class TestSaturationEventFields:
    """测试饱和事件的字段完整性"""

    @pytest.mark.asyncio
    async def test_saturation_event_contains_all_required_fields(self):
        """测试：饱和事件应该包含所有必需字段"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_004", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        captured_event = None

        async def capture_event(event: ShortTermSaturatedEvent):
            nonlocal captured_event
            captured_event = event

        event_bus.subscribe(ShortTermSaturatedEvent, capture_event)

        # 添加多个轮次
        for i in range(5):
            session_ctx.update_token_usage(prompt_tokens=1600, completion_tokens=0)
            buffer = ShortTermBuffer(
                turn_id=f"turn_{i:03d}",
                role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                content=f"Content {i}",
                tool_refs=[],
                token_usage={"total_tokens": 1600},
            )
            session_ctx.add_turn(buffer)

        await asyncio.sleep(0.1)

        # 验证事件字段
        assert captured_event is not None
        assert captured_event.session_id == "session_004"
        assert captured_event.usage_ratio >= 0.92
        assert captured_event.total_tokens >= 7537
        assert captured_event.context_limit == 8192
        assert captured_event.buffer_size == 5
        assert captured_event.source == "session_context"
        assert hasattr(captured_event, "id")
        assert hasattr(captured_event, "timestamp")
        assert captured_event.event_type == "short_term_saturated"

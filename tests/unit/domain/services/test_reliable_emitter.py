"""可靠发射器测试 - Phase 5

测试内容：
1. 有界队列与溢出策略
2. 背压机制
3. 消息持久化
4. 重试机制
5. 负载测试
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from src.domain.services.conversation_flow_emitter import (
    ConversationStep,
    StepKind,
)

# =============================================================================
# 第一部分：溢出策略枚举测试
# =============================================================================


class TestBufferOverflowPolicy:
    """测试缓冲区溢出策略枚举"""

    def test_policy_enum_exists(self):
        """测试：BufferOverflowPolicy 枚举存在"""
        from src.domain.services.reliable_emitter import BufferOverflowPolicy

        assert BufferOverflowPolicy is not None

    def test_policy_has_block(self):
        """测试：策略包含 BLOCK"""
        from src.domain.services.reliable_emitter import BufferOverflowPolicy

        assert hasattr(BufferOverflowPolicy, "BLOCK")
        assert BufferOverflowPolicy.BLOCK.value == "block"

    def test_policy_has_drop_oldest(self):
        """测试：策略包含 DROP_OLDEST"""
        from src.domain.services.reliable_emitter import BufferOverflowPolicy

        assert hasattr(BufferOverflowPolicy, "DROP_OLDEST")
        assert BufferOverflowPolicy.DROP_OLDEST.value == "drop_oldest"

    def test_policy_has_drop_newest(self):
        """测试：策略包含 DROP_NEWEST"""
        from src.domain.services.reliable_emitter import BufferOverflowPolicy

        assert hasattr(BufferOverflowPolicy, "DROP_NEWEST")
        assert BufferOverflowPolicy.DROP_NEWEST.value == "drop_newest"

    def test_policy_has_raise(self):
        """测试：策略包含 RAISE"""
        from src.domain.services.reliable_emitter import BufferOverflowPolicy

        assert hasattr(BufferOverflowPolicy, "RAISE")
        assert BufferOverflowPolicy.RAISE.value == "raise"


# =============================================================================
# 第二部分：ReliableEmitter 基础测试
# =============================================================================


class TestReliableEmitterBasics:
    """测试可靠发射器基础功能"""

    def test_reliable_emitter_class_exists(self):
        """测试：ReliableEmitter 类存在"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        assert ReliableEmitter is not None

    def test_reliable_emitter_can_be_instantiated(self):
        """测试：ReliableEmitter 可以实例化"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test_session")
        assert emitter is not None
        assert emitter.session_id == "test_session"

    def test_reliable_emitter_has_max_size(self):
        """测试：ReliableEmitter 有 max_size 属性"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test", max_size=100)
        assert emitter.max_size == 100

    def test_reliable_emitter_default_max_size(self):
        """测试：ReliableEmitter 默认 max_size 为 1000"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test")
        assert emitter.max_size == 1000

    def test_reliable_emitter_has_overflow_policy(self):
        """测试：ReliableEmitter 有 overflow_policy 属性"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )
        assert emitter.overflow_policy == BufferOverflowPolicy.DROP_OLDEST

    def test_reliable_emitter_default_policy_is_block(self):
        """测试：ReliableEmitter 默认策略为 BLOCK"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(session_id="test")
        assert emitter.overflow_policy == BufferOverflowPolicy.BLOCK


# =============================================================================
# 第三部分：有界队列测试
# =============================================================================


class TestBoundedQueue:
    """测试有界队列行为"""

    @pytest.mark.asyncio
    async def test_queue_respects_max_size(self):
        """测试：队列尊重 max_size 限制"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=5,
            overflow_policy=BufferOverflowPolicy.DROP_NEWEST,
        )

        # 发送 10 条消息
        for i in range(10):
            await emitter.emit_thinking(f"思考 {i}")

        # 队列大小不应超过 max_size
        assert emitter.queue_size <= 5

    @pytest.mark.asyncio
    async def test_queue_size_property(self):
        """测试：queue_size 属性正确"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test", max_size=100)

        await emitter.emit_thinking("消息 1")
        await emitter.emit_thinking("消息 2")

        assert emitter.queue_size == 2


# =============================================================================
# 第四部分：溢出策略行为测试
# =============================================================================


class TestOverflowPolicyBehavior:
    """测试溢出策略的具体行为"""

    @pytest.mark.asyncio
    async def test_drop_oldest_policy(self):
        """测试：DROP_OLDEST 策略丢弃最旧的消息"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=3,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        # 发送 5 条消息
        for i in range(5):
            await emitter.emit_thinking(f"消息 {i}")

        # 收集所有消息
        messages = []
        while emitter.queue_size > 0:
            step = await emitter.get_nowait()
            if step:
                messages.append(step.content)

        # 应该只有最新的 3 条消息
        assert len(messages) == 3
        assert "消息 2" in messages
        assert "消息 3" in messages
        assert "消息 4" in messages
        assert "消息 0" not in messages
        assert "消息 1" not in messages

    @pytest.mark.asyncio
    async def test_drop_newest_policy(self):
        """测试：DROP_NEWEST 策略丢弃新消息"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=3,
            overflow_policy=BufferOverflowPolicy.DROP_NEWEST,
        )

        # 发送 5 条消息
        for i in range(5):
            await emitter.emit_thinking(f"消息 {i}")

        # 收集所有消息
        messages = []
        while emitter.queue_size > 0:
            step = await emitter.get_nowait()
            if step:
                messages.append(step.content)

        # 应该只有最早的 3 条消息
        assert len(messages) == 3
        assert "消息 0" in messages
        assert "消息 1" in messages
        assert "消息 2" in messages

    @pytest.mark.asyncio
    async def test_raise_policy(self):
        """测试：RAISE 策略在队列满时抛出异常"""
        from src.domain.services.reliable_emitter import (
            BufferFullError,
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=3,
            overflow_policy=BufferOverflowPolicy.RAISE,
        )

        # 发送 3 条消息填满队列
        for i in range(3):
            await emitter.emit_thinking(f"消息 {i}")

        # 第 4 条应该抛出异常
        with pytest.raises(BufferFullError):
            await emitter.emit_thinking("溢出消息")

    @pytest.mark.asyncio
    async def test_block_policy_waits(self):
        """测试：BLOCK 策略在队列满时等待"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=2,
            overflow_policy=BufferOverflowPolicy.BLOCK,
        )

        # 填满队列
        await emitter.emit_thinking("消息 1")
        await emitter.emit_thinking("消息 2")

        # 启动消费者
        consumed = []

        async def consumer():
            await asyncio.sleep(0.1)  # 短暂延迟
            step = await emitter.get_nowait()
            if step:
                consumed.append(step.content)

        async def producer():
            await emitter.emit_thinking("消息 3", timeout=1.0)

        # 并发执行
        await asyncio.gather(consumer(), producer())

        # 验证消息 3 成功发送（因为消费者腾出了空间）
        assert emitter.queue_size == 2


# =============================================================================
# 第五部分：dropped_count 统计测试
# =============================================================================


class TestDroppedCountStatistics:
    """测试丢弃消息的统计"""

    @pytest.mark.asyncio
    async def test_dropped_count_for_drop_oldest(self):
        """测试：DROP_OLDEST 策略正确统计丢弃数量"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=3,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        for i in range(5):
            await emitter.emit_thinking(f"消息 {i}")

        # 应该丢弃了 2 条消息
        assert emitter.dropped_count == 2

    @pytest.mark.asyncio
    async def test_dropped_count_for_drop_newest(self):
        """测试：DROP_NEWEST 策略正确统计丢弃数量"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=3,
            overflow_policy=BufferOverflowPolicy.DROP_NEWEST,
        )

        for i in range(5):
            await emitter.emit_thinking(f"消息 {i}")

        # 应该丢弃了 2 条消息
        assert emitter.dropped_count == 2

    @pytest.mark.asyncio
    async def test_statistics_include_dropped_count(self):
        """测试：统计信息包含 dropped_count"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="test",
            max_size=3,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        for i in range(5):
            await emitter.emit_thinking(f"消息 {i}")

        stats = emitter.get_statistics()
        assert "dropped_count" in stats
        assert stats["dropped_count"] == 2


# =============================================================================
# 第六部分：消息持久化测试
# =============================================================================


class TestMessagePersistence:
    """测试消息持久化功能"""

    def test_message_store_interface_exists(self):
        """测试：MessageStore 接口存在"""
        from src.domain.services.reliable_emitter import MessageStore

        assert MessageStore is not None

    def test_in_memory_store_exists(self):
        """测试：InMemoryMessageStore 实现存在"""
        from src.domain.services.reliable_emitter import InMemoryMessageStore

        store = InMemoryMessageStore()
        assert store is not None

    @pytest.mark.asyncio
    async def test_store_save_and_retrieve(self):
        """测试：存储和检索消息"""
        from src.domain.services.reliable_emitter import InMemoryMessageStore

        store = InMemoryMessageStore()

        step = ConversationStep(
            kind=StepKind.THINKING,
            content="测试思考",
        )

        await store.save("session_1", step)

        messages = await store.get_by_session_id("session_1")
        assert len(messages) == 1
        assert messages[0].content == "测试思考"

    @pytest.mark.asyncio
    async def test_store_filter_by_kind(self):
        """测试：按类型筛选消息"""
        from src.domain.services.reliable_emitter import InMemoryMessageStore

        store = InMemoryMessageStore()

        await store.save(
            "session_1",
            ConversationStep(kind=StepKind.THINKING, content="思考"),
        )
        await store.save(
            "session_1",
            ConversationStep(kind=StepKind.TOOL_CALL, content="工具调用"),
        )
        await store.save(
            "session_1",
            ConversationStep(kind=StepKind.FINAL, content="最终响应"),
        )

        thinking_msgs = await store.get_by_kind("session_1", StepKind.THINKING)
        assert len(thinking_msgs) == 1
        assert thinking_msgs[0].content == "思考"

    @pytest.mark.asyncio
    async def test_store_filter_by_time_range(self):
        """测试：按时间范围筛选消息"""
        from src.domain.services.reliable_emitter import InMemoryMessageStore

        store = InMemoryMessageStore()

        now = datetime.now()
        old_time = now - timedelta(hours=2)
        recent_time = now - timedelta(minutes=30)

        step1 = ConversationStep(kind=StepKind.THINKING, content="旧消息")
        step1.timestamp = old_time

        step2 = ConversationStep(kind=StepKind.THINKING, content="新消息")
        step2.timestamp = recent_time

        await store.save("session_1", step1)
        await store.save("session_1", step2)

        # 查询最近 1 小时的消息
        start = now - timedelta(hours=1)
        messages = await store.get_by_time_range("session_1", start, now)

        assert len(messages) == 1
        assert messages[0].content == "新消息"


# =============================================================================
# 第七部分：Emitter 与 Store 集成测试
# =============================================================================


class TestEmitterWithStore:
    """测试 Emitter 与 Store 的集成"""

    @pytest.mark.asyncio
    async def test_emitter_with_message_store(self):
        """测试：Emitter 配置 MessageStore 后自动保存消息"""
        from src.domain.services.reliable_emitter import (
            InMemoryMessageStore,
            ReliableEmitter,
        )

        store = InMemoryMessageStore()
        emitter = ReliableEmitter(
            session_id="test_session",
            message_store=store,
        )

        await emitter.emit_thinking("思考内容")
        await emitter.emit_tool_call("search", "tool_1", {"query": "test"})
        await emitter.emit_final_response("最终响应")

        # 验证消息已保存
        messages = await store.get_by_session_id("test_session")
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_emitter_without_store_works(self):
        """测试：Emitter 不配置 Store 时也能正常工作"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test")

        await emitter.emit_thinking("思考")
        assert emitter.queue_size == 1


# =============================================================================
# 第八部分：协调者查询接口测试
# =============================================================================


class TestCoordinatorQuery:
    """测试协调者查询历史消息的能力"""

    @pytest.mark.asyncio
    async def test_get_session_summary(self):
        """测试：获取会话摘要"""
        from src.domain.services.reliable_emitter import (
            InMemoryMessageStore,
        )

        store = InMemoryMessageStore()

        # 模拟一个完整会话
        await store.save(
            "session_1",
            ConversationStep(kind=StepKind.THINKING, content="分析问题"),
        )
        await store.save(
            "session_1",
            ConversationStep(kind=StepKind.TOOL_CALL, content="", metadata={"tool_name": "search"}),
        )
        await store.save(
            "session_1",
            ConversationStep(kind=StepKind.TOOL_RESULT, content="", metadata={"result": "found"}),
        )
        await store.save(
            "session_1",
            ConversationStep(kind=StepKind.FINAL, content="任务完成"),
        )

        summary = await store.get_session_summary("session_1")

        assert summary is not None
        assert summary["total_messages"] == 4
        assert summary["thinking_count"] >= 1
        assert summary["tool_calls_count"] == 1
        assert summary["has_final_response"] is True

    @pytest.mark.asyncio
    async def test_list_all_sessions(self):
        """测试：列出所有会话"""
        from src.domain.services.reliable_emitter import InMemoryMessageStore

        store = InMemoryMessageStore()

        await store.save("session_1", ConversationStep(kind=StepKind.THINKING, content="1"))
        await store.save("session_2", ConversationStep(kind=StepKind.THINKING, content="2"))
        await store.save("session_3", ConversationStep(kind=StepKind.THINKING, content="3"))

        sessions = await store.list_sessions()
        assert len(sessions) == 3
        assert "session_1" in sessions
        assert "session_2" in sessions
        assert "session_3" in sessions


# =============================================================================
# 第九部分：负载测试
# =============================================================================


class TestLoadHandling:
    """测试高负载下的行为"""

    @pytest.mark.asyncio
    async def test_high_throughput_emit(self):
        """测试：高吞吐量发送"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="load_test",
            max_size=100,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        # 快速发送 1000 条消息
        start_time = asyncio.get_event_loop().time()

        for i in range(1000):
            await emitter.emit_delta(f"chunk_{i}")

        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time

        # 应该在合理时间内完成（< 1 秒）
        assert elapsed < 1.0

        # 统计信息应该正确
        stats = emitter.get_statistics()
        assert stats["total_steps"] == 1000
        assert stats["dropped_count"] == 900  # 1000 - 100 = 900 丢弃

    @pytest.mark.asyncio
    async def test_concurrent_producers(self):
        """测试：多个并发生产者"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="concurrent_test",
            max_size=500,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        async def producer(prefix: str, count: int):
            for i in range(count):
                await emitter.emit_thinking(f"{prefix}_{i}")

        # 5 个并发生产者，各发送 100 条
        await asyncio.gather(
            producer("A", 100),
            producer("B", 100),
            producer("C", 100),
            producer("D", 100),
            producer("E", 100),
        )

        # 总共 500 条，队列大小 500，不应丢弃
        stats = emitter.get_statistics()
        assert stats["total_steps"] == 500

    @pytest.mark.asyncio
    async def test_producer_consumer_balance(self):
        """测试：生产者-消费者平衡"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="balance_test",
            max_size=50,
            overflow_policy=BufferOverflowPolicy.BLOCK,
        )

        consumed = []
        producer_done = asyncio.Event()

        async def producer():
            for i in range(100):
                await emitter.emit_thinking(f"msg_{i}", timeout=5.0)
            producer_done.set()

        async def consumer():
            while not producer_done.is_set() or emitter.queue_size > 0:
                step = await emitter.get_with_timeout(timeout=0.5)
                if step:
                    consumed.append(step)
                else:
                    await asyncio.sleep(0.01)

        await asyncio.gather(producer(), consumer())

        # 所有消息都应该被消费
        assert len(consumed) == 100


# =============================================================================
# 第十部分：重试机制测试
# =============================================================================


class TestRetryMechanism:
    """测试重试机制"""

    @pytest.mark.asyncio
    async def test_emit_with_retry_on_timeout(self):
        """测试：发送超时时自动重试"""
        from src.domain.services.reliable_emitter import (
            BufferOverflowPolicy,
            ReliableEmitter,
        )

        emitter = ReliableEmitter(
            session_id="retry_test",
            max_size=1,
            overflow_policy=BufferOverflowPolicy.BLOCK,
            max_retries=3,
        )

        # 填满队列
        await emitter.emit_thinking("blocking")

        # 启动消费者延迟消费
        async def delayed_consumer():
            await asyncio.sleep(0.2)
            await emitter.get_nowait()

        async def producer_with_retry():
            await emitter.emit_thinking("retry_msg", timeout=0.5)

        # 并发执行
        await asyncio.gather(delayed_consumer(), producer_with_retry())

        # 验证 retry_msg 成功发送
        step = await emitter.get_nowait()
        assert step is not None
        assert step.content == "retry_msg"

    @pytest.mark.asyncio
    async def test_retry_count_in_statistics(self):
        """测试：统计信息包含重试次数"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(
            session_id="test",
            max_retries=3,
        )

        await emitter.emit_thinking("test")

        stats = emitter.get_statistics()
        assert "retry_count" in stats


# =============================================================================
# 第十一部分：向后兼容性测试
# =============================================================================


class TestBackwardCompatibility:
    """测试与原有 ConversationFlowEmitter 的兼容性"""

    @pytest.mark.asyncio
    async def test_reliable_emitter_is_async_iterable(self):
        """测试：ReliableEmitter 是异步可迭代的"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test")

        await emitter.emit_thinking("思考")
        await emitter.complete()

        messages = []
        async for step in emitter:
            messages.append(step)
            if step.kind == StepKind.END:
                break

        assert len(messages) == 2  # thinking + end

    @pytest.mark.asyncio
    async def test_reliable_emitter_complete_method(self):
        """测试：ReliableEmitter 有 complete 方法"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test")

        await emitter.emit_thinking("test")
        await emitter.complete()

        assert emitter.is_completed is True

    @pytest.mark.asyncio
    async def test_reliable_emitter_has_all_emit_methods(self):
        """测试：ReliableEmitter 有所有 emit 方法"""
        from src.domain.services.reliable_emitter import ReliableEmitter

        emitter = ReliableEmitter(session_id="test")

        # 验证所有方法存在
        assert hasattr(emitter, "emit_thinking")
        assert hasattr(emitter, "emit_reasoning")
        assert hasattr(emitter, "emit_delta")
        assert hasattr(emitter, "emit_tool_call")
        assert hasattr(emitter, "emit_tool_result")
        assert hasattr(emitter, "emit_final_response")
        assert hasattr(emitter, "emit_error")
        assert hasattr(emitter, "complete")

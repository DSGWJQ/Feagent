"""可靠发射器负载测试 - Phase 5

测试目标：
1. 验证高 QPS 下的稳定性
2. 验证背压机制在高负载下正常工作
3. 验证消息持久化在高并发下的正确性
4. 验证协调者查询接口的性能
"""

import asyncio
import time
from datetime import datetime, timedelta

import pytest

from src.domain.services.conversation_flow_emitter import StepKind
from src.domain.services.reliable_emitter import (
    BufferOverflowPolicy,
    InMemoryMessageStore,
    ReliableEmitter,
)

# =============================================================================
# 负载测试配置
# =============================================================================

# QPS 目标（每秒查询数）
TARGET_QPS = 1000

# 测试持续时间（秒）
TEST_DURATION = 2.0

# 最大允许延迟（秒）
MAX_LATENCY = 0.1


# =============================================================================
# 第一部分：高吞吐量测试
# =============================================================================


class TestHighThroughput:
    """高吞吐量测试"""

    @pytest.mark.asyncio
    async def test_emit_1000_messages_per_second(self):
        """测试：每秒发送 1000 条消息"""
        emitter = ReliableEmitter(
            session_id="throughput_test",
            max_size=2000,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        message_count = TARGET_QPS
        start_time = time.perf_counter()

        for i in range(message_count):
            await emitter.emit_delta(f"msg_{i}")

        end_time = time.perf_counter()
        elapsed = end_time - start_time

        # 计算实际 QPS
        actual_qps = message_count / elapsed

        print("\n吞吐量测试结果:")
        print(f"  - 消息数量: {message_count}")
        print(f"  - 耗时: {elapsed:.3f}s")
        print(f"  - 实际 QPS: {actual_qps:.0f}")

        # 应该在合理时间内完成（允许一定误差）
        assert elapsed < 2.0, f"发送 {message_count} 条消息耗时 {elapsed:.2f}s，超过预期"

        # 统计信息正确
        stats = emitter.get_statistics()
        assert stats["total_steps"] == message_count

    @pytest.mark.asyncio
    async def test_sustained_high_load(self):
        """测试：持续高负载"""
        emitter = ReliableEmitter(
            session_id="sustained_load",
            max_size=500,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        # 持续发送消息
        total_sent = 0
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < TEST_DURATION:
            await emitter.emit_delta(f"sustained_{total_sent}")
            total_sent += 1

        elapsed = time.perf_counter() - start_time
        qps = total_sent / elapsed

        print("\n持续负载测试结果:")
        print(f"  - 持续时间: {elapsed:.3f}s")
        print(f"  - 总消息数: {total_sent}")
        print(f"  - 平均 QPS: {qps:.0f}")

        # 应该能保持合理的 QPS
        assert qps > 500, f"QPS {qps:.0f} 低于预期"


# =============================================================================
# 第二部分：并发测试
# =============================================================================


class TestConcurrentLoad:
    """并发负载测试"""

    @pytest.mark.asyncio
    async def test_10_concurrent_producers(self):
        """测试：10 个并发生产者"""
        emitter = ReliableEmitter(
            session_id="concurrent_10",
            max_size=1000,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        messages_per_producer = 100

        async def producer(producer_id: int):
            for i in range(messages_per_producer):
                await emitter.emit_thinking(f"P{producer_id}_M{i}")

        start_time = time.perf_counter()

        # 启动 10 个并发生产者
        await asyncio.gather(*[producer(i) for i in range(10)])

        elapsed = time.perf_counter() - start_time
        total_messages = 10 * messages_per_producer

        print("\n10 并发生产者测试:")
        print(f"  - 总消息数: {total_messages}")
        print(f"  - 耗时: {elapsed:.3f}s")
        print(f"  - QPS: {total_messages / elapsed:.0f}")

        stats = emitter.get_statistics()
        assert stats["total_steps"] == total_messages

    @pytest.mark.asyncio
    async def test_producer_consumer_high_load(self):
        """测试：生产者-消费者高负载平衡"""
        emitter = ReliableEmitter(
            session_id="prod_cons_load",
            max_size=100,
            overflow_policy=BufferOverflowPolicy.BLOCK,
        )

        produced = 0
        consumed = 0
        target_messages = 500
        producer_done = asyncio.Event()

        async def producer():
            nonlocal produced
            for i in range(target_messages):
                await emitter.emit_delta(f"msg_{i}", timeout=5.0)
                produced += 1
            producer_done.set()

        async def consumer():
            nonlocal consumed
            while not producer_done.is_set() or emitter.queue_size > 0:
                step = await emitter.get_with_timeout(timeout=0.1)
                if step:
                    consumed += 1
                await asyncio.sleep(0.001)  # 模拟消费延迟

        start_time = time.perf_counter()
        await asyncio.gather(producer(), consumer())
        elapsed = time.perf_counter() - start_time

        print("\n生产者-消费者平衡测试:")
        print(f"  - 生产: {produced}")
        print(f"  - 消费: {consumed}")
        print(f"  - 耗时: {elapsed:.3f}s")
        print(f"  - 丢弃: {emitter.dropped_count}")

        # 所有消息都应该被处理
        assert produced == target_messages
        assert consumed >= target_messages * 0.9  # 允许少量未消费


# =============================================================================
# 第三部分：背压测试
# =============================================================================


class TestBackpressure:
    """背压机制测试"""

    @pytest.mark.asyncio
    async def test_backpressure_with_slow_consumer(self):
        """测试：慢消费者场景的背压"""
        emitter = ReliableEmitter(
            session_id="backpressure_test",
            max_size=50,
            overflow_policy=BufferOverflowPolicy.BLOCK,
        )

        producer_blocked_count = 0
        consumed_count = 0

        async def slow_consumer():
            nonlocal consumed_count
            for _ in range(100):
                step = await emitter.get_with_timeout(timeout=1.0)
                if step:
                    consumed_count += 1
                    await asyncio.sleep(0.02)  # 慢消费

        async def fast_producer():
            nonlocal producer_blocked_count
            for i in range(100):
                try:
                    await emitter.emit_thinking(f"msg_{i}", timeout=2.0)
                except TimeoutError:
                    producer_blocked_count += 1

        await asyncio.gather(fast_producer(), slow_consumer())

        print("\n背压测试:")
        print(f"  - 消费数量: {consumed_count}")
        print(f"  - 生产者阻塞次数: {producer_blocked_count}")
        print(f"  - 队列当前大小: {emitter.queue_size}")

        # 消费者应该能处理大部分消息
        assert consumed_count >= 90

    @pytest.mark.asyncio
    async def test_drop_oldest_under_pressure(self):
        """测试：高压下 DROP_OLDEST 策略"""
        emitter = ReliableEmitter(
            session_id="drop_oldest_test",
            max_size=100,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        )

        # 快速发送大量消息
        for i in range(1000):
            await emitter.emit_delta(f"msg_{i}")

        stats = emitter.get_statistics()

        print("\nDROP_OLDEST 压力测试:")
        print("  - 发送总数: 1000")
        print(f"  - 队列大小: {emitter.queue_size}")
        print(f"  - 丢弃数量: {stats['dropped_count']}")

        # 队列不应超过最大大小
        assert emitter.queue_size <= 100

        # 应该丢弃了 900 条消息
        assert stats["dropped_count"] == 900


# =============================================================================
# 第四部分：消息持久化性能测试
# =============================================================================


class TestPersistencePerformance:
    """消息持久化性能测试"""

    @pytest.mark.asyncio
    async def test_persistence_under_high_load(self):
        """测试：高负载下的持久化性能"""
        store = InMemoryMessageStore()
        emitter = ReliableEmitter(
            session_id="persistence_load",
            max_size=2000,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
            message_store=store,
        )

        message_count = 1000
        start_time = time.perf_counter()

        for i in range(message_count):
            await emitter.emit_thinking(f"persistent_msg_{i}")

        elapsed = time.perf_counter() - start_time

        # 验证所有消息都被持久化
        messages = await store.get_by_session_id("persistence_load")

        print("\n持久化性能测试:")
        print(f"  - 消息数量: {message_count}")
        print(f"  - 耗时: {elapsed:.3f}s")
        print(f"  - 持久化数量: {len(messages)}")

        assert len(messages) == message_count
        assert elapsed < 2.0  # 应在合理时间内完成

    @pytest.mark.asyncio
    async def test_query_performance(self):
        """测试：查询性能"""
        store = InMemoryMessageStore()

        # 预先存入大量消息
        emitter = ReliableEmitter(
            session_id="query_perf",
            message_store=store,
        )

        for i in range(1000):
            if i % 3 == 0:
                await emitter.emit_thinking(f"thinking_{i}")
            elif i % 3 == 1:
                await emitter.emit_tool_call("tool", f"t_{i}", {"arg": i})
            else:
                await emitter.emit_delta(f"delta_{i}")

        # 测试查询性能
        start_time = time.perf_counter()

        all_messages = await store.get_by_session_id("query_perf")
        thinking_messages = await store.get_by_kind("query_perf", StepKind.THINKING)
        summary = await store.get_session_summary("query_perf")

        query_time = time.perf_counter() - start_time

        print("\n查询性能测试:")
        print(f"  - 总消息数: {len(all_messages)}")
        print(f"  - 思考消息数: {len(thinking_messages)}")
        print(f"  - 查询耗时: {query_time * 1000:.2f}ms")
        print(f"  - 摘要: {summary}")

        assert query_time < 0.1  # 查询应在 100ms 内完成
        assert len(all_messages) == 1000


# =============================================================================
# 第五部分：协调者查询集成测试
# =============================================================================


class TestCoordinatorQueryIntegration:
    """协调者查询接口集成测试"""

    @pytest.mark.asyncio
    async def test_multiple_sessions_query(self):
        """测试：多会话查询"""
        store = InMemoryMessageStore()

        # 创建多个会话
        for session_num in range(5):
            emitter = ReliableEmitter(
                session_id=f"session_{session_num}",
                message_store=store,
            )
            for i in range(100):
                await emitter.emit_thinking(f"S{session_num}_M{i}")

        # 查询所有会话
        sessions = await store.list_sessions()
        assert len(sessions) == 5

        # 查询每个会话的摘要
        for session_id in sessions:
            summary = await store.get_session_summary(session_id)
            assert summary["total_messages"] == 100
            assert summary["thinking_count"] == 100

    @pytest.mark.asyncio
    async def test_time_range_query_accuracy(self):
        """测试：时间范围查询准确性"""
        store = InMemoryMessageStore()
        emitter = ReliableEmitter(
            session_id="time_range_test",
            message_store=store,
        )

        now = datetime.now()

        # 发送一些消息
        for i in range(10):
            await emitter.emit_thinking(f"msg_{i}")

        # 查询最近时间范围
        recent = await store.get_by_time_range(
            "time_range_test",
            now - timedelta(minutes=1),
            now + timedelta(minutes=1),
        )

        assert len(recent) == 10

    @pytest.mark.asyncio
    async def test_summary_for_complete_workflow(self):
        """测试：完整工作流的摘要查询"""
        store = InMemoryMessageStore()
        emitter = ReliableEmitter(
            session_id="complete_workflow",
            message_store=store,
        )

        # 模拟完整工作流
        await emitter.emit_thinking("分析用户请求...")
        await emitter.emit_reasoning("决定调用搜索工具")
        await emitter.emit_tool_call("search", "t1", {"query": "test"})
        await emitter.emit_tool_result("t1", {"results": ["a", "b"]})
        await emitter.emit_thinking("整理搜索结果...")
        await emitter.emit_final_response("这是最终响应")
        await emitter.complete()

        summary = await store.get_session_summary("complete_workflow")

        assert summary["total_messages"] == 7  # 6 + END
        assert summary["thinking_count"] == 3  # 2 thinking + 1 reasoning
        assert summary["tool_calls_count"] == 1
        assert summary["has_final_response"] is True


# =============================================================================
# 第六部分：稳定性测试
# =============================================================================


class TestStability:
    """稳定性测试"""

    @pytest.mark.asyncio
    async def test_no_memory_leak_under_load(self):
        """测试：高负载下无内存泄漏"""
        import gc

        store = InMemoryMessageStore(max_messages_per_session=100)
        emitter = ReliableEmitter(
            session_id="memory_test",
            max_size=100,
            overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
            message_store=store,
        )

        # 发送大量消息
        for i in range(10000):
            await emitter.emit_delta(f"msg_{i}")

        # 强制垃圾回收
        gc.collect()

        # 队列大小应该受限
        assert emitter.queue_size <= 100

        # 存储应该受限
        messages = await store.get_by_session_id("memory_test")
        assert len(messages) <= 100

    @pytest.mark.asyncio
    async def test_graceful_handling_of_rapid_complete(self):
        """测试：快速 complete 的优雅处理"""
        emitter = ReliableEmitter(
            session_id="rapid_complete",
            max_size=10,
        )

        # 快速发送和完成
        for i in range(5):
            await emitter.emit_thinking(f"msg_{i}")

        await emitter.complete()

        # 再次 complete 应该是幂等的
        await emitter.complete()

        assert emitter.is_completed is True

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """测试：错误恢复"""
        emitter = ReliableEmitter(
            session_id="error_recovery",
            max_size=5,
            overflow_policy=BufferOverflowPolicy.RAISE,
        )

        # 填满队列
        for i in range(5):
            await emitter.emit_thinking(f"msg_{i}")

        # 应该抛出异常
        from src.domain.services.reliable_emitter import BufferFullError

        with pytest.raises(BufferFullError):
            await emitter.emit_thinking("overflow")

        # 消费一些消息后应该能继续
        await emitter.get_nowait()
        await emitter.get_nowait()

        # 现在应该可以发送了
        await emitter.emit_thinking("recovered")

        assert emitter.queue_size == 4

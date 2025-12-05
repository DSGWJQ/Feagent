"""ToolConcurrencyController 测试 - 阶段 5

测试目标：
1. 验证并发槽位管理（获取/释放）
2. 验证排队策略（FIFO、优先级、拒绝）
3. 验证仅统计对话 Agent 调用
4. 验证负载均衡（按工具类型分桶）
5. 验证资源管理（执行时间记录、超时取消）
6. 验证监控指标
7. 压力测试验证并发限制
"""

import asyncio
import time

import pytest

# =============================================================================
# 第一部分：ConcurrencyConfig 配置测试
# =============================================================================


class TestConcurrencyConfig:
    """并发配置测试"""

    def test_create_default_config(self):
        """测试：创建默认配置"""
        from src.domain.services.tool_concurrency_controller import ConcurrencyConfig

        config = ConcurrencyConfig()

        assert config.max_concurrent == 10
        assert config.queue_size == 100
        assert config.default_timeout == 30.0
        assert config.strategy == "fifo"

    def test_create_custom_config(self):
        """测试：创建自定义配置"""
        from src.domain.services.tool_concurrency_controller import ConcurrencyConfig

        config = ConcurrencyConfig(
            max_concurrent=5,
            queue_size=50,
            default_timeout=60.0,
            strategy="priority",
        )

        assert config.max_concurrent == 5
        assert config.queue_size == 50
        assert config.default_timeout == 60.0
        assert config.strategy == "priority"

    def test_config_with_bucket_limits(self):
        """测试：带分桶限制的配置"""
        from src.domain.services.tool_concurrency_controller import ConcurrencyConfig

        config = ConcurrencyConfig(
            max_concurrent=10,
            bucket_limits={
                "http": 3,
                "ai": 2,
                "database": 5,
            },
        )

        assert config.bucket_limits["http"] == 3
        assert config.bucket_limits["ai"] == 2
        assert config.bucket_limits["database"] == 5

    def test_config_validation(self):
        """测试：配置验证"""
        from src.domain.services.tool_concurrency_controller import ConcurrencyConfig

        # 无效的最大并发数
        with pytest.raises(ValueError, match="max_concurrent"):
            ConcurrencyConfig(max_concurrent=0)

        # 无效的队列大小
        with pytest.raises(ValueError, match="queue_size"):
            ConcurrencyConfig(queue_size=-1)

        # 无效的策略
        with pytest.raises(ValueError, match="strategy"):
            ConcurrencyConfig(strategy="invalid")


# =============================================================================
# 第二部分：ExecutionSlot 槽位测试
# =============================================================================


class TestExecutionSlot:
    """执行槽位测试"""

    def test_create_slot(self):
        """测试：创建槽位"""
        from src.domain.services.tool_concurrency_controller import ExecutionSlot

        slot = ExecutionSlot(
            slot_id="slot_1",
            tool_name="http_request",
            caller_id="agent_123",
            caller_type="conversation_agent",
        )

        assert slot.slot_id == "slot_1"
        assert slot.tool_name == "http_request"
        assert slot.caller_id == "agent_123"
        assert slot.caller_type == "conversation_agent"
        assert slot.started_at is not None

    def test_slot_elapsed_time(self):
        """测试：槽位已用时间"""
        from src.domain.services.tool_concurrency_controller import ExecutionSlot

        slot = ExecutionSlot(
            slot_id="slot_1",
            tool_name="test_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        time.sleep(0.1)
        elapsed = slot.elapsed_time()

        assert elapsed >= 0.1

    def test_slot_is_timeout(self):
        """测试：槽位是否超时"""
        from src.domain.services.tool_concurrency_controller import ExecutionSlot

        slot = ExecutionSlot(
            slot_id="slot_1",
            tool_name="test_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
            timeout=0.05,  # 50ms 超时
        )

        assert slot.is_timeout() is False
        time.sleep(0.1)
        assert slot.is_timeout() is True

    def test_slot_to_dict(self):
        """测试：槽位转换为字典"""
        from src.domain.services.tool_concurrency_controller import ExecutionSlot

        slot = ExecutionSlot(
            slot_id="slot_1",
            tool_name="http_request",
            caller_id="agent_123",
            caller_type="conversation_agent",
            timeout=30.0,
        )

        data = slot.to_dict()

        assert data["slot_id"] == "slot_1"
        assert data["tool_name"] == "http_request"
        assert data["caller_id"] == "agent_123"
        assert "started_at" in data


# =============================================================================
# 第三部分：QueuedExecution 排队执行测试
# =============================================================================


class TestQueuedExecution:
    """排队执行测试"""

    def test_create_queued_execution(self):
        """测试：创建排队执行"""
        from src.domain.services.tool_concurrency_controller import QueuedExecution

        queued = QueuedExecution(
            queue_id="queue_1",
            tool_name="http_request",
            caller_id="agent_123",
            caller_type="conversation_agent",
            params={"url": "https://api.example.com"},
            priority=1,
        )

        assert queued.queue_id == "queue_1"
        assert queued.tool_name == "http_request"
        assert queued.priority == 1
        assert queued.enqueued_at is not None

    def test_queued_execution_wait_time(self):
        """测试：排队等待时间"""
        from src.domain.services.tool_concurrency_controller import QueuedExecution

        queued = QueuedExecution(
            queue_id="queue_1",
            tool_name="test_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
            params={},
        )

        time.sleep(0.1)
        wait_time = queued.wait_time()

        assert wait_time >= 0.1

    def test_queued_execution_comparison(self):
        """测试：排队执行比较（用于优先级队列）"""
        from src.domain.services.tool_concurrency_controller import QueuedExecution

        queued1 = QueuedExecution(
            queue_id="q1",
            tool_name="tool",
            caller_id="a1",
            caller_type="conversation_agent",
            params={},
            priority=1,  # 高优先级
        )

        queued2 = QueuedExecution(
            queue_id="q2",
            tool_name="tool",
            caller_id="a2",
            caller_type="conversation_agent",
            params={},
            priority=5,  # 低优先级
        )

        # 优先级数字越小越优先
        assert queued1 < queued2


# =============================================================================
# 第四部分：基础并发控制测试
# =============================================================================


class TestBasicConcurrencyControl:
    """基础并发控制测试"""

    @pytest.mark.asyncio
    async def test_acquire_slot_success(self):
        """测试：成功获取槽位"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2)
        controller = ToolConcurrencyController(config)

        slot = await controller.acquire_slot(
            tool_name="http_request",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        assert slot is not None
        assert slot.tool_name == "http_request"
        assert controller.current_concurrent == 1

    @pytest.mark.asyncio
    async def test_acquire_slot_at_limit(self):
        """测试：达到并发限制时获取槽位"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2, strategy="reject")
        controller = ToolConcurrencyController(config)

        # 获取两个槽位
        slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )
        slot2 = await controller.acquire_slot(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
        )

        assert slot1 is not None
        assert slot2 is not None

        # 第三个应该被拒绝
        slot3 = await controller.acquire_slot(
            tool_name="tool3",
            caller_id="agent_3",
            caller_type="conversation_agent",
        )

        assert slot3 is None
        assert controller.current_concurrent == 2

    @pytest.mark.asyncio
    async def test_release_slot(self):
        """测试：释放槽位"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2)
        controller = ToolConcurrencyController(config)

        slot = await controller.acquire_slot(
            tool_name="http_request",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        assert controller.current_concurrent == 1

        await controller.release_slot(slot.slot_id)

        assert controller.current_concurrent == 0

    @pytest.mark.asyncio
    async def test_release_nonexistent_slot(self):
        """测试：释放不存在的槽位"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2)
        controller = ToolConcurrencyController(config)

        # 不应抛出异常
        await controller.release_slot("nonexistent_slot")

    @pytest.mark.asyncio
    async def test_only_count_conversation_agent(self):
        """测试：仅统计对话 Agent 调用"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2, strategy="reject")
        controller = ToolConcurrencyController(config)

        # 对话 Agent 调用计入并发数
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="conv_agent_1",
            caller_type="conversation_agent",
        )
        _slot2 = await controller.acquire_slot(
            tool_name="tool2",
            caller_id="conv_agent_2",
            caller_type="conversation_agent",
        )

        # 达到限制，对话 Agent 被拒绝
        slot3 = await controller.acquire_slot(
            tool_name="tool3",
            caller_id="conv_agent_3",
            caller_type="conversation_agent",
        )
        assert slot3 is None

        # 但 Workflow 节点不计入并发数，应该成功
        slot4 = await controller.acquire_slot(
            tool_name="tool4",
            caller_id="workflow_node_1",
            caller_type="workflow_node",
        )
        assert slot4 is not None

        # 验证并发数只计对话 Agent
        assert controller.current_concurrent == 2


# =============================================================================
# 第五部分：排队策略测试
# =============================================================================


class TestQueueStrategies:
    """排队策略测试"""

    @pytest.mark.asyncio
    async def test_fifo_queue_strategy(self):
        """测试：FIFO 排队策略"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=1, queue_size=10, strategy="fifo")
        controller = ToolConcurrencyController(config)

        # 占用唯一槽位
        slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        # 后续请求应该排队
        queued1 = await controller.enqueue(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
            params={},
        )
        queued2 = await controller.enqueue(
            tool_name="tool3",
            caller_id="agent_3",
            caller_type="conversation_agent",
            params={},
        )

        assert queued1 is not None
        assert queued2 is not None
        assert controller.queue_length == 2

        # 释放槽位后，第一个排队的应该先出队
        await controller.release_slot(slot1.slot_id)

        next_item = await controller.dequeue()
        assert next_item.queue_id == queued1.queue_id

    @pytest.mark.asyncio
    async def test_priority_queue_strategy(self):
        """测试：优先级排队策略"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=1, queue_size=10, strategy="priority")
        controller = ToolConcurrencyController(config)

        # 占用槽位
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        # 入队不同优先级的请求（数字越小优先级越高）
        queued_low = await controller.enqueue(
            tool_name="tool_low",
            caller_id="agent_low",
            caller_type="conversation_agent",
            params={},
            priority=10,
        )
        queued_high = await controller.enqueue(
            tool_name="tool_high",
            caller_id="agent_high",
            caller_type="conversation_agent",
            params={},
            priority=1,
        )
        queued_medium = await controller.enqueue(
            tool_name="tool_medium",
            caller_id="agent_medium",
            caller_type="conversation_agent",
            params={},
            priority=5,
        )

        # 出队顺序应该按优先级
        next1 = await controller.dequeue()
        next2 = await controller.dequeue()
        next3 = await controller.dequeue()

        assert next1.queue_id == queued_high.queue_id
        assert next2.queue_id == queued_medium.queue_id
        assert next3.queue_id == queued_low.queue_id

    @pytest.mark.asyncio
    async def test_reject_strategy(self):
        """测试：拒绝策略"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=1, strategy="reject")
        controller = ToolConcurrencyController(config)

        # 占用槽位
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        # 后续请求应该被拒绝
        slot2 = await controller.acquire_slot(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
        )

        assert slot2 is None
        assert controller.metrics.total_rejected == 1

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self):
        """测试：队列满时拒绝"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=1, queue_size=2, strategy="fifo")
        controller = ToolConcurrencyController(config)

        # 占用槽位
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        # 填满队列
        _queued1 = await controller.enqueue(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
            params={},
        )
        _queued2 = await controller.enqueue(
            tool_name="tool3",
            caller_id="agent_3",
            caller_type="conversation_agent",
            params={},
        )

        # 队列满后应该被拒绝
        queued3 = await controller.enqueue(
            tool_name="tool4",
            caller_id="agent_4",
            caller_type="conversation_agent",
            params={},
        )

        assert queued3 is None
        assert controller.queue_length == 2


# =============================================================================
# 第六部分：负载均衡（分桶）测试
# =============================================================================


class TestLoadBalancing:
    """负载均衡测试"""

    @pytest.mark.asyncio
    async def test_bucket_based_limiting(self):
        """测试：基于分桶的限流"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(
            max_concurrent=10,  # 总并发限制
            bucket_limits={
                "http": 2,  # HTTP 工具最多 2 个并发
                "ai": 1,  # AI 工具最多 1 个并发
            },
            strategy="reject",
        )
        controller = ToolConcurrencyController(config)

        # HTTP 工具获取 2 个槽位
        http_slot1 = await controller.acquire_slot(
            tool_name="http_request",
            caller_id="agent_1",
            caller_type="conversation_agent",
            bucket="http",
        )
        http_slot2 = await controller.acquire_slot(
            tool_name="http_get",
            caller_id="agent_2",
            caller_type="conversation_agent",
            bucket="http",
        )

        # 第三个 HTTP 请求应该被拒绝
        http_slot3 = await controller.acquire_slot(
            tool_name="http_post",
            caller_id="agent_3",
            caller_type="conversation_agent",
            bucket="http",
        )

        assert http_slot1 is not None
        assert http_slot2 is not None
        assert http_slot3 is None

        # 但 AI 工具仍然可以获取（不同分桶）
        ai_slot1 = await controller.acquire_slot(
            tool_name="llm_call",
            caller_id="agent_4",
            caller_type="conversation_agent",
            bucket="ai",
        )

        assert ai_slot1 is not None

    @pytest.mark.asyncio
    async def test_bucket_queue_separation(self):
        """测试：分桶队列隔离"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(
            max_concurrent=10,
            bucket_limits={"http": 1, "ai": 1},
            queue_size=10,
            strategy="fifo",
        )
        controller = ToolConcurrencyController(config)

        # 占用 HTTP 槽位
        _http_slot1 = await controller.acquire_slot(
            tool_name="http_request",
            caller_id="agent_1",
            caller_type="conversation_agent",
            bucket="http",
        )

        # HTTP 请求排队
        http_queued = await controller.enqueue(
            tool_name="http_get",
            caller_id="agent_2",
            caller_type="conversation_agent",
            params={},
            bucket="http",
        )

        # AI 请求应该直接成功（不同分桶）
        ai_slot = await controller.acquire_slot(
            tool_name="llm_call",
            caller_id="agent_3",
            caller_type="conversation_agent",
            bucket="ai",
        )

        assert http_queued is not None
        assert ai_slot is not None

    @pytest.mark.asyncio
    async def test_default_bucket(self):
        """测试：未指定分桶时使用默认分桶"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(
            max_concurrent=2,
            bucket_limits={"http": 1},
            strategy="reject",
        )
        controller = ToolConcurrencyController(config)

        # 未指定分桶的工具使用总并发限制
        slot1 = await controller.acquire_slot(
            tool_name="custom_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )
        slot2 = await controller.acquire_slot(
            tool_name="another_tool",
            caller_id="agent_2",
            caller_type="conversation_agent",
        )

        assert slot1 is not None
        assert slot2 is not None

        # 达到总并发限制
        slot3 = await controller.acquire_slot(
            tool_name="third_tool",
            caller_id="agent_3",
            caller_type="conversation_agent",
        )

        assert slot3 is None


# =============================================================================
# 第七部分：资源管理测试
# =============================================================================


class TestResourceManagement:
    """资源管理测试"""

    @pytest.mark.asyncio
    async def test_execution_time_recording(self):
        """测试：记录执行时间"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5)
        controller = ToolConcurrencyController(config)

        slot = await controller.acquire_slot(
            tool_name="test_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        await asyncio.sleep(0.1)

        execution_time = await controller.release_slot(slot.slot_id)

        assert execution_time >= 0.1
        assert controller.metrics.total_execution_time >= 0.1

    @pytest.mark.asyncio
    async def test_timeout_detection(self):
        """测试：超时检测"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5, default_timeout=0.05)
        controller = ToolConcurrencyController(config)

        slot = await controller.acquire_slot(
            tool_name="slow_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        await asyncio.sleep(0.1)

        # 检测超时的槽位
        timeout_slots = controller.get_timeout_slots()

        assert len(timeout_slots) == 1
        assert timeout_slots[0].slot_id == slot.slot_id

    @pytest.mark.asyncio
    async def test_cancel_timeout_slots(self):
        """测试：取消超时槽位"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5, default_timeout=0.05)
        controller = ToolConcurrencyController(config)

        _slot = await controller.acquire_slot(
            tool_name="slow_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        await asyncio.sleep(0.1)

        # 取消超时槽位
        cancelled = await controller.cancel_timeout_slots()

        assert len(cancelled) == 1
        assert controller.current_concurrent == 0
        assert controller.metrics.total_timeout == 1

    @pytest.mark.asyncio
    async def test_custom_timeout_per_slot(self):
        """测试：每个槽位自定义超时"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5, default_timeout=10.0)
        controller = ToolConcurrencyController(config)

        # 使用自定义超时
        _slot = await controller.acquire_slot(
            tool_name="quick_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
            timeout=0.05,  # 50ms 超时
        )

        await asyncio.sleep(0.1)

        timeout_slots = controller.get_timeout_slots()
        assert len(timeout_slots) == 1


# =============================================================================
# 第八部分：监控指标测试
# =============================================================================


class TestMonitoringMetrics:
    """监控指标测试"""

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """测试：获取监控指标"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5)
        controller = ToolConcurrencyController(config)

        # 执行一些操作
        slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )
        _slot2 = await controller.acquire_slot(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
        )

        await controller.release_slot(slot1.slot_id)

        metrics = controller.get_metrics()

        assert metrics.current_concurrent == 1
        assert metrics.total_acquired == 2
        assert metrics.total_released == 1

    @pytest.mark.asyncio
    async def test_metrics_with_queue(self):
        """测试：带队列的指标"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=1, queue_size=10, strategy="fifo")
        controller = ToolConcurrencyController(config)

        # 占用槽位
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        # 入队
        _queued1 = await controller.enqueue(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
            params={},
        )
        _queued2 = await controller.enqueue(
            tool_name="tool3",
            caller_id="agent_3",
            caller_type="conversation_agent",
            params={},
        )

        metrics = controller.get_metrics()

        assert metrics.current_concurrent == 1
        assert metrics.queue_length == 2
        assert metrics.total_enqueued == 2

    @pytest.mark.asyncio
    async def test_metrics_with_rejection(self):
        """测试：带拒绝统计的指标"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=1, strategy="reject")
        controller = ToolConcurrencyController(config)

        # 占用槽位
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        # 被拒绝
        _slot2 = await controller.acquire_slot(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
        )
        _slot3 = await controller.acquire_slot(
            tool_name="tool3",
            caller_id="agent_3",
            caller_type="conversation_agent",
        )

        metrics = controller.get_metrics()

        assert metrics.total_rejected == 2

    @pytest.mark.asyncio
    async def test_metrics_average_calculations(self):
        """测试：平均值计算"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5)
        controller = ToolConcurrencyController(config)

        # 执行多次
        for i in range(3):
            slot = await controller.acquire_slot(
                tool_name=f"tool_{i}",
                caller_id=f"agent_{i}",
                caller_type="conversation_agent",
            )
            await asyncio.sleep(0.05)
            await controller.release_slot(slot.slot_id)

        metrics = controller.get_metrics()

        assert metrics.avg_execution_time >= 0.05
        assert metrics.total_released == 3

    @pytest.mark.asyncio
    async def test_metrics_to_dict(self):
        """测试：指标转换为字典"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5)
        controller = ToolConcurrencyController(config)

        _slot = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )

        metrics_dict = controller.get_metrics().to_dict()

        assert "current_concurrent" in metrics_dict
        assert "queue_length" in metrics_dict
        assert "total_acquired" in metrics_dict
        assert "total_rejected" in metrics_dict
        assert "avg_execution_time" in metrics_dict

    @pytest.mark.asyncio
    async def test_bucket_metrics(self):
        """测试：分桶指标"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(
            max_concurrent=10,
            bucket_limits={"http": 2, "ai": 1},
        )
        controller = ToolConcurrencyController(config)

        _http_slot = await controller.acquire_slot(
            tool_name="http_request",
            caller_id="agent_1",
            caller_type="conversation_agent",
            bucket="http",
        )
        _ai_slot = await controller.acquire_slot(
            tool_name="llm_call",
            caller_id="agent_2",
            caller_type="conversation_agent",
            bucket="ai",
        )

        bucket_metrics = controller.get_bucket_metrics()

        assert bucket_metrics["http"]["current"] == 1
        assert bucket_metrics["http"]["limit"] == 2
        assert bucket_metrics["ai"]["current"] == 1
        assert bucket_metrics["ai"]["limit"] == 1


# =============================================================================
# 第九部分：压力测试
# =============================================================================


class TestStressConcurrency:
    """压力测试"""

    @pytest.mark.asyncio
    async def test_concurrent_limit_enforcement(self):
        """测试：并发限制强制执行"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        max_concurrent = 5
        config = ConcurrencyConfig(max_concurrent=max_concurrent, strategy="reject")
        controller = ToolConcurrencyController(config)

        # 并发获取 20 个槽位
        tasks = []
        for i in range(20):
            task = controller.acquire_slot(
                tool_name=f"tool_{i}",
                caller_id=f"agent_{i}",
                caller_type="conversation_agent",
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # 成功获取的槽位数应该等于最大并发数
        successful = [r for r in results if r is not None]
        rejected = [r for r in results if r is None]

        assert len(successful) == max_concurrent
        assert len(rejected) == 15
        assert controller.current_concurrent == max_concurrent

    @pytest.mark.asyncio
    async def test_queue_ordering_under_load(self):
        """测试：高负载下队列顺序"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=1, queue_size=100, strategy="fifo")
        controller = ToolConcurrencyController(config)

        # 占用槽位
        _blocking_slot = await controller.acquire_slot(
            tool_name="blocking_tool",
            caller_id="agent_0",
            caller_type="conversation_agent",
        )

        # 快速入队 50 个请求
        queue_ids = []
        for i in range(50):
            queued = await controller.enqueue(
                tool_name=f"tool_{i}",
                caller_id=f"agent_{i + 1}",
                caller_type="conversation_agent",
                params={},
            )
            queue_ids.append(queued.queue_id)

        # 验证出队顺序
        for expected_id in queue_ids:
            item = await controller.dequeue()
            assert item.queue_id == expected_id

    @pytest.mark.asyncio
    async def test_concurrent_acquire_release(self):
        """测试：并发获取和释放"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=10)
        controller = ToolConcurrencyController(config)

        max_observed = 0

        async def worker(worker_id: int):
            nonlocal max_observed
            for _ in range(10):
                slot = await controller.acquire_slot(
                    tool_name=f"tool_{worker_id}",
                    caller_id=f"agent_{worker_id}",
                    caller_type="conversation_agent",
                )
                if slot:
                    current = controller.current_concurrent
                    max_observed = max(max_observed, current)
                    await asyncio.sleep(0.01)
                    await controller.release_slot(slot.slot_id)

        # 启动 20 个并发 worker
        workers = [worker(i) for i in range(20)]
        await asyncio.gather(*workers)

        # 验证并发数从未超过限制
        assert max_observed <= 10
        assert controller.current_concurrent == 0

    @pytest.mark.asyncio
    async def test_high_throughput(self):
        """测试：高吞吐量"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=50)
        controller = ToolConcurrencyController(config)

        start_time = time.perf_counter()

        # 执行 1000 次获取和释放
        for i in range(1000):
            slot = await controller.acquire_slot(
                tool_name=f"tool_{i % 10}",
                caller_id=f"agent_{i}",
                caller_type="conversation_agent",
            )
            if slot:
                await controller.release_slot(slot.slot_id)

        elapsed = time.perf_counter() - start_time

        print(f"\n1000 次获取/释放耗时: {elapsed:.3f}s")
        print(f"吞吐量: {1000 / elapsed:.0f} ops/s")

        # 应该在合理时间内完成
        assert elapsed < 5.0

        metrics = controller.get_metrics()
        assert metrics.total_acquired == 1000
        assert metrics.total_released == 1000


# =============================================================================
# 第十部分：集成场景测试
# =============================================================================


class TestIntegrationScenarios:
    """集成场景测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_with_queuing(self):
        """测试：完整工作流程（含排队）"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2, queue_size=10, strategy="fifo")
        controller = ToolConcurrencyController(config)

        # 模拟多个请求
        results = []

        async def execute_tool(tool_id: int):
            # 尝试获取槽位
            slot = await controller.acquire_slot(
                tool_name=f"tool_{tool_id}",
                caller_id=f"agent_{tool_id}",
                caller_type="conversation_agent",
            )

            if slot:
                # 模拟执行
                await asyncio.sleep(0.05)
                await controller.release_slot(slot.slot_id)
                results.append(("executed", tool_id))
            else:
                # 排队
                queued = await controller.enqueue(
                    tool_name=f"tool_{tool_id}",
                    caller_id=f"agent_{tool_id}",
                    caller_type="conversation_agent",
                    params={},
                )
                if queued:
                    results.append(("queued", tool_id))
                else:
                    results.append(("rejected", tool_id))

        # 并发执行 5 个请求
        await asyncio.gather(*[execute_tool(i) for i in range(5)])

        # 验证结果
        executed = [r for r in results if r[0] == "executed"]
        queued = [r for r in results if r[0] == "queued"]

        assert len(executed) == 2  # 最大并发数
        assert len(queued) == 3  # 剩余排队

    @pytest.mark.asyncio
    async def test_timeout_recovery(self):
        """测试：超时恢复"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2, default_timeout=0.05, strategy="reject")
        controller = ToolConcurrencyController(config)

        # 获取所有槽位
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )
        _slot2 = await controller.acquire_slot(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
        )

        # 新请求被拒绝
        slot3 = await controller.acquire_slot(
            tool_name="tool3",
            caller_id="agent_3",
            caller_type="conversation_agent",
        )
        assert slot3 is None

        # 等待超时
        await asyncio.sleep(0.1)

        # 取消超时槽位
        await controller.cancel_timeout_slots()

        # 现在应该可以获取新槽位
        slot4 = await controller.acquire_slot(
            tool_name="tool4",
            caller_id="agent_4",
            caller_type="conversation_agent",
        )
        assert slot4 is not None

    @pytest.mark.asyncio
    async def test_mixed_caller_types(self):
        """测试：混合调用者类型"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=2, strategy="reject")
        controller = ToolConcurrencyController(config)

        # 对话 Agent 调用
        _conv_slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="conv_1",
            caller_type="conversation_agent",
        )
        _conv_slot2 = await controller.acquire_slot(
            tool_name="tool2",
            caller_id="conv_2",
            caller_type="conversation_agent",
        )

        # 对话 Agent 达到限制
        conv_slot3 = await controller.acquire_slot(
            tool_name="tool3",
            caller_id="conv_3",
            caller_type="conversation_agent",
        )
        assert conv_slot3 is None

        # Workflow 节点不受限制
        wf_slots = []
        for i in range(5):
            slot = await controller.acquire_slot(
                tool_name=f"wf_tool_{i}",
                caller_id=f"workflow_{i}",
                caller_type="workflow_node",
            )
            wf_slots.append(slot)

        # 所有 Workflow 节点都成功
        assert all(s is not None for s in wf_slots)

        # 验证指标
        metrics = controller.get_metrics()
        assert metrics.current_concurrent == 2  # 仅对话 Agent

    @pytest.mark.asyncio
    async def test_controller_reset(self):
        """测试：控制器重置"""
        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        config = ConcurrencyConfig(max_concurrent=5, queue_size=10, strategy="fifo")
        controller = ToolConcurrencyController(config)

        # 执行一些操作
        _slot1 = await controller.acquire_slot(
            tool_name="tool1",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )
        _queued1 = await controller.enqueue(
            tool_name="tool2",
            caller_id="agent_2",
            caller_type="conversation_agent",
            params={},
        )

        # 重置
        await controller.reset()

        # 验证状态清空
        assert controller.current_concurrent == 0
        assert controller.queue_length == 0
        metrics = controller.get_metrics()
        assert metrics.total_acquired == 0

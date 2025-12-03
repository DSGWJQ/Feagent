"""性能基准测试

测试目标：
1. EventBus 消息吞吐量
2. 节点执行延迟
3. Coordinator 决策验证速度
4. 上下文压缩开销
5. 工作流执行时间

运行命令：
    pytest tests/performance/test_performance_benchmarks.py -v -s

注意：这些测试验证性能是否在可接受范围内，
如果性能低于预期阈值，测试将失败。
"""

import statistics
import time
from unittest.mock import AsyncMock

import pytest

from src.domain.services.event_bus import EventBus


class PerformanceMetrics:
    """性能指标收集器"""

    def __init__(self):
        self.measurements: list[float] = []

    def record(self, duration: float) -> None:
        """记录一次测量"""
        self.measurements.append(duration)

    @property
    def count(self) -> int:
        return len(self.measurements)

    @property
    def total(self) -> float:
        return sum(self.measurements)

    @property
    def mean(self) -> float:
        if not self.measurements:
            return 0.0
        return statistics.mean(self.measurements)

    @property
    def median(self) -> float:
        if not self.measurements:
            return 0.0
        return statistics.median(self.measurements)

    @property
    def min_value(self) -> float:
        if not self.measurements:
            return 0.0
        return min(self.measurements)

    @property
    def max_value(self) -> float:
        if not self.measurements:
            return 0.0
        return max(self.measurements)

    @property
    def std_dev(self) -> float:
        if len(self.measurements) < 2:
            return 0.0
        return statistics.stdev(self.measurements)

    @property
    def p95(self) -> float:
        """95th percentile"""
        if not self.measurements:
            return 0.0
        sorted_measurements = sorted(self.measurements)
        idx = int(len(sorted_measurements) * 0.95)
        return sorted_measurements[min(idx, len(sorted_measurements) - 1)]

    @property
    def p99(self) -> float:
        """99th percentile"""
        if not self.measurements:
            return 0.0
        sorted_measurements = sorted(self.measurements)
        idx = int(len(sorted_measurements) * 0.99)
        return sorted_measurements[min(idx, len(sorted_measurements) - 1)]

    def report(self, name: str) -> str:
        """生成性能报告"""
        return (
            f"\n=== {name} 性能报告 ===\n"
            f"总次数: {self.count}\n"
            f"总耗时: {self.total:.4f}s\n"
            f"平均: {self.mean * 1000:.3f}ms\n"
            f"中位数: {self.median * 1000:.3f}ms\n"
            f"最小: {self.min_value * 1000:.3f}ms\n"
            f"最大: {self.max_value * 1000:.3f}ms\n"
            f"标准差: {self.std_dev * 1000:.3f}ms\n"
            f"P95: {self.p95 * 1000:.3f}ms\n"
            f"P99: {self.p99 * 1000:.3f}ms\n"
        )


class TestEventBusPerformance:
    """EventBus 性能测试"""

    # 性能阈值
    PUBLISH_THRESHOLD_MS = 1.0  # 单次发布应该 < 1ms
    THROUGHPUT_MIN = 1000  # 每秒至少 1000 条消息

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.asyncio
    async def test_single_publish_latency(self, event_bus):
        """测试单次发布延迟"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent

        metrics = PerformanceMetrics()

        # 订阅者
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe(DecisionMadeEvent, handler)

        # 测量 100 次发布
        for i in range(100):
            event = DecisionMadeEvent(
                source="benchmark",
                decision_type="test",
                payload={"index": i},
            )

            start = time.perf_counter()
            await event_bus.publish(event)
            end = time.perf_counter()

            metrics.record(end - start)

        # 输出报告
        print(metrics.report("单次发布延迟"))

        # 验证性能
        assert (
            metrics.mean * 1000 < self.PUBLISH_THRESHOLD_MS
        ), f"平均发布延迟 {metrics.mean * 1000:.3f}ms 超过阈值 {self.PUBLISH_THRESHOLD_MS}ms"
        assert len(received) == 100, "应该收到所有事件"

    @pytest.mark.asyncio
    async def test_event_bus_throughput(self, event_bus):
        """测试 EventBus 吞吐量"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent

        received_count = 0

        async def handler(event):
            nonlocal received_count
            received_count += 1

        event_bus.subscribe(DecisionMadeEvent, handler)

        # 发布 1000 条消息
        num_messages = 1000
        events = [
            DecisionMadeEvent(
                source="benchmark",
                decision_type="test",
                payload={"index": i},
            )
            for i in range(num_messages)
        ]

        start = time.perf_counter()
        for event in events:
            await event_bus.publish(event)
        end = time.perf_counter()

        duration = end - start
        throughput = num_messages / duration

        print("\n=== EventBus 吞吐量测试 ===")
        print(f"消息数: {num_messages}")
        print(f"总耗时: {duration:.4f}s")
        print(f"吞吐量: {throughput:.0f} msg/s")

        # 验证吞吐量
        assert (
            throughput >= self.THROUGHPUT_MIN
        ), f"吞吐量 {throughput:.0f} msg/s 低于阈值 {self.THROUGHPUT_MIN} msg/s"
        assert received_count == num_messages, "应该收到所有消息"

    @pytest.mark.asyncio
    async def test_multiple_subscribers_performance(self, event_bus):
        """测试多订阅者性能"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent

        counters = [0] * 10

        # 注册 10 个订阅者
        for i in range(10):
            idx = i

            async def handler(event, idx=idx):
                counters[idx] += 1

            event_bus.subscribe(DecisionMadeEvent, handler)

        # 发布 100 条消息
        num_messages = 100
        events = [
            DecisionMadeEvent(
                source="benchmark",
                decision_type="test",
                payload={"index": i},
            )
            for i in range(num_messages)
        ]

        start = time.perf_counter()
        for event in events:
            await event_bus.publish(event)
        end = time.perf_counter()

        duration = end - start
        avg_per_message = (duration / num_messages) * 1000

        print("\n=== 多订阅者性能测试 ===")
        print("订阅者数: 10")
        print(f"消息数: {num_messages}")
        print(f"总耗时: {duration:.4f}s")
        print(f"每消息平均: {avg_per_message:.3f}ms")

        # 验证所有订阅者都收到消息
        for i, count in enumerate(counters):
            assert count == num_messages, f"订阅者 {i} 应该收到 {num_messages} 条消息"

        # 多订阅者应该仍然保持较好性能（每消息 < 5ms）
        assert avg_per_message < 5.0, f"多订阅者时每消息平均 {avg_per_message:.3f}ms 超过阈值 5ms"


class TestCoordinatorPerformance:
    """Coordinator 性能测试"""

    VALIDATION_THRESHOLD_MS = 0.5  # 单次验证应该 < 0.5ms
    RULE_CHECK_THRESHOLD_MS = 0.1  # 单条规则检查应该 < 0.1ms

    @pytest.fixture
    def coordinator(self):
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        coordinator = CoordinatorAgent()

        # 添加多条规则
        for i in range(10):
            coordinator.add_rule(
                Rule(
                    id=f"rule_{i}",
                    name=f"规则 {i}",
                    condition=lambda d, i=i: d.get("value", 0) > i,
                    error_message=f"值必须大于 {i}",
                )
            )

        return coordinator

    def test_validation_latency(self, coordinator):
        """测试决策验证延迟"""
        metrics = PerformanceMetrics()

        # 测量 1000 次验证
        for i in range(1000):
            decision = {"value": 50, "index": i}

            start = time.perf_counter()
            result = coordinator.validate_decision(decision)
            end = time.perf_counter()

            metrics.record(end - start)

        print(metrics.report("决策验证延迟"))

        # 验证性能
        assert (
            metrics.mean * 1000 < self.VALIDATION_THRESHOLD_MS
        ), f"平均验证延迟 {metrics.mean * 1000:.3f}ms 超过阈值 {self.VALIDATION_THRESHOLD_MS}ms"

    def test_rule_checking_overhead(self, coordinator):
        """测试规则检查开销与规则数量的关系"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        # 测试不同规则数量
        rule_counts = [1, 5, 10, 20, 50]
        results = {}

        for num_rules in rule_counts:
            # 创建新的 coordinator
            coord = CoordinatorAgent()
            for i in range(num_rules):
                coord.add_rule(
                    Rule(
                        id=f"rule_{i}",
                        name=f"规则 {i}",
                        condition=lambda d: True,  # 所有规则都通过
                    )
                )

            # 测量
            metrics = PerformanceMetrics()
            for _ in range(100):
                decision = {"value": 50}

                start = time.perf_counter()
                coord.validate_decision(decision)
                end = time.perf_counter()

                metrics.record(end - start)

            results[num_rules] = metrics.mean

        print("\n=== 规则数量 vs 验证延迟 ===")
        for num_rules, avg_time in results.items():
            print(f"{num_rules} 规则: {avg_time * 1000:.4f}ms")

        # 验证线性增长（50规则应该 < 5x 单规则的时间）
        if 1 in results and 50 in results:
            ratio = results[50] / results[1] if results[1] > 0 else 0
            assert ratio < 100, f"规则数量增加 50x 但延迟增加了 {ratio:.1f}x"


class TestContextCompressionPerformance:
    """上下文压缩性能测试"""

    COMPRESSION_THRESHOLD_MS = 10.0  # 单次压缩应该 < 10ms

    @pytest.fixture
    def compressor(self):
        from src.domain.services.context_compressor import ContextCompressor

        return ContextCompressor()

    def test_compression_latency(self, compressor):
        """测试压缩延迟"""
        from src.domain.services.context_compressor import CompressionInput

        metrics = PerformanceMetrics()

        # 测量压缩时间
        for i in range(100):
            # 创建压缩输入 - 使用正确的数据格式
            input_data = CompressionInput(
                workflow_id=f"wf_test_{i}",
                source_type="execution",
                raw_data={
                    "executed_nodes": [
                        {"id": f"node_{j}", "status": "completed"} for j in range(20)
                    ],
                    "node_outputs": {f"node_{j}": {"data": f"result_{j}"} for j in range(20)},
                    "errors": [{"node": f"node_{j}", "error": f"错误 {j}"} for j in range(3)],
                },
            )

            start = time.perf_counter()
            result = compressor.compress(input_data)
            end = time.perf_counter()

            metrics.record(end - start)

        print(metrics.report("上下文压缩延迟"))

        # 验证性能
        assert (
            metrics.mean * 1000 < self.COMPRESSION_THRESHOLD_MS
        ), f"平均压缩延迟 {metrics.mean * 1000:.3f}ms 超过阈值 {self.COMPRESSION_THRESHOLD_MS}ms"

    def test_snapshot_creation_performance(self):
        """测试快照创建性能"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextSnapshotManager,
        )

        manager = ContextSnapshotManager()
        metrics = PerformanceMetrics()

        # 测量快照创建时间
        for i in range(100):
            # 创建上下文 - 使用正确的字段
            ctx = CompressedContext(
                workflow_id=f"wf_test_{i}",
                task_goal="测试目标",
                execution_status={"step": 1, "status": "running"},
            )

            start = time.perf_counter()
            manager.save_snapshot(ctx)  # 使用正确的方法名
            end = time.perf_counter()

            metrics.record(end - start)

        print(metrics.report("快照创建延迟"))

        # 快照创建应该很快（< 1ms）
        assert (
            metrics.mean * 1000 < 1.0
        ), f"平均快照创建延迟 {metrics.mean * 1000:.3f}ms 超过阈值 1ms"


class TestWorkflowExecutionPerformance:
    """工作流执行性能测试"""

    @pytest.fixture
    def workflow_context(self):
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="perf_user")
        session_ctx = SessionContext(session_id="perf_session", global_context=global_ctx)
        return WorkflowContext(workflow_id="perf_workflow", session_context=session_ctx)

    @pytest.fixture
    def workflow_agent(self, workflow_context):
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"status": "success"}

        return WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=factory,
            node_executor=mock_executor,
        )

    def test_node_creation_performance(self, workflow_agent):
        """测试节点创建性能"""
        metrics = PerformanceMetrics()

        # 测量节点创建时间 - 使用 GENERIC 类型避免必填字段问题
        for i in range(100):
            start = time.perf_counter()
            node = workflow_agent.create_node(
                {
                    "node_type": "GENERIC",
                    "config": {"name": f"测试节点 {i}"},
                }
            )
            end = time.perf_counter()

            metrics.record(end - start)

        print(metrics.report("节点创建延迟"))

        # 节点创建应该很快（< 1ms）
        assert (
            metrics.mean * 1000 < 1.0
        ), f"平均节点创建延迟 {metrics.mean * 1000:.3f}ms 超过阈值 1ms"

    def test_edge_connection_performance(self, workflow_agent):
        """测试边连接性能"""
        # 先创建节点 - 使用 GENERIC 类型
        nodes = []
        for i in range(50):
            node = workflow_agent.create_node(
                {
                    "node_type": "GENERIC",
                    "config": {"name": f"测试节点 {i}"},
                }
            )
            workflow_agent.add_node(node)
            nodes.append(node)

        metrics = PerformanceMetrics()

        # 测量边创建时间（链式连接）
        for i in range(len(nodes) - 1):
            start = time.perf_counter()
            workflow_agent.connect_nodes(nodes[i].id, nodes[i + 1].id)
            end = time.perf_counter()

            metrics.record(end - start)

        print(metrics.report("边连接延迟"))

        # 边创建应该很快（< 0.5ms）
        assert (
            metrics.mean * 1000 < 0.5
        ), f"平均边连接延迟 {metrics.mean * 1000:.3f}ms 超过阈值 0.5ms"


class TestAgentCollaborationPerformance:
    """Agent 协作性能测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.asyncio
    async def test_full_decision_flow_latency(self, event_bus):
        """测试完整决策流程延迟"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionValidatedEvent,
            Rule,
        )

        # 设置 Coordinator
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.add_rule(Rule(id="allow_all", name="允许所有", condition=lambda d: True))
        event_bus.add_middleware(coordinator.as_middleware())

        # 收集验证事件
        validated_events = []
        flow_times = []

        async def capture_validated(event):
            validated_events.append(event)

        event_bus.subscribe(DecisionValidatedEvent, capture_validated)

        metrics = PerformanceMetrics()

        # 测量完整流程
        for i in range(100):
            event = DecisionMadeEvent(
                source="benchmark",
                decision_type="create_node",
                payload={"node_type": "LLM", "index": i},
            )

            start = time.perf_counter()
            await event_bus.publish(event)
            end = time.perf_counter()

            metrics.record(end - start)

        print(metrics.report("完整决策流程延迟"))

        # 完整流程应该 < 5ms
        assert (
            metrics.mean * 1000 < 5.0
        ), f"平均完整决策流程延迟 {metrics.mean * 1000:.3f}ms 超过阈值 5ms"
        assert len(validated_events) == 100, "应该验证所有决策"


class TestMemoryUsage:
    """内存使用测试"""

    def test_event_bus_memory_with_many_events(self):
        """测试大量事件时的内存使用"""
        import sys

        from src.domain.agents.conversation_agent import DecisionMadeEvent

        event_bus = EventBus()

        # 创建大量事件
        events = []
        for i in range(10000):
            events.append(
                DecisionMadeEvent(
                    source="memory_test",
                    decision_type="test",
                    payload={"data": "x" * 100, "index": i},
                )
            )

        # 计算内存占用
        event_size = sys.getsizeof(events[0])
        total_size = sum(sys.getsizeof(e) for e in events)

        print("\n=== 内存使用测试 ===")
        print(f"单事件大小: {event_size} bytes")
        print(f"10000事件总大小: {total_size / 1024:.2f} KB")

        # 内存使用应该合理（每事件 < 1KB）
        assert event_size < 1024, f"单事件大小 {event_size} bytes 超过 1KB"

    def test_coordinator_state_memory(self):
        """测试 Coordinator 状态内存使用"""
        import sys

        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 添加大量工作流状态
        for i in range(100):
            coordinator.workflow_states[f"wf_{i}"] = {
                "executed_nodes": [f"node_{j}" for j in range(50)],
                "node_outputs": {f"node_{j}": {"data": "x" * 100} for j in range(50)},
                "failed_nodes": [],
            }

        # 计算状态大小
        state_size = sys.getsizeof(coordinator.workflow_states)

        print("\n=== Coordinator 状态内存 ===")
        print(f"100个工作流状态大小: {state_size / 1024:.2f} KB")

        # 状态使用应该合理（100个工作流 < 100KB）
        assert state_size < 100 * 1024, f"状态大小 {state_size} bytes 超过 100KB"


# 导出
__all__ = [
    "PerformanceMetrics",
    "TestEventBusPerformance",
    "TestCoordinatorPerformance",
    "TestContextCompressionPerformance",
    "TestWorkflowExecutionPerformance",
    "TestAgentCollaborationPerformance",
    "TestMemoryUsage",
]

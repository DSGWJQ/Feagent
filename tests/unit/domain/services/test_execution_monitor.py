"""执行监控器测试 - Phase 7.3

TDD RED阶段：测试执行上下文和监控器
"""

import pytest


class TestExecutionMetrics:
    """执行指标数据类测试"""

    def test_create_execution_metrics_with_defaults(self):
        """创建执行指标应有默认值"""
        from src.domain.services.execution_monitor import ExecutionMetrics

        metrics = ExecutionMetrics()

        assert metrics.total_nodes == 0
        assert metrics.completed_nodes == 0
        assert metrics.failed_nodes == 0
        assert metrics.total_time_ms == 0
        assert metrics.total_tokens == 0
        assert metrics.total_cost == 0.0

    def test_update_execution_metrics(self):
        """更新执行指标"""
        from src.domain.services.execution_monitor import ExecutionMetrics

        metrics = ExecutionMetrics(total_nodes=5)
        metrics.completed_nodes = 3
        metrics.failed_nodes = 1
        metrics.total_time_ms = 5000

        assert metrics.completed_nodes == 3
        assert metrics.failed_nodes == 1
        assert metrics.total_time_ms == 5000


class TestErrorEntry:
    """错误记录数据类测试"""

    def test_create_error_entry(self):
        """创建错误记录"""
        from src.domain.services.execution_monitor import ErrorEntry, ErrorHandlingAction

        entry = ErrorEntry(
            node_id="node_123",
            error_type="TimeoutError",
            error_message="执行超时",
            attempt=1,
            action_taken=ErrorHandlingAction.RETRY,
        )

        assert entry.node_id == "node_123"
        assert entry.error_type == "TimeoutError"
        assert entry.attempt == 1
        assert entry.action_taken == ErrorHandlingAction.RETRY
        assert entry.timestamp is not None


class TestExecutionContext:
    """执行上下文数据类测试"""

    def test_create_execution_context(self):
        """创建执行上下文"""
        from src.domain.services.execution_monitor import ExecutionContext

        ctx = ExecutionContext(
            workflow_id="wf_123",
            node_ids=["node_1", "node_2", "node_3"],
        )

        assert ctx.workflow_id == "wf_123"
        assert len(ctx.pending_nodes) == 3
        assert len(ctx.executed_nodes) == 0
        assert len(ctx.running_nodes) == 0
        assert ctx.started_at is not None

    def test_execution_context_track_node_start(self):
        """执行上下文应跟踪节点开始"""
        from src.domain.services.execution_monitor import ExecutionContext

        ctx = ExecutionContext(
            workflow_id="wf_123",
            node_ids=["node_1", "node_2"],
        )

        ctx.mark_node_running("node_1", {"input": "data"})

        assert "node_1" in ctx.running_nodes
        assert "node_1" not in ctx.pending_nodes
        assert ctx.node_inputs["node_1"] == {"input": "data"}

    def test_execution_context_track_node_complete(self):
        """执行上下文应跟踪节点完成"""
        from src.domain.services.execution_monitor import ExecutionContext

        ctx = ExecutionContext(
            workflow_id="wf_123",
            node_ids=["node_1", "node_2"],
        )

        ctx.mark_node_running("node_1", {})
        ctx.mark_node_completed("node_1", {"output": "result"})

        assert "node_1" in ctx.executed_nodes
        assert "node_1" not in ctx.running_nodes
        assert ctx.node_outputs["node_1"] == {"output": "result"}
        assert ctx.metrics.completed_nodes == 1

    def test_execution_context_track_node_failed(self):
        """执行上下文应跟踪节点失败"""
        from src.domain.services.execution_monitor import ErrorHandlingAction, ExecutionContext

        ctx = ExecutionContext(
            workflow_id="wf_123",
            node_ids=["node_1", "node_2"],
        )

        ctx.mark_node_running("node_1", {})
        # 使用ABORT动作，表示节点真正失败（不是重试）
        ctx.mark_node_failed(
            "node_1",
            error_type="ValueError",
            error_message="无效的输入",
            action_taken=ErrorHandlingAction.ABORT,
        )

        assert "node_1" in ctx.failed_nodes
        assert "node_1" not in ctx.running_nodes
        assert len(ctx.error_log) == 1
        assert ctx.metrics.failed_nodes == 1

    def test_execution_context_retry_should_not_mark_failed(self):
        """重试时不应标记为失败"""
        from src.domain.services.execution_monitor import ErrorHandlingAction, ExecutionContext

        ctx = ExecutionContext(
            workflow_id="wf_123",
            node_ids=["node_1"],
        )

        ctx.mark_node_running("node_1", {})
        ctx.mark_node_failed(
            "node_1",
            error_type="TimeoutError",
            error_message="超时",
            action_taken=ErrorHandlingAction.RETRY,
        )

        # RETRY时不应加入failed_nodes
        assert "node_1" not in ctx.failed_nodes
        # 但应该记录错误日志
        assert len(ctx.error_log) == 1
        assert ctx.metrics.failed_nodes == 0

    def test_execution_context_track_node_skipped(self):
        """执行上下文应跟踪节点跳过"""
        from src.domain.services.execution_monitor import ExecutionContext

        ctx = ExecutionContext(
            workflow_id="wf_123",
            node_ids=["node_1", "node_2"],
        )

        ctx.mark_node_skipped("node_1", reason="可选节点")

        assert "node_1" in ctx.skipped_nodes
        assert "node_1" not in ctx.pending_nodes

    def test_execution_context_get_progress(self):
        """执行上下文应提供进度信息"""
        from src.domain.services.execution_monitor import ExecutionContext

        ctx = ExecutionContext(
            workflow_id="wf_123",
            node_ids=["node_1", "node_2", "node_3", "node_4"],
        )

        ctx.mark_node_running("node_1", {})
        ctx.mark_node_completed("node_1", {})
        ctx.mark_node_running("node_2", {})

        progress = ctx.get_progress()

        assert progress["total"] == 4
        assert progress["completed"] == 1
        assert progress["running"] == 1
        assert progress["pending"] == 2
        assert progress["percentage"] == 25.0  # 1/4 = 25%


class TestExecutionMonitor:
    """执行监控器测试"""

    def test_create_execution_monitor(self):
        """创建执行监控器"""
        from src.domain.services.execution_monitor import ExecutionMonitor

        monitor = ExecutionMonitor()

        assert monitor is not None
        assert len(monitor.contexts) == 0

    def test_on_workflow_start_should_create_context(self):
        """工作流开始应创建上下文"""
        from src.domain.services.execution_monitor import ExecutionMonitor

        monitor = ExecutionMonitor()
        monitor.on_workflow_start(
            workflow_id="wf_123",
            node_ids=["node_1", "node_2", "node_3"],
        )

        ctx = monitor.get_context("wf_123")
        assert ctx is not None
        assert ctx.workflow_id == "wf_123"
        assert len(ctx.pending_nodes) == 3

    def test_on_node_start_should_update_context(self):
        """节点开始应更新上下文"""
        from src.domain.services.execution_monitor import ExecutionMonitor

        monitor = ExecutionMonitor()
        monitor.on_workflow_start("wf_123", ["node_1", "node_2"])

        monitor.on_node_start("wf_123", "node_1", {"input": "data"})

        ctx = monitor.get_context("wf_123")
        assert "node_1" in ctx.running_nodes
        assert ctx.node_inputs["node_1"] == {"input": "data"}

    def test_on_node_complete_should_update_context(self):
        """节点完成应更新上下文"""
        from src.domain.services.execution_monitor import ExecutionMonitor

        monitor = ExecutionMonitor()
        monitor.on_workflow_start("wf_123", ["node_1", "node_2"])
        monitor.on_node_start("wf_123", "node_1", {})

        monitor.on_node_complete("wf_123", "node_1", {"result": "success"})

        ctx = monitor.get_context("wf_123")
        assert "node_1" in ctx.executed_nodes
        assert ctx.node_outputs["node_1"] == {"result": "success"}

    def test_on_node_error_should_return_handling_action(self):
        """节点错误应返回处理动作"""
        from src.domain.services.execution_monitor import (
            ErrorHandlingAction,
            ExecutionMonitor,
        )

        monitor = ExecutionMonitor()
        monitor.on_workflow_start("wf_123", ["node_1"])
        monitor.on_node_start("wf_123", "node_1", {})

        action = monitor.on_node_error(
            workflow_id="wf_123",
            node_id="node_1",
            error=TimeoutError("执行超时"),
        )

        # 默认应该返回RETRY（对于超时错误）
        assert action in [
            ErrorHandlingAction.RETRY,
            ErrorHandlingAction.FEEDBACK,
            ErrorHandlingAction.ABORT,
        ]

    def test_on_node_skipped_should_update_context(self):
        """节点跳过应更新上下文"""
        from src.domain.services.execution_monitor import ExecutionMonitor

        monitor = ExecutionMonitor()
        monitor.on_workflow_start("wf_123", ["node_1", "node_2"])

        monitor.on_node_skipped("wf_123", "node_2", reason="incoming_edge_conditions_not_met")

        ctx = monitor.get_context("wf_123")
        assert "node_2" in ctx.skipped_nodes

    def test_on_workflow_complete_should_finalize_context(self):
        """工作流完成应终结上下文"""
        from src.domain.services.execution_monitor import ExecutionMonitor

        monitor = ExecutionMonitor()
        monitor.on_workflow_start("wf_123", ["node_1"])
        monitor.on_node_start("wf_123", "node_1", {})
        monitor.on_node_complete("wf_123", "node_1", {})

        monitor.on_workflow_complete("wf_123", status="completed")

        ctx = monitor.get_context("wf_123")
        assert ctx.completed_at is not None
        assert ctx.status == "completed"

    def test_get_all_workflows_should_return_summary(self):
        """获取所有工作流应返回摘要"""
        from src.domain.services.execution_monitor import ExecutionMonitor

        monitor = ExecutionMonitor()
        monitor.on_workflow_start("wf_1", ["node_1", "node_2"])
        monitor.on_workflow_start("wf_2", ["node_a", "node_b", "node_c"])

        summary = monitor.get_all_workflows()

        assert len(summary) == 2
        assert "wf_1" in summary
        assert "wf_2" in summary
        assert summary["wf_1"]["total_nodes"] == 2
        assert summary["wf_2"]["total_nodes"] == 3


class TestExecutionMonitorWithErrorHandler:
    """执行监控器与错误处理器集成测试"""

    def test_monitor_should_use_error_handler_policy(self):
        """监控器应使用错误处理策略"""
        from src.domain.services.execution_monitor import (
            ErrorHandler,
            ErrorHandlingAction,
            ErrorHandlingPolicy,
            ExecutionMonitor,
        )

        policy = ErrorHandlingPolicy(
            max_retries=3,
            retryable_errors=["TimeoutError", "ConnectionError"],
        )
        handler = ErrorHandler(policy)
        monitor = ExecutionMonitor(error_handler=handler)

        monitor.on_workflow_start("wf_123", ["node_1"])
        monitor.on_node_start("wf_123", "node_1", {})

        # 第一次超时错误应该重试
        action = monitor.on_node_error(
            "wf_123",
            "node_1",
            TimeoutError("超时"),
        )

        assert action == ErrorHandlingAction.RETRY

    def test_monitor_should_track_retry_count(self):
        """监控器应跟踪重试次数"""
        from src.domain.services.execution_monitor import (
            ErrorHandler,
            ErrorHandlingAction,
            ErrorHandlingPolicy,
            ExecutionMonitor,
        )

        policy = ErrorHandlingPolicy(max_retries=2)
        handler = ErrorHandler(policy)
        monitor = ExecutionMonitor(error_handler=handler)

        monitor.on_workflow_start("wf_123", ["node_1"])

        # 模拟多次重试
        for i in range(3):
            monitor.on_node_start("wf_123", "node_1", {})
            action = monitor.on_node_error("wf_123", "node_1", TimeoutError("超时"))

            if i < 2:
                assert action == ErrorHandlingAction.RETRY
            else:
                # 超过最大重试次数
                assert action in [ErrorHandlingAction.FEEDBACK, ErrorHandlingAction.ABORT]


class TestExecutionMonitorEvents:
    """执行监控器事件测试"""

    @pytest.mark.asyncio
    async def test_monitor_should_emit_events(self):
        """监控器应发出事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.execution_monitor import ExecutionMonitor

        events_received = []

        async def event_handler(event):
            events_received.append(event)

        event_bus = EventBus()
        monitor = ExecutionMonitor(event_bus=event_bus)

        # 订阅事件
        from src.domain.services.execution_monitor import (
            NodeExecutionStartedEvent,
            WorkflowExecutionStartedEvent,
        )

        event_bus.subscribe(WorkflowExecutionStartedEvent, event_handler)
        event_bus.subscribe(NodeExecutionStartedEvent, event_handler)

        # 触发事件
        await monitor.on_workflow_start_async("wf_123", ["node_1"])
        await monitor.on_node_start_async("wf_123", "node_1", {})

        assert len(events_received) >= 2

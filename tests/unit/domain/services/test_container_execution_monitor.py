"""ContainerExecutionMonitor 单元测试

TDD测试：先写测试，后实现
测试容器执行监控服务的所有功能：
- 事件订阅/取消订阅
- 容器执行记录
- 日志记录（有界列表）
- 统计汇总
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ==================== 初始化测试 ====================


class TestContainerExecutionMonitorInit:
    """初始化测试"""

    def test_init_with_event_bus(self) -> None:
        """测试使用EventBus初始化"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = MagicMock(spec=EventBus)
        monitor = ContainerExecutionMonitor(event_bus=event_bus)

        assert monitor.event_bus == event_bus
        assert monitor.max_log_size == 500  # 默认值
        assert monitor.container_executions == {}
        assert monitor.container_logs == {}
        assert monitor._is_listening_container_events is False

    def test_init_with_custom_max_log_size(self) -> None:
        """测试自定义日志大小上限"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None, max_log_size=100)

        assert monitor.max_log_size == 100

    def test_init_without_event_bus(self) -> None:
        """测试不提供EventBus初始化"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        assert monitor.event_bus is None


# ==================== 事件订阅测试 ====================


class TestContainerExecutionMonitorSubscription:
    """事件订阅测试"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        from src.domain.services.event_bus import EventBus

        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = MagicMock()
        event_bus.unsubscribe = MagicMock()
        return event_bus

    def test_start_listening_subscribes_events(self, mock_event_bus) -> None:
        """测试启动监听订阅事件"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=mock_event_bus)
        monitor.start_container_execution_listening()

        assert monitor._is_listening_container_events is True
        assert mock_event_bus.subscribe.call_count == 3

    def test_start_listening_without_event_bus_raises_error(self) -> None:
        """测试无EventBus时启动监听抛出异常"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        with pytest.raises(ValueError, match="EventBus is required"):
            monitor.start_container_execution_listening()

    def test_start_listening_idempotent(self, mock_event_bus) -> None:
        """测试重复启动监听是幂等的"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=mock_event_bus)
        monitor.start_container_execution_listening()
        monitor.start_container_execution_listening()

        # 只应该订阅一次
        assert mock_event_bus.subscribe.call_count == 3

    def test_stop_listening_unsubscribes_events(self, mock_event_bus) -> None:
        """测试停止监听取消订阅"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=mock_event_bus)
        monitor.start_container_execution_listening()
        monitor.stop_container_execution_listening()

        assert monitor._is_listening_container_events is False
        assert mock_event_bus.unsubscribe.call_count == 3

    def test_stop_listening_without_start_is_safe(self, mock_event_bus) -> None:
        """测试未启动直接停止是安全的"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=mock_event_bus)
        monitor.stop_container_execution_listening()

        # 不应该调用 unsubscribe
        mock_event_bus.unsubscribe.assert_not_called()

    def test_start_listening_alias(self, mock_event_bus) -> None:
        """测试别名方法 start_listening"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=mock_event_bus)
        monitor.start_listening()

        assert monitor._is_listening_container_events is True


# ==================== 容器执行记录测试 ====================


class TestContainerExecutionRecording:
    """容器执行记录测试"""

    @pytest.mark.asyncio
    async def test_handle_container_started(self) -> None:
        """测试处理容器开始事件"""
        from src.domain.agents.container_events import ContainerExecutionStartedEvent
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        event = ContainerExecutionStartedEvent(
            container_id="c001",
            node_id="n001",
            workflow_id="wf001",
            image="python:3.11",
        )

        await monitor._handle_container_started(event)

        assert "wf001" in monitor.container_executions
        executions = monitor.container_executions["wf001"]
        assert len(executions) == 1
        assert executions[0]["container_id"] == "c001"
        assert executions[0]["status"] == "running"
        assert executions[0]["image"] == "python:3.11"

    @pytest.mark.asyncio
    async def test_handle_container_completed(self) -> None:
        """测试处理容器完成事件"""
        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
        )
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        event = ContainerExecutionCompletedEvent(
            container_id="c001",
            node_id="n001",
            workflow_id="wf001",
            success=True,
            exit_code=0,
            stdout="Hello",
            stderr="",
            execution_time=1.5,
        )

        await monitor._handle_container_completed(event)

        assert "wf001" in monitor.container_executions
        executions = monitor.container_executions["wf001"]
        assert len(executions) == 1
        assert executions[0]["container_id"] == "c001"
        assert executions[0]["success"] is True
        assert executions[0]["exit_code"] == 0
        assert executions[0]["status"] == "completed"
        assert executions[0]["execution_time"] == 1.5

    @pytest.mark.asyncio
    async def test_handle_container_failed(self) -> None:
        """测试处理容器失败事件"""
        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
        )
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        event = ContainerExecutionCompletedEvent(
            container_id="c001",
            node_id="n001",
            workflow_id="wf001",
            success=False,
            exit_code=1,
            stderr="Error occurred",
            execution_time=0.5,
        )

        await monitor._handle_container_completed(event)

        executions = monitor.container_executions["wf001"]
        assert executions[0]["success"] is False
        assert executions[0]["status"] == "failed"
        assert executions[0]["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_multiple_containers_same_workflow(self) -> None:
        """测试同一工作流多个容器"""
        from src.domain.agents.container_events import ContainerExecutionStartedEvent
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        event1 = ContainerExecutionStartedEvent(
            container_id="c001",
            node_id="n001",
            workflow_id="wf001",
        )
        event2 = ContainerExecutionStartedEvent(
            container_id="c002",
            node_id="n002",
            workflow_id="wf001",
        )

        await monitor._handle_container_started(event1)
        await monitor._handle_container_started(event2)

        executions = monitor.container_executions["wf001"]
        assert len(executions) == 2
        assert executions[0]["container_id"] == "c001"
        assert executions[1]["container_id"] == "c002"


# ==================== 容器日志记录测试 ====================


class TestContainerLogRecording:
    """容器日志记录测试"""

    @pytest.mark.asyncio
    async def test_handle_container_log(self) -> None:
        """测试处理容器日志事件"""
        from src.domain.agents.container_events import ContainerLogEvent
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None, max_log_size=10)

        event = ContainerLogEvent(
            container_id="c001",
            node_id="n001",
            log_level="INFO",
            message="Processing started",
            timestamp="2025-01-01T00:00:00",
        )

        await monitor._handle_container_log(event)

        assert "c001" in monitor.container_logs
        logs = monitor.container_logs["c001"]
        assert len(logs) == 1
        assert logs[0]["level"] == "INFO"
        assert logs[0]["message"] == "Processing started"

    @pytest.mark.asyncio
    async def test_bounded_log_list(self) -> None:
        """测试日志有界列表防止内存泄漏"""
        from src.domain.agents.container_events import ContainerLogEvent
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None, max_log_size=3)

        # 添加4条日志，应该只保留最新的3条
        for i in range(4):
            event = ContainerLogEvent(
                container_id="c001",
                node_id="n001",
                log_level="INFO",
                message=f"Log {i}",
            )
            await monitor._handle_container_log(event)

        logs = monitor.container_logs["c001"]
        assert len(logs) == 3  # 只保留最新3条
        assert logs[0]["message"] == "Log 1"  # 最旧的Log 0被移除
        assert logs[1]["message"] == "Log 2"
        assert logs[2]["message"] == "Log 3"

    @pytest.mark.asyncio
    async def test_logs_for_different_containers(self) -> None:
        """测试不同容器的日志分开存储"""
        from src.domain.agents.container_events import ContainerLogEvent
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        event1 = ContainerLogEvent(container_id="c001", message="Log from c001")
        event2 = ContainerLogEvent(container_id="c002", message="Log from c002")

        await monitor._handle_container_log(event1)
        await monitor._handle_container_log(event2)

        assert len(monitor.container_logs["c001"]) == 1
        assert len(monitor.container_logs["c002"]) == 1
        assert monitor.container_logs["c001"][0]["message"] == "Log from c001"


# ==================== 查询方法测试 ====================


class TestContainerExecutionQueries:
    """查询方法测试"""

    def test_get_workflow_container_executions(self) -> None:
        """测试获取工作流执行记录"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        # 添加测试数据
        monitor.container_executions["wf001"] = [
            {"container_id": "c001", "success": True},
            {"container_id": "c002", "success": False},
        ]

        executions = monitor.get_workflow_container_executions("wf001")

        assert len(executions) == 2
        assert executions[0]["container_id"] == "c001"
        assert executions[1]["container_id"] == "c002"

    def test_get_workflow_executions_not_found(self) -> None:
        """测试获取不存在的工作流"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        executions = monitor.get_workflow_container_executions("nonexistent")

        assert executions == []

    def test_get_container_logs(self) -> None:
        """测试获取容器日志"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        # 添加测试数据
        monitor.container_logs["c001"] = [
            {"level": "INFO", "message": "Log 1"},
            {"level": "ERROR", "message": "Log 2"},
        ]

        logs = monitor.get_container_logs("c001")

        assert len(logs) == 2
        assert logs[0]["level"] == "INFO"
        assert logs[1]["level"] == "ERROR"

    def test_get_container_logs_not_found(self) -> None:
        """测试获取不存在容器的日志"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        logs = monitor.get_container_logs("nonexistent")

        assert logs == []

    def test_get_workflow_executions_alias(self) -> None:
        """测试别名方法 get_workflow_executions"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)
        monitor.container_executions["wf001"] = [{"container_id": "c001"}]

        executions = monitor.get_workflow_executions("wf001")

        assert len(executions) == 1


# ==================== 统计方法测试 ====================


class TestContainerExecutionStatistics:
    """统计方法测试"""

    def test_statistics_with_status_field(self) -> None:
        """测试使用status字段的统计"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        # 添加测试数据（status 格式）
        monitor.container_executions["wf001"] = [
            {"status": "completed", "success": True, "execution_time": 1.0},
            {"status": "failed", "success": False, "execution_time": 0.5},
            {"status": "running"},  # 未完成，不计入统计
        ]

        stats = monitor.get_container_execution_statistics()

        assert stats["total_executions"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1
        assert stats["total_execution_time"] == 1.5

    def test_statistics_with_success_field_only(self) -> None:
        """测试仅使用success字段的统计（向后兼容）"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        # 添加测试数据（只有 success 字段）
        monitor.container_executions["wf001"] = [
            {"success": True, "execution_time": 2.0},
            {"success": False, "execution_time": 1.0},
        ]

        stats = monitor.get_container_execution_statistics()

        assert stats["total_executions"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1
        assert stats["total_execution_time"] == 3.0

    def test_statistics_empty(self) -> None:
        """测试空统计"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        stats = monitor.get_container_execution_statistics()

        assert stats["total_executions"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0
        assert stats["total_execution_time"] == 0.0

    def test_statistics_multiple_workflows(self) -> None:
        """测试多工作流统计汇总"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)

        monitor.container_executions["wf001"] = [
            {"status": "completed", "success": True, "execution_time": 1.0},
        ]
        monitor.container_executions["wf002"] = [
            {"status": "completed", "success": True, "execution_time": 2.0},
            {"status": "failed", "success": False, "execution_time": 0.5},
        ]

        stats = monitor.get_container_execution_statistics()

        assert stats["total_executions"] == 3
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        assert stats["total_execution_time"] == 3.5

    def test_get_statistics_alias(self) -> None:
        """测试别名方法 get_statistics"""
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None)
        monitor.container_executions["wf001"] = [
            {"status": "completed", "success": True, "execution_time": 1.0},
        ]

        stats = monitor.get_statistics()

        assert stats["total_executions"] == 1


# ==================== 集成测试 ====================


class TestContainerExecutionMonitorIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """测试完整生命周期"""
        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
            ContainerExecutionStartedEvent,
            ContainerLogEvent,
        )
        from src.domain.services.container_execution_monitor import (
            ContainerExecutionMonitor,
        )

        monitor = ContainerExecutionMonitor(event_bus=None, max_log_size=10)

        # 1. 容器开始
        started_event = ContainerExecutionStartedEvent(
            container_id="c001",
            node_id="n001",
            workflow_id="wf001",
            image="python:3.11",
        )
        await monitor._handle_container_started(started_event)

        # 2. 记录日志
        log_event1 = ContainerLogEvent(
            container_id="c001",
            log_level="INFO",
            message="Processing...",
        )
        await monitor._handle_container_log(log_event1)

        # 3. 容器完成
        completed_event = ContainerExecutionCompletedEvent(
            container_id="c001",
            node_id="n001",
            workflow_id="wf001",
            success=True,
            exit_code=0,
            execution_time=1.5,
        )
        await monitor._handle_container_completed(completed_event)

        # 验证执行记录
        executions = monitor.get_workflow_container_executions("wf001")
        assert len(executions) == 2  # started + completed
        assert executions[0]["status"] == "running"
        assert executions[1]["status"] == "completed"

        # 验证日志
        logs = monitor.get_container_logs("c001")
        assert len(logs) == 1
        assert logs[0]["message"] == "Processing..."

        # 验证统计
        stats = monitor.get_container_execution_statistics()
        assert stats["total_executions"] == 1
        assert stats["successful"] == 1

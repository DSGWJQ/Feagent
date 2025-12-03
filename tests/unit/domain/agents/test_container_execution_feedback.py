"""测试：容器执行与日志反馈

测试目标：
1. 容器执行事件定义
2. Coordinator 接收容器执行结果
3. 执行日志记录
4. 执行失败处理

完成标准：
- 容器执行发布事件
- Coordinator 订阅并记录事件
- 日志正确保存
- 失败有正确的错误信息
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus

# ==================== 测试1：容器执行事件 ====================


class TestContainerExecutionEvents:
    """测试容器执行事件"""

    def test_container_execution_started_event_exists(self):
        """ContainerExecutionStartedEvent 存在"""
        from src.domain.agents.container_events import ContainerExecutionStartedEvent

        event = ContainerExecutionStartedEvent(
            container_id="container_001",
            node_id="node_001",
            workflow_id="workflow_001",
            image="python:3.11",
        )

        assert event.container_id == "container_001"
        assert event.node_id == "node_001"
        assert event.image == "python:3.11"

    def test_container_execution_completed_event_exists(self):
        """ContainerExecutionCompletedEvent 存在"""
        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
        )

        event = ContainerExecutionCompletedEvent(
            container_id="container_001",
            node_id="node_001",
            workflow_id="workflow_001",
            success=True,
            exit_code=0,
            stdout="Hello World",
            stderr="",
            execution_time=1.5,
        )

        assert event.success is True
        assert event.exit_code == 0
        assert event.stdout == "Hello World"
        assert event.execution_time == 1.5

    def test_container_execution_failed_event(self):
        """容器执行失败事件"""
        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
        )

        event = ContainerExecutionCompletedEvent(
            container_id="container_001",
            node_id="node_001",
            workflow_id="workflow_001",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: module not found",
            execution_time=0.5,
        )

        assert event.success is False
        assert event.exit_code == 1
        assert "Error" in event.stderr

    def test_container_log_event_exists(self):
        """ContainerLogEvent 存在"""
        from src.domain.agents.container_events import ContainerLogEvent

        event = ContainerLogEvent(
            container_id="container_001",
            node_id="node_001",
            log_level="INFO",
            message="Processing started",
            timestamp="2025-01-01T00:00:00",
        )

        assert event.log_level == "INFO"
        assert event.message == "Processing started"


# ==================== 测试2：Coordinator 订阅容器事件 ====================


class TestCoordinatorContainerSubscription:
    """测试 Coordinator 订阅容器事件"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    def test_coordinator_can_start_container_listening(self, mock_event_bus):
        """Coordinator 可以启动容器事件监听"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        coordinator.start_container_execution_listening()

        assert coordinator._is_listening_container_events is True
        mock_event_bus.subscribe.assert_called()

    def test_coordinator_can_stop_container_listening(self, mock_event_bus):
        """Coordinator 可以停止容器事件监听"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)
        coordinator.start_container_execution_listening()
        coordinator.stop_container_execution_listening()

        assert coordinator._is_listening_container_events is False


# ==================== 测试3：容器执行结果记录 ====================


class TestContainerExecutionRecording:
    """测试容器执行结果记录"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    def test_coordinator_has_container_executions_storage(self, mock_event_bus):
        """Coordinator 有容器执行记录存储"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        assert hasattr(coordinator, "container_executions")
        assert isinstance(coordinator.container_executions, dict)

    @pytest.mark.asyncio
    async def test_coordinator_records_container_execution(self, mock_event_bus):
        """Coordinator 记录容器执行结果"""
        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
        )
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        event = ContainerExecutionCompletedEvent(
            container_id="container_001",
            node_id="node_001",
            workflow_id="workflow_001",
            success=True,
            exit_code=0,
            stdout="Output",
            execution_time=1.0,
        )

        await coordinator._handle_container_completed(event)

        assert "workflow_001" in coordinator.container_executions
        executions = coordinator.container_executions["workflow_001"]
        assert len(executions) == 1
        assert executions[0]["container_id"] == "container_001"
        assert executions[0]["success"] is True

    def test_get_workflow_container_executions(self, mock_event_bus):
        """获取工作流的容器执行记录"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        # 添加测试数据
        coordinator.container_executions["workflow_001"] = [
            {"container_id": "c1", "success": True},
            {"container_id": "c2", "success": False},
        ]

        executions = coordinator.get_workflow_container_executions("workflow_001")

        assert len(executions) == 2
        assert executions[0]["container_id"] == "c1"


# ==================== 测试4：容器日志收集 ====================


class TestContainerLogCollection:
    """测试容器日志收集"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    def test_coordinator_has_container_logs_storage(self, mock_event_bus):
        """Coordinator 有容器日志存储"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        assert hasattr(coordinator, "container_logs")
        assert isinstance(coordinator.container_logs, dict)

    @pytest.mark.asyncio
    async def test_coordinator_records_container_log(self, mock_event_bus):
        """Coordinator 记录容器日志"""
        from src.domain.agents.container_events import ContainerLogEvent
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        event = ContainerLogEvent(
            container_id="container_001",
            node_id="node_001",
            log_level="INFO",
            message="Processing data",
            timestamp="2025-01-01T00:00:00",
        )

        await coordinator._handle_container_log(event)

        assert "container_001" in coordinator.container_logs
        logs = coordinator.container_logs["container_001"]
        assert len(logs) == 1
        assert logs[0]["message"] == "Processing data"

    def test_get_container_logs(self, mock_event_bus):
        """获取容器日志"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        coordinator.container_logs["container_001"] = [
            {"level": "INFO", "message": "Started"},
            {"level": "INFO", "message": "Completed"},
        ]

        logs = coordinator.get_container_logs("container_001")

        assert len(logs) == 2
        assert logs[0]["message"] == "Started"


# ==================== 测试5：容器执行统计 ====================


class TestContainerExecutionStatistics:
    """测试容器执行统计"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    def test_get_container_execution_statistics(self, mock_event_bus):
        """获取容器执行统计"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        # 添加测试数据
        coordinator.container_executions["wf1"] = [
            {"container_id": "c1", "success": True, "execution_time": 1.0},
            {"container_id": "c2", "success": True, "execution_time": 2.0},
        ]
        coordinator.container_executions["wf2"] = [
            {"container_id": "c3", "success": False, "execution_time": 0.5},
        ]

        stats = coordinator.get_container_execution_statistics()

        assert stats["total_executions"] == 3
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        assert stats["total_execution_time"] == 3.5


# ==================== 测试6：容器执行器与事件集成 ====================


class TestContainerExecutorEventIntegration:
    """测试容器执行器与事件集成"""

    @pytest.mark.asyncio
    async def test_mock_executor_publishes_events(self):
        """Mock 执行器可以发布事件"""
        from src.domain.agents.container_executor import (
            ContainerConfig,
            MockContainerExecutor,
        )

        event_bus = MagicMock()
        event_bus.publish = AsyncMock()

        executor = MockContainerExecutor()
        config = ContainerConfig(image="python:3.11")

        result = await executor.execute_with_events(
            code="print('test')",
            config=config,
            event_bus=event_bus,
            node_id="node_001",
            workflow_id="workflow_001",
        )

        assert result.success is True
        # 验证事件发布
        assert event_bus.publish.call_count >= 1


# 导出
__all__ = [
    "TestContainerExecutionEvents",
    "TestCoordinatorContainerSubscription",
    "TestContainerExecutionRecording",
    "TestContainerLogCollection",
    "TestContainerExecutionStatistics",
    "TestContainerExecutorEventIntegration",
]

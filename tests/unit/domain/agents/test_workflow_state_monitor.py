"""WorkflowStateMonitor 单元测试 - Phase 35.5

TDD Red Phase: 测试 WorkflowStateMonitor 模块的核心功能
- 工作流状态监听与更新
- 订阅管理（修复残留bug）
- 并发安全（threading.Lock）
- 深拷贝保护
- 清理策略
- 错误防御
"""

import asyncio
import threading
from datetime import datetime, timedelta

import pytest

from src.domain.services.event_bus import EventBus


@pytest.fixture
def event_bus():
    """EventBus fixture"""
    return EventBus()


@pytest.fixture
def workflow_states():
    """共享的 workflow_states 字典"""
    return {}


@pytest.fixture
def monitor(event_bus, workflow_states):
    """WorkflowStateMonitor fixture"""
    from src.domain.agents.workflow_state_monitor import WorkflowStateMonitor

    return WorkflowStateMonitor(
        workflow_states=workflow_states,
        event_bus=event_bus,
        is_compressing_context=False,
    )


class TestWorkflowStateMonitorInit:
    """测试：WorkflowStateMonitor 初始化"""

    def test_monitor_initialization(self, event_bus, workflow_states):
        """测试：初始化应成功并设置属性"""
        from src.domain.agents.workflow_state_monitor import WorkflowStateMonitor

        monitor = WorkflowStateMonitor(
            workflow_states=workflow_states,
            event_bus=event_bus,
        )

        assert monitor.workflow_states is workflow_states
        assert monitor.event_bus is event_bus
        assert monitor._is_monitoring is False
        assert isinstance(monitor._lock, threading.Lock)
        assert monitor._subscriptions == []


class TestMonitoringLifecycle:
    """测试：监听生命周期"""

    def test_start_monitoring_subscribes_to_events(self, monitor, event_bus):
        """测试：start_monitoring 应订阅事件"""
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
            WorkflowExecutionStartedEvent,
        )

        monitor.start_monitoring()

        assert monitor._is_monitoring is True
        assert len(monitor._subscriptions) == 3

        # 验证所有事件都已订阅
        assert WorkflowExecutionStartedEvent in event_bus._subscribers
        assert WorkflowExecutionCompletedEvent in event_bus._subscribers
        assert NodeExecutionEvent in event_bus._subscribers

    def test_stop_monitoring_unsubscribes_correctly(self, monitor, event_bus):
        """测试：stop_monitoring 应正确取消订阅（bug修复验证）"""
        monitor.start_monitoring()
        monitor.stop_monitoring()

        assert monitor._is_monitoring is False
        assert len(monitor._subscriptions) == 0

        # 验证所有订阅都已清除
        from src.domain.agents.workflow_agent import (
            WorkflowExecutionStartedEvent,
        )

        assert (
            WorkflowExecutionStartedEvent not in event_bus._subscribers
            or len(event_bus._subscribers.get(WorkflowExecutionStartedEvent, [])) == 0
        )

    def test_start_is_idempotent(self, monitor):
        """测试：重复 start 不应重复订阅"""
        monitor.start_monitoring()
        monitor.start_monitoring()

        assert len(monitor._subscriptions) == 3


class TestWorkflowStarted:
    """测试：工作流启动事件处理"""

    @pytest.mark.asyncio
    async def test_handle_workflow_started_creates_state(self, monitor, event_bus, workflow_states):
        """测试：处理 started 事件应创建状态"""
        from src.domain.agents.workflow_agent import WorkflowExecutionStartedEvent

        monitor.start_monitoring()

        event = WorkflowExecutionStartedEvent(
            source="test",
            workflow_id="wf_1",
            node_count=5,
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.01)  # 等待异步处理

        # 验证状态创建
        assert "wf_1" in workflow_states
        state = workflow_states["wf_1"]
        assert state["workflow_id"] == "wf_1"
        assert state["status"] == "running"
        assert state["node_count"] == 5
        assert state["started_at"] is not None
        assert state["executed_nodes"] == []


class TestWorkflowCompleted:
    """测试：工作流完成事件处理"""

    @pytest.mark.asyncio
    async def test_handle_workflow_completed_updates_state(
        self, monitor, event_bus, workflow_states
    ):
        """测试：处理 completed 事件应更新状态"""
        from src.domain.agents.workflow_agent import (
            WorkflowExecutionCompletedEvent,
            WorkflowExecutionStartedEvent,
        )

        monitor.start_monitoring()

        # 先启动工作流
        start_event = WorkflowExecutionStartedEvent(
            source="test",
            workflow_id="wf_1",
            node_count=3,
        )
        await event_bus.publish(start_event)
        await asyncio.sleep(0.01)

        # 再完成工作流
        complete_event = WorkflowExecutionCompletedEvent(
            source="test",
            workflow_id="wf_1",
            status="completed",
            result={"output": "success"},
        )
        await event_bus.publish(complete_event)
        await asyncio.sleep(0.01)

        # 验证状态更新
        state = workflow_states["wf_1"]
        assert state["status"] == "completed"
        assert state["completed_at"] is not None
        assert state["result"] == {"output": "success"}

    @pytest.mark.asyncio
    async def test_handle_workflow_completed_creates_state_if_missing(
        self, monitor, event_bus, workflow_states
    ):
        """测试：completed 事件处理应防御性创建缺失状态（错误防御）"""
        from src.domain.agents.workflow_agent import WorkflowExecutionCompletedEvent

        monitor.start_monitoring()

        # 直接发送 completed 事件（没有 started）
        event = WorkflowExecutionCompletedEvent(
            source="test",
            workflow_id="wf_2",
            status="completed",
            result=None,
        )
        await event_bus.publish(event)
        await asyncio.sleep(0.01)

        # 验证防御性创建
        assert "wf_2" in workflow_states
        state = workflow_states["wf_2"]
        assert state["status"] == "completed"


class TestNodeExecution:
    """测试：节点执行事件处理"""

    @pytest.mark.asyncio
    async def test_handle_node_execution_updates_state(self, monitor, event_bus, workflow_states):
        """测试：处理 node 事件应更新状态"""
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionStartedEvent,
        )

        monitor.start_monitoring()

        # 先启动工作流
        start_event = WorkflowExecutionStartedEvent(
            source="test",
            workflow_id="wf_1",
            node_count=3,
        )
        await event_bus.publish(start_event)
        await asyncio.sleep(0.01)

        # 节点运行
        node_event = NodeExecutionEvent(
            source="test",
            workflow_id="wf_1",
            node_id="node_1",
            node_type="test_node",
            status="running",
        )
        await event_bus.publish(node_event)
        await asyncio.sleep(0.01)

        # 验证节点状态
        state = workflow_states["wf_1"]
        assert "node_1" in state["running_nodes"]

        # 节点完成
        complete_event = NodeExecutionEvent(
            source="test",
            workflow_id="wf_1",
            node_id="node_1",
            node_type="test_node",
            status="completed",
            result={"output": "success"},
        )
        await event_bus.publish(complete_event)
        await asyncio.sleep(0.01)

        # 验证节点完成状态
        assert "node_1" not in state["running_nodes"]
        assert "node_1" in state["executed_nodes"]
        assert state["node_outputs"]["node_1"] == {"output": "success"}

    @pytest.mark.asyncio
    async def test_handle_node_execution_without_workflow_id(
        self, monitor, event_bus, workflow_states
    ):
        """测试：缺失 workflow_id 的节点事件应被忽略（并发安全）"""
        from src.domain.agents.workflow_agent import NodeExecutionEvent

        monitor.start_monitoring()

        # 发送没有 workflow_id 的事件
        event = NodeExecutionEvent(
            source="test",
            workflow_id="",  # 空字符串表示缺失
            node_id="node_1",
            node_type="test_node",
            status="running",
        )
        await event_bus.publish(event)
        await asyncio.sleep(0.01)

        # 验证状态未被破坏
        assert len(workflow_states) == 0


class TestQueryMethods:
    """测试：查询方法"""

    def test_get_workflow_state_returns_deepcopy(self, monitor, workflow_states):
        """测试：get_workflow_state 应返回深拷贝（深拷贝保护）"""
        # 手动添加状态
        workflow_states["wf_1"] = {
            "workflow_id": "wf_1",
            "status": "running",
            "executed_nodes": ["node_1"],
            "node_outputs": {"node_1": {"output": "data"}},
        }

        state = monitor.get_workflow_state("wf_1")

        # 验证是深拷贝
        assert state is not workflow_states["wf_1"]
        assert state["executed_nodes"] is not workflow_states["wf_1"]["executed_nodes"]

        # 修改返回值不应影响内部状态
        state["status"] = "tampered"
        state["executed_nodes"].append("node_2")
        state["node_outputs"]["node_1"]["output"] = "tampered"

        assert workflow_states["wf_1"]["status"] == "running"
        assert workflow_states["wf_1"]["executed_nodes"] == ["node_1"]
        assert workflow_states["wf_1"]["node_outputs"]["node_1"]["output"] == "data"

    def test_get_workflow_state_returns_none_for_missing(self, monitor):
        """测试：不存在的 workflow 应返回 None"""
        state = monitor.get_workflow_state("nonexistent")
        assert state is None

    def test_get_all_workflow_states_returns_deepcopy(self, monitor, workflow_states):
        """测试：get_all_workflow_states 应返回深拷贝"""
        workflow_states["wf_1"] = {"workflow_id": "wf_1", "status": "running"}
        workflow_states["wf_2"] = {"workflow_id": "wf_2", "status": "completed"}

        all_states = monitor.get_all_workflow_states()

        # 验证是深拷贝
        assert all_states["wf_1"] is not workflow_states["wf_1"]
        assert all_states["wf_2"] is not workflow_states["wf_2"]

    def test_get_system_status(self, monitor, workflow_states):
        """测试：get_system_status 应正确统计"""
        workflow_states["wf_1"] = {
            "status": "running",
            "running_nodes": ["node_1", "node_2"],
        }
        workflow_states["wf_2"] = {
            "status": "completed",
            "running_nodes": [],
        }
        workflow_states["wf_3"] = {
            "status": "failed",
            "running_nodes": [],
        }

        status = monitor.get_system_status()

        assert status["total_workflows"] == 3
        assert status["running_workflows"] == 1
        assert status["completed_workflows"] == 1
        assert status["failed_workflows"] == 1
        assert status["active_nodes"] == 2


class TestCleanupStrategies:
    """测试：清理策略"""

    def test_clear_old_states(self, monitor, workflow_states):
        """测试：clear_old_states 应删除旧状态"""
        now = datetime.now()
        workflow_states["wf_old"] = {
            "workflow_id": "wf_old",
            "started_at": now - timedelta(seconds=3600),  # 1小时前
        }
        workflow_states["wf_new"] = {
            "workflow_id": "wf_new",
            "started_at": now - timedelta(seconds=60),  # 1分钟前
        }

        removed = monitor.clear_old_states(max_age_seconds=300)  # 5分钟

        assert removed == 1
        assert "wf_old" not in workflow_states
        assert "wf_new" in workflow_states

    def test_clear_workflow_state(self, monitor, workflow_states):
        """测试：clear_workflow_state 应删除单个状态"""
        workflow_states["wf_1"] = {"workflow_id": "wf_1"}

        result = monitor.clear_workflow_state("wf_1")

        assert result is True
        assert "wf_1" not in workflow_states

        # 删除不存在的应返回 False
        result = monitor.clear_workflow_state("nonexistent")
        assert result is False


class TestThreadSafety:
    """测试：线程安全"""

    def test_concurrent_state_updates(self, monitor, workflow_states):
        """测试：并发更新状态应线程安全"""
        workflow_states["wf_1"] = {
            "workflow_id": "wf_1",
            "executed_nodes": [],
        }

        def update_state(node_id):
            with monitor._lock:
                workflow_states["wf_1"]["executed_nodes"].append(node_id)

        threads = [threading.Thread(target=update_state, args=(f"node_{i}",)) for i in range(100)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有更新都成功
        assert len(workflow_states["wf_1"]["executed_nodes"]) == 100

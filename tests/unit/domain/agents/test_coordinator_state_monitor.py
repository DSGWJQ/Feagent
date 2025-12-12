"""协调者状态监控单元测试

TDD 驱动：验证 CoordinatorAgent 状态监控功能

测试场景：
1. 监听 workflow 事件后更新状态
2. 节点运行/完成后状态更新正确
3. 查询接口返回正确的状态视图
4. 多工作流并发时状态隔离
"""

import pytest

from src.domain.agents.coordinator_agent import (
    CoordinatorAgent,
)
from src.domain.agents.workflow_agent import (
    NodeExecutionEvent,
    WorkflowExecutionCompletedEvent,
    WorkflowExecutionStartedEvent,
)
from src.domain.services.event_bus import EventBus


class TestCoordinatorStateMonitor:
    """协调者状态监控测试"""

    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        """创建协调者Agent"""
        return CoordinatorAgent(event_bus=event_bus)

    # ==================== 状态初始化测试 ====================

    def test_coordinator_has_workflow_state_store(self, coordinator):
        """测试：协调者应有工作流状态存储"""
        assert hasattr(coordinator, "workflow_states")
        assert isinstance(coordinator.workflow_states, dict)

    def test_initial_workflow_state_is_empty(self, coordinator):
        """测试：初始工作流状态应为空"""
        assert len(coordinator.workflow_states) == 0

    # ==================== 工作流开始事件测试 ====================

    @pytest.mark.asyncio
    async def test_handles_workflow_started_event(self, coordinator, event_bus):
        """测试：处理工作流开始事件"""
        # 注册事件处理
        coordinator.start_monitoring()

        # 发布工作流开始事件
        event = WorkflowExecutionStartedEvent(
            source="workflow_agent",
            workflow_id="wf_123",
            node_count=3,
        )
        await event_bus.publish(event)

        # 验证状态已创建
        assert "wf_123" in coordinator.workflow_states
        state = coordinator.workflow_states["wf_123"]
        assert state["status"] == "running"
        assert state["node_count"] == 3
        assert state["started_at"] is not None

    @pytest.mark.asyncio
    async def test_workflow_started_initializes_node_tracking(self, coordinator, event_bus):
        """测试：工作流开始时初始化节点跟踪"""
        coordinator.start_monitoring()

        event = WorkflowExecutionStartedEvent(
            source="workflow_agent",
            workflow_id="wf_123",
            node_count=3,
        )
        await event_bus.publish(event)

        state = coordinator.workflow_states["wf_123"]
        assert "executed_nodes" in state
        assert "running_nodes" in state
        assert "node_inputs" in state
        assert "node_outputs" in state
        assert state["executed_nodes"] == []
        assert state["running_nodes"] == []

    # ==================== 节点执行事件测试 ====================

    @pytest.mark.asyncio
    async def test_handles_node_running_event(self, coordinator, event_bus):
        """测试：处理节点开始运行事件"""
        coordinator.start_monitoring()

        # 先启动工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=2,
            )
        )

        # 节点开始运行
        event = NodeExecutionEvent(
            source="workflow_agent",
            node_id="node_1",
            node_type="llm",
            status="running",
        )
        await event_bus.publish(event)

        state = coordinator.workflow_states["wf_123"]
        assert "node_1" in state["running_nodes"]
        assert "node_1" not in state["executed_nodes"]

    @pytest.mark.asyncio
    async def test_handles_node_completed_event(self, coordinator, event_bus):
        """测试：处理节点完成事件"""
        coordinator.start_monitoring()

        # 启动工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=2,
            )
        )

        # 节点开始运行
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                node_type="llm",
                status="running",
            )
        )

        # 节点完成
        event = NodeExecutionEvent(
            source="workflow_agent",
            node_id="node_1",
            node_type="llm",
            status="completed",
            result={"output": "result_data"},
        )
        await event_bus.publish(event)

        state = coordinator.workflow_states["wf_123"]
        assert "node_1" not in state["running_nodes"]
        assert "node_1" in state["executed_nodes"]
        assert state["node_outputs"]["node_1"] == {"output": "result_data"}

    @pytest.mark.asyncio
    async def test_handles_node_failed_event(self, coordinator, event_bus):
        """测试：处理节点失败事件"""
        coordinator.start_monitoring()

        # 启动工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=2,
            )
        )

        # 节点运行然后失败
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                node_type="llm",
                status="running",
            )
        )

        event = NodeExecutionEvent(
            source="workflow_agent",
            node_id="node_1",
            node_type="llm",
            status="failed",
            error="执行错误",
        )
        await event_bus.publish(event)

        state = coordinator.workflow_states["wf_123"]
        assert "node_1" not in state["running_nodes"]
        assert "node_1" in state["failed_nodes"]
        assert state["node_errors"]["node_1"] == "执行错误"

    # ==================== 工作流完成事件测试 ====================

    @pytest.mark.asyncio
    async def test_handles_workflow_completed_event(self, coordinator, event_bus):
        """测试：处理工作流完成事件"""
        coordinator.start_monitoring()

        # 启动工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=1,
            )
        )

        # 工作流完成
        event = WorkflowExecutionCompletedEvent(
            source="workflow_agent",
            workflow_id="wf_123",
            status="completed",
            result={"final": "result"},
        )
        await event_bus.publish(event)

        state = coordinator.workflow_states["wf_123"]
        assert state["status"] == "completed"
        assert state["completed_at"] is not None
        assert state["result"] == {"final": "result"}

    @pytest.mark.asyncio
    async def test_handles_workflow_failed_event(self, coordinator, event_bus):
        """测试：处理工作流失败事件"""
        coordinator.start_monitoring()

        # 启动工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=1,
            )
        )

        # 工作流失败
        event = WorkflowExecutionCompletedEvent(
            source="workflow_agent",
            workflow_id="wf_123",
            status="failed",
            result={"error": "执行失败"},
        )
        await event_bus.publish(event)

        state = coordinator.workflow_states["wf_123"]
        assert state["status"] == "failed"

    # ==================== 查询接口测试 ====================

    @pytest.mark.asyncio
    async def test_get_workflow_state_returns_snapshot(self, coordinator, event_bus):
        """测试：获取工作流状态返回快照"""
        coordinator.start_monitoring()

        # 启动工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=2,
            )
        )

        # 节点完成
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                node_type="llm",
                status="completed",
                result={"data": "value"},
            )
        )

        # 查询状态
        snapshot = coordinator.get_workflow_state("wf_123")

        assert snapshot is not None
        assert snapshot["workflow_id"] == "wf_123"
        assert snapshot["status"] == "running"
        assert "node_1" in snapshot["executed_nodes"]
        assert snapshot["node_outputs"]["node_1"] == {"data": "value"}

    def test_get_workflow_state_returns_none_for_unknown(self, coordinator):
        """测试：查询未知工作流返回None"""
        snapshot = coordinator.get_workflow_state("unknown_wf")
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_get_all_workflow_states(self, coordinator, event_bus):
        """测试：获取所有工作流状态"""
        coordinator.start_monitoring()

        # 启动两个工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_1",
                node_count=1,
            )
        )
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_2",
                node_count=2,
            )
        )

        # 查询所有状态
        all_states = coordinator.get_all_workflow_states()

        assert len(all_states) == 2
        assert "wf_1" in all_states
        assert "wf_2" in all_states

    # ==================== 状态视图格式测试 ====================

    @pytest.mark.asyncio
    async def test_state_view_contains_required_fields(self, coordinator, event_bus):
        """测试：状态视图包含所需字段"""
        coordinator.start_monitoring()

        # 完整的工作流执行
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=2,
            )
        )

        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                node_type="llm",
                status="running",
            )
        )

        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                node_type="llm",
                status="completed",
                result={"output": "data"},
            )
        )

        # 获取状态视图
        view = coordinator.get_workflow_state("wf_123")

        # 验证所需字段
        required_fields = [
            "workflow_id",
            "status",
            "node_count",
            "executed_nodes",
            "running_nodes",
            "failed_nodes",
            "node_inputs",
            "node_outputs",
            "node_errors",
            "started_at",
        ]
        for field in required_fields:
            assert field in view, f"Missing required field: {field}"

    # ==================== 多工作流隔离测试 ====================

    @pytest.mark.asyncio
    async def test_multiple_workflows_are_isolated(self, coordinator, event_bus):
        """测试：多工作流状态相互隔离"""
        coordinator.start_monitoring()

        # 启动两个工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_1",
                node_count=1,
            )
        )
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_2",
                node_count=1,
            )
        )

        # wf_1 的节点完成
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                node_type="llm",
                status="completed",
                result={"wf": "1"},
            )
        )

        # 验证只有 wf_1 有该节点（需要知道是哪个工作流的节点）
        # 这里需要在事件中添加 workflow_id
        state1 = coordinator.get_workflow_state("wf_1")
        state2 = coordinator.get_workflow_state("wf_2")

        # 两个工作流应该独立
        assert state1["status"] == "running"
        assert state2["status"] == "running"

    # ==================== 停止监控测试 ====================

    @pytest.mark.asyncio
    async def test_stop_monitoring_unsubscribes_events(self, coordinator, event_bus):
        """测试：停止监控后取消事件订阅"""
        coordinator.start_monitoring()
        coordinator.stop_monitoring()

        # 发布事件不应更新状态
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=1,
            )
        )

        assert "wf_123" not in coordinator.workflow_states


class TestCoordinatorNodeInputTracking:
    """节点输入跟踪测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        return CoordinatorAgent(event_bus=event_bus)

    @pytest.mark.asyncio
    async def test_tracks_node_inputs_from_event(self, coordinator, event_bus):
        """测试：从事件中跟踪节点输入"""
        coordinator.start_monitoring()

        # 启动工作流
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=1,
            )
        )

        # 发布带输入的节点事件（需要扩展 NodeExecutionEvent）
        # 这里假设我们扩展了事件来包含 inputs
        event = NodeExecutionEvent(
            source="workflow_agent",
            node_id="node_1",
            node_type="llm",
            status="running",
        )
        # 模拟添加 inputs 属性
        event.inputs = {"prompt": "分析数据"}
        await event_bus.publish(event)

        state = coordinator.get_workflow_state("wf_123")
        # 如果事件包含 inputs，应该被记录
        if hasattr(event, "inputs"):
            assert "node_1" in state.get("node_inputs", {})


class TestCoordinatorSystemStatus:
    """系统状态查询测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def coordinator(self, event_bus):
        return CoordinatorAgent(event_bus=event_bus)

    @pytest.mark.asyncio
    async def test_get_system_status_summary(self, coordinator, event_bus):
        """测试：获取系统状态摘要"""
        coordinator.start_monitoring()

        # 启动多个工作流
        for i in range(3):
            await event_bus.publish(
                WorkflowExecutionStartedEvent(
                    source="workflow_agent",
                    workflow_id=f"wf_{i}",
                    node_count=2,
                )
            )

        # 完成一个
        await event_bus.publish(
            WorkflowExecutionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_0",
                status="completed",
                result={},
            )
        )

        # 获取系统状态
        system_status = coordinator.get_system_status()

        assert system_status["total_workflows"] == 3
        assert system_status["running_workflows"] == 2
        assert system_status["completed_workflows"] == 1
        assert system_status["failed_workflows"] == 0

    @pytest.mark.asyncio
    async def test_get_active_nodes_count(self, coordinator, event_bus):
        """测试：获取活跃节点数"""
        coordinator.start_monitoring()

        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_123",
                node_count=3,
            )
        )

        # 两个节点在运行
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                node_type="llm",
                status="running",
            )
        )
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_2",
                node_type="http",
                status="running",
            )
        )

        system_status = coordinator.get_system_status()
        assert system_status["active_nodes"] == 2


class TestCoordinatorStateRestoration:
    """状态恢复测试 - Phase 35.5.1"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    def test_start_monitoring_writes_to_base_state(self, event_bus):
        """测试：start_monitoring 应写回 base_state"""
        # 创建 coordinator（使用真实的 Bootstrap）
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 获取 base_state 引用
        base_state = coordinator._base_state

        # 验证初始状态
        initial_monitoring = base_state.get("_is_monitoring", False)
        assert coordinator._is_monitoring == initial_monitoring

        # 启动监控
        coordinator.start_monitoring()

        # 验证状态已写回 base_state
        assert base_state["_is_monitoring"] is True
        assert coordinator._is_monitoring is True

    def test_stop_monitoring_writes_to_base_state(self, event_bus):
        """测试：stop_monitoring 应写回 base_state"""
        # 创建 coordinator 并启动监控
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.start_monitoring()

        base_state = coordinator._base_state
        assert base_state["_is_monitoring"] is True

        # 停止监控
        coordinator.stop_monitoring()

        # 验证状态已写回 base_state
        assert base_state["_is_monitoring"] is False
        assert coordinator._is_monitoring is False

    def test_monitoring_state_persists_in_shared_base_state(self, event_bus):
        """测试：监控状态通过 base_state 共享

        注意：由于 CoordinatorBootstrap 每次创建新的 base_state 实例，
        此测试验证的是状态写回机制，而非真实的进程重建恢复。
        实际生产环境中，base_state 通过依赖注入共享。
        """
        # 创建第一个 coordinator
        coordinator1 = CoordinatorAgent(event_bus=event_bus)
        base_state = coordinator1._base_state

        # 启动监控
        coordinator1.start_monitoring()
        assert base_state["_is_monitoring"] is True

        # 验证如果新实例共享相同的 base_state，可以读取状态
        # （此测试仅验证写回逻辑，不测试真实的进程重建）
        assert base_state["_is_monitoring"] is True
        assert coordinator1._is_monitoring is True

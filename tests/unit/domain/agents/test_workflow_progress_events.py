"""测试：WorkflowAgent 执行进度事件 - Phase 8.4 TDD Red 阶段

测试目标：
1. WorkflowAgent 在节点执行过程中发布 ExecutionProgressEvent
2. 进度事件包含完整的执行信息（节点ID、状态、进度百分比）
3. 进度事件通过 EventBus 正确发布
4. 支持不同的进度阶段（started/running/completed/failed）

完成标准：
- 所有测试初始失败（Red阶段）
- 实现代码后所有测试通过（Green阶段）
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestExecutionProgressEventStructure:
    """测试 ExecutionProgressEvent 数据结构"""

    def test_execution_progress_event_should_have_required_fields(self):
        """ExecutionProgressEvent 应包含必填字段

        场景：定义进度事件的数据结构
        期望：事件包含 workflow_id, node_id, status, progress 等字段
        """
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="node_1",
            status="running",
            progress=0.5,
            message="正在执行节点...",
        )

        assert event.workflow_id == "workflow_001"
        assert event.node_id == "node_1"
        assert event.status == "running"
        assert event.progress == 0.5
        assert event.message == "正在执行节点..."

    def test_execution_progress_event_should_support_optional_metadata(self):
        """ExecutionProgressEvent 应支持可选的元数据

        场景：进度事件包含额外的执行信息
        期望：支持 metadata 字段
        """
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="node_1",
            status="running",
            progress=0.5,
            message="处理中",
            metadata={"attempt": 1, "elapsed_time": 2.5},
        )

        assert event.metadata is not None
        assert event.metadata["attempt"] == 1
        assert event.metadata["elapsed_time"] == 2.5


class TestProgressEventEmissionDuringExecution:
    """测试执行过程中的进度事件发布"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.fixture
    def mock_node_executor(self):
        """创建 Mock NodeExecutor"""
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "success"})
        return executor

    @pytest.mark.asyncio
    async def test_emit_progress_event_when_node_starts(self, mock_event_bus, mock_node_executor):
        """节点开始执行时应发布进度事件

        场景：WorkflowAgent 开始执行某个节点
        期望：发布 status="started", progress=0 的事件
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        # 创建完整的上下文链
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        context = WorkflowContext(workflow_id="workflow_001", session_context=session_ctx)
        agent = WorkflowAgent(
            workflow_context=context,
            node_executor=mock_node_executor,
            event_bus=mock_event_bus,
        )

        # 添加测试节点
        agent.add_node("node_1", "api", config={"url": "http://example.com"})

        # 执行节点
        await agent.execute_node_with_progress("node_1")

        # 验证发布了 started 事件
        calls = mock_event_bus.publish.call_args_list
        started_event = None
        for call in calls:
            event = call[0][0]
            if hasattr(event, "status") and event.status == "started":
                started_event = event
                break

        assert started_event is not None
        assert started_event.node_id == "node_1"
        assert started_event.progress == 0.0

    @pytest.mark.asyncio
    async def test_emit_progress_event_when_node_completes(
        self, mock_event_bus, mock_node_executor
    ):
        """节点完成执行时应发布进度事件

        场景：WorkflowAgent 完成节点执行
        期望：发布 status="completed", progress=1.0 的事件
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        # 创建完整的上下文链
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        context = WorkflowContext(workflow_id="workflow_001", session_context=session_ctx)
        agent = WorkflowAgent(
            workflow_context=context,
            node_executor=mock_node_executor,
            event_bus=mock_event_bus,
        )

        agent.add_node("node_1", "api", config={"url": "http://example.com"})

        await agent.execute_node_with_progress("node_1")

        # 验证发布了 completed 事件
        calls = mock_event_bus.publish.call_args_list
        completed_event = None
        for call in calls:
            event = call[0][0]
            if hasattr(event, "status") and event.status == "completed":
                completed_event = event
                break

        assert completed_event is not None
        assert completed_event.node_id == "node_1"
        assert completed_event.progress == 1.0

    @pytest.mark.asyncio
    async def test_emit_progress_event_when_node_fails(self, mock_event_bus):
        """节点执行失败时应发布进度事件

        场景：节点执行过程中抛出异常
        期望：发布 status="failed" 的事件
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        # 创建会失败的 executor
        failing_executor = MagicMock()
        failing_executor.execute = AsyncMock(side_effect=Exception("执行失败"))

        # 创建完整的上下文链
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        context = WorkflowContext(workflow_id="workflow_001", session_context=session_ctx)
        agent = WorkflowAgent(
            workflow_context=context,
            node_executor=failing_executor,
            event_bus=mock_event_bus,
        )

        agent.add_node("node_1", "api", config={"url": "http://example.com"})

        # 执行节点（预期失败）
        with pytest.raises(Exception, match="执行失败"):
            await agent.execute_node_with_progress("node_1")

        # 验证发布了 failed 事件
        calls = mock_event_bus.publish.call_args_list
        failed_event = None
        for call in calls:
            event = call[0][0]
            if hasattr(event, "status") and event.status == "failed":
                failed_event = event
                break

        assert failed_event is not None
        assert failed_event.node_id == "node_1"
        assert "失败" in failed_event.message or "failed" in failed_event.message.lower()


class TestWorkflowProgressTracking:
    """测试工作流整体进度跟踪"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.fixture
    def mock_node_executor(self):
        """创建 Mock NodeExecutor"""
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "success"})
        return executor

    @pytest.mark.asyncio
    async def test_emit_workflow_progress_for_multiple_nodes(
        self, mock_event_bus, mock_node_executor
    ):
        """执行多个节点时应发布工作流级别的进度

        场景：工作流包含 3 个节点，依次执行
        期望：发布工作流进度事件，progress 从 0 → 0.33 → 0.66 → 1.0
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        # 创建完整的上下文链
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        context = WorkflowContext(workflow_id="workflow_001", session_context=session_ctx)
        agent = WorkflowAgent(
            workflow_context=context,
            node_executor=mock_node_executor,
            event_bus=mock_event_bus,
        )

        # 添加 3 个节点
        agent.add_node("node_1", "api", config={})
        agent.add_node("node_2", "llm", config={})
        agent.add_node("node_3", "code", config={})

        # 连接节点
        agent.connect_nodes("node_1", "node_2")
        agent.connect_nodes("node_2", "node_3")

        # 执行工作流
        await agent.execute_workflow_with_progress()

        # 验证发布了多个进度事件
        calls = mock_event_bus.publish.call_args_list
        progress_events = [
            call[0][0]
            for call in calls
            if hasattr(call[0][0], "workflow_id") and hasattr(call[0][0], "progress")
        ]

        # 至少应该有 3 个节点的进度事件
        assert len(progress_events) >= 3

    @pytest.mark.asyncio
    async def test_calculate_overall_progress_correctly(self, mock_event_bus, mock_node_executor):
        """正确计算工作流整体进度

        场景：工作流执行到第 2 个节点（共 4 个）
        期望：整体进度 = 2/4 = 0.5
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        # 创建完整的上下文链
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        context = WorkflowContext(workflow_id="workflow_001", session_context=session_ctx)
        agent = WorkflowAgent(
            workflow_context=context,
            node_executor=mock_node_executor,
            event_bus=mock_event_bus,
        )

        # 添加 4 个节点
        for i in range(1, 5):
            agent.add_node(f"node_{i}", "api", config={})

        # 执行前 2 个节点
        await agent.execute_node_with_progress("node_1")
        await agent.execute_node_with_progress("node_2")

        # 获取当前进度
        progress = agent.get_workflow_progress()

        assert progress == pytest.approx(0.5, rel=0.01)


class TestProgressEventBusIntegration:
    """测试进度事件与 EventBus 的集成"""

    @pytest.mark.asyncio
    async def test_progress_events_are_published_to_event_bus(self):
        """进度事件应正确发布到 EventBus

        场景：WorkflowAgent 执行节点并发布进度事件
        期望：EventBus 收到 ExecutionProgressEvent
        """
        from src.domain.agents.workflow_agent import (
            ExecutionProgressEvent,
            WorkflowAgent,
        )
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        received_events = []

        # 订阅进度事件
        async def handler(event: ExecutionProgressEvent):
            received_events.append(event)

        event_bus.subscribe(ExecutionProgressEvent, handler)

        # 创建 WorkflowAgent
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"result": "ok"})

        # 创建完整的上下文链
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        context = WorkflowContext(workflow_id="workflow_001", session_context=session_ctx)
        agent = WorkflowAgent(
            workflow_context=context,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        agent.add_node("node_1", "api", config={})

        # 执行节点
        await agent.execute_node_with_progress("node_1")

        # 验证收到进度事件
        assert len(received_events) > 0
        assert isinstance(received_events[0], ExecutionProgressEvent)

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_progress_events(self):
        """多个订阅者应都能收到进度事件

        场景：有 2 个订阅者监听进度事件
        期望：两个订阅者都收到事件
        """
        from src.domain.agents.workflow_agent import (
            ExecutionProgressEvent,
            WorkflowAgent,
        )
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        subscriber1_events = []
        subscriber2_events = []

        async def handler1(event: ExecutionProgressEvent):
            subscriber1_events.append(event)

        async def handler2(event: ExecutionProgressEvent):
            subscriber2_events.append(event)

        event_bus.subscribe(ExecutionProgressEvent, handler1)
        event_bus.subscribe(ExecutionProgressEvent, handler2)

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"result": "ok"})

        # 创建完整的上下文链
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        context = WorkflowContext(workflow_id="workflow_001", session_context=session_ctx)
        agent = WorkflowAgent(
            workflow_context=context,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        agent.add_node("node_1", "api", config={})
        await agent.execute_node_with_progress("node_1")

        # 两个订阅者都应收到事件
        assert len(subscriber1_events) > 0
        assert len(subscriber2_events) > 0


# =============================================================================
# Gap-Filling Tests: get_progress_summary() Edge Cases (Lines 2273-2288)
# =============================================================================


class TestProgressSummaryEdgeCases:
    """测试get_progress_summary()的边界情况"""

    @pytest.mark.asyncio
    async def test_progress_summary_with_total_nodes_zero(self):
        """测试_total_nodes为0时的进度摘要计算

        目标行：workflow_agent.py line 2280
        逻辑：total = self._total_nodes if self._total_nodes > 0 else len(self._nodes)
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        # 创建agent
        ctx = WorkflowContext(
            workflow_id="test_wf",
            session_context=SessionContext(
                session_id="test_session",
                global_context=GlobalContext(user_id="test_user"),
            ),
        )
        factory = NodeFactory(NodeRegistry())
        agent = WorkflowAgent(workflow_context=ctx, node_factory=factory)

        # 添加5个节点
        for i in range(5):
            node = factory.create(NodeType.GENERIC, {"name": f"node_{i}"})
            agent.add_node(node)

        # 验证：_total_nodes默认为0
        assert agent._total_nodes == 0

        # 获取进度摘要
        summary = agent.get_progress_summary()

        # 验证：total_nodes应该等于len(self._nodes)=5
        assert summary["total_nodes"] == 5
        assert summary["completed_nodes"] == 0
        assert summary["progress"] == 0.0

    @pytest.mark.asyncio
    async def test_progress_summary_metadata_structure(self):
        """测试进度摘要的元数据结构正确性

        目标行：workflow_agent.py lines 2282-2288
        验证返回字典的所有必需键
        """
        from src.domain.agents.workflow_agent import ExecutionStatus, WorkflowAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        # 创建agent
        ctx = WorkflowContext(
            workflow_id="test_wf",
            session_context=SessionContext(
                session_id="test_session",
                global_context=GlobalContext(user_id="test_user"),
            ),
        )
        factory = NodeFactory(NodeRegistry())

        from unittest.mock import AsyncMock, MagicMock
        node_executor = MagicMock()
        node_executor.execute = AsyncMock(return_value={"done": True})

        agent = WorkflowAgent(
            workflow_context=ctx,
            node_factory=factory,
            node_executor=node_executor
        )

        # 添加5个节点
        nodes = []
        for i in range(5):
            node = factory.create(NodeType.GENERIC, {"name": f"node_{i}"})
            agent.add_node(node)
            nodes.append(node)

        # 执行3个节点（使用execute_node_with_progress以填充_executed_nodes）
        for node in nodes[:3]:
            await agent.execute_node_with_progress(node.id)

        # 设置执行状态
        agent._execution_status = ExecutionStatus.RUNNING

        # 获取进度摘要
        summary = agent.get_progress_summary()

        # 验证：包含所有必需字段
        assert "total_nodes" in summary
        assert "completed_nodes" in summary
        assert "progress" in summary
        assert "status" in summary
        assert "executed_nodes" in summary

        # 验证：值正确
        assert summary["total_nodes"] == 5
        assert summary["completed_nodes"] == 3
        assert summary["progress"] == 0.6  # 3/5 = 0.6 (小数格式，非百分比)
        assert summary["status"] == ExecutionStatus.RUNNING.value
        assert len(summary["executed_nodes"]) == 3


# 导出
__all__ = [
    "TestExecutionProgressEventStructure",
    "TestProgressEventEmissionDuringExecution",
    "TestWorkflowProgressTracking",
    "TestProgressEventBusIntegration",
    "TestProgressSummaryEdgeCases",
]

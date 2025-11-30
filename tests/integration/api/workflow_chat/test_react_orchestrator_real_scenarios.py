"""集成测试：ReAct 编排器 - 真实场景验证

TDD REFACTOR 阶段：在真实工作流场景下验证 ReAct 编排

真实场景：
1. 简单线性工作流：单节点执行
2. 多节点顺序工作流：多个节点依次执行
3. 事件流验证：确保所有事件正确发出
4. 循环完成和状态保存
"""

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.lc.workflow.react_orchestrator import ReActOrchestrator


class TestReActOrchestratorRealScenarios:
    """测试：真实 ReAct 编排场景"""

    def test_single_node_workflow_execution(self):
        """集成：单节点工作流执行"""
        # 创建单节点工作流
        node = Node.create(
            type=NodeType.HTTP,
            name="fetch_data",
            config={"url": "https://example.com"},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="single_node",
            description="single node workflow",
            nodes=[node],
            edges=[],
        )

        # 创建编排器
        orchestrator = ReActOrchestrator(max_iterations=10)

        # 运行工作流
        state = orchestrator.run(workflow)

        # 验证
        assert state is not None
        assert state.workflow_id == workflow.id
        assert state.workflow_name == "single_node"
        assert len(state.available_nodes) == 1

    def test_multi_node_workflow_execution(self):
        """集成：多节点工作流执行"""
        # 创建多个节点
        node_a = Node.create(
            type=NodeType.HTTP,
            name="fetch",
            config={},
            position=Position(0, 0),
        )

        node_b = Node.create(
            type=NodeType.TRANSFORM,
            name="process",
            config={},
            position=Position(100, 0),
        )

        node_c = Node.create(
            type=NodeType.HTTP,
            name="save",
            config={},
            position=Position(200, 0),
        )

        workflow = Workflow.create(
            name="multi_node",
            description="multi node workflow",
            nodes=[node_a, node_b, node_c],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=10)
        state = orchestrator.run(workflow)

        assert state is not None
        assert len(state.available_nodes) == 3
        assert state.available_nodes == [node_a.id, node_b.id, node_c.id]

    def test_event_emission_during_execution(self):
        """集成：执行过程中事件正确发出"""
        node = Node.create(
            type=NodeType.HTTP,
            name="test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="event_test",
            description="test event emission",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator()

        # 记录所有事件
        events = []

        def event_callback(event):
            events.append(event)

        orchestrator.on_event(event_callback)

        # 运行工作流
        orchestrator.run(workflow)

        # 验证事件
        assert len(events) > 0
        event_types = [e.event_type for e in events]
        assert "workflow_started" in event_types

    def test_final_state_accessibility(self):
        """集成：最终状态可访问"""
        node = Node.create(
            type=NodeType.HTTP,
            name="test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="final_state",
            description="test final state",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator()
        state = orchestrator.run(workflow)

        # 通过 get_final_state 获取状态
        final_state = orchestrator.get_final_state()

        assert final_state is not None
        assert final_state == state
        assert final_state.workflow_name == "final_state"

    def test_workflow_state_includes_messages(self):
        """集成：工作流状态包含消息历史"""
        node = Node.create(
            type=NodeType.HTTP,
            name="test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="messages_test",
            description="test message history",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator()
        state = orchestrator.run(workflow)

        # 验证消息
        assert len(state.messages) > 0
        assert any("开始执行" in str(m.content) for m in state.messages)

    def test_iteration_tracking(self):
        """集成：迭代计数正确追踪"""
        node = Node.create(
            type=NodeType.HTTP,
            name="test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="iteration_test",
            description="test iteration tracking",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=5)
        state = orchestrator.run(workflow)

        # 迭代计数应该被追踪
        assert state.iteration_count >= 0

    def test_max_iterations_limit(self):
        """集成：最大迭代数限制"""
        node = Node.create(
            type=NodeType.HTTP,
            name="test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="max_iter_test",
            description="test max iterations",
            nodes=[node],
            edges=[],
        )

        # 设置较小的最大迭代数
        orchestrator = ReActOrchestrator(max_iterations=3)
        state = orchestrator.run(workflow)

        # 迭代数应该不超过最大值
        assert state.iteration_count <= 3

    def test_multiple_workflows_independence(self):
        """集成：不同工作流的独立执行"""
        # 工作流 1
        node1 = Node.create(
            type=NodeType.HTTP,
            name="wf1_node",
            config={},
            position=Position(0, 0),
        )

        wf1 = Workflow.create(
            name="workflow_1",
            description="first workflow",
            nodes=[node1],
            edges=[],
        )

        # 工作流 2
        node2 = Node.create(
            type=NodeType.HTTP,
            name="wf2_node",
            config={},
            position=Position(0, 0),
        )

        wf2 = Workflow.create(
            name="workflow_2",
            description="second workflow",
            nodes=[node2],
            edges=[],
        )

        # 分别执行
        orch1 = ReActOrchestrator()
        orch2 = ReActOrchestrator()

        state1 = orch1.run(wf1)
        state2 = orch2.run(wf2)

        # 验证独立性
        assert state1.workflow_name == "workflow_1"
        assert state2.workflow_name == "workflow_2"
        assert state1.workflow_id != state2.workflow_id

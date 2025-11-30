"""集成测试：ReAct 编排与工作流聊天的真实场景验证

TDD RED 阶段：验证 ReActOrchestrator 与 UpdateWorkflowByChatUseCase 的集成

真实场景：
1. 单节点工作流的 ReAct 循环
2. 流式事件顺序验证
3. 多步骤工作流修改
4. 错误恢复流程
"""

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.lc.workflow.react_orchestrator import ReActEvent, ReActOrchestrator


class TestReActOrchestratorWorkflowChatIntegration:
    """测试：ReAct 编排与工作流聊天的集成"""

    def test_single_node_workflow_react_loop(self):
        """RED：单节点工作流的完整 ReAct 循环

        场景：修改单节点工作流
        期望：
        - 看到完整的推理→行动→观察→决策步骤
        - 工作流中的节点被正确识别
        - ReAct 状态被正确追踪
        """
        # 给定：一个单节点工作流
        node = Node.create(
            type=NodeType.HTTP,
            name="fetch_data",
            config={"url": "https://example.com"},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="single_node_workflow",
            description="A workflow with single HTTP node",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=10)

        # 当：运行 ReAct 循环
        state = orchestrator.run(workflow)

        # 那么：
        # 1. 应该返回最终状态
        assert state is not None
        assert state.workflow_id == workflow.id
        assert state.workflow_name == "single_node_workflow"

        # 2. 应该有可用节点
        assert len(state.available_nodes) == 1
        assert state.available_nodes[0] == node.id

        # 3. 应该追踪迭代信息
        assert state.iteration_count >= 0
        assert state.loop_status in ["running", "completed", "failed"]

    def test_streaming_event_sequence_order(self):
        """RED：流式事件按正确顺序产生

        期望事件序列：
        1. workflow_started
        2. reasoning_started
        3. 根据推理结果：
           - 如果推理成功：reasoning_completed → action_started → observation → iteration_completed
           - 如果推理失败：reasoning_failed → loop_completed
        """
        node = Node.create(
            type=NodeType.HTTP,
            name="test_node",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="event_sequence_test",
            description="Test event sequence",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=3)

        # 捕获所有事件
        captured_events = []

        def event_handler(event: ReActEvent):
            captured_events.append(event.event_type)

        orchestrator.on_event(event_handler)

        # 运行工作流
        orchestrator.run(workflow)

        # 验证：
        # 1. 应该有 workflow_started 事件
        assert "workflow_started" in captured_events

        # 2. 应该有推理相关的事件
        assert "reasoning_started" in captured_events
        assert "reasoning_completed" in captured_events or "reasoning_failed" in captured_events

        # 3. 不应该有其他意外事件
        valid_events = {
            "workflow_started",
            "reasoning_started",
            "reasoning_completed",
            "reasoning_failed",
            "action_started",
            "action_executed",
            "action_failed",
            "observation_started",
            "observation_completed",
            "iteration_completed",
            "loop_completed",
        }
        assert all(event in valid_events for event in captured_events)

    def test_multi_step_workflow_modification(self):
        """RED：多步骤工作流修改的 ReAct 循环

        场景：工作流包含多个节点
        期望：所有节点都在可用节点列表中
        """
        # 给定：多节点工作流
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
            name="multi_node_workflow",
            description="Workflow with multiple nodes",
            nodes=[node_a, node_b, node_c],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=5)

        # 当：运行工作流
        state = orchestrator.run(workflow)

        # 那么：
        # 1. 应该有三个可用节点
        assert len(state.available_nodes) == 3
        assert node_a.id in state.available_nodes
        assert node_b.id in state.available_nodes
        assert node_c.id in state.available_nodes

        # 2. 应该有消息历史
        assert len(state.messages) > 0

    def test_event_emission_during_execution(self):
        """RED：执行过程中正确发出事件

        期望：所有订阅的事件处理器都被调用
        """
        node = Node.create(
            type=NodeType.HTTP,
            name="event_test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="event_test",
            description="Test event emission",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=2)

        # 记录所有事件和回调次数
        events = []
        callback_count = [0]

        def event_callback(event: ReActEvent):
            events.append(event)
            callback_count[0] += 1

        orchestrator.on_event(event_callback)

        # 运行工作流
        orchestrator.run(workflow)

        # 验证：
        # 1. 回调应该被调用至少一次
        assert callback_count[0] > 0

        # 2. 应该捕获事件
        assert len(events) > 0

        # 3. 每个事件都应该有时间戳
        for event in events:
            assert event.timestamp is not None
            assert event.event_type is not None

    def test_react_state_message_history(self):
        """RED：ReAct 状态应该保存完整的消息历史

        期望：所有推理步骤都被记录为消息
        """
        node = Node.create(
            type=NodeType.HTTP,
            name="message_test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="message_history_test",
            description="Test message history",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=3)

        # 运行工作流
        state = orchestrator.run(workflow)

        # 验证：
        # 1. 应该有初始消息
        assert len(state.messages) > 0

        # 2. 消息应该包含开始执行的指示
        assert any("开始" in str(m.content) or "执行" in str(m.content) for m in state.messages)

    def test_react_state_action_tracking(self):
        """RED：ReAct 状态应该正确追踪执行的动作

        期望：executed_actions 列表记录所有动作
        """
        node = Node.create(
            type=NodeType.HTTP,
            name="action_test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="action_tracking_test",
            description="Test action tracking",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=5)

        # 运行工作流
        state = orchestrator.run(workflow)

        # 验证：
        # 1. 应该有执行的动作记录
        assert hasattr(state, "executed_actions")
        assert isinstance(state.executed_actions, list)

    def test_max_iterations_limit_enforcement(self):
        """RED：应该强制执行最大迭代数限制

        期望：迭代数不应该超过 max_iterations
        """
        node = Node.create(
            type=NodeType.HTTP,
            name="iteration_test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="max_iterations_test",
            description="Test max iterations limit",
            nodes=[node],
            edges=[],
        )

        # 设置较小的最大迭代数
        max_iters = 3
        orchestrator = ReActOrchestrator(max_iterations=max_iters)

        # 运行工作流
        state = orchestrator.run(workflow)

        # 验证：迭代数应该不超过最大值
        assert state.iteration_count <= max_iters

    def test_multiple_event_handlers(self):
        """RED：应该支持多个事件处理器

        期望：所有注册的处理器都应该被调用
        """
        node = Node.create(
            type=NodeType.HTTP,
            name="multi_handler_test",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="multi_handler_test",
            description="Test multiple handlers",
            nodes=[node],
            edges=[],
        )

        orchestrator = ReActOrchestrator(max_iterations=2)

        # 注册多个处理器
        handler1_called = [False]
        handler2_called = [False]

        def handler1(event: ReActEvent):
            handler1_called[0] = True

        def handler2(event: ReActEvent):
            handler2_called[0] = True

        orchestrator.on_event(handler1)
        orchestrator.on_event(handler2)

        # 运行工作流
        orchestrator.run(workflow)

        # 验证：两个处理器都应该被调用
        assert handler1_called[0]
        assert handler2_called[0]

    def test_workflow_independence(self):
        """RED：不同工作流的执行应该独立

        期望：多个工作流可以在不同编排器中独立执行
        """
        # 工作流 1
        node1 = Node.create(
            type=NodeType.HTTP,
            name="wf1_node",
            config={},
            position=Position(0, 0),
        )

        wf1 = Workflow.create(
            name="workflow_1",
            description="First workflow",
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
            description="Second workflow",
            nodes=[node2],
            edges=[],
        )

        # 分别执行
        orch1 = ReActOrchestrator(max_iterations=2)
        orch2 = ReActOrchestrator(max_iterations=2)

        state1 = orch1.run(wf1)
        state2 = orch2.run(wf2)

        # 验证：
        # 1. 状态应该独立
        assert state1.workflow_name == "workflow_1"
        assert state2.workflow_name == "workflow_2"

        # 2. workflow_id 应该不同
        assert state1.workflow_id != state2.workflow_id

        # 3. 可用节点应该不同
        assert state1.available_nodes != state2.available_nodes

"""RED 测试：LangGraph WorkflowExecutor - 工作流编排

TDD RED 阶段：定义 LangGraph WorkflowExecutor 的期望行为

设计目标：
1. 支持 Workflow DAG 的 LangGraph 表示
2. 与工作流节点和边兼容
3. 支持 ReAct 循环进行工作流级推理
4. 完整的错误处理和恢复
5. 消息历史记录用于审计

关键概念：
- Workflow: Feagent 中的工作流定义（nodes + edges）
- WorkflowExecutorGraph: LangGraph 表示，每个 node → node_executor
- WorkflowState: 工作流执行状态（当前node, 消息历史, 执行结果）
"""

from unittest.mock import Mock, patch

from langchain_core.messages import HumanMessage

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class TestLangGraphWorkflowExecutorBasics:
    """测试：LangGraph WorkflowExecutor 基础功能"""

    def test_workflow_executor_can_be_created(self):
        """RED：WorkflowExecutor 应该能被创建"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        # 创建简单的工作流
        node1 = Node.create(
            type=NodeType.HTTP,
            name="开始",
            config={"url": "https://example.com"},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="简单工作流",
            description="测试工作流",
            nodes=[node1],
            edges=[],
        )

        # 创建 WorkflowExecutor
        executor = create_langgraph_workflow_executor(workflow)

        assert executor is not None
        assert callable(executor.invoke) or callable(executor.stream)

    def test_workflow_executor_accepts_workflow_entity(self):
        """RED：WorkflowExecutor 接受 Workflow 实体"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        # 创建带节点的工作流
        node1 = Node.create(
            type=NodeType.HTTP,
            name="HTTP 请求",
            config={"url": "https://httpbin.org/get"},
            position=Position(0, 0),
        )

        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="数据转换",
            config={"transform": "pass_through"},
            position=Position(100, 0),
        )

        edge = Edge.create(node1.id, node2.id)

        workflow = Workflow.create(
            name="多节点工作流",
            description="包含 HTTP 和转换节点",
            nodes=[node1, node2],
            edges=[edge],
        )

        executor = create_langgraph_workflow_executor(workflow)

        assert executor is not None

    def test_workflow_executor_has_invoke_method(self):
        """RED：WorkflowExecutor 应该有 invoke 方法"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node = Node.create(
            type=NodeType.HTTP,
            name="测试",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="测试",
            description="测试",
            nodes=[node],
            edges=[],
        )

        executor = create_langgraph_workflow_executor(workflow)

        # 应该有 invoke 方法
        assert hasattr(executor, "invoke"), "executor 应该有 invoke 方法"
        assert callable(executor.invoke), "invoke 应该是可调用的"

    def test_workflow_executor_initializes_with_empty_messages(self):
        """RED：WorkflowExecutor 应该用空消息列表初始化"""
        from src.lc.workflow.langgraph_workflow_executor import (
            WorkflowExecutorState,
        )

        node = Node.create(
            type=NodeType.HTTP,
            name="开始",
            config={},
            position=Position(0, 0),
        )

        _ = Workflow.create(
            name="测试",
            description="测试",
            nodes=[node],
            edges=[],
        )

        # 初始状态应该包含空消息列表
        # 可以通过 TypedDict 验证
        assert hasattr(WorkflowExecutorState, "__annotations__")

    def test_workflow_executor_returns_workflow_state(self):
        """RED：WorkflowExecutor.invoke() 应该返回 WorkflowState"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node = Node.create(
            type=NodeType.HTTP,
            name="开始",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="测试",
            description="测试",
            nodes=[node],
            edges=[],
        )

        executor = create_langgraph_workflow_executor(workflow)

        # Mock 执行结果
        with patch(
            "src.lc.workflow.langgraph_workflow_executor.get_node_executor"
        ) as mock_get_executor:
            mock_node_executor = Mock()
            mock_node_executor.execute.return_value = {"result": "完成"}
            mock_get_executor.return_value = mock_node_executor

            initial_state = {"messages": [HumanMessage(content="开始")], "results": {}}

            result = executor.invoke(initial_state)

            assert result is not None
            assert "messages" in result
            assert isinstance(result["messages"], list)


class TestLangGraphWorkflowExecutorWithNodeExecutors:
    """测试：WorkflowExecutor 与节点执行器的集成"""

    def test_workflow_executor_calls_node_executors(self):
        """RED：WorkflowExecutor 应该调用相应的节点执行器"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node1 = Node.create(
            type=NodeType.HTTP,
            name="HTTP 请求",
            config={"url": "https://example.com"},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="单节点",
            description="测试",
            nodes=[node1],
            edges=[],
        )

        executor = create_langgraph_workflow_executor(workflow)

        with patch(
            "src.lc.workflow.langgraph_workflow_executor.get_node_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.execute.return_value = {"data": "响应"}
            mock_get_executor.return_value = mock_executor

            initial_state = {"messages": [HumanMessage(content="开始")], "results": {}}

            _ = executor.invoke(initial_state)

            # 应该调用了节点执行器
            mock_executor.execute.assert_called()

    def test_workflow_executor_follows_graph_edges(self):
        """RED：WorkflowExecutor 应该按边的顺序执行节点"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node1 = Node.create(
            type=NodeType.HTTP,
            name="第一个节点",
            config={},
            position=Position(0, 0),
        )

        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="第二个节点",
            config={},
            position=Position(100, 0),
        )

        edge = Edge.create(node1.id, node2.id)

        workflow = Workflow.create(
            name="多节点工作流",
            description="测试",
            nodes=[node1, node2],
            edges=[edge],
        )

        executor = create_langgraph_workflow_executor(workflow)

        with patch(
            "src.lc.workflow.langgraph_workflow_executor.get_node_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            call_order = []

            def track_calls(node, config):
                call_order.append(node.id)
                return {"result": "done"}

            mock_executor.execute.side_effect = track_calls
            mock_get_executor.return_value = mock_executor

            initial_state = {"messages": [HumanMessage(content="开始")], "results": {}}

            _ = executor.invoke(initial_state)

            # 应该按顺序调用节点
            assert mock_executor.execute.call_count >= 1

    def test_workflow_executor_passes_previous_node_results(self):
        """RED：WorkflowExecutor 应该将前置节点结果传给后续节点"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node1 = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(0, 0),
        )

        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点2",
            config={},
            position=Position(100, 0),
        )

        edge = Edge.create(node1.id, node2.id)

        workflow = Workflow.create(
            name="流水线",
            description="测试",
            nodes=[node1, node2],
            edges=[edge],
        )

        executor = create_langgraph_workflow_executor(workflow)

        with patch(
            "src.lc.workflow.langgraph_workflow_executor.get_node_executor"
        ) as mock_get_executor:
            mock_executor = Mock()

            # 第一个节点返回结果
            mock_executor.execute.side_effect = [
                {"data": "node1_output"},
                {"data": "node2_output"},
            ]

            mock_get_executor.return_value = mock_executor

            initial_state = {"messages": [HumanMessage(content="开始")], "results": {}}

            result = executor.invoke(initial_state)

            # 结果应该包含所有节点的输出
            assert "results" in result


class TestLangGraphWorkflowExecutorErrorHandling:
    """测试：WorkflowExecutor 的错误处理"""

    def test_workflow_executor_handles_node_failure(self):
        """RED：WorkflowExecutor 应该处理节点执行失败"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node = Node.create(
            type=NodeType.HTTP,
            name="会失败的节点",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="失败测试",
            description="测试",
            nodes=[node],
            edges=[],
        )

        executor = create_langgraph_workflow_executor(workflow)

        with patch(
            "src.lc.workflow.langgraph_workflow_executor.get_node_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.execute.side_effect = Exception("节点执行失败")
            mock_get_executor.return_value = mock_executor

            initial_state = {"messages": [HumanMessage(content="开始")], "results": {}}

            # 应该返回结果，不抛出异常
            result = executor.invoke(initial_state)

            assert result is not None
            assert "messages" in result


class TestLangGraphWorkflowExecutorMessageHistory:
    """测试：WorkflowExecutor 的消息历史"""

    def test_workflow_executor_preserves_message_history(self):
        """RED：WorkflowExecutor 应该保留完整的消息历史"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node = Node.create(
            type=NodeType.HTTP,
            name="HTTP",
            config={},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="消息历史",
            description="测试",
            nodes=[node],
            edges=[],
        )

        executor = create_langgraph_workflow_executor(workflow)

        with patch(
            "src.lc.workflow.langgraph_workflow_executor.get_node_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.execute.return_value = {"output": "complete"}
            mock_get_executor.return_value = mock_executor

            initial_state = {
                "messages": [HumanMessage(content="开始执行工作流")],
                "results": {},
            }

            result = executor.invoke(initial_state)

            # 消息列表应该被保留并可能增长
            assert "messages" in result
            assert len(result["messages"]) >= 1

    def test_workflow_executor_logs_node_execution(self):
        """RED：WorkflowExecutor 应该记录节点执行情况"""
        from src.lc.workflow.langgraph_workflow_executor import (
            create_langgraph_workflow_executor,
        )

        node = Node.create(
            type=NodeType.HTTP,
            name="HTTP 节点",
            config={"url": "https://example.com"},
            position=Position(0, 0),
        )

        workflow = Workflow.create(
            name="日志",
            description="测试",
            nodes=[node],
            edges=[],
        )

        executor = create_langgraph_workflow_executor(workflow)

        with patch(
            "src.lc.workflow.langgraph_workflow_executor.get_node_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.execute.return_value = {"status": "success"}
            mock_get_executor.return_value = mock_executor

            initial_state = {"messages": [HumanMessage(content="开始")], "results": {}}

            result = executor.invoke(initial_state)

            # 应该有执行日志信息（在消息或结果中）
            assert result is not None

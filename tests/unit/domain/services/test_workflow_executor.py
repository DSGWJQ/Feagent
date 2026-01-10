"""测试：WorkflowExecutor（工作流执行器）

Domain 层服务：负责执行工作流

测试策略：
- 测试拓扑排序（按依赖顺序执行节点）
- 测试节点执行（HTTP、Transform、Conditional 等）
- 测试错误处理

注意：execute 方法是异步的，需要使用 pytest-asyncio
"""

from typing import Any

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor, NodeExecutorRegistry
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class _EchoExecutor(NodeExecutor):
    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        return {"node_id": node.id, "node_type": node.type.value, "inputs": inputs}


class _ConditionalStubExecutor(NodeExecutor):
    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        value = next(iter(inputs.values())) if inputs else None
        is_true = value == "test"
        return {"result": is_true, "branch": "true" if is_true else "false"}


class TestWorkflowExecutor:
    """测试工作流执行器"""

    @pytest.mark.asyncio
    async def test_execute_simple_workflow_should_succeed(self):
        """测试：执行简单工作流应该成功

        场景：
        - Start → HTTP → End
        - 按顺序执行节点

        验收标准：
        - 节点按顺序执行
        - 返回最终结果
        """
        # Arrange
        node1 = Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=0, y=0),
        )
        node2 = Node.create(
            type=NodeType.HTTP,
            name="HTTP 请求",
            config={"url": "https://api.example.com", "method": "GET"},
            position=Position(x=100, y=0),
        )
        node3 = Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=Position(x=200, y=0),
        )

        edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
        edge2 = Edge.create(source_node_id=node2.id, target_node_id=node3.id)

        workflow = Workflow.create(
            name="简单工作流",
            description="",
            nodes=[node1, node2, node3],
            edges=[edge1, edge2],
        )

        registry = NodeExecutorRegistry()
        registry.register(NodeType.HTTP.value, _EchoExecutor())
        executor = WorkflowExecutor(executor_registry=registry)

        # Act
        result = await executor.execute(workflow, initial_input="test")

        # Assert
        assert result is not None
        assert result["node_type"] == NodeType.HTTP.value
        # 验证执行顺序：Start → HTTP → End
        assert len(executor.execution_log) == 3
        assert executor.execution_log[0]["node_id"] == node1.id
        assert executor.execution_log[1]["node_id"] == node2.id
        assert executor.execution_log[2]["node_id"] == node3.id

    @pytest.mark.asyncio
    async def test_execute_workflow_with_conditional_should_succeed(self):
        """测试：执行带条件分支的工作流应该成功

        场景：
        - Start → Conditional → (True: Node A, False: Node B) → End

        验收标准：
        - 仅执行满足条件的分支（edge.condition）
        """
        # Arrange
        node1 = Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=0, y=0),
        )
        node2 = Node.create(
            type=NodeType.CONDITIONAL,
            name="条件判断",
            config={"condition": "input1 === 'test'"},
            position=Position(x=100, y=0),
        )
        node3 = Node.create(
            type=NodeType.TRANSFORM,
            name="分支 A",
            config={},
            position=Position(x=200, y=-50),
        )
        node4 = Node.create(
            type=NodeType.TRANSFORM,
            name="分支 B",
            config={},
            position=Position(x=200, y=50),
        )
        node5 = Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=Position(x=300, y=0),
        )

        edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
        edge2 = Edge.create(
            source_node_id=node2.id,
            target_node_id=node3.id,
            condition="true",  # True 分支
        )
        edge3 = Edge.create(
            source_node_id=node2.id,
            target_node_id=node4.id,
            condition="false",  # False 分支
        )
        edge4 = Edge.create(source_node_id=node3.id, target_node_id=node5.id)
        edge5 = Edge.create(source_node_id=node4.id, target_node_id=node5.id)

        workflow = Workflow.create(
            name="条件工作流",
            description="",
            nodes=[node1, node2, node3, node4, node5],
            edges=[edge1, edge2, edge3, edge4, edge5],
        )

        registry = NodeExecutorRegistry()
        registry.register(NodeType.CONDITIONAL.value, _ConditionalStubExecutor())
        registry.register(NodeType.TRANSFORM.value, _EchoExecutor())
        executor = WorkflowExecutor(executor_registry=registry)

        # Act
        result = await executor.execute(workflow, initial_input="test")

        # Assert
        assert result is not None
        executed_ids = [row["node_id"] for row in executor.execution_log]
        assert node4.id not in executed_ids
        assert len(executor.execution_log) == 4

        result_2 = await executor.execute(workflow, initial_input="nope")
        assert result_2 is not None
        executed_ids_2 = [row["node_id"] for row in executor.execution_log]
        assert node3.id not in executed_ids_2
        assert len(executor.execution_log) == 4

    @pytest.mark.asyncio
    async def test_execute_workflow_with_cycle_should_raise_error(self):
        """测试：执行有环的工作流应该抛出错误

        场景：
        - Node A → Node B → Node A（形成环）

        验收标准：
        - 抛出 DomainError
        """
        # Arrange
        node1 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点 A",
            config={},
            position=Position(x=0, y=0),
        )
        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点 B",
            config={},
            position=Position(x=100, y=0),
        )

        edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
        edge2 = Edge.create(source_node_id=node2.id, target_node_id=node1.id)  # 形成环

        workflow = Workflow.create(
            name="有环工作流",
            description="",
            nodes=[node1, node2],
            edges=[edge1, edge2],
        )

        executor = WorkflowExecutor()

        # Act & Assert
        with pytest.raises(DomainError, match="工作流包含环"):
            await executor.execute(workflow, initial_input="test")

    def test_topological_sort_should_return_correct_order(self):
        """测试：拓扑排序应该返回正确的执行顺序

        场景：
        - A → B → D
        - A → C → D
        - 正确顺序：A, B, C, D 或 A, C, B, D

        验收标准：
        - A 在最前
        - D 在最后
        - B 和 C 在 A 之后、D 之前
        """
        # Arrange
        node_a = Node.create(
            type=NodeType.START,
            name="A",
            config={},
            position=Position(x=0, y=0),
        )
        node_b = Node.create(
            type=NodeType.TRANSFORM,
            name="B",
            config={},
            position=Position(x=100, y=-50),
        )
        node_c = Node.create(
            type=NodeType.TRANSFORM,
            name="C",
            config={},
            position=Position(x=100, y=50),
        )
        node_d = Node.create(
            type=NodeType.END,
            name="D",
            config={},
            position=Position(x=200, y=0),
        )

        edge1 = Edge.create(source_node_id=node_a.id, target_node_id=node_b.id)
        edge2 = Edge.create(source_node_id=node_a.id, target_node_id=node_c.id)
        edge3 = Edge.create(source_node_id=node_b.id, target_node_id=node_d.id)
        edge4 = Edge.create(source_node_id=node_c.id, target_node_id=node_d.id)

        workflow = Workflow.create(
            name="拓扑排序测试",
            description="",
            nodes=[node_a, node_b, node_c, node_d],
            edges=[edge1, edge2, edge3, edge4],
        )

        executor = WorkflowExecutor()

        # Act
        sorted_nodes = executor._topological_sort(workflow)

        # Assert
        assert sorted_nodes[0].id == node_a.id  # A 在最前
        assert sorted_nodes[-1].id == node_d.id  # D 在最后
        # B 和 C 在 A 之后、D 之前
        b_index = next(i for i, n in enumerate(sorted_nodes) if n.id == node_b.id)
        c_index = next(i for i, n in enumerate(sorted_nodes) if n.id == node_c.id)
        assert b_index > 0 and b_index < len(sorted_nodes) - 1
        assert c_index > 0 and c_index < len(sorted_nodes) - 1

    @pytest.mark.asyncio
    async def test_execute_skips_node_when_edge_condition_is_invalid_fail_closed(self):
        """测试：edge.condition 非法时应 fail-closed 且跳过节点

        场景：
        - Start → End（主链路）
        - Start -(invalid condition)-> Transform（应被跳过）

        验收标准：
        - Transform 节点不执行（不出现在 execution_log）
        - 触发 node_skipped 事件（reason=incoming_edge_conditions_not_met）
        """
        node_start = Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=0, y=0),
        )
        node_end = Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=Position(x=200, y=0),
        )
        node_should_skip = Node.create(
            type=NodeType.TRANSFORM,
            name="应跳过",
            config={},
            position=Position(x=100, y=100),
        )

        edge_main = Edge.create(source_node_id=node_start.id, target_node_id=node_end.id)
        edge_invalid = Edge.create(
            source_node_id=node_start.id,
            target_node_id=node_should_skip.id,
            condition="value ===",  # invalid expression after normalization
        )

        workflow = Workflow.create(
            name="invalid_condition_should_skip",
            description="",
            nodes=[node_start, node_end, node_should_skip],
            edges=[edge_main, edge_invalid],
        )

        events: list[tuple[str, dict[str, Any]]] = []
        registry = NodeExecutorRegistry()
        registry.register(NodeType.TRANSFORM.value, _EchoExecutor())
        executor = WorkflowExecutor(executor_registry=registry)
        executor.set_event_callback(lambda t, d: events.append((t, d)))

        result = await executor.execute(workflow, initial_input="test")

        assert result is not None
        executed_ids = [row["node_id"] for row in executor.execution_log]
        assert node_should_skip.id not in executed_ids
        skip_events = [
            d
            for t, d in events
            if t == "node_skipped"
            and d.get("node_id") == node_should_skip.id
            and d.get("reason") == "incoming_edge_conditions_not_met"
        ]
        assert skip_events
        details = skip_events[0].get("incoming_edge_conditions")
        assert isinstance(details, list)
        assert any(
            d.get("source_node_id") == node_start.id and d.get("expression") == "value ==="
            for d in details
        )

    @pytest.mark.asyncio
    async def test_execute_filters_inputs_after_conditional_branch(self):
        """测试：条件分支后 join 节点 inputs 仅包含满足条件的来源输出

        场景：
        - Start → Conditional
        - Conditional -> (true) Branch A
        - Conditional -> (false) Branch B
        - Branch A/B → Join(Transform Echo) → End

        验收标准：
        - 当 true 分支命中时，Join.inputs 仅包含 Branch A 输出
        - 当 false 分支命中时，Join.inputs 仅包含 Branch B 输出
        """
        node1 = Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=0, y=0),
        )
        node2 = Node.create(
            type=NodeType.CONDITIONAL,
            name="条件判断",
            config={"condition": "input1 == 'test'"},
            position=Position(x=100, y=0),
        )
        node3 = Node.create(
            type=NodeType.TRANSFORM,
            name="分支 A",
            config={},
            position=Position(x=200, y=-50),
        )
        node4 = Node.create(
            type=NodeType.TRANSFORM,
            name="分支 B",
            config={},
            position=Position(x=200, y=50),
        )
        node_join = Node.create(
            type=NodeType.TRANSFORM,
            name="Join",
            config={},
            position=Position(x=300, y=0),
        )
        node_end = Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=Position(x=400, y=0),
        )

        edges = [
            Edge.create(source_node_id=node1.id, target_node_id=node2.id),
            Edge.create(source_node_id=node2.id, target_node_id=node3.id, condition="true"),
            Edge.create(source_node_id=node2.id, target_node_id=node4.id, condition="false"),
            Edge.create(source_node_id=node3.id, target_node_id=node_join.id),
            Edge.create(source_node_id=node4.id, target_node_id=node_join.id),
            Edge.create(source_node_id=node_join.id, target_node_id=node_end.id),
        ]

        workflow = Workflow.create(
            name="branch_join_inputs_filtered",
            description="",
            nodes=[node1, node2, node3, node4, node_join, node_end],
            edges=edges,
        )

        registry = NodeExecutorRegistry()
        registry.register(NodeType.CONDITIONAL.value, _ConditionalStubExecutor())
        registry.register(NodeType.TRANSFORM.value, _EchoExecutor())
        executor = WorkflowExecutor(executor_registry=registry)

        result_true = await executor.execute(workflow, initial_input="test")
        assert isinstance(result_true, dict)
        assert "inputs" in result_true
        assert list(result_true["inputs"].keys()) == [node3.id]

        result_false = await executor.execute(workflow, initial_input="nope")
        assert isinstance(result_false, dict)
        assert "inputs" in result_false
        assert list(result_false["inputs"].keys()) == [node4.id]

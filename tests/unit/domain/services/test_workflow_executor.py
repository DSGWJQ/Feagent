"""测试：WorkflowExecutor（工作流执行器）

Domain 层服务：负责执行工作流

测试策略：
- 测试拓扑排序（按依赖顺序执行节点）
- 测试节点执行（HTTP、Transform、Conditional 等）
- 测试错误处理

注意：execute 方法是异步的，需要使用 pytest-asyncio
"""

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


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

        executor = WorkflowExecutor()

        # Act
        result = await executor.execute(workflow, initial_input="test")

        # Assert
        assert result is not None
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
        - 所有节点都被执行（暂时不实现条件分支逻辑）

        TODO: 完整实现条件分支逻辑（只执行满足条件的分支）
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

        executor = WorkflowExecutor()

        # Act
        result = await executor.execute(workflow, initial_input="test")

        # Assert
        assert result is not None
        # 暂时验证所有节点都被执行（未来实现条件分支后，只执行满足条件的分支）
        assert len(executor.execution_log) == 5

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

"""测试：Workflow 实体

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- Workflow 是工作流的聚合根
- 包含多个 Node 和 Edge
- 支持拖拽调整（添加/删除/更新节点和边）
"""

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.workflow_status import WorkflowStatus


class TestWorkflowCreation:
    """测试 Workflow 创建"""

    def test_create_workflow_with_valid_params_should_succeed(self):
        """测试：使用有效参数创建 Workflow 应该成功

        验收标准：
        - Workflow 必须有唯一 ID
        - name、description、nodes、edges 必须被正确保存
        - 默认状态为 DRAFT
        - 记录创建时间和更新时间
        """
        # Arrange
        nodes = [
            Node.create(
                type=NodeType.HTTP,
                name="获取数据",
                config={"url": "https://api.example.com"},
                position=Position(x=100, y=100),
            )
        ]
        edges = []

        # Act
        workflow = Workflow.create(
            name="测试工作流",
            description="这是一个测试工作流",
            nodes=nodes,
            edges=edges,
        )

        # Assert
        assert workflow.id is not None, "Workflow 必须有唯一 ID"
        assert workflow.id.startswith("wf_"), "Workflow ID 应该以 wf_ 开头"
        assert workflow.name == "测试工作流"
        assert workflow.description == "这是一个测试工作流"
        assert len(workflow.nodes) == 1
        assert len(workflow.edges) == 0
        assert workflow.status == WorkflowStatus.DRAFT
        assert workflow.created_at is not None
        assert workflow.updated_at is not None

    def test_create_workflow_with_empty_name_should_raise_error(self):
        """测试：使用空名称创建 Workflow 应该抛出错误"""
        # Arrange
        nodes = [
            Node.create(
                type=NodeType.HTTP,
                name="测试节点",
                config={},
                position=Position(x=100, y=100),
            )
        ]

        # Act & Assert
        with pytest.raises(DomainError, match="name 不能为空"):
            Workflow.create(name="", description="", nodes=nodes, edges=[])

    def test_create_workflow_with_no_nodes_should_raise_error(self):
        """测试：创建没有节点的 Workflow 应该抛出错误

        业务规则：
        - Workflow 至少要有一个节点
        """
        # Act & Assert
        with pytest.raises(DomainError, match="至少需要一个节点"):
            Workflow.create(name="测试工作流", description="", nodes=[], edges=[])

    def test_create_workflow_with_invalid_edge_should_raise_error(self):
        """测试：创建包含无效边的 Workflow 应该抛出错误

        业务规则：
        - Edge 引用的节点必须存在
        """
        # Arrange
        nodes = [
            Node.create(
                type=NodeType.HTTP,
                name="节点1",
                config={},
                position=Position(x=100, y=100),
            )
        ]
        edges = [
            Edge.create(
                source_node_id=nodes[0].id,
                target_node_id="node_999",  # 不存在的节点
            )
        ]

        # Act & Assert
        with pytest.raises(DomainError, match="节点不存在"):
            Workflow.create(name="测试工作流", description="", nodes=nodes, edges=edges)


class TestWorkflowNodeOperations:
    """测试 Workflow 节点操作"""

    def test_add_node_should_succeed(self):
        """测试：添加节点应该成功"""
        # Arrange
        node1 = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(x=100, y=100),
        )
        workflow = Workflow.create(name="测试工作流", description="", nodes=[node1], edges=[])

        # Act
        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点2",
            config={},
            position=Position(x=200, y=200),
        )
        workflow.add_node(node2)

        # Assert
        assert len(workflow.nodes) == 2
        assert workflow.nodes[1] == node2

    def test_remove_node_should_succeed(self):
        """测试：删除节点应该成功"""
        # Arrange
        node1 = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(x=100, y=100),
        )
        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点2",
            config={},
            position=Position(x=200, y=200),
        )
        workflow = Workflow.create(
            name="测试工作流", description="", nodes=[node1, node2], edges=[]
        )

        # Act
        workflow.remove_node(node1.id)

        # Assert
        assert len(workflow.nodes) == 1
        assert workflow.nodes[0] == node2

    def test_remove_node_should_remove_related_edges(self):
        """测试：删除节点时应该删除相关的边

        业务规则：
        - 删除节点时，所有连接到该节点的边也应该被删除
        """
        # Arrange
        node1 = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(x=100, y=100),
        )
        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点2",
            config={},
            position=Position(x=200, y=200),
        )
        edge = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
        workflow = Workflow.create(
            name="测试工作流", description="", nodes=[node1, node2], edges=[edge]
        )

        # Act
        workflow.remove_node(node1.id)

        # Assert
        assert len(workflow.nodes) == 1
        assert len(workflow.edges) == 0, "相关的边应该被删除"

    def test_remove_last_node_should_raise_error(self):
        """测试：删除最后一个节点应该抛出错误

        业务规则：
        - Workflow 至少要有一个节点
        """
        # Arrange
        node = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(x=100, y=100),
        )
        workflow = Workflow.create(name="测试工作流", description="", nodes=[node], edges=[])

        # Act & Assert
        with pytest.raises(DomainError, match="至少需要一个节点"):
            workflow.remove_node(node.id)

    def test_update_node_should_succeed(self):
        """测试：更新节点应该成功"""
        # Arrange
        node = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={"url": "https://old.com"},
            position=Position(x=100, y=100),
        )
        workflow = Workflow.create(name="测试工作流", description="", nodes=[node], edges=[])

        # Act
        updated_node = Node.create(
            type=NodeType.HTTP,
            name="更新后的节点",
            config={"url": "https://new.com"},
            position=Position(x=200, y=200),
        )
        updated_node.id = node.id  # 保持相同的 ID
        workflow.update_node(updated_node)

        # Assert
        assert workflow.nodes[0].name == "更新后的节点"
        assert workflow.nodes[0].config == {"url": "https://new.com"}
        assert workflow.nodes[0].position == Position(x=200, y=200)


class TestWorkflowEdgeOperations:
    """测试 Workflow 边操作"""

    def test_add_edge_should_succeed(self):
        """测试：添加边应该成功"""
        # Arrange
        node1 = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(x=100, y=100),
        )
        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点2",
            config={},
            position=Position(x=200, y=200),
        )
        workflow = Workflow.create(
            name="测试工作流", description="", nodes=[node1, node2], edges=[]
        )

        # Act
        edge = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
        workflow.add_edge(edge)

        # Assert
        assert len(workflow.edges) == 1
        assert workflow.edges[0] == edge

    def test_add_edge_with_invalid_source_should_raise_error(self):
        """测试：添加引用不存在节点的边应该抛出错误"""
        # Arrange
        node = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(x=100, y=100),
        )
        workflow = Workflow.create(name="测试工作流", description="", nodes=[node], edges=[])

        # Act & Assert
        edge = Edge.create(source_node_id="node_999", target_node_id=node.id)
        with pytest.raises(DomainError, match="节点不存在"):
            workflow.add_edge(edge)

    def test_remove_edge_should_succeed(self):
        """测试：删除边应该成功"""
        # Arrange
        node1 = Node.create(
            type=NodeType.HTTP,
            name="节点1",
            config={},
            position=Position(x=100, y=100),
        )
        node2 = Node.create(
            type=NodeType.TRANSFORM,
            name="节点2",
            config={},
            position=Position(x=200, y=200),
        )
        edge = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
        workflow = Workflow.create(
            name="测试工作流", description="", nodes=[node1, node2], edges=[edge]
        )

        # Act
        workflow.remove_edge(edge.id)

        # Assert
        assert len(workflow.edges) == 0

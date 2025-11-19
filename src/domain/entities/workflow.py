"""Workflow 实体 - 工作流聚合根

业务定义：
- Workflow 是工作流的聚合根
- 包含多个 Node 和 Edge
- 支持拖拽调整（添加/删除/更新节点和边）

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
- 维护聚合根不变式（节点和边的一致性）
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.workflow_status import WorkflowStatus


@dataclass
class Workflow:
    """Workflow 实体（聚合根）

    属性说明：
    - id: 唯一标识符（wf_ 前缀）
    - name: 工作流名称（用户可见）
    - description: 工作流描述
    - nodes: 节点列表
    - edges: 边列表
    - status: 工作流状态（DRAFT/PUBLISHED/ARCHIVED）
    - created_at: 创建时间
    - updated_at: 更新时间

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__ 等方法
    2. 类型注解清晰，IDE 友好
    3. 符合 Python 3.11+ 最佳实践
    4. 纯 Python，不依赖框架（符合 DDD 要求）

    为什么是聚合根？
    1. Workflow 管理 Node 和 Edge 的生命周期
    2. 外部只能通过 Workflow 操作 Node 和 Edge
    3. Workflow 维护节点和边的一致性
    """

    id: str
    name: str
    description: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        nodes: list[Node],
        edges: list[Edge],
    ) -> "Workflow":
        """创建 Workflow 的工厂方法

        为什么使用工厂方法？
        1. 封装创建逻辑：自动生成 ID、设置默认值
        2. 验证业务规则：确保 name 不为空、至少有一个节点、边引用的节点存在
        3. 符合 DDD 聚合根创建模式

        参数：
            name: 工作流名称（必需）
            description: 工作流描述
            nodes: 节点列表（至少一个）
            edges: 边列表

        返回：
            Workflow 实例

        抛出：
            DomainError: 当验证失败时
        """
        # 验证业务规则
        if not name or not name.strip():
            raise DomainError("name 不能为空")

        if not nodes:
            raise DomainError("至少需要一个节点")

        # 验证边引用的节点存在
        node_ids = {node.id for node in nodes}
        for edge in edges:
            if edge.source_node_id not in node_ids:
                raise DomainError(f"节点不存在: {edge.source_node_id}")
            if edge.target_node_id not in node_ids:
                raise DomainError(f"节点不存在: {edge.target_node_id}")

        return cls(
            id=f"wf_{uuid4().hex[:8]}",
            name=name.strip(),
            description=description.strip() if description else "",
            nodes=nodes.copy(),  # 复制列表，避免外部修改
            edges=edges.copy(),  # 复制列表，避免外部修改
            status=WorkflowStatus.DRAFT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def add_node(self, node: Node) -> None:
        """添加节点

        用于拖拽调整工作流时添加新节点

        参数：
            node: 要添加的节点
        """
        self.nodes.append(node)
        self.updated_at = datetime.now(UTC)

    def remove_node(self, node_id: str) -> None:
        """删除节点

        用于拖拽调整工作流时删除节点

        业务规则：
        - 至少保留一个节点
        - 删除节点时，同时删除相关的边

        参数：
            node_id: 要删除的节点 ID

        抛出：
            DomainError: 当删除最后一个节点时
        """
        if len(self.nodes) <= 1:
            raise DomainError("至少需要一个节点")

        # 删除节点
        self.nodes = [node for node in self.nodes if node.id != node_id]

        # 删除相关的边
        self.edges = [
            edge
            for edge in self.edges
            if edge.source_node_id != node_id and edge.target_node_id != node_id
        ]

        self.updated_at = datetime.now(UTC)

    def update_node(self, updated_node: Node) -> None:
        """更新节点

        用于拖拽调整工作流时更新节点（位置、配置等）

        参数：
            updated_node: 更新后的节点

        抛出：
            DomainError: 当节点不存在时
        """
        for i, node in enumerate(self.nodes):
            if node.id == updated_node.id:
                self.nodes[i] = updated_node
                self.updated_at = datetime.now(UTC)
                return

        raise DomainError(f"节点不存在: {updated_node.id}")

    def add_edge(self, edge: Edge) -> None:
        """添加边

        用于拖拽调整工作流时添加新边

        业务规则：
        - 边引用的节点必须存在

        参数：
            edge: 要添加的边

        抛出：
            DomainError: 当边引用的节点不存在时
        """
        # 验证节点存在
        node_ids = {node.id for node in self.nodes}
        if edge.source_node_id not in node_ids:
            raise DomainError(f"节点不存在: {edge.source_node_id}")
        if edge.target_node_id not in node_ids:
            raise DomainError(f"节点不存在: {edge.target_node_id}")

        self.edges.append(edge)
        self.updated_at = datetime.now(UTC)

    def remove_edge(self, edge_id: str) -> None:
        """删除边

        用于拖拽调整工作流时删除边

        参数：
            edge_id: 要删除的边 ID
        """
        self.edges = [edge for edge in self.edges if edge.id != edge_id]
        self.updated_at = datetime.now(UTC)

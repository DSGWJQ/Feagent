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

from typing import Any, Dict

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
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
    source: str = "feagent"  # V2新增：工作流来源（feagent/coze/user）
    source_id: str | None = None  # V2新增：原始来源的ID（如Coze workflow_id）
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        nodes: list[Node],
        edges: list[Edge],
        source: str = "feagent",
        source_id: str | None = None,
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
            source=source,
            source_id=source_id,
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

    @staticmethod
    def from_coze_json(coze_data: Dict[str, Any]) -> "Workflow":
        """从Coze JSON创建Workflow

        V2功能：支持从Coze平台导入工作流

        业务规则：
        1. 节点类型映射：llm→LLM, http→HTTP, javascript→JAVASCRIPT等
        2. 边引用验证：source和target必须存在于节点列表中
        3. Source追踪：记录来源为"coze"，保存原始workflow_id

        Coze JSON格式示例：
        {
            "workflow_id": "coze_wf_12345",
            "name": "工作流名称",
            "description": "工作流描述",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "llm",
                    "name": "节点名称",
                    "config": {...},
                    "position": {"x": 100, "y": 100}
                }
            ],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2"}
            ]
        }

        参数：
            coze_data: Coze工作流JSON数据

        返回：
            Workflow实例

        抛出：
            DomainError: 当验证失败时
        """
        # Coze节点类型到Feagent节点类型的映射
        COZE_NODE_TYPE_MAPPING = {
            "llm": NodeType.LLM,
            "http": NodeType.HTTP,
            "javascript": NodeType.JAVASCRIPT,
            "condition": NodeType.CONDITION,
            "start": NodeType.START,
            "end": NodeType.END,
            "database": NodeType.DATABASE,
            "transform": NodeType.TRANSFORM,
            "loop": NodeType.LOOP,
        }

        # 验证JSON不为空
        if not coze_data:
            raise DomainError("Coze JSON不能为空")

        # 提取基本信息
        workflow_id = coze_data.get("workflow_id", "")
        name = coze_data.get("name", "")
        description = coze_data.get("description", "")
        coze_nodes = coze_data.get("nodes", [])
        coze_edges = coze_data.get("edges", [])

        # 验证至少有一个节点
        if not coze_nodes:
            raise DomainError("至少需要一个节点")

        # 转换节点
        nodes = []
        for coze_node in coze_nodes:
            coze_type = coze_node.get("type", "").lower()

            # 验证节点类型是否支持
            if coze_type not in COZE_NODE_TYPE_MAPPING:
                raise DomainError(
                    f"不支持的Coze节点类型: {coze_type}. "
                    f"支持的类型: {', '.join(COZE_NODE_TYPE_MAPPING.keys())}"
                )

            # 映射节点类型
            node_type = COZE_NODE_TYPE_MAPPING[coze_type]

            # 提取position
            coze_position = coze_node.get("position", {"x": 0, "y": 0})
            position = Position(x=coze_position.get("x", 0), y=coze_position.get("y", 0))

            # 创建节点
            node = Node.create(
                type=node_type,
                name=coze_node.get("name", coze_type),
                config=coze_node.get("config", {}),
                position=position,
            )
            # 保留原始ID，避免edge引用失效
            node.id = coze_node.get("id", node.id)
            nodes.append(node)

        # 转换边
        edges = []
        for coze_edge in coze_edges:
            edge = Edge.create(
                source_node_id=coze_edge.get("source", ""),
                target_node_id=coze_edge.get("target", ""),
            )
            # 保留原始ID
            edge.id = coze_edge.get("id", edge.id)
            edges.append(edge)

        # 使用create方法创建Workflow（会自动验证边引用）
        return Workflow.create(
            name=name,
            description=description,
            nodes=nodes,
            edges=edges,
            source="coze",
            source_id=workflow_id,
        )

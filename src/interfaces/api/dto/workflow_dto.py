"""Workflow DTO（Data Transfer Objects）

定义 Workflow 相关的请求和响应模型
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow


class PositionDTO(BaseModel):
    """Position DTO

    字段：
    - x: 横坐标
    - y: 纵坐标

    注意：允许负坐标（画布可以有负坐标）
    """

    x: float = Field(..., description="横坐标")
    y: float = Field(..., description="纵坐标")

    model_config = ConfigDict(from_attributes=True)


class NodeDTO(BaseModel):
    """Node DTO

    字段：
    - id: 节点 ID
    - type: 节点类型
    - name: 节点名称（可选，默认为空字符串）
    - data: 节点配置（V0 前端使用 data，后端内部使用 config）
    - position: 节点位置

    注意：
    - 为了兼容 V0 前端（React Flow），使用 `data` 字段名
    - 后端 Domain 层仍使用 `config` 字段名
    """

    id: str
    type: str
    name: str = Field(default="", description="节点名称（可选）")
    data: dict = Field(default_factory=dict, description="节点配置")
    position: PositionDTO

    @classmethod
    def from_entity(cls, node: Node) -> "NodeDTO":
        """从 Domain 实体创建 DTO

        参数：
            node: Node 实体

        返回：
            NodeDTO
        """
        return cls(
            id=node.id,
            type=node.type.value,
            name=node.name,
            data=node.config,  # config → data
            position=PositionDTO(x=node.position.x, y=node.position.y),
        )

    def to_entity(self) -> Node:
        """转换为 Domain 实体

        返回：
            Node 实体
        """
        from src.domain.value_objects.node_type import NodeType
        from src.domain.value_objects.position import Position

        node = Node(
            id=self.id,
            type=NodeType(self.type),
            name=self.name,
            config=self.data,  # data → config
            position=Position(x=self.position.x, y=self.position.y),
        )
        return node

    model_config = ConfigDict(from_attributes=True)


class EdgeDTO(BaseModel):
    """Edge DTO

    字段：
    - id: 边 ID
    - source: 源节点 ID（V0 前端使用 source）
    - target: 目标节点 ID（V0 前端使用 target）
    - condition: 条件表达式（可选）
    - sourceHandle: 源节点句柄（可选，用于条件分支）
    - label: 边标签（可选）

    注意：
    - 为了兼容 V0 前端（React Flow），使用 `source` 和 `target` 字段名
    - 后端 Domain 层使用 `source_node_id` 和 `target_node_id`
    """

    id: str
    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    condition: str | None = Field(default=None, description="条件表达式（可选）")
    sourceHandle: str | None = Field(default=None, description="源节点句柄（可选）")
    label: str | None = Field(default=None, description="边标签（可选）")

    @classmethod
    def from_entity(cls, edge: Edge) -> "EdgeDTO":
        """从 Domain 实体创建 DTO

        参数：
            edge: Edge 实体

        返回：
            EdgeDTO
        """
        return cls(
            id=edge.id,
            source=edge.source_node_id,  # source_node_id → source
            target=edge.target_node_id,  # target_node_id → target
            condition=edge.condition,
        )

    def to_entity(self) -> Edge:
        """转换为 Domain 实体

        返回：
            Edge 实体
        """
        edge = Edge(
            id=self.id,
            source_node_id=self.source,  # source → source_node_id
            target_node_id=self.target,  # target → target_node_id
            condition=self.condition,
        )
        return edge

    model_config = ConfigDict(from_attributes=True)


class WorkflowResponse(BaseModel):
    """Workflow 响应 DTO

    业务场景：API 返回 Workflow 信息给前端

    字段：
    - id: Workflow ID
    - name: 工作流名称
    - description: 工作流描述
    - nodes: 节点列表
    - edges: 边列表
    - status: 工作流状态
    - created_at: 创建时间
    - updated_at: 更新时间
    """

    id: str
    name: str
    description: str
    nodes: list[NodeDTO]
    edges: list[EdgeDTO]
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, workflow: Workflow) -> "WorkflowResponse":
        """从 Domain 实体创建响应 DTO

        参数：
            workflow: Workflow 实体

        返回：
            WorkflowResponse DTO
        """
        return cls(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            nodes=[NodeDTO.from_entity(node) for node in workflow.nodes],
            edges=[EdgeDTO.from_entity(edge) for edge in workflow.edges],
            status=workflow.status.value,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

    model_config = ConfigDict(from_attributes=True)


class CreateWorkflowRequest(BaseModel):
    """创建 Workflow 请求 DTO

    业务场景：用户创建新工作流

    字段：
    - name: 工作流名称
    - description: 工作流描述（可选）
    - nodes: 初始节点列表（可选）
    - edges: 初始边列表（可选）

    验证规则：
    - name 不能为空
    """

    name: str = Field(..., min_length=1, description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    nodes: list[NodeDTO] = Field(default_factory=list, description="节点列表")
    edges: list[EdgeDTO] = Field(default_factory=list, description="边列表")

    model_config = ConfigDict(from_attributes=True)


class UpdateWorkflowRequest(BaseModel):
    """更新 Workflow 请求 DTO

    业务场景：用户通过拖拽调整工作流

    字段：
    - nodes: 更新后的节点列表
    - edges: 更新后的边列表

    验证规则：
    - nodes 可以为空（允许清空所有节点）
    """

    nodes: list[NodeDTO] = Field(default_factory=list, description="节点列表")
    edges: list[EdgeDTO] = Field(default_factory=list, description="边列表")

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    """对话请求 DTO

    业务场景：用户通过对话式交互修改工作流

    字段：
    - message: 用户消息（如"添加一个HTTP节点"）

    验证规则：
    - message 不能为空
    """

    message: str = Field(..., min_length=1, description="用户消息")

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    """对话响应 DTO（增强版）

    业务场景：返回修改后的工作流和AI回复消息，包含增强字段和RAG来源

    字段：
    - workflow: 更新后的工作流
    - ai_message: AI 回复消息
    - intent: 用户意图类型（add_node、delete_node、add_edge等）
    - confidence: AI 的信心度（0-1）
    - modifications_count: 修改数量
    - rag_sources: RAG检索来源列表
    - react_steps: ReAct推理步骤列表（思考→行动→观察）

    注意：
    - workflow 包含完整的 nodes 和 edges
    - ai_message 描述了做了什么修改
    - 增强字段由 EnhancedWorkflowChatService 提供
    - rag_sources 包含知识库检索来源（如果启用RAG）
    - react_steps 包含ReAct推理循环的步骤（思考、行动、观察）
    """

    workflow: "WorkflowResponse"
    ai_message: str = Field(..., description="AI 回复消息")
    intent: str = Field(default="", description="用户意图类型")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="AI 信心度")
    modifications_count: int = Field(default=0, ge=0, description="修改数量")
    rag_sources: list[dict] = Field(default_factory=list, description="RAG检索来源列表")
    react_steps: list[dict] = Field(default_factory=list, description="ReAct推理步骤列表")


class ImportWorkflowRequest(BaseModel):
    """导入工作流请求 DTO

    V2新功能：支持从 Coze 平台导入工作流

    业务场景：用户上传 Coze 工作流 JSON 数据，系统导入并创建 Workflow

    字段：
    - coze_json: Coze 工作流 JSON 数据（dict 格式）

    验证规则：
    - coze_json 不能为空
    - 必须是有效的 JSON 结构

    示例：
    {
        "coze_json": {
            "workflow_id": "coze_wf_12345",
            "name": "测试工作流",
            "description": "从Coze导入",
            "nodes": [...],
            "edges": [...]
        }
    }
    """

    coze_json: dict = Field(..., description="Coze 工作流 JSON 数据")

    model_config = ConfigDict(from_attributes=True)


class ImportWorkflowResponse(BaseModel):
    """导入工作流响应 DTO

    V2新功能：返回导入后的工作流基本信息

    字段：
    - workflow_id: 生成的 Workflow ID
    - name: 工作流名称
    - source: 工作流来源（固定为 "coze"）
    - source_id: 原始 Coze workflow_id

    注意：
    - 返回的是导入后的 Workflow 基本信息
    - 如需获取完整工作流详情，调用 GET /workflows/{workflow_id}
    - source_id 用于追踪原始来源，方便同步更新
    """

    workflow_id: str = Field(..., description="生成的 Workflow ID")
    name: str = Field(..., description="工作流名称")
    source: str = Field(..., description="工作流来源（coze）")
    source_id: str | None = Field(None, description="原始 Coze workflow_id")

    model_config = ConfigDict(from_attributes=True)

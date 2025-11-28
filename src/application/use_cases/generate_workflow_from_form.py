"""Generate Workflow From Form Use Case（表单→工作流生成用例）

Application 层：从表单输入生成工作流

业务规则：
1. 用户提供工作流描述和目标
2. 使用 LLM 分析描述并生成结构化的工作流
3. 创建包含节点和边的完整工作流
4. 保存到工作流仓库
"""

from dataclasses import dataclass

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


@dataclass
class GenerateWorkflowInput:
    """生成工作流的输入参数

    属性：
        description: 工作流描述（用户输入的自然语言描述）
        goal: 工作流目标
    """

    description: str
    goal: str


class GenerateWorkflowFromFormUseCase:
    """从表单生成工作流用例

    职责：
    1. 验证输入参数
    2. 调用 LLM 生成工作流结构
    3. 创建工作流实体
    4. 保存到仓库

    依赖：
    - workflow_repository: 工作流仓库
    - llm_client: LLM 客户端（用于工作流生成）
    """

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        llm_client,
    ):
        """初始化用例

        参数：
            workflow_repository: 工作流仓库
            llm_client: LLM 客户端
        """
        self.workflow_repository = workflow_repository
        self.llm_client = llm_client

    async def execute(self, input_data: GenerateWorkflowInput) -> Workflow:
        """执行工作流生成

        参数：
            input_data: 输入参数

        返回：
            创建的工作流实体

        抛出：
            DomainError: 当验证失败或生成失败时
        """
        # 1. 验证输入
        if not input_data.description or not input_data.description.strip():
            raise DomainError("description不能为空")

        if not input_data.goal or not input_data.goal.strip():
            raise DomainError("goal不能为空")

        # 2. 使用 LLM 生成工作流结构
        try:
            workflow_data = await self.llm_client.generate_workflow(
                description=input_data.description,
                goal=input_data.goal,
            )
        except Exception as e:
            # 重新抛出 LLM API 异常
            raise e

        # 3. 解析 LLM 返回的数据，创建节点和边
        nodes = self._parse_nodes(workflow_data.get("nodes", []))
        edges = self._parse_edges(workflow_data.get("edges", []))

        # 4. 创建工作流实体
        workflow = Workflow.create(
            name=workflow_data.get("name", "AI生成工作流"),
            description=workflow_data.get("description", input_data.description),
            nodes=nodes,
            edges=edges,
            source="feagent",
        )

        # 5. 保存到仓库
        self.workflow_repository.save(workflow)

        return workflow

    @staticmethod
    def _parse_nodes(nodes_data: list[dict]) -> list[Node]:
        """解析节点数据

        参数：
            nodes_data: LLM 返回的节点列表

        返回：
            节点实体列表

        抛出：
            DomainError: 当节点数据无效时
        """
        nodes = []
        node_id_map = {}  # 用于映射原始ID到新生成的ID

        for i, node_data in enumerate(nodes_data, start=1):
            # 提取节点类型（不转换大小写，保持原始格式）
            node_type_str = node_data.get("type", "")
            try:
                node_type = NodeType(node_type_str)
            except ValueError as exc:
                raise DomainError(f"不支持的节点类型: {node_type_str}") from exc

            # 提取位置
            position_data = node_data.get("position", {"x": 0, "y": 0})
            position = Position(
                x=position_data.get("x", 0),
                y=position_data.get("y", 0),
            )

            # 创建节点
            node = Node.create(
                type=node_type,
                name=node_data.get("name", f"节点{i}"),
                config=node_data.get("config", {}),
                position=position,
            )

            # 记录ID映射（LLM可能返回node_1, node_2...，需要映射到实际ID）
            original_id = f"node_{i}"
            node_id_map[original_id] = node.id

            # 保存原始ID到节点（用于后续边引用）
            node.id = original_id

            nodes.append(node)

        return nodes

    @staticmethod
    def _parse_edges(edges_data: list[dict]) -> list[Edge]:
        """解析边数据

        参数：
            edges_data: LLM 返回的边列表

        返回：
            边实体列表

        抛出：
            DomainError: 当边数据无效时
        """
        edges = []

        for edge_data in edges_data:
            source_node_id = edge_data.get("source", "")
            target_node_id = edge_data.get("target", "")
            condition = edge_data.get("condition")

            # 创建边
            edge = Edge.create(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                condition=condition,
            )

            edges.append(edge)

        return edges

"""UpdateWorkflowByDragUseCase - 通过拖拽更新工作流

业务场景：
- 用户在前端拖拽编辑器中调整工作流
- 添加/删除/更新节点
- 添加/删除边
- 保存变更到数据库

设计原则：
- 单一职责：只负责业务编排，不包含业务逻辑
- 依赖倒置：依赖 Repository 接口，不依赖具体实现
- 输入输出明确：使用 Input/Output 对象
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_save_validator import WorkflowSaveValidator


@dataclass
class UpdateWorkflowByDragInput:
    """UpdateWorkflowByDrag 输入参数

    为什么需要 Input 对象？
    1. 类型安全：明确输入参数类型
    2. 验证集中：可以在 Input 对象中验证参数
    3. 可测试性：测试时容易构造输入
    4. 文档化：清晰表达 Use Case 需要什么输入

    属性说明：
    - workflow_id: 工作流 ID
    - nodes: 更新后的节点列表
    - edges: 更新后的边列表
    """

    workflow_id: str
    nodes: list[Node]
    edges: list[Edge]


class UpdateWorkflowByDragUseCase:
    """UpdateWorkflowByDrag Use Case

    职责：
    1. 获取现有工作流
    2. 应用拖拽变更（替换节点和边）
    3. 保存工作流

    为什么不在这里验证业务规则？
    - 业务规则验证在 Domain 层（Workflow 实体）
    - Use Case 只负责编排（获取 → 应用变更 → 保存）
    - 符合单一职责原则

    依赖：
    - WorkflowRepository: 工作流仓储接口
    """

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        save_validator: WorkflowSaveValidator,
    ):
        """初始化 Use Case

        参数：
            workflow_repository: 工作流仓储接口

        为什么通过构造函数注入依赖？
        - 依赖倒置：Use Case 依赖接口，不依赖具体实现
        - 可测试性：测试时可以注入 Mock Repository
        - 灵活性：可以轻松切换不同的 Repository 实现
        """
        self.workflow_repository = workflow_repository
        self.save_validator = save_validator

    def execute(self, input_data: UpdateWorkflowByDragInput) -> Workflow:
        """执行 Use Case

        业务流程：
        1. 获取现有工作流（不存在抛出 NotFoundError）
        2. 替换节点和边（直接替换，不做增量更新）
        3. 更新时间戳
        4. 保存工作流

        为什么直接替换而不是增量更新？
        - 前端拖拽编辑器会发送完整的节点和边列表
        - 直接替换更简单，避免复杂的 diff 逻辑
        - 性能影响不大（工作流节点数量通常不多）

        参数：
            input_data: 输入参数

        返回：
            更新后的 Workflow 实体

        抛出：
            NotFoundError: 当 Workflow 不存在时
            DomainError: 当业务规则验证失败时（如边引用的节点不存在）
        """
        # 1. 获取现有工作流
        workflow = self.workflow_repository.get_by_id(input_data.workflow_id)

        # 2. 替换节点和边
        workflow.nodes = input_data.nodes.copy()
        workflow.edges = input_data.edges.copy()

        # 3. 更新时间戳
        workflow.updated_at = datetime.now(UTC)

        # 4. 保存前强校验（可执行性 / DAG / 引用完整性）
        self.save_validator.validate_or_raise(workflow)

        # 5. 保存工作流
        self.workflow_repository.save(workflow)

        return workflow

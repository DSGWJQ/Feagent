"""SQLAlchemy Workflow Repository 实现

第一性原理：Repository 是领域对象和数据存储之间的转换器

职责：
1. 转换（Translation）：领域实体 ⇄ ORM 模型
2. 持久化（Persistence）：保存、查询、删除
3. 异常转换（Exception Translation）：数据库异常 → 领域异常
4. 聚合根管理：级联保存/加载 Node 和 Edge

设计模式：
- Adapter 模式：实现领域层定义的 Port 接口
- Assembler 模式：负责对象转换（ORM ⇄ Entity）
- Repository 模式：封装数据访问逻辑
- Aggregate Root 模式：Workflow 管理 Node 和 Edge 的生命周期

为什么需要 Assembler？
- 关注点分离：转换逻辑独立于持久化逻辑
- 可测试性：可以单独测试转换逻辑
- 可维护性：转换逻辑集中管理
"""

from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import NotFoundError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.workflow_status import WorkflowStatus
from src.infrastructure.database.models import EdgeModel, NodeModel, WorkflowModel


class SQLAlchemyWorkflowRepository:
    """SQLAlchemy Workflow Repository 实现

    实现领域层定义的 WorkflowRepository Port 接口

    依赖：
    - Session: SQLAlchemy 同步会话（依赖注入）

    为什么使用同步 Session？
    - 当前实现是同步的（Use Case 是同步的）
    - 简单易懂，易于调试
    - 未来可以迁移到异步

    为什么不显式继承 WorkflowRepository？
    - 使用 Protocol（结构化子类型）
    - 只要方法签名匹配，就符合接口
    - 更灵活，不需要显式继承
    """

    def __init__(self, session: Session):
        """初始化 Repository

        参数：
            session: SQLAlchemy 同步会话

        为什么通过构造函数注入 session？
        - 依赖注入：由外部管理 session 生命周期
        - 事务控制：调用者控制事务边界
        - 可测试性：测试时可以注入 Mock session
        """
        self.session = session

    # ==================== Assembler 方法 ====================
    # 职责：ORM 模型 ⇄ 领域实体转换

    def _to_entity(self, model: WorkflowModel) -> Workflow:
        """将 ORM 模型转换为领域实体（聚合根）

        为什么需要这个方法？
        - ORM 模型是数据库表映射（Infrastructure 层）
        - 领域实体是业务逻辑载体（Domain 层）
        - 两者职责不同，需要转换

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 级联加载：加载 Node 和 Edge（聚合根特性）
        - 值对象转换：Position、NodeType、WorkflowStatus

        参数：
            model: WorkflowModel ORM 模型

        返回：
            Workflow 领域实体（包含所有 Node 和 Edge）
        """
        # 转换 Node
        nodes = [
            Node(
                id=node_model.id,
                type=NodeType(node_model.type),
                name=node_model.name,
                config=node_model.config,
                position=Position(x=node_model.position_x, y=node_model.position_y),
            )
            for node_model in model.nodes
        ]

        # 转换 Edge
        edges = [
            Edge(
                id=edge_model.id,
                source_node_id=edge_model.source_node_id,
                target_node_id=edge_model.target_node_id,
                condition=edge_model.condition,
            )
            for edge_model in model.edges
        ]

        # 转换 Workflow
        return Workflow(
            id=model.id,
            name=model.name,
            description=model.description,
            nodes=nodes,
            edges=edges,
            status=WorkflowStatus(model.status),
            created_at=model.created_at.replace(tzinfo=UTC),
            updated_at=model.updated_at.replace(tzinfo=UTC),
        )

    def _to_model(self, entity: Workflow) -> WorkflowModel:
        """将领域实体转换为 ORM 模型（聚合根）

        为什么需要这个方法？
        - 保存实体到数据库时需要 ORM 模型
        - 领域实体不应该知道数据库细节

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 级联保存：保存 Node 和 Edge（聚合根特性）
        - 值对象转换：Position、NodeType、WorkflowStatus

        参数：
            entity: Workflow 领域实体

        返回：
            WorkflowModel ORM 模型（包含所有 Node 和 Edge）
        """
        # 转换 Workflow
        model = WorkflowModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            status=entity.status.value,
            created_at=entity.created_at.replace(tzinfo=None),
            updated_at=entity.updated_at.replace(tzinfo=None),
        )

        # 转换 Node（级联）
        model.nodes = [
            NodeModel(
                id=node.id,
                workflow_id=entity.id,
                type=node.type.value,
                name=node.name,
                config=node.config,
                position_x=node.position.x,
                position_y=node.position.y,
            )
            for node in entity.nodes
        ]

        # 转换 Edge（级联）
        model.edges = [
            EdgeModel(
                id=edge.id,
                workflow_id=entity.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                condition=edge.condition,
            )
            for edge in entity.edges
        ]

        return model

    # ==================== Repository 方法 ====================
    # 职责：持久化操作

    def save(self, workflow: Workflow) -> None:
        """保存 Workflow 实体（新增或更新）

        实现策略：
        - 使用 merge()：自动判断新增或更新
        - 级联保存：自动保存 Node 和 Edge
        - 事务控制：由调用者控制（session.commit()）

        参数：
            workflow: Workflow 实体
        """
        model = self._to_model(workflow)
        self.session.merge(model)

    def get_by_id(self, workflow_id: str) -> Workflow:
        """根据 ID 获取 Workflow 实体（不存在抛异常）

        实现策略：
        - 使用 select() + scalars().first()
        - 级联加载：lazy="selectin" 自动加载 Node 和 Edge
        - 不存在抛出 NotFoundError

        参数：
            workflow_id: Workflow ID

        返回：
            Workflow 实体（包含所有 Node 和 Edge）

        抛出：
            NotFoundError: 当 Workflow 不存在时
        """
        stmt = select(WorkflowModel).where(WorkflowModel.id == workflow_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            raise NotFoundError(entity_type="Workflow", entity_id=workflow_id)

        return self._to_entity(model)

    def find_by_id(self, workflow_id: str) -> Workflow | None:
        """根据 ID 查找 Workflow 实体（不存在返回 None）

        实现策略：
        - 使用 select() + scalars().first()
        - 级联加载：lazy="selectin" 自动加载 Node 和 Edge
        - 不存在返回 None

        参数：
            workflow_id: Workflow ID

        返回：
            Workflow 实体（包含所有 Node 和 Edge）或 None
        """
        stmt = select(WorkflowModel).where(WorkflowModel.id == workflow_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            return None

        return self._to_entity(model)

    def find_all(self) -> list[Workflow]:
        """查找所有 Workflow

        实现策略：
        - 使用 select() + scalars().all()
        - 按 created_at 倒序排列
        - 级联加载：lazy="selectin" 自动加载 Node 和 Edge

        返回：
            Workflow 列表（可能为空）
        """
        stmt = select(WorkflowModel).order_by(WorkflowModel.created_at.desc())
        models = self.session.scalars(stmt).all()

        return [self._to_entity(model) for model in models]

    def exists(self, workflow_id: str) -> bool:
        """检查 Workflow 是否存在

        实现策略：
        - 使用 select(1) + exists()
        - 不加载实体（性能优化）

        参数：
            workflow_id: Workflow ID

        返回：
            True 表示存在，False 表示不存在
        """
        stmt = select(WorkflowModel.id).where(WorkflowModel.id == workflow_id)
        return self.session.scalar(stmt) is not None

    def delete(self, workflow_id: str) -> None:
        """删除 Workflow 实体

        实现策略：
        - 使用 delete() + where()
        - 级联删除：ondelete="CASCADE" 自动删除 Node 和 Edge
        - 幂等：多次删除不报错

        参数：
            workflow_id: Workflow ID
        """
        stmt = select(WorkflowModel).where(WorkflowModel.id == workflow_id)
        model = self.session.scalars(stmt).first()

        if model is not None:
            self.session.delete(model)

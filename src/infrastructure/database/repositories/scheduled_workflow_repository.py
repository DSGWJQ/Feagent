"""SQLAlchemy ScheduledWorkflow Repository 实现

Repository 职责：
1. 转换（Translation）：领域实体 ⇄ ORM 模型
2. 持久化（Persistence）：保存、查询、删除
3. 异常转换（Exception Translation）：数据库异常 → 领域异常
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.models import ScheduledWorkflowModel


class SQLAlchemyScheduledWorkflowRepository:
    """SQLAlchemy ScheduledWorkflow Repository 实现

    依赖：
    - Session: SQLAlchemy 同步会话（依赖注入）
    """

    def __init__(self, session: Session):
        """初始化 Repository

        参数：
            session: SQLAlchemy 同步会话
        """
        self.session = session

    # ==================== Assembler 方法 ====================
    # 职责：ORM 模型 ⇄ 领域实体转换

    def _to_entity(self, model: ScheduledWorkflowModel) -> ScheduledWorkflow:
        """将 ORM 模型转换为领域实体

        参数：
            model: ScheduledWorkflowModel ORM 模型

        返回：
            ScheduledWorkflow 领域实体
        """
        updated_at = model.updated_at or datetime.now(UTC)

        return ScheduledWorkflow(
            id=model.id,
            workflow_id=model.workflow_id,
            cron_expression=model.cron_expression,
            status=model.status,
            max_retries=model.max_retries,
            consecutive_failures=model.consecutive_failures,
            last_execution_at=model.last_execution_at,
            last_execution_status=model.last_execution_status,
            last_error_message=model.last_error_message,
            created_at=model.created_at,
            updated_at=updated_at,
        )

    def _to_model(self, entity: ScheduledWorkflow) -> ScheduledWorkflowModel:
        """将领域实体转换为 ORM 模型

        参数：
            entity: ScheduledWorkflow 领域实体

        返回：
            ScheduledWorkflowModel ORM 模型
        """
        return ScheduledWorkflowModel(
            id=entity.id,
            workflow_id=entity.workflow_id,
            cron_expression=entity.cron_expression,
            status=entity.status,
            max_retries=entity.max_retries,
            consecutive_failures=entity.consecutive_failures,
            last_execution_at=entity.last_execution_at,
            last_execution_status=entity.last_execution_status,
            last_error_message=entity.last_error_message,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    # ==================== CRUD 操作 ====================

    def save(self, entity: ScheduledWorkflow) -> None:
        """保存定时工作流

        参数：
            entity: ScheduledWorkflow 领域实体
        """
        # 检查是否已存在
        existing = (
            self.session.query(ScheduledWorkflowModel)
            .filter(ScheduledWorkflowModel.id == entity.id)
            .first()
        )

        if existing:
            # 更新现有记录
            existing.cron_expression = entity.cron_expression
            existing.status = entity.status
            existing.max_retries = entity.max_retries
            existing.consecutive_failures = entity.consecutive_failures
            existing.last_execution_at = entity.last_execution_at
            existing.last_execution_status = entity.last_execution_status
            existing.last_error_message = entity.last_error_message
            existing.updated_at = entity.updated_at
        else:
            # 插入新记录
            model = self._to_model(entity)
            self.session.add(model)

        self.session.commit()

    def get_by_id(self, scheduled_workflow_id: str) -> ScheduledWorkflow:
        """按 ID 获取定时工作流

        参数：
            scheduled_workflow_id: 定时工作流 ID

        返回：
            ScheduledWorkflow 领域实体

        抛出：
            NotFoundError: 定时工作流不存在
        """
        model = (
            self.session.query(ScheduledWorkflowModel)
            .filter(ScheduledWorkflowModel.id == scheduled_workflow_id)
            .first()
        )

        if not model:
            raise NotFoundError("ScheduledWorkflow", scheduled_workflow_id)

        return self._to_entity(model)

    def find_by_workflow_id(self, workflow_id: str) -> list[ScheduledWorkflow]:
        """按工作流 ID 查找定时工作流

        参数：
            workflow_id: 工作流 ID

        返回：
            ScheduledWorkflow 列表
        """
        models = (
            self.session.query(ScheduledWorkflowModel)
            .filter(ScheduledWorkflowModel.workflow_id == workflow_id)
            .all()
        )

        return [self._to_entity(model) for model in models]

    def find_all(self) -> list[ScheduledWorkflow]:
        """查找所有定时工作流

        返回：
            ScheduledWorkflow 列表
        """
        models = self.session.query(ScheduledWorkflowModel).all()
        return [self._to_entity(model) for model in models]

    def find_active(self) -> list[ScheduledWorkflow]:
        """查找所有活跃的定时工作流

        返回：
            活跃 ScheduledWorkflow 列表
        """
        models = (
            self.session.query(ScheduledWorkflowModel)
            .filter(ScheduledWorkflowModel.status == "active")
            .all()
        )

        return [self._to_entity(model) for model in models]

    def delete(self, scheduled_workflow_id: str) -> None:
        """删除定时工作流

        参数：
            scheduled_workflow_id: 定时工作流 ID

        抛出：
            NotFoundError: 定时工作流不存在
        """
        model = (
            self.session.query(ScheduledWorkflowModel)
            .filter(ScheduledWorkflowModel.id == scheduled_workflow_id)
            .first()
        )

        if not model:
            raise NotFoundError("ScheduledWorkflow", scheduled_workflow_id)

        self.session.delete(model)
        self.session.commit()

"""SQLAlchemy Run Repository 实现

第一性原理: Repository 是领域对象和数据存储之间的转换器

职责:
    1. 转换 (Translation): 领域实体 ↔ ORM 模型
    2. 持久化 (Persistence): 保存、查询、更新
    3. 异常转换 (Exception Translation): 数据库异常 → 领域异常

事务边界规则 (Phase 1):
    - Repository 不调用 session.commit()
    - 只使用 add/merge/flush/delete
    - 事务由 Application UseCase 控制
"""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.domain.entities.run import Run
from src.domain.exceptions import NotFoundError
from src.domain.value_objects.run_status import RunStatus
from src.infrastructure.database.models import RunModel


class SQLAlchemyRunRepository:
    """SQLAlchemy Run Repository 实现

    Implements:
        RunRepository Protocol (src/domain/ports/run_repository.py)
    """

    def __init__(self, session: Session) -> None:
        """初始化 Repository

        Args:
            session: SQLAlchemy Session (由依赖注入提供)
        """
        self.session = session

    # ==================== Assembler 方法 ====================

    def _to_entity(self, model: RunModel) -> Run:
        """ORM 模型 → 领域实体

        时区处理:
            - 数据库存储 naive datetime
            - 领域层使用 UTC aware datetime
        """
        # 时区转换: naive → UTC aware
        created_at = (
            model.created_at.replace(tzinfo=UTC)
            if model.created_at.tzinfo is None
            else model.created_at
        )

        finished_at = None
        if model.finished_at is not None:
            finished_at = (
                model.finished_at.replace(tzinfo=UTC)
                if model.finished_at.tzinfo is None
                else model.finished_at
            )

        return Run(
            id=model.id,
            project_id=model.project_id,
            workflow_id=model.workflow_id,
            status=RunStatus(model.status),
            created_at=created_at,
            finished_at=finished_at,
        )

    def _to_model(self, entity: Run) -> RunModel:
        """领域实体 → ORM 模型

        时区处理:
            - 领域层使用 UTC aware datetime
            - 数据库存储 naive datetime
        """
        # 时区转换: UTC aware → naive
        created_at = entity.created_at.replace(tzinfo=None)
        finished_at = (
            entity.finished_at.replace(tzinfo=None) if entity.finished_at is not None else None
        )

        return RunModel(
            id=entity.id,
            project_id=entity.project_id,
            workflow_id=entity.workflow_id,
            status=entity.status.value,
            created_at=created_at,
            finished_at=finished_at,
        )

    # ==================== Repository 方法 ====================

    def save(self, run: Run) -> None:
        """保存 Run (新增)

        语义: 创建新的 Run 记录
        实现: 使用 add() 明确新增

        Phase 1 规则: 只 add，不 commit
        """
        model = self._to_model(run)
        self.session.add(model)

    def update(self, run: Run) -> None:
        """更新 Run (必须已存在)

        语义: 更新已存在的 Run 记录
        实现: 使用 merge() 合并状态

        Phase 1 规则: 只 merge，不 commit
        """
        model = self._to_model(run)
        self.session.merge(model)

    def get_by_id(self, run_id: str) -> Run:
        """按 ID 获取 Run (不存在抛异常)

        Raises:
            NotFoundError: 当 Run 不存在时
        """
        stmt = select(RunModel).where(RunModel.id == run_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            raise NotFoundError(entity_type="Run", entity_id=run_id)

        return self._to_entity(model)

    def find_by_id(self, run_id: str) -> Run | None:
        """按 ID 查找 Run (不存在返回 None)"""
        stmt = select(RunModel).where(RunModel.id == run_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            return None

        return self._to_entity(model)

    def list_by_workflow_id(
        self,
        workflow_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Run]:
        """查询指定 Workflow 下的 Run 列表

        Returns:
            Run 列表，按 created_at 倒序排列 (最新在前)
        """
        stmt = (
            select(RunModel)
            .where(RunModel.workflow_id == workflow_id)
            .order_by(RunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = self.session.scalars(stmt).all()
        return [self._to_entity(model) for model in models]

    def list_by_project_id(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Run]:
        """查询指定 Project 下的 Run 列表

        Returns:
            Run 列表，按 created_at 倒序排列 (最新在前)
        """
        stmt = (
            select(RunModel)
            .where(RunModel.project_id == project_id)
            .order_by(RunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = self.session.scalars(stmt).all()
        return [self._to_entity(model) for model in models]

    def count_by_workflow_id(self, workflow_id: str) -> int:
        """统计指定 Workflow 下的 Run 数量"""
        stmt = select(func.count(RunModel.id)).where(RunModel.workflow_id == workflow_id)
        return int(self.session.scalar(stmt) or 0)

    def update_status_if_current(
        self,
        run_id: str,
        *,
        current_status: RunStatus,
        target_status: RunStatus,
        finished_at: datetime | None = None,
    ) -> bool:
        """条件更新状态 (乐观并发控制 / Compare-And-Swap)

        使用 UPDATE ... WHERE status = current_status 实现原子条件更新。
        只有当数据库中的状态等于 current_status 时，才会更新为 target_status。

        Args:
            run_id: Run ID
            current_status: 期望的当前状态
            target_status: 目标状态
            finished_at: 结束时间 (终态时设置，UTC aware)

        Returns:
            True 表示成功更新 1 行；False 表示状态不匹配
        """
        # 时区转换: UTC aware → naive (数据库存储格式)
        finished_at_naive = None
        if finished_at is not None:
            finished_at_naive = finished_at.replace(tzinfo=None)

        # 构建条件更新语句
        stmt = (
            update(RunModel)
            .where(RunModel.id == run_id)
            .where(RunModel.status == current_status.value)
            .values(
                status=target_status.value,
                finished_at=finished_at_naive,
            )
        )

        result = self.session.execute(stmt)
        return bool(result.rowcount == 1)

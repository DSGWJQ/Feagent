"""ScheduledWorkflow Repository - TDD RED 阶段测试

定义定时工作流仓库的持久化期望行为
"""

import pytest
from datetime import datetime, UTC
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.base import Base


class TestScheduledWorkflowRepository:
    """测试定时工作流仓库"""

    @pytest.fixture
    def db_session(self):
        """创建内存数据库会话"""
        # 使用 SQLite 内存数据库进行测试
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_save_scheduled_workflow(self, db_session):
        """测试：应该能保存定时工作流"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 创建定时工作流
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )

        # 保存
        repo.save(scheduled)

        # 验证可以查询到
        retrieved = repo.get_by_id(scheduled.id)
        assert retrieved is not None
        assert retrieved.workflow_id == "wf_123"
        assert retrieved.cron_expression == "0 9 * * MON-FRI"

    def test_get_scheduled_workflow_by_id(self, db_session):
        """测试：应该能按 ID 获取定时工作流"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 创建并保存
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_456",
            cron_expression="0 18 * * *",
            max_retries=5,
        )
        repo.save(scheduled)

        # 按 ID 查询
        retrieved = repo.get_by_id(scheduled.id)
        assert retrieved is not None
        assert retrieved.id == scheduled.id
        assert retrieved.status == "active"

    def test_get_scheduled_workflow_not_found(self, db_session):
        """测试：查询不存在的定时工作流应该抛出异常"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 查询不存在的 ID
        with pytest.raises(NotFoundError):
            repo.get_by_id("invalid_id")

    def test_find_scheduled_workflows_by_workflow_id(self, db_session):
        """测试：应该能按工作流 ID 查找定时任务"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 创建多个定时工作流
        sched1 = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )
        sched2 = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="0 18 * * MON-FRI",
            max_retries=3,
        )
        sched3 = ScheduledWorkflow.create(
            workflow_id="wf_456",
            cron_expression="0 12 * * *",
            max_retries=5,
        )

        repo.save(sched1)
        repo.save(sched2)
        repo.save(sched3)

        # 按工作流 ID 查找
        results = repo.find_by_workflow_id("wf_123")
        assert len(results) == 2
        assert all(r.workflow_id == "wf_123" for r in results)

    def test_find_all_scheduled_workflows(self, db_session):
        """测试：应该能查找所有定时工作流"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 创建多个
        for i in range(3):
            scheduled = ScheduledWorkflow.create(
                workflow_id=f"wf_{i}",
                cron_expression="0 9 * * *",
                max_retries=3,
            )
            repo.save(scheduled)

        # 查找所有
        results = repo.find_all()
        assert len(results) == 3

    def test_update_scheduled_workflow(self, db_session):
        """测试：应该能更新定时工作流"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 创建并保存
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )
        repo.save(scheduled)

        # 修改状态
        scheduled.disable()

        # 更新
        repo.save(scheduled)

        # 验证更新
        retrieved = repo.get_by_id(scheduled.id)
        assert retrieved.status == "disabled"

    def test_delete_scheduled_workflow(self, db_session):
        """测试：应该能删除定时工作流"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 创建并保存
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )
        repo.save(scheduled)
        scheduled_id = scheduled.id

        # 删除
        repo.delete(scheduled_id)

        # 验证已删除
        with pytest.raises(NotFoundError):
            repo.get_by_id(scheduled_id)

    def test_find_active_scheduled_workflows(self, db_session):
        """测试：应该能查找所有活跃的定时工作流"""
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        repo = SQLAlchemyScheduledWorkflowRepository(db_session)

        # 创建活跃和禁用的工作流
        active = ScheduledWorkflow.create(
            workflow_id="wf_1",
            cron_expression="0 9 * * *",
            max_retries=3,
        )
        disabled = ScheduledWorkflow.create(
            workflow_id="wf_2",
            cron_expression="0 9 * * *",
            max_retries=3,
        )
        disabled.disable()

        repo.save(active)
        repo.save(disabled)

        # 查找活跃的
        results = repo.find_active()
        assert len(results) == 1
        assert results[0].status == "active"

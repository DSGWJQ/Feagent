"""调度器集成测试 - TDD RED 阶段

定义定时工作流的实际执行行为：
1. 调度器接收定时工作流配置
2. 在指定时间触发工作流执行
3. 记录执行结果
4. 支持暂停、删除、修改调度
"""

from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import WorkflowModel
from src.infrastructure.database.repositories.scheduled_workflow_repository import (
    SQLAlchemyScheduledWorkflowRepository,
)


class TestSchedulerIntegration:
    """调度器 + 定时工作流集成测试

    验证：
    1. 定时工作流可以被调度
    2. 在指定时间执行
    3. 执行结果被记录
    4. 调度生命周期（启动、暂停、删除）
    """

    @pytest.fixture
    def db_setup(self):
        """创建内存数据库"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # 创建测试工作流
        workflow = WorkflowModel(
            id="wf_scheduler_test",
            name="Test Workflow",
            description="用于调度器测试",
            nodes=[],
            edges=[],
            status="active",
        )
        session.add(workflow)
        session.commit()

        yield session
        session.close()

    def test_schedule_workflow_for_immediate_execution(self, db_setup):
        """测试：应该能调度一个工作流立即执行

        RED 阶段期望：
        - ScheduleWorkflowService 接收定时工作流配置
        - 返回一个 job_id
        - job_id 可以用于追踪执行
        """
        from src.domain.services.workflow_scheduler import ScheduleWorkflowService

        repo = SQLAlchemyScheduledWorkflowRepository(db_setup)

        # 创建定时工作流
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_scheduler_test",
            cron_expression="* * * * *",  # 每分钟执行一次
            max_retries=3,
        )
        repo.save(scheduled)

        # 创建调度器服务
        scheduler_service = ScheduleWorkflowService(
            scheduled_workflow_repo=repo,
            workflow_executor=Mock(),  # 暂时 mock 工作流执行器
        )

        # 启动调度器
        scheduler_service.start()

        try:
            # 检查工作流是否已被注册到调度器
            scheduled_job = scheduler_service.get_scheduled_job(scheduled.id)
            assert scheduled_job is not None, "工作流应该被注册到调度器"
            assert scheduled_job.id == scheduled.id
            assert scheduled_job.name == f"scheduled_workflow_{scheduled.id}"
        finally:
            # 清理：停止调度器
            scheduler_service.stop()

    def test_scheduled_workflow_execution_is_recorded(self, db_setup):
        """测试：工作流执行结果应该被记录

        RED 阶段期望：
        - 工作流执行时，记录执行时间和结果
        - 可以查询执行历史
        - 失败时自动禁用
        """
        from src.domain.services.workflow_scheduler import ScheduleWorkflowService

        repo = SQLAlchemyScheduledWorkflowRepository(db_setup)

        # 创建定时工作流（max_retries=1 用于快速测试）
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_scheduler_test",
            cron_expression="* * * * *",
            max_retries=1,
        )
        repo.save(scheduled)

        # mock 工作流执行器
        executor_mock = Mock()
        executor_mock.execute_workflow = Mock(return_value={"status": "success"})

        # 创建调度器服务
        scheduler_service = ScheduleWorkflowService(
            scheduled_workflow_repo=repo,
            workflow_executor=executor_mock,
        )

        scheduler_service.start()

        try:
            # 手动触发执行（用于测试）
            scheduler_service.trigger_execution(scheduled.id)

            # 验证工作流执行器被调用了
            executor_mock.execute_workflow.assert_called_once()

            # 验证执行记录已保存
            updated = repo.get_by_id(scheduled.id)
            assert updated.last_execution_status == "success"
            assert updated.last_execution_at is not None
        finally:
            scheduler_service.stop()

    def test_remove_scheduled_workflow_from_scheduler(self, db_setup):
        """测试：应该能从调度器中移除定时工作流

        RED 阶段期望：
        - 删除定时工作流时，同时从调度器中移除
        - 之后不再执行
        """
        from src.domain.services.workflow_scheduler import ScheduleWorkflowService

        repo = SQLAlchemyScheduledWorkflowRepository(db_setup)

        # 创建定时工作流
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_scheduler_test",
            cron_expression="* * * * *",
            max_retries=3,
        )
        repo.save(scheduled)

        scheduler_service = ScheduleWorkflowService(
            scheduled_workflow_repo=repo,
            workflow_executor=Mock(),
        )

        scheduler_service.start()

        try:
            # 验证工作流已被注册
            assert scheduler_service.get_scheduled_job(scheduled.id) is not None

            # 删除定时工作流
            scheduler_service.unschedule_workflow(scheduled.id)
            repo.delete(scheduled.id)

            # 验证已从调度器中移除
            assert scheduler_service.get_scheduled_job(scheduled.id) is None
        finally:
            scheduler_service.stop()

    def test_pause_and_resume_scheduled_workflow(self, db_setup):
        """测试：应该能暂停和恢复定时工作流执行

        RED 阶段期望：
        - 暂停时：禁用调度（不执行）
        - 恢复时：重新启用调度（继续执行）
        """
        from src.domain.services.workflow_scheduler import ScheduleWorkflowService

        repo = SQLAlchemyScheduledWorkflowRepository(db_setup)

        # 创建定时工作流
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_scheduler_test",
            cron_expression="* * * * *",
            max_retries=3,
        )
        repo.save(scheduled)

        scheduler_service = ScheduleWorkflowService(
            scheduled_workflow_repo=repo,
            workflow_executor=Mock(),
        )

        scheduler_service.start()

        try:
            # 暂停定时工作流
            scheduler_service.pause_scheduled_workflow(scheduled.id)

            # 验证状态为 disabled
            paused = repo.get_by_id(scheduled.id)
            assert paused.status == "disabled"

            # 恢复定时工作流
            scheduler_service.resume_scheduled_workflow(scheduled.id)

            # 验证状态回到 active
            resumed = repo.get_by_id(scheduled.id)
            assert resumed.status == "active"
        finally:
            scheduler_service.stop()

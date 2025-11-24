"""WorkflowScheduler与执行器完整集成测试

TDD RED阶段：先编写测试用例，明确调度器与执行器的完整集成需求

测试覆盖：
1. 调度器自动启动和加载活跃任务
2. 定时任务的完整执行流程
3. 执行失败时的自动重试和禁用机制
4. 调度器生命周期管理（启动/停止）
5. 手动触发执行功能
6. 调度监控API
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.application.use_cases.schedule_workflow import (
    ScheduleWorkflowInput,
    ScheduleWorkflowUseCase,
)
from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_scheduler import ScheduleWorkflowService
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import WorkflowModel
from src.infrastructure.database.repositories.scheduled_workflow_repository import (
    SQLAlchemyScheduledWorkflowRepository,
)
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.services.workflow_executor_adapter import (
    WorkflowExecutorAdapter,
)


@pytest.mark.integration
class TestSchedulerIntegrationComplete:
    """WorkflowScheduler与执行器完整集成测试"""

    @pytest.fixture
    def db_setup(self):
        """创建测试数据库和会话"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # 创建测试工作流
        workflow = WorkflowModel(
            id="wf_123",
            name="Test Workflow",
            description="A test workflow",
            nodes=[],
            edges=[],
            status="published",  # 使用正确的状态值
        )
        session.add(workflow)
        session.commit()

        yield session
        session.close()

    def _create_repositories(self, session: Session):
        """创建仓库实例"""
        workflow_repo = SQLAlchemyWorkflowRepository(session)
        scheduled_repo = SQLAlchemyScheduledWorkflowRepository(session)
        return workflow_repo, scheduled_repo

    def _create_executor(self):
        """创建工作流执行器"""
        return WorkflowExecutorAdapter()

    def _create_scheduler_service(self, scheduled_repo, executor):
        """创建调度器服务"""
        return ScheduleWorkflowService(
            scheduled_workflow_repo=scheduled_repo,
            workflow_executor=executor,
        )

    def test_scheduler_should_start_and_load_active_tasks(self, db_setup):
        """测试：调度器启动时应该自动加载所有活跃任务"""
        # Arrange
        workflow_repo, scheduled_repo = self._create_repositories(db_setup)
        executor = self._create_executor()
        scheduler = self._create_scheduler_service(scheduled_repo, executor)

        # 创建活跃的定时任务
        scheduled1 = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="*/1 * * * *",  # 每分钟执行
            max_retries=2,
        )
        scheduled_repo.save(scheduled1)

        # Act
        scheduler.start()

        # Assert
        assert scheduler._is_running, "调度器应该处于运行状态"

        # 验证任务已添加到调度器
        job = scheduler.get_scheduled_job(scheduled1.id)
        assert job is not None, "活跃任务应该被加载到调度器中"
        assert job.name == f"scheduled_workflow_{scheduled1.id}"

        # Cleanup
        scheduler.stop()

    def test_scheduler_should_execute_workflow_on_schedule(self, db_setup):
        """测试：调度器应该按计划执行工作流"""
        # Arrange
        workflow_repo, scheduled_repo = self._create_repositories(db_setup)
        executor = self._create_executor()
        scheduler = self._create_scheduler_service(scheduled_repo, executor)

        # 创建定时任务
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="*/1 * * * *",
            max_retries=2,
        )
        scheduled_repo.save(scheduled)

        # Mock执行器以验证调用
        with patch.object(executor, 'execute_workflow') as mock_execute:
            mock_execute.return_value = {"status": "success"}

            scheduler.start()

            # Act - 手动触发执行
            result = scheduler.trigger_execution(scheduled.id)

            # Assert
            assert result["status"] == "success", "执行应该成功"
            mock_execute.assert_called_once_with(
                workflow_id="wf_123",
                input_data={},
            )

            # 验证执行记录已保存
            updated = scheduled_repo.get_by_id(scheduled.id)
            assert updated.last_execution_status == "success"
            assert updated.last_execution_at is not None

        # Cleanup
        scheduler.stop()

    def test_scheduler_should_handle_execution_failure_and_retry(self, db_setup):
        """测试：调度器应该处理执行失败并重试"""
        # Arrange
        workflow_repo, scheduled_repo = self._create_repositories(db_setup)
        executor = self._create_executor()
        scheduler = self._create_scheduler_service(scheduled_repo, executor)

        # 创建定时任务
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="*/1 * * * *",
            max_retries=2,
        )
        scheduled_repo.save(scheduled)

        # Mock执行器抛出异常
        with patch.object(executor, 'execute_workflow') as mock_execute:
            mock_execute.side_effect = Exception("工作流执行失败")

            scheduler.start()

            # Act - 执行3次（达到max_retries）
            for i in range(3):
                try:
                    scheduler.trigger_execution(scheduled.id)
                except Exception:
                    pass  # 忽略执行异常，我们关注记录状态

            # Assert
            updated = scheduled_repo.get_by_id(scheduled.id)
            assert updated.last_execution_status == "failure"
            assert updated.consecutive_failures == 3
            assert updated.status == "disabled", "达到重试限制应该自动禁用"
            assert "工作流执行失败" in updated.last_error_message

        # Cleanup
        scheduler.stop()

    def test_scheduler_should_support_pause_and_resume(self, db_setup):
        """测试：调度器应该支持暂停和恢复任务"""
        # Arrange
        workflow_repo, scheduled_repo = self._create_repositories(db_setup)
        executor = self._create_executor()
        scheduler = self._create_scheduler_service(scheduled_repo, executor)

        # 创建定时任务
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="*/1 * * * *",
            max_retries=2,
        )
        scheduled_repo.save(scheduled)

        scheduler.start()

        # 验证任务已加载
        job_before_pause = scheduler.get_scheduled_job(scheduled.id)
        assert job_before_pause is not None

        # Act - 暂停任务
        scheduler.pause_scheduled_workflow(scheduled.id)

        # Assert
        job_after_pause = scheduler.get_scheduled_job(scheduled.id)
        assert job_after_pause is None, "暂停后任务应该从调度器中移除"

        updated_after_pause = scheduled_repo.get_by_id(scheduled.id)
        assert updated_after_pause.status == "disabled"

        # Act - 恢复任务
        scheduler.resume_scheduled_workflow(scheduled.id)

        # Assert
        job_after_resume = scheduler.get_scheduled_job(scheduled.id)
        assert job_after_resume is not None, "恢复后任务应该重新添加到调度器"

        updated_after_resume = scheduled_repo.get_by_id(scheduled.id)
        assert updated_after_resume.status == "active"
        assert updated_after_resume.consecutive_failures == 0, "恢复时应该重置失败计数"

        # Cleanup
        scheduler.stop()

    def test_scheduler_should_provide_monitoring_information(self, db_setup):
        """测试：调度器应该提供监控信息"""
        # Arrange
        workflow_repo, scheduled_repo = self._create_repositories(db_setup)
        executor = self._create_executor()
        scheduler = self._create_scheduler_service(scheduled_repo, executor)

        # 创建多个不同状态的任务
        active_task = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="*/1 * * * *",
            max_retries=2,
        )
        scheduled_repo.save(active_task)

        paused_task = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="*/2 * * * *",
            max_retries=1,
        )
        paused_task.disable()
        scheduled_repo.save(paused_task)

        scheduler.start()

        # Act & Assert
        assert scheduler._is_running, "调度器应该在运行"

        # 验证活跃任务在调度器中
        active_job = scheduler.get_scheduled_job(active_task.id)
        assert active_job is not None

        # 验证暂停任务不在调度器中
        paused_job = scheduler.get_scheduled_job(paused_task.id)
        assert paused_job is None

        # Cleanup
        scheduler.stop()
        assert not scheduler._is_running, "调度器应该已停止"

    def test_scheduler_use_case_integration(self, db_setup):
        """测试：调度器通过UseCase的完整集成"""
        # Arrange
        workflow_repo, scheduled_repo = self._create_repositories(db_setup)
        executor = self._create_executor()
        scheduler = self._create_scheduler_service(scheduled_repo, executor)

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=workflow_repo,
            scheduled_workflow_repo=scheduled_repo,
            scheduler=scheduler,
        )

        # Act - 创建定时任务
        input_data = ScheduleWorkflowInput(
            workflow_id="wf_123",
            cron_expression="*/5 * * * *",
            max_retries=3,
        )
        result = use_case.execute(input_data)

        # Assert
        assert result.workflow_id == "wf_123"
        assert result.cron_expression == "*/5 * * * *"
        assert result.status == "active"

        # 验证任务已被添加到调度器
        scheduler.start()
        job = scheduler.get_scheduled_job(result.id)
        assert job is not None

        # 验证可以列出任务
        tasks = use_case.list_scheduled_workflows()
        assert len(tasks) >= 1
        assert any(t.id == result.id for t in tasks)

        # Cleanup
        scheduler.stop()
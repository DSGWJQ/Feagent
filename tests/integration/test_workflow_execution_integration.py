"""工作流执行集成测试 - TDD RED 阶段

定义真实工作流执行的端到端行为：
1. 创建定时工作流 → 调度 → 执行 → 记录结果
2. 验证每个步骤的完整流程
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
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)


class TestWorkflowExecutionIntegration:
    """工作流执行端到端集成测试

    验证完整的调度 → 执行 → 追踪流程
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
            id="wf_exec_test",
            name="Test Execution Workflow",
            description="用于执行测试",
            nodes=[],
            edges=[],
            status="published",  # WorkflowModel 状态应该是 draft/published/archived
        )
        session.add(workflow)
        session.commit()

        yield session
        session.close()

    def test_end_to_end_schedule_and_execute_workflow(self, db_setup):
        """测试：从 API 创建定时工作流到自动执行的完整流程

        RED 阶段期望流程：
        1. 通过 API 创建定时工作流配置
        2. 调度器加载并注册工作流
        3. 触发执行（模拟时间到达）
        4. 记录执行结果
        5. 验证数据库的执行历史
        """
        from src.application.use_cases.schedule_workflow import (
            ScheduleWorkflowInput,
            ScheduleWorkflowUseCase,
        )
        from src.domain.services.workflow_scheduler import ScheduleWorkflowService
        from src.interfaces.api.services.workflow_executor_adapter import (
            WorkflowExecutorAdapter,
        )

        scheduled_repo = SQLAlchemyScheduledWorkflowRepository(db_setup)
        workflow_repo = SQLAlchemyWorkflowRepository(db_setup)

        # 1. 通过 UseCase 创建定时工作流
        executor = WorkflowExecutorAdapter()
        scheduler = ScheduleWorkflowService(
            scheduled_workflow_repo=scheduled_repo,
            workflow_executor=executor,
        )

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=workflow_repo,
            scheduled_workflow_repo=scheduled_repo,
            scheduler=scheduler,
        )

        input_data = ScheduleWorkflowInput(
            workflow_id="wf_exec_test",
            cron_expression="* * * * *",  # 每分钟
            max_retries=3,
        )

        result = use_case.execute(input_data)
        assert result is not None
        assert result.status == "active"

        # 2. 启动调度器
        scheduler.start()

        try:
            # 3. 手动触发执行（模拟时间到达）
            execution_result = scheduler.trigger_execution(result.id)
            assert execution_result["status"] == "success"

            # 4. 验证执行记录已保存
            updated = scheduled_repo.get_by_id(result.id)
            assert updated.last_execution_status == "success"
            assert updated.last_execution_at is not None
            assert updated.consecutive_failures == 0

        finally:
            scheduler.stop()

    def test_workflow_execution_with_failure_and_auto_disable(self, db_setup):
        """测试：工作流执行失败时的自动禁用逻辑

        RED 阶段期望：
        1. 创建 max_retries=2 的定时工作流
        2. 第 1 次失败 → 记录但仍保持 active
        3. 第 2 次失败 → 自动禁用（consecutive_failures >= max_retries）
        """
        from src.domain.services.workflow_scheduler import ScheduleWorkflowService

        scheduled_repo = SQLAlchemyScheduledWorkflowRepository(db_setup)

        # 创建定时工作流 max_retries=2
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_exec_test",
            cron_expression="* * * * *",
            max_retries=2,
        )
        scheduled_repo.save(scheduled)

        # 创建会失败的执行器
        failing_executor = Mock()
        failing_executor.execute_workflow = Mock(side_effect=Exception("模拟执行失败"))

        scheduler = ScheduleWorkflowService(
            scheduled_workflow_repo=scheduled_repo,
            workflow_executor=failing_executor,
        )

        scheduler.start()

        try:
            # 第 1 次失败
            scheduler.trigger_execution(scheduled.id)
            after_first_failure = scheduled_repo.get_by_id(scheduled.id)
            assert after_first_failure.consecutive_failures == 1
            assert after_first_failure.status == "active"  # 1 < 2，仍然 active

            # 第 2 次失败 → 自动禁用（2 >= 2）
            scheduler.trigger_execution(scheduled.id)
            after_second_failure = scheduled_repo.get_by_id(scheduled.id)
            assert after_second_failure.consecutive_failures == 2
            assert after_second_failure.status == "disabled"  # 自动禁用

        finally:
            scheduler.stop()

    def test_successful_execution_resets_failure_count(self, db_setup):
        """测试：成功执行会重置失败计数

        RED 阶段期望：
        1. 记录 1 次失败
        2. 执行成功 → 失败计数重置为 0
        """
        from src.domain.services.workflow_scheduler import ScheduleWorkflowService

        scheduled_repo = SQLAlchemyScheduledWorkflowRepository(db_setup)

        # 创建定时工作流
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_exec_test",
            cron_expression="* * * * *",
            max_retries=3,
        )
        scheduled_repo.save(scheduled)

        # 先记录一次失败
        scheduled.record_execution_failure("初始失败")
        scheduled_repo.save(scheduled)

        assert scheduled_repo.get_by_id(scheduled.id).consecutive_failures == 1

        # 创建成功的执行器
        success_executor = Mock()
        success_executor.execute_workflow = Mock(return_value={"status": "success"})

        scheduler = ScheduleWorkflowService(
            scheduled_workflow_repo=scheduled_repo,
            workflow_executor=success_executor,
        )

        scheduler.start()

        try:
            # 执行成功
            scheduler.trigger_execution(scheduled.id)

            # 验证失败计数已重置
            after_success = scheduled_repo.get_by_id(scheduled.id)
            assert after_success.consecutive_failures == 0
            assert after_success.last_execution_status == "success"

        finally:
            scheduler.stop()

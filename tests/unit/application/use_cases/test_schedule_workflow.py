"""ScheduleWorkflowUseCase - TDD RED 阶段测试

定义为工作流创建定时任务的期望行为
"""

from unittest.mock import Mock

import pytest

from src.domain.exceptions import NotFoundError


class TestScheduleWorkflowUseCase:
    """测试定时工作流用例"""

    @pytest.fixture
    def mock_workflow_repo(self):
        """模拟工作流仓库"""
        return Mock()

    @pytest.fixture
    def mock_scheduled_workflow_repo(self):
        """模拟定时工作流仓库"""
        return Mock()

    @pytest.fixture
    def mock_scheduler(self):
        """模拟调度器"""
        return Mock()

    def test_schedule_workflow_with_valid_inputs(
        self, mock_workflow_repo, mock_scheduled_workflow_repo, mock_scheduler
    ):
        """测试：使用有效输入为工作流创建定时任务"""
        from src.application.use_cases.schedule_workflow import (
            ScheduleWorkflowInput,
            ScheduleWorkflowUseCase,
        )

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            scheduled_workflow_repo=mock_scheduled_workflow_repo,
            scheduler=mock_scheduler,
        )

        # 模拟工作流存在
        mock_wf = Mock()
        mock_wf.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_wf

        input_data = ScheduleWorkflowInput(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )

        result = use_case.execute(input_data)

        assert result is not None
        assert result.workflow_id == "wf_123"
        assert result.cron_expression == "0 9 * * MON-FRI"
        assert result.status == "active"

    def test_schedule_workflow_checks_workflow_exists(
        self, mock_workflow_repo, mock_scheduled_workflow_repo, mock_scheduler
    ):
        """测试：定时工作流前应该检查工作流存在"""
        from src.application.use_cases.schedule_workflow import (
            ScheduleWorkflowInput,
            ScheduleWorkflowUseCase,
        )

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            scheduled_workflow_repo=mock_scheduled_workflow_repo,
            scheduler=mock_scheduler,
        )

        # 模拟工作流不存在
        mock_workflow_repo.get_by_id.side_effect = NotFoundError("Workflow", "wf_invalid")

        input_data = ScheduleWorkflowInput(
            workflow_id="wf_invalid",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )

        with pytest.raises(NotFoundError):
            use_case.execute(input_data)

    def test_schedule_workflow_saves_to_repository(
        self, mock_workflow_repo, mock_scheduled_workflow_repo, mock_scheduler
    ):
        """测试：应该将定时任务保存到仓库"""
        from src.application.use_cases.schedule_workflow import (
            ScheduleWorkflowInput,
            ScheduleWorkflowUseCase,
        )

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            scheduled_workflow_repo=mock_scheduled_workflow_repo,
            scheduler=mock_scheduler,
        )

        mock_wf = Mock()
        mock_wf.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_wf

        input_data = ScheduleWorkflowInput(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )

        use_case.execute(input_data)

        # 验证保存被调用
        assert mock_scheduled_workflow_repo.save.called

    def test_schedule_workflow_registers_with_scheduler(
        self, mock_workflow_repo, mock_scheduled_workflow_repo, mock_scheduler
    ):
        """测试：应该在调度器中注册定时任务"""
        from src.application.use_cases.schedule_workflow import (
            ScheduleWorkflowInput,
            ScheduleWorkflowUseCase,
        )

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            scheduled_workflow_repo=mock_scheduled_workflow_repo,
            scheduler=mock_scheduler,
        )

        mock_wf = Mock()
        mock_wf.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_wf

        input_data = ScheduleWorkflowInput(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )

        use_case.execute(input_data)

        # 验证调度器注册被调用
        assert mock_scheduler.add_job.called

    def test_unschedule_workflow(
        self, mock_workflow_repo, mock_scheduled_workflow_repo, mock_scheduler
    ):
        """测试：应该能移除定时任务"""
        from src.application.use_cases.schedule_workflow import (
            ScheduleWorkflowUseCase,
            UnscheduleWorkflowInput,
        )

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            scheduled_workflow_repo=mock_scheduled_workflow_repo,
            scheduler=mock_scheduler,
        )

        mock_scheduled = Mock()
        mock_scheduled.id = "scheduled_123"
        mock_scheduled_workflow_repo.get_by_id.return_value = mock_scheduled

        input_data = UnscheduleWorkflowInput(scheduled_workflow_id="scheduled_123")

        use_case.unschedule(input_data)

        # 验证删除被调用
        assert mock_scheduled_workflow_repo.delete.called
        assert mock_scheduler.remove_job.called

    def test_list_scheduled_workflows(
        self, mock_workflow_repo, mock_scheduled_workflow_repo, mock_scheduler
    ):
        """测试：应该能列出所有定时任务"""
        from src.application.use_cases.schedule_workflow import ScheduleWorkflowUseCase

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            scheduled_workflow_repo=mock_scheduled_workflow_repo,
            scheduler=mock_scheduler,
        )

        # 模拟返回定时任务列表
        mock_scheduled = [Mock(), Mock()]
        mock_scheduled_workflow_repo.find_all.return_value = mock_scheduled

        result = use_case.list_scheduled_workflows()

        assert len(result) == 2
        assert mock_scheduled_workflow_repo.find_all.called

    def test_get_scheduled_workflow_details(
        self, mock_workflow_repo, mock_scheduled_workflow_repo, mock_scheduler
    ):
        """测试：应该能获取定时任务详情"""
        from src.application.use_cases.schedule_workflow import ScheduleWorkflowUseCase

        use_case = ScheduleWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            scheduled_workflow_repo=mock_scheduled_workflow_repo,
            scheduler=mock_scheduler,
        )

        mock_scheduled = Mock()
        mock_scheduled.id = "scheduled_123"
        mock_scheduled.workflow_id = "wf_123"
        mock_scheduled_workflow_repo.get_by_id.return_value = mock_scheduled

        result = use_case.get_scheduled_workflow_details("scheduled_123")

        assert result is not None
        assert result.id == "scheduled_123"

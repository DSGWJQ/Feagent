"""ScheduledWorkflow 实体 - TDD RED 阶段测试

定义定时工作流的期望行为
"""

from datetime import UTC, datetime

import pytest

from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.exceptions import DomainError


@pytest.fixture
def sample_scheduled_workflow():
    """创建示例定时工作流"""
    return ScheduledWorkflow.create(
        workflow_id="wf_123",
        cron_expression="0 9 * * MON-FRI",
        max_retries=3,
    )


class TestScheduledWorkflowCreation:
    """测试定时工作流创建"""

    def test_create_scheduled_workflow_with_valid_inputs(self):
        """测试：使用有效输入创建定时工作流应该成功"""
        wf = ScheduledWorkflow.create(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )

        assert wf.id is not None
        assert wf.workflow_id == "wf_123"
        assert wf.cron_expression == "0 9 * * MON-FRI"
        assert wf.max_retries == 3
        assert wf.status == "active"
        assert wf.created_at is not None

    def test_create_scheduled_workflow_without_workflow_id_should_fail(self):
        """测试：缺少 workflow_id 应该抛出 DomainError"""
        with pytest.raises(DomainError, match="workflow_id"):
            ScheduledWorkflow.create(
                workflow_id="",
                cron_expression="0 9 * * MON-FRI",
                max_retries=3,
            )

    def test_create_scheduled_workflow_with_invalid_cron_should_fail(self):
        """测试：无效的 cron 表达式应该抛出 DomainError"""
        with pytest.raises(DomainError, match="cron"):
            ScheduledWorkflow.create(
                workflow_id="wf_123",
                cron_expression="invalid_cron",
                max_retries=3,
            )

    def test_create_scheduled_workflow_with_negative_retries_should_fail(self):
        """测试：负数重试次数应该抛出 DomainError"""
        with pytest.raises(DomainError, match="max_retries"):
            ScheduledWorkflow.create(
                workflow_id="wf_123",
                cron_expression="0 9 * * MON-FRI",
                max_retries=-1,
            )


class TestScheduledWorkflowStatus:
    """测试定时工作流状态管理"""

    def test_scheduled_workflow_initial_status_is_active(self, sample_scheduled_workflow):
        """测试：新创建的定时工作流状态应该是 active"""
        assert sample_scheduled_workflow.status == "active"

    def test_disable_scheduled_workflow(self, sample_scheduled_workflow):
        """测试：应该能禁用定时工作流"""
        sample_scheduled_workflow.disable()

        assert sample_scheduled_workflow.status == "disabled"
        assert sample_scheduled_workflow.updated_at > sample_scheduled_workflow.created_at

    def test_enable_scheduled_workflow(self, sample_scheduled_workflow):
        """测试：应该能启用禁用的定时工作流"""
        sample_scheduled_workflow.disable()
        sample_scheduled_workflow.enable()

        assert sample_scheduled_workflow.status == "active"

    def test_cannot_disable_already_disabled_workflow(self, sample_scheduled_workflow):
        """测试：禁用已禁用的工作流应该抛出异常"""
        sample_scheduled_workflow.disable()

        with pytest.raises(DomainError):
            sample_scheduled_workflow.disable()

    def test_cannot_enable_already_enabled_workflow(self, sample_scheduled_workflow):
        """测试：启用已启用的工作流应该抛出异常"""
        with pytest.raises(DomainError):
            sample_scheduled_workflow.enable()


class TestScheduledWorkflowExecution:
    """测试定时工作流执行相关逻辑"""

    def test_track_execution_success(self, sample_scheduled_workflow):
        """测试：应该能记录成功的执行"""
        sample_scheduled_workflow.record_execution_success()

        assert sample_scheduled_workflow.last_execution_at is not None
        assert sample_scheduled_workflow.last_execution_status == "success"
        assert sample_scheduled_workflow.consecutive_failures == 0

    def test_track_execution_failure(self, sample_scheduled_workflow):
        """测试：应该能记录失败的执行"""
        sample_scheduled_workflow.record_execution_failure("Test error")

        assert sample_scheduled_workflow.last_execution_at is not None
        assert sample_scheduled_workflow.last_execution_status == "failure"
        assert sample_scheduled_workflow.consecutive_failures == 1
        assert "Test error" in sample_scheduled_workflow.last_error_message

    def test_consecutive_failures_increment(self, sample_scheduled_workflow):
        """测试：连续失败次数应该递增"""
        sample_scheduled_workflow.record_execution_failure("Error 1")
        sample_scheduled_workflow.record_execution_failure("Error 2")
        sample_scheduled_workflow.record_execution_failure("Error 3")

        assert sample_scheduled_workflow.consecutive_failures == 3

    def test_consecutive_failures_reset_on_success(self, sample_scheduled_workflow):
        """测试：成功执行应该重置连续失败计数"""
        sample_scheduled_workflow.record_execution_failure("Error")
        sample_scheduled_workflow.record_execution_failure("Error")
        sample_scheduled_workflow.record_execution_success()

        assert sample_scheduled_workflow.consecutive_failures == 0
        assert sample_scheduled_workflow.last_execution_status == "success"

    def test_auto_disable_on_too_many_failures(self, sample_scheduled_workflow):
        """测试：超过最大重试次数应该自动禁用"""
        # 设置 max_retries = 3
        for i in range(3):
            sample_scheduled_workflow.record_execution_failure(f"Error {i}")

        # 再失败一次应该自动禁用
        sample_scheduled_workflow.record_execution_failure("Error 4")

        assert sample_scheduled_workflow.status == "disabled"


class TestScheduledWorkflowValidation:
    """测试定时工作流验证"""

    def test_validate_cron_expression_simple(self):
        """测试：验证简单的 cron 表达式"""
        valid_expressions = [
            "0 9 * * MON-FRI",  # 工作日 9 点
            "*/5 * * * *",  # 每 5 分钟
            "0 0 1 * *",  # 每月 1 号
            "0 0 * * 0",  # 每周日
        ]

        for expr in valid_expressions:
            wf = ScheduledWorkflow.create(
                workflow_id="wf_test",
                cron_expression=expr,
                max_retries=1,
            )
            assert wf.cron_expression == expr

    def test_invalid_cron_expression_should_fail(self):
        """测试：无效的 cron 表达式应该失败"""
        invalid_expressions = [
            "invalid",
            "99 99 99 99 99",
            "",
            "not a cron",
        ]

        for expr in invalid_expressions:
            with pytest.raises(DomainError):
                ScheduledWorkflow.create(
                    workflow_id="wf_test",
                    cron_expression=expr,
                    max_retries=1,
                )


class TestScheduledWorkflowNextExecution:
    """测试下次执行时间计算"""

    def test_calculate_next_execution_time(self, sample_scheduled_workflow):
        """测试：应该能计算下次执行时间"""
        next_time = sample_scheduled_workflow.get_next_execution_time()

        assert next_time is not None
        assert isinstance(next_time, datetime)
        # 下次执行时间应该在未来
        assert next_time > datetime.now(UTC)

    def test_next_execution_time_updates_after_run(self, sample_scheduled_workflow):
        """测试：执行后下次执行时间应该更新"""
        first_next_time = sample_scheduled_workflow.get_next_execution_time()

        sample_scheduled_workflow.record_execution_success()

        second_next_time = sample_scheduled_workflow.get_next_execution_time()

        # 第二个执行时间应该在第一个之后或相同（因为cron是5分钟精度）
        assert second_next_time >= first_next_time
        # 最后执行时间应该被记录
        assert sample_scheduled_workflow.last_execution_at is not None

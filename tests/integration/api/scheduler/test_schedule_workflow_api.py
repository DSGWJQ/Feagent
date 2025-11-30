"""Schedule Workflow API - TDD RED 阶段测试

定义工作流调度 API 的期望行为
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


class TestScheduleWorkflowAPI:
    """测试工作流调度 API 端点"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    def test_schedule_workflow_post_creates_scheduled_workflow(self, client):
        """测试：POST /api/workflows/{workflow_id}/schedule 应该创建定时任务"""
        with patch(
            "src.application.use_cases.schedule_workflow.ScheduleWorkflowUseCase"
        ) as mock_use_case_class:
            # Mock the use case
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock the result
            mock_result = Mock()
            mock_result.id = "scheduled_123"
            mock_result.workflow_id = "wf_123"
            mock_result.cron_expression = "0 9 * * MON-FRI"
            mock_result.status = "active"
            mock_use_case.execute.return_value = mock_result

            response = client.post(
                "/api/workflows/wf_123/schedule",
                json={
                    "cron_expression": "0 9 * * MON-FRI",
                    "max_retries": 3,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow_id"] == "wf_123"
            assert data["cron_expression"] == "0 9 * * MON-FRI"
            assert data["status"] == "active"

    def test_schedule_workflow_unschedule_removes_scheduled_task(self, client):
        """测试：DELETE /api/scheduled-workflows/{scheduled_workflow_id} 应该移除定时任务"""
        with patch(
            "src.application.use_cases.schedule_workflow.ScheduleWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            response = client.delete("/api/scheduled-workflows/scheduled_123")

            assert response.status_code == 204

    def test_schedule_workflow_list_returns_all_scheduled_workflows(self, client):
        """测试：GET /api/scheduled-workflows 应该返回所有定时任务"""
        with patch(
            "src.application.use_cases.schedule_workflow.ScheduleWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock results
            mock_scheduled_1 = Mock()
            mock_scheduled_1.id = "scheduled_1"
            mock_scheduled_1.workflow_id = "wf_1"
            mock_scheduled_1.cron_expression = "0 9 * * MON-FRI"
            mock_scheduled_1.status = "active"

            mock_scheduled_2 = Mock()
            mock_scheduled_2.id = "scheduled_2"
            mock_scheduled_2.workflow_id = "wf_2"
            mock_scheduled_2.cron_expression = "0 18 * * MON-FRI"
            mock_scheduled_2.status = "active"

            mock_use_case.list_scheduled_workflows.return_value = [
                mock_scheduled_1,
                mock_scheduled_2,
            ]

            response = client.get("/api/scheduled-workflows")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["workflow_id"] == "wf_1"
            assert data[1]["workflow_id"] == "wf_2"

    def test_schedule_workflow_get_returns_scheduled_workflow_details(self, client):
        """测试：GET /api/scheduled-workflows/{scheduled_workflow_id} 应该返回定时任务详情"""
        with patch(
            "src.application.use_cases.schedule_workflow.ScheduleWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            mock_scheduled = Mock()
            mock_scheduled.id = "scheduled_123"
            mock_scheduled.workflow_id = "wf_123"
            mock_scheduled.cron_expression = "0 9 * * MON-FRI"
            mock_scheduled.status = "active"
            mock_scheduled.next_execution_time = "2025-01-24T09:00:00"

            mock_use_case.get_scheduled_workflow_details.return_value = mock_scheduled

            response = client.get("/api/scheduled-workflows/scheduled_123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "scheduled_123"
            assert data["workflow_id"] == "wf_123"
            assert data["cron_expression"] == "0 9 * * MON-FRI"

    def test_schedule_workflow_handles_invalid_cron_expression(self, client):
        """测试：无效的 cron 表达式应该返回 400"""
        with patch(
            "src.application.use_cases.schedule_workflow.ScheduleWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            from src.domain.exceptions import DomainError

            mock_use_case.execute.side_effect = DomainError("Invalid cron expression")

            response = client.post(
                "/api/workflows/wf_123/schedule",
                json={
                    "cron_expression": "invalid cron",
                    "max_retries": 3,
                },
            )

            assert response.status_code == 400

    def test_schedule_workflow_handles_workflow_not_found(self, client):
        """测试：工作流不存在应该返回 404"""
        with patch(
            "src.application.use_cases.schedule_workflow.ScheduleWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            from src.domain.exceptions import NotFoundError

            mock_use_case.execute.side_effect = NotFoundError("Workflow", "wf_invalid")

            response = client.post(
                "/api/workflows/wf_invalid/schedule",
                json={
                    "cron_expression": "0 9 * * MON-FRI",
                    "max_retries": 3,
                },
            )

            assert response.status_code == 404

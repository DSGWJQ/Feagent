"""Concurrent Workflows API - TDD RED 阶段测试

定义并发工作流执行 API 的期望行为
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


class TestConcurrentWorkflowsAPI:
    """测试并发工作流执行 API 端点"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    def test_execute_concurrent_workflows_post_starts_concurrent_execution(self, client):
        """测试：POST /api/workflows/execute-concurrent 应该启动并发执行"""
        with patch(
            "src.application.use_cases.execute_concurrent_workflows.ExecuteConcurrentWorkflowsUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock execution results
            mock_result_1 = Mock()
            mock_result_1.workflow_id = "wf_1"
            mock_result_1.run_id = "run_1"
            mock_result_1.status = "submitted"

            mock_result_2 = Mock()
            mock_result_2.workflow_id = "wf_2"
            mock_result_2.run_id = "run_2"
            mock_result_2.status = "submitted"

            mock_use_case.execute.return_value = [mock_result_1, mock_result_2]

            response = client.post(
                "/api/workflows/execute-concurrent",
                json={
                    "workflow_ids": ["wf_1", "wf_2"],
                    "max_concurrent": 5,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["workflow_id"] == "wf_1"
            assert data[1]["workflow_id"] == "wf_2"

    def test_execute_concurrent_workflows_wait_for_completion(self, client):
        """测试：GET /api/workflows/concurrent-runs/{run_ids}/wait 应该等待完成"""
        with patch(
            "src.application.use_cases.execute_concurrent_workflows.ExecuteConcurrentWorkflowsUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case
            mock_use_case.wait_all_completion.return_value = True

            response = client.get("/api/workflows/concurrent-runs/wait?timeout=60")

            assert response.status_code == 200
            data = response.json()
            assert data["completed"] is True

    def test_execute_concurrent_workflows_get_execution_result(self, client):
        """测试：GET /api/runs/{run_id} 应该返回执行结果"""
        with patch(
            "src.application.use_cases.execute_concurrent_workflows.ExecuteConcurrentWorkflowsUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            mock_run = Mock()
            mock_run.id = "run_123"
            mock_run.agent_id = "workflow_wf_123"
            mock_run.status = "succeeded"
            mock_run.created_at = "2025-01-23T10:00:00"
            mock_run.finished_at = "2025-01-23T10:05:00"

            mock_use_case.get_execution_result.return_value = mock_run

            response = client.get("/api/runs/run_123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "run_123"
            assert data["status"] == "succeeded"

    def test_execute_concurrent_workflows_cancel_all_executions(self, client):
        """测试：POST /api/workflows/concurrent-runs/cancel-all 应该取消所有执行"""
        with patch(
            "src.application.use_cases.execute_concurrent_workflows.ExecuteConcurrentWorkflowsUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case
            mock_use_case.cancel_all_executions.return_value = True

            response = client.post("/api/workflows/concurrent-runs/cancel-all")

            assert response.status_code == 200
            data = response.json()
            assert data["cancelled"] is True

    def test_execute_concurrent_workflows_respects_max_concurrent_limit(self, client):
        """测试：应该尊重最大并发限制"""
        with patch(
            "src.application.use_cases.execute_concurrent_workflows.ExecuteConcurrentWorkflowsUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Create mock results
            results = [
                Mock(workflow_id=f"wf_{i}", run_id=f"run_{i}", status="submitted") for i in range(3)
            ]
            mock_use_case.execute.return_value = results

            response = client.post(
                "/api/workflows/execute-concurrent",
                json={
                    "workflow_ids": ["wf_0", "wf_1", "wf_2"],
                    "max_concurrent": 2,
                },
            )

            assert response.status_code == 200
            # Verify max_concurrent was set correctly
            call_args = mock_use_case.execute.call_args
            assert call_args[0][0].max_concurrent == 2

    def test_execute_concurrent_workflows_handles_workflow_not_found(self, client):
        """测试：工作流不存在应该返回 404"""
        with patch(
            "src.application.use_cases.execute_concurrent_workflows.ExecuteConcurrentWorkflowsUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            from src.domain.exceptions import NotFoundError

            mock_use_case.execute.side_effect = NotFoundError("Workflow", "wf_invalid")

            response = client.post(
                "/api/workflows/execute-concurrent",
                json={
                    "workflow_ids": ["wf_invalid"],
                    "max_concurrent": 5,
                },
            )

            assert response.status_code == 404

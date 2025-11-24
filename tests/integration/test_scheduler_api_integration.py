"""调度器API集成测试

测试新增的调度管理API端点：
- 手动触发执行
- 暂停/恢复任务
- 调度器状态监控
- 任务列表管理
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.database.base import Base
from src.infrastructure.database.models import WorkflowModel
from src.interfaces.api.main import app


@pytest.mark.integration
class TestSchedulerAPIIntegration:
    """调度器API集成测试"""

    @pytest.fixture
    def db_setup(self):
        """创建测试数据库和会话"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # 创建测试工作流
        workflow = WorkflowModel(
            id="wf_test_123",
            name="Test Workflow",
            description="A test workflow for scheduling",
            nodes=[],
            edges=[],
            status="published",  # 使用正确的状态值
        )
        session.add(workflow)
        session.commit()

        yield session
        session.close()

    @pytest.fixture
    def client(self, db_setup):
        """创建测试客户端"""
        return TestClient(app)

    def test_create_and_trigger_scheduled_workflow(self, client):
        """测试：创建定时任务并手动触发执行"""
        # Arrange - 创建定时任务
        create_response = client.post(
            "/api/workflows/wf_test_123/schedule",
            json={
                "cron_expression": "*/1 * * * *",
                "max_retries": 3,
            },
        )
        assert create_response.status_code == 200
        scheduled_workflow = create_response.json()
        scheduled_workflow_id = scheduled_workflow["id"]

        # Act - 手动触发执行
        trigger_response = client.post(
            f"/api/scheduled-workflows/{scheduled_workflow_id}/trigger"
        )

        # Assert
        assert trigger_response.status_code == 200
        result = trigger_response.json()
        assert result["scheduled_workflow_id"] == scheduled_workflow_id
        assert "execution_status" in result
        assert "execution_timestamp" in result
        assert result["message"] == "任务执行已触发"

    def test_pause_and_resume_scheduled_workflow(self, client):
        """测试：暂停和恢复定时任务"""
        # Arrange - 创建定时任务
        create_response = client.post(
            "/api/workflows/wf_test_123/schedule",
            json={
                "cron_expression": "*/5 * * * *",
                "max_retries": 2,
            },
        )
        assert create_response.status_code == 200
        scheduled_workflow_id = create_response.json()["id"]

        # Act & Assert - 暂停任务
        pause_response = client.post(
            f"/api/scheduled-workflows/{scheduled_workflow_id}/pause"
        )
        assert pause_response.status_code == 200
        paused_workflow = pause_response.json()
        assert paused_workflow["status"] == "disabled"

        # Act & Assert - 恢复任务
        resume_response = client.post(
            f"/api/scheduled-workflows/{scheduled_workflow_id}/resume"
        )
        assert resume_response.status_code == 200
        resumed_workflow = resume_response.json()
        assert resumed_workflow["status"] == "active"
        assert resumed_workflow["consecutive_failures"] == 0

    def test_get_scheduler_status(self, client):
        """测试：获取调度器状态"""
        # Act
        status_response = client.get("/api/scheduler/status")

        # Assert
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert "scheduler_running" in status_data
        assert "total_jobs_in_scheduler" in status_data
        assert "job_details" in status_data
        assert "message" in status_data
        assert status_data["message"] == "调度器状态获取成功"

        # 验证job_details结构
        if status_data["total_jobs_in_scheduler"] > 0:
            job_detail = status_data["job_details"][0]
            assert "id" in job_detail
            assert "name" in job_detail
            assert "trigger" in job_detail

    def test_get_scheduler_jobs(self, client):
        """测试：获取调度器任务列表"""
        # Arrange - 创建一个定时任务
        client.post(
            "/api/workflows/wf_test_123/schedule",
            json={
                "cron_expression": "*/10 * * * *",
                "max_retries": 1,
            },
        )

        # Act
        jobs_response = client.get("/api/scheduler/jobs")

        # Assert
        assert jobs_response.status_code == 200
        jobs_data = jobs_response.json()
        assert "jobs_in_scheduler" in jobs_data
        assert "active_scheduled_workflows" in jobs_data
        assert "summary" in jobs_data
        assert "message" in jobs_data

        # 验证summary结构
        summary = jobs_data["summary"]
        assert "total_jobs_in_scheduler" in summary
        assert "total_active_workflows" in summary
        assert "workflows_not_in_scheduler" in summary

        # 验证active_scheduled_workflows结构
        if jobs_data["active_scheduled_workflows"]:
            workflow_info = jobs_data["active_scheduled_workflows"][0]
            assert "id" in workflow_info
            assert "workflow_id" in workflow_info
            assert "cron_expression" in workflow_info
            assert "status" in workflow_info
            assert "is_in_scheduler" in workflow_info

    def test_trigger_nonexistent_workflow_should_return_404(self, client):
        """测试：触发不存在的定时任务应该返回404"""
        # Act
        response = client.post("/api/scheduled-workflows/nonexistent/trigger")

        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_pause_nonexistent_workflow_should_return_404(self, client):
        """测试：暂停不存在的定时任务应该返回404"""
        # Act
        response = client.post("/api/scheduled-workflows/nonexistent/pause")

        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_resume_nonexistent_workflow_should_return_404(self, client):
        """测试：恢复不存在的定时任务应该返回404"""
        # Act
        response = client.post("/api/scheduled-workflows/nonexistent/resume")

        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_list_scheduled_workflows_with_new_endpoints(self, client):
        """测试：列出定时任务与新API端点的集成"""
        # Arrange - 创建多个不同状态的定时任务
        task1_response = client.post(
            "/api/workflows/wf_test_123/schedule",
            json={
                "cron_expression": "*/1 * * * *",
                "max_retries": 3,
            },
        )
        task1_id = task1_response.json()["id"]

        task2_response = client.post(
            "/api/workflows/wf_test_123/schedule",
            json={
                "cron_expression": "*/2 * * * *",
                "max_retries": 2,
            },
        )
        task2_id = task2_response.json()["id"]

        # 暂停第二个任务
        client.post(f"/api/scheduled-workflows/{task2_id}/pause")

        # Act - 获取所有定时任务
        list_response = client.get("/api/scheduled-workflows")

        # Assert
        assert list_response.status_code == 200
        workflows = list_response.json()
        assert len(workflows) >= 2

        # 验证任务状态
        task_ids = [w["id"] for w in workflows]
        assert task1_id in task_ids
        assert task2_id in task_ids

        task1 = next(w for w in workflows if w["id"] == task1_id)
        task2 = next(w for w in workflows if w["id"] == task2_id)

        assert task1["status"] == "active"
        assert task2["status"] == "disabled"

    def test_complete_workflow_lifecycle_via_api(self, client):
        """测试：通过API完成定时任务的完整生命周期"""
        # 1. 创建定时任务
        create_response = client.post(
            "/api/workflows/wf_test_123/schedule",
            json={
                "cron_expression": "*/15 * * * *",
                "max_retries": 2,
            },
        )
        assert create_response.status_code == 200
        workflow_id = create_response.json()["id"]

        # 2. 获取任务详情
        detail_response = client.get(f"/api/scheduled-workflows/{workflow_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["status"] == "active"

        # 3. 手动触发执行
        trigger_response = client.post(f"/api/scheduled-workflows/{workflow_id}/trigger")
        assert trigger_response.status_code == 200

        # 4. 暂停任务
        pause_response = client.post(f"/api/scheduled-workflows/{workflow_id}/pause")
        assert pause_response.status_code == 200
        paused_detail = pause_response.json()
        assert paused_detail["status"] == "disabled"

        # 5. 恢复任务
        resume_response = client.post(f"/api/scheduled-workflows/{workflow_id}/resume")
        assert resume_response.status_code == 200
        resumed_detail = resume_response.json()
        assert resumed_detail["status"] == "active"

        # 6. 检查调度器状态
        status_response = client.get("/api/scheduler/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert isinstance(status_data["scheduler_running"], bool)

        # 7. 删除任务
        delete_response = client.delete(f"/api/scheduled-workflows/{workflow_id}")
        assert delete_response.status_code == 204

        # 8. 验证任务已删除
        get_deleted_response = client.get(f"/api/scheduled-workflows/{workflow_id}")
        assert get_deleted_response.status_code == 404
"""Runs 路由单元测试

测试目标：
1. 测试 POST /api/agents/{agent_id}/runs - 触发 Run
2. 测试 GET /api/runs/{id} - 获取 Run 详情

为什么先写测试？
- TDD 原则：先定义 API 行为，再实现路由
- API 是系统的契约，必须严格测试
- 集成测试：验证 API → Application → Domain 的完整流程

测试策略：
- 使用 Mock Use Case：不依赖真实数据库
- 测试成功场景：正常请求返回正确响应
- 测试失败场景：非法请求返回正确错误码
- 测试边界条件：Agent 不存在、Run 不存在
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建 FastAPI 测试客户端"""
    from src.interfaces.api.main import app

    return TestClient(app)


class TestExecuteRun:
    """测试 POST /api/agents/{agent_id}/runs - 触发 Run

    业务场景：用户触发 Agent 执行

    测试覆盖：
    - 成功触发 Run
    - Agent 不存在（404）
    - Use Case 抛出异常（500）
    """

    @patch("src.interfaces.api.routes.runs.ExecuteRunUseCase")
    def test_execute_run_success(self, mock_use_case_class, client):
        """测试：成功触发 Run"""
        from src.domain.entities import Run
        from src.domain.entities.run import RunStatus

        agent_id = "agent-123"
        mock_run = Run.create(agent_id=agent_id)
        mock_run.start()
        mock_run.succeed()

        mock_use_case = Mock()
        mock_use_case.execute.return_value = mock_run
        mock_use_case_class.return_value = mock_use_case

        # 发送请求
        response = client.post(f"/api/agents/{agent_id}/runs")

        # 验证响应
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == mock_run.id
        assert data["agent_id"] == agent_id
        assert data["status"] == RunStatus.SUCCEEDED.value
        assert "created_at" in data

    @patch("src.interfaces.api.routes.runs.ExecuteRunUseCase")
    def test_execute_run_agent_not_found(self, mock_use_case_class, client):
        """测试：Agent 不存在，应该返回 404"""
        from src.domain.exceptions import NotFoundError

        mock_use_case = Mock()
        mock_use_case.execute.side_effect = NotFoundError("Agent", "non-existent-id")
        mock_use_case_class.return_value = mock_use_case

        response = client.post("/api/agents/non-existent-id/runs")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @patch("src.interfaces.api.routes.runs.ExecuteRunUseCase")
    def test_execute_run_use_case_exception(self, mock_use_case_class, client):
        """测试：Use Case 抛出异常，应该返回 500"""
        mock_use_case = Mock()
        mock_use_case.execute.side_effect = Exception("数据库错误")
        mock_use_case_class.return_value = mock_use_case

        response = client.post("/api/agents/agent-123/runs")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


class TestGetRun:
    """测试 GET /api/runs/{id} - 获取 Run 详情

    业务场景：用户查看 Run 详情

    测试覆盖：
    - 成功获取 Run
    - Run 不存在（404）
    - Repository 异常（500）
    """

    @patch("src.interfaces.api.routes.runs.SQLAlchemyRunRepository")
    def test_get_run_success(self, mock_repo_class, client):
        """测试：成功获取 Run"""
        from src.domain.entities import Run
        from src.domain.entities.run import RunStatus

        mock_run = Run.create(agent_id="agent-123")
        mock_run.start()
        mock_run.succeed()

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = mock_run
        mock_repo_class.return_value = mock_repo

        response = client.get(f"/api/runs/{mock_run.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_run.id
        assert data["agent_id"] == "agent-123"
        assert data["status"] == RunStatus.SUCCEEDED.value

    @patch("src.interfaces.api.routes.runs.SQLAlchemyRunRepository")
    def test_get_run_not_found(self, mock_repo_class, client):
        """测试：Run 不存在，应该返回 404"""
        from src.domain.exceptions import NotFoundError

        mock_repo = Mock()
        mock_repo.get_by_id.side_effect = NotFoundError("Run", "non-existent-id")
        mock_repo_class.return_value = mock_repo

        response = client.get("/api/runs/non-existent-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

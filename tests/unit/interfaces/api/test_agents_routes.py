"""Agents 路由单元测试

测试目标：
1. 测试 POST /api/agents - 创建 Agent
2. 测试 GET /api/agents/{id} - 获取 Agent 详情
3. 测试 GET /api/agents - 列出所有 Agents
4. 测试错误处理（404、400、500）

为什么先写测试？
- TDD 原则：先定义 API 行为，再实现路由
- API 是系统的契约，必须严格测试
- 集成测试：验证 API → Application → Domain 的完整流程

测试策略：
- 使用 Mock Use Case：不依赖真实数据库
- 测试成功场景：正常请求返回正确响应
- 测试失败场景：非法请求返回正确错误码
- 测试边界条件：空字符串、不存在的 ID
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建 FastAPI 测试客户端

    为什么使用 fixture？
    - 每个测试都需要一个干净的客户端
    - 避免测试之间的相互影响
    - 符合 pytest 最佳实践
    """
    from src.interfaces.api.main import app

    return TestClient(app)


class TestCreateAgent:
    """测试 POST /api/agents - 创建 Agent

    业务场景：用户通过 API 创建 Agent

    测试覆盖：
    - 成功创建 Agent
    - 缺少必填字段（start、goal）
    - 字段为空字符串
    - Use Case 抛出异常
    """

    @patch("src.interfaces.api.routes.agents.CreateAgentUseCase")
    def test_create_agent_success(self, mock_use_case_class, client):
        """测试：成功创建 Agent"""
        # Mock Use Case
        from src.domain.entities import Agent

        mock_agent = Agent.create(
            start="我有一个 CSV 文件，包含销售数据",
            goal="分析销售数据并生成报告",
            name="销售分析 Agent",
        )

        mock_use_case = Mock()
        # execute() 返回 tuple[Agent, str | None]
        mock_use_case.execute.return_value = (mock_agent, None)
        mock_use_case_class.return_value = mock_use_case

        # 发送请求
        response = client.post(
            "/api/agents",
            json={
                "start": "我有一个 CSV 文件，包含销售数据",
                "goal": "分析销售数据并生成报告",
                "name": "销售分析 Agent",
            },
        )

        # 验证响应
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == mock_agent.id
        assert data["start"] == "我有一个 CSV 文件，包含销售数据"
        assert data["goal"] == "分析销售数据并生成报告"
        assert data["name"] == "销售分析 Agent"
        assert data["status"] == "active"
        assert "created_at" in data

    def test_create_agent_missing_start(self, client):
        """测试：缺少 start 字段，应该返回 422"""
        response = client.post(
            "/api/agents",
            json={
                "goal": "分析数据",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_create_agent_missing_goal(self, client):
        """测试：缺少 goal 字段，应该返回 422"""
        response = client.post(
            "/api/agents",
            json={
                "start": "我有一个 CSV 文件",
            },
        )

        assert response.status_code == 422

    def test_create_agent_empty_start(self, client):
        """测试：start 为空字符串，应该返回 422"""
        response = client.post(
            "/api/agents",
            json={
                "start": "",
                "goal": "分析数据",
            },
        )

        assert response.status_code == 422

    @patch("src.interfaces.api.routes.agents.CreateAgentUseCase")
    def test_create_agent_use_case_exception(self, mock_use_case_class, client):
        """测试：Use Case 抛出异常，应该返回 500"""
        mock_use_case = Mock()
        mock_use_case.execute.side_effect = Exception("数据库错误")
        mock_use_case_class.return_value = mock_use_case

        response = client.post(
            "/api/agents",
            json={
                "start": "我有一个 CSV 文件，包含销售数据",
                "goal": "分析销售数据并生成报告",
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


class TestGetAgent:
    """测试 GET /api/agents/{id} - 获取 Agent 详情

    业务场景：用户查看 Agent 详情

    测试覆盖：
    - 成功获取 Agent
    - Agent 不存在（404）
    - Repository 异常（500）
    """

    @patch("src.interfaces.api.routes.agents.SQLAlchemyAgentRepository")
    def test_get_agent_success(self, mock_repo_class, client):
        """测试：成功获取 Agent"""
        from src.domain.entities import Agent

        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = mock_agent
        mock_repo_class.return_value = mock_repo

        response = client.get(f"/api/agents/{mock_agent.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_agent.id
        assert data["start"] == "我有一个 CSV 文件"

    @patch("src.interfaces.api.routes.agents.SQLAlchemyAgentRepository")
    def test_get_agent_not_found(self, mock_repo_class, client):
        """测试：Agent 不存在，应该返回 404"""
        from src.domain.exceptions import NotFoundError

        mock_repo = Mock()
        mock_repo.get_by_id.side_effect = NotFoundError("Agent", "non-existent-id")
        mock_repo_class.return_value = mock_repo

        response = client.get("/api/agents/non-existent-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestListAgents:
    """测试 GET /api/agents - 列出所有 Agents

    业务场景：用户查看所有 Agents

    测试覆盖：
    - 成功列出多个 Agents
    - 没有 Agents（返回空列表）
    - Repository 异常（500）
    """

    @patch("src.interfaces.api.routes.agents.SQLAlchemyAgentRepository")
    def test_list_agents_success(self, mock_repo_class, client):
        """测试：成功列出多个 Agents"""
        from src.domain.entities import Agent

        mock_agents = [
            Agent.create(start="起点1", goal="目的1", name="Agent 1"),
            Agent.create(start="起点2", goal="目的2", name="Agent 2"),
        ]

        mock_repo = Mock()
        mock_repo.find_all.return_value = mock_agents
        mock_repo_class.return_value = mock_repo

        response = client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Agent 1"
        assert data[1]["name"] == "Agent 2"

    @patch("src.interfaces.api.routes.agents.SQLAlchemyAgentRepository")
    def test_list_agents_empty(self, mock_repo_class, client):
        """测试：没有 Agents，应该返回空列表"""
        mock_repo = Mock()
        mock_repo.find_all.return_value = []
        mock_repo_class.return_value = mock_repo

        response = client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
        assert data == []

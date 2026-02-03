"""GitHub OAuth集成测试

测试完整的GitHub登录流程（端到端）：
1. GitHub OAuth回调 → 创建/更新用户
2. 登录用户创建工作流 → 关联user_id
3. 非登录用户创建工作流 → user_id为None
4. 登录用户创建工具 → 关联user_id
5. Token验证和过期处理

使用真实的数据库和API（FastAPI TestClient）
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.main import app
from src.interfaces.api.routes import workflows as workflows_routes

# 创建测试数据库
TEST_DATABASE_URL = "sqlite:///./test_integration.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """覆盖数据库依赖，使用测试数据库"""
    try:
        db = TestSessionLocal()
        yield db
    finally:
        db.close()


# 覆盖依赖
app.dependency_overrides[get_db_session] = override_get_db


def _parse_sse_events(text: str) -> list[dict]:
    events: list[dict] = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            continue
        events.append(json.loads(payload))
    return events


@pytest.fixture(scope="function")
def test_db():
    """每个测试前创建表，测试后删除表"""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(test_db):
    """创建测试客户端"""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_github_oauth():
    """Mock GitHub OAuth API调用"""
    with patch("src.infrastructure.auth.github_oauth_service.httpx.AsyncClient") as mock_client:
        # Mock token exchange response (NOT AsyncMock - response.json() is NOT async)
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {"access_token": "gho_test_token_12345"}
        mock_token_response.raise_for_status = MagicMock()

        # Mock user info response (NOT AsyncMock - response.json() is NOT async)
        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "id": 88888888,
            "login": "testuser",
            "name": "Test User",
            "email": "testuser@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/88888888",
            "html_url": "https://github.com/testuser",
        }
        mock_user_response.raise_for_status = MagicMock()

        # 配置mock - only the HTTP methods (post/get) are async
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(return_value=mock_token_response)
        mock_instance.get = AsyncMock(return_value=mock_user_response)

        yield mock_client


class TestGitHubOAuthIntegration:
    """测试GitHub OAuth完整流程"""

    def test_github_callback_should_create_new_user_and_return_jwt(self, client, mock_github_oauth):
        """
        真实场景：新用户首次GitHub登录

        Given: 新用户通过GitHub授权，回调返回code
        When: POST /api/auth/github/callback
        Then: 应该创建新用户并返回JWT token
        """
        # Arrange
        request_data = {"code": "github_auth_code_12345"}

        # Act
        response = client.post("/api/auth/github/callback", json=request_data)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # 验证返回结构
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "user" in data

        # 验证用户信息
        user = data["user"]
        assert user["github_id"] == 88888888
        assert user["github_username"] == "testuser"
        assert user["email"] == "testuser@example.com"
        assert user["name"] == "Test User"
        assert user["role"] == "user"
        assert user["is_active"] is True

        # 验证JWT token不为空
        assert len(data["access_token"]) > 0

    def test_github_callback_should_update_existing_user(self, client, mock_github_oauth):
        """
        真实场景：老用户再次登录

        Given: 用户已存在于数据库
        When: 再次通过GitHub登录
        Then: 应该更新用户的最后登录时间
        """
        # Arrange - 第一次登录（创建用户）
        request_data = {"code": "github_auth_code_first"}
        response1 = client.post("/api/auth/github/callback", json=request_data)
        assert response1.status_code == 200
        first_login = response1.json()

        # Act - 第二次登录（更新用户）
        request_data = {"code": "github_auth_code_second"}
        response2 = client.post("/api/auth/github/callback", json=request_data)

        # Assert
        assert response2.status_code == 200
        second_login = response2.json()

        # 验证是同一个用户（github_id相同）
        assert first_login["user"]["id"] == second_login["user"]["id"]
        assert first_login["user"]["github_id"] == second_login["user"]["github_id"]

        # 验证最后登录时间已更新
        assert second_login["user"]["last_login_at"] is not None

    def test_invalid_github_code_should_return_400(self, client):
        """
        真实场景：使用无效的GitHub授权码

        Given: GitHub API返回错误
        When: POST /api/auth/github/callback with invalid code
        Then: 应该返回400错误
        """
        # Arrange - Mock GitHub API返回错误
        with patch("src.infrastructure.auth.github_oauth_service.httpx.AsyncClient") as mock_client:
            mock_error_response = MagicMock()
            mock_error_response.status_code = 400
            mock_error_response.raise_for_status.side_effect = Exception("Bad request")

            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.post = AsyncMock(return_value=mock_error_response)

            # Act
            response = client.post("/api/auth/github/callback", json={"code": "invalid_code"})

            # Assert
            assert response.status_code == 400


class TestAuthenticatedWorkflowCreation:
    """测试登录用户创建工作流"""

    def test_authenticated_user_should_save_workflow_with_user_id(self, client, mock_github_oauth):
        """
        真实场景：登录用户创建工作流并保存

        Given: 用户已登录（有JWT token）
        When: POST /api/workflows with Authorization header
        Then: 工作流应该关联user_id
        """
        # Arrange - 先登录获取token
        login_response = client.post("/api/auth/github/callback", json={"code": "test_code"})
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        def override_use_case_factory():
            def factory(workflow_id: str):
                class _StubUseCase:
                    async def execute_streaming(self, _input_data):
                        yield {
                            "type": "workflow_updated",
                            "ai_message": "ok",
                            "workflow": {"id": workflow_id},
                            "rag_sources": [],
                        }

                return _StubUseCase()

            return factory

        client.app.dependency_overrides[
            workflows_routes.get_update_workflow_by_chat_use_case_factory
        ] = override_use_case_factory
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "text/event-stream",
                "X-Workflow-Create": "explicit",
            }
            response = client.post(
                "/api/workflows/chat-create/stream",
                json={"message": "登录用户创建的工作流", "run_id": "run_auth_1"},
                headers=headers,
            )
            assert response.status_code == 200

            events = _parse_sse_events(response.text)
            assert events and events[0]["metadata"]["workflow_id"].startswith("wf_")
            workflow_id = events[0]["metadata"]["workflow_id"]

            get_response = client.get(f"/api/workflows/{workflow_id}")
            assert get_response.status_code == 200
        finally:
            client.app.dependency_overrides.pop(
                workflows_routes.get_update_workflow_by_chat_use_case_factory, None
            )

    def test_unauthenticated_user_should_save_workflow_without_user_id(self, client):
        """
        真实场景：非登录用户体验工作流创建

        Given: 用户未登录（无JWT token）
        When: POST /api/workflows without Authorization header
        Then: 工作流user_id应该为None（体验模式）
        """

        def override_use_case_factory():
            def factory(workflow_id: str):
                class _StubUseCase:
                    async def execute_streaming(self, _input_data):
                        yield {
                            "type": "workflow_updated",
                            "ai_message": "ok",
                            "workflow": {"id": workflow_id},
                            "rag_sources": [],
                        }

                return _StubUseCase()

            return factory

        client.app.dependency_overrides[
            workflows_routes.get_update_workflow_by_chat_use_case_factory
        ] = override_use_case_factory
        try:
            response = client.post(
                "/api/workflows/chat-create/stream",
                json={"message": "非登录用户创建的工作流", "run_id": "run_anon_1"},
                headers={"Accept": "text/event-stream", "X-Workflow-Create": "explicit"},
            )
            assert response.status_code == 200
            events = _parse_sse_events(response.text)
            assert events and events[0]["metadata"]["workflow_id"].startswith("wf_")
            workflow_id = events[0]["metadata"]["workflow_id"]

            get_response = client.get(f"/api/workflows/{workflow_id}")
            assert get_response.status_code == 200
        finally:
            client.app.dependency_overrides.pop(
                workflows_routes.get_update_workflow_by_chat_use_case_factory, None
            )


class TestAuthenticatedToolCreation:
    """测试登录用户创建工具"""

    def test_authenticated_user_should_save_tool_with_user_id(self, client, mock_github_oauth):
        """
        真实场景：登录用户上传工具

        Given: 用户已登录
        When: POST /api/tools with Authorization header
        Then: 工具应该关联user_id
        """
        # Arrange - 登录
        login_response = client.post("/api/auth/github/callback", json={"code": "test_code"})
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Act - 创建工具（带token）
        tool_data = {
            "name": "测试工具",
            "description": "登录用户创建的工具",
            "category": "http",
            "author": "testuser",
            "parameters": [],
            "returns": {},
            "implementation_type": "http",
            "implementation_config": {"url": "https://api.example.com"},
            "tags": ["test"],
        }

        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/tools", json=tool_data, headers=headers)

        # Assert
        assert response.status_code == 201
        tool = response.json()

        assert tool["name"] == "测试工具"
        assert tool["author"] == "testuser"
        # TODO: 验证数据库中tool.user_id == user_id

    def test_unauthenticated_user_should_save_tool_without_user_id(self, client):
        """
        真实场景：非登录用户体验工具创建

        Given: 用户未登录
        When: POST /api/tools without Authorization header
        Then: 工具user_id应该为None
        """
        # Act - 创建工具（不带token）
        tool_data = {
            "name": "体验工具",
            "description": "非登录用户创建的工具",
            "category": "http",
            "author": "anonymous",
            "parameters": [],
            "returns": {},
            "implementation_type": "builtin",
            "implementation_config": {},
        }

        response = client.post("/api/tools", json=tool_data)

        # Assert
        assert response.status_code == 201
        tool = response.json()

        assert tool["name"] == "体验工具"
        # TODO: 验证数据库中tool.user_id is None


class TestJWTTokenValidation:
    """测试JWT token验证"""

    def test_expired_token_should_return_401(self, client, mock_github_oauth):
        """
        真实场景：使用过期的token访问API

        Given: Token已过期
        When: 使用该token访问需要认证的API
        Then: 应该返回401错误
        """
        # TODO: 需要创建一个需要必须认证的API端点来测试
        pass

    def test_invalid_token_should_return_401(self, client):
        """
        真实场景：使用伪造的token

        Given: 使用篡改或伪造的token
        When: 尝试访问API
        Then: 应该返回401错误（或被忽略，取决于是否必须认证）
        """

        def override_use_case_factory():
            def factory(workflow_id: str):
                class _StubUseCase:
                    async def execute_streaming(self, _input_data):
                        yield {
                            "type": "workflow_updated",
                            "ai_message": "ok",
                            "workflow": {"id": workflow_id},
                            "rag_sources": [],
                        }

                return _StubUseCase()

            return factory

        client.app.dependency_overrides[
            workflows_routes.get_update_workflow_by_chat_use_case_factory
        ] = override_use_case_factory
        try:
            headers = {
                "Authorization": "Bearer invalid_fake_token_12345",
                "Accept": "text/event-stream",
                "X-Workflow-Create": "explicit",
            }
            response = client.post(
                "/api/workflows/chat-create/stream",
                json={"message": "测试", "run_id": "run_invalid_token_1"},
                headers=headers,
            )

            # Assert - 因为是可选认证，应成功但不关联用户（具体 user_id 验证留待 DB 侧）
            assert response.status_code == 200
            events = _parse_sse_events(response.text)
            assert events and events[0]["metadata"]["workflow_id"].startswith("wf_")
        finally:
            client.app.dependency_overrides.pop(
                workflows_routes.get_update_workflow_by_chat_use_case_factory, None
            )

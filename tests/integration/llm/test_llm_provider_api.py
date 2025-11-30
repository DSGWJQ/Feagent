"""LLMProvider API 集成测试

测试 LLMProvider API 端点的完整功能

测试策略：
1. 使用真实的数据库（SQLite :memory:）
2. 测试完整的请求-响应流程
3. 验证业务逻辑正确性
4. 测试错误处理
5. 验证 API 密钥掩码
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 导入所有模型以确保它们都被注册
from src.infrastructure.database import models  # noqa: F401
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.main import app


@pytest.fixture
def test_db():
    """创建测试数据库"""
    # Use StaticPool to ensure a single connection for all operations
    # This avoids isolation issues with SQLite in-memory databases
    # Each connection to sqlite:///:memory: creates a separate database,
    # so we must use the same connection throughout the test
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_get_db

    yield engine

    Base.metadata.drop_all(engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    """创建测试客户端"""
    return TestClient(app)


class TestRegisterLLMProvider:
    """注册 LLM 提供商测试"""

    def test_register_provider_success(self, client: TestClient):
        """测试成功注册提供商"""
        response = client.post(
            "/api/llm-providers",
            json={
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "sk-test-key-12345",
                "models": ["gpt-4", "gpt-3.5-turbo"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "openai"
        assert data["display_name"] == "OpenAI"
        # 验证 API 密钥被掩码
        assert data["api_key"] == "sk-***"
        assert len(data["models"]) == 2
        assert "id" in data
        assert data["id"].startswith("llm_provider_")
        assert data["enabled"] is True

    def test_register_provider_without_models(self, client: TestClient):
        """测试没有模型的注册失败"""
        response = client.post(
            "/api/llm-providers",
            json={
                "name": "test",
                "display_name": "Test",
                "api_base": "https://test.com",
                "api_key": "test-key",
                "models": [],  # 空列表
            },
        )

        # Pydantic validation with min_items returns 422, not 400
        assert response.status_code == 422

    def test_register_provider_without_api_key(self, client: TestClient):
        """测试不提供 API 密钥（本地模型）"""
        response = client.post(
            "/api/llm-providers",
            json={
                "name": "ollama",
                "display_name": "Ollama (本地)",
                "api_base": "http://localhost:11434/v1",
                "api_key": None,  # 本地模型不需要 API 密钥
                "models": ["llama2", "mistral"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["api_key"] is None


class TestListLLMProviders:
    """列出 LLM 提供商测试"""

    def test_list_providers_empty(self, client: TestClient):
        """测试列出空提供商列表"""
        response = client.get("/api/llm-providers")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["providers"] == []

    def test_list_providers_with_data(self, client: TestClient):
        """测试列出包含数据的提供商列表"""
        # 注册两个提供商
        client.post(
            "/api/llm-providers",
            json={
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "test-key",
                "models": ["gpt-4"],
            },
        )
        client.post(
            "/api/llm-providers",
            json={
                "name": "deepseek",
                "display_name": "DeepSeek",
                "api_base": "https://api.deepseek.com",
                "api_key": "test-key",
                "models": ["deepseek-chat"],
            },
        )

        # 列出所有提供商
        response = client.get("/api/llm-providers")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["providers"]) == 2

    def test_list_providers_enabled_only(self, client: TestClient):
        """测试只列出已启用的提供商"""
        # 注册一个启用的提供商
        create_response_1 = client.post(
            "/api/llm-providers",
            json={
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "test-key",
                "models": ["gpt-4"],
            },
        )
        provider_1_id = create_response_1.json()["id"]

        # 注册一个提供商后禁用它
        create_response_2 = client.post(
            "/api/llm-providers",
            json={
                "name": "deepseek",
                "display_name": "DeepSeek",
                "api_base": "https://api.deepseek.com",
                "api_key": "test-key",
                "models": ["deepseek-chat"],
            },
        )
        provider_2_id = create_response_2.json()["id"]

        # 禁用第二个提供商
        client.post(f"/api/llm-providers/{provider_2_id}/disable", json={})

        # 只列出已启用的提供商
        response = client.get("/api/llm-providers?enabled_only=true")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["providers"][0]["id"] == provider_1_id


class TestGetLLMProvider:
    """获取 LLM 提供商详情测试"""

    def test_get_provider_success(self, client: TestClient):
        """测试成功获取提供商详情"""
        # 注册提供商
        create_response = client.post(
            "/api/llm-providers",
            json={
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "sk-test-key-12345",
                "models": ["gpt-4"],
            },
        )
        provider_id = create_response.json()["id"]

        # 获取提供商详情
        response = client.get(f"/api/llm-providers/{provider_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == provider_id
        assert data["name"] == "openai"
        # 验证 API 密钥被掩码
        assert data["api_key"] == "sk-***"

    def test_get_provider_not_found(self, client: TestClient):
        """测试获取不存在的提供商"""
        response = client.get("/api/llm-providers/llm_provider_nonexistent")

        assert response.status_code == 404


class TestUpdateLLMProvider:
    """更新 LLM 提供商测试"""

    def test_update_provider_api_key(self, client: TestClient):
        """测试更新提供商的 API 密钥"""
        # 注册提供商
        create_response = client.post(
            "/api/llm-providers",
            json={
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "sk-old-key",
                "models": ["gpt-4"],
            },
        )
        provider_id = create_response.json()["id"]

        # 更新 API 密钥
        response = client.put(
            f"/api/llm-providers/{provider_id}",
            json={"api_key": "sk-new-key-12345"},
        )

        assert response.status_code == 200
        data = response.json()
        # 验证 API 密钥被掩码
        assert data["api_key"] == "sk-***"

    def test_update_provider_not_found(self, client: TestClient):
        """测试更新不存在的提供商"""
        response = client.put(
            "/api/llm-providers/llm_provider_nonexistent",
            json={"api_key": "new-key"},
        )

        assert response.status_code == 404


class TestDeleteLLMProvider:
    """删除 LLM 提供商测试"""

    def test_delete_provider_success(self, client: TestClient):
        """测试成功删除提供商"""
        # 注册提供商
        create_response = client.post(
            "/api/llm-providers",
            json={
                "name": "test",
                "display_name": "Test",
                "api_base": "https://test.com",
                "api_key": "test-key",
                "models": ["test-model"],
            },
        )
        provider_id = create_response.json()["id"]

        # 删除提供商
        response = client.delete(f"/api/llm-providers/{provider_id}")

        assert response.status_code == 204

        # 验证已删除
        get_response = client.get(f"/api/llm-providers/{provider_id}")
        assert get_response.status_code == 404

    def test_delete_provider_not_found(self, client: TestClient):
        """测试删除不存在的提供商"""
        response = client.delete("/api/llm-providers/llm_provider_nonexistent")

        assert response.status_code == 404


class TestEnableDisableLLMProvider:
    """启用/禁用 LLM 提供商测试"""

    def test_enable_provider(self, client: TestClient):
        """测试启用提供商"""
        # 注册提供商
        create_response = client.post(
            "/api/llm-providers",
            json={
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "test-key",
                "models": ["gpt-4"],
            },
        )
        provider_id = create_response.json()["id"]

        # 禁用提供商
        client.post(f"/api/llm-providers/{provider_id}/disable", json={})

        # 验证已禁用
        get_response = client.get(f"/api/llm-providers/{provider_id}")
        assert get_response.json()["enabled"] is False

        # 启用提供商
        response = client.post(f"/api/llm-providers/{provider_id}/enable", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    def test_disable_provider(self, client: TestClient):
        """测试禁用提供商"""
        # 注册提供商
        create_response = client.post(
            "/api/llm-providers",
            json={
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "test-key",
                "models": ["gpt-4"],
            },
        )
        provider_id = create_response.json()["id"]

        # 禁用提供商
        response = client.post(f"/api/llm-providers/{provider_id}/disable", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

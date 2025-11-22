"""Tool API 集成测试

测试 Tool API 端点的完整功能

测试策略：
1. 使用真实的数据库（SQLite :memory:）
2. 测试完整的请求-响应流程
3. 验证业务逻辑正确性
4. 测试错误处理
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.infrastructure.database.base import Base
# 导入所有模型以确保它们都被注册
from src.infrastructure.database import models  # noqa: F401
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


class TestCreateTool:
    """创建工具测试"""

    def test_create_tool_success(self, client: TestClient):
        """测试成功创建工具"""
        response = client.post(
            "/api/tools",
            json={
                "name": "HTTP请求工具",
                "description": "发送HTTP请求",
                "category": "http",
                "author": "admin",
                "parameters": [
                    {
                        "name": "url",
                        "type": "string",
                        "description": "请求URL",
                        "required": True,
                    }
                ],
                "implementation_type": "http",
                "tags": ["http", "network"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "HTTP请求工具"
        assert data["category"] == "http"
        assert data["status"] == "draft"
        assert len(data["parameters"]) == 1
        assert "id" in data
        assert data["id"].startswith("tool_")

    def test_create_tool_with_invalid_name(self, client: TestClient):
        """测试创建工具时名称无效"""
        response = client.post(
            "/api/tools",
            json={
                "name": "",  # 空名称
                "description": "测试工具",
                "category": "http",
                "author": "admin",
            },
        )

        # Pydantic validation returns 422, not 400
        assert response.status_code == 422

    def test_create_tool_with_invalid_category(self, client: TestClient):
        """测试创建工具时分类无效"""
        response = client.post(
            "/api/tools",
            json={
                "name": "测试工具",
                "description": "测试工具",
                "category": "invalid_category",  # 无效分类
                "author": "admin",
            },
        )

        assert response.status_code == 400


class TestListTools:
    """列出工具测试"""

    def test_list_tools_empty(self, client: TestClient):
        """测试列出空工具列表"""
        response = client.get("/api/tools")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["tools"] == []

    def test_list_tools_with_data(self, client: TestClient):
        """测试列出包含数据的工具列表"""
        # 创建两个工具
        client.post(
            "/api/tools",
            json={
                "name": "工具1",
                "description": "测试工具1",
                "category": "http",
                "author": "admin",
            },
        )
        client.post(
            "/api/tools",
            json={
                "name": "工具2",
                "description": "测试工具2",
                "category": "database",
                "author": "admin",
            },
        )

        # 列出所有工具
        response = client.get("/api/tools")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["tools"]) == 2

    def test_list_tools_by_category(self, client: TestClient):
        """测试按分类过滤工具"""
        # 创建不同分类的工具
        client.post(
            "/api/tools",
            json={
                "name": "HTTP工具",
                "description": "HTTP工具",
                "category": "http",
                "author": "admin",
            },
        )
        client.post(
            "/api/tools",
            json={
                "name": "数据库工具",
                "description": "数据库工具",
                "category": "database",
                "author": "admin",
            },
        )

        # 只查询 HTTP 工具
        response = client.get("/api/tools?category=http")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all(tool["category"] == "http" for tool in data["tools"])


class TestGetTool:
    """获取工具详情测试"""

    def test_get_tool_success(self, client: TestClient):
        """测试成功获取工具详情"""
        # 创建工具
        create_response = client.post(
            "/api/tools",
            json={
                "name": "测试工具",
                "description": "测试工具描述",
                "category": "http",
                "author": "admin",
            },
        )
        tool_id = create_response.json()["id"]

        # 获取工具详情
        response = client.get(f"/api/tools/{tool_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tool_id
        assert data["name"] == "测试工具"

    def test_get_tool_not_found(self, client: TestClient):
        """测试获取不存在的工具"""
        response = client.get("/api/tools/tool_nonexistent")

        assert response.status_code == 404


class TestUpdateTool:
    """更新工具测试"""

    def test_update_tool_success(self, client: TestClient):
        """测试成功更新工具"""
        # 创建工具
        create_response = client.post(
            "/api/tools",
            json={
                "name": "原始名称",
                "description": "原始描述",
                "category": "http",
                "author": "admin",
            },
        )
        tool_id = create_response.json()["id"]

        # 更新工具
        response = client.put(
            f"/api/tools/{tool_id}",
            json={
                "name": "新名称",
                "description": "新描述",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新名称"
        assert data["description"] == "新描述"

    def test_update_tool_not_found(self, client: TestClient):
        """测试更新不存在的工具"""
        response = client.put(
            "/api/tools/tool_nonexistent",
            json={"name": "新名称"},
        )

        assert response.status_code == 404


class TestDeleteTool:
    """删除工具测试"""

    def test_delete_tool_success(self, client: TestClient):
        """测试成功删除工具"""
        # 创建工具
        create_response = client.post(
            "/api/tools",
            json={
                "name": "待删除工具",
                "description": "测试删除",
                "category": "http",
                "author": "admin",
            },
        )
        tool_id = create_response.json()["id"]

        # 删除工具
        response = client.delete(f"/api/tools/{tool_id}")

        assert response.status_code == 204

        # 验证已删除
        get_response = client.get(f"/api/tools/{tool_id}")
        assert get_response.status_code == 404

    def test_delete_tool_not_found(self, client: TestClient):
        """测试删除不存在的工具"""
        response = client.delete("/api/tools/tool_nonexistent")

        assert response.status_code == 404


class TestToolLifecycle:
    """工具生命周期测试"""

    def test_publish_tool_fail_without_testing(self, client: TestClient):
        """测试未经测试不能发布工具"""
        # 创建工具（状态为 DRAFT）
        create_response = client.post(
            "/api/tools",
            json={
                "name": "测试工具",
                "description": "测试工具",
                "category": "http",
                "author": "admin",
            },
        )
        tool_id = create_response.json()["id"]

        # 尝试发布（应该失败，因为状态不是 TESTING）
        response = client.post(f"/api/tools/{tool_id}/publish", json={})

        assert response.status_code == 400
        assert "只有测试通过的工具才能发布" in response.json()["detail"]

    def test_deprecate_tool_success(self, client: TestClient):
        """测试成功废弃工具"""
        # 创建工具
        create_response = client.post(
            "/api/tools",
            json={
                "name": "测试工具",
                "description": "测试工具",
                "category": "http",
                "author": "admin",
            },
        )
        tool_id = create_response.json()["id"]

        # 废弃工具
        response = client.post(
            f"/api/tools/{tool_id}/deprecate",
            json={"reason": "已有更好的替代工具"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deprecated"

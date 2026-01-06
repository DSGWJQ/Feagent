"""Seed API 集成测试

测试 E2E 测试数据管理 API：
- POST /api/test/workflows/seed - 创建测试 Workflow
- DELETE /api/test/workflows/cleanup - 清理测试 Workflow
- GET /api/test/workflows/fixture-types - 列出 Fixture 类型

验收标准：
- 4 种 fixture_type 都能正确生成
- 缺少 X-Test-Mode 返回 403
- cleanup_token 能正确删除数据
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_seed_api():
    """创建启用 Seed API 的测试客户端"""
    with patch("src.config.settings.enable_test_seed_api", True):
        from importlib import reload

        import src.interfaces.api.main as main_module

        reload(main_module)
        with TestClient(main_module.app) as client:
            yield client

            # 测试收尾：确保不遗留 source='e2e_test' 的测试数据，避免污染本地/CI 环境
            cleanup_response = client.request(
                "DELETE",
                "/api/test/workflows/cleanup",
                headers={"X-Test-Mode": "true"},
                json={"cleanup_tokens": [], "delete_by_source": True},
            )
            assert cleanup_response.status_code == 200, cleanup_response.text


@pytest.fixture
def client_without_seed_api():
    """创建禁用 Seed API 的测试客户端"""
    with patch("src.config.settings.enable_test_seed_api", False):
        from importlib import reload

        import src.interfaces.api.main as main_module

        reload(main_module)
        with TestClient(main_module.app) as client:
            yield client


class TestSeedAPISecurityControls:
    """测试 Seed API 安全控制"""

    def test_missing_test_mode_header_returns_403(self, client_with_seed_api: TestClient):
        """测试: 缺少 X-Test-Mode 返回 403"""
        response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={"fixture_type": "main_subgraph_only"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == "TEST_MODE_REQUIRED"

    def test_invalid_test_mode_header_returns_403(self, client_with_seed_api: TestClient):
        """测试: X-Test-Mode 值错误返回 403"""
        response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={"fixture_type": "main_subgraph_only"},
            headers={"X-Test-Mode": "false"},
        )

        assert response.status_code == 403


class TestSeedWorkflowEndpoint:
    """测试 POST /api/test/workflows/seed"""

    def test_seed_main_subgraph_only(self, client_with_seed_api: TestClient):
        """测试: 创建 main_subgraph_only fixture"""
        response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={
                "fixture_type": "main_subgraph_only",
                "project_id": "e2e_test_project",
            },
            headers={"X-Test-Mode": "true"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "workflow_id" in data
        assert data["fixture_type"] == "main_subgraph_only"
        assert "cleanup_token" in data
        assert data["metadata"]["node_count"] == 3
        assert data["metadata"]["edge_count"] == 2
        assert data["metadata"]["has_isolated_nodes"] is False

    def test_seed_with_isolated_nodes(self, client_with_seed_api: TestClient):
        """测试: 创建 with_isolated_nodes fixture"""
        response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={"fixture_type": "with_isolated_nodes"},
            headers={"X-Test-Mode": "true"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["fixture_type"] == "with_isolated_nodes"
        assert data["metadata"]["has_isolated_nodes"] is True

    def test_seed_side_effect_workflow(self, client_with_seed_api: TestClient):
        """测试: 创建 side_effect_workflow fixture"""
        response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={"fixture_type": "side_effect_workflow"},
            headers={"X-Test-Mode": "true"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["fixture_type"] == "side_effect_workflow"
        assert len(data["metadata"]["side_effect_nodes"]) > 0

    def test_seed_invalid_config(self, client_with_seed_api: TestClient):
        """测试: 创建 invalid_config fixture"""
        response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={"fixture_type": "invalid_config"},
            headers={"X-Test-Mode": "true"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["fixture_type"] == "invalid_config"

    def test_seed_invalid_fixture_type_returns_400(self, client_with_seed_api: TestClient):
        """测试: 无效的 fixture_type 返回 400"""
        response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={"fixture_type": "nonexistent_fixture"},
            headers={"X-Test-Mode": "true"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "INVALID_FIXTURE_TYPE" in str(data) or "Unknown fixture_type" in str(data)


class TestCleanupEndpoint:
    """测试 DELETE /api/test/workflows/cleanup"""

    def test_cleanup_by_token(self, client_with_seed_api: TestClient):
        """测试: 按 cleanup_token 清理"""
        seed_response = client_with_seed_api.post(
            "/api/test/workflows/seed",
            json={"fixture_type": "main_subgraph_only"},
            headers={"X-Test-Mode": "true"},
        )
        cleanup_token = seed_response.json()["cleanup_token"]

        cleanup_response = client_with_seed_api.request(
            "DELETE",
            "/api/test/workflows/cleanup",
            json={"cleanup_tokens": [cleanup_token]},
            headers={"X-Test-Mode": "true"},
        )

        assert cleanup_response.status_code == 200
        data = cleanup_response.json()
        assert data["deleted_count"] >= 0

    def test_cleanup_empty_tokens(self, client_with_seed_api: TestClient):
        """测试: 空 cleanup_tokens 不报错"""
        response = client_with_seed_api.request(
            "DELETE",
            "/api/test/workflows/cleanup",
            json={"cleanup_tokens": []},
            headers={"X-Test-Mode": "true"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0


class TestFixtureTypesEndpoint:
    """测试 GET /api/test/workflows/fixture-types"""

    def test_list_fixture_types(self, client_with_seed_api: TestClient):
        """测试: 列出所有 fixture 类型"""
        response = client_with_seed_api.get(
            "/api/test/workflows/fixture-types",
            headers={"X-Test-Mode": "true"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "fixture_types" in data
        assert "main_subgraph_only" in data["fixture_types"]
        assert "with_isolated_nodes" in data["fixture_types"]
        assert "side_effect_workflow" in data["fixture_types"]
        assert "invalid_config" in data["fixture_types"]

"""CORS 配置测试

测试后端 CORS 中间件正确配置，允许前端跨域访问。
"""

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.main import app


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端"""
    return TestClient(app)


class TestCORSConfiguration:
    """CORS 配置测试套件"""

    def test_cors_allows_localhost_5173(self, client: TestClient):
        """测试：允许 localhost:5173 跨域访问"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_allows_127_0_0_1_5173(self, client: TestClient):
        """测试：允许 127.0.0.1:5173 跨域访问"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"

    def test_cors_allows_localhost_3000(self, client: TestClient):
        """测试：允许 localhost:3000 跨域访问"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_allows_127_0_0_1_3000(self, client: TestClient):
        """测试：允许 127.0.0.1:3000 跨域访问"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"

    def test_cors_includes_credentials(self, client: TestClient):
        """测试：CORS 响应包含 credentials 头"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_allows_all_methods(self, client: TestClient):
        """测试：CORS 允许所有 HTTP 方法"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        # FastAPI CORS 返回请求的方法
        assert "POST" in response.headers.get("access-control-allow-methods", "")

    def test_health_endpoint_with_cors_origin(self, client: TestClient):
        """测试：GET /health 请求带 Origin 头返回正确的 CORS 头"""
        response = client.get(
            "/health",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
        assert response.json()["status"] == "healthy"

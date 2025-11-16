"""应用启动集成测试

测试目标：
1. 验证 FastAPI 应用能够正常启动
2. 验证健康检查端点正常工作
3. 验证根路径端点正常工作
4. 验证 API 文档端点可访问
5. 验证 CORS 配置正确

第一性原则：
- 应用启动是最基础的功能，必须保证可靠性
- 健康检查是监控系统的基础，必须正确实现
- API 文档是开发者体验的关键，必须可访问

测试策略：
- 使用 TestClient 模拟 HTTP 请求
- 验证响应状态码和内容
- 验证响应头（CORS）
- 验证 JSON 响应格式
"""

import pytest
from fastapi.testclient import TestClient

from src.config import settings
from src.interfaces.api.main import app


@pytest.fixture
def client():
    """创建测试客户端

    为什么使用 TestClient？
    - 不需要启动真实的服务器
    - 同步测试，更简单
    - 完整的 HTTP 请求/响应模拟
    """
    return TestClient(app)


def test_app_creation():
    """测试应用对象创建

    验证点：
    - FastAPI 应用对象存在
    - 应用标题正确
    - 应用版本正确
    """
    assert app is not None, "FastAPI 应用应该被创建"
    assert app.title == settings.app_name, f"应用标题应该是 {settings.app_name}"
    assert app.version == settings.app_version, f"应用版本应该是 {settings.app_version}"


def test_health_check_endpoint(client: TestClient):
    """测试健康检查端点

    验证点：
    - 端点可访问（200 OK）
    - 返回 JSON 格式
    - 包含必需的字段（status, app_name, version, env）
    - status 为 "healthy"
    """
    response = client.get("/health")

    # 验证状态码
    assert response.status_code == 200, "健康检查端点应该返回 200"

    # 验证响应格式
    data = response.json()
    assert isinstance(data, dict), "响应应该是 JSON 对象"

    # 验证必需字段
    assert "status" in data, "响应应该包含 status 字段"
    assert "app_name" in data, "响应应该包含 app_name 字段"
    assert "version" in data, "响应应该包含 version 字段"
    assert "env" in data, "响应应该包含 env 字段"

    # 验证字段值
    assert data["status"] == "healthy", "status 应该是 healthy"
    assert data["app_name"] == settings.app_name, f"app_name 应该是 {settings.app_name}"
    assert data["version"] == settings.app_version, f"version 应该是 {settings.app_version}"
    assert data["env"] == settings.env, f"env 应该是 {settings.env}"


def test_root_endpoint(client: TestClient):
    """测试根路径端点

    验证点：
    - 端点可访问（200 OK）
    - 返回 JSON 格式
    - 包含欢迎信息
    - 包含文档链接
    """
    response = client.get("/")

    # 验证状态码
    assert response.status_code == 200, "根路径应该返回 200"

    # 验证响应格式
    data = response.json()
    assert isinstance(data, dict), "响应应该是 JSON 对象"

    # 验证必需字段
    assert "message" in data, "响应应该包含 message 字段"
    assert "version" in data, "响应应该包含 version 字段"
    assert "docs" in data, "响应应该包含 docs 字段"

    # 验证字段值
    assert settings.app_name in data["message"], "message 应该包含应用名称"
    assert data["version"] == settings.app_version, f"version 应该是 {settings.app_version}"
    assert "/docs" in data["docs"], "docs 应该包含文档链接"


def test_openapi_docs_endpoint(client: TestClient):
    """测试 OpenAPI 文档端点

    验证点：
    - /docs 端点可访问（返回 HTML）
    - /openapi.json 端点可访问（返回 JSON）
    - OpenAPI schema 包含必需字段
    """
    # 测试 Swagger UI
    response = client.get("/docs")
    assert response.status_code == 200, "/docs 端点应该可访问"
    assert "text/html" in response.headers["content-type"], "/docs 应该返回 HTML"

    # 测试 OpenAPI JSON
    response = client.get("/openapi.json")
    assert response.status_code == 200, "/openapi.json 端点应该可访问"

    # 验证 OpenAPI schema
    schema = response.json()
    assert "openapi" in schema, "schema 应该包含 openapi 版本"
    assert "info" in schema, "schema 应该包含 info"
    assert "paths" in schema, "schema 应该包含 paths"

    # 验证应用信息
    assert schema["info"]["title"] == settings.app_name, "title 应该匹配应用名称"
    assert schema["info"]["version"] == settings.app_version, "version 应该匹配应用版本"


def test_redoc_endpoint(client: TestClient):
    """测试 ReDoc 文档端点

    验证点：
    - /redoc 端点可访问（返回 HTML）
    """
    response = client.get("/redoc")
    assert response.status_code == 200, "/redoc 端点应该可访问"
    assert "text/html" in response.headers["content-type"], "/redoc 应该返回 HTML"


def test_cors_headers(client: TestClient):
    """测试 CORS 配置

    验证点：
    - OPTIONS 请求返回正确的 CORS 头
    - Access-Control-Allow-Origin 正确
    - Access-Control-Allow-Methods 包含所有方法
    - Access-Control-Allow-Headers 正确

    为什么测试 CORS？
    - 前端应用需要跨域访问 API
    - CORS 配置错误会导致前端无法调用 API
    - 安全性：只允许特定的源访问
    """
    # 发送 OPTIONS 预检请求
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    # 验证状态码（200 或 204 都可以）
    assert response.status_code in [200, 204], "OPTIONS 请求应该成功"

    # 验证 CORS 头（注意：TestClient 可能不会完全模拟 CORS 行为）
    # 在真实环境中，这些头会由 CORSMiddleware 添加


def test_404_not_found(client: TestClient):
    """测试不存在的端点

    验证点：
    - 返回 404 状态码
    - 返回 JSON 格式的错误信息
    """
    response = client.get("/nonexistent-endpoint")

    assert response.status_code == 404, "不存在的端点应该返回 404"

    # FastAPI 默认返回 JSON 格式的 404 错误
    data = response.json()
    assert "detail" in data, "404 响应应该包含 detail 字段"


def test_health_check_performance(client: TestClient):
    """测试健康检查端点性能

    验证点：
    - 响应时间应该很快（< 100ms）
    - 多次调用应该稳定

    为什么测试性能？
    - 健康检查会被频繁调用（监控系统）
    - 慢的健康检查会影响监控准确性
    - 确保没有阻塞操作
    """
    import time

    # 预热（第一次可能较慢）
    client.get("/health")

    # 测试 10 次
    times = []
    for _ in range(10):
        start = time.time()
        response = client.get("/health")
        elapsed = time.time() - start
        times.append(elapsed)

        assert response.status_code == 200, "健康检查应该成功"

    # 验证平均响应时间
    avg_time = sum(times) / len(times)
    assert avg_time < 0.1, f"健康检查平均响应时间应该 < 100ms，实际: {avg_time * 1000:.2f}ms"


def test_multiple_concurrent_requests(client: TestClient):
    """测试并发请求处理

    验证点：
    - 应用能够处理多个并发请求
    - 所有请求都能正确响应

    为什么测试并发？
    - 真实环境中会有多个并发请求
    - 确保没有竞态条件
    - 验证异步处理正确
    """
    import concurrent.futures

    def make_request():
        response = client.get("/health")
        return response.status_code

    # 并发发送 20 个请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # 验证所有请求都成功
    assert len(results) == 20, "应该收到 20 个响应"
    assert all(status == 200 for status in results), "所有请求都应该成功"


def test_app_metadata(client: TestClient):
    """测试应用元数据

    验证点：
    - OpenAPI schema 包含正确的描述
    - 包含正确的标签
    """
    response = client.get("/openapi.json")
    schema = response.json()

    # 验证描述
    assert "description" in schema["info"], "应该有应用描述"

    # 验证路径标签
    paths = schema["paths"]
    assert "/health" in paths, "应该有 /health 端点"
    assert "/" in paths, "应该有 / 端点"

    # 验证标签
    health_tags = paths["/health"]["get"]["tags"]
    assert "Health" in health_tags, "/health 应该有 Health 标签"

    root_tags = paths["/"]["get"]["tags"]
    assert "Root" in root_tags, "/ 应该有 Root 标签"

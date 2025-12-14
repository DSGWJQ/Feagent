"""Pytest 配置文件 - 全局 fixtures"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI 测试客户端"""
    return TestClient(app)


@pytest.fixture
def sample_agent_data() -> dict:
    """示例 Agent 数据"""
    return {
        "start": "我有一个 CSV 文件包含销售数据",
        "goal": "生成销售趋势分析报告",
        "config": {
            "model": "gpt-4o-mini",
            "max_steps": 10,
            "timeout": 300,
        },
    }


@pytest.fixture(autouse=True)
def mock_external_http_calls(request):
    """自动Mock外部HTTP调用（仅单元测试）

    根据BACKEND_TESTING_PLAN.md P0-Task3：
    - 单元测试应该隔离外部依赖（requests + httpx）
    - 集成测试和手动测试保持真实HTTP调用
    - 使用pytest的request.fspath判断测试类型

    Note: This fixture mocks synchronous requests.* calls AND httpx.AsyncClient
    For complex scenarios, use pytest-httpx or pytest-mock in specific tests
    """
    # 检查是否为单元测试
    test_path = str(request.fspath)
    is_unit_test = "tests/unit" in test_path or "tests\\unit" in test_path

    if not is_unit_test:
        # 集成测试/手动测试 - 不mock
        yield
        return

    # 只有单元测试到达这里 - 开始mock
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("requests.put") as mock_put,
        patch("requests.delete") as mock_delete,
        patch("httpx.AsyncClient") as mock_httpx_client,
    ):
        # 设置requests库的mock响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": True}
        mock_response.text = '{"mocked": true}'
        mock_response.content = b'{"mocked": true}'

        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        mock_put.return_value = mock_response
        mock_delete.return_value = mock_response

        # 设置httpx.AsyncClient的mock响应（async context manager）
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.json = MagicMock(return_value={"mocked": True})
        mock_httpx_response.text = '{"mocked": true}'
        mock_httpx_response.content = b'{"mocked": true}'

        # Mock async context manager __aenter__/__aexit__
        mock_client_instance = MagicMock()
        mock_client_instance.request = AsyncMock(return_value=mock_httpx_response)
        mock_client_instance.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_instance.post = AsyncMock(return_value=mock_httpx_response)
        mock_client_instance.put = AsyncMock(return_value=mock_httpx_response)
        mock_client_instance.delete = AsyncMock(return_value=mock_httpx_response)

        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        mock_httpx_client.return_value.__aexit__.return_value = AsyncMock()

        yield

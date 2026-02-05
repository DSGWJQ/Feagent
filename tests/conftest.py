"""Pytest 配置文件 - 全局 fixtures"""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import settings

# Force a test-scoped SQLite DB by default (fail-closed / deterministic).
# Rationale:
# - The repository `.env` may point to a local demo DB in a temp folder.
# - Many tests import `SessionLocal` at module import time, so we must override
#   settings BEFORE any engine/sessionmaker module is imported.
if settings.database_url.startswith("sqlite"):
    settings.database_url = "sqlite+aiosqlite:///./test_pytest.db"


@pytest.fixture(scope="session", autouse=True)
def normalize_test_feature_flags() -> None:
    """Normalize feature flags for the pytest suite.

    The repository `.env` is tuned for local demos (deterministic mode, legacy execution, test seed APIs).
    The pytest suite, however, expects a test-like baseline:
    - Runs enabled by default (tests patch disable_run_persistence explicitly when needed).
    - Test seed APIs disabled by default (tests enable them explicitly when needed).
    - Executor deterministic mode disabled by default (unit tests validate real error paths).
    """

    original_env = settings.env
    original_disable_run_persistence = settings.disable_run_persistence
    original_enable_test_seed_api = settings.enable_test_seed_api
    original_e2e_test_mode = settings.e2e_test_mode

    settings.env = "test"
    settings.disable_run_persistence = False
    settings.enable_test_seed_api = False
    settings.e2e_test_mode = "hybrid"

    try:
        yield
    finally:
        settings.env = original_env
        settings.disable_run_persistence = original_disable_run_persistence
        settings.enable_test_seed_api = original_enable_test_seed_api
        settings.e2e_test_mode = original_e2e_test_mode


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI 测试客户端"""
    # Import lazily so settings overrides above are applied before the app initializes engines.
    from src.interfaces.api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def ensure_sync_event_loop(request: pytest.FixtureRequest):
    """Provide a default event loop for sync tests that call `asyncio.get_event_loop()`.

    Red-team note:
    - Some legacy sync tests still rely on `asyncio.get_event_loop().run_until_complete(...)`.
    - Other tests may close/unset the global loop, causing order-dependent failures.
    - We avoid touching async (`@pytest.mark.asyncio`) tests to prevent interfering with pytest-asyncio.
    """

    if request.node.get_closest_marker("asyncio") is not None:
        yield
        return

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("event loop is closed")
        yield
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            yield
        finally:
            loop.close()
            asyncio.set_event_loop(None)


@pytest.fixture(scope="session", autouse=True)
def bootstrap_test_sqlite_schema(normalize_test_feature_flags) -> None:  # noqa: ANN001
    """Ensure the configured SQLite DB has an up-to-date schema for tests.

    Red-team note:
    - Some integration tests validate the actual DB schema via raw SQL.
    - These tests create their own engines and do not go through FastAPI lifespan hooks.
    - To keep the suite deterministic, we reset and bootstrap the test SQLite database once per session.
    """

    if settings.env != "test":
        return

    url = settings.database_url
    if not url.startswith("sqlite"):
        return

    sync_url = url.replace("+aiosqlite", "")
    if sync_url.endswith(":memory:"):
        return

    path_prefix = "sqlite:///"
    if not sync_url.startswith(path_prefix):
        return

    raw_path = sync_url[len(path_prefix) :]
    if not raw_path or raw_path.startswith("file:"):
        return

    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()

    # Fail-closed safety guard: only reset clearly test-scoped DB files.
    if not (db_path.name.startswith("test_") and db_path.suffix == ".db"):
        return

    try:
        if db_path.exists():
            db_path.unlink()
    except OSError:
        # If the DB is locked (e.g., by an IDE), avoid masking the error later.
        raise

    from src.infrastructure.database.schema import ensure_sqlite_schema

    ensure_sqlite_schema()


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

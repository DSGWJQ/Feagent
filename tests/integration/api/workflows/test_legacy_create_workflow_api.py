"""测试：Legacy POST /api/workflows（兼容期保留）.

覆盖点（WCC-070）：
- 当 nodes 为空时，仍可创建 workflow（使用统一的基底 workflow shape：start->end）
- 响应包含 deprecation 提示头，指导迁移到 /api/workflows/chat-create/stream
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.infrastructure.database import models  # noqa: F401 - 注册 ORM 模型
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.dependencies.rag import get_rag_service
from src.interfaces.api.routes import workflows as workflows_routes


@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(test_engine):
    test_app = FastAPI()
    test_app.include_router(workflows_routes.router, prefix="/api")

    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def override_get_rag_service():
        yield object()

    test_app.dependency_overrides[get_db_session] = override_get_db_session
    test_app.dependency_overrides[get_rag_service] = override_get_rag_service
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


class TestLegacyCreateWorkflowAPI:
    def test_create_without_nodes_uses_base_workflow_shape_and_sets_deprecation_headers(
        self,
        client: TestClient,
    ):
        response = client.post(
            "/api/workflows",
            json={"name": "legacy", "description": "deprecated create"},
        )

        assert response.status_code == 201
        assert response.headers.get("Deprecation") == "true"
        assert "/api/workflows/chat-create/stream" in (response.headers.get("Link") or "")
        assert "Deprecated" in (response.headers.get("Warning") or "")

        body = response.json()
        assert body["name"] == "legacy"
        assert len(body["nodes"]) >= 2
        assert {node["type"] for node in body["nodes"]} >= {"start", "end"}
        assert any(edge["source"] and edge["target"] for edge in body["edges"])

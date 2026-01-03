"""测试：Legacy POST /api/workflows（已移除）.

覆盖点（WCC-070）：
- POST /api/workflows 不应再被挂载到 API app（应当 404）
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
    def test_legacy_create_is_removed(
        self,
        client: TestClient,
    ):
        response = client.post(
            "/api/workflows",
            json={"name": "legacy", "description": "deprecated create"},
        )

        assert response.status_code == 404

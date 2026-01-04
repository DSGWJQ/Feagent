from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import settings
from src.domain.entities.user import User
from src.domain.value_objects.user_role import UserRole
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dependencies.current_user import get_current_user_optional
from src.interfaces.api.dependencies.rag import get_rag_service
from src.interfaces.api.routes import workflows as workflows_routes

_WORKFLOWS_LOGGER_NAME = "src.interfaces.api.routes.workflows"


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


@pytest.fixture()
def app_with_overrides(test_engine) -> FastAPI:
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

    def override_get_container():
        def workflow_repository(session: Session):
            return SQLAlchemyWorkflowRepository(session)

        tool_repo = Mock()
        tool_repo.exists.return_value = False
        tool_repo.find_by_id.return_value = None

        return ApiContainer(
            executor_registry=create_executor_registry(),
            workflow_execution_kernel=lambda _s: Mock(),
            workflow_run_execution_entry=lambda _s: Mock(),
            conversation_turn_orchestrator=lambda: Mock(),
            user_repository=lambda _s: Mock(),
            agent_repository=lambda _s: Mock(),
            task_repository=lambda _s: Mock(),
            workflow_repository=workflow_repository,
            chat_message_repository=lambda _s: Mock(),
            llm_provider_repository=lambda _s: Mock(),
            tool_repository=lambda _s: tool_repo,
            run_repository=lambda _s: Mock(),
            scheduled_workflow_repository=lambda _s: Mock(),
        )

    test_app.dependency_overrides[get_db_session] = override_get_db_session
    test_app.dependency_overrides[get_rag_service] = override_get_rag_service
    test_app.dependency_overrides[get_container] = override_get_container
    test_app.dependency_overrides[get_current_user_optional] = lambda: None
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture()
def client(app_with_overrides: FastAPI) -> TestClient:
    return TestClient(app_with_overrides)


def test_internal_import_disabled_by_default_returns_410(client: TestClient, caplog):
    caplog.set_level(logging.INFO, logger=_WORKFLOWS_LOGGER_NAME)
    response = client.post(
        "/api/workflows/import",
        json={
            "coze_json": {
                "workflow_id": "coze_wf_1",
                "name": "Imported",
                "description": "desc",
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "start",
                        "name": "Start",
                        "config": {},
                        "position": {"x": 0, "y": 0},
                    }
                ],
                "edges": [],
            }
        },
    )
    assert response.status_code == 410
    assert response.headers.get("Deprecation") == "true"
    assert response.headers.get("Warning")
    assert response.json().get("detail")
    assert any(r.message == "workflow_internal_create_blocked" for r in caplog.records)


def test_internal_generate_disabled_by_default_returns_410(client: TestClient, caplog):
    caplog.set_level(logging.INFO, logger=_WORKFLOWS_LOGGER_NAME)
    response = client.post(
        "/api/workflows/generate-from-form",
        json={"description": "d", "goal": "g"},
    )
    assert response.status_code == 410
    assert response.headers.get("Deprecation") == "true"
    assert response.headers.get("Warning")
    assert response.json().get("detail")
    assert any(r.message == "workflow_internal_create_blocked" for r in caplog.records)


def test_internal_import_requires_admin_when_enabled(
    client: TestClient, app_with_overrides: FastAPI, monkeypatch
):
    monkeypatch.setattr(settings, "enable_internal_workflow_create_endpoints", True)

    response = client.post(
        "/api/workflows/import",
        json={
            "coze_json": {
                "workflow_id": "coze_wf_1",
                "name": "Imported",
                "description": "desc",
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "start",
                        "name": "Start",
                        "config": {},
                        "position": {"x": 0, "y": 0},
                    }
                ],
                "edges": [],
            }
        },
    )
    assert response.status_code == 403


def test_internal_import_succeeds_for_admin_when_enabled(
    client: TestClient,
    app_with_overrides: FastAPI,
    monkeypatch,
    caplog,
):
    caplog.set_level(logging.INFO, logger=_WORKFLOWS_LOGGER_NAME)
    monkeypatch.setattr(settings, "enable_internal_workflow_create_endpoints", True)
    admin_user = User(
        id="user_admin",
        github_id=1,
        github_username="admin",
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
    app_with_overrides.dependency_overrides[get_current_user_optional] = lambda: admin_user

    response = client.post(
        "/api/workflows/import",
        json={
            "coze_json": {
                "workflow_id": "coze_wf_2",
                "name": "Imported2",
                "description": "desc2",
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "start",
                        "name": "Start",
                        "config": {},
                        "position": {"x": 0, "y": 0},
                    }
                ],
                "edges": [],
            }
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["workflow_id"].startswith("wf_")
    assert body["name"] == "Imported2"
    assert body["source"] == "coze"
    assert body["source_id"] == "coze_wf_2"

    assert any(r.message == "workflow_internal_create_succeeded" for r in caplog.records)

    # Rollback: disabling the feature flag restores default unreachability.
    monkeypatch.setattr(settings, "enable_internal_workflow_create_endpoints", False)
    response = client.post(
        "/api/workflows/import",
        json={
            "coze_json": {
                "workflow_id": "coze_wf_3",
                "name": "Imported3",
                "description": "desc3",
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "start",
                        "name": "Start",
                        "config": {},
                        "position": {"x": 0, "y": 0},
                    }
                ],
                "edges": [],
            }
        },
    )
    assert response.status_code == 410


def test_internal_generate_requires_admin_when_enabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_internal_workflow_create_endpoints", True)
    response = client.post(
        "/api/workflows/generate-from-form",
        json={"description": "d", "goal": "g"},
    )
    assert response.status_code == 403


def test_internal_generate_returns_503_for_admin_when_enabled_without_openai_key(
    client: TestClient,
    app_with_overrides: FastAPI,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "enable_internal_workflow_create_endpoints", True)
    monkeypatch.setattr(settings, "openai_api_key", "")

    admin_user = User(
        id="user_admin",
        github_id=1,
        github_username="admin",
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
    app_with_overrides.dependency_overrides[get_current_user_optional] = lambda: admin_user

    response = client.post(
        "/api/workflows/generate-from-form",
        json={"description": "d", "goal": "g"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "OPENAI_API_KEY is not configured."

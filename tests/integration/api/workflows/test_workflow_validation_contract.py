from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainValidationError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
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

    registry: NodeExecutorRegistry = create_executor_registry()
    tool_repo = Mock()
    tool_repo.exists.return_value = False
    tool_repo.find_by_id.return_value = None

    def override_get_container():
        def workflow_repository(session: Session):
            return SQLAlchemyWorkflowRepository(session)

        def tool_repository(_session: Session):
            return tool_repo

        return ApiContainer(
            executor_registry=registry,
            workflow_execution_kernel=lambda _s: Mock(),
            conversation_turn_orchestrator=lambda: Mock(),
            user_repository=lambda _s: Mock(),
            agent_repository=lambda _s: Mock(),
            task_repository=lambda _s: Mock(),
            workflow_repository=workflow_repository,
            chat_message_repository=lambda _s: Mock(),
            llm_provider_repository=lambda _s: Mock(),
            tool_repository=tool_repository,
            run_repository=lambda _s: Mock(),
            scheduled_workflow_repository=lambda _s: Mock(),
        )

    test_app.dependency_overrides[get_db_session] = override_get_db_session
    test_app.dependency_overrides[get_rag_service] = override_get_rag_service
    test_app.dependency_overrides[get_container] = override_get_container
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture()
def client(app_with_overrides: FastAPI) -> TestClient:
    return TestClient(app_with_overrides)


@pytest.fixture()
def workflow_id(test_engine) -> str:
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db: Session = TestingSessionLocal()
    try:
        repo = SQLAlchemyWorkflowRepository(db)
        workflow = Workflow.create_base(description="base")
        repo.save(workflow)
        db.commit()
        return workflow.id
    finally:
        db.close()


def test_drag_update_returns_structured_validation_error(client: TestClient, workflow_id: str):
    response = client.patch(
        f"/api/workflows/{workflow_id}",
        json={
            "nodes": [
                {
                    "id": "node_tool",
                    "type": "tool",
                    "name": "Tool Node",
                    "data": {},
                    "position": {"x": 0, "y": 0},
                }
            ],
            "edges": [],
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["code"] == "workflow_invalid"
    codes = {err.get("code") for err in payload["detail"]["errors"]}
    assert "missing_executor" in codes
    assert "missing_tool_id" in codes


def test_chat_update_returns_structured_validation_error(
    client: TestClient, workflow_id: str, app_with_overrides
):
    class _StubUseCase:
        def execute(self, _input_data):
            raise DomainValidationError(
                "Workflow validation failed",
                code="workflow_invalid",
                errors=[{"code": "cycle_detected", "message": "cycle"}],
            )

    def override_use_case(workflow_id: str):
        return _StubUseCase()

    app_with_overrides.dependency_overrides[
        workflows_routes.get_update_workflow_by_chat_use_case
    ] = override_use_case

    response = client.post(
        f"/api/workflows/{workflow_id}/chat",
        json={"message": "hi"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["code"] == "workflow_invalid"

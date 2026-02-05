from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.workflow_execution_orchestrator import (
    WorkflowExecutionOrchestrator,
    WorkflowExecutionPolicy,
)
from src.config import settings
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.run import Run
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import NotFoundError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.event_bus import EventBus
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.run_event_repository import (
    SQLAlchemyRunEventRepository,
)
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
from src.infrastructure.database.transaction_manager import SQLAlchemyTransactionManager
from src.interfaces.api.container import ApiContainer
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


def test_execute_stream_endpoint_goes_through_orchestrator_and_policy_chain(
    monkeypatch: pytest.MonkeyPatch, test_engine
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)
    monkeypatch.setattr(settings, "enable_langgraph_workflow_executor", False)

    calls: list[str] = []

    class FakeFacade:
        async def execute_streaming(self, *, workflow_id: str, input_data=None):
            yield {"type": "node_start", "metadata": {"workflow_id": workflow_id}}
            yield {"type": "workflow_complete", "metadata": {"workflow_id": workflow_id}}

    class RecordingPolicy(WorkflowExecutionPolicy):
        async def before_execute(
            self,
            *,
            workflow_id: str,
            input_data,
            correlation_id: str | None,
            original_decision_id: str | None,
        ) -> None:
            calls.append("before")

        async def after_execute(
            self,
            *,
            workflow_id: str,
            input_data,
            result,
            correlation_id: str | None,
            original_decision_id: str | None,
        ) -> None:
            calls.append("after")

        async def on_error(
            self,
            *,
            workflow_id: str,
            input_data,
            error: Exception,
            correlation_id: str | None,
            original_decision_id: str | None,
        ) -> None:
            calls.append("error")

        async def on_event(
            self,
            *,
            workflow_id: str,
            input_data,
            event: dict,
            correlation_id: str | None,
            original_decision_id: str | None,
        ) -> None:
            calls.append("event")

    def orchestrator_factory(_: Session) -> WorkflowExecutionOrchestrator:
        return WorkflowExecutionOrchestrator(facade=FakeFacade(), policies=[RecordingPolicy()])

    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Seed a CREATED run so the execute/stream endpoint can fail-closed on run_id.
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db: Session = TestingSessionLocal()
    try:
        run = Run.create(project_id="proj_1", workflow_id="wf_123")
        SQLAlchemyRunRepository(db).save(run)
        db.commit()
    finally:
        db.close()

    def _noop_repo(_: Session):
        return None

    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=1, y=0))
    workflow = Workflow.create(
        name="test",
        description="",
        nodes=[start, end],
        edges=[Edge.create(source_node_id=start.id, target_node_id=end.id)],
    )
    workflow.id = "wf_123"

    class _FakeWorkflowRepository:
        def get_by_id(self, workflow_id: str):
            if workflow_id != workflow.id:
                raise NotFoundError(entity_type="Workflow", entity_id=workflow_id)
            return workflow

    test_app = FastAPI()
    test_app.state.event_bus = EventBus()

    class _AllowCoordinator:
        def validate_decision(self, decision: dict):
            return type("Validation", (), {"is_valid": True, "errors": []})()

    test_app.state.coordinator = _AllowCoordinator()

    # Phase 5: execute/stream must go through WorkflowRunExecutionEntry (Runs is the execution SoT).
    def workflow_run_execution_entry_factory(session: Session):
        from src.application.services.workflow_run_execution_entry import WorkflowRunExecutionEntry
        from src.application.use_cases.append_run_event import AppendRunEventUseCase
        from src.application.use_cases.execute_workflow import WORKFLOW_EXECUTION_KERNEL_ID

        run_repo = SQLAlchemyRunRepository(session)
        return WorkflowRunExecutionEntry(
            workflow_repository=_FakeWorkflowRepository(),
            run_repository=run_repo,
            save_validator=MagicMock(validate_for_execution_or_raise=lambda _w: None),
            run_event_use_case=AppendRunEventUseCase(
                run_repository=run_repo,
                run_event_repository=SQLAlchemyRunEventRepository(session),
                transaction_manager=SQLAlchemyTransactionManager(session),
            ),
            kernel=orchestrator_factory(session),
            executor_id=WORKFLOW_EXECUTION_KERNEL_ID,
        )

    test_app.state.container = ApiContainer(
        executor_registry=NodeExecutorRegistry(),
        workflow_execution_kernel=orchestrator_factory,
        workflow_run_execution_entry=workflow_run_execution_entry_factory,
        conversation_turn_orchestrator=lambda: None,  # type: ignore[return-value]
        user_repository=_noop_repo,
        agent_repository=_noop_repo,
        task_repository=_noop_repo,
        workflow_repository=lambda _s: _FakeWorkflowRepository(),
        chat_message_repository=_noop_repo,
        llm_provider_repository=_noop_repo,
        tool_repository=_noop_repo,
        run_repository=_noop_repo,
        scheduled_workflow_repository=_noop_repo,
    )
    test_app.dependency_overrides[get_db_session] = override_get_db_session
    test_app.include_router(workflows_routes.router, prefix="/api")

    with TestClient(test_app) as client:
        response = client.post(
            "/api/workflows/wf_123/execute/stream",
            json={"initial_input": {"k": "v"}, "run_id": run.id},
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert [e["type"] for e in events] == ["node_start", "workflow_complete"]
    assert all(e["run_id"] == run.id for e in events)
    assert calls == ["before", "event", "event"]

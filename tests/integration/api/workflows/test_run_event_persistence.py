"""T-RUN-1：execute/stream 关键事件强一致落库（workflow_start/workflow_complete/workflow_error）。

覆盖点：
- POST /api/workflows/{id}/execute/stream 强制 run_id
- start/complete 事件可查询且不丢（数据库 RunEventModel）
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.workflow_execution_orchestrator import WorkflowExecutionOrchestrator
from src.config import settings
from src.domain.entities.run import Run
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.models import RunEventModel
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
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


def test_t_run_1_execute_stream_persists_key_events(
    monkeypatch: pytest.MonkeyPatch, test_engine
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)
    monkeypatch.setattr(settings, "enable_langgraph_workflow_executor", False)

    class FakeFacade:
        async def execute_streaming(self, *, workflow_id: str, input_data=None):
            yield {"type": "node_start", "metadata": {"workflow_id": workflow_id}}
            yield {"type": "workflow_complete", "metadata": {"workflow_id": workflow_id}}

    def orchestrator_factory(_: Session) -> WorkflowExecutionOrchestrator:
        return WorkflowExecutionOrchestrator(facade=FakeFacade())

    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Seed a CREATED run and ensure it is queryable.
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

    test_app = FastAPI()
    test_app.state.container = ApiContainer(
        executor_registry=NodeExecutorRegistry(),
        workflow_execution_kernel=orchestrator_factory,
        conversation_turn_orchestrator=lambda: None,  # type: ignore[return-value]
        user_repository=_noop_repo,
        agent_repository=_noop_repo,
        task_repository=_noop_repo,
        workflow_repository=_noop_repo,
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

    # Assert key run events are persisted (strong consistency: start + complete).
    db = TestingSessionLocal()
    try:
        rows = db.execute(
            select(RunEventModel.type)
            .where(RunEventModel.run_id == run.id)
            .order_by(RunEventModel.id.asc())
        ).all()
        event_types = [r[0] for r in rows]
        assert event_types[:2] == ["workflow_start", "workflow_complete"]
    finally:
        db.close()

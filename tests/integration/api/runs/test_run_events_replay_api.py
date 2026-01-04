"""Integration tests: GET /api/runs/{run_id}/events (Run replay)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.run_event import RunEvent
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.models import RunEventModel
from src.infrastructure.database.repositories.run_event_repository import (
    SQLAlchemyRunEventRepository,
)
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.main import app


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
def client(test_engine):
    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session(test_engine) -> Session:
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_simple_workflow(db: Session) -> Workflow:
    node1 = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node2 = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=100, y=0))
    edge = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
    workflow = Workflow.create(name="wf", description="", nodes=[node1, node2], edges=[edge])
    repo = SQLAlchemyWorkflowRepository(db)
    repo.save(workflow)
    db.commit()
    return workflow


def test_list_run_events_paginates_and_preserves_sse_shape(client: TestClient, db_session: Session):
    workflow = _create_simple_workflow(db_session)

    # create run via API (ensures run exists for fail-closed replay endpoint)
    run_resp = client.post(f"/api/projects/proj_1/workflows/{workflow.id}/runs", json={})
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    # seed run_events (execution channel) directly for deterministic replay
    run_event_repo = SQLAlchemyRunEventRepository(db_session)
    run_event_repo.append(
        RunEvent.create(
            run_id=run_id, type="node_start", channel="execution", payload={"node_id": "n1"}
        )
    )
    run_event_repo.append(
        RunEvent.create(
            run_id=run_id,
            type="node_complete",
            channel="execution",
            payload={"node_id": "n1", "output": {"ok": True}},
        )
    )
    run_event_repo.append(
        RunEvent.create(
            run_id=run_id,
            type="workflow_complete",
            channel="execution",
            payload={"result": {"ok": True}},
        )
    )
    # terminal event should be unique per (run_id, type, channel)
    run_event_repo.append(
        RunEvent.create(
            run_id=run_id,
            type="workflow_complete",
            channel="execution",
            payload={"result": {"ok": True, "dup": True}},
        )
    )
    db_session.commit()

    terminal_count = db_session.execute(
        select(func.count(RunEventModel.id)).where(
            RunEventModel.run_id == run_id,
            RunEventModel.type == "workflow_complete",
            RunEventModel.channel == "execution",
        )
    ).scalar_one()
    assert terminal_count == 1

    page1 = client.get(f"/api/runs/{run_id}/events?limit=2")
    assert page1.status_code == 200
    payload1 = page1.json()
    assert payload1["run_id"] == run_id
    assert payload1["has_more"] is True
    assert isinstance(payload1["next_cursor"], int)
    assert len(payload1["events"]) == 2

    # SSE shape: flattened fields (no nested payload)
    assert payload1["events"][0]["type"] == "node_start"
    assert payload1["events"][0]["run_id"] == run_id
    assert payload1["events"][0]["node_id"] == "n1"
    assert "payload" not in payload1["events"][0]

    page2 = client.get(f"/api/runs/{run_id}/events?cursor={payload1['next_cursor']}&limit=2")
    assert page2.status_code == 200
    payload2 = page2.json()
    assert payload2["has_more"] is False
    assert payload2["next_cursor"] is None
    assert len(payload2["events"]) == 1
    assert payload2["events"][0]["type"] == "workflow_complete"
    assert payload2["events"][0]["run_id"] == run_id


def test_create_run_is_idempotent_with_idempotency_key(
    client: TestClient, db_session: Session
) -> None:
    """INV-7: POST /runs is idempotent per (project_id, workflow_id, Idempotency-Key)."""

    workflow = _create_simple_workflow(db_session)

    resp1 = client.post(
        f"/api/projects/proj_1/workflows/{workflow.id}/runs",
        json={},
        headers={"Idempotency-Key": "key_1"},
    )
    assert resp1.status_code == 200
    run_id_1 = resp1.json()["id"]

    resp2 = client.post(
        f"/api/projects/proj_1/workflows/{workflow.id}/runs",
        json={},
        headers={"Idempotency-Key": "key_1"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == run_id_1

    assert SQLAlchemyRunRepository(db_session).count_by_workflow_id(workflow.id) == 1


def test_list_run_events_returns_404_when_run_missing(client: TestClient):
    resp = client.get("/api/runs/run_missing/events")
    assert resp.status_code == 404

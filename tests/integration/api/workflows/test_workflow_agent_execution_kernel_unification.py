"""WFCORE-030: REST execute/stream and WorkflowAgent execute_workflow share one authoritative entry."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
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


def _create_simple_workflow(db: Session) -> Workflow:
    node1 = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node2 = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=100, y=0))
    edge = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
    workflow = Workflow.create(name="wf", description="", nodes=[node1, node2], edges=[edge])
    repo = SQLAlchemyWorkflowRepository(db)
    repo.save(workflow)
    db.commit()
    return workflow


@pytest.mark.anyio
async def test_workflow_agent_matches_rest_stream_events_and_status(
    client: TestClient, test_engine
):
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        workflow = _create_simple_workflow(db)
    finally:
        db.close()

    # Arrange - REST run (REST contract requires run_id)
    run_resp = client.post(f"/api/projects/proj_1/workflows/{workflow.id}/runs", json={})
    assert run_resp.status_code == 200
    run_id_rest = run_resp.json()["id"]

    # REST execute/stream (SSE)
    resp = client.post(
        f"/api/workflows/{workflow.id}/execute/stream",
        json={"initial_input": {"message": "test"}, "run_id": run_id_rest},
    )
    assert resp.status_code == 200
    sse_events = []
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            sse_events.append(json.loads(line[6:]))
    assert sse_events

    # Gate sanity: completed run cannot be re-executed by WorkflowAgent.
    db2 = TestingSessionLocal()
    try:
        entry = app.state.container.workflow_run_execution_entry(db2)
        agent = WorkflowAgent(workflow_run_execution_entry=entry)
        rejected = await agent.handle_decision(
            {
                "decision_type": "execute_workflow",
                "workflow_id": workflow.id,
                "run_id": run_id_rest,
                "initial_input": {"message": "test"},
            }
        )
    finally:
        db2.close()

    assert rejected["success"] is False

    # Agent run (fresh run_id) - events/status must match REST semantics.
    run_resp_2 = client.post(f"/api/projects/proj_1/workflows/{workflow.id}/runs", json={})
    assert run_resp_2.status_code == 200
    run_id_agent = run_resp_2.json()["id"]

    db3 = TestingSessionLocal()
    try:
        entry = app.state.container.workflow_run_execution_entry(db3)
        agent = WorkflowAgent(workflow_run_execution_entry=entry)
        result = await agent.handle_decision(
            {
                "decision_type": "execute_workflow",
                "workflow_id": workflow.id,
                "run_id": run_id_agent,
                "initial_input": {"message": "test"},
            }
        )
    finally:
        db3.close()

    assert result["workflow_id"] == workflow.id
    assert result["run_id"] == run_id_agent
    assert [e["type"] for e in result["events"]] == [e["type"] for e in sse_events]

    # Success判定：终态事件 + RunStatus（REST: Run.status; Agent: derived status value）
    run_get_agent = client.get(f"/api/runs/{run_id_agent}")
    assert run_get_agent.status_code == 200
    assert run_get_agent.json()["status"] == result["status"]

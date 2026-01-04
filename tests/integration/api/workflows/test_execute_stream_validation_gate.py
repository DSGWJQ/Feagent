from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.coordinator_policy_chain import CoordinatorRejectedError
from src.config import settings
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.run import Run
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.event_bus import EventBus
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
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


class _AllowCoordinator:
    def validate_decision(self, decision: dict):
        return type("Validation", (), {"is_valid": True, "errors": []})()


class _DenyCoordinator:
    def validate_decision(self, decision: dict):
        return type("Validation", (), {"is_valid": False, "errors": ["denied"]})()


class _FakeWorkflowRepository:
    def __init__(self, workflow: Workflow) -> None:
        self._workflow = workflow

    def get_by_id(self, workflow_id: str) -> Workflow:
        return self._workflow


class _FakeToolRepository:
    def exists(self, tool_id: str) -> bool:
        return False

    def find_by_id(self, tool_id: str):
        return None


class _DummyExecutor:
    async def execute(self, node, inputs, context):  # pragma: no cover - not invoked by validator
        return None


class _UnreachableKernel:
    async def gate_execute(
        self,
        *,
        workflow_id: str,
        input_data=None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        after_gate=None,
    ) -> None:  # pragma: no cover
        raise CoordinatorRejectedError(
            decision_type="execute_workflow",
            correlation_id=correlation_id or "",
            original_decision_id=original_decision_id or "",
            errors=["denied"],
        )

    async def execute(self, *, workflow_id: str, input_data=None):  # pragma: no cover
        raise AssertionError("kernel must not be reached when gated")

    async def execute_streaming(self, *, workflow_id: str, input_data=None):  # pragma: no cover
        raise AssertionError("kernel must not be reached when gated")
        if False:  # pragma: no cover
            yield {}


def _seed_run(test_engine, *, workflow_id: str) -> Run:
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db: Session = TestingSessionLocal()
    try:
        run = Run.create(project_id="proj_1", workflow_id=workflow_id)
        SQLAlchemyRunRepository(db).save(run)
        db.commit()
        return run
    finally:
        db.close()


def _build_app(
    *,
    test_engine,
    container: ApiContainer,
    coordinator: object,
) -> TestClient:
    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.state.container = container
    app.state.coordinator = coordinator
    app.state.event_bus = EventBus()
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.include_router(workflows_routes.router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize(
    ("workflow_factory", "tool_repo_factory"),
    [
        (
            # missing executor
            lambda registry: (
                lambda start, llm: Workflow.create(
                    name="invalid",
                    description="",
                    nodes=[start, llm],
                    edges=[Edge.create(source_node_id=start.id, target_node_id=llm.id)],
                )
            )(
                Node.create(
                    type=NodeType.START,
                    name="start",
                    config={},
                    position=Position(x=0, y=0),
                ),
                Node.create(
                    type=NodeType.LLM,
                    name="llm",
                    config={},
                    position=Position(x=1, y=0),
                ),
            ),
            lambda: None,
        ),
        (
            # cycle detected
            lambda registry: (
                lambda start, end: Workflow.create(
                    name="cycle",
                    description="",
                    nodes=[start, end],
                    edges=[
                        Edge.create(source_node_id=start.id, target_node_id=end.id),
                        Edge.create(source_node_id=end.id, target_node_id=start.id),
                    ],
                )
            )(
                Node.create(
                    type=NodeType.START,
                    name="start",
                    config={},
                    position=Position(x=0, y=0),
                ),
                Node.create(
                    type=NodeType.END,
                    name="end",
                    config={},
                    position=Position(x=1, y=0),
                ),
            ),
            lambda: None,
        ),
        (
            # tool missing (executor exists but tool repo reports not found)
            lambda registry: Workflow.create(
                name="tool",
                description="",
                nodes=[
                    Node.create(
                        type=NodeType.TOOL,
                        name="tool",
                        config={"tool_id": "missing_tool"},
                        position=Position(x=0, y=0),
                    ),
                ],
                edges=[],
            ),
            lambda: _FakeToolRepository(),
        ),
    ],
)
def test_execute_stream_validation_blocks_before_persisting_workflow_start(
    monkeypatch: pytest.MonkeyPatch,
    test_engine,
    workflow_factory,
    tool_repo_factory,
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)
    monkeypatch.setattr(settings, "enable_langgraph_workflow_executor", False)

    run = _seed_run(test_engine, workflow_id="wf_invalid")

    registry = NodeExecutorRegistry()
    registry.register(NodeType.TOOL.value, _DummyExecutor())

    workflow = workflow_factory(registry)
    workflow.id = "wf_invalid"

    def _noop_repo(_: Session):
        return None

    client = _build_app(
        test_engine=test_engine,
        coordinator=_AllowCoordinator(),
        container=ApiContainer(
            executor_registry=registry,
            workflow_execution_kernel=lambda _s: _UnreachableKernel(),  # should not reach kernel
            conversation_turn_orchestrator=lambda: None,  # type: ignore[return-value]
            user_repository=_noop_repo,
            agent_repository=_noop_repo,
            task_repository=_noop_repo,
            workflow_repository=lambda _s: _FakeWorkflowRepository(workflow),
            chat_message_repository=_noop_repo,
            llm_provider_repository=_noop_repo,
            tool_repository=lambda _s: tool_repo_factory(),
            run_repository=_noop_repo,
            scheduled_workflow_repository=_noop_repo,
        ),
    )

    response = client.post(
        "/api/workflows/wf_invalid/execute/stream",
        json={"initial_input": {"k": "v"}, "run_id": run.id},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 400

    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        rows = db.execute(select(RunEventModel.type).where(RunEventModel.run_id == run.id)).all()
        assert rows == []
    finally:
        db.close()


def test_execute_stream_coordinator_rejection_blocks_before_persisting_workflow_start(
    monkeypatch: pytest.MonkeyPatch, test_engine
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)
    monkeypatch.setattr(settings, "enable_langgraph_workflow_executor", False)

    run = _seed_run(test_engine, workflow_id="wf_123")

    registry = NodeExecutorRegistry()
    workflow = Workflow.create(
        name="ok",
        description="",
        nodes=[
            Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0)),
            Node.create(type=NodeType.END, name="end", config={}, position=Position(x=1, y=0)),
        ],
        edges=[],
    )
    workflow.id = "wf_123"

    def _noop_repo(_: Session):
        return None

    client = _build_app(
        test_engine=test_engine,
        coordinator=_DenyCoordinator(),
        container=ApiContainer(
            executor_registry=registry,
            workflow_execution_kernel=lambda _s: _UnreachableKernel(),  # should not reach kernel
            conversation_turn_orchestrator=lambda: None,  # type: ignore[return-value]
            user_repository=_noop_repo,
            agent_repository=_noop_repo,
            task_repository=_noop_repo,
            workflow_repository=lambda _s: _FakeWorkflowRepository(workflow),
            chat_message_repository=_noop_repo,
            llm_provider_repository=_noop_repo,
            tool_repository=lambda _s: None,
            run_repository=_noop_repo,
            scheduled_workflow_repository=_noop_repo,
        ),
    )

    response = client.post(
        "/api/workflows/wf_123/execute/stream",
        json={"initial_input": {"k": "v"}, "run_id": run.id},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 403

    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        rows = db.execute(select(RunEventModel.type).where(RunEventModel.run_id == run.id)).all()
        assert rows == []
    finally:
        db.close()

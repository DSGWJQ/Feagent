"""Phase 5 E2E-ish parity tests: editor execute/stream vs validated decision execution.

Goal (docs/planning/workflow-reflection-acceptance-unification-plan.md):
- Different entry points produce the same acceptance lifecycle event sequence
  (workflow_execution_completed -> workflow_reflection_*), with Runs as the execution SoT.

Notes:
- Keep deterministic by using an in-memory DB and a fake execution facade.
- We persist a minimal WorkflowModel so AcceptanceLoopOrchestrator can fetch description
  via SQLAlchemyWorkflowRepository (it is the production dependency).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.acceptance_loop_orchestrator import AcceptanceLoopOrchestrator
from src.application.services.workflow_execution_orchestrator import WorkflowExecutionOrchestrator
from src.config import settings
from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.run import Run
from src.domain.entities.workflow import Workflow
from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
from src.domain.services.event_bus import EventBus
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.models import ProjectModel, RunEventModel, WorkflowModel
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


def _seed_project_and_workflow(
    db: Session,
    *,
    project_id: str,
    workflow_id: str,
    description: str = "a deterministic goal",
) -> None:
    if db.get(ProjectModel, project_id) is None:
        db.add(
            ProjectModel(
                id=project_id,
                name="entry-parity-project",
                description="",
                rules_text="",
                status="active",
            )
        )

    if db.get(WorkflowModel, workflow_id) is None:
        db.add(
            WorkflowModel(
                id=workflow_id,
                project_id=project_id,
                name="entry-parity-workflow",
                description=description,
                status="draft",
                source="test",
            )
        )

    db.commit()


def _build_domain_workflow(workflow_id: str) -> Workflow:
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=1, y=0))
    wf = Workflow.create(
        name="test",
        description="",
        nodes=[start, end],
        edges=[Edge.create(source_node_id=start.id, target_node_id=end.id)],
    )
    wf.id = workflow_id
    return wf


def _acceptance_event_types(db: Session, *, run_id: str) -> list[str]:
    want = {
        "workflow_test_report",
        "workflow_execution_completed",
        "workflow_reflection_requested",
        "workflow_reflection_completed",
        "workflow_adjustment_requested",
    }
    rows = (
        db.execute(
            select(RunEventModel)
            .where(RunEventModel.run_id == run_id, RunEventModel.channel == "lifecycle")
            .order_by(RunEventModel.id.asc())
        )
        .scalars()
        .all()
    )
    return [str(r.type) for r in rows if str(r.type) in want]


def _build_test_app(*, test_engine, workflow: Workflow, event_bus: EventBus) -> FastAPI:
    TestingSessionLocal = sessionmaker(bind=test_engine)

    def override_get_db_session():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    class FakeFacade:
        async def execute_streaming(self, *, workflow_id: str, input_data=None):
            yield {"type": "node_start", "metadata": {"workflow_id": workflow_id}}
            yield {"type": "workflow_complete", "metadata": {"workflow_id": workflow_id}}

    def orchestrator_factory(_: Session) -> WorkflowExecutionOrchestrator:
        return WorkflowExecutionOrchestrator(facade=FakeFacade())

    class _WorkflowRepo:
        def get_by_id(self, workflow_id: str):
            assert workflow_id == workflow.id
            return workflow

    def workflow_run_execution_entry_factory(session: Session):
        from src.application.services.workflow_run_execution_entry import WorkflowRunExecutionEntry
        from src.application.use_cases.append_run_event import AppendRunEventUseCase
        from src.application.use_cases.execute_workflow import WORKFLOW_EXECUTION_KERNEL_ID

        run_repo = SQLAlchemyRunRepository(session)
        return WorkflowRunExecutionEntry(
            workflow_repository=_WorkflowRepo(),
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

    def _noop_repo(_: Session):
        return None

    app = FastAPI()
    app.state.event_bus = event_bus

    class _AllowCoordinator:
        def validate_decision(self, decision: dict):
            return type("Validation", (), {"is_valid": True, "errors": []})()

    app.state.coordinator = _AllowCoordinator()
    app.state.container = ApiContainer(
        executor_registry=MagicMock(),
        workflow_execution_kernel=orchestrator_factory,
        workflow_run_execution_entry=workflow_run_execution_entry_factory,
        conversation_turn_orchestrator=lambda: None,  # type: ignore[return-value]
        user_repository=_noop_repo,
        agent_repository=_noop_repo,
        task_repository=_noop_repo,
        workflow_repository=lambda _s: _WorkflowRepo(),
        chat_message_repository=_noop_repo,
        llm_provider_repository=_noop_repo,
        tool_repository=_noop_repo,
        run_repository=lambda s: SQLAlchemyRunRepository(s),
        scheduled_workflow_repository=_noop_repo,
    )
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.include_router(workflows_routes.router, prefix="/api")
    return app


def test_editor_execute_stream_and_validated_decision_have_same_acceptance_sequence(
    monkeypatch: pytest.MonkeyPatch,
    test_engine,
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)

    project_id = "proj_entry_parity"
    workflow_id = "wf_entry_parity"

    SessionLocal = sessionmaker(bind=test_engine)
    with SessionLocal() as db:
        _seed_project_and_workflow(db, project_id=project_id, workflow_id=workflow_id)

    workflow = _build_domain_workflow(workflow_id)
    bus = EventBus()
    app = _build_test_app(test_engine=test_engine, workflow=workflow, event_bus=bus)

    # --- Entry A: editor execute/stream ---
    with SessionLocal() as db:
        run_a = Run.create(project_id=project_id, workflow_id=workflow_id)
        SQLAlchemyRunRepository(db).save(run_a)
        db.commit()
        run_a_id = run_a.id

    with TestClient(app) as client:
        resp = client.post(
            f"/api/workflows/{workflow_id}/execute/stream",
            json={"initial_input": {"k": "v"}, "run_id": run_a_id},
            headers={"Accept": "text/event-stream"},
        )
    assert resp.status_code == 200
    # Sanity: stream includes terminal.
    sse_events = [
        json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")
    ]
    assert sse_events[-1]["type"] == "workflow_complete"

    with SessionLocal() as db:
        a_types = _acceptance_event_types(db, run_id=run_a_id)

    # --- Entry B: validated decision (bridge-style) ---
    with SessionLocal() as db:
        run_b = Run.create(project_id=project_id, workflow_id=workflow_id)
        SQLAlchemyRunRepository(db).save(run_b)
        db.commit()
        run_b_id = run_b.id

    async def _workflow_decision_handler(decision: dict) -> dict:
        # Mimic src/interfaces/api/main.py handler: run entry execute -> acceptance loop.
        with SessionLocal() as db:
            entry = app.state.container.workflow_run_execution_entry(db)
            agent = WorkflowAgent(event_bus=bus, workflow_run_execution_entry=entry)
            result = await agent.handle_decision(decision)
            await AcceptanceLoopOrchestrator(db=db, event_bus=bus).on_run_terminal(
                workflow_id=workflow_id,
                run_id=run_b_id,
                session_id=run_b_id,
                attempt=1,
                max_replan_attempts=3,
            )
            return result

    bridge = DecisionExecutionBridge(
        event_bus=bus,
        workflow_decision_handler=_workflow_decision_handler,
        actionable_decision_types={DecisionType.EXECUTE_WORKFLOW.value},
    )

    import anyio

    async def _run_bridge_flow() -> None:
        await bridge.start()
        await bus.publish(
            DecisionMadeEvent(
                source="test",
                correlation_id=run_b_id,
                decision_type=DecisionType.EXECUTE_WORKFLOW.value,
                decision_id="dec_parity_1",
                payload={
                    "workflow_id": workflow_id,
                    "run_id": run_b_id,
                    "initial_input": {"k": "v"},
                },
            )
        )
        await bridge.stop()

    anyio.run(_run_bridge_flow)

    with SessionLocal() as db:
        b_types = _acceptance_event_types(db, run_id=run_b_id)

    assert a_types == [
        "workflow_test_report",
        "workflow_execution_completed",
        "workflow_reflection_requested",
        "workflow_reflection_completed",
    ]
    assert b_types == a_types

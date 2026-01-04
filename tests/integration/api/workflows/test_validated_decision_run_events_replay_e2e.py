"""Integration tests (WFCL-080): validated decision -> RunEvents -> replay consistency.

Goal:
- allow decision triggers execution and persists execution-channel RunEvents
- deny decision does not execute (no DB side effects)
- bridge exception is fail-closed (no DB side effects)
- duplicate delivery does not duplicate RunEvents

Notes:
- Use an in-memory DB and a fake execution facade to keep tests deterministic and CI-friendly.
- Model "validated decision" via EventBus middleware allow/deny (fail-closed gate).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.workflow_execution_orchestrator import WorkflowExecutionOrchestrator
from src.config import settings
from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.entities.run import Run
from src.domain.entities.workflow import Workflow
from src.domain.services.decision_execution_bridge import (
    DecisionExecutionBridge,
    ExecutionResultEvent,
)
from src.domain.services.event_bus import Event, EventBus
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.models import RunEventModel
from src.infrastructure.database.repositories.run_event_repository import (
    SQLAlchemyRunEventRepository,
)
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
from src.infrastructure.database.transaction_manager import SQLAlchemyTransactionManager
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.routes import runs as runs_routes


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


def _create_workflow_in_memory(workflow_id: str) -> Workflow:
    from src.domain.entities.node import Node
    from src.domain.value_objects.node_type import NodeType
    from src.domain.value_objects.position import Position

    workflow = Workflow.create(
        name="test",
        description="",
        nodes=[
            Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0)),
            Node.create(type=NodeType.END, name="end", config={}, position=Position(x=1, y=0)),
        ],
        edges=[],
    )
    workflow.id = workflow_id
    return workflow


def _seed_created_run(db: Session, *, workflow_id: str) -> str:
    run = Run.create(project_id="proj_1", workflow_id=workflow_id)
    SQLAlchemyRunRepository(db).save(run)
    db.commit()
    return run.id


def _build_test_app(
    *,
    test_engine,
    workflow: Workflow,
    event_bus: EventBus,
) -> FastAPI:
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
            save_validator=MagicMock(validate_or_raise=lambda _w: None),
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
    app.include_router(runs_routes.router, prefix="/api")
    return app


def _count_execution_events(db: Session, *, run_id: str) -> int:
    return db.execute(
        select(func.count(RunEventModel.id)).where(
            RunEventModel.run_id == run_id,
            RunEventModel.channel == "execution",
        )
    ).scalar_one()


async def _allow_middleware(event: Event) -> Event | None:
    return event


async def _deny_execute_workflow_middleware(event: Event) -> Event | None:
    if (
        isinstance(event, DecisionMadeEvent)
        and event.decision_type == DecisionType.EXECUTE_WORKFLOW.value
    ):
        return None
    return event


@pytest.mark.asyncio
async def test_allow_decision_persists_events_and_replay_matches(
    monkeypatch: pytest.MonkeyPatch, test_engine
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)

    event_bus = EventBus()
    event_bus.add_middleware(_allow_middleware)

    workflow = _create_workflow_in_memory("wf_1")
    SessionLocal = sessionmaker(bind=test_engine)
    with SessionLocal() as db:
        run_id = _seed_created_run(db, workflow_id=workflow.id)

    app = _build_test_app(test_engine=test_engine, workflow=workflow, event_bus=event_bus)

    results: list[ExecutionResultEvent] = []

    async def _collect_result(event: ExecutionResultEvent) -> None:
        results.append(event)

    event_bus.subscribe(ExecutionResultEvent, _collect_result)

    async def _workflow_decision_handler(decision: dict) -> dict:
        with SessionLocal() as db:
            entry = app.state.container.workflow_run_execution_entry(db)
            agent = WorkflowAgent(event_bus=event_bus, workflow_run_execution_entry=entry)
            return await agent.handle_decision(decision)

    bridge = DecisionExecutionBridge(
        event_bus=event_bus,
        workflow_decision_handler=_workflow_decision_handler,
        actionable_decision_types={DecisionType.EXECUTE_WORKFLOW.value},
    )
    await bridge.start()

    await event_bus.publish(
        DecisionMadeEvent(
            source="test",
            correlation_id=run_id,
            decision_type=DecisionType.EXECUTE_WORKFLOW.value,
            decision_id="dec_1",
            payload={"workflow_id": workflow.id, "run_id": run_id, "initial_input": {"k": "v"}},
        )
    )

    assert len(results) == 1
    assert results[0].correlation_id == run_id
    assert results[0].run_id == run_id
    sse_events = results[0].result.get("events", [])
    assert [e.get("type") for e in sse_events] == ["node_start", "workflow_complete"]
    assert all(e.get("run_id") == run_id for e in sse_events)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/runs/{run_id}/events?channel=execution")
    assert resp.status_code == 200
    replay = resp.json()
    replay_types = [e["type"] for e in replay["events"]]
    assert replay_types == ["node_start", "workflow_complete"]
    assert replay["events"][-1]["type"] == "workflow_complete"

    await bridge.stop()


@pytest.mark.asyncio
async def test_deny_decision_has_zero_db_side_effects(
    monkeypatch: pytest.MonkeyPatch, test_engine
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)

    event_bus = EventBus()
    event_bus.add_middleware(_deny_execute_workflow_middleware)

    workflow = _create_workflow_in_memory("wf_1")
    SessionLocal = sessionmaker(bind=test_engine)
    with SessionLocal() as db:
        run_id = _seed_created_run(db, workflow_id=workflow.id)

    results: list[ExecutionResultEvent] = []

    async def _collect_result(event: ExecutionResultEvent) -> None:
        results.append(event)

    event_bus.subscribe(ExecutionResultEvent, _collect_result)

    async def _workflow_decision_handler(_decision: dict) -> dict:
        raise AssertionError("handler should not be called when gate denies")

    bridge = DecisionExecutionBridge(
        event_bus=event_bus,
        workflow_decision_handler=_workflow_decision_handler,
        actionable_decision_types={DecisionType.EXECUTE_WORKFLOW.value},
    )
    await bridge.start()

    await event_bus.publish(
        DecisionMadeEvent(
            source="test",
            correlation_id=run_id,
            decision_type=DecisionType.EXECUTE_WORKFLOW.value,
            decision_id="dec_1",
            payload={"workflow_id": workflow.id, "run_id": run_id},
        )
    )

    assert results == []
    with SessionLocal() as db:
        assert _count_execution_events(db, run_id=run_id) == 0

    await bridge.stop()


@pytest.mark.asyncio
async def test_bridge_exception_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch, test_engine
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)

    event_bus = EventBus()
    event_bus.add_middleware(_allow_middleware)

    workflow = _create_workflow_in_memory("wf_1")
    SessionLocal = sessionmaker(bind=test_engine)
    with SessionLocal() as db:
        run_id = _seed_created_run(db, workflow_id=workflow.id)

    results: list[ExecutionResultEvent] = []

    async def _collect_result(event: ExecutionResultEvent) -> None:
        results.append(event)

    event_bus.subscribe(ExecutionResultEvent, _collect_result)

    async def _workflow_decision_handler(_decision: dict) -> dict:
        raise RuntimeError("boom")

    bridge = DecisionExecutionBridge(
        event_bus=event_bus,
        workflow_decision_handler=_workflow_decision_handler,
        actionable_decision_types={DecisionType.EXECUTE_WORKFLOW.value},
    )
    await bridge.start()

    await event_bus.publish(
        DecisionMadeEvent(
            source="test",
            correlation_id=run_id,
            decision_type=DecisionType.EXECUTE_WORKFLOW.value,
            decision_id="dec_1",
            payload={"workflow_id": workflow.id, "run_id": run_id},
        )
    )

    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].correlation_id == run_id
    assert results[0].run_id == run_id
    with SessionLocal() as db:
        assert _count_execution_events(db, run_id=run_id) == 0

    await bridge.stop()


@pytest.mark.asyncio
async def test_duplicate_delivery_does_not_duplicate_run_events(
    monkeypatch: pytest.MonkeyPatch, test_engine
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)

    event_bus = EventBus()
    event_bus.add_middleware(_allow_middleware)

    workflow = _create_workflow_in_memory("wf_1")
    SessionLocal = sessionmaker(bind=test_engine)
    with SessionLocal() as db:
        run_id = _seed_created_run(db, workflow_id=workflow.id)

    app = _build_test_app(test_engine=test_engine, workflow=workflow, event_bus=event_bus)

    async def _workflow_decision_handler(decision: dict) -> dict:
        with SessionLocal() as db:
            entry = app.state.container.workflow_run_execution_entry(db)
            agent = WorkflowAgent(event_bus=event_bus, workflow_run_execution_entry=entry)
            return await agent.handle_decision(decision)

    bridge = DecisionExecutionBridge(
        event_bus=event_bus,
        workflow_decision_handler=_workflow_decision_handler,
        actionable_decision_types={DecisionType.EXECUTE_WORKFLOW.value},
    )
    await bridge.start()

    decision_event = DecisionMadeEvent(
        source="test",
        correlation_id=run_id,
        decision_type=DecisionType.EXECUTE_WORKFLOW.value,
        decision_id="dec_1",
        payload={"workflow_id": workflow.id, "run_id": run_id},
    )

    # First delivery executes.
    await event_bus.publish(decision_event)
    # Duplicate delivery should not append any more execution-channel RunEvents.
    await event_bus.publish(decision_event)

    with SessionLocal() as db:
        stmt = (
            select(RunEventModel.type)
            .where(RunEventModel.run_id == run_id, RunEventModel.channel == "execution")
            .order_by(RunEventModel.id.asc())
        )
        event_types = [r[0] for r in db.execute(stmt).all()]
    assert event_types == ["node_start", "workflow_complete"]

    await bridge.stop()

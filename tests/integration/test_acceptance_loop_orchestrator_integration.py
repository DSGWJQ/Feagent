from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.application.services.acceptance_loop_orchestrator import AcceptanceLoopOrchestrator
from src.domain.entities.run import Run
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_failure_orchestrator import WorkflowAdjustmentRequestedEvent
from src.infrastructure.database.engine import SessionLocal
from src.infrastructure.database.models import ProjectModel, RunEventModel, WorkflowModel
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository


@pytest.mark.asyncio
async def test_acceptance_loop_appends_events_and_publishes_replan_idempotently():
    session = SessionLocal()
    try:
        project_id = "proj_test_acceptance"
        workflow_id = "wf_test_acceptance"

        if session.get(ProjectModel, project_id) is None:
            session.add(
                ProjectModel(
                    id=project_id,
                    name="acceptance-test-project",
                    description="",
                    rules_text="",
                    status="active",
                )
            )

        if session.get(WorkflowModel, workflow_id) is None:
            session.add(
                WorkflowModel(
                    id=workflow_id,
                    name="acceptance-test-workflow",
                    description="a deterministic goal",
                    status="draft",
                    source="test",
                )
            )

        session.commit()

        run = Run.create(project_id=project_id, workflow_id=workflow_id)
        SQLAlchemyRunRepository(session).save(run)
        session.commit()

        # Seed a terminal failure event as the execution SoT.
        session.add(
            RunEventModel(
                run_id=run.id,
                type="workflow_error",
                channel="execution",
                payload={"workflow_id": workflow_id, "executor_id": "executor_test"},
            )
        )
        session.commit()

        bus = EventBus()
        published: list[WorkflowAdjustmentRequestedEvent] = []

        async def _on_adjust(event):
            published.append(event)

        bus.subscribe(WorkflowAdjustmentRequestedEvent, _on_adjust)

        orchestrator = AcceptanceLoopOrchestrator(db=session, event_bus=bus)
        result1 = await orchestrator.on_run_terminal(
            workflow_id=workflow_id,
            run_id=run.id,
            attempt=1,
            max_replan_attempts=3,
        )

        assert result1.verdict.value == "REPLAN"
        assert len(published) == 1
        assert published[0].workflow_id == workflow_id
        assert published[0].execution_context.get("run_id") == run.id

        # Idempotent: second call must not publish a second adjustment.
        result2 = await orchestrator.on_run_terminal(
            workflow_id=workflow_id,
            run_id=run.id,
            attempt=1,
            max_replan_attempts=3,
        )
        assert result2.verdict.value == "REPLAN"
        assert len(published) == 1

        lifecycle_types = [
            row.type
            for row in session.query(RunEventModel)
            .filter(RunEventModel.run_id == run.id, RunEventModel.channel == "lifecycle")
            .all()
        ]
        assert "workflow_execution_completed" in lifecycle_types
        assert "workflow_reflection_requested" in lifecycle_types
        assert "workflow_reflection_completed" in lifecycle_types
        assert "workflow_adjustment_requested" in lifecycle_types
        assert "workflow_test_report" in lifecycle_types
        # Idempotent: do not keep appending deterministic reports on re-entry.
        assert lifecycle_types.count("workflow_test_report") == 1
    finally:
        session.close()


def test_acceptance_loop_is_concurrency_safe_for_replan_publish_and_lifecycle_dedupe():
    """Red-team regression: concurrent orchestrators must not double-publish REPLAN."""

    # Use one session to bootstrap data and seed a terminal error event.
    session = SessionLocal()
    try:
        project_id = "proj_test_acceptance_concurrency"
        workflow_id = "wf_test_acceptance_concurrency"

        if session.get(ProjectModel, project_id) is None:
            session.add(
                ProjectModel(
                    id=project_id,
                    name="acceptance-test-project",
                    description="",
                    rules_text="",
                    status="active",
                )
            )

        if session.get(WorkflowModel, workflow_id) is None:
            session.add(
                WorkflowModel(
                    id=workflow_id,
                    name="acceptance-test-workflow",
                    description="a deterministic goal",
                    status="draft",
                    source="test",
                )
            )

        session.commit()

        run = Run.create(project_id=project_id, workflow_id=workflow_id)
        SQLAlchemyRunRepository(session).save(run)
        session.commit()

        # Seed a terminal failure event as the execution SoT.
        session.add(
            RunEventModel(
                run_id=run.id,
                type="workflow_error",
                channel="execution",
                payload={"workflow_id": workflow_id, "executor_id": "executor_test"},
            )
        )
        session.commit()
    finally:
        session.close()

    class _ThreadSafeBus:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self.published: list[WorkflowAdjustmentRequestedEvent] = []

        async def publish(self, event):  # noqa: ANN001 - test stub
            with self._lock:
                self.published.append(event)

    bus = _ThreadSafeBus()
    barrier = threading.Barrier(2)

    def _invoke() -> str:
        local = SessionLocal()
        try:
            orchestrator = AcceptanceLoopOrchestrator(db=local, event_bus=bus)  # type: ignore[arg-type]
            # Force both threads to race on the idempotency keys.
            barrier.wait(timeout=5)
            result = asyncio.run(
                orchestrator.on_run_terminal(
                    workflow_id=workflow_id,
                    run_id=run.id,
                    attempt=1,
                    max_replan_attempts=3,
                )
            )
            return result.verdict.value
        finally:
            local.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        verdicts = [f.result(timeout=30) for f in [pool.submit(_invoke), pool.submit(_invoke)]]

    assert verdicts == ["REPLAN", "REPLAN"]
    assert len(bus.published) == 1

    verify = SessionLocal()
    try:
        lifecycle_types = [
            row.type
            for row in verify.query(RunEventModel)
            .filter(RunEventModel.run_id == run.id, RunEventModel.channel == "lifecycle")
            .all()
        ]
        assert lifecycle_types.count("workflow_execution_completed") == 1
        assert lifecycle_types.count("workflow_reflection_requested") == 1
        assert lifecycle_types.count("workflow_reflection_completed") == 1
        assert lifecycle_types.count("workflow_adjustment_requested") == 1
        assert lifecycle_types.count("workflow_test_report") == 1
    finally:
        verify.close()


@pytest.mark.asyncio
async def test_acceptance_loop_is_noop_when_run_not_terminal():
    session = SessionLocal()
    try:
        project_id = "proj_test_acceptance_non_terminal"
        workflow_id = "wf_test_acceptance_non_terminal"

        if session.get(ProjectModel, project_id) is None:
            session.add(
                ProjectModel(
                    id=project_id,
                    name="acceptance-test-project",
                    description="",
                    rules_text="",
                    status="active",
                )
            )

        if session.get(WorkflowModel, workflow_id) is None:
            session.add(
                WorkflowModel(
                    id=workflow_id,
                    name="acceptance-test-workflow",
                    description="a deterministic goal",
                    status="draft",
                    source="test",
                )
            )

        session.commit()

        run = Run.create(project_id=project_id, workflow_id=workflow_id)
        SQLAlchemyRunRepository(session).save(run)
        session.commit()

        bus = EventBus()
        published: list[WorkflowAdjustmentRequestedEvent] = []

        async def _on_adjust(event):
            published.append(event)

        bus.subscribe(WorkflowAdjustmentRequestedEvent, _on_adjust)

        orchestrator = AcceptanceLoopOrchestrator(db=session, event_bus=bus)
        result = await orchestrator.on_run_terminal(
            workflow_id=workflow_id,
            run_id=run.id,
            attempt=1,
            max_replan_attempts=3,
        )

        assert result.verdict.value == "BLOCKED"
        assert result.blocked_reason == "run_not_terminal"
        assert published == []
        lifecycle_rows = (
            session.query(RunEventModel)
            .filter(RunEventModel.run_id == run.id, RunEventModel.channel == "lifecycle")
            .all()
        )
        assert lifecycle_rows == []
    finally:
        session.close()

"""Phase 6 release gate: REPLAN -> new run -> must confirm again (no confirm reuse).

We model:
1) A workflow that requires confirmation (side-effect node).
2) Run #1: user denies confirmation -> terminal workflow_error -> acceptance verdict REPLAN.
3) Run #2: user allows confirmation -> terminal workflow_complete -> acceptance verdict PASS.

Hard assertions:
- confirm_id differs across runs (confirm not reused after REPLAN).
- acceptance loop publishes WorkflowAdjustmentRequestedEvent exactly once for the failing run.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.acceptance_loop_orchestrator import AcceptanceLoopOrchestrator
from src.application.services.run_confirmation_store import run_confirmation_store
from src.application.services.workflow_execution_orchestrator import WorkflowExecutionOrchestrator
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.run import Run
from src.domain.entities.workflow import Workflow
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_failure_orchestrator import WorkflowAdjustmentRequestedEvent
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import ProjectModel, RunEventModel, WorkflowModel
from src.infrastructure.database.repositories.run_event_repository import (
    SQLAlchemyRunEventRepository,
)
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
from src.infrastructure.database.transaction_manager import SQLAlchemyTransactionManager


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


def _seed_project_and_workflow(db: Session, *, project_id: str, workflow_id: str) -> None:
    if db.get(ProjectModel, project_id) is None:
        db.add(
            ProjectModel(
                id=project_id,
                name="replan-confirm-project",
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
                name="replan-confirm-workflow",
                description="requires confirmation",
                status="draft",
                source="test",
            )
        )
    db.commit()


def _build_side_effect_workflow(workflow_id: str) -> Workflow:
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    tool = Node.create(type=NodeType.TOOL, name="tool", config={}, position=Position(x=1, y=0))
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=2, y=0))
    wf = Workflow.create(
        name="side-effect",
        description="",
        nodes=[start, tool, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=tool.id),
            Edge.create(source_node_id=tool.id, target_node_id=end.id),
        ],
    )
    wf.id = workflow_id
    return wf


@pytest.mark.asyncio
async def test_replan_requires_new_confirm_id_in_next_run(test_engine) -> None:
    project_id = "proj_replan_confirm"
    workflow_id = "wf_replan_confirm"

    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        _seed_project_and_workflow(db, project_id=project_id, workflow_id=workflow_id)

        # Build an execution entry whose workflow contains a side-effect node (TOOL).
        workflow = _build_side_effect_workflow(workflow_id)

        class _WorkflowRepo:
            def get_by_id(self, wid: str):
                assert wid == workflow.id
                return workflow

        class FakeFacade:
            async def execute_streaming(self, *, workflow_id: str, input_data=None):
                # Not reached when confirmation is denied; reached when allow.
                yield {"type": "node_start", "metadata": {"workflow_id": workflow_id}}
                yield {"type": "workflow_complete", "metadata": {"workflow_id": workflow_id}}

        def kernel_factory() -> WorkflowExecutionOrchestrator:
            return WorkflowExecutionOrchestrator(facade=FakeFacade())

        from src.application.services.workflow_run_execution_entry import WorkflowRunExecutionEntry
        from src.application.use_cases.append_run_event import AppendRunEventUseCase
        from src.application.use_cases.execute_workflow import WORKFLOW_EXECUTION_KERNEL_ID

        run_repo = SQLAlchemyRunRepository(db)
        entry = WorkflowRunExecutionEntry(
            workflow_repository=_WorkflowRepo(),
            run_repository=run_repo,
            save_validator=MagicMock(validate_for_execution_or_raise=lambda _w: None),
            run_event_use_case=AppendRunEventUseCase(
                run_repository=run_repo,
                run_event_repository=SQLAlchemyRunEventRepository(db),
                transaction_manager=SQLAlchemyTransactionManager(db),
            ),
            kernel=kernel_factory(),
            executor_id=WORKFLOW_EXECUTION_KERNEL_ID,
        )

        bus = EventBus()
        published: list[WorkflowAdjustmentRequestedEvent] = []

        async def _on_adjust(event: WorkflowAdjustmentRequestedEvent) -> None:
            published.append(event)

        bus.subscribe(WorkflowAdjustmentRequestedEvent, _on_adjust)

        # --- Run #1 (deny) ---
        run1 = Run.create(project_id=project_id, workflow_id=workflow_id)
        run_repo.save(run1)
        db.commit()

        confirm_id_1: str | None = None
        terminal_1: str | None = None

        await entry.prepare(workflow_id=workflow_id, run_id=run1.id, input_data=None)
        async for event in entry.stream_after_gate(
            workflow_id=workflow_id,
            run_id=run1.id,
            input_data=None,
            correlation_id=run1.id,
            original_decision_id=run1.id,
            record_execution_events=True,
        ):
            if event.get("type") == "workflow_confirm_required":
                confirm_id_1 = event.get("confirm_id")
                assert isinstance(confirm_id_1, str) and confirm_id_1
                await run_confirmation_store.resolve(
                    run_id=run1.id,
                    confirm_id=confirm_id_1,
                    decision="deny",
                )
            terminal_1 = event.get("type")

        assert terminal_1 == "workflow_error"

        result1 = await AcceptanceLoopOrchestrator(db=db, event_bus=bus).on_run_terminal(
            workflow_id=workflow_id,
            run_id=run1.id,
            attempt=1,
            max_replan_attempts=3,
        )
        assert result1.verdict.value == "REPLAN"
        assert len(published) == 1
        assert published[0].workflow_id == workflow_id
        assert published[0].execution_context.get("run_id") == run1.id

        # --- Run #2 (allow) ---
        run2 = Run.create(project_id=project_id, workflow_id=workflow_id)
        run_repo.save(run2)
        db.commit()

        confirm_id_2: str | None = None
        terminal_2: str | None = None

        await entry.prepare(workflow_id=workflow_id, run_id=run2.id, input_data=None)
        async for event in entry.stream_after_gate(
            workflow_id=workflow_id,
            run_id=run2.id,
            input_data=None,
            correlation_id=run2.id,
            original_decision_id=run2.id,
            record_execution_events=True,
        ):
            if event.get("type") == "workflow_confirm_required":
                confirm_id_2 = event.get("confirm_id")
                assert isinstance(confirm_id_2, str) and confirm_id_2
                await run_confirmation_store.resolve(
                    run_id=run2.id,
                    confirm_id=confirm_id_2,
                    decision="allow",
                )
            terminal_2 = event.get("type")

        assert terminal_2 == "workflow_complete"

        # Hard gate: confirm must not be reused across runs.
        assert confirm_id_1 is not None and confirm_id_2 is not None
        assert confirm_id_1 != confirm_id_2

        result2 = await AcceptanceLoopOrchestrator(db=db, event_bus=bus).on_run_terminal(
            workflow_id=workflow_id,
            run_id=run2.id,
            attempt=2,
            max_replan_attempts=3,
        )
        assert result2.verdict.value == "PASS"
        assert len(published) == 1  # no new adjustment on PASS

        # Sanity: reflection_completed is persisted and includes a test_report_ref.
        reflection_rows = (
            db.execute(
                select(RunEventModel)
                .where(
                    RunEventModel.run_id == run2.id,
                    RunEventModel.channel == "lifecycle",
                    RunEventModel.type == "workflow_reflection_completed",
                )
                .order_by(RunEventModel.id.asc())
            )
            .scalars()
            .all()
        )
        assert len(reflection_rows) == 1
        payload = reflection_rows[0].payload or {}
        assert payload.get("verdict") == "PASS"
        assert isinstance(payload.get("evidence_map"), dict)
        assert isinstance(payload.get("test_report_ref"), str) and payload["test_report_ref"]
    finally:
        db.close()

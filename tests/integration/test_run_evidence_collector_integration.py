from __future__ import annotations

from src.application.services.run_evidence_collector import RunEvidenceCollector
from src.domain.entities.run import Run
from src.infrastructure.database.engine import SessionLocal
from src.infrastructure.database.models import ProjectModel, RunEventModel, WorkflowModel
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository


def test_run_evidence_snapshot_is_idempotent_and_order_independent():
    session = SessionLocal()
    try:
        project_id = "proj_test_evidence"
        workflow_id = "wf_test_evidence"

        if session.get(ProjectModel, project_id) is None:
            session.add(
                ProjectModel(
                    id=project_id,
                    name="evidence-test-project",
                    description="",
                    rules_text="",
                    status="active",
                )
            )

        if session.get(WorkflowModel, workflow_id) is None:
            session.add(
                WorkflowModel(
                    id=workflow_id,
                    name="evidence-test-workflow",
                    description="",
                    status="draft",
                    source="test",
                )
            )

        session.commit()

        run = Run.create(project_id=project_id, workflow_id=workflow_id)
        SQLAlchemyRunRepository(session).save(run)
        session.commit()

        # Insert events without relying on query order; collector must sort deterministically.
        session.add(
            RunEventModel(
                run_id=run.id,
                type="workflow_start",
                channel="lifecycle",
                payload={"workflow_id": workflow_id, "executor_id": "executor_test"},
            )
        )
        session.add(
            RunEventModel(
                run_id=run.id,
                type="workflow_complete",
                channel="execution",
                payload={"workflow_id": workflow_id, "executor_id": "executor_test"},
            )
        )
        session.commit()

        collector = RunEvidenceCollector(db=session)
        snap1 = collector.collect(run_id=run.id)
        snap2 = collector.collect(run_id=run.id)

        assert snap1 == snap2
        assert snap1.run_id == run.id
        assert len(snap1.run_event_refs) == 2
        assert all(ref.startswith("run_event:") for ref in snap1.run_event_refs)

        summary = snap1.execution_summary
        assert summary["run_event_count"] == 2
        assert summary["terminal_event_type"] == "workflow_complete"
    finally:
        session.close()

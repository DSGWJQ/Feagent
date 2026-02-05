"""RunEvidenceCollector - build an idempotent evidence snapshot from Runs (Phase 2).

Evidence is derived from persisted RunEvents (and later artifacts/test reports).
This module intentionally does NOT rely on streaming order (SSE timing) to avoid
missing evidence in partial/aborted streams.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError
from src.infrastructure.database.models import RunEventModel
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository


def format_run_event_ref(*, run_id: str, channel: str, event_id: int) -> str:
    """Stable reference format for a persisted RunEvent.

    Note: we keep this as a compact string so it can be embedded in JSON payloads
    and future workflow_* lifecycle events.
    """

    return f"run_event:{run_id}:{channel}:{event_id}"


@dataclass(frozen=True, slots=True)
class RunEvidenceSnapshot:
    run_id: str
    run_event_refs: list[str]
    artifact_refs: list[str] = field(default_factory=list)
    test_report_ref: str | None = None
    execution_summary: dict[str, Any] = field(default_factory=dict)


class RunEvidenceCollector:
    """Collect evidence for a given run_id (Phase 2).

    Red-team notes:
    - Fail-closed: run must exist.
    - Idempotent: snapshot is deterministic for a fixed set of persisted events.
    - Order-independent: snapshot does not depend on DB row iteration order.
    """

    def __init__(self, *, db: Session) -> None:
        self._db = db

    def collect(self, *, run_id: str) -> RunEvidenceSnapshot:
        run_id = (run_id or "").strip()
        if not run_id:
            raise ValueError("run_id is required")

        # Fail-closed: ensure run exists (and avoid returning empty evidence silently).
        repo = SQLAlchemyRunRepository(self._db)
        try:
            repo.get_by_id(run_id)
        except NotFoundError:
            raise

        # Do NOT rely on DB ordering; sort in-memory to keep evidence deterministic.
        models = list(
            self._db.execute(select(RunEventModel).where(RunEventModel.run_id == run_id))
            .scalars()
            .all()
        )
        models.sort(key=lambda m: int(m.id))

        run_event_refs: list[str] = []
        type_counts: dict[str, int] = {}
        channel_counts: dict[str, int] = {}
        refs_by_type: dict[str, list[str]] = {}

        terminal_event_type: str | None = None
        confirm_required = False
        confirm_decision: str | None = None

        for m in models:
            ref = format_run_event_ref(run_id=run_id, channel=str(m.channel), event_id=int(m.id))
            run_event_refs.append(ref)

            etype = str(m.type)
            type_counts[etype] = type_counts.get(etype, 0) + 1
            refs_by_type.setdefault(etype, []).append(ref)

            channel = str(m.channel)
            channel_counts[channel] = channel_counts.get(channel, 0) + 1

            if etype in {"workflow_complete", "workflow_error"}:
                terminal_event_type = etype
            if etype == "workflow_confirm_required":
                confirm_required = True
            if etype == "workflow_confirmed":
                payload = m.payload or {}
                decision = payload.get("decision")
                if isinstance(decision, str) and decision.strip():
                    confirm_decision = decision.strip()

        summary: dict[str, Any] = {
            "run_event_count": len(models),
            "type_counts": dict(sorted(type_counts.items(), key=lambda kv: kv[0])),
            "event_refs_by_type": dict(sorted(refs_by_type.items(), key=lambda kv: kv[0])),
            "channel_counts": dict(sorted(channel_counts.items(), key=lambda kv: kv[0])),
            "terminal_event_type": terminal_event_type,
            "confirm_required": confirm_required,
            "confirm_decision": confirm_decision,
            "first_event_id": int(models[0].id) if models else None,
            "last_event_id": int(models[-1].id) if models else None,
        }

        # Artifacts/test reports are Phase 2/6 deliverables; keep placeholders here.
        return RunEvidenceSnapshot(
            run_id=run_id,
            run_event_refs=run_event_refs,
            artifact_refs=[],
            test_report_ref=None,
            execution_summary=summary,
        )


__all__ = ["RunEvidenceCollector", "RunEvidenceSnapshot", "format_run_event_ref"]

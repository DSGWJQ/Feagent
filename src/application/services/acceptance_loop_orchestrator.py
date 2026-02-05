"""Acceptance loop orchestrator (Phase 4).

This orchestrator connects:
Run terminal state -> Evidence snapshot -> Acceptance verdict -> (optional) REPLAN signal.

Persisted artifacts:
- workflow_execution_completed (lifecycle)
- workflow_test_report (lifecycle)  [minimal deterministic gate, Phase 6 will refine]
- workflow_reflection_requested (lifecycle)
- workflow_reflection_completed (lifecycle)
- workflow_adjustment_requested (lifecycle, only when verdict=REPLAN)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.services.acceptance_evaluator import (
    AcceptanceEvaluator,
    AcceptanceResult,
    AcceptanceVerdict,
)
from src.application.services.criteria_manager import CriteriaManager, CriteriaSnapshot
from src.application.services.run_evidence_collector import (
    RunEvidenceCollector,
    format_run_event_ref,
)
from src.application.use_cases.append_run_event import AppendRunEventInput, AppendRunEventUseCase
from src.domain.entities.run_event import RunEvent
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_failure_orchestrator import WorkflowAdjustmentRequestedEvent
from src.infrastructure.database.models import RunEventModel
from src.infrastructure.database.repositories.run_event_repository import (
    SQLAlchemyRunEventRepository,
)
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.database.transaction_manager import SQLAlchemyTransactionManager

logger = logging.getLogger(__name__)

_ACCEPTANCE_EXECUTOR_ID = "acceptance_loop_v1"
_REFLECTION_ID_VERSION = "v1"


def compute_reflection_id(*, run_id: str, criteria_hash: str) -> str:
    material = f"{run_id.strip()}|{criteria_hash.strip()}|{_REFLECTION_ID_VERSION}".encode()
    return hashlib.sha256(material).hexdigest()


class AcceptanceLoopOrchestrator:
    def __init__(
        self,
        *,
        db: Session,
        event_bus: EventBus | None,
        evaluator: AcceptanceEvaluator | None = None,
        criteria_manager: CriteriaManager | None = None,
        evidence_collector: RunEvidenceCollector | None = None,
    ) -> None:
        self._db = db
        self._event_bus = event_bus
        self._criteria_manager = criteria_manager or CriteriaManager()
        self._evidence_collector = evidence_collector or RunEvidenceCollector(db=db)
        self._evaluator = evaluator or AcceptanceEvaluator(require_test_report_for_pass=True)

        run_repo = SQLAlchemyRunRepository(db)
        run_event_repo = SQLAlchemyRunEventRepository(db)
        tx = SQLAlchemyTransactionManager(db)
        self._append_run_event = AppendRunEventUseCase(
            run_repository=run_repo,
            run_event_repository=run_event_repo,
            transaction_manager=tx,
        )

    async def on_run_terminal(
        self,
        *,
        workflow_id: str,
        run_id: str,
        session_id: str | None = None,
        attempt: int = 1,
        max_replan_attempts: int = 3,
        user_criteria: list[str] | None = None,
        plan_criteria: list[str] | None = None,
    ) -> AcceptanceResult:
        """Process a terminal run and close the acceptance loop (best-effort)."""

        run_id = (run_id or "").strip()
        workflow_id = (workflow_id or "").strip()
        if not run_id:
            raise ValueError("run_id is required")
        if not workflow_id:
            raise ValueError("workflow_id is required")

        effective_session_id = (session_id or "").strip() or run_id

        # Infer criteria from workflow description when missing.
        wf = SQLAlchemyWorkflowRepository(self._db).get_by_id(workflow_id)
        task_description = getattr(wf, "description", None)

        criteria_snapshot = self._criteria_manager.build_snapshot(
            task_description=task_description,
            user_criteria=user_criteria,
            plan_criteria=plan_criteria,
        )

        reflection_id = compute_reflection_id(
            run_id=run_id, criteria_hash=criteria_snapshot.criteria_hash
        )

        if self._already_reflected(run_id=run_id, reflection_id=reflection_id):
            # Idempotent: do not publish again; re-evaluate and return.
            evidence_snapshot = self._evidence_collector.collect(run_id=run_id)
            terminal_type = self._get_terminal_event_type(evidence_snapshot)
            if terminal_type not in {"workflow_complete", "workflow_error"}:
                return self._blocked_not_terminal(
                    attempt=attempt, max_replan_attempts=max_replan_attempts
                )

            tests_passed, test_report_ref = self._get_or_create_test_report(
                reflection_id=reflection_id,
                workflow_id=workflow_id,
                run_id=run_id,
                attempt=attempt,
                criteria_snapshot=criteria_snapshot,
                evidence_snapshot=evidence_snapshot,
            )
            return self._evaluator.evaluate(
                criteria_snapshot=criteria_snapshot,
                evidence_snapshot=evidence_snapshot,
                attempt=attempt,
                max_replan_attempts=max_replan_attempts,
                previous_unmet_criteria_ids=None,
                tests_passed=tests_passed,
                test_report_ref=test_report_ref,
            )

        # Evidence snapshot must be based on persisted RunEvents (critical events are synced).
        evidence_snapshot = self._evidence_collector.collect(run_id=run_id)
        terminal_type = self._get_terminal_event_type(evidence_snapshot)
        if terminal_type not in {"workflow_complete", "workflow_error"}:
            return self._blocked_not_terminal(
                attempt=attempt, max_replan_attempts=max_replan_attempts
            )

        run_entity = SQLAlchemyRunRepository(self._db).get_by_id(run_id)

        tests_passed, test_report_ref = self._get_or_create_test_report(
            reflection_id=reflection_id,
            workflow_id=workflow_id,
            run_id=run_id,
            attempt=attempt,
            criteria_snapshot=criteria_snapshot,
            evidence_snapshot=evidence_snapshot,
        )

        started_at = getattr(run_entity, "started_at", None)
        finished_at = getattr(run_entity, "finished_at", None)

        # 1) workflow_execution_completed
        if not self._already_execution_completed(run_id=run_id):
            self._append_lifecycle_event(
                run_id=run_id,
                event_type="workflow_execution_completed",
                idempotency_key="workflow_execution_completed",
                payload={
                    "session_id": effective_session_id,
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "attempt": attempt,
                    "status": getattr(getattr(run_entity, "status", None), "value", None)
                    or evidence_snapshot.execution_summary.get("terminal_event_type"),
                    "started_at": started_at.isoformat() if started_at is not None else None,
                    "ended_at": finished_at.isoformat() if finished_at is not None else None,
                    "executor_id": _ACCEPTANCE_EXECUTOR_ID,
                    "run_event_refs": list(evidence_snapshot.run_event_refs),
                    "artifact_refs": [],
                    "test_report_ref": test_report_ref,
                    "confirm_required": bool(
                        evidence_snapshot.execution_summary.get("confirm_required") is True
                    ),
                },
            )

        # 2) workflow_reflection_requested
        if not self._already_reflection_requested(run_id=run_id, reflection_id=reflection_id):
            self._append_lifecycle_event(
                run_id=run_id,
                event_type="workflow_reflection_requested",
                idempotency_key=f"workflow_reflection_requested:{reflection_id}",
                payload={
                    "reflection_id": reflection_id,
                    "run_id": run_id,
                    "session_id": effective_session_id,
                    "attempt": attempt,
                    "criteria_hash": criteria_snapshot.criteria_hash,
                    # Phase 4 event contract: keep a stable ref; we use criteria_hash as the minimal ref.
                    "criteria_snapshot_ref": criteria_snapshot.criteria_hash,
                    # Keep the snapshot inline for audit/replay (optional but useful).
                    "criteria_snapshot": self._serialize_criteria_snapshot(criteria_snapshot),
                    "executor_id": _ACCEPTANCE_EXECUTOR_ID,
                },
            )

        # 3) Evaluate acceptance (strict)
        result = self._evaluator.evaluate(
            criteria_snapshot=criteria_snapshot,
            evidence_snapshot=evidence_snapshot,
            attempt=attempt,
            max_replan_attempts=max_replan_attempts,
            previous_unmet_criteria_ids=None,
            tests_passed=tests_passed,
            test_report_ref=test_report_ref,
        )

        # 4) workflow_reflection_completed
        self._append_lifecycle_event(
            run_id=run_id,
            event_type="workflow_reflection_completed",
            idempotency_key=f"workflow_reflection_completed:{reflection_id}",
            payload={
                "reflection_id": reflection_id,
                "run_id": run_id,
                "session_id": effective_session_id,
                "attempt": attempt,
                "verdict": result.verdict.value,
                "executor_id": _ACCEPTANCE_EXECUTOR_ID,
                "unmet_criteria": list(result.unmet_criteria),
                "evidence_map": {k: list(v) for k, v in (result.evidence_map or {}).items()},
                "missing_evidence": list(result.missing_evidence),
                "user_questions": list(result.user_questions or []),
                "replan_constraints": list(result.replan_constraints or []),
                "test_report_ref": test_report_ref,
            },
        )

        # 5) REPLAN (publish domain event + persist lifecycle)
        if result.verdict.value == "REPLAN":
            await self._publish_adjustment_requested(
                workflow_id=workflow_id,
                run_id=run_id,
                reflection_id=reflection_id,
                next_attempt=attempt + 1,
                unmet_criteria=list(result.unmet_criteria),
                missing_evidence=list(result.missing_evidence),
                constraints=list(result.replan_constraints or []),
            )

        return result

    def _get_terminal_event_type(self, evidence_snapshot) -> str | None:
        summary = (
            evidence_snapshot.execution_summary
            if isinstance(evidence_snapshot.execution_summary, dict)
            else {}
        )
        terminal_raw = summary.get("terminal_event_type")
        if isinstance(terminal_raw, str) and terminal_raw.strip():
            return terminal_raw.strip()
        return None

    def _blocked_not_terminal(self, *, attempt: int, max_replan_attempts: int) -> AcceptanceResult:
        # Defensive: orchestrator might be triggered by stream cancellation/disconnect.
        # We MUST NOT publish REPLAN unless we have a terminal evidence.
        return AcceptanceResult(
            verdict=AcceptanceVerdict.BLOCKED,
            attempt=attempt,
            max_replan_attempts=max_replan_attempts,
            unmet_criteria=[],
            evidence_map={},
            missing_evidence=[],
            blocked_reason="run_not_terminal",
        )

    def _append_lifecycle_event(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> RunEvent:
        return self._append_run_event.execute(
            AppendRunEventInput(
                run_id=run_id,
                event_type=event_type,
                channel="lifecycle",
                payload=self._safe_json_payload(payload),
                idempotency_key=idempotency_key,
            )
        )

    def _already_execution_completed(self, *, run_id: str) -> bool:
        row = self._db.execute(
            select(RunEventModel)
            .where(
                RunEventModel.run_id == run_id,
                RunEventModel.channel == "lifecycle",
                RunEventModel.type == "workflow_execution_completed",
            )
            .order_by(RunEventModel.id.asc())
        ).scalar_one_or_none()
        return row is not None

    def _already_reflected(self, *, run_id: str, reflection_id: str) -> bool:
        rows = list(
            self._db.execute(
                select(RunEventModel)
                .where(
                    RunEventModel.run_id == run_id,
                    RunEventModel.channel == "lifecycle",
                    RunEventModel.type == "workflow_reflection_completed",
                )
                .order_by(RunEventModel.id.asc())
            )
            .scalars()
            .all()
        )
        for row in rows:
            payload = row.payload or {}
            if payload.get("reflection_id") == reflection_id:
                return True
        return False

    def _already_reflection_requested(self, *, run_id: str, reflection_id: str) -> bool:
        rows = list(
            self._db.execute(
                select(RunEventModel)
                .where(
                    RunEventModel.run_id == run_id,
                    RunEventModel.channel == "lifecycle",
                    RunEventModel.type == "workflow_reflection_requested",
                )
                .order_by(RunEventModel.id.asc())
            )
            .scalars()
            .all()
        )
        for row in rows:
            payload = row.payload or {}
            if payload.get("reflection_id") == reflection_id:
                return True
        return False

    def _already_adjustment_requested(self, *, run_id: str, reflection_id: str) -> bool:
        rows = list(
            self._db.execute(
                select(RunEventModel)
                .where(
                    RunEventModel.run_id == run_id,
                    RunEventModel.channel == "lifecycle",
                    RunEventModel.type == "workflow_adjustment_requested",
                )
                .order_by(RunEventModel.id.asc())
            )
            .scalars()
            .all()
        )
        for row in rows:
            payload = row.payload or {}
            if payload.get("from_reflection_id") == reflection_id:
                return True
        return False

    def _serialize_criteria_snapshot(self, snapshot: CriteriaSnapshot) -> dict[str, Any]:
        # Freeze as plain dict for persistence/replay.
        return {
            "criteria_hash": snapshot.criteria_hash,
            "criteria": [
                {
                    "id": c.id,
                    "text": c.text,
                    "source": c.source.value,
                    "verification_method": c.verification_method.value,
                    "meta": dict(c.meta or {}),
                }
                for c in snapshot.criteria
            ],
            "conflicts": [asdict(c) for c in snapshot.conflicts],
            "unverifiable_criteria_ids": list(snapshot.unverifiable_criteria_ids),
        }

    def _get_or_create_test_report(
        self,
        *,
        reflection_id: str,
        workflow_id: str,
        run_id: str,
        attempt: int,
        criteria_snapshot: CriteriaSnapshot,
        evidence_snapshot,
    ) -> tuple[bool, str]:
        """Return (passed, ref) for a deterministic test report (idempotent by reflection_id)."""

        existing = self._get_existing_test_report(run_id=run_id, reflection_id=reflection_id)
        if existing is not None:
            return existing

        summary = (
            evidence_snapshot.execution_summary
            if isinstance(evidence_snapshot.execution_summary, dict)
            else {}
        )
        terminal = summary.get("terminal_event_type")
        confirm_required = bool(summary.get("confirm_required") is True)
        confirm_decision = summary.get("confirm_decision")

        checks: list[dict[str, Any]] = []
        checks.append({"check": "terminal_event", "passed": terminal == "workflow_complete"})
        if confirm_required:
            checks.append({"check": "confirm_allow", "passed": confirm_decision == "allow"})

        passed = all(bool(c.get("passed") is True) for c in checks)
        payload = {
            "reflection_id": reflection_id,
            "workflow_id": workflow_id,
            "run_id": run_id,
            "attempt": attempt,
            "executor_id": _ACCEPTANCE_EXECUTOR_ID,
            "status": "passed" if passed else "failed",
            "checks": checks,
            "criteria_hash": criteria_snapshot.criteria_hash,
        }
        persisted = self._append_lifecycle_event(
            run_id=run_id,
            event_type="workflow_test_report",
            idempotency_key=f"workflow_test_report:{reflection_id}",
            payload=payload,
        )
        event_id = int(getattr(persisted, "id", 0) or 0)
        ref = format_run_event_ref(run_id=run_id, channel="lifecycle", event_id=event_id)
        return passed, ref

    def _get_existing_test_report(
        self, *, run_id: str, reflection_id: str
    ) -> tuple[bool, str] | None:
        rows = list(
            self._db.execute(
                select(RunEventModel)
                .where(
                    RunEventModel.run_id == run_id,
                    RunEventModel.channel == "lifecycle",
                    RunEventModel.type == "workflow_test_report",
                )
                .order_by(RunEventModel.id.asc())
            )
            .scalars()
            .all()
        )
        for row in rows:
            payload = row.payload or {}
            if payload.get("reflection_id") != reflection_id:
                continue
            status = payload.get("status")
            passed = status == "passed"
            ref = format_run_event_ref(run_id=run_id, channel="lifecycle", event_id=int(row.id))
            return passed, ref
        return None

    async def _publish_adjustment_requested(
        self,
        *,
        workflow_id: str,
        run_id: str,
        reflection_id: str,
        next_attempt: int,
        unmet_criteria: list[str],
        missing_evidence: list[str],
        constraints: list[str],
    ) -> None:
        # Persist lifecycle event for audit/replay (idempotent via idempotency_key).
        persisted = self._append_lifecycle_event(
            run_id=run_id,
            event_type="workflow_adjustment_requested",
            idempotency_key=f"workflow_adjustment_requested:{reflection_id}",
            payload={
                "from_reflection_id": reflection_id,
                "next_attempt": next_attempt,
                "unmet_criteria": list(unmet_criteria),
                "missing_evidence": list(missing_evidence),
                "constraints": list(constraints),
                "executor_id": _ACCEPTANCE_EXECUTOR_ID,
            },
        )

        # Critical: publish at most once (concurrent orchestrators rely on DB-level idempotency).
        if bool(getattr(persisted, "deduped", False) is True):
            return

        if self._event_bus is None:
            return

        # Reuse existing REPLAN event class so ConversationAgent recovery can react.
        await self._event_bus.publish(
            WorkflowAdjustmentRequestedEvent(
                source=_ACCEPTANCE_EXECUTOR_ID,
                workflow_id=workflow_id,
                failed_node_id="acceptance",
                failure_reason="acceptance_replan_requested",
                suggested_action="replan",
                execution_context={
                    "run_id": run_id,
                    "reflection_id": reflection_id,
                    "next_attempt": next_attempt,
                    "unmet_criteria": list(unmet_criteria),
                    "missing_evidence": list(missing_evidence),
                    "constraints": list(constraints),
                },
            )
        )

    def _safe_json_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Defensive JSON serialization so RunEvent persistence doesn't explode on non-serializable values.
        try:
            json.dumps(payload, ensure_ascii=False)
            return payload
        except TypeError:
            return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


__all__ = ["AcceptanceLoopOrchestrator", "compute_reflection_id"]

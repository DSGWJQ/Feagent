"""AcceptanceEvaluator - strict PASS/REPLAN/NEED_USER/BLOCKED verdict engine (Phase 3).

Inputs:
- CriteriaSnapshot (Phase 1)
- RunEvidenceSnapshot (Phase 2)

This module is intentionally side-effect free. Phase 4 will orchestrate the loop and
publish workflow_* events / trigger replans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.application.services.criteria_manager import (
    CriteriaSnapshot,
    Criterion,
    VerificationMethod,
)
from src.application.services.run_evidence_collector import RunEvidenceSnapshot


class AcceptanceVerdict(str, Enum):
    PASS = "PASS"
    REPLAN = "REPLAN"
    NEED_USER = "NEED_USER"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    verdict: AcceptanceVerdict
    attempt: int
    max_replan_attempts: int

    unmet_criteria: list[str] = field(default_factory=list)
    evidence_map: dict[str, list[str]] = field(default_factory=dict)
    missing_evidence: list[str] = field(default_factory=list)

    # Branch fields
    user_questions: list[str] = field(default_factory=list)
    replan_constraints: list[str] = field(default_factory=list)
    blocked_reason: str | None = None

    # Optional support fields
    test_report_ref: str | None = None


class AcceptanceEvaluator:
    """Strict acceptance evaluator (Phase 3)."""

    def __init__(self, *, require_test_report_for_pass: bool = True) -> None:
        self._require_test_report_for_pass = require_test_report_for_pass

    def evaluate(
        self,
        *,
        criteria_snapshot: CriteriaSnapshot,
        evidence_snapshot: RunEvidenceSnapshot,
        attempt: int,
        max_replan_attempts: int = 3,
        previous_unmet_criteria_ids: set[str] | None = None,
        tests_passed: bool | None = None,
        test_report_ref: str | None = None,
    ) -> AcceptanceResult:
        if attempt < 1:
            raise ValueError("attempt must start from 1")
        if max_replan_attempts < 1:
            raise ValueError("max_replan_attempts must be >= 1")

        criteria = list(criteria_snapshot.criteria or [])
        event_refs_by_type = self._get_event_refs_by_type(evidence_snapshot)

        unmet: list[str] = []
        missing: list[str] = []
        evidence_map: dict[str, list[str]] = {}

        for c in criteria:
            refs, satisfied = self._evaluate_single_criterion(
                criterion=c,
                criteria_snapshot=criteria_snapshot,
                evidence_snapshot=evidence_snapshot,
                event_refs_by_type=event_refs_by_type,
                tests_passed=tests_passed,
                test_report_ref=test_report_ref,
            )
            evidence_map[c.id] = list(refs)
            if not refs:
                missing.append(c.id)
            if not satisfied:
                unmet.append(c.id)

        unmet_set = set(unmet)

        # Conflicts are always NEED_USER (fail-closed).
        if criteria_snapshot.conflicts:
            return AcceptanceResult(
                verdict=AcceptanceVerdict.NEED_USER,
                attempt=attempt,
                max_replan_attempts=max_replan_attempts,
                unmet_criteria=unmet,
                evidence_map=evidence_map,
                missing_evidence=missing,
                user_questions=self._limit_questions(criteria_snapshot.user_questions, 3)
                or ["存在冲突的验收标准，请确认取舍（可一行回答）"],
                test_report_ref=test_report_ref,
            )

        # PASS hard constraints (Phase 3):
        # - all criteria satisfied
        # - evidence_map covers all criteria (each has >= 1 evidence ref)
        # - tests passed (and has a reference) if required
        pass_requirements_met = (
            not unmet
            and not missing
            and (tests_passed is True)
            and (not self._require_test_report_for_pass or bool((test_report_ref or "").strip()))
        )
        if pass_requirements_met:
            return AcceptanceResult(
                verdict=AcceptanceVerdict.PASS,
                attempt=attempt,
                max_replan_attempts=max_replan_attempts,
                unmet_criteria=[],
                evidence_map=evidence_map,
                missing_evidence=[],
                test_report_ref=test_report_ref,
            )

        # If we cannot verify criteria (missing evidence), or criteria are unverifiable,
        # prefer NEED_USER over REPLAN to avoid meaningless loops.
        needs_user = bool(criteria_snapshot.unverifiable_criteria_ids) or any(
            self._criterion_requires_user_confirmation(c, criteria_snapshot=criteria_snapshot)
            for c in criteria
            if c.id in missing
        )

        # Attempt limit gate.
        if attempt >= max_replan_attempts:
            return AcceptanceResult(
                verdict=AcceptanceVerdict.BLOCKED,
                attempt=attempt,
                max_replan_attempts=max_replan_attempts,
                unmet_criteria=unmet,
                evidence_map=evidence_map,
                missing_evidence=missing,
                blocked_reason="max_replan_attempts_reached",
                user_questions=self._limit_questions(criteria_snapshot.user_questions, 3),
                test_report_ref=test_report_ref,
            )

        # REPLAN loop guard: if unmet does not strictly shrink, stop automatic replanning.
        if previous_unmet_criteria_ids is not None and unmet_set:
            if not (unmet_set < set(previous_unmet_criteria_ids)):
                needs_user = True

        if needs_user:
            questions = list(criteria_snapshot.user_questions or [])
            if not questions:
                # Fall back to asking about unverifiable/missing criteria.
                questions = self._derive_questions_from_missing(
                    criteria=criteria,
                    missing_ids=set(missing),
                    limit=3,
                )
            return AcceptanceResult(
                verdict=AcceptanceVerdict.NEED_USER,
                attempt=attempt,
                max_replan_attempts=max_replan_attempts,
                unmet_criteria=unmet,
                evidence_map=evidence_map,
                missing_evidence=missing,
                user_questions=self._limit_questions(questions, 3),
                test_report_ref=test_report_ref,
            )

        # Otherwise, there is unmet evidence we can act on => REPLAN.
        constraints = self._build_replan_constraints(criteria=criteria, unmet_ids=set(unmet))
        return AcceptanceResult(
            verdict=AcceptanceVerdict.REPLAN,
            attempt=attempt,
            max_replan_attempts=max_replan_attempts,
            unmet_criteria=unmet,
            evidence_map=evidence_map,
            missing_evidence=missing,
            replan_constraints=constraints,
            test_report_ref=test_report_ref,
        )

    def _get_event_refs_by_type(
        self, evidence_snapshot: RunEvidenceSnapshot
    ) -> dict[str, list[str]]:
        summary = (
            evidence_snapshot.execution_summary
            if isinstance(evidence_snapshot.execution_summary, dict)
            else {}
        )
        refs = summary.get("event_refs_by_type")
        if not isinstance(refs, dict):
            return {}
        typed: dict[str, list[str]] = {}
        for k, v in refs.items():
            if not isinstance(k, str):
                continue
            if not isinstance(v, list):
                continue
            typed[k] = [str(x) for x in v if isinstance(x, str)]
        return typed

    def _evaluate_single_criterion(
        self,
        *,
        criterion: Criterion,
        criteria_snapshot: CriteriaSnapshot,
        evidence_snapshot: RunEvidenceSnapshot,
        event_refs_by_type: dict[str, list[str]],
        tests_passed: bool | None,
        test_report_ref: str | None,
    ) -> tuple[list[str], bool]:
        # Unverifiable criteria must not be auto-satisfied (fail-closed).
        if criterion.id in set(criteria_snapshot.unverifiable_criteria_ids or []):
            return ([], False)

        if criterion.verification_method is VerificationMethod.MANUAL:
            return ([], False)

        if criterion.verification_method is VerificationMethod.TEST:
            ref = (test_report_ref or "").strip()
            if tests_passed is True and ref:
                return ([ref], True)
            # Missing/failed tests => not satisfied; evidence is the missing ref (empty list).
            return ([], False)

        if criterion.verification_method is VerificationMethod.ARTIFACT:
            # Phase 2 placeholder.
            return ([], False)

        if criterion.verification_method is VerificationMethod.RUN_EVENT:
            return self._evaluate_run_event_criterion(
                criterion=criterion,
                evidence_snapshot=evidence_snapshot,
                event_refs_by_type=event_refs_by_type,
            )

        # UNKNOWN: fail-closed, require evidence mapping to be defined later.
        return ([], False)

    def _evaluate_run_event_criterion(
        self,
        *,
        criterion: Criterion,
        evidence_snapshot: RunEvidenceSnapshot,
        event_refs_by_type: dict[str, list[str]],
    ) -> tuple[list[str], bool]:
        # Phase 3 minimal evaluator: recognize only the baseline success criterion.
        baseline_text = "Run 执行成功（run.status=COMPLETED 且终态事件为 workflow_complete）"
        if criterion.text.strip() != baseline_text:
            return ([], False)

        terminal = None
        summary = (
            evidence_snapshot.execution_summary
            if isinstance(evidence_snapshot.execution_summary, dict)
            else {}
        )
        terminal_raw = summary.get("terminal_event_type")
        if isinstance(terminal_raw, str) and terminal_raw.strip():
            terminal = terminal_raw.strip()

        # Evidence refs: prefer terminal event refs if present (complete/error).
        refs: list[str] = []
        if event_refs_by_type.get("workflow_complete"):
            refs = list(event_refs_by_type["workflow_complete"])
        elif event_refs_by_type.get("workflow_error"):
            refs = list(event_refs_by_type["workflow_error"])

        confirm_required = bool(summary.get("confirm_required") is True)
        confirm_decision = summary.get("confirm_decision")
        confirm_allowed = (not confirm_required) or (confirm_decision == "allow")

        satisfied = terminal == "workflow_complete" and confirm_allowed
        return (refs, satisfied)

    def _criterion_requires_user_confirmation(
        self, criterion: Criterion, *, criteria_snapshot: CriteriaSnapshot
    ) -> bool:
        # If it is unverifiable, we need the user.
        if criterion.id in set(criteria_snapshot.unverifiable_criteria_ids or []):
            return True
        if criterion.verification_method in {VerificationMethod.MANUAL, VerificationMethod.UNKNOWN}:
            return True
        return False

    def _derive_questions_from_missing(
        self, *, criteria: list[Criterion], missing_ids: set[str], limit: int
    ) -> list[str]:
        questions: list[str] = []
        for c in criteria:
            if c.id not in missing_ids:
                continue
            if len(questions) >= limit:
                break
            if c.verification_method is VerificationMethod.MANUAL:
                questions.append(f"请确认该标准是否已满足：{c.text}（allow/deny 或一句话描述）")
            else:
                questions.append(
                    f"缺少可复查证据以验收：{c.text}。请提供证据口径（例如期望的输出/阈值/文件路径）。"
                )
        return questions

    def _build_replan_constraints(
        self, *, criteria: list[Criterion], unmet_ids: set[str]
    ) -> list[str]:
        constraints: list[str] = []
        for c in criteria:
            if c.id not in unmet_ids:
                continue
            constraints.append(f"fix_unmet_criterion:{c.id}:{c.text}")
        # Defensive cap to keep payload bounded.
        return constraints[:20]

    def _limit_questions(self, questions: list[str] | None, limit: int) -> list[str]:
        if not questions:
            return []
        return [q for q in questions if isinstance(q, str) and q.strip()][:limit]


__all__ = ["AcceptanceEvaluator", "AcceptanceResult", "AcceptanceVerdict"]

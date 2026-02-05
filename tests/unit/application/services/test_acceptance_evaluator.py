from __future__ import annotations

from src.application.services.acceptance_evaluator import (
    AcceptanceEvaluator,
    AcceptanceVerdict,
)
from src.application.services.criteria_manager import CriteriaManager
from src.application.services.run_evidence_collector import RunEvidenceSnapshot


def _evidence_snapshot(
    *,
    run_id: str,
    terminal_event_type: str,
    refs_by_type: dict[str, list[str]],
    confirm_required: bool = False,
    confirm_decision: str | None = None,
) -> RunEvidenceSnapshot:
    # Flatten refs for the snapshot root field.
    run_event_refs: list[str] = []
    for refs in refs_by_type.values():
        run_event_refs.extend(list(refs))

    return RunEvidenceSnapshot(
        run_id=run_id,
        run_event_refs=sorted(run_event_refs),
        artifact_refs=[],
        test_report_ref=None,
        execution_summary={
            "run_event_count": len(run_event_refs),
            "terminal_event_type": terminal_event_type,
            "confirm_required": confirm_required,
            "confirm_decision": confirm_decision,
            "event_refs_by_type": refs_by_type,
        },
    )


def test_acceptance_pass_requires_full_evidence_and_tests():
    criteria_snapshot = CriteriaManager().build_snapshot(
        task_description=None, user_criteria=None, plan_criteria=None
    )
    run_id = "run_1"
    complete_ref = f"run_event:{run_id}:execution:1"
    evidence_snapshot = _evidence_snapshot(
        run_id=run_id,
        terminal_event_type="workflow_complete",
        refs_by_type={"workflow_complete": [complete_ref]},
    )

    evaluator = AcceptanceEvaluator(require_test_report_for_pass=True)
    result = evaluator.evaluate(
        criteria_snapshot=criteria_snapshot,
        evidence_snapshot=evidence_snapshot,
        attempt=1,
        max_replan_attempts=3,
        tests_passed=True,
        test_report_ref="test_report:unit",
    )

    assert result.verdict is AcceptanceVerdict.PASS
    assert result.unmet_criteria == []
    assert result.missing_evidence == []


def test_acceptance_replan_when_unmet_but_evidence_exists():
    criteria_snapshot = CriteriaManager().build_snapshot(
        task_description=None, user_criteria=None, plan_criteria=None
    )
    run_id = "run_2"
    error_ref = f"run_event:{run_id}:execution:2"
    evidence_snapshot = _evidence_snapshot(
        run_id=run_id,
        terminal_event_type="workflow_error",
        refs_by_type={"workflow_error": [error_ref]},
    )

    evaluator = AcceptanceEvaluator(require_test_report_for_pass=True)
    result = evaluator.evaluate(
        criteria_snapshot=criteria_snapshot,
        evidence_snapshot=evidence_snapshot,
        attempt=1,
        max_replan_attempts=3,
        tests_passed=True,
        test_report_ref="test_report:unit",
    )

    assert result.verdict is AcceptanceVerdict.REPLAN
    assert result.unmet_criteria
    assert result.missing_evidence == []


def test_acceptance_need_user_on_conflicting_criteria():
    criteria_snapshot = CriteriaManager().build_snapshot(
        task_description=None,
        user_criteria=["必须写入数据库", "禁止写入数据库"],
        plan_criteria=None,
    )
    run_id = "run_3"
    evidence_snapshot = _evidence_snapshot(
        run_id=run_id,
        terminal_event_type="workflow_complete",
        refs_by_type={"workflow_complete": [f"run_event:{run_id}:execution:3"]},
    )

    evaluator = AcceptanceEvaluator()
    result = evaluator.evaluate(
        criteria_snapshot=criteria_snapshot,
        evidence_snapshot=evidence_snapshot,
        attempt=1,
        max_replan_attempts=3,
        tests_passed=True,
        test_report_ref="test_report:unit",
    )

    assert result.verdict is AcceptanceVerdict.NEED_USER
    assert result.user_questions


def test_acceptance_blocked_when_attempt_limit_reached():
    criteria_snapshot = CriteriaManager().build_snapshot(
        task_description=None, user_criteria=None, plan_criteria=None
    )
    run_id = "run_4"
    error_ref = f"run_event:{run_id}:execution:4"
    evidence_snapshot = _evidence_snapshot(
        run_id=run_id,
        terminal_event_type="workflow_error",
        refs_by_type={"workflow_error": [error_ref]},
    )

    evaluator = AcceptanceEvaluator()
    result = evaluator.evaluate(
        criteria_snapshot=criteria_snapshot,
        evidence_snapshot=evidence_snapshot,
        attempt=3,
        max_replan_attempts=3,
        tests_passed=True,
        test_report_ref="test_report:unit",
    )

    assert result.verdict is AcceptanceVerdict.BLOCKED
    assert result.blocked_reason


def test_acceptance_need_user_when_unmet_does_not_shrink():
    criteria_snapshot = CriteriaManager().build_snapshot(
        task_description=None, user_criteria=None, plan_criteria=None
    )
    baseline_id = criteria_snapshot.criteria[0].id
    run_id = "run_5"
    error_ref = f"run_event:{run_id}:execution:5"
    evidence_snapshot = _evidence_snapshot(
        run_id=run_id,
        terminal_event_type="workflow_error",
        refs_by_type={"workflow_error": [error_ref]},
    )

    evaluator = AcceptanceEvaluator()
    result = evaluator.evaluate(
        criteria_snapshot=criteria_snapshot,
        evidence_snapshot=evidence_snapshot,
        attempt=2,
        max_replan_attempts=3,
        previous_unmet_criteria_ids={baseline_id},
        tests_passed=True,
        test_report_ref="test_report:unit",
    )

    assert result.verdict is AcceptanceVerdict.NEED_USER

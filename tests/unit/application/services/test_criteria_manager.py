from __future__ import annotations

from src.application.services.criteria_manager import (
    CriteriaManager,
    CriteriaSource,
    VerificationMethod,
)


def test_explicit_user_criteria_builds_snapshot_without_questions():
    manager = CriteriaManager()

    snapshot = manager.build_snapshot(
        task_description="any",
        user_criteria=["Run 必须成功"],
        plan_criteria=None,
    )

    assert len(snapshot.criteria) == 1
    assert snapshot.criteria[0].source is CriteriaSource.USER
    assert snapshot.criteria[0].verification_method in {
        VerificationMethod.UNKNOWN,
        VerificationMethod.RUN_EVENT,
    }
    assert snapshot.conflicts == []
    assert snapshot.user_questions == []
    assert len(snapshot.criteria_hash) == 64


def test_inferred_subjective_criteria_triggers_need_user_questions():
    manager = CriteriaManager()

    snapshot = manager.build_snapshot(
        task_description="让结果更漂亮",
        user_criteria=None,
        plan_criteria=None,
    )

    # Always includes a baseline success criterion.
    assert any(c.text == CriteriaManager.BASELINE_SUCCESS_CRITERION_TEXT for c in snapshot.criteria)

    # Subjective goal is treated as manual/unverifiable => ask user.
    assert snapshot.unverifiable_criteria_ids
    assert snapshot.user_questions
    assert len(snapshot.user_questions) <= 3
    assert any("量化" in q or "可验证" in q for q in snapshot.user_questions)


def test_conflicting_criteria_triggers_conflict_question():
    manager = CriteriaManager()

    snapshot = manager.build_snapshot(
        task_description=None,
        user_criteria=["必须写入数据库", "禁止写入数据库"],
        plan_criteria=None,
    )

    assert snapshot.conflicts
    assert snapshot.user_questions
    assert snapshot.user_questions[0].startswith("以下标准存在冲突")

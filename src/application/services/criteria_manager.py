"""CriteriaManager - Session-side criteria schema + merge/conflict helpers.

Phase 1 deliverable (docs/planning/workflow-reflection-acceptance-unification-plan.md):
- criteria schema (source/verification_method/hash/snapshot)
- merge + conflict detection (fail-closed)
- minimal NEED_USER question generation (1~3)

This module is intentionally self-contained (no DB / no I/O) so later phases can
reuse it in API flows, background jobs, and tests.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CriteriaSource(str, Enum):
    USER = "user"
    PLAN = "plan"
    INFERRED = "inferred"


class VerificationMethod(str, Enum):
    # Evidence is expected to come from Runs (run.status + run_events replay).
    RUN_EVENT = "run_event"
    # Evidence is expected to come from a test report / deterministic E2E.
    TEST = "test"
    # Evidence is expected to come from an artifact reference (future Phase 2).
    ARTIFACT = "artifact"
    # Evidence requires explicit user confirmation (manual / subjective).
    MANUAL = "manual"
    UNKNOWN = "unknown"


_SOURCE_PRIORITY: dict[CriteriaSource, int] = {
    CriteriaSource.USER: 3,
    CriteriaSource.PLAN: 2,
    CriteriaSource.INFERRED: 1,
}


@dataclass(frozen=True, slots=True)
class Criterion:
    """A single acceptance criterion.

    id is stable across sources (derived from normalized text) so merging is deterministic.
    """

    id: str
    text: str
    source: CriteriaSource
    verification_method: VerificationMethod
    meta: dict[str, Any] = field(default_factory=dict)

    def to_canonical_dict(self) -> dict[str, Any]:
        # Keep canonical form minimal to make hashing stable.
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source.value,
            "verification_method": self.verification_method.value,
            "meta": self.meta,
        }


@dataclass(frozen=True, slots=True)
class CriteriaConflict:
    left_id: str
    right_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class CriteriaSnapshot:
    criteria: list[Criterion]
    criteria_hash: str
    conflicts: list[CriteriaConflict] = field(default_factory=list)
    unverifiable_criteria_ids: list[str] = field(default_factory=list)
    user_questions: list[str] = field(default_factory=list)


_RE_SPACES = re.compile(r"\s+")
_RE_PUNCT = re.compile(r"[^\w\u4e00-\u9fff]+", flags=re.UNICODE)
_RE_HAS_NUMBER = re.compile(r"\d")

_NEGATION_TOKENS: tuple[str, ...] = (
    # Chinese
    "不",
    "禁止",
    "不得",
    "不能",
    "无需",
    "不要",
    # English
    "no",
    "not",
    "never",
    "deny",
)

_STOPWORDS: tuple[str, ...] = (
    # Chinese
    "必须",
    "需要",
    "应当",
    "应该",
    "请",
    "确保",
    "允许",
    "可以",
    "尽量",
    "务必",
    # English
    "must",
    "should",
    "shall",
    "may",
    "please",
    "ensure",
)

_SUBJECTIVE_HINTS: tuple[str, ...] = (
    "更好",
    "更快",
    "更漂亮",
    "更美观",
    "好看",
    "优雅",
    "易用",
    "友好",
    "更稳定",
    "更安全",
    "better",
    "faster",
    "prettier",
    "beautiful",
    "secure",
)


def _normalize_text(text: str) -> str:
    normalized = (text or "").strip().lower()
    normalized = _RE_SPACES.sub(" ", normalized)
    return normalized


def _stable_criterion_id(text: str) -> str:
    digest = hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()[:12]
    return f"crit_{digest}"


def _is_negated(text: str) -> bool:
    t = _normalize_text(text)
    return any(token in t for token in _NEGATION_TOKENS)


def _core_text(text: str) -> str:
    """Best-effort core extractor for conflict detection.

    Fail-closed philosophy: prefer detecting a conflict when we are reasonably sure,
    but avoid being overly aggressive to reduce noisy NEED_USER.
    """

    t = _normalize_text(text)
    for token in _NEGATION_TOKENS:
        t = t.replace(token, " ")
    for token in _STOPWORDS:
        t = t.replace(token, " ")
    t = _RE_PUNCT.sub(" ", t)
    t = _RE_SPACES.sub(" ", t).strip()
    return t


def _is_subjective_and_unquantified(text: str) -> bool:
    t = _normalize_text(text)
    if _RE_HAS_NUMBER.search(t):
        return False
    return any(hint in t for hint in _SUBJECTIVE_HINTS)


class CriteriaManager:
    """Build and validate criteria snapshots (Phase 1)."""

    BASELINE_SUCCESS_CRITERION_TEXT = (
        "Run 执行成功（run.status=COMPLETED 且终态事件为 workflow_complete）"
    )

    def build_snapshot(
        self,
        *,
        task_description: str | None,
        user_criteria: list[str] | None = None,
        plan_criteria: list[str] | None = None,
    ) -> CriteriaSnapshot:
        merged: dict[str, Criterion] = {}

        def _add(text: str, source: CriteriaSource) -> None:
            normalized = _normalize_text(text)
            if not normalized:
                return
            cid = _stable_criterion_id(normalized)

            verification_method = self._infer_verification_method(text=text, source=source)
            candidate = Criterion(
                id=cid,
                text=text.strip(),
                source=source,
                verification_method=verification_method,
                meta={},
            )

            existing = merged.get(cid)
            if existing is None:
                merged[cid] = candidate
                return

            # Prefer higher-priority sources (user > plan > inferred).
            if _SOURCE_PRIORITY[candidate.source] > _SOURCE_PRIORITY[existing.source]:
                merged[cid] = candidate

        for text in user_criteria or []:
            _add(text, CriteriaSource.USER)
        for text in plan_criteria or []:
            _add(text, CriteriaSource.PLAN)

        if not merged:
            inferred = self._infer_minimum_criteria(task_description=task_description)
            for text, method in inferred:
                _add(text, CriteriaSource.INFERRED)
                # Override inferred verification_method if we already know it.
                cid = _stable_criterion_id(_normalize_text(text))
                if cid in merged:
                    merged[cid] = Criterion(
                        id=cid,
                        text=text.strip(),
                        source=CriteriaSource.INFERRED,
                        verification_method=method,
                        meta={},
                    )

        # Deterministic ordering for hashing + stable UIs.
        criteria = sorted(
            merged.values(),
            key=lambda c: (-_SOURCE_PRIORITY[c.source], _normalize_text(c.text)),
        )

        conflicts = self._detect_conflicts(criteria)
        unverifiable = [c.id for c in criteria if self._is_unverifiable(c)]
        questions = self._build_user_questions(
            criteria=criteria,
            conflicts=conflicts,
            unverifiable_ids=unverifiable,
            limit=3,
        )

        canonical = [c.to_canonical_dict() for c in criteria]
        criteria_hash = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return CriteriaSnapshot(
            criteria=criteria,
            criteria_hash=criteria_hash,
            conflicts=conflicts,
            unverifiable_criteria_ids=unverifiable,
            user_questions=questions,
        )

    def _infer_minimum_criteria(
        self, *, task_description: str | None
    ) -> list[tuple[str, VerificationMethod]]:
        # KISS: always include a verifiable baseline success criterion.
        inferred: list[tuple[str, VerificationMethod]] = [
            (self.BASELINE_SUCCESS_CRITERION_TEXT, VerificationMethod.RUN_EVENT)
        ]

        # If the task description contains subjective hints, add it as a manual criterion
        # so acceptance fails-closed unless user clarifies.
        desc = (task_description or "").strip()
        if desc and _is_subjective_and_unquantified(desc):
            inferred.append((f"满足目标：{desc}", VerificationMethod.MANUAL))

        return inferred

    def _infer_verification_method(
        self, *, text: str, source: CriteriaSource
    ) -> VerificationMethod:
        # Heuristics only; later phases can enrich this based on workflow structure.
        normalized = _normalize_text(text)
        if source is CriteriaSource.INFERRED and normalized == _normalize_text(
            self.BASELINE_SUCCESS_CRITERION_TEXT
        ):
            return VerificationMethod.RUN_EVENT
        if _is_subjective_and_unquantified(normalized):
            return VerificationMethod.MANUAL
        return VerificationMethod.UNKNOWN

    def _is_unverifiable(self, criterion: Criterion) -> bool:
        # For Phase 1, we treat MANUAL as unverifiable without explicit user confirmation.
        if criterion.verification_method is VerificationMethod.MANUAL:
            return True
        # UNKNOWN criteria that look subjective should also be treated as unverifiable.
        if (
            criterion.verification_method is VerificationMethod.UNKNOWN
            and _is_subjective_and_unquantified(criterion.text)
        ):
            return True
        return False

    def _detect_conflicts(self, criteria: list[Criterion]) -> list[CriteriaConflict]:
        # Conflict heuristic: same "core" but opposite polarity.
        indexed: dict[str, tuple[Criterion, bool]] = {}
        conflicts: list[CriteriaConflict] = []

        for c in criteria:
            core = _core_text(c.text)
            if not core:
                continue
            neg = _is_negated(c.text)
            existing = indexed.get(core)
            if existing is None:
                indexed[core] = (c, neg)
                continue

            other, other_neg = existing
            if neg != other_neg:
                # Stable ordering to avoid duplicate conflicts.
                left, right = (other, c) if other.id < c.id else (c, other)
                conflicts.append(
                    CriteriaConflict(
                        left_id=left.id,
                        right_id=right.id,
                        reason=f"conflict_on_core:{core}",
                    )
                )

        return conflicts

    def _build_user_questions(
        self,
        *,
        criteria: list[Criterion],
        conflicts: list[CriteriaConflict],
        unverifiable_ids: list[str],
        limit: int,
    ) -> list[str]:
        questions: list[str] = []

        # Conflicts first (fail-closed).
        id_to_text = {c.id: c.text for c in criteria}
        for conflict in conflicts:
            if len(questions) >= limit:
                return questions
            left = id_to_text.get(conflict.left_id, conflict.left_id)
            right = id_to_text.get(conflict.right_id, conflict.right_id)
            questions.append(f"以下标准存在冲突，请确认保留哪一条：A) {left}  B) {right}")

        for cid in unverifiable_ids:
            if len(questions) >= limit:
                return questions
            text = id_to_text.get(cid, cid)
            questions.append(
                f"请将该标准量化/可验证：{text}（例如给出阈值/示例输出/对比基准；可一行回答）"
            )

        return questions


__all__ = [
    "CriteriaManager",
    "CriteriaSnapshot",
    "CriteriaSource",
    "CriteriaConflict",
    "Criterion",
    "VerificationMethod",
]

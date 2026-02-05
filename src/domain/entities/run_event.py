"""RunEvent 实体 - Run 的事件流记录

业务定义：
- RunEvent 表示一次 Run 的可追踪事件（execution/planning 等通道）
- 用于审计、调试与前端回放
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class RunEvent:
    """RunEvent 领域实体"""

    id: int | str
    run_id: str
    type: str
    channel: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sequence: int | None = None
    # Optional idempotency key for persistence-level de-duplication.
    # When present, repositories may treat (run_id, channel, idempotency_key) as unique.
    idempotency_key: str | None = None
    # Persistence metadata (not part of domain equality): True when repository returns an existing row.
    deduped: bool = field(default=False, compare=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        type: str | None = None,
        event_type: str | None = None,
        channel: str,
        payload: dict[str, Any] | None = None,
        sequence: int | None = None,
        idempotency_key: str | None = None,
        event_id: int | str | None = None,
        id: int | str | None = None,  # noqa: A002 - compat alias for tests/legacy callers
    ) -> RunEvent:
        effective_type = type or event_type
        if not isinstance(effective_type, str) or not effective_type.strip():
            raise ValueError("RunEvent.create requires `type` (or legacy `event_type`)")

        effective_id: int | str
        if event_id is not None:
            effective_id = event_id
        elif id is not None:
            effective_id = id
        else:
            effective_id = f"evt_{uuid4().hex[:8]}"

        normalized_key = None
        if isinstance(idempotency_key, str) and idempotency_key.strip():
            normalized_key = idempotency_key.strip()

        return cls(
            id=effective_id,
            run_id=run_id,
            type=effective_type,
            channel=channel,
            payload=payload or {},
            created_at=datetime.now(UTC),
            sequence=sequence,
            idempotency_key=normalized_key,
        )

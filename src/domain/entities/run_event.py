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

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        type: str,
        channel: str,
        payload: dict[str, Any] | None = None,
        sequence: int | None = None,
    ) -> RunEvent:
        return cls(
            id=f"evt_{uuid4().hex[:8]}",
            run_id=run_id,
            type=type,
            channel=channel,
            payload=payload or {},
            created_at=datetime.now(UTC),
            sequence=sequence,
        )

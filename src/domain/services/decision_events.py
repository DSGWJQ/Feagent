from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.services.event_bus import Event


@dataclass
class DecisionValidatedEvent(Event):
    """决策验证通过事件"""

    original_decision_id: str = ""
    decision_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionRejectedEvent(Event):
    """决策拒绝事件"""

    original_decision_id: str = ""
    decision_type: str = ""
    reason: str = ""
    errors: list[str] = field(default_factory=list)

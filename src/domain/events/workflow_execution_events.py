"""Workflow execution events (Domain).

These events are published to the in-process EventBus to support:
- multi-agent collaboration (state monitors / orchestrators)
- workflow execution observability (SSE / run-events persistence)

Design (KISS):
- Use a single NodeExecutionEvent with a `status` field to avoid event-type explosion.
- Keep fields optional and backward-compatible; consumers must read defensively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.services.event_bus import Event


@dataclass
class WorkflowExecutionStartedEvent(Event):
    """Workflow execution started."""

    workflow_id: str = ""
    node_count: int = 0


@dataclass
class WorkflowExecutionCompletedEvent(Event):
    """Workflow execution reached a terminal state (completed/failed)."""

    workflow_id: str = ""
    status: str = "completed"  # completed | failed
    success: bool = True

    # Backward-compatible payload (used by legacy WorkflowAgent paths).
    result: dict[str, Any] = field(default_factory=dict)

    # Execution-kernel payload (used by ExecuteWorkflowUseCase / SSE).
    final_result: Any = None
    execution_log: list[dict[str, Any]] = field(default_factory=list)
    execution_summary: dict[str, Any] = field(default_factory=dict)

    error: str | None = None
    error_type: str | None = None


@dataclass
class NodeExecutionEvent(Event):
    """Node execution lifecycle event.

    status:
    - running: node_start
    - completed: node_complete
    - failed: node_error
    - skipped: node_skipped
    """

    workflow_id: str = ""
    node_id: str = ""
    node_type: str = ""
    status: str = ""  # running | completed | failed | skipped

    inputs: dict[str, Any] | None = None
    result: Any | None = None
    error: str | None = None

    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "WorkflowExecutionStartedEvent",
    "WorkflowExecutionCompletedEvent",
    "NodeExecutionEvent",
]

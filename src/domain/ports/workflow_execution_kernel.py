"""WorkflowExecutionKernelPort (Domain Port)

This port defines the single authoritative workflow execution surface used by:
- API streaming execution endpoints
- WorkflowAgent decision execution path

Contract (event semantics):
- node_start / node_complete / node_error
- workflow_complete / workflow_error

The concrete implementation lives outside the Domain (Application/Infrastructure),
following dependency inversion.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, Protocol


class WorkflowExecutionKernelPort(Protocol):
    async def execute(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def gate_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        after_gate: Callable[[], Awaitable[None]] | None = None,
    ) -> None: ...

    def execute_streaming(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        after_gate: Callable[[], Awaitable[None]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    def stream_after_gate(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

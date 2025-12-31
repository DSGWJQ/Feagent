"""Planning event mapper.

Transforms Application-layer planning events into PlanningEvent SSE contract.

Responsibilities:
- Assign sequence numbers (monotonically increasing)
- Generate timestamps
- Assemble metadata
- Map domain events to SSE contract types

The router layer should only:
- Call this mapper
- Emit SSE strings
- Record to RunEvents (optional)
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.application.events.workflow_planning_events import (
    ReActStepCompleted,
    ResearchPlanGenerated,
    WorkflowPatchGenerated,
    WorkflowPlanningCompleted,
    WorkflowPlanningEvent,
    WorkflowPlanningFailed,
    WorkflowPlanningStarted,
)
from src.application.services.planning_event import PlanningEvent

if TYPE_CHECKING:
    from src.application.services.workflow_public_mapper import WorkflowPublicMapper


class PlanningEventMapper:
    """Maps workflow planning events to PlanningEvent SSE contract.

    Usage:
        mapper = PlanningEventMapper(workflow_mapper=WorkflowPublicMapper())

        # Optional: emit initial event before UseCase starts
        yield emit(mapper.create_initial_event())

        for use_case_event in use_case.execute_streaming(input):
            for sse_event in mapper.map(use_case_event):
                yield emit(sse_event)
    """

    def __init__(
        self,
        *,
        workflow_mapper: WorkflowPublicMapper,
        clock: Callable[[], str] | None = None,
        initial_sequence: int = 0,
    ) -> None:
        """Initialize the mapper.

        Args:
            workflow_mapper: Mapper for Workflow entity -> dict
            clock: Optional clock function for timestamps (default: UTC ISO format)
            initial_sequence: Starting sequence number (default: 0)
        """
        self._workflow_mapper = workflow_mapper
        self._clock = clock or (lambda: datetime.now(UTC).isoformat())
        self._sequence = initial_sequence

    def _next_sequence(self) -> int:
        """Get next sequence number (1-based, monotonically increasing)."""
        self._sequence += 1
        return self._sequence

    def create_initial_event(
        self,
        content: str = "AI is analyzing the request.",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> PlanningEvent:
        """Create initial thinking event before UseCase starts.

        This provides a public API for creating the first event,
        avoiding router layer needing to access _next_sequence().

        Args:
            content: Initial message content
            metadata: Optional additional metadata (e.g. workflow_id)

        Returns:
            PlanningEvent with type="thinking" and proper sequence
        """
        return PlanningEvent(
            type="thinking",
            content=content,
            sequence=self._next_sequence(),
            timestamp=self._clock(),
            metadata=metadata or {},
        )

    def create_error_event(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> PlanningEvent:
        """Create error event for unexpected failures.

        This provides a public API for creating error events,
        used by router layer for exception/fallback handling.

        Args:
            content: Error message
            metadata: Optional additional metadata

        Returns:
            PlanningEvent with type="error" and is_final=True
        """
        return PlanningEvent(
            type="error",
            content=content,
            sequence=self._next_sequence(),
            timestamp=self._clock(),
            is_final=True,
            metadata=metadata or {},
        )

    def map(self, event: WorkflowPlanningEvent) -> list[PlanningEvent]:
        """Map a planning event to one or more PlanningEvents.

        A single domain event may produce multiple PlanningEvents.
        For example, ReActStepCompleted produces up to 3 events:
        - thinking (from thought)
        - tool_call (from action)
        - tool_result (from observation)

        Args:
            event: Application-layer planning event

        Returns:
            List of PlanningEvent instances ready for SSE emission

        Raises:
            TypeError: If event type is not supported
        """
        ts = self._clock()

        if isinstance(event, WorkflowPlanningStarted):
            return self._map_started(event, ts)

        if isinstance(event, ReActStepCompleted):
            return self._map_react_step(event, ts)

        if isinstance(event, WorkflowPatchGenerated):
            return self._map_patch(event, ts)

        if isinstance(event, ResearchPlanGenerated):
            return self._map_research_plan(event, ts)

        if isinstance(event, WorkflowPlanningCompleted):
            return self._map_completed(event, ts)

        if isinstance(event, WorkflowPlanningFailed):
            return self._map_failed(event, ts)

        raise TypeError(f"Unsupported planning event type: {type(event).__name__}")

    def _map_started(self, event: WorkflowPlanningStarted, ts: str) -> list[PlanningEvent]:
        """Map WorkflowPlanningStarted -> thinking event."""
        return [
            PlanningEvent(
                type="thinking",
                content="Processing workflow request.",
                sequence=self._next_sequence(),
                timestamp=ts,
                metadata={"workflow_id": event.workflow_id},
            )
        ]

    def _map_react_step(self, event: ReActStepCompleted, ts: str) -> list[PlanningEvent]:
        """Map ReActStepCompleted -> thinking, tool_call, tool_result events."""
        step_number = event.step_number
        tool_id = f"react_{step_number}"
        events: list[PlanningEvent] = []

        # thought -> thinking
        if event.thought:
            events.append(
                PlanningEvent(
                    type="thinking",
                    content=event.thought,
                    sequence=self._next_sequence(),
                    timestamp=ts,
                    metadata={"step_number": step_number},
                )
            )

        # action -> tool_call
        action = event.action or {}
        if action:
            events.append(
                PlanningEvent(
                    type="tool_call",
                    sequence=self._next_sequence(),
                    timestamp=ts,
                    metadata={
                        "tool_name": action.get("type", "unknown"),
                        "tool_id": tool_id,
                        "arguments": action,
                        "step_number": step_number,
                    },
                )
            )

        # observation -> tool_result
        if event.observation:
            events.append(
                PlanningEvent(
                    type="tool_result",
                    sequence=self._next_sequence(),
                    timestamp=ts,
                    metadata={
                        "tool_id": tool_id,
                        "result": {"observation": event.observation},
                        "success": True,
                        "step_number": step_number,
                    },
                )
            )

        return events

    def _map_patch(self, event: WorkflowPatchGenerated, ts: str) -> list[PlanningEvent]:
        """Map WorkflowPatchGenerated -> patch event."""
        workflow_dict = None
        if event.workflow_preview is not None:
            workflow_dict = self._workflow_mapper.to_dict(event.workflow_preview)

        return [
            PlanningEvent(
                type="patch",
                content="Preview workflow changes.",
                sequence=self._next_sequence(),
                timestamp=ts,
                metadata={
                    "modifications_count": event.modifications_count,
                    "intent": event.intent,
                    "confidence": event.confidence,
                    "workflow": workflow_dict,
                },
            )
        ]

    def _map_research_plan(self, event: ResearchPlanGenerated, ts: str) -> list[PlanningEvent]:
        """Map ResearchPlanGenerated -> research_plan event.

        Note: This is a terminal event (is_final=True) for research plan generation.
        """
        plan_dict = event.plan.model_dump()

        return [
            PlanningEvent(
                type="research_plan",
                content="Research plan generated successfully.",
                sequence=self._next_sequence(),
                timestamp=ts,
                is_final=True,
                metadata={
                    "research_plan": plan_dict,
                },
            )
        ]

    def _map_completed(self, event: WorkflowPlanningCompleted, ts: str) -> list[PlanningEvent]:
        """Map WorkflowPlanningCompleted -> final event."""
        workflow_dict = self._workflow_mapper.to_dict(event.workflow)

        return [
            PlanningEvent(
                type="final",
                content=event.ai_message or "Workflow updated successfully.",
                sequence=self._next_sequence(),
                timestamp=ts,
                is_final=True,
                metadata={
                    "workflow": workflow_dict,
                    "rag_sources": event.rag_sources,
                },
            )
        ]

    def _map_failed(self, event: WorkflowPlanningFailed, ts: str) -> list[PlanningEvent]:
        """Map WorkflowPlanningFailed -> error event."""
        return [
            PlanningEvent(
                type="error",
                content=event.detail or "Unknown error",
                sequence=self._next_sequence(),
                timestamp=ts,
                is_final=True,
                metadata={
                    "error_code": event.error_code,
                    "details": event.details,
                },
            )
        ]

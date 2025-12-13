"""Protocol definitions for ConversationAgent mixins (P2 improvement).

This module defines structural typing contracts (Protocols) that mixins
expect from their host class (ConversationAgent). This replaces the use
of `Any` type hints in mixin host contracts, providing compile-time
type checking and better IDE support.

Design principles:
- Use typing.Protocol for structural subtyping (duck typing with type safety)
- Keep protocols minimal: only declare what each mixin actually needs
- Use TYPE_CHECKING guards to avoid circular imports
- Document the runtime expectations clearly

Created in: P1-6 P2 improvements (step A)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import asyncio

    from src.domain.services.context_manager import SessionContext


class EventBusProtocol(Protocol):
    """Minimal EventBus protocol for mixin type hints.

    This avoids importing the full EventBus class in mixin files,
    breaking potential circular dependencies.
    """

    def subscribe(self, event_type: type, handler: Any) -> None:
        """Subscribe to an event type."""
        ...

    def unsubscribe(self, event_type: type, handler: Any) -> None:
        """Unsubscribe from an event type."""
        ...

    def publish(self, event: Any) -> None:
        """Publish an event."""
        ...


class WorkflowHost(Protocol):
    """Host contract for ConversationAgentWorkflowMixin.

    Any class that uses ConversationAgentWorkflowMixin must provide:
    - llm: An LLM object with plan_workflow/decompose_to_nodes/replan_workflow methods
    - event_bus: Optional EventBus for publishing DecisionMadeEvent
    - session_context: SessionContext for decision recording
    - get_context_for_reasoning(): Returns reasoning context dict
    - _stage_decision_record(): Stages decision for batch commit (P0-2 Phase 2)
    - _flush_staged_state(): Flushes staged state updates (P0-2 Phase 2)

    This protocol ensures compile-time checking that the host class
    provides all required attributes and methods.
    """

    llm: Any  # LLM object with async plan_workflow/decompose_to_nodes/replan_workflow
    event_bus: EventBusProtocol | None
    session_context: SessionContext

    def get_context_for_reasoning(self) -> dict[str, Any]:
        """Get reasoning context for LLM calls.

        Returns:
            dict containing conversation history, goals, decision history, etc.
        """
        ...

    def _stage_decision_record(self, record: dict[str, Any]) -> None:
        """Stage decision record for batch commit (P0-2 Phase 2).

        Args:
            record: Decision record to stage
        """
        ...

    async def _flush_staged_state(self) -> None:
        """Flush staged state updates to session_context (P0-2 Phase 2)."""
        ...


class RecoveryHost(Protocol):
    """Host contract for ConversationAgentRecoveryMixin.

    Any class that uses ConversationAgentRecoveryMixin must provide:
    - llm: An LLM object with optional plan_error_recovery method
    - event_bus: Optional EventBus for subscribing to coordinator events
    - session_context: SessionContext for decision recording
    - _state_lock: asyncio.Lock for protecting pending_feedbacks
    - get_context_for_reasoning(): Returns reasoning context dict
    - _stage_decision_record(): Stages decision for batch commit
    - _flush_staged_state(): Flushes staged state updates

    Note: pending_feedbacks and _is_listening_feedbacks are initialized
    by the mixin itself via _init_recovery_mixin(), so they're not part
    of this protocol.

    This protocol ensures compile-time checking that the host class
    provides all required attributes and methods.
    """

    llm: Any  # LLM object with optional plan_error_recovery method
    event_bus: EventBusProtocol | None
    session_context: SessionContext
    _state_lock: asyncio.Lock

    def get_context_for_reasoning(self) -> dict[str, Any]:
        """Get reasoning context for LLM calls.

        Returns:
            dict containing conversation history, goals, decision history, etc.
        """
        ...

    def _stage_decision_record(self, record: dict[str, Any]) -> None:
        """Stage decision record for batch commit (P0-2 Phase 2).

        Args:
            record: Decision record to stage
        """
        ...

    async def _flush_staged_state(self) -> None:
        """Flush staged state updates to session_context (P0-2 Phase 2)."""
        ...

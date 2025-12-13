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

    async def publish(self, event: Any) -> None:
        """Publish an event (async)."""
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
    - pending_feedbacks: List of pending feedback items (initialized by mixin)
    - get_context_for_reasoning(): Returns reasoning context dict
    - _stage_decision_record(): Stages decision for batch commit
    - _flush_staged_state(): Flushes staged state updates

    Note: pending_feedbacks is initialized by the mixin via _init_recovery_mixin(),
    but it is part of the effective host surface and is used by get_context_for_reasoning().

    This protocol ensures compile-time checking that the host class
    provides all required attributes and methods.
    """

    llm: Any  # LLM object with optional plan_error_recovery method
    event_bus: EventBusProtocol | None
    session_context: SessionContext
    _state_lock: asyncio.Lock
    pending_feedbacks: list[dict[str, Any]]
    _is_listening_feedbacks: bool  # Initialized by mixin

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

    async def _handle_adjustment_event(self, event: Any) -> None:
        """Handle adjustment event from coordinator (internal)."""
        ...

    async def _handle_failure_handled_event(self, event: Any) -> None:
        """Handle failure handled event from coordinator (internal)."""
        ...


class ReActCoreHost(Protocol):
    """Host contract for ConversationAgentReActCoreMixin (P1-7 Phase 6).

    Any class that uses ConversationAgentReActCoreMixin must provide:
    - llm: LLM object with think/decide_action/should_continue methods
    - session_context: SessionContext for tracking and history
    - event_bus: Optional EventBus for publishing decision events
    - max_iterations: Maximum ReAct loop iterations
    - timeout_seconds: Optional timeout for loop (Phase 5)
    - max_tokens: Optional token limit (Phase 5)
    - max_cost: Optional cost limit (Phase 5)
    - coordinator: Optional coordinator for context/circuit breaker (Phase 1)
    - emitter: Optional emitter for streaming output (Phase 2)
    - _current_input: Current user input being processed
    - _coordinator_context: Cached coordinator context (Phase 1)
    - _decision_metadata: Decision metadata tracking
    - Helper methods: get_context_for_reasoning, _initialize_model_info, etc.
    - Staging methods: _stage_token_usage, _flush_staged_state (P0-2 Phase 2)

    This protocol ensures compile-time checking for ReAct core host requirements.
    """

    llm: Any
    session_context: SessionContext
    event_bus: EventBusProtocol | None
    max_iterations: int
    timeout_seconds: float | None
    max_tokens: int | None
    max_cost: float | None
    coordinator: Any | None
    _current_input: str | None
    emitter: Any | None
    _coordinator_context: Any | None
    _decision_metadata: list[dict[str, Any]]

    def get_context_for_reasoning(self) -> dict[str, Any]:
        """Build context dict for LLM calls."""
        ...

    def _initialize_model_info(self) -> None:
        """Initialize model context limits if not set."""
        ...

    def _log_coordinator_context(self, context: Any) -> None:
        """Log coordinator context information."""
        ...

    def _log_context_warning(self) -> None:
        """Log warning when approaching context limit."""
        ...

    def _stage_token_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Stage token usage for batch commit (P0-2 Phase 2)."""
        ...

    def _stage_decision_record(self, record: dict[str, Any]) -> None:
        """Stage decision record for batch commit (P0-2 Phase 2)."""
        ...

    async def _flush_staged_state(self) -> None:
        """Flush all staged state updates atomically (P0-2 Phase 2)."""
        ...

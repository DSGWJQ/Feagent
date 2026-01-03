from __future__ import annotations

import logging
from typing import Any, cast

from src.domain.services.conversation_flow_emitter import (
    ConversationStep,
    EmitterClosedError,
    StepKind,
)
from src.domain.services.event_bus import Event, EventBus
from src.interfaces.api.services.sse_emitter_handler import get_session_manager

logger = logging.getLogger(__name__)


def attach_event_bus_sse_bridge(event_bus: EventBus) -> None:
    """
    Attach a minimal EventBus -> SSE bridge for active ConversationFlowEmitter sessions.

    KISS: only forwards Coordinator allow/deny signals.
    Defensive: idempotent attach + emitter-closed tolerant.
    """

    if getattr(event_bus, "_sse_bridge_attached", False):
        return
    cast(Any, event_bus)._sse_bridge_attached = True

    from src.domain.services.decision_events import DecisionRejectedEvent, DecisionValidatedEvent

    async def _emit_step(session_id: str, step: ConversationStep) -> None:
        session_manager = get_session_manager()
        handler = await session_manager.get_session(session_id)
        if handler is None:
            return
        try:
            await handler.emitter.emit_step(step)
        except EmitterClosedError:
            return

    async def on_decision_validated(event: DecisionValidatedEvent) -> None:
        session_id = event.correlation_id
        if not session_id:
            return
        await _emit_step(
            session_id,
            ConversationStep(
                kind=StepKind.OBSERVATION,
                content="coordinator: allow",
                metadata={
                    "source": event.source,
                    "decision_type": event.decision_type,
                    "original_decision_id": event.original_decision_id,
                    "correlation_id": event.correlation_id,
                },
            ),
        )

    async def on_decision_rejected(event: DecisionRejectedEvent) -> None:
        session_id = event.correlation_id
        if not session_id:
            return
        session_manager = get_session_manager()
        handler = await session_manager.get_session(session_id)
        if handler is None:
            return
        try:
            reason = (event.reason or "").strip()
            if len(reason) > 300:
                reason = reason[:300] + "..."
            await handler.emitter.emit_error(
                error_message=reason or "coordinator: rejected",
                error_code="COORDINATOR_REJECTED",
                recoverable=False,
                decision_type=event.decision_type,
                original_decision_id=event.original_decision_id,
                correlation_id=event.correlation_id,
            )
            await handler.emitter.complete()
        except EmitterClosedError:
            return
        except Exception:  # best-effort bridge
            logger.exception("Failed to emit coordinator rejection to SSE: session=%s", session_id)

    async def _on_decision_validated(event: Event) -> None:
        if not isinstance(event, DecisionValidatedEvent):
            return
        await on_decision_validated(event)

    async def _on_decision_rejected(event: Event) -> None:
        if not isinstance(event, DecisionRejectedEvent):
            return
        await on_decision_rejected(event)

    event_bus.subscribe(DecisionValidatedEvent, _on_decision_validated)
    event_bus.subscribe(DecisionRejectedEvent, _on_decision_rejected)

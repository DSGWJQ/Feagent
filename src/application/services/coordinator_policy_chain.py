from __future__ import annotations

import logging
from typing import Any, Protocol

from src.domain.services.decision_events import DecisionRejectedEvent, DecisionValidatedEvent
from src.domain.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class CoordinatorPort(Protocol):
    def validate_decision(self, decision: dict[str, Any]) -> Any: ...


class CoordinatorRejectedError(RuntimeError):
    def __init__(
        self,
        *,
        decision_type: str,
        correlation_id: str,
        original_decision_id: str,
        errors: list[str],
    ) -> None:
        self.decision_type = decision_type
        self.correlation_id = correlation_id
        self.original_decision_id = original_decision_id
        self.errors = errors
        message = "; ".join(errors) or "coordinator rejected decision"
        super().__init__(message)


class CoordinatorPolicyChain:
    def __init__(
        self,
        *,
        coordinator: CoordinatorPort | None,
        event_bus: EventBus | None,
        source: str,
        fail_closed: bool = True,
        supervised_decision_types: set[str] | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._event_bus = event_bus
        self._source = source
        self._fail_closed = fail_closed
        self._dedupe_keys: set[tuple[str, str, str]] = set()
        self._supervised_decision_types = supervised_decision_types or {
            "api_request",
            "create_node",
            "file_operation",
            "human_interaction",
            "tool_call",
        }

    def is_supervised(self, decision_type: str) -> bool:
        return decision_type in self._supervised_decision_types

    async def enforce_action_or_raise(
        self,
        *,
        decision_type: str,
        decision: dict[str, Any],
        correlation_id: str,
        original_decision_id: str,
    ) -> None:
        if not self.is_supervised(decision_type):
            return

        key = (decision_type, correlation_id, original_decision_id)
        if key in self._dedupe_keys:
            return
        self._dedupe_keys.add(key)

        if self._coordinator is None or self._event_bus is None:
            if not self._fail_closed:
                return
            raise CoordinatorRejectedError(
                decision_type=decision_type,
                correlation_id=correlation_id,
                original_decision_id=original_decision_id,
                errors=["coordinator or event_bus not configured"],
            )

        validation = self._coordinator.validate_decision(decision)
        is_valid = bool(getattr(validation, "is_valid", False))
        errors = list(getattr(validation, "errors", []) or [])

        if is_valid:
            await self._event_bus.publish(
                DecisionValidatedEvent(
                    source=self._source,
                    correlation_id=correlation_id,
                    original_decision_id=original_decision_id,
                    decision_type=decision_type,
                    payload=decision,
                )
            )
            logger.info(
                "coordinator_allow",
                extra={
                    "decision_type": decision_type,
                    "original_decision_id": original_decision_id,
                    "correlation_id": correlation_id,
                },
            )
            return

        reason = "; ".join(errors) or "coordinator rejected decision"
        await self._event_bus.publish(
            DecisionRejectedEvent(
                source=self._source,
                correlation_id=correlation_id,
                original_decision_id=original_decision_id,
                decision_type=decision_type,
                reason=reason,
                errors=errors,
            )
        )
        logger.info(
            "coordinator_deny",
            extra={
                "decision_type": decision_type,
                "original_decision_id": original_decision_id,
                "correlation_id": correlation_id,
                "errors_count": len(errors),
            },
        )
        raise CoordinatorRejectedError(
            decision_type=decision_type,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
            errors=errors or [reason],
        )

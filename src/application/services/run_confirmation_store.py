"""RunConfirmationStore - in-memory confirm/allow/deny gate for side effects (PRD-030).

Design goals (KISS / fail-closed):
- Single-run single-pending confirmation (idempotent by run_id).
- Default decision is deny when confirmation cannot be obtained.
- In-memory only (MVP): persistence/retry is handled via RunEvents replay, not by this store.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import time
from typing import Literal
from uuid import uuid4

from src.domain.exceptions import DomainValidationError

Decision = Literal["allow", "deny"]


@dataclass(frozen=True, slots=True)
class PendingConfirmation:
    confirm_id: str
    run_id: str
    workflow_id: str
    node_id: str
    created_at_ms: int
    future: asyncio.Future[Decision]


class RunConfirmationStore:
    """In-memory confirmation store keyed by run_id/confirm_id."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pending_by_confirm_id: dict[str, PendingConfirmation] = {}
        self._confirm_id_by_run_id: dict[str, str] = {}

    async def create_or_get_pending(
        self,
        *,
        run_id: str,
        workflow_id: str,
        node_id: str,
    ) -> PendingConfirmation:
        run_id = (run_id or "").strip()
        if not run_id:
            raise DomainValidationError("run_id is required")

        workflow_id = (workflow_id or "").strip()
        if not workflow_id:
            raise DomainValidationError("workflow_id is required")

        node_id = (node_id or "").strip()
        if not node_id:
            raise DomainValidationError("node_id is required")

        async with self._lock:
            existing_id = self._confirm_id_by_run_id.get(run_id)
            if existing_id:
                existing = self._pending_by_confirm_id.get(existing_id)
                if existing and not existing.future.done():
                    return existing

            confirm_id = uuid4().hex
            future: asyncio.Future[Decision] = asyncio.get_running_loop().create_future()
            pending = PendingConfirmation(
                confirm_id=confirm_id,
                run_id=run_id,
                workflow_id=workflow_id,
                node_id=node_id,
                created_at_ms=int(time() * 1000),
                future=future,
            )
            self._pending_by_confirm_id[confirm_id] = pending
            self._confirm_id_by_run_id[run_id] = confirm_id
            return pending

    async def resolve(
        self,
        *,
        run_id: str,
        confirm_id: str,
        decision: Decision,
    ) -> None:
        run_id = (run_id or "").strip()
        confirm_id = (confirm_id or "").strip()

        if not run_id:
            raise DomainValidationError("run_id is required")
        if not confirm_id:
            raise DomainValidationError("confirm_id is required")
        if decision not in {"allow", "deny"}:
            raise DomainValidationError("decision must be 'allow' or 'deny'")

        async with self._lock:
            pending = self._pending_by_confirm_id.get(confirm_id)
            if pending is None:
                raise DomainValidationError("confirmation not found (may be expired)")
            if pending.run_id != run_id:
                raise DomainValidationError("confirm_id does not belong to this run_id")
            if pending.future.done():
                return
            pending.future.set_result(decision)

    async def wait_for_decision(
        self,
        *,
        confirm_id: str,
        timeout_s: float,
    ) -> Decision:
        confirm_id = (confirm_id or "").strip()
        if not confirm_id:
            raise DomainValidationError("confirm_id is required")

        pending: PendingConfirmation | None
        async with self._lock:
            pending = self._pending_by_confirm_id.get(confirm_id)

        if pending is None:
            raise DomainValidationError("confirmation not found (may be expired)")

        try:
            return await asyncio.wait_for(pending.future, timeout=timeout_s)
        finally:
            await self._cleanup(confirm_id=confirm_id)

    async def _cleanup(self, *, confirm_id: str) -> None:
        async with self._lock:
            pending = self._pending_by_confirm_id.pop(confirm_id, None)
            if pending is None:
                return
            current = self._confirm_id_by_run_id.get(pending.run_id)
            if current == confirm_id:
                self._confirm_id_by_run_id.pop(pending.run_id, None)


run_confirmation_store = RunConfirmationStore()

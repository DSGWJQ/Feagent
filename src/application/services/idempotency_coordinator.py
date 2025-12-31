"""IdempotencyCoordinator - Application-level idempotency + concurrency control.

Implements per-idempotency-key in-flight de-duplication using stdlib asyncio primitives
and persists successful results via the IdempotencyStore Domain Port.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from src.domain.ports.idempotency_store import IdempotencyStore


class IdempotencyNotReadyError(RuntimeError):
    """Raised when idempotency is requested but cannot be served."""


class IdempotencyCoordinator:
    def __init__(self, *, store: IdempotencyStore) -> None:
        self._store = store
        self._guard = asyncio.Lock()
        self._in_flight: dict[str, asyncio.Task[Any]] = {}

    async def run(
        self,
        *,
        idempotency_key: str,
        work: Callable[[], Awaitable[Any]],
    ) -> Any:
        if await self._store.exists(idempotency_key):
            return await self._store.get_result(idempotency_key)

        async with self._guard:
            if await self._store.exists(idempotency_key):
                return await self._store.get_result(idempotency_key)

            task = self._in_flight.get(idempotency_key)
            if task is None:
                task = asyncio.create_task(self._run_and_persist(idempotency_key, work))
                self._in_flight[idempotency_key] = task

        return await asyncio.shield(task)

    async def _run_and_persist(
        self,
        idempotency_key: str,
        work: Callable[[], Awaitable[Any]],
    ) -> Any:
        try:
            result = await work()
            await self._store.save_result(idempotency_key, result)
            return result
        finally:
            async with self._guard:
                self._in_flight.pop(idempotency_key, None)

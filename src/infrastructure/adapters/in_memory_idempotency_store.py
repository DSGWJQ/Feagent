"""In-memory IdempotencyStore adapter (Infrastructure)."""

from __future__ import annotations

import asyncio
from typing import Any

from src.domain.ports.idempotency_store import IdempotencyStore


class InMemoryIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def exists(self, idempotency_key: str) -> bool:
        async with self._lock:
            return idempotency_key in self._data

    async def get_result(self, idempotency_key: str) -> Any:
        async with self._lock:
            return self._data[idempotency_key]

    async def save_result(self, idempotency_key: str, result: Any) -> None:
        async with self._lock:
            self._data[idempotency_key] = result

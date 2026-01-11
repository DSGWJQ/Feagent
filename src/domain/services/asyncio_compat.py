"""Asyncio helpers for sync entrypoints.

This module provides a small compatibility layer for code paths that expose
sync wrappers around async implementations (tests/scripts/legacy callers).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
from typing import Any, TypeVar, cast

T = TypeVar("T")


def run_sync(awaitable: Awaitable[T]) -> T:
    """Run an awaitable from synchronous code.

    Defensive behavior:
    - If no loop is running in the current thread, use `asyncio.run`.
    - If a loop is already running in the current thread, fail fast with a
      clear error (calling sync wrappers from async contexts is a bug).
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(cast(Coroutine[Any, Any, T], awaitable))

    raise RuntimeError("run_sync() cannot be called from a running event loop")

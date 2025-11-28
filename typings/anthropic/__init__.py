from __future__ import annotations

from typing import Any


class _Messages:
    async def create(self, *args: Any, **kwargs: Any) -> Any: ...


class AsyncAnthropic:
    def __init__(self, api_key: str | None = None) -> None: ...

    @property
    def messages(self) -> _Messages: ...

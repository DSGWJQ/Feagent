"""RunEventRepository Port - 定义 RunEvent 的持久化接口

KISS：当前仅提供 append（写入事件流），以满足 Run 事件落库与回放基础能力。
"""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.run_event import RunEvent


class RunEventRepository(Protocol):
    def append(self, event: RunEvent) -> RunEvent: ...

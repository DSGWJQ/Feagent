"""ExecutionEventSink Port（执行事件输出端口）

Domain 层端口：将执行过程中的事件输出到外部（SSE/DB/日志等）。

约束：
- 只能依赖标准库与 Domain 层类型
- 事件结构保持宽松，具体序列化/传输由 Infrastructure 负责
"""

from __future__ import annotations

from typing import Any, Protocol


class ExecutionEventSink(Protocol):
    """执行事件输出端口。"""

    async def publish(self, event: Any) -> None:
        """发布执行事件。"""
        ...

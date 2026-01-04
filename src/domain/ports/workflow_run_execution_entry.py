"""WorkflowRunExecutionEntry Port（Run 级权威执行编排入口）

Domain 层端口：用于统一 REST execute/stream 与 WorkflowAgent execute_workflow 的执行语义。

约束：
- Domain 仅依赖该 Protocol，不依赖 Application/Infrastructure 具体实现
- 具体的 run 门禁 / 事件落库 / 状态机 驱动由 Application 实现
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Mapping
from typing import Any, Protocol


class WorkflowRunExecutionEntryPort(Protocol):
    async def prepare(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
    ) -> None: ...

    def stream_after_gate(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
        record_execution_events: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    def execute_streaming(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
        record_execution_events: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    async def execute_with_results(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
        record_execution_events: bool = False,
    ) -> dict[str, Any]: ...

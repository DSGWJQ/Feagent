"""PRD-040: WorkflowRunExecutionEntry ReAct-style repair loop (unit).

This verifies:
- workflow_error is suppressed for intermediate attempts (failures become workflow_attempt_failed).
- config-only patch is applied (e.g., timeout) and the kernel is retried.
- stop conditions emit workflow_termination_report and a final workflow_error.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.application.services.run_confirmation_store import run_confirmation_store
from src.application.services.workflow_run_execution_entry import WorkflowRunExecutionEntry
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.tool import Tool
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus


class _KernelTimeoutThenSuccess:
    def __init__(self, *, failing_node_id: str) -> None:
        self._calls = 0
        self._failing_node_id = failing_node_id

    async def stream_after_gate(self, *, workflow_id: str, input_data=None, **_kwargs):
        self._calls += 1
        yield {"type": "workflow_start", "workflow_id": workflow_id}
        if self._calls == 1:
            yield {
                "type": "node_error",
                "node_id": self._failing_node_id,
                "node_type": "transform",
                "error_type": "timeout",
                "retryable": True,
                "error": "simulated timeout",
            }
            yield {"type": "workflow_error", "error": "attempt_failed"}
            return

        yield {"type": "workflow_complete", "result": {"ok": True}}


class _KernelAlwaysTimeout:
    def __init__(self, *, failing_node_id: str) -> None:
        self._calls = 0
        self._failing_node_id = failing_node_id

    async def stream_after_gate(self, *, workflow_id: str, input_data=None, **_kwargs):
        self._calls += 1
        yield {"type": "workflow_start", "workflow_id": workflow_id}
        yield {
            "type": "node_error",
            "node_id": self._failing_node_id,
            "node_type": "transform",
            "error_type": "timeout",
            "retryable": True,
            "error": f"simulated timeout (attempt={self._calls})",
        }
        yield {"type": "workflow_error", "error": "attempt_failed"}


class _KernelToolNotFoundThenSuccess:
    def __init__(self, *, failing_node_id: str) -> None:
        self._calls = 0
        self._failing_node_id = failing_node_id

    async def stream_after_gate(self, *, workflow_id: str, input_data=None, **_kwargs):
        self._calls += 1
        yield {"type": "workflow_start", "workflow_id": workflow_id}
        if self._calls == 1:
            yield {
                "type": "node_error",
                "node_id": self._failing_node_id,
                "node_type": "tool",
                "error_type": "tool_not_found",
                "retryable": False,
                "error": "simulated tool not found",
            }
            yield {"type": "workflow_error", "error": "attempt_failed"}
            return
        yield {"type": "workflow_complete", "result": {"ok": True}}


@pytest.mark.asyncio
async def test_react_loop_applies_timeout_patch_and_retries() -> None:
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    transform = Node.create(
        type=NodeType.TRANSFORM, name="xform", config={}, position=Position(x=1, y=0)
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=2, y=0))
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, transform, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=transform.id),
            Edge.create(source_node_id=transform.id, target_node_id=end.id),
        ],
    )

    workflow_repo = MagicMock()
    workflow_repo.get_by_id.return_value = workflow

    run_repo = MagicMock()
    save_validator = MagicMock()
    run_event_use_case = MagicMock()

    entry = WorkflowRunExecutionEntry(
        workflow_repository=workflow_repo,
        run_repository=run_repo,
        save_validator=save_validator,
        run_event_use_case=run_event_use_case,
        kernel=_KernelTimeoutThenSuccess(failing_node_id=transform.id),
        executor_id="executor_test",
    )

    events: list[dict] = []
    async for e in entry.stream_after_gate(workflow_id=workflow.id, run_id="run_1"):
        events.append(e)

    assert any(e.get("type") == "workflow_react_loop_started" for e in events)
    assert any(e.get("type") == "workflow_attempt_failed" for e in events)
    assert any(e.get("type") == "workflow_react_patch_applied" for e in events)
    assert events[-1]["type"] == "workflow_complete"
    assert all(e.get("type") != "workflow_error" for e in events)

    workflow_repo.save.assert_called()
    assert float(transform.config.get("timeout")) >= 60.0


@pytest.mark.asyncio
async def test_react_loop_can_patch_tool_not_found_by_switching_tool_id() -> None:
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    tool_node = Node.create(
        type=NodeType.TOOL,
        name="tool",
        config={"tool_id": "tool_missing"},
        position=Position(x=1, y=0),
    )
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, tool_node],
        edges=[Edge.create(source_node_id=start.id, target_node_id=tool_node.id)],
    )

    fallback_tool = Tool(
        id="tool_ok",
        name="noop_tool",
        description="fallback noop tool",
        category=ToolCategory.CUSTOM,
        status=ToolStatus.PUBLISHED,
        version="1.0.0",
        implementation_type="builtin",
        implementation_config={"handler": "noop"},
    )

    tool_repo = MagicMock()
    tool_repo.find_published.return_value = [fallback_tool]

    workflow_repo = MagicMock()
    workflow_repo.get_by_id.return_value = workflow

    run_repo = MagicMock()
    save_validator = MagicMock()
    save_validator.tool_repository = tool_repo
    run_event_use_case = MagicMock()

    entry = WorkflowRunExecutionEntry(
        workflow_repository=workflow_repo,
        run_repository=run_repo,
        save_validator=save_validator,
        run_event_use_case=run_event_use_case,
        kernel=_KernelToolNotFoundThenSuccess(failing_node_id=tool_node.id),
        executor_id="executor_test",
    )

    gen = entry.stream_after_gate(workflow_id=workflow.id, run_id="run_1")
    confirm_required = await anext(gen)
    assert confirm_required["type"] == "workflow_confirm_required"
    await run_confirmation_store.resolve(
        run_id="run_1",
        confirm_id=confirm_required["confirm_id"],
        decision="allow",
    )
    confirmed = await anext(gen)
    assert confirmed["type"] == "workflow_confirmed"

    rest: list[dict] = []
    async for e in gen:
        rest.append(e)

    assert any(e.get("type") == "workflow_react_patch_applied" for e in rest)
    assert rest[-1]["type"] == "workflow_complete"
    assert all(e.get("type") != "workflow_error" for e in rest)
    workflow_repo.save.assert_called()
    assert tool_node.config.get("tool_id") == "tool_ok"


@pytest.mark.asyncio
async def test_react_loop_emits_termination_report_on_max_attempts() -> None:
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    transform = Node.create(
        type=NodeType.TRANSFORM, name="xform", config={}, position=Position(x=1, y=0)
    )
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, transform],
        edges=[Edge.create(source_node_id=start.id, target_node_id=transform.id)],
    )

    workflow_repo = MagicMock()
    workflow_repo.get_by_id.return_value = workflow

    run_repo = MagicMock()
    save_validator = MagicMock()
    run_event_use_case = MagicMock()

    entry = WorkflowRunExecutionEntry(
        workflow_repository=workflow_repo,
        run_repository=run_repo,
        save_validator=save_validator,
        run_event_use_case=run_event_use_case,
        kernel=_KernelAlwaysTimeout(failing_node_id=transform.id),
        executor_id="executor_test",
    )

    last = None
    report = None
    async for e in entry.stream_after_gate(workflow_id=workflow.id, run_id="run_1"):
        last = e
        if e.get("type") == "workflow_termination_report":
            report = e

    assert report is not None
    assert report["stop_reason"] == "consecutive_failures"
    assert report["attempts_total"] == 3
    assert last is not None
    assert last["type"] == "workflow_error"
    assert last.get("attempt") == 3

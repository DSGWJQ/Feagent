"""PRD-030: WorkflowRunExecutionEntry confirm gate (unit).

This verifies:
- Side-effect workflows emit workflow_confirm_required before executing the kernel.
- allow resumes execution and emits workflow_confirmed.
- deny terminates with workflow_error (fail-closed).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.application.services.run_confirmation_store import run_confirmation_store
from src.application.services.workflow_run_execution_entry import WorkflowRunExecutionEntry
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class _Kernel:
    async def stream_after_gate(self, *, workflow_id: str, input_data=None, **_kwargs):
        yield {"type": "workflow_complete", "result": {"ok": True}}


@pytest.mark.asyncio
async def test_confirm_gate_allow_resumes_kernel_stream() -> None:
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(type=NodeType.HTTP, name="http", config={}, position=Position(x=1, y=0))
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http],
        edges=[Edge.create(source_node_id=start.id, target_node_id=http.id)],
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
        kernel=_Kernel(),
        executor_id="executor_test",
    )

    gen = entry.stream_after_gate(workflow_id="wf_1", run_id="run_1")

    first = await anext(gen)
    assert first["type"] == "workflow_confirm_required"
    assert first["run_id"] == "run_1"
    assert first["confirm_id"]
    assert first["default_decision"] == "deny"

    await run_confirmation_store.resolve(
        run_id="run_1",
        confirm_id=first["confirm_id"],
        decision="allow",
    )

    second = await anext(gen)
    assert second["type"] == "workflow_confirmed"
    assert second["decision"] == "allow"

    third = await anext(gen)
    assert third["type"] == "workflow_complete"


@pytest.mark.asyncio
async def test_confirm_gate_deny_terminates_fail_closed() -> None:
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[
            Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0)),
            Node.create(type=NodeType.TOOL, name="tool", config={}, position=Position(x=1, y=0)),
        ],
        edges=[],
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
        kernel=_Kernel(),
        executor_id="executor_test",
    )

    gen = entry.stream_after_gate(workflow_id="wf_1", run_id="run_1")
    first = await anext(gen)
    await run_confirmation_store.resolve(
        run_id="run_1",
        confirm_id=first["confirm_id"],
        decision="deny",
    )

    _confirmed = await anext(gen)
    denied = await anext(gen)
    assert denied["type"] == "workflow_error"
    assert denied["error"] == "side_effect_confirm_denied"

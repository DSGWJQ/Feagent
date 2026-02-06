from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.events.workflow_execution_events import NodeExecutionEvent
from src.domain.exceptions import DomainError
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors import create_executor_registry


@pytest.mark.asyncio
async def test_loop_for_each_empty_collection_returns_empty_list():
    """P1: for_each 空集合应成功执行并返回空列表（而不是抛错/返回 None）。"""

    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    loop = Node.create(
        type=NodeType.LOOP,
        name="loop",
        config={"type": "for_each", "array": "items"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="loop_empty_collection",
        description="",
        nodes=[start, loop, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=loop.id),
            Edge.create(source_node_id=loop.id, target_node_id=end.id),
        ],
    )

    executor = WorkflowExecutor(executor_registry=create_executor_registry())
    result = await executor.execute(workflow, initial_input={"items": []})

    assert result == []
    loop_log = next(row for row in executor.execution_log if row["node_id"] == loop.id)
    assert loop_log["output"] == []


@pytest.mark.asyncio
async def test_file_read_missing_file_emits_node_error_event():
    """P1: file.read 文件不存在时必须失败且可定位到节点与原因。"""

    # CI/sandbox environments may not allow writing into OS temp dirs (tmp_path fixture).
    # Use a guaranteed-missing workspace-relative path instead.
    missing_path = Path("tmp") / "__pytest__" / f"missing_{uuid.uuid4().hex}.txt"
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    file_node = Node.create(
        type=NodeType.FILE,
        name="file",
        config={"operation": "read", "path": str(missing_path), "encoding": "utf-8"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="file_read_missing",
        description="",
        nodes=[start, file_node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=file_node.id),
            Edge.create(source_node_id=file_node.id, target_node_id=end.id),
        ],
    )

    event_bus = EventBus()
    captured: list[NodeExecutionEvent] = []

    async def _on_event(event):  # pragma: no cover - type asserted below
        if isinstance(event, NodeExecutionEvent):
            captured.append(event)

    event_bus.subscribe(NodeExecutionEvent, _on_event)

    executor = WorkflowExecutor(executor_registry=create_executor_registry(), event_bus=event_bus)

    with pytest.raises(DomainError) as exc:
        await executor.execute(
            workflow, initial_input={"unused": True}, correlation_id="it_file_missing"
        )

    assert "文件不存在" in str(exc.value)
    assert missing_path.name in str(exc.value)

    node_errors = [e for e in captured if e.status == "failed" and e.node_id == file_node.id]
    assert node_errors, captured
    assert node_errors[0].node_type == NodeType.FILE.value
    assert "文件不存在" in str(node_errors[0].error)
    assert missing_path.name in str(node_errors[0].error)

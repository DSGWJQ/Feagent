from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
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

    events: list[dict[str, object]] = []

    def _event_callback(event_type: str, payload: dict[str, object]) -> None:
        events.append({"type": event_type, **payload})

    executor = WorkflowExecutor(executor_registry=create_executor_registry())
    executor.set_event_callback(_event_callback)

    with pytest.raises(DomainError) as exc:
        await executor.execute(workflow, initial_input={"unused": True})

    assert "文件不存在" in str(exc.value)
    assert missing_path.name in str(exc.value)

    node_errors = [e for e in events if e.get("type") == "node_error"]
    assert node_errors, events
    assert node_errors[0].get("node_id") == file_node.id
    assert node_errors[0].get("node_type") == NodeType.FILE.value
    assert "文件不存在" in str(node_errors[0].get("error"))
    assert missing_path.name in str(node_errors[0].get("error"))

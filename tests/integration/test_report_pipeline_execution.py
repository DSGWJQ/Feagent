from __future__ import annotations

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors.base_executor import EndExecutor, StartExecutor
from src.infrastructure.executors.database_executor import DatabaseExecutor
from src.infrastructure.executors.file_executor import FileExecutor
from src.infrastructure.executors.llm_executor import LlmExecutor
from src.infrastructure.executors.python_executor import PythonExecutor
from src.infrastructure.executors.transform_executor import TransformExecutor


@pytest.mark.asyncio
async def test_report_pipeline_executes_and_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("E2E_TEST_MODE", "deterministic")

    db_path = tmp_path / "db.sqlite3"
    db_url = f"sqlite:///{db_path}"

    out_path = tmp_path / "report.txt"

    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    db = Node.create(
        type=NodeType.DATABASE,
        name="db",
        config={"database_url": db_url, "sql": "SELECT 1 as value", "params": {}},
        position=Position(x=100, y=0),
    )
    transform = Node.create(
        type=NodeType.TRANSFORM,
        name="transform",
        config={"type": "field_mapping", "mapping": {"data": "input1"}},
        position=Position(x=200, y=0),
    )
    python_node = Node.create(
        type=NodeType.PYTHON,
        name="python",
        config={
            "code": """
payload = input1
rows = payload.get("data") if payload.__class__ is dict else payload
if rows.__class__ is not list:
    rows = []
result = {"count": len(rows), "value": rows[0]["value"] if rows and rows[0].__class__ is dict else None}
""".strip("\n")
        },
        position=Position(x=300, y=0),
    )
    llm = Node.create(
        type=NodeType.TEXT_MODEL,
        name="llm",
        config={"model": "openai/gpt-5", "prompt": "count={input1.count}"},
        position=Position(x=400, y=0),
    )
    file_node = Node.create(
        type=NodeType.FILE,
        name="file",
        config={
            "operation": "write",
            "path": str(out_path),
            "encoding": "utf-8",
            "content": "{input1}",
        },
        position=Position(x=500, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=600, y=0))

    workflow = Workflow.create(
        name="report_pipeline",
        description="",
        nodes=[start, db, transform, python_node, llm, file_node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=db.id),
            Edge.create(source_node_id=db.id, target_node_id=transform.id),
            Edge.create(source_node_id=transform.id, target_node_id=python_node.id),
            Edge.create(source_node_id=python_node.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=file_node.id),
            Edge.create(source_node_id=file_node.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.START.value, StartExecutor())
    registry.register(NodeType.END.value, EndExecutor())
    registry.register(NodeType.DATABASE.value, DatabaseExecutor())
    registry.register(NodeType.TRANSFORM.value, TransformExecutor())
    registry.register(NodeType.PYTHON.value, PythonExecutor())
    registry.register(NodeType.TEXT_MODEL.value, LlmExecutor(api_key=None))
    registry.register(NodeType.FILE.value, FileExecutor())

    executor = WorkflowExecutor(executor_registry=registry)
    result = await executor.execute(workflow, initial_input={"unused": True})

    assert isinstance(result, dict)
    assert result.get("operation") == "write"
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "deterministic stub" in content
    assert "count=1" in content

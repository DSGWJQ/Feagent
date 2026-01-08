from __future__ import annotations

from typing import Any

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutor, NodeExecutorRegistry
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class _ReturnValueExecutor(NodeExecutor):
    def __init__(self, value: Any):
        self._value = value

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        return self._value


class _CaptureConfigExecutor(NodeExecutor):
    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        return node.config


@pytest.mark.asyncio
async def test_engine_renders_config_placeholders_from_inputs_initial_input_and_context():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    transform = Node.create(
        type=NodeType.TRANSFORM,
        name="transform",
        config={},
        position=Position(x=50, y=0),
    )
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={
            "url": "https://example.test/{input1.userId}?region={initial_input.region}",
            "headers": (
                '{"X-Region":"{context.initial_input.region}",'
                '"X-Item":"{input1.items[0].id}",'
                '"X-Missing":"{input1.missing}"}'
            ),
            "payload": {
                "ids": ["{input1.userId}", "{input1.items[0].id}"],
            },
        },
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, transform, http, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=transform.id),
            Edge.create(source_node_id=transform.id, target_node_id=http.id),
            Edge.create(source_node_id=http.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(
        NodeType.TRANSFORM.value, _ReturnValueExecutor({"userId": 42, "items": [{"id": "abc"}]})
    )
    registry.register(NodeType.HTTP_REQUEST.value, _CaptureConfigExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"region": "cn"})
    assert result["url"] == "https://example.test/42?region=cn"
    assert '"X-Region":"cn"' in result["headers"]
    assert '"X-Item":"abc"' in result["headers"]
    assert "{input1.missing}" in result["headers"]
    assert result["payload"]["ids"] == ["42", "abc"]


@pytest.mark.asyncio
async def test_engine_keeps_config_values_without_placeholders():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={"url": "https://example.test/plain", "method": "GET"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=http.id),
            Edge.create(source_node_id=http.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.HTTP_REQUEST.value, _CaptureConfigExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    assert result["url"] == "https://example.test/plain"


@pytest.mark.asyncio
async def test_engine_renders_file_config_templates():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    transform = Node.create(
        type=NodeType.TRANSFORM,
        name="transform",
        config={},
        position=Position(x=50, y=0),
    )
    file_node = Node.create(
        type=NodeType.FILE,
        name="file",
        config={
            "operation": "write",
            "path": "tmp/{input1.userId}.txt",
            "content": "hello {input1.userId}",
        },
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, transform, file_node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=transform.id),
            Edge.create(source_node_id=transform.id, target_node_id=file_node.id),
            Edge.create(source_node_id=file_node.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.TRANSFORM.value, _ReturnValueExecutor({"userId": 7}))
    registry.register(NodeType.FILE.value, _CaptureConfigExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    assert result["path"] == "tmp/7.txt"
    assert result["content"] == "hello 7"


@pytest.mark.asyncio
async def test_engine_renders_database_sql_and_params_templates():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    transform = Node.create(
        type=NodeType.TRANSFORM,
        name="transform",
        config={},
        position=Position(x=50, y=0),
    )
    db_node = Node.create(
        type=NodeType.DATABASE,
        name="db",
        config={
            "database_url": "sqlite:///agent_data.db",
            "sql": "select * from users where id = {input1.userId}",
            "params": ["{input1.userId}"],
        },
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, transform, db_node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=transform.id),
            Edge.create(source_node_id=transform.id, target_node_id=db_node.id),
            Edge.create(source_node_id=db_node.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.TRANSFORM.value, _ReturnValueExecutor({"userId": 99}))
    registry.register(NodeType.DATABASE.value, _CaptureConfigExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    assert result["sql"] == "select * from users where id = 99"
    assert result["params"] == ["99"]

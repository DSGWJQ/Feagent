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


class _EchoInputsExecutor(NodeExecutor):
    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        return {"inputs": inputs}


@pytest.mark.asyncio
async def test_edge_condition_none_is_unconditional_pass():
    source = Node.create(
        type=NodeType.PYTHON,
        name="source",
        config={},
        position=Position(x=0, y=0),
    )
    target = Node.create(
        type=NodeType.TRANSFORM,
        name="target",
        config={},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[source, target, end],
        edges=[
            Edge.create(source_node_id=source.id, target_node_id=target.id, condition=None),
            Edge.create(source_node_id=target.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.PYTHON.value, _ReturnValueExecutor({"value": 1}))
    registry.register(NodeType.TRANSFORM.value, _EchoInputsExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    assert result["inputs"][source.id] == {"value": 1}


@pytest.mark.asyncio
async def test_edge_condition_empty_string_is_unconditional_pass():
    source = Node.create(
        type=NodeType.PYTHON,
        name="source",
        config={},
        position=Position(x=0, y=0),
    )
    target = Node.create(
        type=NodeType.TRANSFORM,
        name="target",
        config={},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[source, target, end],
        edges=[
            Edge.create(source_node_id=source.id, target_node_id=target.id, condition=""),
            Edge.create(source_node_id=target.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.PYTHON.value, _ReturnValueExecutor({"value": 2}))
    registry.register(NodeType.TRANSFORM.value, _EchoInputsExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    assert result["inputs"][source.id] == {"value": 2}


@pytest.mark.asyncio
async def test_edge_condition_eval_error_fail_closed_skips_target_node():
    source = Node.create(
        type=NodeType.PYTHON,
        name="source",
        config={},
        position=Position(x=0, y=0),
    )
    target = Node.create(
        type=NodeType.TRANSFORM,
        name="target",
        config={},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[source, target, end],
        edges=[
            Edge.create(source_node_id=source.id, target_node_id=target.id, condition="value ==="),
            Edge.create(source_node_id=target.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.PYTHON.value, _ReturnValueExecutor({"value": "x"}))
    registry.register(NodeType.TRANSFORM.value, _EchoInputsExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    executed_ids = [row["node_id"] for row in executor.execution_log]
    assert target.id not in executed_ids
    assert end.id not in executed_ids
    assert result is None


@pytest.mark.asyncio
async def test_multi_incoming_edges_or_join_and_input_filtering():
    node_true = Node.create(
        type=NodeType.PYTHON,
        name="true_branch",
        config={},
        position=Position(x=0, y=-50),
    )
    node_false = Node.create(
        type=NodeType.JAVASCRIPT,
        name="false_branch",
        config={},
        position=Position(x=0, y=50),
    )
    join = Node.create(
        type=NodeType.TRANSFORM,
        name="join",
        config={},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[node_true, node_false, join, end],
        edges=[
            Edge.create(source_node_id=node_true.id, target_node_id=join.id, condition="true"),
            Edge.create(source_node_id=node_false.id, target_node_id=join.id, condition="true"),
            Edge.create(source_node_id=join.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(
        NodeType.PYTHON.value, _ReturnValueExecutor({"branch": "true", "result": True})
    )
    registry.register(
        NodeType.JAVASCRIPT.value, _ReturnValueExecutor({"branch": "false", "result": False})
    )
    registry.register(NodeType.TRANSFORM.value, _EchoInputsExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    assert set(result["inputs"]) == {node_true.id}
    assert result["inputs"][node_true.id]["branch"] == "true"


@pytest.mark.asyncio
async def test_edge_condition_supports_len_function_in_advanced_mode():
    source = Node.create(
        type=NodeType.PYTHON,
        name="source",
        config={},
        position=Position(x=0, y=0),
    )
    target = Node.create(
        type=NodeType.TRANSFORM,
        name="target",
        config={},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[source, target, end],
        edges=[
            Edge.create(
                source_node_id=source.id,
                target_node_id=target.id,
                condition="len(high_value_orders) > 0",
            ),
            Edge.create(source_node_id=target.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(
        NodeType.PYTHON.value,
        _ReturnValueExecutor({"high_value_orders": [{"id": "o-1"}], "regular_orders": []}),
    )
    registry.register(NodeType.TRANSFORM.value, _EchoInputsExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})
    assert result["inputs"][source.id]["high_value_orders"][0]["id"] == "o-1"

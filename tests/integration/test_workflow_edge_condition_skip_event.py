import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors import create_executor_registry


@pytest.mark.asyncio
async def test_edge_condition_skips_node_and_emits_node_skipped_event_integration():
    node_start = Node.create(
        type=NodeType.START,
        name="start",
        config={},
        position=Position(x=0, y=0),
    )
    node_a = Node.create(
        type=NodeType.PYTHON,
        name="produce",
        config={"code": "result = {'x': 1}"},
        position=Position(x=100, y=0),
    )
    node_skipped = Node.create(
        type=NodeType.PYTHON,
        name="skipped",
        config={"code": "result = {'y': 2}"},
        position=Position(x=200, y=0),
    )
    node_end = Node.create(
        type=NodeType.END,
        name="end",
        config={},
        position=Position(x=300, y=0),
    )

    edges = [
        Edge.create(source_node_id=node_start.id, target_node_id=node_a.id),
        Edge.create(source_node_id=node_a.id, target_node_id=node_skipped.id, condition="false"),
        Edge.create(source_node_id=node_a.id, target_node_id=node_end.id),
        Edge.create(source_node_id=node_skipped.id, target_node_id=node_end.id),
    ]

    workflow = Workflow.create(
        name="edge_condition_skip_event",
        description="",
        nodes=[node_start, node_a, node_skipped, node_end],
        edges=edges,
    )

    registry = create_executor_registry(openai_api_key=None, anthropic_api_key=None)
    executor = WorkflowExecutor(executor_registry=registry)

    events: list[dict] = []

    def event_callback(event_type: str, data: dict) -> None:
        events.append({"type": event_type, **data})

    executor.set_event_callback(event_callback)

    result = await executor.execute(workflow, initial_input={})
    assert result == {"x": 1}

    executed = {row["node_id"] for row in executor.execution_log}
    assert node_skipped.id not in executed

    skipped_events = [
        event
        for event in events
        if event.get("type") == "node_skipped" and event.get("node_id") == node_skipped.id
    ]
    assert skipped_events

    payload = skipped_events[0]
    assert payload.get("reason") == "incoming_edge_conditions_not_met"
    conditions = payload.get("incoming_edge_conditions")
    assert isinstance(conditions, list) and conditions
    assert any(
        c.get("expression") == "false" and c.get("normalized") == "False" for c in conditions
    )

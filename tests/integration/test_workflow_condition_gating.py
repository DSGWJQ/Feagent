import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors import create_executor_registry


@pytest.mark.asyncio
async def test_condition_gating_executes_only_the_selected_branch_integration():
    node_start = Node.create(
        type=NodeType.START,
        name="start",
        config={},
        position=Position(x=0, y=0),
    )
    node_cond = Node.create(
        type=NodeType.CONDITIONAL,
        name="if",
        config={"condition": "input1 == 'test'"},
        position=Position(x=100, y=0),
    )
    node_true = Node.create(
        type=NodeType.JAVASCRIPT,
        name="true_branch",
        config={"code": "result = 'A'"},
        position=Position(x=200, y=-50),
    )
    node_false = Node.create(
        type=NodeType.JAVASCRIPT,
        name="false_branch",
        config={"code": "result = 'B'"},
        position=Position(x=200, y=50),
    )
    node_end = Node.create(
        type=NodeType.END,
        name="end",
        config={},
        position=Position(x=300, y=0),
    )

    edges = [
        Edge.create(source_node_id=node_start.id, target_node_id=node_cond.id),
        Edge.create(source_node_id=node_cond.id, target_node_id=node_true.id, condition="true"),
        Edge.create(source_node_id=node_cond.id, target_node_id=node_false.id, condition="false"),
        Edge.create(source_node_id=node_true.id, target_node_id=node_end.id),
        Edge.create(source_node_id=node_false.id, target_node_id=node_end.id),
    ]

    workflow = Workflow.create(
        name="condition_gating_integration",
        description="",
        nodes=[node_start, node_cond, node_true, node_false, node_end],
        edges=edges,
    )

    registry = create_executor_registry(openai_api_key=None, anthropic_api_key=None)
    executor = WorkflowExecutor(executor_registry=registry)

    result_true = await executor.execute(workflow, initial_input="test")
    assert result_true == "A"
    executed_true = [row["node_id"] for row in executor.execution_log]
    assert node_false.id not in executed_true

    result_false = await executor.execute(workflow, initial_input="nope")
    assert result_false == "B"
    executed_false = [row["node_id"] for row in executor.execution_log]
    assert node_true.id not in executed_false

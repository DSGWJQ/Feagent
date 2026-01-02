from __future__ import annotations

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.workflow_engine import WorkflowEngine, topological_sort_ids
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


def test_topological_sort_ids_detects_cycle() -> None:
    with pytest.raises(DomainError, match="工作流包含环"):
        topological_sort_ids(node_ids=["a", "b"], edges=[("a", "b"), ("b", "a")])


@pytest.mark.asyncio
async def test_execute_raises_when_missing_executor_registry() -> None:
    node1 = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node2 = Node.create(
        type=NodeType.HTTP, name="HTTP 请求", config={}, position=Position(x=100, y=0)
    )
    node3 = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))
    edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
    edge2 = Edge.create(source_node_id=node2.id, target_node_id=node3.id)
    workflow = Workflow.create(
        name="simple",
        description="",
        nodes=[node1, node2, node3],
        edges=[edge1, edge2],
    )

    engine = WorkflowEngine(executor_registry=None)

    with pytest.raises(DomainError, match="Missing executor registry"):
        await engine.execute(workflow=workflow, initial_input="hello")


@pytest.mark.asyncio
async def test_execute_raises_when_missing_executor() -> None:
    node1 = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node2 = Node.create(
        type=NodeType.HTTP, name="HTTP 请求", config={}, position=Position(x=100, y=0)
    )
    node3 = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))
    edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
    edge2 = Edge.create(source_node_id=node2.id, target_node_id=node3.id)
    workflow = Workflow.create(
        name="simple",
        description="",
        nodes=[node1, node2, node3],
        edges=[edge1, edge2],
    )

    engine = WorkflowEngine(executor_registry=NodeExecutorRegistry())

    with pytest.raises(DomainError, match="Missing executor for"):
        await engine.execute(workflow=workflow, initial_input="hello")

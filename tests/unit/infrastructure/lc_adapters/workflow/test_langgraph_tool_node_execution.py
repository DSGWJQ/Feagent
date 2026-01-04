from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.tool import Tool, ToolParameter
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.tool_category import ToolCategory
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.tool_repository import SQLAlchemyToolRepository
from src.infrastructure.executors.tool_node_executor import ToolNodeExecutor
from src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor import (
    execute_workflow_async,
)


@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.mark.anyio
async def test_langgraph_executor_runs_tool_node_via_tool_id(test_engine) -> None:
    TestingSessionLocal = sessionmaker(bind=test_engine)

    db: Session = TestingSessionLocal()
    try:
        tool = Tool.create(
            name="echo_tool",
            description="",
            category=ToolCategory.CUSTOM,
            author="tester",
            parameters=[ToolParameter(name="message", type="string", description="")],
            implementation_type="builtin",
            implementation_config={"handler": "echo"},
        )
        SQLAlchemyToolRepository(db).save(tool)
        db.commit()
    finally:
        db.close()

    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    tool_node = Node.create(
        type=NodeType.TOOL,
        name="tool",
        config={"tool_id": tool.id, "params": {"message": "hello"}},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))
    edges = [
        Edge.create(source_node_id=start.id, target_node_id=tool_node.id),
        Edge.create(source_node_id=tool_node.id, target_node_id=end.id),
    ]
    workflow = Workflow.create(
        name="wf", description="", nodes=[start, tool_node, end], edges=edges
    )

    registry = NodeExecutorRegistry()
    registry.register("tool", ToolNodeExecutor(session_factory=TestingSessionLocal))

    final_result, _log = await execute_workflow_async(
        workflow,
        initial_input={"ignored": True},
        executor_registry=registry,
    )
    assert final_result == {"echoed": "hello"}

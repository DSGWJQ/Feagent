from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entities.node import Node
from src.domain.entities.tool import Tool, ToolParameter
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.tool_repository import SQLAlchemyToolRepository
from src.infrastructure.executors.tool_node_executor import ToolNodeExecutor


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


def _session_factory(test_engine) -> sessionmaker[Session]:
    return sessionmaker(bind=test_engine)


@pytest.mark.anyio
async def test_tool_node_executor_executes_echo_tool(test_engine) -> None:
    SessionLocal = _session_factory(test_engine)
    db = SessionLocal()
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

    executor = ToolNodeExecutor(session_factory=SessionLocal)
    node = Node.create(
        type=NodeType.TOOL,
        name="tool",
        config={"tool_id": tool.id, "params": {"message": "hello"}},
        position=Position(x=0, y=0),
    )
    result = await executor.execute(node, inputs={}, context={"initial_input": None})
    assert result == {"echoed": "hello"}


@pytest.mark.anyio
async def test_tool_node_executor_fails_closed_when_tool_missing(test_engine) -> None:
    SessionLocal = _session_factory(test_engine)
    executor = ToolNodeExecutor(session_factory=SessionLocal)
    node = Node.create(
        type=NodeType.TOOL,
        name="tool",
        config={"tool_id": "tool_missing", "params": {"message": "hello"}},
        position=Position(x=0, y=0),
    )
    with pytest.raises(DomainError, match="tool not found"):
        await executor.execute(node, inputs={}, context={})


@pytest.mark.anyio
async def test_tool_node_executor_fails_closed_when_tool_deprecated(test_engine) -> None:
    SessionLocal = _session_factory(test_engine)
    db = SessionLocal()
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
        tool.status = ToolStatus.DEPRECATED
        SQLAlchemyToolRepository(db).save(tool)
        db.commit()
    finally:
        db.close()

    executor = ToolNodeExecutor(session_factory=SessionLocal)
    node = Node.create(
        type=NodeType.TOOL,
        name="tool",
        config={"tool_id": tool.id, "params": {"message": "hello"}},
        position=Position(x=0, y=0),
    )
    with pytest.raises(DomainError, match="tool is deprecated"):
        await executor.execute(node, inputs={}, context={})

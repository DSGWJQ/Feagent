from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.tool import Tool
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainValidationError
from src.domain.services.workflow_save_validator import WorkflowSaveValidator
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus
from src.infrastructure.executors import create_executor_registry


def _node(node_type: NodeType, *, config: dict | None = None) -> Node:
    return Node.create(
        type=node_type,
        name=node_type.value,
        config=config or {},
        position=Position(x=0, y=0),
    )


def test_validator_accepts_simple_dag():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    end = _node(NodeType.END)
    edge = Edge.create(source_node_id=start.id, target_node_id=end.id)

    workflow = Workflow.create(name="wf", description="", nodes=[start, end], edges=[edge])
    validator.validate_or_raise(workflow)


def test_validator_rejects_cycles():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    a = _node(NodeType.HTTP)
    b = _node(NodeType.TRANSFORM)
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[a, b],
        edges=[
            Edge.create(source_node_id=a.id, target_node_id=b.id),
            Edge.create(source_node_id=b.id, target_node_id=a.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "cycle_detected" in codes


def test_validator_rejects_missing_executor():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    node = _node(NodeType.IMAGE)
    workflow = Workflow.create(name="wf", description="", nodes=[node], edges=[])

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "missing_executor" in codes


def test_validator_rejects_tool_node_missing_tool_id():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    node = _node(NodeType.TOOL, config={})
    workflow = Workflow.create(name="wf", description="", nodes=[node], edges=[])

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "missing_tool_id" in codes


def test_validator_rejects_deprecated_tool():
    registry = create_executor_registry()
    tool = Tool.create(
        name="t",
        description="",
        category=ToolCategory.HTTP,
        author="tester",
    )
    tool.id = "tool_123"
    tool.status = ToolStatus.DEPRECATED

    tool_repo = Mock()
    tool_repo.exists.return_value = True
    tool_repo.find_by_id.return_value = tool

    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=tool_repo)
    node = _node(NodeType.TOOL, config={"tool_id": "tool_123"})
    workflow = Workflow.create(name="wf", description="", nodes=[node], edges=[])

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "tool_deprecated" in codes


def test_validator_rejects_when_tool_not_found_fail_closed():
    registry = create_executor_registry(session_factory=lambda: None)

    tool_repo = Mock()
    tool_repo.exists.return_value = False
    tool_repo.find_by_id.return_value = None

    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=tool_repo)
    node = _node(NodeType.TOOL, config={"tool_id": "tool_missing"})
    workflow = Workflow.create(name="wf", description="", nodes=[node], edges=[])

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "tool_not_found" in codes


def test_validator_normalizes_tool_id_from_toolId_before_persisting_shape():
    registry = create_executor_registry()

    tool = Tool.create(
        name="t",
        description="",
        category=ToolCategory.HTTP,
        author="tester",
    )
    tool.id = "tool_123"
    tool.status = ToolStatus.PUBLISHED

    tool_repo = Mock()
    tool_repo.exists.return_value = True
    tool_repo.find_by_id.return_value = tool

    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=tool_repo)
    node = _node(NodeType.TOOL, config={"toolId": " tool_123 "})
    workflow = Workflow.create(name="wf", description="", nodes=[node], edges=[])

    with pytest.raises(DomainValidationError):
        validator.validate_or_raise(workflow)

    assert node.config.get("tool_id") == "tool_123"
    assert "toolId" not in node.config


def test_validator_prefers_non_empty_tool_id_over_blank_tool_id_field():
    registry = create_executor_registry()

    tool = Tool.create(
        name="t",
        description="",
        category=ToolCategory.HTTP,
        author="tester",
    )
    tool.id = "tool_123"
    tool.status = ToolStatus.PUBLISHED

    tool_repo = Mock()
    tool_repo.exists.return_value = True
    tool_repo.find_by_id.return_value = tool

    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=tool_repo)
    node = _node(NodeType.TOOL, config={"tool_id": "   ", "toolId": "tool_123"})
    workflow = Workflow.create(name="wf", description="", nodes=[node], edges=[])

    with pytest.raises(DomainValidationError):
        validator.validate_or_raise(workflow)

    assert node.config.get("tool_id") == "tool_123"
    assert "toolId" not in node.config

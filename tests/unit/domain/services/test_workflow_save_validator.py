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

    start = _node(NodeType.START)
    node = _node(NodeType.TOOL, config={"tool_id": "tool_123"})
    end = _node(NodeType.END)
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node.id),
            Edge.create(source_node_id=node.id, target_node_id=end.id),
        ],
    )

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


def test_validator_allows_draft_to_contain_incomplete_tool_node_outside_main_subgraph():
    # Draft editing: in-progress nodes outside the main start->end subgraph should not block saving.
    # This specifically avoids tool nodes being a "dead end" if a user drags one onto the canvas
    # but hasn't selected a tool yet.
    registry = (
        create_executor_registry()
    )  # NOTE: tool executor is not registered without session_factory.
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    tool = _node(NodeType.TOOL, config={})
    end = _node(NodeType.END)

    # Main runnable path is start -> end; tool is disconnected (outside the main subgraph).
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, tool, end],
        edges=[Edge.create(source_node_id=start.id, target_node_id=end.id)],
    )

    validator.validate_or_raise(workflow)


def test_validator_rejects_tool_node_when_tool_repository_is_unavailable_fail_closed():
    # Registry must include tool executor; otherwise we'd get a `missing_executor` drift.
    registry = create_executor_registry(session_factory=lambda: None)
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=None)

    start = _node(NodeType.START)
    node = _node(NodeType.TOOL, config={"tool_id": "tool_123"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node.id),
            Edge.create(source_node_id=node.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "tool_repository_unavailable" in codes
    assert "missing_executor" not in codes


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


def test_validator_normalizes_http_url_from_legacy_path_before_persisting_shape():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    http = _node(
        NodeType.HTTP_REQUEST,
        config={"path": " https://api.example.com/health ", "method": "GET"},
    )
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=http.id),
            Edge.create(source_node_id=http.id, target_node_id=end.id),
        ],
    )

    validator.validate_or_raise(workflow)

    assert http.config.get("url") == "https://api.example.com/health"
    assert "path" not in http.config


def test_validator_normalizes_loop_for_to_range_and_moves_iterations_to_end():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    loop = _node(NodeType.LOOP, config={"type": "for", "iterations": 3, "code": "result = i"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, loop, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=loop.id),
            Edge.create(source_node_id=loop.id, target_node_id=end.id),
        ],
    )

    validator.validate_or_raise(workflow)

    assert loop.config.get("type") == "range"
    assert loop.config.get("end") == 3
    assert "iterations" not in loop.config


def test_validator_rejects_text_model_multi_input_without_prompt_source():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    http = _node(
        NodeType.HTTP_REQUEST,
        config={"url": "https://example.test/api", "method": "GET"},
    )
    transform = _node(
        NodeType.TRANSFORM, config={"type": "field_mapping", "mapping": {"x": "input1"}}
    )
    llm = _node(NodeType.TEXT_MODEL, config={"model": "openai/gpt-4"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, transform, llm, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=http.id),
            Edge.create(source_node_id=start.id, target_node_id=transform.id),
            Edge.create(source_node_id=http.id, target_node_id=llm.id),
            Edge.create(source_node_id=transform.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "ambiguous_prompt_source" in codes


def test_validator_rejects_text_model_when_prompt_source_node_id_not_in_incoming_sources():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    a = _node(NodeType.PYTHON, config={"code": "result = 1"})
    b = _node(NodeType.PYTHON, config={"code": "result = 2"})
    llm = _node(
        NodeType.TEXT_MODEL,
        config={"model": "openai/gpt-4", "promptSourceNodeId": "node_missing"},
    )
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, a, b, llm, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=a.id),
            Edge.create(source_node_id=start.id, target_node_id=b.id),
            Edge.create(source_node_id=a.id, target_node_id=llm.id),
            Edge.create(source_node_id=b.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    invalid = [err for err in exc.value.errors if err.get("code") == "invalid_prompt_source"]
    assert invalid, exc.value.errors
    assert invalid[0].get("path") == "nodes[3].config.promptSourceNodeId"
    assert set(invalid[0].get("meta", {}).get("incoming_sources", [])) == {a.id, b.id}


def test_validator_rejects_database_url_when_not_sqlite():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    db = _node(
        NodeType.DATABASE,
        config={"database_url": "postgresql://localhost:5432/db", "sql": "SELECT 1"},
    )
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, db, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=db.id),
            Edge.create(source_node_id=db.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "unsupported_database_url" in codes


def test_validator_rejects_text_model_when_provider_is_not_openai():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    llm = _node(NodeType.TEXT_MODEL, config={"model": "google/gemini-2.5-flash", "prompt": "hi"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, llm, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "unsupported_model_provider" in codes


def test_validator_rejects_text_model_when_model_looks_like_non_openai_without_prefix():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    llm = _node(NodeType.TEXT_MODEL, config={"model": "gemini-2.5-flash", "prompt": "hi"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, llm, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "unsupported_model" in codes


def test_validator_rejects_embedding_model_when_provider_is_not_openai():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    embedding = _node(NodeType.EMBEDDING, config={"model": "cohere/embed-v1"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, embedding, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=embedding.id),
            Edge.create(source_node_id=embedding.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "unsupported_model_provider" in codes


def test_validator_rejects_image_generation_when_model_is_gemini_family():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    image = _node(NodeType.IMAGE, config={"model": "gemini-2.5-flash-image"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, image, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=image.id),
            Edge.create(source_node_id=image.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "unsupported_model" in codes


def test_validator_rejects_structured_output_when_provider_is_not_openai():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    node = _node(
        NodeType.STRUCTURED_OUTPUT,
        config={
            "model": "anthropic/claude-3.5-sonnet",
            "schemaName": "S",
            "schema": {"type": "object", "properties": {"a": {"type": "string"}}},
        },
    )
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node.id),
            Edge.create(source_node_id=node.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "unsupported_model_provider" in codes


def test_validator_rejects_structured_output_missing_schema_fields():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    node = _node(NodeType.STRUCTURED_OUTPUT, config={})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node.id),
            Edge.create(source_node_id=node.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "missing_schema_name" in codes
    assert "missing_schema" in codes


def test_validator_rejects_structured_output_schema_when_json_is_invalid():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    node = _node(
        NodeType.STRUCTURED_OUTPUT,
        config={
            "schemaName": "S",
            "schema": "{not json}",
        },
    )
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node.id),
            Edge.create(source_node_id=node.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "invalid_json" in codes


def test_validator_rejects_notification_webhook_missing_url_and_message():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    node = _node(NodeType.NOTIFICATION, config={"type": "webhook"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node.id),
            Edge.create(source_node_id=node.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "missing_message" in codes
    assert "missing_url" in codes


def test_validator_rejects_notification_email_missing_required_fields():
    registry = create_executor_registry()
    validator = WorkflowSaveValidator(executor_registry=registry, tool_repository=Mock())

    start = _node(NodeType.START)
    node = _node(NodeType.NOTIFICATION, config={"type": "email", "message": "hi"})
    end = _node(NodeType.END)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node.id),
            Edge.create(source_node_id=node.id, target_node_id=end.id),
        ],
    )

    with pytest.raises(DomainValidationError) as exc:
        validator.validate_or_raise(workflow)

    codes = {err.get("code") for err in exc.value.errors}
    assert "missing_smtp_host" in codes
    assert "missing_sender" in codes
    assert "missing_sender_password" in codes
    assert "missing_recipients" in codes

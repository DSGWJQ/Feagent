from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainValidationError
from src.domain.services.workflow_chat_service_enhanced import EnhancedWorkflowChatService
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class _NoopLLM:
    def invoke(self, *_args, **_kwargs):  # pragma: no cover - not used
        raise AssertionError("LLM should not be called in this unit test")

    async def ainvoke(self, *_args, **_kwargs):  # pragma: no cover - not used
        raise AssertionError("LLM should not be called in this unit test")


def test_apply_modifications_supports_nodes_to_update_and_edges_to_update():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={"url": "https://old.test", "method": "GET"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    edge1 = Edge.create(source_node_id=start.id, target_node_id=http.id)
    edge2 = Edge.create(source_node_id=http.id, target_node_id=end.id, condition="True")

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[edge1, edge2],
    )

    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=_NoopLLM(),  # type: ignore[arg-type]
        chat_message_repository=Mock(),
        tool_repository=None,
    )

    modified, count = service._apply_modifications(
        workflow,
        {
            "nodes_to_update": [
                {"id": http.id, "config_patch": {"url": "https://new.test"}, "name": "HTTP 新"}
            ],
            "edges_to_update": [{"id": edge2.id, "condition": "False"}],
        },
    )

    assert count == 2
    updated_http = next(n for n in modified.nodes if n.id == http.id)
    assert updated_http.name == "HTTP 新"
    assert updated_http.config["url"] == "https://new.test"

    updated_edge2 = next(e for e in modified.edges if e.id == edge2.id)
    assert updated_edge2.condition == "False"


def test_apply_modifications_config_patch_merges_and_preserves_other_fields():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={"url": "https://old.test", "method": "GET", "headers": "{}"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    edge1 = Edge.create(source_node_id=start.id, target_node_id=http.id)
    edge2 = Edge.create(source_node_id=http.id, target_node_id=end.id)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[edge1, edge2],
    )

    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=_NoopLLM(),  # type: ignore[arg-type]
        chat_message_repository=Mock(),
        tool_repository=None,
    )

    modified, count = service._apply_modifications(
        workflow,
        {"nodes_to_update": [{"id": http.id, "config_patch": {"url": "https://new.test"}}]},
    )

    assert count == 1
    updated_http = next(n for n in modified.nodes if n.id == http.id)
    assert updated_http.config["url"] == "https://new.test"
    assert updated_http.config["method"] == "GET"
    assert updated_http.config["headers"] == "{}"


def test_apply_modifications_config_overwrite_replaces_config():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={"url": "https://old.test", "method": "GET", "headers": "{}"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    edge1 = Edge.create(source_node_id=start.id, target_node_id=http.id)
    edge2 = Edge.create(source_node_id=http.id, target_node_id=end.id)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[edge1, edge2],
    )

    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=_NoopLLM(),  # type: ignore[arg-type]
        chat_message_repository=Mock(),
        tool_repository=None,
    )

    modified, count = service._apply_modifications(
        workflow,
        {"nodes_to_update": [{"id": http.id, "config": {"url": "https://only.test"}}]},
    )

    assert count == 1
    updated_http = next(n for n in modified.nodes if n.id == http.id)
    assert updated_http.config == {"url": "https://only.test"}


def test_apply_modifications_edges_to_update_can_clear_condition():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={"url": "https://old.test", "method": "GET"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    edge1 = Edge.create(source_node_id=start.id, target_node_id=http.id)
    edge2 = Edge.create(source_node_id=http.id, target_node_id=end.id, condition="True")

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[edge1, edge2],
    )

    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=_NoopLLM(),  # type: ignore[arg-type]
        chat_message_repository=Mock(),
        tool_repository=None,
    )

    modified, count = service._apply_modifications(
        workflow,
        {"edges_to_update": [{"id": edge2.id, "condition": None}]},
    )

    assert count == 1
    updated_edge2 = next(e for e in modified.edges if e.id == edge2.id)
    assert updated_edge2.condition is None


def test_apply_modifications_rejects_updates_outside_main_subgraph():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))
    isolated = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="isolated",
        config={"url": "https://old.test", "method": "GET"},
        position=Position(x=100, y=100),
    )

    edge_main = Edge.create(source_node_id=start.id, target_node_id=end.id)
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, end, isolated],
        edges=[edge_main],
    )

    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=_NoopLLM(),  # type: ignore[arg-type]
        chat_message_repository=Mock(),
        tool_repository=None,
    )

    with pytest.raises(DomainValidationError) as excinfo:
        service._apply_modifications(
            workflow,
            {"nodes_to_update": [{"id": isolated.id, "config_patch": {"url": "https://new.test"}}]},
        )

    assert excinfo.value.code == "workflow_modification_rejected"


def test_apply_modifications_rejects_nodes_to_update_with_disallowed_fields():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={"url": "https://old.test", "method": "GET"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    edge1 = Edge.create(source_node_id=start.id, target_node_id=http.id)
    edge2 = Edge.create(source_node_id=http.id, target_node_id=end.id)
    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[edge1, edge2],
    )

    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=_NoopLLM(),  # type: ignore[arg-type]
        chat_message_repository=Mock(),
        tool_repository=None,
    )

    with pytest.raises(DomainValidationError) as excinfo:
        service._apply_modifications(
            workflow,
            {
                "nodes_to_update": [
                    {"id": http.id, "type": NodeType.END.value, "config_patch": {"url": "x"}}
                ]
            },
        )

    assert excinfo.value.code == "workflow_modification_rejected"
    assert any(
        err.get("field") == "nodes_to_update" and err.get("reason") == "disallowed_fields"
        for err in excinfo.value.errors
    )


def test_apply_modifications_config_patch_takes_precedence_over_config():
    start = Node.create(type=NodeType.START, name="start", config={}, position=Position(x=0, y=0))
    http = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={"url": "https://old.test", "method": "GET", "headers": "{}"},
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    edge1 = Edge.create(source_node_id=start.id, target_node_id=http.id)
    edge2 = Edge.create(source_node_id=http.id, target_node_id=end.id)

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, http, end],
        edges=[edge1, edge2],
    )

    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=_NoopLLM(),  # type: ignore[arg-type]
        chat_message_repository=Mock(),
        tool_repository=None,
    )

    modified, count = service._apply_modifications(
        workflow,
        {
            "nodes_to_update": [
                {
                    "id": http.id,
                    "config": {"url": "https://replace.test"},
                    "config_patch": {"url": "https://patch.test"},
                }
            ]
        },
    )

    assert count == 1
    updated_http = next(n for n in modified.nodes if n.id == http.id)
    assert updated_http.config["url"] == "https://patch.test"
    assert updated_http.config["method"] == "GET"

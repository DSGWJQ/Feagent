from __future__ import annotations

from unittest.mock import Mock

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_chat_service_enhanced import EnhancedWorkflowChatService
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class _FakeLLM:
    def __init__(self, modifications: dict):
        self._modifications = modifications

    def generate_modifications(self, _system_prompt: str, _user_prompt: str) -> dict:
        return self._modifications


def test_process_message_applies_nodes_to_update_and_edges_to_update():
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

    repo = Mock()
    repo.save = Mock()
    repo.find_by_workflow_id.return_value = []

    llm = _FakeLLM(
        {
            "ai_message": "ok",
            "nodes_to_update": [{"id": http.id, "config_patch": {"url": "https://new.test"}}],
            "edges_to_update": [{"id": edge2.id, "condition": "False"}],
        }
    )
    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=llm,
        chat_message_repository=repo,
        tool_repository=None,
    )

    result = service.process_message(workflow, "update http url and edge condition")

    assert result.success is True
    assert result.modified_workflow is not None

    updated_http = next(n for n in result.modified_workflow.nodes if n.id == http.id)
    assert updated_http.config["url"] == "https://new.test"

    updated_edge = next(e for e in result.modified_workflow.edges if e.id == edge2.id)
    assert updated_edge.condition == "False"

    assert repo.save.call_count >= 2

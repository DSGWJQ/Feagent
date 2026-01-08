from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.workflow_chat_service_enhanced import EnhancedWorkflowChatService
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors.python_executor import PythonExecutor


class _FakeLLM:
    def __init__(self, modifications: dict):
        self._modifications = modifications

    def generate_modifications(self, _system_prompt: str, _user_prompt: str) -> dict:
        return self._modifications


@pytest.mark.asyncio
async def test_chat_update_changes_config_and_edge_condition_affect_execution_result():
    start = Node.create(
        type=NodeType.START,
        name="start",
        config={},
        position=Position(x=-100, y=0),
    )
    python_node = Node.create(
        type=NodeType.PYTHON,
        name="python",
        config={"code": "result = 1"},
        position=Position(x=0, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))
    edge_start = Edge.create(source_node_id=start.id, target_node_id=python_node.id)
    edge = Edge.create(source_node_id=python_node.id, target_node_id=end.id, condition="false")

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[start, python_node, end],
        edges=[edge_start, edge],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.PYTHON.value, PythonExecutor())
    executor = WorkflowExecutor(executor_registry=registry)

    original_result = await executor.execute(workflow, initial_input={"unused": True})
    assert original_result is None

    repo = Mock()
    repo.save = Mock()
    repo.find_by_workflow_id.return_value = []

    llm = _FakeLLM(
        {
            "ai_message": "ok",
            "nodes_to_update": [{"id": python_node.id, "config": {"code": "result = 2"}}],
            "edges_to_update": [{"id": edge.id, "condition": "true"}],
        }
    )
    service = EnhancedWorkflowChatService(
        workflow_id=workflow.id,
        llm=llm,
        chat_message_repository=repo,
        tool_repository=None,
    )

    modification_result = service.process_message(workflow, "update python code and edge condition")
    assert modification_result.success is True
    assert modification_result.modified_workflow is not None

    updated_result = await executor.execute(
        modification_result.modified_workflow, initial_input={"unused": True}
    )
    assert updated_result == 2

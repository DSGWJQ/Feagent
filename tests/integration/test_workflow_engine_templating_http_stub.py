from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors.http_executor import HttpExecutor
from src.infrastructure.executors.python_executor import PythonExecutor


@pytest.mark.asyncio
async def test_templated_http_url_is_rendered_before_request(monkeypatch):
    calls: list[dict[str, Any]] = []

    class _StubResponse:
        def __init__(self, payload: dict[str, Any]):
            self._payload = payload
            self.status_code = 200
            self.text = "OK"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    class _StubAsyncClient:
        def __init__(self, *args, **kwargs):
            self._timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, *, method: str, url: str, headers: dict[str, str], json: Any):
            calls.append(
                {
                    "timeout": self._timeout,
                    "method": method,
                    "url": url,
                    "headers": headers,
                    "json": json,
                }
            )
            return _StubResponse({"ok": True, "url": url})

    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)

    python_node = Node.create(
        type=NodeType.PYTHON,
        name="python",
        config={"code": "result = {'userId': 123}"},
        position=Position(x=0, y=0),
    )
    http_node = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="http",
        config={
            "url": "https://api.test/users/{input1.userId}",
            "method": "POST",
            "headers": '{"X-User":"{input1.userId}"}',
            "body": '{"id":"{input1.userId}"}',
        },
        position=Position(x=100, y=0),
    )
    end = Node.create(type=NodeType.END, name="end", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(
        name="wf",
        description="",
        nodes=[python_node, http_node, end],
        edges=[
            Edge.create(source_node_id=python_node.id, target_node_id=http_node.id),
            Edge.create(source_node_id=http_node.id, target_node_id=end.id),
        ],
    )

    registry = NodeExecutorRegistry()
    registry.register(NodeType.PYTHON.value, PythonExecutor())
    registry.register(NodeType.HTTP_REQUEST.value, HttpExecutor(timeout=5.0))
    executor = WorkflowExecutor(executor_registry=registry)

    result = await executor.execute(workflow, initial_input={"unused": True})

    assert calls == [
        {
            "timeout": 5.0,
            "method": "POST",
            "url": "https://api.test/users/123",
            "headers": {"X-User": "123"},
            "json": {"id": "123"},
        }
    ]
    assert result == {"ok": True, "url": "https://api.test/users/123"}

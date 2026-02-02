"""P2 / Milestone 1: `/api/workflows/capabilities` contract test.

Goal: UI/chat/doc can consume a single machine-readable capability matrix derived from SoT.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interfaces.api.routes import workflow_capabilities


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(workflow_capabilities.router, prefix="/api")
    return TestClient(app)


def test_capabilities_endpoint_returns_schema_and_constraints(client: TestClient) -> None:
    response = client.get("/api/workflows/capabilities")
    assert response.status_code == 200
    body = response.json()

    assert isinstance(body.get("schema_version"), str)
    assert body["schema_version"]

    constraints = body["constraints"]
    assert constraints["sqlite_only"] is True
    assert constraints["sqlite_database_url_prefix"] == "sqlite:///"
    assert constraints["openai_only"] is True
    assert constraints["model_providers_supported"] == ["openai"]
    assert constraints["draft_validation_scope"] == "main_subgraph_only"


def test_capabilities_endpoint_covers_ui_canonical_node_types(client: TestClient) -> None:
    response = client.get("/api/workflows/capabilities")
    assert response.status_code == 200
    body = response.json()

    expected = {
        "start",
        "end",
        "httpRequest",
        "textModel",
        "conditional",
        "javascript",
        "python",
        "transform",
        "prompt",
        "imageGeneration",
        "audio",
        "tool",
        "embeddingModel",
        "structuredOutput",
        "database",
        "file",
        "notification",
        "loop",
    }

    node_types = body["node_types"]
    assert isinstance(node_types, list) and node_types
    returned = {item["type"] for item in node_types}
    assert returned == expected

    # Executor availability should match the API container registry in this runtime.
    assert all(item.get("executor_available") is True for item in node_types)

    by_type = {item["type"]: item for item in node_types}
    assert "http" in by_type["httpRequest"]["aliases"]
    assert "llm" in by_type["textModel"]["aliases"]
    assert "condition" in by_type["conditional"]["aliases"]

    # Tool must include a tool-specific contract section (fail-closed).
    tool_contract = by_type["tool"]["validation_contract"]["tool_node"]
    assert tool_contract is not None
    assert "tool_id" in tool_contract["tool_id_keys"]

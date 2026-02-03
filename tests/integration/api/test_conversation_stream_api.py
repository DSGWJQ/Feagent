"""Conversation Stream API integration tests (respond-only contract).

Contract (Phase 3):
- /api/conversation/stream must be respond-only (no tool_call/create_node/execute_workflow)
- Output content must be natural language (no JSON, no code fences)
- When information is insufficient, ask 1–3 clarification questions per turn (<= 3 question marks)
- Stream terminates with `data: [DONE]`
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.main import app


def _parse_sse_events(content: str) -> list[dict]:
    events: list[dict] = []
    for line in content.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


class TestConversationStreamAPI:
    def test_stream_endpoint_exists(self, client: TestClient):
        response = client.post(
            "/api/conversation/stream",
            json={"message": "你好"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_returns_sse_format_and_done_marker(self, client: TestClient):
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试消息"},
        )

        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("Connection") == "keep-alive"
        assert "data:" in response.text
        assert response.text.strip().endswith("data: [DONE]")

    def test_stream_has_only_final_event(self, client: TestClient):
        response = client.post(
            "/api/conversation/stream",
            json={"message": "分析这个请求"},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        assert event_types.count("final") == 1
        assert "thinking" not in event_types
        assert "tool_call" not in event_types
        assert "tool_result" not in event_types

    def test_stream_final_is_natural_language_and_limits_questions(self, client: TestClient):
        response = client.post(
            "/api/conversation/stream",
            json={"message": "帮我做一个自动化流程"},
        )
        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        final = next(e for e in events if e.get("type") == "final")
        content = str(final.get("content", "")).strip()

        assert content, "final content must not be empty"
        assert not content.startswith("{"), "must not return raw JSON to user"
        assert "```" not in content, "must not return code fences to user"
        assert content.count("?") + content.count("？") <= 3

    def test_stream_with_workflow_id_is_still_respond_only(self, client: TestClient):
        response = client.post(
            "/api/conversation/stream",
            json={
                "message": "分析工作流",
                "workflow_id": "wf_test_123",
            },
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]
        assert "tool_call" not in event_types
        assert "tool_result" not in event_types
        assert event_types.count("final") == 1

    def test_stream_returns_session_id_header(self, client: TestClient):
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )

        assert response.status_code == 200
        assert "X-Session-ID" in response.headers

    def test_stream_events_have_sequence_and_timestamp(self, client: TestClient):
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )
        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        sequences = [e.get("sequence") for e in events if "sequence" in e]
        assert sequences == sorted(sequences), "sequence must be monotonic"

        for event in events:
            assert "timestamp" in event, f"event must include timestamp: {event}"


class TestConversationStreamSession:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint(self, client: TestClient):
        response = client.get("/api/conversation/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "active_sessions" in data

    def test_session_cancel(self, client: TestClient):
        stream_response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )
        session_id = stream_response.headers.get("X-Session-ID")

        if session_id:
            cancel_response = client.delete(f"/api/conversation/stream/{session_id}")
            assert cancel_response.status_code == 200
            assert cancel_response.json()["status"] == "cancelled"

"""Integration Tests for Workflow Execution Error Classification (Story C)

Tests SSE contract compliance for error classification fields:
- node_error events MUST contain: error_level, error_type, retryable, hint, message
- Validates ToolNotFoundError, ToolDeprecatedError, ToolExecutionError scenarios
- Ensures backward compatibility with old error events
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import (
    ToolDeprecatedError,
    ToolExecutionError,
    ToolNotFoundError,
)
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.run_status import RunStatus
from src.interfaces.api.main import app
from src.interfaces.api.routes.workflows import get_container, get_db_session, get_event_bus


class TestWorkflowExecutionErrorClassification:
    """Test error classification SSE contract for workflow execution"""

    @pytest.fixture
    def dependency_overrides(self):
        original = app.dependency_overrides.copy()
        try:
            app.dependency_overrides = {}
            yield app.dependency_overrides
        finally:
            app.dependency_overrides = original

    @pytest.fixture
    def client(self, dependency_overrides):
        """Create FastAPI test client with context manager"""
        with TestClient(app) as test_client:
            yield test_client

    @pytest.fixture
    def mock_workflow(self):
        """Create a workflow with a tool node"""
        from src.domain.value_objects.position import Position

        return Workflow(
            id="wf_test_001",
            name="Test Workflow",
            description="Test workflow with tool node",
            nodes=[
                Node(
                    id="node_input",
                    type=NodeType.INPUT,
                    name="Input Node",
                    config={},
                    position=Position(x=0, y=0),
                ),
                Node(
                    id="node_tool",
                    type=NodeType.TOOL,
                    name="Tool Node",
                    config={"tool_id": "test_tool_001"},
                    position=Position(x=100, y=100),
                ),
                Node(
                    id="node_output",
                    type=NodeType.OUTPUT,
                    name="Output Node",
                    config={},
                    position=Position(x=200, y=200),
                ),
            ],
            edges=[
                MagicMock(source_node_id="node_input", target_node_id="node_tool"),
                MagicMock(source_node_id="node_tool", target_node_id="node_output"),
            ],
        )

    @pytest.fixture
    def mock_run(self):
        """Create a mock run entity"""
        mock = MagicMock()
        mock.id = "run_test_001"
        mock.workflow_id = "wf_test_001"
        mock.status = RunStatus.CREATED
        return mock

    def _parse_sse_events(self, response_text: str) -> list[dict]:
        """Parse SSE events from response text"""
        events = []
        for line in response_text.strip().split("\n"):
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str and data_str != "[DONE]":
                    try:
                        events.append(json.loads(data_str))
                    except json.JSONDecodeError:
                        pass
        return events

    def _assert_error_classification_fields(
        self, event: dict, expected_error_level: str, expected_retryable: bool
    ):
        """Assert error classification fields are present and correct"""
        assert "error_level" in event, f"Missing error_level in event: {event}"
        assert "error_type" in event, f"Missing error_type in event: {event}"
        assert "retryable" in event, f"Missing retryable in event: {event}"
        assert "hint" in event, f"Missing hint in event: {event}"
        assert "message" in event, f"Missing message in event: {event}"

        assert isinstance(event["error_level"], str), "error_level must be string"
        assert isinstance(event["error_type"], str), "error_type must be string"
        assert isinstance(event["retryable"], bool), "retryable must be boolean"
        assert isinstance(event["hint"], str), "hint must be string"
        assert isinstance(event["message"], str), "message must be string"

        assert event["error_level"] == expected_error_level
        assert event["retryable"] == expected_retryable
        assert len(event["hint"]) > 0, "hint must be non-empty"
        assert len(event["message"]) > 0, "message must be non-empty"

    @pytest.mark.integration
    def test_tool_not_found_error_sse_contract(self, client, dependency_overrides):
        """Test: Tool not found → node_error with correct classification fields"""
        mock_db = MagicMock()
        dependency_overrides[get_db_session] = lambda: mock_db
        dependency_overrides[get_event_bus] = lambda: MagicMock()

        mock_container = MagicMock()
        mock_entry = MagicMock()
        mock_entry.prepare = AsyncMock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "workflow_start", "workflow_id": "wf_test_001"}
            yield {"type": "node_start", "node_id": "node_input"}
            yield {
                "type": "node_complete",
                "node_id": "node_input",
                "output": {"test": "data"},
            }
            yield {"type": "node_start", "node_id": "node_tool"}

            exc = ToolNotFoundError(tool_id="test_tool_001")
            error_dict = exc.to_dict()
            yield {
                "type": "node_error",
                "node_id": "node_tool",
                "node_type": "tool",
                "error": str(exc),
                **error_dict,
            }

            yield {"type": "workflow_error", "error": "Node execution failed"}

        mock_entry.stream_after_gate = mock_stream
        mock_container.workflow_run_execution_entry.return_value = mock_entry
        dependency_overrides[get_container] = lambda: mock_container

        response = client.post(
            "/api/workflows/wf_test_001/execute/stream",
            json={"run_id": "run_test_001", "initial_input": {"test": "data"}},
        )

        assert response.status_code == 200

        events = self._parse_sse_events(response.text)
        node_error_events = [e for e in events if e.get("type") == "node_error"]
        assert len(node_error_events) == 1, "Should have exactly one node_error event"

        error_event = node_error_events[0]

        self._assert_error_classification_fields(
            error_event,
            expected_error_level="user_action_required",
            expected_retryable=False,
        )

        assert error_event["error_type"] == "tool_not_found"
        assert "test_tool_001" in error_event["hint"]
        assert "Tool not found" in error_event["message"]

    @pytest.mark.integration
    def test_tool_deprecated_error_sse_contract(self, client, dependency_overrides):
        """Test: Tool deprecated → node_error with correct classification fields"""
        mock_db = MagicMock()
        dependency_overrides[get_db_session] = lambda: mock_db
        dependency_overrides[get_event_bus] = lambda: MagicMock()

        mock_container = MagicMock()
        mock_entry = MagicMock()
        mock_entry.prepare = AsyncMock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "workflow_start", "workflow_id": "wf_test_001"}
            yield {"type": "node_start", "node_id": "node_tool"}

            exc = ToolDeprecatedError(tool_id="deprecated_tool")
            error_dict = exc.to_dict()
            yield {
                "type": "node_error",
                "node_id": "node_tool",
                "node_type": "tool",
                "error": str(exc),
                **error_dict,
            }

            yield {"type": "workflow_error", "error": "Tool is deprecated"}

        mock_entry.stream_after_gate = mock_stream
        mock_container.workflow_run_execution_entry.return_value = mock_entry
        dependency_overrides[get_container] = lambda: mock_container

        response = client.post(
            "/api/workflows/wf_test_001/execute/stream",
            json={"run_id": "run_test_001", "initial_input": {}},
        )

        assert response.status_code == 200

        events = self._parse_sse_events(response.text)
        node_error_events = [e for e in events if e.get("type") == "node_error"]
        assert len(node_error_events) == 1

        error_event = node_error_events[0]

        self._assert_error_classification_fields(
            error_event,
            expected_error_level="user_action_required",
            expected_retryable=False,
        )

        assert error_event["error_type"] == "tool_deprecated"
        assert "已废弃" in error_event["hint"]

    @pytest.mark.integration
    def test_tool_execution_timeout_error_sse_contract(self, client, dependency_overrides):
        """Test: Tool execution timeout → node_error with retryable=True"""
        mock_db = MagicMock()
        dependency_overrides[get_db_session] = lambda: mock_db
        dependency_overrides[get_event_bus] = lambda: MagicMock()

        mock_container = MagicMock()
        mock_entry = MagicMock()
        mock_entry.prepare = AsyncMock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "workflow_start", "workflow_id": "wf_test_001"}
            yield {"type": "node_start", "node_id": "node_tool"}

            exc = ToolExecutionError(
                tool_id="slow_tool",
                error_type="timeout",
                error_message="Execution exceeded 30s timeout",
            )
            error_dict = exc.to_dict()
            yield {
                "type": "node_error",
                "node_id": "node_tool",
                "node_type": "tool",
                "error": str(exc),
                **error_dict,
            }

            yield {"type": "workflow_error", "error": "Tool execution failed"}

        mock_entry.stream_after_gate = mock_stream
        mock_container.workflow_run_execution_entry.return_value = mock_entry
        dependency_overrides[get_container] = lambda: mock_container

        response = client.post(
            "/api/workflows/wf_test_001/execute/stream",
            json={"run_id": "run_test_001", "initial_input": {}},
        )

        assert response.status_code == 200

        events = self._parse_sse_events(response.text)
        node_error_events = [e for e in events if e.get("type") == "node_error"]
        assert len(node_error_events) == 1

        error_event = node_error_events[0]

        self._assert_error_classification_fields(
            error_event,
            expected_error_level="retryable",
            expected_retryable=True,
        )

        assert error_event["error_type"] == "timeout"
        assert "超时" in error_event["hint"] or "timeout" in error_event["hint"].lower()

    @pytest.mark.integration
    def test_all_error_types_have_classification_fields(self, client):
        """Test: All three error types emit complete classification fields"""
        error_scenarios = [
            (
                ToolNotFoundError("missing_tool"),
                "user_action_required",
                False,
                "tool_not_found",
            ),
            (
                ToolDeprecatedError("old_tool"),
                "user_action_required",
                False,
                "tool_deprecated",
            ),
            (
                ToolExecutionError("failing_tool", "execution_error", "Runtime error occurred"),
                "retryable",
                True,
                "execution_error",
            ),
        ]

        for exc, expected_level, expected_retryable, expected_type in error_scenarios:
            error_dict = exc.to_dict()

            assert "error_level" in error_dict
            assert "error_type" in error_dict
            assert "retryable" in error_dict
            assert "hint" in error_dict
            assert "message" in error_dict

            assert error_dict["error_level"] == expected_level
            assert error_dict["retryable"] == expected_retryable
            assert error_dict["error_type"] == expected_type
            assert len(error_dict["hint"]) > 0
            assert len(error_dict["message"]) > 0

    @pytest.mark.integration
    def test_backward_compatibility_missing_fields(self, client, dependency_overrides):
        """Test: Frontend should handle old error events without classification fields"""
        mock_db = MagicMock()
        dependency_overrides[get_db_session] = lambda: mock_db
        dependency_overrides[get_event_bus] = lambda: MagicMock()

        mock_container = MagicMock()
        mock_entry = MagicMock()
        mock_entry.prepare = AsyncMock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "workflow_start", "workflow_id": "wf_test_001"}
            yield {"type": "node_start", "node_id": "node_tool"}

            yield {
                "type": "node_error",
                "node_id": "node_tool",
                "node_type": "tool",
                "error": "Some generic error",
            }

            yield {"type": "workflow_error", "error": "Workflow failed"}

        mock_entry.stream_after_gate = mock_stream
        mock_container.workflow_run_execution_entry.return_value = mock_entry
        dependency_overrides[get_container] = lambda: mock_container

        response = client.post(
            "/api/workflows/wf_test_001/execute/stream",
            json={"run_id": "run_test_001", "initial_input": {}},
        )

        assert response.status_code == 200

        events = self._parse_sse_events(response.text)
        node_error_events = [e for e in events if e.get("type") == "node_error"]
        assert len(node_error_events) == 1

        error_event = node_error_events[0]

        assert "error" in error_event
        assert error_event["error"] == "Some generic error"


__all__ = ["TestWorkflowExecutionErrorClassification"]

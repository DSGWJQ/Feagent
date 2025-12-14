"""TDD RED: tests for UpdateWorkflowByChatUseCase

Coverage focus (target ~70% for src/application/use_cases/update_workflow_by_chat.py):
- Input validation (empty/whitespace messages)
- Workflow retrieval (exists vs NotFoundError)
- Service compatibility (basic tuple vs enhanced ModificationResult)
- Enhanced service error handling (success=False, None workflow)
- Persistence ordering and instance integrity
- Output field mapping (all 7 fields)
- Async streaming (event order, content, react_steps iteration)
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.application.use_cases.update_workflow_by_chat import (
    UpdateWorkflowByChatInput,
    UpdateWorkflowByChatUseCase,
)
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


@pytest.fixture()
def workflow():
    """Create sample workflow with 2 nodes."""
    node1 = Node.create(
        type=NodeType.HTTP,
        name="HTTP Node",
        config={"url": "https://example.com"},
        position=Position(x=100, y=100),
    )
    node2 = Node.create(
        type=NodeType.LLM,
        name="LLM Node",
        config={"model": "gpt-4"},
        position=Position(x=200, y=200),
    )
    return Workflow.create(
        name="Test Workflow",
        description="Test workflow for chat updates",
        nodes=[node1, node2],
        edges=[],
    )


@pytest.fixture()
def mock_repo():
    """Mock WorkflowRepository"""
    return Mock()


@pytest.fixture()
def basic_chat_service(workflow):
    """Mock basic WorkflowChatService returning tuple"""
    service = Mock()
    service.process_message.return_value = (workflow, "AI response message")
    return service


@pytest.fixture()
def enhanced_chat_service(workflow):
    """Mock enhanced WorkflowChatService returning ModificationResult-like object"""
    service = Mock()
    service.process_message.return_value = SimpleNamespace(
        success=True,
        modified_workflow=workflow,
        ai_message="Enhanced AI response",
        intent="add_node",
        confidence=0.87,
        modifications_count=1,
        rag_sources=[{"doc_id": "123", "score": 0.95}],
        react_steps=[
            {
                "step": 1,
                "thought": "Analyzing request",
                "action": {"type": "parse"},
                "observation": "Parsed successfully",
            }
        ],
        error_message="",
    )
    return service


@pytest.fixture()
def use_case_basic(mock_repo, basic_chat_service):
    """UpdateWorkflowByChatUseCase with basic service"""
    return UpdateWorkflowByChatUseCase(
        workflow_repository=mock_repo,
        chat_service=basic_chat_service,
    )


@pytest.fixture()
def use_case_enhanced(mock_repo, enhanced_chat_service):
    """UpdateWorkflowByChatUseCase with enhanced service"""
    return UpdateWorkflowByChatUseCase(
        workflow_repository=mock_repo,
        chat_service=enhanced_chat_service,
    )


# --- A) Input Validation -----------------------------------------------------------


@pytest.mark.parametrize("user_message", ["", "   ", "\n\t"])
def test_execute_rejects_empty_or_whitespace_message(use_case_basic, mock_repo, user_message):
    """Empty or whitespace-only messages should raise DomainError before repository access."""
    input_data = UpdateWorkflowByChatInput(
        workflow_id="workflow-123",
        user_message=user_message,
    )

    with pytest.raises(DomainError, match="消息不能为空"):
        use_case_basic.execute(input_data)

    mock_repo.get_by_id.assert_not_called()
    mock_repo.save.assert_not_called()


@pytest.mark.parametrize("user_message", ["", "   ", "\n\t"])
@pytest.mark.asyncio
async def test_execute_streaming_rejects_empty_or_whitespace_message(
    use_case_basic, mock_repo, user_message
):
    """Streaming mode should raise DomainError on empty message without yielding events."""
    input_data = UpdateWorkflowByChatInput(
        workflow_id="workflow-123",
        user_message=user_message,
    )

    with pytest.raises(DomainError, match="消息不能为空"):
        async for _ in use_case_basic.execute_streaming(input_data):
            pytest.fail("Should not yield any events")

    mock_repo.get_by_id.assert_not_called()


# --- B) Workflow Retrieval ---------------------------------------------------------


def test_execute_raises_not_found_when_repo_returns_none(use_case_basic, mock_repo):
    """Repository returning None should raise NotFoundError."""
    mock_repo.get_by_id.return_value = None

    input_data = UpdateWorkflowByChatInput(
        workflow_id="nonexistent-workflow",
        user_message="Add a new node",
    )

    with pytest.raises(NotFoundError, match="Workflow"):
        use_case_basic.execute(input_data)

    mock_repo.get_by_id.assert_called_once_with("nonexistent-workflow")
    mock_repo.save.assert_not_called()


def test_execute_propagates_not_found_when_repo_raises(use_case_basic, mock_repo):
    """Repository raising NotFoundError should propagate the exception."""
    mock_repo.get_by_id.side_effect = NotFoundError(
        entity_type="Workflow",
        entity_id="missing-workflow",
    )

    input_data = UpdateWorkflowByChatInput(
        workflow_id="missing-workflow",
        user_message="Update workflow",
    )

    with pytest.raises(NotFoundError, match="Workflow.*missing-workflow"):
        use_case_basic.execute(input_data)


@pytest.mark.asyncio
async def test_execute_streaming_raises_not_found_before_any_events_when_missing_workflow(
    use_case_basic, mock_repo
):
    """Streaming should raise NotFoundError without yielding any events if workflow missing."""
    mock_repo.get_by_id.return_value = None

    input_data = UpdateWorkflowByChatInput(
        workflow_id="nonexistent-workflow",
        user_message="Add node",
    )

    with pytest.raises(NotFoundError, match="Workflow"):
        async for _ in use_case_basic.execute_streaming(input_data):
            pytest.fail("Should not yield any events")


# --- C) Service Compatibility ------------------------------------------------------


def test_execute_basic_service_tuple_maps_defaults_and_saves(
    use_case_basic, mock_repo, basic_chat_service, workflow
):
    """Basic service returning tuple should map to output with default values."""
    mock_repo.get_by_id.return_value = workflow

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Add HTTP node",
    )

    result = use_case_basic.execute(input_data)

    # Assert all output fields
    assert result.workflow is workflow
    assert result.ai_message == "AI response message"
    assert result.intent == ""
    assert result.confidence == 0.0
    assert result.modifications_count == 0
    assert result.rag_sources == []
    assert result.react_steps == []

    # Assert save called once with returned workflow
    mock_repo.save.assert_called_once_with(workflow)


def test_execute_enhanced_service_maps_all_fields_and_saves(
    use_case_enhanced, mock_repo, enhanced_chat_service, workflow
):
    """Enhanced service should map all 7 output fields correctly."""
    mock_repo.get_by_id.return_value = workflow

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Add database node",
    )

    result = use_case_enhanced.execute(input_data)

    # Assert all 7 fields match enhanced service response
    assert result.workflow is workflow
    assert result.ai_message == "Enhanced AI response"
    assert result.intent == "add_node"
    assert result.confidence == 0.87
    assert result.modifications_count == 1
    assert result.rag_sources == [{"doc_id": "123", "score": 0.95}]
    assert result.react_steps == [
        {
            "step": 1,
            "thought": "Analyzing request",
            "action": {"type": "parse"},
            "observation": "Parsed successfully",
        }
    ]

    # Assert save called with the returned workflow instance
    assert mock_repo.save.call_args.args[0] is workflow


# --- D) Enhanced Service Error Handling --------------------------------------------


def test_execute_enhanced_service_success_false_raises_domain_error_and_does_not_save(
    use_case_enhanced, mock_repo, enhanced_chat_service, workflow
):
    """Enhanced service with success=False should raise DomainError and skip save."""
    mock_repo.get_by_id.return_value = workflow
    enhanced_chat_service.process_message.return_value = SimpleNamespace(
        success=False,
        error_message="Failed to parse user intent",
        modified_workflow=None,
        ai_message="",
        intent="",
        confidence=0.0,
        modifications_count=0,
        rag_sources=[],
        react_steps=[],
    )

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Invalid request",
    )

    with pytest.raises(DomainError, match="Failed to parse user intent"):
        use_case_enhanced.execute(input_data)

    mock_repo.save.assert_not_called()


def test_execute_enhanced_service_success_false_without_message_uses_default_error(
    use_case_enhanced, mock_repo, enhanced_chat_service, workflow
):
    """Enhanced service with success=False and empty error_message should use default."""
    mock_repo.get_by_id.return_value = workflow
    enhanced_chat_service.process_message.return_value = SimpleNamespace(
        success=False,
        error_message="",
        modified_workflow=None,
        ai_message="",
        intent="",
        confidence=0.0,
        modifications_count=0,
        rag_sources=[],
        react_steps=[],
    )

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Bad request",
    )

    with pytest.raises(DomainError, match="修改工作流失败"):
        use_case_enhanced.execute(input_data)


def test_execute_enhanced_service_modified_workflow_none_raises_domain_error(
    use_case_enhanced, mock_repo, enhanced_chat_service, workflow
):
    """Enhanced service with success=True but modified_workflow=None should raise DomainError."""
    mock_repo.get_by_id.return_value = workflow
    enhanced_chat_service.process_message.return_value = SimpleNamespace(
        success=True,
        modified_workflow=None,
        ai_message="Processed",
        intent="add_node",
        confidence=0.8,
        modifications_count=1,
        rag_sources=[],
        react_steps=[],
        error_message="",
    )

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Add node",
    )

    with pytest.raises(DomainError, match="修改工作流失败：返回的工作流为空"):
        use_case_enhanced.execute(input_data)

    mock_repo.save.assert_not_called()


# --- E) Persistence Ordering / Instance Integrity ---------------------------------


def test_execute_calls_save_after_process_message_and_saves_returned_instance(
    use_case_basic, mock_repo, basic_chat_service, workflow
):
    """save() should be called after process_message() with the returned workflow instance."""
    mock_repo.get_by_id.return_value = workflow

    # Create parent mock to track call order
    parent_mock = Mock()
    parent_mock.attach_mock(basic_chat_service, "chat_service")
    parent_mock.attach_mock(mock_repo, "repo")

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Update nodes",
    )

    use_case_basic.execute(input_data)

    # Assert call order: process_message -> save
    call_names = [call[0] for call in parent_mock.mock_calls]
    process_index = call_names.index("chat_service.process_message")
    save_index = call_names.index("repo.save")
    assert process_index < save_index, "process_message should be called before save"

    # Assert save receives the same workflow instance
    assert mock_repo.save.call_args.args[0] is workflow


# --- F) Output / Event Mapping (Streaming) ----------------------------------------


@pytest.mark.asyncio
async def test_execute_streaming_basic_service_yields_expected_event_sequence(
    use_case_basic, mock_repo, basic_chat_service, workflow
):
    """Streaming with basic service should yield 3 events in order: started -> preview -> updated."""
    mock_repo.get_by_id.return_value = workflow

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Update workflow",
    )

    events = []
    async for event in use_case_basic.execute_streaming(input_data):
        events.append(event)

    # Assert event count and order
    assert len(events) == 3
    assert events[0]["type"] == "processing_started"
    assert events[1]["type"] == "modifications_preview"
    assert events[2]["type"] == "workflow_updated"

    # Assert processing_started content
    assert events[0]["workflow_id"] == workflow.id
    assert "timestamp" in events[0]

    # Assert modifications_preview defaults
    assert events[1]["modifications_count"] == 0
    assert events[1]["intent"] == ""
    assert events[1]["confidence"] == 0.0

    # Assert workflow_updated content
    assert events[2]["ai_message"] == "AI response message"
    assert events[2]["rag_sources"] == []
    assert "workflow" in events[2]
    assert events[2]["workflow"]["id"] == workflow.id
    assert len(events[2]["workflow"]["nodes"]) == 2


@pytest.mark.asyncio
async def test_execute_streaming_enhanced_service_yields_react_steps_then_preview_then_updated(
    use_case_enhanced, mock_repo, enhanced_chat_service, workflow
):
    """Streaming with enhanced service should yield: started -> react_steps -> preview -> updated."""
    mock_repo.get_by_id.return_value = workflow

    # Mock enhanced service with multiple react_steps
    enhanced_chat_service.process_message.return_value = SimpleNamespace(
        success=True,
        modified_workflow=workflow,
        ai_message="Enhanced response",
        intent="delete_node",
        confidence=0.92,
        modifications_count=2,
        rag_sources=[{"doc": "A"}, {"doc": "B"}],
        react_steps=[
            {"step": 1, "thought": "Step 1", "action": {"a": 1}, "observation": "Obs 1"},
            {"step": 2, "thought": "Step 2", "action": {"a": 2}, "observation": "Obs 2"},
        ],
        error_message="",
    )

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Delete node",
    )

    events = []
    async for event in use_case_enhanced.execute_streaming(input_data):
        events.append(event)

    # Assert event count: 1 started + 2 react_steps + 1 preview + 1 updated = 5
    assert len(events) == 5

    # Assert event order
    assert events[0]["type"] == "processing_started"
    assert events[1]["type"] == "react_step"
    assert events[2]["type"] == "react_step"
    assert events[3]["type"] == "modifications_preview"
    assert events[4]["type"] == "workflow_updated"

    # Assert react_step content
    assert events[1]["step_number"] == 1
    assert events[1]["thought"] == "Step 1"
    assert events[1]["action"] == {"a": 1}
    assert events[1]["observation"] == "Obs 1"

    assert events[2]["step_number"] == 2
    assert events[2]["thought"] == "Step 2"

    # Assert modifications_preview content
    assert events[3]["modifications_count"] == 2
    assert events[3]["intent"] == "delete_node"
    assert events[3]["confidence"] == 0.92

    # Assert workflow_updated content
    assert events[4]["ai_message"] == "Enhanced response"
    assert events[4]["rag_sources"] == [{"doc": "A"}, {"doc": "B"}]


@pytest.mark.asyncio
async def test_execute_streaming_enhanced_modified_workflow_none_yields_started_then_raises_domain_error(
    use_case_enhanced, mock_repo, enhanced_chat_service, workflow
):
    """Streaming should yield processing_started before raising on modified_workflow=None."""
    mock_repo.get_by_id.return_value = workflow
    enhanced_chat_service.process_message.return_value = SimpleNamespace(
        success=True,
        modified_workflow=None,
        ai_message="Processed",
        intent="add_node",
        confidence=0.8,
        modifications_count=1,
        rag_sources=[],
        react_steps=[],
        error_message="",
    )

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Add node",
    )

    events = []
    with pytest.raises(DomainError, match="修改工作流失败：返回的工作流为空"):
        async for event in use_case_enhanced.execute_streaming(input_data):
            events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "processing_started"
    mock_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_execute_streaming_enhanced_failure_yields_started_then_raises_domain_error(
    use_case_enhanced, mock_repo, enhanced_chat_service, workflow
):
    """Streaming should yield processing_started before raising DomainError on enhanced failure."""
    mock_repo.get_by_id.return_value = workflow
    enhanced_chat_service.process_message.return_value = SimpleNamespace(
        success=False,
        error_message="Intent parsing failed",
        modified_workflow=None,
        ai_message="",
        intent="",
        confidence=0.0,
        modifications_count=0,
        rag_sources=[],
        react_steps=[],
    )

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Invalid",
    )

    events = []
    with pytest.raises(DomainError, match="Intent parsing failed"):
        async for event in use_case_enhanced.execute_streaming(input_data):
            events.append(event)

    # Should have yielded processing_started before exception
    assert len(events) == 1
    assert events[0]["type"] == "processing_started"

    mock_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_streaming_timestamps_are_valid_isoformat(use_case_basic, mock_repo, workflow):
    """All streaming events with timestamp field should have valid ISO format."""
    mock_repo.get_by_id.return_value = workflow

    input_data = UpdateWorkflowByChatInput(
        workflow_id=workflow.id,
        user_message="Test timestamps",
    )

    async for event in use_case_basic.execute_streaming(input_data):
        if "timestamp" in event:
            # Should not raise ValueError
            datetime.fromisoformat(event["timestamp"])

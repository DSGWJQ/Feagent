"""WFCORE-090: WorkflowAgent plan reachability validation feedback loop (unit).

Coverage:
- When execute_workflow is unreachable (e.g., RunGateError), WorkflowAgent publishes a
  WorkflowAdjustmentRequestedEvent for replanning and returns a structured error.
- ConversationAgent can receive this feedback via start_feedback_listening().
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.entities.session_context import GlobalContext, SessionContext
from src.domain.exceptions import RunGateError
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_failure_orchestrator import WorkflowAdjustmentRequestedEvent


class _RejectingEntry:
    async def execute_with_results(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data=None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        execution_event_sink=None,
        record_execution_events: bool = False,
    ):
        _ = (workflow_id, input_data, correlation_id, original_decision_id, execution_event_sink)
        _ = record_execution_events
        raise RunGateError(
            "run is not executable",
            code="run_not_executable",
            details={"run_id": run_id, "status": "running"},
        )


@pytest.mark.asyncio
async def test_execute_workflow_unreachable_publishes_feedback_and_is_received():
    event_bus = EventBus()

    session_context = SessionContext(
        session_id="session_1",
        global_context=GlobalContext(user_id="user_1"),
    )
    conversation_agent = ConversationAgent(
        session_context=session_context,
        llm=MagicMock(),
        event_bus=event_bus,
    )
    conversation_agent.start_feedback_listening()

    workflow_agent = WorkflowAgent(
        event_bus=event_bus,
        workflow_run_execution_entry=_RejectingEntry(),
    )

    result = await workflow_agent.handle_decision(
        {
            "decision_type": "execute_workflow",
            "workflow_id": "wf_1",
            "run_id": "run_1",
            # Ensure user input is not leaked into feedback payloads.
            "initial_input": {"secret": "do_not_leak"},
        }
    )

    assert result["success"] is False
    assert result["status"] == "rejected"
    assert result["error"]["code"] == "run_not_executable"
    assert result["requires_replan"] is True

    assert any(isinstance(e, WorkflowAdjustmentRequestedEvent) for e in event_bus.event_log)

    feedbacks = await conversation_agent.get_pending_feedbacks_async()
    assert any(f.get("type") == "workflow_adjustment" for f in feedbacks)
    assert any(f.get("workflow_id") == "wf_1" for f in feedbacks)
    assert all("do_not_leak" not in str(f) for f in feedbacks)

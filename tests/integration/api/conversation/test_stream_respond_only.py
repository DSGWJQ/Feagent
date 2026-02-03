from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.services.conversation_turn_orchestrator import ConversationTurnOrchestrator
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.routes import conversation_stream as conversation_routes


class _RecordingToolExecutor:
    def __init__(self) -> None:
        self.called = False

    async def execute(self, *, tool_name: str, tool_call_id: str, arguments: dict):  # noqa: ANN001
        self.called = True
        return {"success": True, "result": {"tool_name": tool_name, "args": arguments}}


class _MaliciousLLM:
    async def think(self, context):  # noqa: ANN001
        return "TOP_SECRET_THOUGHT"

    async def decide_action(self, context):  # noqa: ANN001
        return {
            "action_type": "tool_call",
            "tool_name": "echo",
            "tool_id": "tool_1",
            "arguments": {"msg": "should not run"},
        }

    async def should_continue(self, context):  # noqa: ANN001
        return True


def test_conversation_stream_is_respond_only_and_does_not_execute_tools() -> None:
    from src.domain.agents.conversation_agent import ConversationAgent
    from src.domain.services.context_manager import GlobalContext, SessionContext

    executor = _RecordingToolExecutor()

    def conversation_turn_orchestrator_factory() -> ConversationTurnOrchestrator:
        session_ctx = SessionContext(session_id="s", global_context=GlobalContext(user_id="u"))
        agent = ConversationAgent(
            session_context=session_ctx, llm=_MaliciousLLM(), max_iterations=2
        )
        agent._respond_only = True  # type: ignore[attr-defined]
        agent.tool_call_executor = executor  # type: ignore[attr-defined]
        return ConversationTurnOrchestrator(conversation_agent=agent, policies=[])

    def _fake_repo(_: Any) -> Any:
        raise AssertionError("repository should not be touched in this test")

    def _fake_workflow_orchestrator(_: Any) -> Any:
        raise AssertionError("workflow orchestrator should not be touched in this test")

    app = FastAPI()
    app.state.container = ApiContainer(
        executor_registry=NodeExecutorRegistry(),
        workflow_execution_kernel=_fake_workflow_orchestrator,
        workflow_run_execution_entry=_fake_workflow_orchestrator,  # type: ignore[arg-type]
        conversation_turn_orchestrator=conversation_turn_orchestrator_factory,
        user_repository=_fake_repo,
        agent_repository=_fake_repo,
        task_repository=_fake_repo,
        workflow_repository=_fake_repo,
        chat_message_repository=_fake_repo,
        llm_provider_repository=_fake_repo,
        tool_repository=_fake_repo,
        run_repository=_fake_repo,
        scheduled_workflow_repository=_fake_repo,
    )
    app.include_router(conversation_routes.router, prefix="/api")

    client = TestClient(app)
    response = client.post("/api/conversation/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert executor.called is False

    # Contract: respond-only. No tool_call/tool_result events must appear in the SSE stream.
    assert '"type": "tool_call"' not in response.text
    assert '"type": "tool_result"' not in response.text

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.services.conversation_turn_orchestrator import (
    ConversationTurnOrchestrator,
    ConversationTurnPolicy,
)
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.routes import conversation_stream as conversation_routes


def test_conversation_stream_endpoint_goes_through_orchestrator_and_policy_chain() -> None:
    calls: list[str] = []

    class FakeConversationAgent:
        async def run_async(self, user_input: str) -> Any:
            return SimpleNamespace(final_response=f"echo:{user_input}")

    class RecordingPolicy(ConversationTurnPolicy):
        async def before_turn(
            self, *, session_id: str, message: str, context: dict[str, Any] | None
        ) -> None:
            calls.append("before")

        async def after_turn(
            self,
            *,
            session_id: str,
            message: str,
            context: dict[str, Any] | None,
            result: Any,
        ) -> None:
            calls.append("after")

        async def on_error(
            self,
            *,
            session_id: str,
            message: str,
            context: dict[str, Any] | None,
            error: Exception,
        ) -> None:
            calls.append("error")

        async def on_emit(self, *, session_id: str, message: str, kind: str, payload: Any) -> None:
            calls.append(f"emit:{kind}")

    def conversation_turn_orchestrator_factory() -> ConversationTurnOrchestrator:
        return ConversationTurnOrchestrator(
            conversation_agent=FakeConversationAgent(),
            policies=[RecordingPolicy()],
        )

    def _fake_repo(_: Any) -> Any:
        raise AssertionError("repository should not be touched in this test")

    def _fake_workflow_orchestrator(_: Any) -> Any:
        raise AssertionError("workflow orchestrator should not be touched in this test")

    app = FastAPI()
    app.state.container = ApiContainer(
        executor_registry=NodeExecutorRegistry(),
        workflow_execution_orchestrator=_fake_workflow_orchestrator,
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
    assert "echo:hello" in response.text
    assert "before" in calls
    assert "after" in calls

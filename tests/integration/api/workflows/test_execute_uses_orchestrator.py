from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.services.workflow_execution_orchestrator import (
    WorkflowExecutionOrchestrator,
    WorkflowExecutionPolicy,
)
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.routes import workflows as workflows_routes


def test_execute_endpoint_goes_through_orchestrator_and_policy_chain() -> None:
    calls: list[str] = []

    class FakeFacade:
        async def execute(self, *, workflow_id: str, input_data: Any = None) -> dict[str, Any]:
            return {"execution_log": [{"workflow_id": workflow_id}], "final_result": input_data}

        async def execute_streaming(
            self, *, workflow_id: str, input_data: Any = None
        ) -> AsyncGenerator[dict[str, Any], None]:
            if False:  # pragma: no cover - keep it an async generator
                yield {}

    class RecordingPolicy(WorkflowExecutionPolicy):
        async def before_execute(self, *, workflow_id: str, input_data: Any) -> None:
            calls.append("before")

        async def after_execute(
            self, *, workflow_id: str, input_data: Any, result: dict[str, Any]
        ) -> None:
            calls.append("after")

        async def on_error(self, *, workflow_id: str, input_data: Any, error: Exception) -> None:
            calls.append("error")

        async def on_event(
            self, *, workflow_id: str, input_data: Any, event: dict[str, Any]
        ) -> None:
            calls.append("event")

    def orchestrator_factory(_: Any) -> WorkflowExecutionOrchestrator:
        return WorkflowExecutionOrchestrator(facade=FakeFacade(), policies=[RecordingPolicy()])

    def _fake_repo(_: Any) -> Any:
        raise AssertionError("repository should not be touched in this test")

    def _fake_db_session() -> Any:
        yield object()

    app = FastAPI()
    app.state.container = ApiContainer(
        executor_registry=NodeExecutorRegistry(),
        workflow_execution_orchestrator=orchestrator_factory,
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
    app.dependency_overrides[get_db_session] = _fake_db_session
    app.include_router(workflows_routes.router, prefix="/api")

    client = TestClient(app)
    response = client.post("/api/workflows/wf_123/execute", json={"initial_input": {"k": "v"}})

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_result"] == {"k": "v"}
    assert calls == ["before", "after"]

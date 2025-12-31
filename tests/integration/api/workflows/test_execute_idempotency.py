from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.services.idempotency_coordinator import IdempotencyCoordinator
from src.application.services.workflow_execution_orchestrator import WorkflowExecutionOrchestrator
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.routes import workflows as workflows_routes


def test_execute_endpoint_is_idempotent_when_idempotency_key_is_reused() -> None:
    execute_calls: list[dict[str, Any]] = []
    idempotency = IdempotencyCoordinator(store=InMemoryIdempotencyStore())

    class FakeFacade:
        async def execute(self, *, workflow_id: str, input_data: Any = None) -> dict[str, Any]:
            execute_calls.append({"workflow_id": workflow_id, "input_data": input_data})
            return {"execution_log": [{"workflow_id": workflow_id}], "final_result": input_data}

        async def execute_streaming(self, *, workflow_id: str, input_data: Any = None) -> Any:
            if False:  # pragma: no cover - keep it an async generator
                yield {}

    def orchestrator_factory(_: Any) -> WorkflowExecutionOrchestrator:
        return WorkflowExecutionOrchestrator(facade=FakeFacade(), idempotency=idempotency)

    def _fake_repo(_: Any) -> Any:
        raise AssertionError("repository should not be touched in this test")

    def _fake_db_session() -> Any:
        yield object()

    app = FastAPI()
    app.state.container = ApiContainer(
        executor_registry=NodeExecutorRegistry(),
        workflow_execution_orchestrator=orchestrator_factory,
        conversation_turn_orchestrator=lambda: None,  # type: ignore[return-value]
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
    headers = {"Idempotency-Key": "idem_123"}

    response_1 = client.post(
        "/api/workflows/wf_123/execute",
        json={"initial_input": {"k": 1}},
        headers=headers,
    )
    response_2 = client.post(
        "/api/workflows/wf_123/execute",
        json={"initial_input": {"k": 999}},
        headers=headers,
    )

    assert response_1.status_code == 200
    assert response_2.status_code == 200
    assert response_1.json() == response_2.json()
    assert execute_calls == [{"workflow_id": "wf_123", "input_data": {"k": 1}}]

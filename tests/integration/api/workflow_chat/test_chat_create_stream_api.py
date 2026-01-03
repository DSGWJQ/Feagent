"""测试：chat-create SSE API（创建 workflow + 首次对话规划流）.

覆盖点（WCC-040）：
- POST /api/workflows/chat-create/stream 端点可用
- SSE 前 1 个事件内包含 metadata.workflow_id
- 输入为空返回 422（pydantic 校验）
- LLM 不可用返回 503（依赖注入阶段）
- LLM/处理报错时，通过 SSE error 事件可诊断（不泄露敏感信息）
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.value_objects.node_type import NodeType
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.rag import get_rag_service
from src.interfaces.api.routes import workflows as workflows_routes


def _parse_sse_events(text: str) -> list[dict]:
    events: list[dict] = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            continue
        events.append(json.loads(payload))
    return events


@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(test_engine):
    test_app = FastAPI()
    test_app.include_router(workflows_routes.router, prefix="/api")

    class _NoopToolRepository:
        def exists(self, _tool_id: str) -> bool:
            return True

        def find_by_id(self, _tool_id: str):
            return None

    class _NoopUserRepository:
        def find_by_id(self, _user_id: str):
            return None

    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def override_get_rag_service():
        yield object()

    def _fake_repo(_: Session):
        raise AssertionError("unexpected repository dependency in this test")

    test_app.state.container = ApiContainer(
        executor_registry=NodeExecutorRegistry(),
        workflow_execution_kernel=lambda _: None,  # type: ignore[return-value]
        conversation_turn_orchestrator=lambda: None,  # type: ignore[return-value]
        user_repository=lambda _: _NoopUserRepository(),
        agent_repository=_fake_repo,
        task_repository=_fake_repo,
        workflow_repository=lambda db: SQLAlchemyWorkflowRepository(db),
        chat_message_repository=_fake_repo,
        llm_provider_repository=_fake_repo,
        tool_repository=lambda _: _NoopToolRepository(),
        run_repository=_fake_repo,
        scheduled_workflow_repository=_fake_repo,
    )

    test_app.dependency_overrides[get_db_session] = override_get_db_session
    test_app.dependency_overrides[get_rag_service] = override_get_rag_service
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


class _FakeUseCase:
    def __init__(self, workflow_id: str, *, raise_exc: Exception | None = None) -> None:
        self._workflow_id = workflow_id
        self._raise_exc = raise_exc

    async def execute_streaming(self, _input_data):
        if self._raise_exc:
            raise self._raise_exc

        yield {
            "type": "workflow_updated",
            "ai_message": "ok",
            "workflow": {"id": self._workflow_id, "nodes": [], "edges": []},
        }


class TestChatCreateStreamAPI:
    def test_success_includes_workflow_id_in_first_event(self, client: TestClient, test_engine):
        def override_use_case_factory() -> Callable[[str], object]:
            def factory(workflow_id: str):
                return _FakeUseCase(workflow_id)

            return factory

        client.app.dependency_overrides[
            workflows_routes.get_update_workflow_by_chat_use_case_factory
        ] = override_use_case_factory

        response = client.post(
            "/api/workflows/chat-create/stream",
            json={"message": "hello", "project_id": "proj_1", "run_id": "run_1"},
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert len(events) >= 2  # thinking + final

        first = events[0]
        assert first["type"] == "thinking"
        assert first["metadata"]["workflow_id"].startswith("wf_")
        assert first["metadata"]["project_id"] == "proj_1"
        assert first["metadata"]["run_id"] == "run_1"

        workflow_id = first["metadata"]["workflow_id"]
        assert any(
            e.get("type") == "final"
            and e.get("metadata", {}).get("workflow", {}).get("id") == workflow_id
            for e in events
        )

        # Ensure workflow is persisted with project_id
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db: Session = TestingSessionLocal()
        try:
            repo = SQLAlchemyWorkflowRepository(db)
            workflow = repo.get_by_id(workflow_id)
            assert workflow is not None
            assert workflow.project_id == "proj_1"
            assert len(workflow.nodes) >= 2
            start_node = next(node for node in workflow.nodes if node.type == NodeType.START)
            end_node = next(node for node in workflow.nodes if node.type == NodeType.END)
            assert any(
                edge.source_node_id == start_node.id and edge.target_node_id == end_node.id
                for edge in workflow.edges
            )
        finally:
            db.close()

    def test_empty_message_returns_422(self, client: TestClient):
        response = client.post(
            "/api/workflows/chat-create/stream",
            json={"message": ""},
        )
        assert response.status_code == 422

    def test_llm_unavailable_returns_503(self, client: TestClient):
        def override_get_workflow_chat_llm():
            raise HTTPException(status_code=503, detail="LLM unavailable")

        client.app.dependency_overrides[workflows_routes.get_workflow_chat_llm] = (
            override_get_workflow_chat_llm
        )

        response = client.post(
            "/api/workflows/chat-create/stream",
            json={"message": "hello"},
        )
        assert response.status_code == 503

    def test_llm_error_emits_sse_error_event_and_deletes_base_workflow(
        self, client: TestClient, test_engine
    ):
        def override_use_case_factory() -> Callable[[str], object]:
            def factory(workflow_id: str):
                return _FakeUseCase(workflow_id, raise_exc=DomainError("LLM error"))

            return factory

        client.app.dependency_overrides[
            workflows_routes.get_update_workflow_by_chat_use_case_factory
        ] = override_use_case_factory

        response = client.post(
            "/api/workflows/chat-create/stream",
            json={"message": "hello"},
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert events[0]["metadata"]["workflow_id"].startswith("wf_")
        assert any(e.get("type") == "error" for e in events)

        # fail-closed: should not leave a half-created workflow in DB
        workflow_id = events[0]["metadata"]["workflow_id"]
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db: Session = TestingSessionLocal()
        try:
            repo = SQLAlchemyWorkflowRepository(db)
            assert repo.find_by_id(workflow_id) is None
        finally:
            db.close()

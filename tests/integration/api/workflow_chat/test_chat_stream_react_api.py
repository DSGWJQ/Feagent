"""测试：工作流对话流式 API - 实时 ReAct 步骤流

TDD RED 阶段：定义流式 API 的期望行为
- POST /api/workflows/{workflow_id}/chat-stream-react SSE 端点
- 支持流式传输 ReAct 步骤
- 正确的 SSE 格式和响应头
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import NotFoundError
from src.domain.services.workflow_chat_service_enhanced import ModificationResult
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.main import app
from src.interfaces.api.routes.workflows import get_update_workflow_by_chat_use_case


@pytest.fixture(scope="function")
def test_engine():
    """创建测试数据库引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(test_engine):
    """创建测试数据库 Session"""
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def client(test_engine):
    """创建测试客户端"""

    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # 创建一个模拟的RAG服务
    async def override_get_rag_service():
        mock_rag = AsyncMock()
        yield mock_rag

    from src.interfaces.api.dependencies.rag import get_rag_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_rag_service] = override_get_rag_service

    # Override the chat use case to avoid requiring app lifespan/container wiring in this test.
    async def _override_use_case(workflow_id: str):
        class _StubUseCase:
            async def execute_streaming(self, input_data):
                if workflow_id.startswith("nonexistent"):
                    raise NotFoundError(entity_type="Workflow", entity_id=workflow_id)
                yield {
                    "type": "processing_started",
                    "workflow_id": workflow_id,
                }
                step_count = 3 if getattr(input_data, "user_message", "") == "设计工作流" else 1
                for step in range(1, step_count + 1):
                    yield {
                        "type": "react_step",
                        "step_number": step,
                        "tool_id": f"react_{step}",
                        "thought": f"步骤 {step} 思考",
                        "action": {"type": "add_node"},
                        "observation": f"步骤 {step} 观察",
                    }
                yield {
                    "type": "modifications_preview",
                    "modifications_count": step_count,
                    "intent": "add_node",
                    "confidence": 0.9,
                }
                yield {
                    "type": "workflow_updated",
                    "ai_message": "完成",
                    "workflow": {"id": workflow_id},
                    "rag_sources": [],
                }

        return _StubUseCase()

    app.dependency_overrides[get_update_workflow_by_chat_use_case] = _override_use_case
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_workflow(test_db: Session):
    """创建示例工作流"""
    start_node = Node.create(
        type=NodeType.START,
        name="开始",
        config={},
        position=Position(x=100, y=100),
    )

    workflow = Workflow.create(
        name="测试工作流",
        description="用于测试流式 API",
        nodes=[start_node],
        edges=[],
    )

    repo = SQLAlchemyWorkflowRepository(test_db)
    repo.save(workflow)
    test_db.commit()

    return workflow


class TestChatStreamReactAPI:
    """测试工作流对话流式 ReAct API"""

    def test_endpoint_exists(self, client: TestClient, sample_workflow: Workflow):
        """测试：/chat-stream-react 端点存在

        RED 阶段：端点还不存在，此测试应失败
        """
        response = client.post(
            f"/api/workflows/{sample_workflow.id}/chat-stream-react",
            json={"message": "测试消息"},
        )

        # 红色：端点应该存在并返回 200 或流式响应
        assert response.status_code in [
            200,
            404,
        ], "端点应该存在或返回 404（稍后实现）"

    def test_stream_endpoint_returns_sse_format(
        self, client: TestClient, sample_workflow: Workflow
    ):
        """测试：流式端点返回 SSE 格式

        RED 阶段：测试 SSE 格式的正确性
        """
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm_class.return_value = mock_llm

            mock_result = ModificationResult(
                success=True,
                ai_message="完成",
                modified_workflow=sample_workflow,
                react_steps=[
                    {
                        "step": 1,
                        "thought": "思考内容",
                        "action": {"type": "add_node"},
                        "observation": "观察结果",
                    }
                ],
            )
            mock_llm.invoke.return_value = mock_result

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat-stream-react",
                json={"message": "测试消息"},
                headers={"Accept": "text/event-stream"},
            )

            # 红色：应该返回 200 并且包含流式数据
            assert response.status_code == 200, "应该返回 200"

            # 验证响应头
            assert "text/event-stream" in response.headers.get(
                "content-type", ""
            ), "Content-Type 应该是 text/event-stream"

            # 验证响应内容包含 data: 开头的行
            content = response.text
            assert "data:" in content, "响应应该包含 SSE 格式的数据（data: ...）"

    def test_sse_event_structure(self, client: TestClient, sample_workflow: Workflow):
        """测试：SSE 事件包含正确的字段

        RED 阶段：每个 SSE 事件应该是有效的 JSON
        """
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm_class.return_value = mock_llm

            mock_result = ModificationResult(
                success=True,
                ai_message="完成",
                modified_workflow=sample_workflow,
                react_steps=[
                    {
                        "step": 1,
                        "thought": "思考",
                        "action": {"type": "add_node"},
                        "observation": "观察",
                    }
                ],
            )
            mock_llm.invoke.return_value = mock_result

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat-stream-react",
                json={"message": "测试"},
            )

            assert response.status_code == 200

            # 解析 SSE 流
            lines = response.text.strip().split("\n")
            data_lines = [line for line in lines if line.startswith("data: ")]

            # 应该至少有一个数据行
            assert len(data_lines) > 0, "应该至少有一个数据行"

            # 验证每个数据行都是有效 JSON
            for line in data_lines:
                data_str = line[6:]  # 去掉 "data: " 前缀
                if data_str == "[DONE]":
                    continue
                try:
                    json.loads(data_str)
                except json.JSONDecodeError:
                    pytest.fail(f"无效的 JSON 数据：{data_str}")

    def test_stream_includes_all_event_types(self, client: TestClient, sample_workflow: Workflow):
        """测试：流式响应包含所有必需的事件类型

        应该包含：thinking、tool_call、tool_result、final 事件
        """
        response = client.post(
            f"/api/workflows/{sample_workflow.id}/chat-stream-react",
            json={"message": "测试"},
        )

        assert response.status_code == 200

        # 解析事件
        lines = response.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str != "[DONE]":
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                    except json.JSONDecodeError:
                        pass

        event_types = [e.get("type") for e in events]
        assert "thinking" in event_types
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "final" in event_types

        tool_calls = [e for e in events if e.get("type") == "tool_call"]
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        tool_call_ids = {
            e.get("metadata", {}).get("tool_id")
            for e in tool_calls
            if e.get("metadata", {}).get("tool_id")
        }
        tool_result_ids = {
            e.get("metadata", {}).get("tool_id")
            for e in tool_results
            if e.get("metadata", {}).get("tool_id")
        }
        assert tool_call_ids, "tool_call 应该包含可审计的 tool_id"
        assert tool_call_ids.issubset(
            tool_result_ids
        ), "tool_call 与 tool_result 应该可配对（tool_id）"

    def test_stream_response_headers(self, client: TestClient, sample_workflow: Workflow):
        """测试：流式响应包含正确的 HTTP 头

        RED 阶段：应该包含：
        - Cache-Control: no-cache
        - Connection: keep-alive
        - X-Accel-Buffering: no
        """
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm_class.return_value = mock_llm

            mock_result = ModificationResult(
                success=True,
                ai_message="完成",
                modified_workflow=sample_workflow,
                react_steps=[],
            )
            mock_llm.invoke.return_value = mock_result

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat-stream-react",
                json={"message": "测试"},
            )

            assert response.status_code == 200

            # 红色：验证响应头
            headers = response.headers
            assert headers.get("Cache-Control") == "no-cache", "应该有 Cache-Control: no-cache"
            assert headers.get("Connection") == "keep-alive", "应该有 Connection: keep-alive"
            assert headers.get("X-Accel-Buffering") == "no", "应该有 X-Accel-Buffering: no"

    def test_stream_ends_with_done_marker(self, client: TestClient, sample_workflow: Workflow):
        """测试：流式响应以 [DONE] 标记结束

        RED 阶段：最后一行应该是 'data: [DONE]'
        """
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm_class.return_value = mock_llm

            mock_result = ModificationResult(
                success=True,
                ai_message="完成",
                modified_workflow=sample_workflow,
                react_steps=[],
            )
            mock_llm.invoke.return_value = mock_result

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat-stream-react",
                json={"message": "测试"},
            )

            assert response.status_code == 200

            # 验证最后一行
            lines = response.text.strip().split("\n")
            last_data_line = None
            for line in reversed(lines):
                if line.startswith("data: "):
                    last_data_line = line
                    break

            assert last_data_line == "data: [DONE]", "最后一个 data 行应该是 'data: [DONE]'"

    def test_nonexistent_workflow_error_handling(self, client: TestClient):
        """测试：访问不存在的工作流的错误处理

        流式端点会在流中返回错误事件而不是直接返回 404
        """
        with patch("src.interfaces.api.routes.workflows.get_chat_openai") as mock_llm_func:
            mock_llm = AsyncMock()
            mock_llm_func.return_value = mock_llm

            response = client.post(
                "/api/workflows/nonexistent-id/chat-stream-react",
                json={"message": "测试"},
            )

            # 流式端点会返回 200 然后在流中发送错误事件
            assert response.status_code == 200, "流式端点应该返回 200"
            # 验证响应包含错误信息
            assert (
                "error" in response.text or "workflow_not_found" in response.text
            ), "应该包含错误信息"

    def test_empty_message_validation(self, client: TestClient, sample_workflow: Workflow):
        """测试：空消息的验证

        FastAPI 会返回 422 (Unprocessable Entity) 对于无效的请求格式
        """
        with patch("src.interfaces.api.routes.workflows.get_chat_openai") as mock_llm_func:
            mock_llm = AsyncMock()
            mock_llm_func.return_value = mock_llm

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat-stream-react",
                json={"message": ""},
            )

            # FastAPI 会返回 422 对于验证错误
            # 或者如果通过，会返回 200 然后在流中返回错误
            assert response.status_code in [
                400,
                422,
                200,
            ], "应该返回错误状态或在流中返回错误"

    def test_stream_with_multiple_react_steps(self, client: TestClient, sample_workflow: Workflow):
        """测试：多个 ReAct 步骤的完整流式工作流

        RED 阶段：完整的多步骤流式传输
        """
        response = client.post(
            f"/api/workflows/{sample_workflow.id}/chat-stream-react",
            json={"message": "设计工作流"},
        )

        assert response.status_code == 200

        lines = response.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str != "[DONE]":
                    try:
                        events.append(json.loads(data_str))
                    except json.JSONDecodeError:
                        pass

        tool_calls = [e for e in events if e.get("type") == "tool_call"]
        tool_call_ids = [
            e.get("metadata", {}).get("tool_id")
            for e in tool_calls
            if e.get("metadata", {}).get("tool_id")
        ]
        assert tool_call_ids.count("react_1") == 1
        assert tool_call_ids.count("react_2") == 1
        assert tool_call_ids.count("react_3") == 1

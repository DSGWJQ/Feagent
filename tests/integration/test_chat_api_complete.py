"""完整的 Chat API 集成测试

真实场景：通过 HTTP 请求测试所有 Chat API 端点
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entities.chat_message import ChatMessage
from src.infrastructure.database import models  # noqa: F401 - 导入整个模块以注册所有模型
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import WorkflowModel
from src.infrastructure.database.repositories.chat_message_repository import (
    SQLAlchemyChatMessageRepository,
)
from src.interfaces.api.routes.chat_workflows_complete import router


@pytest.fixture
def test_app():
    """创建测试 FastAPI 应用"""
    app = FastAPI()
    app.include_router(router)

    # 创建测试数据库
    # 使用 StaticPool 确保所有操作使用同一个连接，避免 SQLite :memory: 的隔离问题
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # 覆盖依赖注入
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from src.infrastructure.database.engine import get_db_session

    app.dependency_overrides[get_db_session] = override_get_db

    # 创建测试数据
    db = TestingSessionLocal()
    workflow = WorkflowModel(
        id="wf_test_api",
        name="API测试工作流",
        description="用于API测试",
        status="draft",
    )
    db.add(workflow)

    # 添加一些测试消息
    repo = SQLAlchemyChatMessageRepository(db)
    repo.save(ChatMessage.create("wf_test_api", "添加HTTP节点", True))
    repo.save(ChatMessage.create("wf_test_api", "已添加HTTP节点", False))
    repo.save(ChatMessage.create("wf_test_api", "添加数据库节点", True))
    db.commit()
    db.close()

    return app


def test_get_chat_history(test_app):
    """测试：GET /api/workflows/{workflow_id}/chat-history"""
    client = TestClient(test_app)

    response = client.get("/api/workflows/wf_test_api/chat-history")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert data[0]["content"] == "添加HTTP节点"
    assert data[0]["is_user"] is True
    assert data[1]["content"] == "已添加HTTP节点"
    assert data[1]["is_user"] is False


def test_search_chat_history(test_app):
    """测试：GET /api/workflows/{workflow_id}/chat-search"""
    client = TestClient(test_app)

    response = client.get("/api/workflows/wf_test_api/chat-search?query=HTTP")

    assert response.status_code == 200
    data = response.json()

    assert len(data) >= 2  # 应该找到包含"HTTP"的消息
    assert "HTTP" in data[0]["message"]["content"]
    assert "relevance_score" in data[0]
    assert data[0]["relevance_score"] > 0.5


def test_get_suggestions(test_app):
    """测试：GET /api/workflows/{workflow_id}/suggestions"""
    client = TestClient(test_app)

    response = client.get("/api/workflows/wf_test_api/suggestions")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0  # 应该至少有一些建议


def test_clear_chat_history(test_app):
    """测试：DELETE /api/workflows/{workflow_id}/chat-history"""
    client = TestClient(test_app)

    # 删除历史
    response = client.delete("/api/workflows/wf_test_api/chat-history")
    assert response.status_code == 204

    # 验证：历史已清空
    response = client.get("/api/workflows/wf_test_api/chat-history")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_chat_context(test_app):
    """测试：GET /api/workflows/{workflow_id}/chat-context"""
    client = TestClient(test_app)

    response = client.get("/api/workflows/wf_test_api/chat-context?max_tokens=1000")

    assert response.status_code == 200
    data = response.json()

    assert "messages" in data
    assert "total_tokens" in data
    assert "compression_ratio" in data
    assert isinstance(data["messages"], list)
    assert data["total_tokens"] <= 1000

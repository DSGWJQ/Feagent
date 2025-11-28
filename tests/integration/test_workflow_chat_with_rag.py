"""测试：带RAG的工作流对话 API - 集成测试

TDD RED 阶段：定义期望行为
- RAG上下文检索和使用
- 知识库引用
- RAG与对话历史结合
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.main import app


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


# Global mock RAG service for testing
_mock_rag_service = None


@pytest.fixture
def client(test_engine):
    """创建测试客户端"""
    global _mock_rag_service

    def override_get_db_session():
        TestingSessionLocal = sessionmaker(bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # 创建一个模拟的RAG服务
    async def override_get_rag_service():
        global _mock_rag_service
        _mock_rag_service = AsyncMock()
        yield _mock_rag_service

    from src.interfaces.api.dependencies.rag import get_rag_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_rag_service] = override_get_rag_service
    yield TestClient(app)
    app.dependency_overrides.clear()
    _mock_rag_service = None


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
        description="用于测试RAG功能",
        nodes=[start_node],
        edges=[],
    )

    repo = SQLAlchemyWorkflowRepository(test_db)
    repo.save(workflow)
    test_db.commit()

    return workflow


class TestWorkflowChatWithRAG:
    """测试带RAG的工作流对话"""

    def test_chat_with_rag_retrieval(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：对话中使用RAG检索知识库

        真实场景：
        1. 用户：\"我想添加一个用于发送邮件的节点\"
        2. 系统从知识库检索相关的邮件节点配置
        3. AI基于检索到的知识库内容提供更专业的回复

        期望行为：
        - 返回结果包含 rag_sources 字段
        - AI 回复中引用了知识库内容
        - 节点配置参考了知识库的最佳实践
        """
        # Mock LLM 服务
        from src.application.services.rag_service import RetrievedContext
        from src.interfaces.api.dependencies.rag import get_rag_service

        # 创建RAG服务mock
        mock_rag_service = AsyncMock()
        mock_rag_service.retrieve_context.return_value = RetrievedContext(
            chunks=[],  # 空列表，因为我们只需要formatted_context和sources
            formatted_context="邮件节点配置示例：使用SMTP协议，需要配置服务器地址、端口、认证信息...",
            sources=[
                {
                    "title": "邮件节点最佳实践.md",
                    "relevance_score": 0.95,
                    "content": "SMTP配置说明...",
                }
            ],
            total_tokens=150,
        )

        # Override RAG service
        async def override_rag():
            yield mock_rag_service

        app.dependency_overrides[get_rag_service] = override_rag

        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            # Mock LLM 返回（基于RAG上下文生成）
            llm_response = Mock()
            llm_response.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.92,
                    "nodes_to_add": [
                        {
                            "type": "notification",
                            "name": "send_email",
                            "config": {
                                "smtp_server": "smtp.example.com",
                                "smtp_port": 587,
                                "use_tls": True,
                            },
                            "position": {"x": 300, "y": 100},
                        }
                    ],
                    "ai_message": "已添加邮件发送节点，配置参考了最佳实践文档",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = llm_response

            # 发送请求
            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "我想添加一个用于发送邮件的节点"},
            )

            # 验证响应
            assert response.status_code == 200
            data = response.json()

            # RED 阶段：这些断言应该失败
            assert "rag_sources" in data, "响应缺少 rag_sources 字段"
            assert len(data["rag_sources"]) > 0, "未检索到RAG来源"

            # 验证知识库被引用
            first_source = data["rag_sources"][0]
            assert "title" in first_source
            assert "relevance_score" in first_source
            assert first_source["title"] == "邮件节点最佳实践.md"

            # 验证 RAG 服务被调用
            assert mock_rag_service.retrieve_context.called, "RAG服务未被调用"

        app.dependency_overrides.pop(get_rag_service, None)

    def test_chat_with_rag_and_conversation_history(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：RAG与对话历史结合使用

        真实场景：
        1. 第一轮：用户询问\"如何处理用户注册\"
        2. 系统从知识库检索注册流程最佳实践
        3. 第二轮：用户说\"按照刚才的方案添加节点\"
        4. 系统结合对话历史和知识库内容添加节点

        期望行为：
        - 第一轮返回知识库引用
        - 第二轮能够理解\"刚才的方案\"（对话历史）
        - 第二轮能够继续使用知识库内容
        """
        from src.application.services.rag_service import RetrievedContext
        from src.interfaces.api.dependencies.rag import get_rag_service

        # 创建RAG服务mock
        mock_rag_service = AsyncMock()

        # 第一轮：检索知识库
        mock_rag_service.retrieve_context.return_value = RetrievedContext(
            chunks=[],
            formatted_context="用户注册流程：1. 验证邮箱 2. 创建账户 3. 发送欢迎邮件",
            sources=[
                {
                    "title": "用户注册最佳实践.md",
                    "relevance_score": 0.88,
                }
            ],
            total_tokens=100,
        )

        # Override RAG service
        async def override_rag():
            yield mock_rag_service

        app.dependency_overrides[get_rag_service] = override_rag

        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            response1_mock = Mock()
            response1_mock.content = json.dumps(
                {
                    "intent": "ask_clarification",
                    "confidence": 0.85,
                    "ai_message": "用户注册流程通常包含：邮箱验证、账户创建、发送欢迎邮件三个步骤",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = response1_mock

            response1 = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "如何处理用户注册"},
            )

            assert response1.status_code == 200
            data1 = response1.json()
            assert "rag_sources" in data1

            # 第二轮：结合对话历史和知识库
            response2_mock = Mock()
            response2_mock.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.90,
                    "nodes_to_add": [
                        {
                            "type": "httpRequest",
                            "name": "validate_email",
                            "config": {"method": "POST"},
                            "position": {"x": 300, "y": 100},
                        }
                    ],
                    "ai_message": "根据刚才讨论的注册流程，我添加了邮箱验证节点",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = response2_mock

            response2 = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "按照刚才的方案添加第一个节点"},
            )

            assert response2.status_code == 200
            data2 = response2.json()

            # 验证对话历史和RAG结合
            nodes = data2["workflow"]["nodes"]
            assert len(nodes) == 2  # start + validate_email

            # 验证 AI 回复理解了\"刚才\"（对话历史）
            assert "刚才" in data2["ai_message"] or "注册" in data2["ai_message"]

        app.dependency_overrides.pop(get_rag_service, None)

    def test_chat_without_rag_when_no_knowledge_found(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：知识库无相关内容时优雅降级

        期望行为：
        - RAG 检索失败或无结果时，不中断流程
        - 继续使用对话历史和LLM基础能力
        - rag_sources 为空列表
        """
        from src.application.services.rag_service import RetrievedContext
        from src.interfaces.api.dependencies.rag import get_rag_service

        # 创建RAG服务mock
        mock_rag_service = AsyncMock()

        # Mock RAG 无结果
        mock_rag_service.retrieve_context.return_value = RetrievedContext(
            chunks=[],
            formatted_context="",
            sources=[],
            total_tokens=0,
        )

        # Override RAG service
        async def override_rag():
            yield mock_rag_service

        app.dependency_overrides[get_rag_service] = override_rag

        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            response_mock = Mock()
            response_mock.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.75,
                    "nodes_to_add": [
                        {
                            "type": "httpRequest",
                            "name": "custom_node",
                            "config": {},
                            "position": {"x": 200, "y": 100},
                        }
                    ],
                    "ai_message": "已添加自定义节点",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = response_mock

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "添加一个自定义节点"},
            )

            assert response.status_code == 200
            data = response.json()

            # 验证降级处理
            assert "rag_sources" in data
            assert data["rag_sources"] == []  # 无RAG来源

            # 验证工作流仍然被正确修改
            nodes = data["workflow"]["nodes"]
            assert len(nodes) == 2  # start + custom_node

        app.dependency_overrides.pop(get_rag_service, None)

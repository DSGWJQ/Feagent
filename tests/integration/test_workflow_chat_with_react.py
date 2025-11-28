"""测试：带ReAct循环的工作流对话 API - 推理与行动

TDD RED 阶段：定义期望行为
- ReAct 循环：思考 → 行动 → 观察
- 复杂工作流设计的多步推理
- 完整的工作流规划与执行
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
        description="用于测试ReAct功能",
        nodes=[start_node],
        edges=[],
    )

    repo = SQLAlchemyWorkflowRepository(test_db)
    repo.save(workflow)
    test_db.commit()

    return workflow


class TestWorkflowChatWithReAct:
    """测试带ReAct循环的工作流对话"""

    def test_chat_with_react_loop_for_complex_workflow(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：使用ReAct循环设计复杂工作流

        真实场景：
        用户需求：\"我需要一个用户认证工作流，包括：
        1. 接收用户登录请求
        2. 验证用户凭证
        3. 如果成功，生成JWT令牌；失败则返回错误\"

        ReAct循环过程：
        第1步：思考 → \"需要3个主要步骤\"
        第2步：行动 → 添加HTTP请求节点
        第3步：观察 → 确认节点已添加
        第4步：思考 → \"现在需要添加认证逻辑\"
        第5步：行动 → 添加条件节点
        ... 重复直到完成

        期望行为：
        - 返回 react_steps 字段表示推理步骤
        - 每个步骤包含：thought、action、observation
        - 最终工作流包含完整的认证逻辑
        - 节点之间的连接正确
        """
        # RED 阶段：这个测试现在应该失败
        # 因为API还不支持 react_steps
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            # Mock LLM 返回 ReAct 格式的响应
            llm_response = Mock()
            llm_response.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.95,
                    "nodes_to_add": [
                        {
                            "type": "httpRequest",
                            "name": "receive_login",
                            "config": {"method": "POST", "path": "/login"},
                            "position": {"x": 200, "y": 100},
                        },
                        {
                            "type": "python",
                            "name": "verify_credentials",
                            "config": {"language": "python"},
                            "position": {"x": 400, "y": 100},
                        },
                        {
                            "type": "conditional",
                            "name": "check_verification",
                            "config": {"condition": "result.success"},
                            "position": {"x": 600, "y": 100},
                        },
                    ],
                    "react_steps": [
                        {
                            "step": 1,
                            "thought": "用户需要认证流程。首先需要接收登录请求的节点",
                            "action": {
                                "type": "add_node",
                                "node": {
                                    "type": "httpRequest",
                                    "name": "receive_login",
                                    "config": {"method": "POST", "path": "/login"},
                                    "position": {"x": 200, "y": 100},
                                },
                            },
                            "observation": "HTTP请求节点已添加，位置为(200, 100)",
                        },
                        {
                            "step": 2,
                            "thought": "现在需要验证凭证的节点",
                            "action": {
                                "type": "add_node",
                                "node": {
                                    "type": "python",
                                    "name": "verify_credentials",
                                    "config": {"language": "python"},
                                    "position": {"x": 400, "y": 100},
                                },
                            },
                            "observation": "Python执行节点已添加用于凭证验证",
                        },
                        {
                            "step": 3,
                            "thought": "需要条件分支来处理成功/失败情况",
                            "action": {
                                "type": "add_node",
                                "node": {
                                    "type": "conditional",
                                    "name": "check_verification",
                                    "config": {"condition": "result.success"},
                                    "position": {"x": 600, "y": 100},
                                },
                            },
                            "observation": "条件节点已添加",
                        },
                    ],
                    "ai_message": "我已通过3步推理和行动完成了用户认证工作流。流程包括：接收请求→验证凭证→条件判断",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = llm_response

            # 发送复杂请求
            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={
                    "message": "我需要一个用户认证工作流，包括：1. 接收用户登录请求；2. 验证用户凭证；3. 如果成功生成JWT令牌，失败返回错误"
                },
            )

            # RED 阶段：这些断言应该失败
            assert response.status_code == 200
            data = response.json()

            # 期望包含 react_steps
            assert "react_steps" in data, "响应缺少 react_steps 字段"
            assert isinstance(data["react_steps"], list), "react_steps 应该是列表"
            assert len(data["react_steps"]) >= 3, "应该至少有3个推理步骤"

            # 验证步骤结构
            first_step = data["react_steps"][0]
            assert "step" in first_step, "步骤缺少 step 字段"
            assert "thought" in first_step, "步骤缺少 thought 字段"
            assert "action" in first_step, "步骤缺少 action 字段"
            assert "observation" in first_step, "步骤缺少 observation 字段"

            # 验证工作流包含所有添加的节点
            nodes = data["workflow"]["nodes"]
            node_names = {n["name"] for n in nodes}
            assert "receive_login" in node_names
            assert "verify_credentials" in node_names
            assert "check_verification" in node_names

            # 验证 AI 修改数量
            assert data["modifications_count"] >= 3, "应该进行至少3次修改"

    def test_react_step_execution_and_feedback(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：ReAct循环中每步的执行和反馈

        期望行为：
        - 用户请求可以触发多步ReAct循环
        - 每一步都能获得观察反馈
        - 错误在观察阶段被捕获
        - 最终工作流反映所有成功的步骤
        """
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            # Mock ReAct 循环（包括一些失败和恢复）
            llm_response = Mock()
            llm_response.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.92,
                    "react_steps": [
                        {
                            "step": 1,
                            "thought": "添加数据库查询节点",
                            "action": {
                                "type": "add_node",
                                "node": {
                                    "type": "database",
                                    "name": "query_users",
                                    "config": {"query": "SELECT * FROM users"},
                                    "position": {"x": 300, "y": 200},
                                },
                            },
                            "observation": "数据库节点成功添加",
                        },
                        {
                            "step": 2,
                            "thought": "尝试添加数据处理节点",
                            "action": {
                                "type": "add_node",
                                "node": {
                                    "type": "transform",
                                    "name": "process_data",
                                    "config": {"format": "json"},
                                    "position": {"x": 500, "y": 200},
                                },
                            },
                            "observation": "转换节点已添加",
                        },
                    ],
                    "ai_message": "已完成数据处理流程：数据库查询→数据转换",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = llm_response

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "添加数据库查询和处理流程"},
            )

            assert response.status_code == 200
            data = response.json()

            # RED 阶段：验证 react_steps 字段
            assert "react_steps" in data
            react_steps = data["react_steps"]

            # 验证每一步都有完整的信息
            for step in react_steps:
                assert step["thought"], "思考步骤不能为空"
                assert step["action"], "行动步骤不能为空"
                assert step["observation"], "观察步骤不能为空"

    def test_react_with_conversation_and_rag_context(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：ReAct循环结合对话历史和RAG上下文

        期望行为：
        - ReAct推理可以利用之前对话的信息
        - RAG检索的知识库内容影响推理步骤
        - 综合所有信息做出更好的设计决策
        """
        from src.application.services.rag_service import RetrievedContext
        from src.interfaces.api.dependencies.rag import get_rag_service

        # 设置 RAG 上下文
        mock_rag_service = AsyncMock()
        mock_rag_service.retrieve_context.return_value = RetrievedContext(
            chunks=[],
            formatted_context="微服务架构最佳实践：使用API网关、服务发现、断路器模式",
            sources=[
                {
                    "title": "微服务设计指南.md",
                    "relevance_score": 0.92,
                }
            ],
            total_tokens=80,
        )

        async def override_rag():
            yield mock_rag_service

        app.dependency_overrides[get_rag_service] = override_rag

        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            # 第一步：询问微服务架构
            llm_response1 = Mock()
            llm_response1.content = json.dumps(
                {
                    "intent": "ask_clarification",
                    "confidence": 0.88,
                    "ai_message": "微服务架构应该包含API网关和服务发现",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = llm_response1

            response1 = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "我想设计一个微服务架构"},
            )

            assert response1.status_code == 200
            data1 = response1.json()

            # 验证RAG内容被使用
            assert "微服务" in data1["ai_message"] or "网关" in data1["ai_message"]

            # 第二步：使用前面的信息进行ReAct推理
            llm_response2 = Mock()
            llm_response2.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.94,
                    "react_steps": [
                        {
                            "step": 1,
                            "thought": "根据知识库，需要API网关作为入口点",
                            "action": {
                                "type": "add_node",
                                "node": {
                                    "type": "httpRequest",
                                    "name": "api_gateway",
                                    "config": {"role": "gateway"},
                                    "position": {"x": 100, "y": 200},
                                },
                            },
                            "observation": "API网关节点已添加",
                        },
                        {
                            "step": 2,
                            "thought": "需要服务发现组件",
                            "action": {
                                "type": "add_node",
                                "node": {
                                    "type": "python",
                                    "name": "service_discovery",
                                    "config": {"type": "service_discovery"},
                                    "position": {"x": 300, "y": 200},
                                },
                            },
                            "observation": "服务发现节点已添加",
                        },
                    ],
                    "ai_message": "已根据微服务最佳实践设计架构",
                },
                ensure_ascii=False,
            )
            mock_llm.invoke.return_value = llm_response2

            response2 = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "根据刚才讨论的架构添加关键组件"},
            )

            assert response2.status_code == 200
            data2 = response2.json()

            # RED 阶段：验证 react_steps 结合了对话和RAG上下文
            assert "react_steps" in data2
            react_steps = data2["react_steps"]
            assert len(react_steps) >= 2

            # 验证思考包含了架构相关的信息
            thoughts = " ".join(step["thought"] for step in react_steps)
            assert "网关" in thoughts or "服务" in thoughts

        app.dependency_overrides.pop(get_rag_service, None)

"""测试：带记忆的工作流对话 API - 真实场景集成测试

TDD RED 阶段：定义期望行为
- 多轮对话中的指代消解
- 对话历史管理
- 意图识别和信心度
"""

import json
from unittest.mock import Mock, patch

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

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_workflow(test_db: Session):
    """创建示例工作流（只有开始节点）"""
    start_node = Node.create(
        type=NodeType.START,
        name="开始",
        config={},
        position=Position(x=100, y=100),
    )

    workflow = Workflow.create(
        name="测试工作流",
        description="用于测试多轮对话",
        nodes=[start_node],
        edges=[],
    )

    repo = SQLAlchemyWorkflowRepository(test_db)
    repo.save(workflow)
    test_db.commit()

    return workflow


class TestWorkflowChatWithMemory:
    """测试带记忆的工作流对话"""

    def test_multi_turn_chat_with_reference_to_previous_node(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：多轮对话中引用之前创建的节点

        真实场景：
        1. 用户："添加一个HTTP节点，名称叫weather_api"
        2. 用户："把它连接到开始节点"（"它" 指代 weather_api）

        期望行为：
        - 第一轮：成功添加 HTTP 节点
        - 第二轮：能够理解"它"指代 weather_api，成功创建边

        验收标准：
        - 第一轮后有 2 个节点（start + weather_api）
        - 第二轮后有 1 条边（start -> weather_api）
        - AI 回复中包含对"它"的理解
        """
        # Mock LLM 调用（只 mock LLM，保持其他逻辑真实）
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            # 设置 LLM mock 实例
            mock_llm_instance = Mock()
            mock_llm_class.return_value = mock_llm_instance

            # === 第一轮对话：添加节点 ===
            # Mock LLM 第一轮返回（添加 HTTP 节点）
            first_response = Mock()
            first_response.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.95,
                    "action": "add_node",
                    "nodes_to_add": [
                        {
                            "type": "httpRequest",
                            "name": "weather_api",
                            "config": {"url": "https://api.weather.com"},
                            "position": {"x": 300, "y": 100},
                        }
                    ],
                    "nodes_to_delete": [],
                    "edges_to_add": [],
                    "edges_to_delete": [],
                    "ai_message": "我已添加了名为 weather_api 的 HTTP 节点",
                },
                ensure_ascii=False,
            )
            mock_llm_instance.invoke.return_value = first_response

            response1 = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "添加一个HTTP节点，名称叫weather_api"},
            )

            # 验证第一轮结果
            assert response1.status_code == 200, f"第一轮请求失败: {response1.text}"
            data1 = response1.json()

            # 验证返回结构包含增强字段
            assert "workflow" in data1
            assert "ai_message" in data1
            # 期望：增强服务应该返回 intent 和 confidence
            # 如果没有这些字段，说明还在使用基础服务
            assert "intent" in data1, "缺少 intent 字段，可能未启用 EnhancedWorkflowChatService"
            assert "confidence" in data1, "缺少 confidence 字段"

            # 验证工作流状态
            nodes1 = data1["workflow"]["nodes"]
            assert len(nodes1) == 2, f"期望 2 个节点，实际 {len(nodes1)} 个"

            # 找到新添加的节点 ID
            weather_api_node = next((n for n in nodes1 if n["name"] == "weather_api"), None)
            assert weather_api_node is not None, "未找到 weather_api 节点"
            weather_api_node_id = weather_api_node["id"]

            # === 第二轮对话：连接节点（引用"它"）===
            # Mock LLM 第二轮返回（添加边，理解"它"指代 weather_api）
            start_node_id = next(n["id"] for n in nodes1 if n["name"] == "开始")

            second_response = Mock()
            second_response.content = json.dumps(
                {
                    "intent": "add_edge",
                    "confidence": 0.88,
                    "action": "add_edge",
                    "nodes_to_add": [],
                    "nodes_to_delete": [],
                    "edges_to_add": [
                        {
                            "source": start_node_id,
                            "target": weather_api_node_id,
                            "condition": None,
                        }
                    ],
                    "edges_to_delete": [],
                    "ai_message": "我理解'它'指的是 weather_api 节点，已将开始节点连接到它",
                },
                ensure_ascii=False,
            )
            mock_llm_instance.invoke.return_value = second_response

            response2 = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "把它连接到开始节点"},
            )

            # 验证第二轮结果
            assert response2.status_code == 200, f"第二轮请求失败: {response2.text}"
            data2 = response2.json()

            # 验证边已创建
            edges2 = data2["workflow"]["edges"]
            assert len(edges2) == 1, f"期望 1 条边，实际 {len(edges2)} 条"

            edge = edges2[0]
            assert edge["source"] == start_node_id, "边的起点不正确"
            assert edge["target"] == weather_api_node_id, "边的终点不正确"

            # 验证 AI 回复理解了"它"
            ai_message = data2["ai_message"]
            assert "weather_api" in ai_message or "它" in ai_message, "AI 回复未体现对指代的理解"

    def test_chat_service_maintains_conversation_history(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：对话服务维护对话历史

        真实场景：
        1. 用户多次修改工作流
        2. 询问"我刚才添加了什么？"
        3. 期望 AI 能够回顾历史记录

        验收标准：
        - 每次对话后历史记录增长
        - AI 能够引用之前的对话内容
        """
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = Mock()
            mock_llm_class.return_value = mock_llm_instance

            # 第一轮：添加节点
            response1 = Mock()
            response1.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.9,
                    "nodes_to_add": [
                        {
                            "type": "httpRequest",
                            "name": "api_node",
                            "config": {},
                            "position": {"x": 200, "y": 100},
                        }
                    ],
                    "ai_message": "已添加 API 节点",
                },
                ensure_ascii=False,
            )
            mock_llm_instance.invoke.return_value = response1

            client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "添加一个 HTTP 节点"},
            )

            # 第二轮：询问历史
            # 期望：LLM 应该收到包含对话历史的 prompt
            response2 = Mock()
            response2.content = json.dumps(
                {
                    "intent": "ask_clarification",
                    "confidence": 1.0,
                    "ai_message": "您刚才添加了一个 HTTP 节点（api_node）",
                },
                ensure_ascii=False,
            )
            mock_llm_instance.invoke.return_value = response2

            result = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "我刚才添加了什么？"},
            )

            assert result.status_code == 200

            # 检查 LLM 是否收到了对话历史
            # 注意：这里需要检查 invoke 的调用参数中是否包含历史
            # 当前基础服务不会传递历史，增强服务会传递
            llm_call_args = mock_llm_instance.invoke.call_args_list
            assert len(llm_call_args) >= 2, "LLM 应该被调用至少 2 次"

            # 获取第二次调用的参数
            second_call_messages = llm_call_args[1][0][0]  # 第二次调用的消息列表

            # 期望：如果使用增强服务，prompt 中应包含历史上下文
            # 将消息转为字符串检查
            prompt_text = str(second_call_messages)

            # 这是一个期望失败的断言（RED 阶段）
            # 因为当前基础服务不传递历史
            assert "对话历史" in prompt_text or "上下文" in prompt_text, (
                "LLM prompt 中应包含对话历史，但未找到"
            )


class TestWorkflowChatEnhancedFeatures:
    """测试增强对话功能"""

    def test_chat_returns_intent_and_confidence(
        self,
        client: TestClient,
        sample_workflow: Workflow,
    ):
        """测试：对话返回意图和信心度

        期望行为：
        - 响应中包含 intent 字段（用户意图类型）
        - 响应中包含 confidence 字段（AI 的信心度 0-1）
        - 响应中包含 modifications_count（修改数量）

        验收标准：
        - 返回结构包含这些字段
        - 字段值有意义（intent 非空，confidence 在 0-1 之间）
        """
        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = Mock()
            mock_llm_class.return_value = mock_llm_instance

            llm_response = Mock()
            llm_response.content = json.dumps(
                {
                    "intent": "add_node",
                    "confidence": 0.95,
                    "nodes_to_add": [
                        {
                            "type": "httpRequest",
                            "name": "test_node",
                            "config": {},
                            "position": {"x": 200, "y": 100},
                        }
                    ],
                    "ai_message": "已添加节点",
                },
                ensure_ascii=False,
            )
            mock_llm_instance.invoke.return_value = llm_response

            response = client.post(
                f"/api/workflows/{sample_workflow.id}/chat",
                json={"message": "添加一个节点"},
            )

            assert response.status_code == 200
            data = response.json()

            # RED 阶段：这些断言应该失败，因为当前未返回这些字段
            assert "intent" in data, "响应缺少 intent 字段"
            assert "confidence" in data, "响应缺少 confidence 字段"
            assert "modifications_count" in data, "响应缺少 modifications_count 字段"

            # 验证字段值
            assert data["intent"] in [
                "add_node",
                "delete_node",
                "add_edge",
                "modify_node",
            ], f"intent 值无效: {data['intent']}"
            assert 0 <= data["confidence"] <= 1, f"confidence 应在 0-1 之间: {data['confidence']}"

"""协调者上下文服务集成测试 - Phase 1

验证真实场景：
1. ConversationAgent 调用 CoordinatorAgent.get_context
2. 上下文信息被正确记录
3. 完整的规则库、知识库、工具库查询流程

运行命令：
    pytest tests/integration/test_coordinator_context_integration.py -v -s
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.domain.agents.conversation_agent import (
    ConversationAgent,
    ConversationAgentLLM,
)
from src.domain.agents.coordinator_agent import (
    ContextResponse,
    CoordinatorAgent,
    Rule,
)
from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus

# === Mock 实现 ===


@dataclass
class MockTool:
    """模拟工具"""

    id: str
    name: str
    description: str
    category: str = "general"
    status: str = "published"
    tags: list[str] = field(default_factory=list)


class MockToolRepository:
    """模拟工具仓库"""

    def __init__(self, tools: list[MockTool] | None = None):
        self._tools = tools or []

    def find_all(self) -> list[MockTool]:
        return self._tools

    def find_published(self) -> list[MockTool]:
        return [t for t in self._tools if t.status == "published"]

    def find_by_tags(self, tags: list[str]) -> list[MockTool]:
        result = []
        for tool in self._tools:
            if any(tag in tool.tags for tag in tags):
                result.append(tool)
        return result


class MockKnowledgeRetriever:
    """模拟知识检索器"""

    def __init__(self, results: list[dict[str, Any]] | None = None):
        self._results = results or []

    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        matched = []
        for item in self._results:
            content = item.get("content_preview", "") + item.get("title", "")
            if any(word in content.lower() for word in query.lower().split()):
                matched.append(item)
        return matched[:top_k]


class MockLLM(ConversationAgentLLM):
    """模拟 LLM"""

    async def think(self, context: dict[str, Any]) -> str:
        return "思考完成"

    async def decide_action(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"action": "respond", "response": "测试响应"}

    async def should_continue(self, context: dict[str, Any]) -> bool:
        return False

    async def decompose_goal(self, goal: str) -> list[dict[str, Any]]:
        return [{"id": "1", "description": goal}]

    async def plan_workflow(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"nodes": [], "edges": []}

    async def decompose_to_nodes(self, goal: str) -> list[dict[str, Any]]:
        return []

    async def replan_workflow(
        self,
        goal: str,
        failed_node_id: str,
        failure_reason: str,
        execution_context: dict[str, Any],
    ) -> dict[str, Any]:
        return {"nodes": [], "edges": []}


# === 测试类 ===


class TestCoordinatorContextIntegration:
    """协调者上下文服务集成测试"""

    @pytest.fixture
    def event_bus(self):
        """事件总线"""
        return EventBus()

    @pytest.fixture
    def sample_tools(self):
        """样例工具"""
        return [
            MockTool(
                id="tool_http",
                name="HTTP请求工具",
                description="发送HTTP请求到指定URL",
                category="http",
                tags=["http", "request", "api"],
            ),
            MockTool(
                id="tool_db",
                name="数据库查询工具",
                description="执行SQL查询操作",
                category="database",
                tags=["database", "sql", "query"],
            ),
            MockTool(
                id="tool_llm",
                name="LLM调用工具",
                description="调用大语言模型进行文本生成",
                category="ai",
                tags=["llm", "ai", "chat", "text"],
            ),
        ]

    @pytest.fixture
    def sample_knowledge(self):
        """样例知识库"""
        return [
            {
                "source_id": "kb_http_best_practices",
                "title": "HTTP请求最佳实践",
                "content_preview": "HTTP请求应该设置合适的超时时间和重试策略",
                "relevance_score": 0.95,
            },
            {
                "source_id": "kb_error_handling",
                "title": "API错误处理指南",
                "content_preview": "所有API调用应该有完善的错误处理逻辑",
                "relevance_score": 0.88,
            },
        ]

    @pytest.fixture
    def sample_rules(self):
        """样例规则"""
        return [
            Rule(
                id="rule_security",
                name="安全检查规则",
                description="检查请求是否包含敏感信息",
                priority=1,
            ),
            Rule(
                id="rule_rate_limit",
                name="频率限制规则",
                description="限制API调用频率",
                priority=2,
            ),
        ]

    @pytest.fixture
    def coordinator_agent(
        self,
        event_bus,
        sample_tools,
        sample_knowledge,
        sample_rules,
    ):
        """配置完整的协调者 Agent"""
        tool_repo = MockToolRepository(sample_tools)
        knowledge_retriever = MockKnowledgeRetriever(sample_knowledge)

        # 创建 mock circuit breaker 配置
        from unittest.mock import MagicMock

        mock_circuit_breaker = MagicMock()
        mock_circuit_breaker.is_open = False

        agent = CoordinatorAgent(
            event_bus=event_bus,
            knowledge_retriever=knowledge_retriever,
        )

        # 设置 circuit_breaker
        agent.circuit_breaker = mock_circuit_breaker

        for rule in sample_rules:
            agent.add_rule(rule)

        agent.tool_repository = tool_repo

        return agent

    @pytest.fixture
    def conversation_agent(self, event_bus, coordinator_agent):
        """配置对话 Agent"""
        session_context = SessionContext(
            global_context=GlobalContext(user_id="test_user"),
            session_id="test_session",
        )

        agent = ConversationAgent(
            session_context=session_context,
            llm=MockLLM(),
            event_bus=event_bus,
            coordinator=coordinator_agent,
        )

        return agent

    def test_coordinator_get_context_returns_complete_response(
        self,
        coordinator_agent,
    ):
        """测试：协调者 get_context 返回完整响应"""
        response = coordinator_agent.get_context("http request api")

        # 验证返回类型
        assert isinstance(response, ContextResponse)

        # 验证规则
        assert len(response.rules) == 2
        rule_names = [r["name"] for r in response.rules]
        assert "安全检查规则" in rule_names
        assert "频率限制规则" in rule_names

        # 验证工具
        assert len(response.tools) > 0
        tool_names = [t["name"] for t in response.tools]
        assert any("HTTP" in name for name in tool_names)

        # 验证摘要
        assert response.summary is not None
        assert len(response.summary) > 0

    @pytest.mark.asyncio
    async def test_coordinator_get_context_async_with_knowledge(
        self,
        coordinator_agent,
    ):
        """测试：协调者异步 get_context 包含知识库查询"""
        response = await coordinator_agent.get_context_async("HTTP 请求 错误")

        # 验证知识库查询结果
        assert len(response.knowledge) > 0
        titles = [k["title"] for k in response.knowledge]
        assert any("HTTP" in title or "错误" in title or "API" in title for title in titles)

    @pytest.mark.asyncio
    async def test_conversation_agent_calls_coordinator_get_context(
        self,
        conversation_agent,
        coordinator_agent,
        caplog,
    ):
        """测试：ConversationAgent 调用 CoordinatorAgent.get_context"""
        # 设置日志级别
        caplog.set_level(logging.INFO)

        # 运行 ConversationAgent
        result = await conversation_agent.run_async("发送一个 HTTP 请求")

        # 验证协调者上下文被调用和记录
        assert "Coordinator context retrieved" in caplog.text

        # 验证 _coordinator_context 被设置
        assert conversation_agent._coordinator_context is not None

    @pytest.mark.asyncio
    async def test_conversation_agent_handles_missing_coordinator(
        self,
        event_bus,
    ):
        """测试：ConversationAgent 在没有协调者时正常工作"""
        session_context = SessionContext(
            global_context=GlobalContext(user_id="test_user"),
            session_id="test_session",
        )

        # 不配置 coordinator
        agent = ConversationAgent(
            session_context=session_context,
            llm=MockLLM(),
            event_bus=event_bus,
            coordinator=None,
        )

        # 应该正常运行
        result = await agent.run_async("测试输入")

        # 上下文应该是 None
        assert agent._coordinator_context is None

    @pytest.mark.asyncio
    async def test_full_integration_scenario(
        self,
        conversation_agent,
        coordinator_agent,
        caplog,
    ):
        """测试：完整集成场景 - 用户请求到上下文获取"""
        caplog.set_level(logging.INFO)

        # 模拟用户输入
        user_input = "帮我 query database sql"

        # 运行对话 Agent
        result = await conversation_agent.run_async(user_input)

        # 验证上下文被获取
        context = conversation_agent._coordinator_context
        assert context is not None

        # 验证包含相关工具
        tool_names = [t["name"] for t in context.tools]
        assert len(tool_names) > 0

        # 验证包含规则
        assert len(context.rules) == 2

        # 验证日志记录
        assert "rules=" in caplog.text
        assert "tools=" in caplog.text

    def test_context_response_to_dict_serialization(self, coordinator_agent):
        """测试：ContextResponse 可以序列化为字典"""
        response = coordinator_agent.get_context("test query")

        # 转换为字典
        response_dict = response.to_dict()

        # 验证字典结构
        assert "rules" in response_dict
        assert "knowledge" in response_dict
        assert "tools" in response_dict
        assert "summary" in response_dict

        # 验证可以 JSON 序列化
        import json

        json_str = json.dumps(response_dict, ensure_ascii=False)
        assert len(json_str) > 0

    def test_context_with_workflow_state(self, coordinator_agent):
        """测试：获取包含工作流状态的上下文"""
        # 设置工作流状态
        workflow_id = "wf_test_integration"
        coordinator_agent.workflow_states[workflow_id] = {
            "workflow_id": workflow_id,
            "status": "running",
            "node_count": 5,
            "executed_nodes": ["node_1", "node_2"],
            "running_nodes": ["node_3"],
        }

        # 获取上下文
        response = coordinator_agent.get_context(
            "继续执行",
            workflow_id=workflow_id,
        )

        # 验证包含工作流上下文
        assert response.workflow_context is not None
        assert response.workflow_context["workflow_id"] == workflow_id
        assert response.workflow_context["status"] == "running"


class TestContextServiceErrorHandling:
    """上下文服务错误处理测试"""

    @pytest.fixture
    def faulty_knowledge_retriever(self):
        """会抛出异常的知识检索器"""

        class FaultyRetriever:
            async def retrieve_by_query(self, query, workflow_id=None, top_k=5):
                raise Exception("Knowledge retrieval failed")

        return FaultyRetriever()

    @pytest.fixture
    def coordinator_with_faulty_retriever(self, faulty_knowledge_retriever):
        """配置故障知识检索器的协调者"""
        return CoordinatorAgent(knowledge_retriever=faulty_knowledge_retriever)

    @pytest.mark.asyncio
    async def test_get_context_handles_knowledge_retrieval_error(
        self,
        coordinator_with_faulty_retriever,
    ):
        """测试：知识检索失败时返回空知识列表"""
        response = await coordinator_with_faulty_retriever.get_context_async("test")

        # 应该返回有效响应，知识列表为空
        assert response is not None
        assert response.knowledge == []

    @pytest.mark.asyncio
    async def test_conversation_agent_handles_context_error(
        self,
        faulty_knowledge_retriever,
        caplog,
    ):
        """测试：ConversationAgent 处理上下文获取错误"""
        from unittest.mock import MagicMock

        caplog.set_level(logging.WARNING)

        session_context = SessionContext(
            global_context=GlobalContext(user_id="test_user"),
            session_id="test_session",
        )

        coordinator = CoordinatorAgent(knowledge_retriever=faulty_knowledge_retriever)

        # 设置 mock circuit breaker
        mock_circuit_breaker = MagicMock()
        mock_circuit_breaker.is_open = False
        coordinator.circuit_breaker = mock_circuit_breaker

        agent = ConversationAgent(
            session_context=session_context,
            llm=MockLLM(),
            coordinator=coordinator,
        )

        # 应该正常运行，不会因为上下文错误而崩溃
        result = await agent.run_async("test input")

        # 上下文应该已获取（虽然知识为空）
        assert agent._coordinator_context is not None


# 导出
__all__ = [
    "TestCoordinatorContextIntegration",
    "TestContextServiceErrorHandling",
]

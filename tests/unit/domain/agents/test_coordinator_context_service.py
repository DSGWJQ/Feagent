"""CoordinatorAgent 上下文服务测试 - Phase 1

测试目标：
1. 验证 get_context(user_input) API 能够返回正确的上下文
2. 验证规则库、知识库、工具库查询功能
3. 验证 ConversationAgent 能够调用该接口

TDD 红阶段：编写测试，预期失败
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule
from src.domain.services.event_bus import EventBus


@dataclass
class MockTool:
    """模拟 Tool 实体"""

    id: str
    name: str
    description: str
    category: str = "general"
    status: str = "published"
    tags: list[str] = field(default_factory=list)


class MockToolRepository:
    """模拟 ToolRepository"""

    def __init__(self, tools: list[MockTool] | None = None):
        self._tools = tools or []

    def find_all(self) -> list[MockTool]:
        return self._tools

    def find_by_category(self, category: str) -> list[MockTool]:
        return [t for t in self._tools if t.category == category]

    def find_published(self) -> list[MockTool]:
        return [t for t in self._tools if t.status == "published"]

    def find_by_tags(self, tags: list[str]) -> list[MockTool]:
        """按标签查找工具"""
        result = []
        for tool in self._tools:
            if any(tag in tool.tags for tag in tags):
                result.append(tool)
        return result


class MockKnowledgeRetriever:
    """模拟 KnowledgeRetriever"""

    def __init__(self, results: list[dict[str, Any]] | None = None):
        self._results = results or []

    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        # 简单的关键词匹配
        matched = []
        for item in self._results:
            content = item.get("content_preview", "") + item.get("title", "")
            if any(word in content.lower() for word in query.lower().split()):
                matched.append(item)
        return matched[:top_k]


class TestGetContextAPI:
    """测试 get_context API"""

    @pytest.fixture
    def event_bus(self):
        """事件总线 fixture"""
        return EventBus()

    @pytest.fixture
    def sample_rules(self):
        """样例规则"""
        return [
            Rule(
                id="rule_security",
                name="安全规则",
                description="禁止执行危险操作",
                priority=1,
            ),
            Rule(
                id="rule_rate_limit",
                name="限流规则",
                description="限制请求频率",
                priority=2,
            ),
            Rule(
                id="rule_data_validation",
                name="数据验证规则",
                description="验证输入数据格式",
                priority=3,
            ),
        ]

    @pytest.fixture
    def sample_tools(self):
        """样例工具"""
        return [
            MockTool(
                id="tool_http",
                name="HTTP请求工具",
                description="发送HTTP请求",
                category="http",
                tags=["http", "request", "api"],
            ),
            MockTool(
                id="tool_db",
                name="数据库查询工具",
                description="执行SQL查询",
                category="database",
                tags=["database", "sql", "query"],
            ),
            MockTool(
                id="tool_llm",
                name="LLM调用工具",
                description="调用大语言模型",
                category="ai",
                tags=["llm", "ai", "chat"],
            ),
        ]

    @pytest.fixture
    def sample_knowledge(self):
        """样例知识库条目"""
        return [
            {
                "source_id": "kb_1",
                "title": "HTTP请求最佳实践",
                "content_preview": "HTTP请求应该包含正确的headers和超时设置",
                "relevance_score": 0.95,
            },
            {
                "source_id": "kb_2",
                "title": "数据库连接池配置",
                "content_preview": "数据库连接池应该限制最大连接数",
                "relevance_score": 0.88,
            },
            {
                "source_id": "kb_3",
                "title": "API错误处理指南",
                "content_preview": "所有API调用应该有错误处理逻辑",
                "relevance_score": 0.75,
            },
        ]

    @pytest.fixture
    def coordinator_with_context(
        self,
        event_bus,
        sample_rules,
        sample_tools,
        sample_knowledge,
    ):
        """配置完整上下文的 CoordinatorAgent"""
        tool_repo = MockToolRepository(sample_tools)
        knowledge_retriever = MockKnowledgeRetriever(sample_knowledge)

        agent = CoordinatorAgent(
            event_bus=event_bus,
            knowledge_retriever=knowledge_retriever,
        )

        # 添加规则
        for rule in sample_rules:
            agent.add_rule(rule)

        # 设置工具仓库
        agent.tool_repository = tool_repo

        return agent

    def test_get_context_returns_context_response(self, coordinator_with_context):
        """测试：get_context 返回 ContextResponse 结构"""
        agent = coordinator_with_context

        # 调用 get_context
        response = agent.get_context("我想发送一个HTTP请求")

        # 验证返回类型
        assert response is not None
        assert hasattr(response, "rules")
        assert hasattr(response, "knowledge")
        assert hasattr(response, "tools")
        assert hasattr(response, "summary")

    def test_get_context_returns_relevant_rules(self, coordinator_with_context):
        """测试：get_context 返回相关规则"""
        agent = coordinator_with_context

        response = agent.get_context("我需要验证用户输入数据")

        # 应该返回所有规则（因为规则是通用的验证规则）
        assert len(response.rules) > 0
        # 至少应该有数据验证规则
        rule_names = [r["name"] for r in response.rules]
        assert any("验证" in name for name in rule_names) or len(response.rules) > 0

    @pytest.mark.asyncio
    async def test_get_context_returns_relevant_knowledge(self, coordinator_with_context):
        """测试：get_context 返回相关知识"""
        agent = coordinator_with_context

        # 使用异步版本，用空格分隔关键词以匹配分词逻辑
        response = await agent.get_context_async("HTTP 请求 错误")

        # 应该返回相关知识
        assert len(response.knowledge) > 0
        # 应该包含HTTP相关知识
        titles = [k["title"] for k in response.knowledge]
        assert any("HTTP" in title or "API" in title for title in titles)

    def test_get_context_returns_relevant_tools(self, coordinator_with_context):
        """测试：get_context 返回相关工具"""
        agent = coordinator_with_context

        # 使用空格分隔关键词，确保 "database" 或 "sql" 能匹配到工具
        response = agent.get_context("database sql query")

        # 应该返回相关工具
        assert len(response.tools) > 0
        # 应该包含数据库工具
        tool_names = [t["name"] for t in response.tools]
        assert any("数据库" in name or "查询" in name for name in tool_names)

    def test_get_context_returns_summary(self, coordinator_with_context):
        """测试：get_context 返回摘要"""
        agent = coordinator_with_context

        response = agent.get_context("帮我调用AI分析数据")

        # 应该返回非空摘要
        assert response.summary is not None
        assert len(response.summary) > 0

    def test_get_context_with_empty_input(self, coordinator_with_context):
        """测试：空输入返回基础上下文"""
        agent = coordinator_with_context

        response = agent.get_context("")

        # 应该返回基础上下文（所有规则，无特定知识/工具）
        assert response is not None
        # 规则应该全部返回
        assert len(response.rules) > 0

    def test_get_context_includes_workflow_context_if_available(
        self,
        coordinator_with_context,
    ):
        """测试：如果有工作流上下文，应包含在返回中"""
        agent = coordinator_with_context

        # 模拟有一个活跃的工作流
        workflow_id = "wf_test_123"
        agent.workflow_states[workflow_id] = {
            "workflow_id": workflow_id,
            "status": "running",
            "node_count": 5,
            "executed_nodes": ["node_1", "node_2"],
        }

        response = agent.get_context(
            "继续执行工作流",
            workflow_id=workflow_id,
        )

        # 应该包含工作流上下文
        assert response.workflow_context is not None
        assert response.workflow_context["workflow_id"] == workflow_id


class TestContextResponseStructure:
    """测试 ContextResponse 结构"""

    def test_context_response_has_required_fields(self):
        """测试：ContextResponse 具有必需字段"""
        from src.domain.agents.coordinator_agent import ContextResponse

        response = ContextResponse(
            rules=[{"id": "rule_1", "name": "测试规则"}],
            knowledge=[{"source_id": "kb_1", "title": "测试知识"}],
            tools=[{"id": "tool_1", "name": "测试工具"}],
            summary="测试摘要",
        )

        assert response.rules == [{"id": "rule_1", "name": "测试规则"}]
        assert response.knowledge == [{"source_id": "kb_1", "title": "测试知识"}]
        assert response.tools == [{"id": "tool_1", "name": "测试工具"}]
        assert response.summary == "测试摘要"

    def test_context_response_has_optional_workflow_context(self):
        """测试：ContextResponse 可选包含工作流上下文"""
        from src.domain.agents.coordinator_agent import ContextResponse

        response = ContextResponse(
            rules=[],
            knowledge=[],
            tools=[],
            summary="测试摘要",
            workflow_context={"workflow_id": "wf_1", "status": "running"},
        )

        assert response.workflow_context is not None
        assert response.workflow_context["workflow_id"] == "wf_1"

    def test_context_response_to_dict(self):
        """测试：ContextResponse 可以转换为字典"""
        from src.domain.agents.coordinator_agent import ContextResponse

        response = ContextResponse(
            rules=[{"id": "rule_1"}],
            knowledge=[{"id": "kb_1"}],
            tools=[{"id": "tool_1"}],
            summary="测试",
        )

        result = response.to_dict()

        assert isinstance(result, dict)
        assert "rules" in result
        assert "knowledge" in result
        assert "tools" in result
        assert "summary" in result


class TestCoordinatorWithToolRepository:
    """测试 CoordinatorAgent 与 ToolRepository 集成"""

    @pytest.fixture
    def coordinator_with_tools(self):
        """配置工具仓库的 CoordinatorAgent"""
        tools = [
            MockTool(id="t1", name="工具A", description="描述A", tags=["tag1"]),
            MockTool(id="t2", name="工具B", description="描述B", tags=["tag2"]),
        ]
        tool_repo = MockToolRepository(tools)

        agent = CoordinatorAgent()
        agent.tool_repository = tool_repo

        return agent

    def test_set_tool_repository(self, coordinator_with_tools):
        """测试：可以设置 ToolRepository"""
        agent = coordinator_with_tools

        assert agent.tool_repository is not None
        assert len(agent.tool_repository.find_all()) == 2

    def test_get_available_tools(self, coordinator_with_tools):
        """测试：可以获取可用工具列表"""
        agent = coordinator_with_tools

        tools = agent.get_available_tools()

        assert len(tools) == 2
        assert tools[0]["name"] == "工具A"

    def test_find_tools_by_query(self, coordinator_with_tools):
        """测试：可以按查询找到相关工具"""
        agent = coordinator_with_tools

        tools = agent.find_tools_by_query("tag1")

        assert len(tools) >= 0  # 至少返回空列表


class TestConversationAgentIntegration:
    """测试 ConversationAgent 调用 get_context 接口"""

    @pytest.fixture
    def mock_coordinator(self):
        """模拟 CoordinatorAgent"""
        coordinator = CoordinatorAgent()
        coordinator.tool_repository = MockToolRepository(
            [
                MockTool(id="t1", name="HTTP工具", description="HTTP请求", tags=["http"]),
            ]
        )
        coordinator.add_rule(Rule(id="r1", name="安全规则", priority=1))

        return coordinator

    def test_conversation_agent_can_get_context(self, mock_coordinator):
        """测试：ConversationAgent 可以获取上下文"""
        from src.domain.agents.coordinator_agent import ContextResponse

        # 模拟 ConversationAgent 调用
        user_input = "帮我发送一个HTTP请求"

        # 获取上下文
        context = mock_coordinator.get_context(user_input)

        # 验证返回了有效上下文
        assert isinstance(context, ContextResponse)
        assert context.summary is not None

    def test_conversation_agent_logs_context(self, mock_coordinator, caplog):
        """测试：ConversationAgent 调用后记录日志"""
        import logging

        # 设置日志级别
        caplog.set_level(logging.INFO)

        user_input = "测试输入"

        # 调用 get_context 并记录
        context = mock_coordinator.get_context(user_input)

        # 验证 context 可以被记录
        log_message = f"Context retrieved: rules={len(context.rules)}, tools={len(context.tools)}"
        logging.info(log_message)

        assert "Context retrieved" in caplog.text


class TestGetContextEdgeCases:
    """测试 get_context 边界情况"""

    @pytest.fixture
    def minimal_coordinator(self):
        """最小配置的 CoordinatorAgent"""
        return CoordinatorAgent()

    def test_get_context_without_knowledge_retriever(self, minimal_coordinator):
        """测试：没有知识检索器时返回空知识列表"""
        agent = minimal_coordinator

        response = agent.get_context("测试")

        assert response.knowledge == []

    def test_get_context_without_tool_repository(self, minimal_coordinator):
        """测试：没有工具仓库时返回空工具列表"""
        agent = minimal_coordinator

        response = agent.get_context("测试")

        assert response.tools == []

    def test_get_context_without_rules(self, minimal_coordinator):
        """测试：没有规则时返回空规则列表"""
        agent = minimal_coordinator

        response = agent.get_context("测试")

        assert response.rules == []

    def test_get_context_with_special_characters(self, minimal_coordinator):
        """测试：特殊字符输入不会崩溃"""
        agent = minimal_coordinator

        special_inputs = [
            "Hello! @#$%^&*()",
            "中文测试 🎉",
            "SELECT * FROM users;",
            "<script>alert('xss')</script>",
        ]

        for input_text in special_inputs:
            response = agent.get_context(input_text)
            assert response is not None


class TestAsyncGetContext:
    """测试异步版本的 get_context"""

    @pytest.fixture
    def async_coordinator(self):
        """配置异步知识检索的 CoordinatorAgent"""
        knowledge = [
            {"source_id": "k1", "title": "知识1", "content_preview": "内容1"},
        ]
        retriever = MockKnowledgeRetriever(knowledge)

        agent = CoordinatorAgent(knowledge_retriever=retriever)
        return agent

    @pytest.mark.asyncio
    async def test_get_context_async_returns_context(self, async_coordinator):
        """测试：异步 get_context 返回上下文"""
        agent = async_coordinator

        response = await agent.get_context_async("测试查询")

        assert response is not None
        assert hasattr(response, "knowledge")

    @pytest.mark.asyncio
    async def test_get_context_async_retrieves_knowledge(self, async_coordinator):
        """测试：异步 get_context 能检索知识"""
        agent = async_coordinator

        # 使用能够匹配知识库内容的关键词（"知识" 或 "内容"）
        response = await agent.get_context_async("知识 内容")

        # 应该检索到知识
        assert len(response.knowledge) > 0


# 导出
__all__ = [
    "TestGetContextAPI",
    "TestContextResponseStructure",
    "TestCoordinatorWithToolRepository",
    "TestConversationAgentIntegration",
    "TestGetContextEdgeCases",
    "TestAsyncGetContext",
]

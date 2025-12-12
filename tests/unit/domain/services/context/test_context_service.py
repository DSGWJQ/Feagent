"""ContextService 单元测试

Phase 35.1: 测试上下文服务的核心功能
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context.models import ContextResponse
from src.domain.services.context.service import ContextService


# Mock 数据类
@dataclass
class MockRule:
    """模拟规则"""

    id: str
    name: str
    description: str
    priority: int


@dataclass
class MockTool:
    """模拟工具"""

    id: str
    name: str
    description: str
    category: str
    tags: list[str]


# Fixtures


@pytest.fixture
def mock_rules():
    """模拟规则列表"""
    return [
        MockRule(id="rule-1", name="验证规则", description="验证用户输入", priority=1),
        MockRule(id="rule-2", name="安全规则", description="检查安全性", priority=2),
    ]


@pytest.fixture
def mock_tools():
    """模拟工具列表"""
    return [
        MockTool(
            id="tool-1",
            name="搜索工具",
            description="搜索网络内容",
            category="search",
            tags=["search", "web"],
        ),
        MockTool(
            id="tool-2",
            name="数据分析",
            description="分析数据集",
            category="analytics",
            tags=["data", "analysis"],
        ),
    ]


@pytest.fixture
def mock_tool_repository(mock_tools):
    """模拟工具仓库"""
    repo = MagicMock()
    repo.find_published.return_value = mock_tools
    repo.find_all.return_value = mock_tools
    repo.find_by_tags.return_value = [mock_tools[0]]  # 返回第一个工具
    return repo


@pytest.fixture
def mock_knowledge_retriever():
    """模拟知识检索器"""
    retriever = AsyncMock()
    retriever.retrieve_by_query.return_value = [
        {"source_id": "kb-1", "title": "知识条目1", "content_preview": "内容预览"},
        {"source_id": "kb-2", "title": "知识条目2", "content_preview": "另一个预览"},
    ]
    return retriever


@pytest.fixture
def mock_workflow_states():
    """模拟工作流状态"""
    return {
        "workflow-001": {"status": "running", "current_node": "node-1"},
        "workflow-002": {"status": "completed", "current_node": "node-final"},
    }


@pytest.fixture
def context_service_basic(mock_rules, mock_tool_repository):
    """基础上下文服务（无知识检索器）"""
    return ContextService(
        rule_provider=lambda: mock_rules,
        tool_repository=mock_tool_repository,
    )


@pytest.fixture
def context_service_full(
    mock_rules, mock_tool_repository, mock_knowledge_retriever, mock_workflow_states
):
    """完整上下文服务（包含所有依赖）"""
    return ContextService(
        rule_provider=lambda: mock_rules,
        tool_repository=mock_tool_repository,
        knowledge_retriever=mock_knowledge_retriever,
        workflow_context_provider=mock_workflow_states,
    )


# 测试用例


def test_get_context_without_retrievers_returns_rules_and_tools_only(context_service_basic):
    """测试：无检索器时仅返回规则和工具"""
    # 使用英文关键词匹配（因为 split() 在中文不分词）
    result = context_service_basic.get_context(user_input="search web")

    assert isinstance(result, ContextResponse)
    assert len(result.rules) == 2
    assert result.rules[0]["id"] == "rule-1"
    assert result.rules[1]["name"] == "安全规则"

    assert len(result.tools) == 1  # 仅匹配 "search" 关键词的工具
    assert result.tools[0]["name"] == "搜索工具"

    assert result.knowledge == []  # 同步版本不查询知识
    assert result.workflow_context is None
    assert "用户输入: search web" in result.summary
    assert "可用规则: 2" in result.summary


@pytest.mark.asyncio
async def test_get_context_async_with_knowledge(context_service_full):
    """测试：异步版本返回知识条目"""
    # 使用英文关键词匹配（因为 split() 在中文不分词）
    result = await context_service_full.get_context_async(
        user_input="data analysis", workflow_id="workflow-001"
    )

    assert isinstance(result, ContextResponse)
    assert len(result.knowledge) == 2
    assert result.knowledge[0]["source_id"] == "kb-1"

    assert len(result.tools) == 1  # 匹配 "analysis" 关键词
    assert result.tools[0]["name"] == "数据分析"

    assert result.workflow_context is not None
    assert result.workflow_context["status"] == "running"
    assert "知识条目: 2" in result.summary


def test_get_context_handles_workflow_state_copy(context_service_full):
    """测试：工作流状态应拷贝以防止引用污染"""
    result = context_service_full.get_context(user_input="测试", workflow_id="workflow-001")

    assert result.workflow_context is not None
    assert result.workflow_context == {"status": "running", "current_node": "node-1"}

    # 修改返回的 context 不应影响原始状态
    result.workflow_context["status"] = "modified"
    original_states = context_service_full._workflow_context_provider
    assert original_states["workflow-001"]["status"] == "running"


def test_summary_builder_truncates_user_input(context_service_basic):
    """测试：摘要应截断长输入"""
    # 使用 55 个字符确保超过 50 字符限制
    long_input = "a" * 55
    result = context_service_basic.get_context(user_input=long_input)

    assert "用户输入:" in result.summary
    assert "..." in result.summary
    # 截断后应该是 "用户输入: " + 50个字符 + "..."
    assert len(result.summary.split("|")[0]) < len(f"用户输入: {long_input}")


def test_find_tools_matches_keywords(context_service_basic):
    """测试：工具查找应匹配关键词"""
    # 测试关键词 "search" 匹配（使用英文标签）
    result1 = context_service_basic.get_context(user_input="search")
    assert len(result1.tools) == 1
    assert result1.tools[0]["name"] == "搜索工具"

    # 测试关键词 "data" 匹配
    result2 = context_service_basic.get_context(user_input="data")
    assert len(result2.tools) == 1
    assert result2.tools[0]["name"] == "数据分析"

    # 测试空输入返回所有工具
    result3 = context_service_basic.get_context(user_input="")
    assert len(result3.tools) == 2


@pytest.mark.asyncio
async def test_failure_returns_empty_lists(mock_rules):
    """测试：检索失败时返回空列表"""
    # 创建会抛异常的 retriever
    failing_retriever = AsyncMock()
    failing_retriever.retrieve_by_query.side_effect = Exception("检索失败")

    # 创建会抛异常的 tool_repository
    failing_tool_repo = MagicMock()
    failing_tool_repo.find_published.side_effect = Exception("工具查询失败")

    service = ContextService(
        rule_provider=lambda: mock_rules,
        tool_repository=failing_tool_repo,
        knowledge_retriever=failing_retriever,
    )

    # 异步调用应吞掉异常，返回空知识列表
    result = await service.get_context_async(user_input="测试")
    assert result.knowledge == []
    assert result.tools == []  # 工具查询失败也返回空列表
    assert len(result.rules) == 2  # 规则来自 lambda，不会失败


def test_get_available_tools(context_service_full):
    """测试：获取所有可用工具"""
    result = context_service_full.get_available_tools()

    assert len(result) == 2
    assert result[0]["id"] == "tool-1"
    assert result[1]["category"] == "analytics"


def test_find_tools_by_query(context_service_full):
    """测试：按标签查询工具"""
    result = context_service_full.find_tools_by_query(query="search")

    assert len(result) == 1
    assert result[0]["name"] == "搜索工具"

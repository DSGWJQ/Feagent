"""KnowledgeRetrievalOrchestrator 单元测试

基于 Codex 分析的 TDD 测试套件：
- 初始化与配置
- 知识检索（query/error/goal）
- 缓存管理
- 上下文增强与注入
- 自动触发机制
- 边界场景
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_knowledge_retriever():
    """Mock KnowledgeRetriever"""
    retriever = AsyncMock()

    # Mock retrieve_by_query
    retriever.retrieve_by_query = AsyncMock(
        return_value=[
            {
                "source_id": "doc1",
                "title": "Query Result 1",
                "content_preview": "Preview 1",
                "relevance_score": 0.95,
                "document_id": "d1",
                "source_type": "knowledge_base",
            },
            {
                "source_id": "doc2",
                "title": "Query Result 2",
                "content_preview": "Preview 2",
                "relevance_score": 0.85,
                "source_type": "knowledge_base",
            },
        ]
    )

    # Mock retrieve_by_error
    retriever.retrieve_by_error = AsyncMock(
        return_value=[
            {
                "source_id": "err_sol1",
                "title": "Error Solution 1",
                "content_preview": "Fix for error",
                "relevance_score": 0.90,
                "source_type": "error_solution",
            }
        ]
    )

    # Mock retrieve_by_goal
    retriever.retrieve_by_goal = AsyncMock(
        return_value=[
            {
                "source_id": "goal1",
                "title": "Goal Guide 1",
                "content_preview": "How to achieve goal",
                "relevance_score": 0.88,
                "document_id": "g1",
                "source_type": "goal_related",
            }
        ]
    )

    return retriever


@pytest.fixture
def mock_context_gateway():
    """Mock ContextGateway for accessing compressed contexts"""
    gateway = MagicMock()

    # 存储上下文
    contexts = {}

    def get_context(workflow_id: str):
        return contexts.get(workflow_id)

    def update_knowledge_refs(workflow_id: str, refs: list):
        if workflow_id in contexts:
            ctx = contexts[workflow_id]
            if hasattr(ctx, "knowledge_references"):
                # 合并逻辑
                existing_refs = ctx.knowledge_references or []
                seen_ids = {r.get("source_id") for r in existing_refs}
                for ref in refs:
                    if ref.get("source_id") not in seen_ids:
                        existing_refs.append(ref)
                        seen_ids.add(ref.get("source_id"))
                ctx.knowledge_references = existing_refs

    def update_error_log(workflow_id: str, error: dict):
        if workflow_id in contexts:
            ctx = contexts[workflow_id]
            if hasattr(ctx, "error_log"):
                ctx.error_log.append(error)

    def update_reflection(workflow_id: str, reflection: dict):
        if workflow_id in contexts:
            ctx = contexts[workflow_id]
            if hasattr(ctx, "reflection_summary"):
                ctx.reflection_summary = reflection
            if hasattr(ctx, "next_actions") and "recommendations" in reflection:
                ctx.next_actions = reflection["recommendations"]

    gateway.get_context = MagicMock(side_effect=get_context)
    gateway.update_knowledge_refs = MagicMock(side_effect=update_knowledge_refs)
    gateway.update_error_log = MagicMock(side_effect=update_error_log)
    gateway.update_reflection = MagicMock(side_effect=update_reflection)
    gateway._contexts = contexts  # 用于测试访问

    return gateway


@pytest.fixture
def orchestrator(mock_knowledge_retriever, mock_context_gateway):
    """KnowledgeRetrievalOrchestrator 实例"""
    from src.domain.services.knowledge_retrieval_orchestrator import (
        KnowledgeRetrievalOrchestrator,
    )

    return KnowledgeRetrievalOrchestrator(
        knowledge_retriever=mock_knowledge_retriever,
        context_gateway=mock_context_gateway,
    )


# =====================================================================
# Test: 初始化与配置
# =====================================================================


def test_orchestrator_initialization(mock_knowledge_retriever, mock_context_gateway):
    """测试编排器初始化"""
    from src.domain.services.knowledge_retrieval_orchestrator import (
        KnowledgeRetrievalOrchestrator,
    )

    orch = KnowledgeRetrievalOrchestrator(
        knowledge_retriever=mock_knowledge_retriever,
        context_gateway=mock_context_gateway,
    )

    assert orch.knowledge_retriever == mock_knowledge_retriever
    assert orch.context_gateway == mock_context_gateway
    assert orch._knowledge_cache == {}
    assert orch._auto_knowledge_retrieval_enabled is False


def test_orchestrator_without_retriever(mock_context_gateway):
    """测试无 retriever 初始化"""
    from src.domain.services.knowledge_retrieval_orchestrator import (
        KnowledgeRetrievalOrchestrator,
    )

    orch = KnowledgeRetrievalOrchestrator(
        knowledge_retriever=None,
        context_gateway=mock_context_gateway,
    )

    assert orch.knowledge_retriever is None


# =====================================================================
# Test: 知识检索
# =====================================================================


async def test_retrieve_knowledge_success(orchestrator, mock_knowledge_retriever):
    """测试按查询检索知识"""
    result = await orchestrator.retrieve_knowledge(
        query="test query",
        workflow_id="wf_001",
        top_k=5,
    )

    # 验证调用 retriever
    mock_knowledge_retriever.retrieve_by_query.assert_called_once_with(
        query="test query",
        workflow_id="wf_001",
        top_k=5,
    )

    # 验证返回 KnowledgeReferences
    assert len(result) == 2
    refs = result.to_list()
    assert refs[0].source_id == "doc1"
    assert refs[0].title == "Query Result 1"

    # 验证缓存
    assert "wf_001" in orchestrator._knowledge_cache


async def test_retrieve_knowledge_without_retriever(mock_context_gateway):
    """测试无 retriever 时检索返回空"""
    from src.domain.services.knowledge_retrieval_orchestrator import (
        KnowledgeRetrievalOrchestrator,
    )

    orch = KnowledgeRetrievalOrchestrator(
        knowledge_retriever=None,
        context_gateway=mock_context_gateway,
    )

    result = await orch.retrieve_knowledge(query="test", workflow_id="wf_002")

    # 应返回空的 KnowledgeReferences
    assert len(result) == 0


async def test_retrieve_knowledge_by_error(orchestrator, mock_knowledge_retriever):
    """测试按错误类型检索"""
    result = await orchestrator.retrieve_knowledge_by_error(
        error_type="TypeError",
        error_message="type error occurred",
        top_k=3,
    )

    mock_knowledge_retriever.retrieve_by_error.assert_called_once_with(
        error_type="TypeError",
        error_message="type error occurred",
        top_k=3,
    )

    assert len(result) == 1
    refs = result.to_list()
    assert refs[0].source_id == "err_sol1"
    assert refs[0].source_type == "error_solution"


async def test_retrieve_knowledge_by_goal(orchestrator, mock_knowledge_retriever):
    """测试按目标检索"""
    result = await orchestrator.retrieve_knowledge_by_goal(
        goal_text="Implement user authentication",
        workflow_id="wf_003",
        top_k=3,
    )

    mock_knowledge_retriever.retrieve_by_goal.assert_called_once_with(
        goal_text="Implement user authentication",
        workflow_id="wf_003",
        top_k=3,
    )

    assert len(result) == 1
    refs = result.to_list()
    assert refs[0].source_id == "goal1"


# =====================================================================
# Test: 缓存管理
# =====================================================================


async def test_get_cached_knowledge(orchestrator):
    """测试获取缓存知识"""
    # 先缓存一些数据
    await orchestrator.retrieve_knowledge(query="test", workflow_id="wf_004")

    # 获取缓存
    cached = orchestrator.get_cached_knowledge("wf_004")

    assert cached is not None
    assert len(cached) == 2


def test_get_cached_knowledge_not_exists(orchestrator):
    """测试获取不存在的缓存"""
    cached = orchestrator.get_cached_knowledge("wf_nonexistent")

    assert cached is None


def test_clear_cached_knowledge(orchestrator):
    """测试清除缓存"""
    # 手动添加缓存
    from src.domain.services.knowledge_reference import KnowledgeReferences

    refs = KnowledgeReferences()
    orchestrator._knowledge_cache["wf_005"] = refs

    # 清除
    orchestrator.clear_cached_knowledge("wf_005")

    assert "wf_005" not in orchestrator._knowledge_cache


def test_clear_nonexistent_cache(orchestrator):
    """测试清除不存在的缓存（不应报错）"""
    orchestrator.clear_cached_knowledge("wf_nonexistent")  # 不应抛异常


# =====================================================================
# Test: 上下文增强与注入
# =====================================================================


async def test_enrich_context_with_knowledge(orchestrator, mock_knowledge_retriever):
    """测试丰富上下文"""
    result = await orchestrator.enrich_context_with_knowledge(
        workflow_id="wf_006",
        goal="Implement feature X",
        errors=[{"error_type": "ValueError", "message": "invalid value"}],
    )

    # 验证调用 retriever
    mock_knowledge_retriever.retrieve_by_goal.assert_called_once()
    mock_knowledge_retriever.retrieve_by_error.assert_called_once()

    # 验证返回格式
    assert result["workflow_id"] == "wf_006"
    assert "knowledge_references" in result

    # 验证缓存
    assert "wf_006" in orchestrator._knowledge_cache


async def test_inject_knowledge_to_context(orchestrator, mock_context_gateway):
    """测试注入知识到上下文"""
    # 创建模拟上下文
    ctx = SimpleNamespace(
        workflow_id="wf_007",
        knowledge_references=[],
        task_goal="Test goal",
    )
    mock_context_gateway._contexts["wf_007"] = ctx

    # 注入知识
    await orchestrator.inject_knowledge_to_context(
        workflow_id="wf_007",
        goal="Test goal",
    )

    # 验证 gateway 被调用
    mock_context_gateway.update_knowledge_refs.assert_called()


async def test_inject_knowledge_no_duplicate_source_id(orchestrator, mock_context_gateway):
    """测试注入知识时去重（按 source_id）"""
    # 创建已有知识引用的上下文
    ctx = SimpleNamespace(
        workflow_id="wf_008",
        knowledge_references=[{"source_id": "doc1", "title": "Existing"}],
        task_goal="Test",
    )
    mock_context_gateway._contexts["wf_008"] = ctx

    # 注入包含重复 source_id 的知识
    await orchestrator.inject_knowledge_to_context(
        workflow_id="wf_008",
        goal="Test goal",
    )

    # 验证不会添加重复的 source_id
    # （通过 gateway.update_knowledge_refs 的去重逻辑）
    updated_refs = ctx.knowledge_references
    source_ids = [r.get("source_id") for r in updated_refs]
    assert len(source_ids) == len(set(source_ids))  # 无重复


async def test_get_knowledge_enhanced_summary(orchestrator, mock_context_gateway):
    """测试获取知识增强摘要"""
    # 创建带知识引用的上下文
    ctx = SimpleNamespace(
        workflow_id="wf_009",
        knowledge_references=[
            {"source_id": "r1", "title": "Ref 1", "relevance_score": 0.95},
            {"source_id": "r2", "title": "Ref 2", "relevance_score": 0.85},
            {"source_id": "r3", "title": "Ref 3", "relevance_score": 0.75},
            {"source_id": "r4", "title": "Ref 4", "relevance_score": 0.65},
        ],
        to_summary_text=lambda: "Base summary",
    )
    mock_context_gateway._contexts["wf_009"] = ctx
    mock_context_gateway.get_context.return_value = ctx

    summary = orchestrator.get_knowledge_enhanced_summary("wf_009")

    # 验证包含基础摘要
    assert "Base summary" in summary

    # 验证包含知识引用（最多3条）
    assert "Ref 1" in summary
    assert "Ref 2" in summary
    assert "Ref 3" in summary
    assert "Ref 4" not in summary  # 第4条不应显示


def test_get_knowledge_enhanced_summary_no_context(orchestrator):
    """测试无上下文时获取摘要"""
    summary = orchestrator.get_knowledge_enhanced_summary("wf_nonexistent")

    assert summary is None


# =====================================================================
# Test: 自动触发机制
# =====================================================================


async def test_auto_enrich_context_on_error(orchestrator, mock_context_gateway):
    """测试错误时自动丰富上下文"""
    # 创建带目标的上下文
    ctx = SimpleNamespace(
        workflow_id="wf_010",
        task_goal="Test goal",
    )
    mock_context_gateway._contexts["wf_010"] = ctx
    mock_context_gateway.get_context.return_value = ctx

    result = await orchestrator.auto_enrich_context_on_error(
        workflow_id="wf_010",
        error_type="RuntimeError",
        error_message="runtime error",
    )

    # 验证返回结果
    assert result["workflow_id"] == "wf_010"
    assert "knowledge_references" in result


async def test_handle_node_failure_with_knowledge(orchestrator, mock_context_gateway):
    """测试处理节点失败"""
    # 创建带 error_log 的上下文
    ctx = SimpleNamespace(
        workflow_id="wf_011",
        error_log=[],
        task_goal="Test",
    )
    mock_context_gateway._contexts["wf_011"] = ctx
    mock_context_gateway.get_context.return_value = ctx

    result = await orchestrator.handle_node_failure_with_knowledge(
        workflow_id="wf_011",
        node_id="node_1",
        error_type="ValueError",
        error_message="value error",
    )

    # 验证调用 gateway 更新错误日志
    mock_context_gateway.update_error_log.assert_called_once_with(
        "wf_011",
        {
            "node_id": "node_1",
            "error_type": "ValueError",
            "error_message": "value error",
        },
    )

    # 验证返回结果
    assert "knowledge_references" in result


async def test_handle_reflection_with_knowledge(orchestrator, mock_context_gateway):
    """测试处理反思事件"""
    # 创建带 reflection_summary 的上下文
    ctx = SimpleNamespace(
        workflow_id="wf_012",
        reflection_summary={},
        next_actions=[],
        task_goal="Test goal",
    )
    mock_context_gateway._contexts["wf_012"] = ctx
    mock_context_gateway.get_context.return_value = ctx

    result = await orchestrator.handle_reflection_with_knowledge(
        workflow_id="wf_012",
        assessment="Good progress",
        confidence=0.85,
        recommendations=["Step 1", "Step 2"],
    )

    # 验证调用 gateway 更新反思
    mock_context_gateway.update_reflection.assert_called_once()

    # 验证返回结果
    assert "knowledge_references" in result


# =====================================================================
# Test: 自动检索开关
# =====================================================================


def test_enable_auto_knowledge_retrieval(orchestrator):
    """测试启用自动知识检索"""
    orchestrator.enable_auto_knowledge_retrieval()

    assert orchestrator._auto_knowledge_retrieval_enabled is True


def test_disable_auto_knowledge_retrieval(orchestrator):
    """测试禁用自动知识检索"""
    orchestrator._auto_knowledge_retrieval_enabled = True

    orchestrator.disable_auto_knowledge_retrieval()

    assert orchestrator._auto_knowledge_retrieval_enabled is False


# =====================================================================
# Test: 对话Agent上下文
# =====================================================================


def test_get_context_for_conversation_agent(orchestrator, mock_context_gateway):
    """测试获取对话Agent上下文"""
    # 创建完整上下文
    from src.domain.services.knowledge_reference import KnowledgeReferences

    refs = KnowledgeReferences()
    orchestrator._knowledge_cache["wf_013"] = refs

    ctx = SimpleNamespace(
        workflow_id="wf_013",
        task_goal="Test goal",
        execution_status={"status": "running"},
        node_summary=[{"node": "n1"}],
        error_log=[{"error": "e1"}],
        next_actions=["action1"],
        conversation_summary="Summary",
        reflection_summary={"assessment": "Good"},
        knowledge_references=[{"ref": "r1"}],
    )
    mock_context_gateway._contexts["wf_013"] = ctx
    mock_context_gateway.get_context.return_value = ctx

    agent_context = orchestrator.get_context_for_conversation_agent("wf_013")

    # 验证返回格式
    assert agent_context is not None
    assert agent_context["workflow_id"] == "wf_013"
    assert agent_context["goal"] == "Test goal"
    assert agent_context["task_goal"] == "Test goal"
    assert "knowledge_references" in agent_context
    assert "cached_knowledge" in agent_context


def test_get_context_for_conversation_agent_no_context(orchestrator):
    """测试无上下文时获取对话Agent上下文"""
    agent_context = orchestrator.get_context_for_conversation_agent("wf_nonexistent")

    assert agent_context is None


# =====================================================================
# Test: 边界场景
# =====================================================================


async def test_enrich_context_with_no_goal_no_errors(orchestrator):
    """测试无目标无错误时丰富上下文"""
    result = await orchestrator.enrich_context_with_knowledge(
        workflow_id="wf_014",
        goal=None,
        errors=None,
    )

    # 应返回空引用
    assert result["workflow_id"] == "wf_014"
    assert len(result["knowledge_references"]) == 0


async def test_inject_knowledge_to_missing_context(orchestrator):
    """测试注入知识到不存在的上下文（不应报错）"""
    await orchestrator.inject_knowledge_to_context(
        workflow_id="wf_nonexistent",
        goal="Test",
    )

    # 不应抛异常


async def test_handle_node_failure_without_error_log_attr(orchestrator, mock_context_gateway):
    """测试处理节点失败但上下文无 error_log 属性"""
    # 创建无 error_log 的上下文
    ctx = SimpleNamespace(
        workflow_id="wf_015",
        task_goal="Test",
    )
    mock_context_gateway._contexts["wf_015"] = ctx
    mock_context_gateway.get_context.return_value = ctx

    # 不应抛异常
    result = await orchestrator.handle_node_failure_with_knowledge(
        workflow_id="wf_015",
        node_id="node_1",
        error_type="Error",
    )

    assert "knowledge_references" in result

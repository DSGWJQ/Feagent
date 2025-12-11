"""PowerCompressorFacade 单元测试

测试 PowerCompressor 包装器的核心功能：
- 压缩上下文存储与查询
- 八段数据查询接口
- 统计信息生成
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_power_compressor():
    """Mock PowerCompressor"""
    compressor = MagicMock()

    # Mock compress_summary 返回值
    mock_compressed = MagicMock()
    mock_compressed.workflow_id = "wf_001"
    mock_compressed.to_dict.return_value = {
        "workflow_id": "wf_001",
        "task_goal": "Test task",
        "execution_status": {"status": "completed"},
        "node_summary": [{"node_id": "node1", "result": "success"}],
        "subtask_errors": [{"error": "test error"}],
        "unresolved_issues": [{"issue": "test issue"}],
        "decision_history": [{"decision": "test"}],
        "next_plan": [{"plan": "next step"}],
        "knowledge_sources": [{"source": "doc1"}],
    }
    compressor.compress_summary.return_value = mock_compressed

    return compressor


@pytest.fixture
def facade(mock_power_compressor):
    """PowerCompressorFacade 实例"""
    from src.domain.services.power_compressor_facade import PowerCompressorFacade

    return PowerCompressorFacade(power_compressor=mock_power_compressor)


@pytest.fixture
def mock_execution_summary():
    """Mock ExecutionSummary"""
    summary = MagicMock()
    summary.workflow_id = "wf_001"
    summary.session_id = "session_001"
    summary.success = True
    return summary


# =====================================================================
# Test: 初始化与配置
# =====================================================================


def test_facade_initialization(mock_power_compressor):
    """测试 Facade 初始化"""
    from src.domain.services.power_compressor_facade import PowerCompressorFacade

    facade = PowerCompressorFacade(power_compressor=mock_power_compressor)

    assert facade.power_compressor == mock_power_compressor
    assert facade._compressed_contexts == {}


def test_facade_without_compressor():
    """测试无 PowerCompressor 初始化（懒加载）"""
    from src.domain.services.power_compressor_facade import PowerCompressorFacade

    facade = PowerCompressorFacade()

    # 应该懒加载创建 PowerCompressor
    assert facade.power_compressor is not None


# =====================================================================
# Test: 压缩与存储
# =====================================================================


async def test_compress_and_store(facade, mock_execution_summary, mock_power_compressor):
    """测试压缩并存储"""
    result = await facade.compress_and_store(mock_execution_summary)

    # 验证调用压缩器
    mock_power_compressor.compress_summary.assert_called_once_with(mock_execution_summary)

    # 验证返回值
    assert result.workflow_id == "wf_001"

    # 验证存储
    assert "wf_001" in facade._compressed_contexts
    stored = facade._compressed_contexts["wf_001"]
    assert stored["workflow_id"] == "wf_001"


async def test_compress_and_store_without_workflow_id(facade, mock_power_compressor):
    """测试压缩没有 workflow_id 的总结"""
    mock_summary = MagicMock()
    mock_summary.workflow_id = "wf_002"

    # Mock 压缩结果没有 workflow_id
    mock_compressed = MagicMock()
    mock_compressed.workflow_id = ""
    mock_compressed.to_dict.return_value = {"workflow_id": ""}
    mock_power_compressor.compress_summary.return_value = mock_compressed

    result = await facade.compress_and_store(mock_summary)

    # 验证返回
    assert result == mock_compressed

    # 验证未存储（因为 workflow_id 为空）
    assert "" not in facade._compressed_contexts


def test_store_compressed_context(facade):
    """测试直接存储压缩上下文"""
    data = {
        "workflow_id": "wf_002",
        "task_goal": "Direct store test",
    }

    facade.store_compressed_context("wf_002", data)

    assert "wf_002" in facade._compressed_contexts
    assert facade._compressed_contexts["wf_002"] == data


# =====================================================================
# Test: 查询接口
# =====================================================================


def test_query_compressed_context_exists(facade):
    """测试查询存在的压缩上下文"""
    data = {"workflow_id": "wf_003", "task_goal": "Query test"}
    facade.store_compressed_context("wf_003", data)

    result = facade.query_compressed_context("wf_003")

    assert result == data


def test_query_compressed_context_not_exists(facade):
    """测试查询不存在的压缩上下文"""
    result = facade.query_compressed_context("wf_nonexistent")

    assert result is None


def test_query_subtask_errors(facade):
    """测试查询子任务错误"""
    data = {
        "workflow_id": "wf_004",
        "subtask_errors": [{"error": "err1"}, {"error": "err2"}],
    }
    facade.store_compressed_context("wf_004", data)

    result = facade.query_subtask_errors("wf_004")

    assert len(result) == 2
    assert result[0]["error"] == "err1"


def test_query_subtask_errors_empty(facade):
    """测试查询不存在的工作流的子任务错误"""
    result = facade.query_subtask_errors("wf_nonexistent")

    assert result == []


def test_query_unresolved_issues(facade):
    """测试查询未解决问题"""
    data = {
        "workflow_id": "wf_005",
        "unresolved_issues": [{"issue": "issue1"}],
    }
    facade.store_compressed_context("wf_005", data)

    result = facade.query_unresolved_issues("wf_005")

    assert len(result) == 1
    assert result[0]["issue"] == "issue1"


def test_query_next_plan(facade):
    """测试查询后续计划"""
    data = {
        "workflow_id": "wf_006",
        "next_plan": [{"plan": "step1"}, {"plan": "step2"}],
    }
    facade.store_compressed_context("wf_006", data)

    result = facade.query_next_plan("wf_006")

    assert len(result) == 2
    assert result[0]["plan"] == "step1"


# =====================================================================
# Test: 对话上下文接口
# =====================================================================


def test_get_context_for_conversation(facade):
    """测试获取对话上下文"""
    data = {
        "workflow_id": "wf_007",
        "task_goal": "Conversation test",
        "execution_status": {"status": "running"},
        "node_summary": [{"node": "n1"}],
        "subtask_errors": [{"error": "e1"}],
        "unresolved_issues": [{"issue": "i1"}],
        "decision_history": [{"decision": "d1"}],
        "next_plan": [{"plan": "p1"}],
        "knowledge_sources": [{"source": "s1"}],
    }
    facade.store_compressed_context("wf_007", data)

    result = facade.get_context_for_conversation("wf_007")

    assert result is not None
    assert result["workflow_id"] == "wf_007"
    assert result["task_goal"] == "Conversation test"
    assert len(result["subtask_errors"]) == 1
    assert len(result["knowledge_sources"]) == 1


def test_get_context_for_conversation_not_exists(facade):
    """测试获取不存在的对话上下文"""
    result = facade.get_context_for_conversation("wf_nonexistent")

    assert result is None


def test_get_knowledge_for_conversation(facade):
    """测试获取知识来源"""
    data = {
        "workflow_id": "wf_008",
        "knowledge_sources": [{"source": "doc1"}, {"source": "doc2"}],
    }
    facade.store_compressed_context("wf_008", data)

    result = facade.get_knowledge_for_conversation("wf_008")

    assert len(result) == 2
    assert result[0]["source"] == "doc1"


def test_get_knowledge_for_conversation_empty(facade):
    """测试获取不存在的知识来源"""
    result = facade.get_knowledge_for_conversation("wf_nonexistent")

    assert result == []


# =====================================================================
# Test: 统计接口
# =====================================================================


def test_get_statistics_empty(facade):
    """测试空统计"""
    stats = facade.get_statistics()

    assert stats["total_contexts"] == 0
    assert stats["total_subtask_errors"] == 0
    assert stats["total_unresolved_issues"] == 0
    assert stats["total_next_plan_items"] == 0


def test_get_statistics_with_data(facade):
    """测试带数据的统计"""
    facade.store_compressed_context(
        "wf_009",
        {
            "subtask_errors": [{"e": "1"}, {"e": "2"}],
            "unresolved_issues": [{"i": "1"}],
            "next_plan": [{"p": "1"}, {"p": "2"}, {"p": "3"}],
        },
    )
    facade.store_compressed_context(
        "wf_010",
        {
            "subtask_errors": [{"e": "3"}],
            "unresolved_issues": [],
            "next_plan": [{"p": "4"}],
        },
    )

    stats = facade.get_statistics()

    assert stats["total_contexts"] == 2
    assert stats["total_subtask_errors"] == 3  # 2 + 1
    assert stats["total_unresolved_issues"] == 1  # 1 + 0
    assert stats["total_next_plan_items"] == 4  # 3 + 1


# =====================================================================
# Test: 边界场景
# =====================================================================


def test_query_with_missing_fields(facade):
    """测试查询缺少字段的上下文"""
    facade.store_compressed_context("wf_011", {"workflow_id": "wf_011"})

    errors = facade.query_subtask_errors("wf_011")
    issues = facade.query_unresolved_issues("wf_011")
    plans = facade.query_next_plan("wf_011")

    assert errors == []
    assert issues == []
    assert plans == []


def test_get_context_with_missing_fields(facade):
    """测试获取缺少字段的对话上下文"""
    facade.store_compressed_context("wf_012", {"workflow_id": "wf_012"})

    context = facade.get_context_for_conversation("wf_012")

    assert context is not None
    assert context["workflow_id"] == "wf_012"
    assert context["task_goal"] == ""
    assert context["subtask_errors"] == []


def test_duplicate_workflow_id_overwrites(facade):
    """测试重复 workflow_id 覆盖"""
    facade.store_compressed_context("wf_013", {"data": "old"})
    facade.store_compressed_context("wf_013", {"data": "new"})

    result = facade.query_compressed_context("wf_013")

    assert result["data"] == "new"

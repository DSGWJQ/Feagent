"""ExecutionSummaryManager 单元测试

测试执行总结管理器的核心功能：
- 存储与查询执行总结
- 事件发布
- 统计信息
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# =====================================================================
# Test Fixtures
# =====================================================================


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_execution_summary():
    """Mock ExecutionSummary"""
    summary = MagicMock()
    summary.workflow_id = "wf_001"
    summary.session_id = "session_001"
    summary.success = True
    summary.summary_id = "summary_001"
    return summary


@pytest.fixture
def manager(mock_event_bus):
    """ExecutionSummaryManager 实例"""
    from src.domain.services.execution_summary_manager import ExecutionSummaryManager

    return ExecutionSummaryManager(event_bus=mock_event_bus)


# =====================================================================
# Test: 初始化与存储管理
# =====================================================================


def test_manager_initialization(manager):
    """测试管理器初始化"""
    assert manager._execution_summaries == {}
    assert manager.event_bus is not None


def test_lazy_storage_initialization(manager):
    """测试懒加载初始化"""
    # 初始状态应该已经初始化
    assert hasattr(manager, "_execution_summaries")
    assert not hasattr(manager, "_channel_bridge")


# =====================================================================
# Test: 同步存储操作
# =====================================================================


def test_record_execution_summary_sync(manager, mock_execution_summary):
    """测试同步记录执行总结"""
    manager.record_execution_summary(mock_execution_summary)

    # 验证存储
    assert "wf_001" in manager._execution_summaries
    assert manager._execution_summaries["wf_001"] == mock_execution_summary


def test_record_summary_without_workflow_id(manager):
    """测试记录没有 workflow_id 的总结"""
    summary = MagicMock()
    summary.workflow_id = ""
    summary.session_id = "session_001"

    manager.record_execution_summary(summary)

    # 不应存储空 workflow_id 的总结
    assert "" not in manager._execution_summaries


def test_get_execution_summary_exists(manager, mock_execution_summary):
    """测试获取存在的执行总结"""
    manager.record_execution_summary(mock_execution_summary)

    result = manager.get_execution_summary("wf_001")
    assert result == mock_execution_summary


def test_get_execution_summary_not_exists(manager):
    """测试获取不存在的执行总结"""
    result = manager.get_execution_summary("wf_999")
    assert result is None


# =====================================================================
# Test: 异步存储与事件发布
# =====================================================================


@pytest.mark.asyncio
async def test_record_execution_summary_async(manager, mock_execution_summary, mock_event_bus):
    """测试异步记录并发布事件"""
    await manager.record_execution_summary_async(mock_execution_summary)

    # 验证存储
    assert "wf_001" in manager._execution_summaries
    assert manager._execution_summaries["wf_001"] == mock_execution_summary

    # 验证事件发布
    mock_event_bus.publish.assert_called_once()
    published_event = mock_event_bus.publish.call_args[0][0]
    assert published_event.workflow_id == "wf_001"
    assert published_event.session_id == "session_001"
    assert published_event.success is True
    assert published_event.summary_id == "summary_001"


@pytest.mark.asyncio
async def test_record_async_without_event_bus(mock_execution_summary):
    """测试异步记录（无 EventBus）"""
    from src.domain.services.execution_summary_manager import ExecutionSummaryManager

    manager = ExecutionSummaryManager(event_bus=None)
    await manager.record_execution_summary_async(mock_execution_summary)

    # 验证存储仍然成功
    assert "wf_001" in manager._execution_summaries


# =====================================================================
# Test: 统计信息
# =====================================================================


def test_get_summary_statistics_empty(manager):
    """测试空统计"""
    stats = manager.get_summary_statistics()

    assert stats["total"] == 0
    assert stats["successful"] == 0
    assert stats["failed"] == 0


def test_get_summary_statistics_with_data(manager):
    """测试有数据的统计"""
    # 添加成功总结
    summary1 = MagicMock()
    summary1.workflow_id = "wf_001"
    summary1.success = True
    manager.record_execution_summary(summary1)

    # 添加失败总结
    summary2 = MagicMock()
    summary2.workflow_id = "wf_002"
    summary2.success = False
    manager.record_execution_summary(summary2)

    # 添加另一个成功总结
    summary3 = MagicMock()
    summary3.workflow_id = "wf_003"
    summary3.success = True
    manager.record_execution_summary(summary3)

    stats = manager.get_summary_statistics()

    assert stats["total"] == 3
    assert stats["successful"] == 2
    assert stats["failed"] == 1


def test_get_all_summaries(manager, mock_execution_summary):
    """测试获取所有总结"""
    manager.record_execution_summary(mock_execution_summary)

    summary2 = MagicMock()
    summary2.workflow_id = "wf_002"
    manager.record_execution_summary(summary2)

    all_summaries = manager.get_all_summaries()

    assert len(all_summaries) == 2
    assert "wf_001" in all_summaries
    assert "wf_002" in all_summaries


def test_get_all_summaries_returns_copy(manager, mock_execution_summary):
    """测试获取所有总结返回副本"""
    manager.record_execution_summary(mock_execution_summary)

    all_summaries = manager.get_all_summaries()
    all_summaries["wf_999"] = MagicMock()

    # 修改副本不应影响原始存储
    assert "wf_999" not in manager._execution_summaries


# =====================================================================
# Test: 边界情况
# =====================================================================


def test_record_duplicate_workflow_id_overwrites(manager, mock_execution_summary):
    """测试记录重复的 workflow_id 会覆盖"""
    manager.record_execution_summary(mock_execution_summary)

    # 创建新总结，相同 workflow_id
    new_summary = MagicMock()
    new_summary.workflow_id = "wf_001"
    new_summary.session_id = "session_002"
    manager.record_execution_summary(new_summary)

    # 应该被新总结覆盖
    result = manager.get_execution_summary("wf_001")
    assert result == new_summary
    assert result.session_id == "session_002"


@pytest.mark.asyncio
async def test_record_async_with_missing_attributes(manager, mock_event_bus):
    """测试异步记录缺少属性的总结"""
    summary = MagicMock()
    summary.workflow_id = "wf_001"
    # 缺少 session_id, success, summary_id 属性
    del summary.session_id
    del summary.success
    del summary.summary_id

    await manager.record_execution_summary_async(summary)

    # 验证存储成功（使用 getattr 默认值）
    assert "wf_001" in manager._execution_summaries

    # 验证事件发布
    mock_event_bus.publish.assert_called_once()
    published_event = mock_event_bus.publish.call_args[0][0]
    assert published_event.workflow_id == "wf_001"
    assert published_event.session_id == ""
    assert published_event.success is False  # 修复：默认值为 False（与统计一致）
    assert published_event.summary_id == ""


# =====================================================================
# Test: 管理器无 EventBus 场景
# =====================================================================


def test_manager_without_event_bus():
    """测试无 EventBus 的管理器"""
    from src.domain.services.execution_summary_manager import ExecutionSummaryManager

    manager = ExecutionSummaryManager(event_bus=None)

    summary = MagicMock()
    summary.workflow_id = "wf_001"
    manager.record_execution_summary(summary)

    # 验证存储成功
    assert "wf_001" in manager._execution_summaries


@pytest.mark.asyncio
async def test_manager_without_event_bus_async():
    """测试无 EventBus 的管理器异步操作"""
    from src.domain.services.execution_summary_manager import ExecutionSummaryManager

    manager = ExecutionSummaryManager(event_bus=None)

    summary = MagicMock()
    summary.workflow_id = "wf_001"
    summary.session_id = "session_001"
    summary.success = True
    summary.summary_id = "summary_001"

    # 不应抛出异常
    await manager.record_execution_summary_async(summary)

    # 验证存储成功
    assert "wf_001" in manager._execution_summaries


# =====================================================================
# Test: Codex Review 修复场景
# =====================================================================


def test_get_execution_summary_returns_copy(manager, mock_execution_summary):
    """测试 get_execution_summary 返回副本（数据隔离）"""
    manager.record_execution_summary(mock_execution_summary)

    # 获取总结
    result = manager.get_execution_summary("wf_001")
    assert result is not None
    assert result.workflow_id == "wf_001"

    # 修改返回值不应影响内部状态
    original_session_id = result.session_id
    result.session_id = "modified_session"

    # 再次获取，应该是原始值
    result2 = manager.get_execution_summary("wf_001")
    assert result2.session_id == original_session_id


@pytest.mark.asyncio
async def test_success_default_consistency_with_statistics(manager):
    """测试 success 默认值与统计逻辑一致"""
    summary_without_success = MagicMock()
    summary_without_success.workflow_id = "wf_no_success"
    summary_without_success.session_id = "session_001"
    summary_without_success.summary_id = "summary_001"
    # 删除 success 属性，模拟缺失场景
    del summary_without_success.success

    # 记录总结
    await manager.record_execution_summary_async(summary_without_success)

    # 获取统计
    stats = manager.get_summary_statistics()

    # 验证：缺失 success 的总结应被计为失败
    assert stats["total"] == 1
    assert stats["successful"] == 0
    assert stats["failed"] == 1

"""UnifiedLogIntegration 单元测试

基于 Codex 分析的 TDD 测试套件（Phase 34.10）：
- 初始化与配置 (3 tests)
- 日志记录方法包装 (5 tests)
- 查询与过滤 (4 tests)
- 统计与聚合 (3 tests)
- 多源日志合并 (3 tests)
- 边界场景 (2 tests)

总计: 20 tests
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_log_collector():
    """Mock UnifiedLogCollector"""
    collector = MagicMock()

    # Mock logs storage
    collector.logs = []

    # Mock 方法返回值
    collector.get_recent.return_value = []
    collector.filter_by_level.return_value = []
    collector.filter_by_source.return_value = []
    collector.filter_by_time_range.return_value = []
    collector.aggregate_by_source.return_value = {}
    collector.aggregate_by_level.return_value = {}
    collector.get_statistics.return_value = {
        "total_entries": 0,
        "by_level": {},
        "by_source": {},
    }
    collector.export_json.return_value = "[]"

    return collector


@pytest.fixture
def mock_message_log_accessor():
    """Mock 访问 message_log 的 gateway"""
    accessor = MagicMock()
    accessor.get_messages.return_value = [
        {"timestamp": "2025-01-01T10:00:00", "level": "INFO", "content": "Message 1"},
        {"timestamp": "2025-01-01T10:01:00", "level": "WARNING", "content": "Message 2"},
    ]
    return accessor


@pytest.fixture
def mock_container_log_accessor():
    """Mock 访问 container_logs 的 gateway"""
    accessor = MagicMock()
    accessor.get_container_logs.return_value = {
        "container_001": [
            {"timestamp": "2025-01-01T10:00:30", "level": "DEBUG", "message": "Container started"},
            {"timestamp": "2025-01-01T10:01:30", "level": "ERROR", "message": "Container failed"},
        ]
    }
    return accessor


@pytest.fixture
def integration(mock_log_collector, mock_message_log_accessor, mock_container_log_accessor):
    """UnifiedLogIntegration 实例"""
    from src.domain.services.unified_log_integration import UnifiedLogIntegration

    return UnifiedLogIntegration(
        log_collector=mock_log_collector,
        message_log_accessor=mock_message_log_accessor,
        container_log_accessor=mock_container_log_accessor,
    )


# =====================================================================
# Test: 初始化与配置 (3 tests)
# =====================================================================


def test_integration_initialization(
    mock_log_collector, mock_message_log_accessor, mock_container_log_accessor
):
    """测试集成模块初始化"""
    from src.domain.services.unified_log_integration import UnifiedLogIntegration

    integration = UnifiedLogIntegration(
        log_collector=mock_log_collector,
        message_log_accessor=mock_message_log_accessor,
        container_log_accessor=mock_container_log_accessor,
    )

    assert integration.log_collector == mock_log_collector
    assert integration.message_log_accessor == mock_message_log_accessor
    assert integration.container_log_accessor == mock_container_log_accessor


def test_integration_without_optional_accessors(mock_log_collector):
    """测试无可选accessor初始化"""
    from src.domain.services.unified_log_integration import UnifiedLogIntegration

    integration = UnifiedLogIntegration(
        log_collector=mock_log_collector,
        message_log_accessor=None,
        container_log_accessor=None,
    )

    assert integration.log_collector == mock_log_collector
    assert integration.message_log_accessor is None
    assert integration.container_log_accessor is None


def test_integration_with_default_collector():
    """测试默认collector初始化（懒加载）"""
    from src.domain.services.unified_log_integration import UnifiedLogIntegration

    integration = UnifiedLogIntegration()

    # 应该有默认的 log_collector
    assert integration.log_collector is not None
    assert hasattr(integration.log_collector, "log")


# =====================================================================
# Test: 日志记录方法包装 (5 tests)
# =====================================================================


def test_log_debug(integration, mock_log_collector):
    """测试 DEBUG 级别日志记录"""
    integration.log_debug("TestSource", "Debug message", {"key": "value"})

    mock_log_collector.debug.assert_called_once_with(
        "TestSource", "Debug message", {"key": "value"}
    )


def test_log_info(integration, mock_log_collector):
    """测试 INFO 级别日志记录"""
    integration.log_info("TestSource", "Info message")

    mock_log_collector.info.assert_called_once_with("TestSource", "Info message", None)


def test_log_warning(integration, mock_log_collector):
    """测试 WARNING 级别日志记录"""
    integration.log_warning("TestSource", "Warning message", {"error_code": "W001"})

    mock_log_collector.warning.assert_called_once_with(
        "TestSource", "Warning message", {"error_code": "W001"}
    )


def test_log_error(integration, mock_log_collector):
    """测试 ERROR 级别日志记录"""
    integration.log_error("TestSource", "Error message", {"traceback": "..."})

    mock_log_collector.error.assert_called_once_with(
        "TestSource", "Error message", {"traceback": "..."}
    )


def test_log_critical(integration, mock_log_collector):
    """测试 CRITICAL 级别日志记录"""
    integration.log_critical("TestSource", "Critical failure")

    mock_log_collector.critical.assert_called_once_with("TestSource", "Critical failure", None)


# =====================================================================
# Test: 查询与过滤 (4 tests)
# =====================================================================


def test_get_recent_logs(integration, mock_log_collector):
    """测试获取最近N条日志"""
    mock_log_collector.get_recent.return_value = [
        {"level": "INFO", "message": "Log 1"},
        {"level": "ERROR", "message": "Log 2"},
    ]

    result = integration.get_recent_logs(count=2)

    mock_log_collector.get_recent.assert_called_once_with(2)
    assert len(result) == 2


def test_filter_logs_by_level(integration, mock_log_collector):
    """测试按级别过滤日志"""
    mock_log_collector.filter_by_level.return_value = [
        {"level": "ERROR", "message": "Error 1"},
        {"level": "ERROR", "message": "Error 2"},
    ]

    result = integration.filter_logs_by_level("ERROR")

    mock_log_collector.filter_by_level.assert_called_once_with("ERROR")
    assert len(result) == 2
    assert all(log["level"] == "ERROR" for log in result)


def test_filter_logs_by_source(integration, mock_log_collector):
    """测试按来源过滤日志"""
    mock_log_collector.filter_by_source.return_value = [
        {"source": "CoordinatorAgent", "message": "Coordinator log 1"},
        {"source": "CoordinatorAgent", "message": "Coordinator log 2"},
    ]

    result = integration.filter_logs_by_source("CoordinatorAgent")

    mock_log_collector.filter_by_source.assert_called_once_with("CoordinatorAgent")
    assert len(result) == 2


def test_filter_logs_by_time_range(integration, mock_log_collector):
    """测试按时间范围过滤日志"""
    since = datetime(2025, 1, 1, 10, 0, 0)
    until = datetime(2025, 1, 1, 11, 0, 0)

    mock_log_collector.filter_by_time_range.return_value = [
        {"timestamp": "2025-01-01T10:30:00", "message": "Log 1"},
    ]

    result = integration.filter_logs_by_time_range(since=since, until=until)

    mock_log_collector.filter_by_time_range.assert_called_once_with(since=since, until=until)
    assert len(result) == 1


# =====================================================================
# Test: 统计与聚合 (3 tests)
# =====================================================================


def test_get_log_statistics(integration, mock_log_collector):
    """测试获取日志统计信息"""
    mock_log_collector.get_statistics.return_value = {
        "total_entries": 100,
        "by_level": {"INFO": 60, "ERROR": 40},
        "by_source": {"CoordinatorAgent": 70, "WorkflowAgent": 30},
    }

    stats = integration.get_log_statistics()

    mock_log_collector.get_statistics.assert_called_once()
    assert stats["total_entries"] == 100
    assert stats["by_level"]["INFO"] == 60


def test_aggregate_logs_by_source(integration, mock_log_collector):
    """测试按来源聚合日志"""
    mock_log_collector.aggregate_by_source.return_value = {
        "CoordinatorAgent": 50,
        "WorkflowAgent": 30,
        "ConversationAgent": 20,
    }

    result = integration.aggregate_logs_by_source()

    mock_log_collector.aggregate_by_source.assert_called_once()
    assert result["CoordinatorAgent"] == 50


def test_aggregate_logs_by_level(integration, mock_log_collector):
    """测试按级别聚合日志"""
    mock_log_collector.aggregate_by_level.return_value = {
        "DEBUG": 10,
        "INFO": 60,
        "WARNING": 20,
        "ERROR": 10,
    }

    result = integration.aggregate_logs_by_level()

    mock_log_collector.aggregate_by_level.assert_called_once()
    assert result["INFO"] == 60


# =====================================================================
# Test: 多源日志合并 (3 tests)
# =====================================================================


def test_get_merged_logs_all_sources(
    integration, mock_log_collector, mock_message_log_accessor, mock_container_log_accessor
):
    """测试合并所有来源的日志"""
    # Mock log_collector 日志
    mock_log_collector.logs = [
        MagicMock(
            level="INFO",
            source="CoordinatorAgent",
            message="Coordinator log",
            timestamp=datetime(2025, 1, 1, 10, 0, 15),
            to_dict=lambda: {
                "level": "INFO",
                "source": "CoordinatorAgent",
                "message": "Coordinator log",
                "timestamp": "2025-01-01T10:00:15",
            },
        )
    ]

    result = integration.get_merged_logs()

    # 应合并 log_collector + message_log + container_logs
    # 总计：1 (collector) + 2 (messages) + 2 (containers) = 5
    assert len(result) >= 3  # 至少有collector和message_log

    # 验证时间排序（从旧到新）
    timestamps = [log.get("timestamp") for log in result]
    assert timestamps == sorted(timestamps)


def test_get_merged_logs_without_optional_sources(mock_log_collector):
    """测试无可选源时的日志合并"""
    from src.domain.services.unified_log_integration import UnifiedLogIntegration

    integration = UnifiedLogIntegration(
        log_collector=mock_log_collector,
        message_log_accessor=None,
        container_log_accessor=None,
    )

    mock_log_collector.logs = [
        MagicMock(
            level="INFO",
            source="Test",
            message="Log",
            timestamp=datetime.now(),
            to_dict=lambda: {
                "level": "INFO",
                "source": "Test",
                "message": "Log",
                "timestamp": datetime.now().isoformat(),
            },
        )
    ]

    result = integration.get_merged_logs()

    # 只有 log_collector 的日志
    assert len(result) == 1


def test_get_merged_logs_time_sorted(integration, mock_log_collector):
    """测试合并日志按时间排序"""
    # Mock 不同时间的日志
    now = datetime(2025, 1, 1, 10, 0, 0)
    mock_log_collector.logs = [
        MagicMock(
            timestamp=now + timedelta(minutes=5),
            to_dict=lambda t=now + timedelta(minutes=5): {
                "timestamp": t.isoformat(),
                "message": "Latest",
            },
        ),
        MagicMock(
            timestamp=now,
            to_dict=lambda t=now: {"timestamp": t.isoformat(), "message": "Earliest"},
        ),
        MagicMock(
            timestamp=now + timedelta(minutes=2),
            to_dict=lambda t=now + timedelta(minutes=2): {
                "timestamp": t.isoformat(),
                "message": "Middle",
            },
        ),
    ]

    result = integration.get_merged_logs()

    # 验证按时间排序
    timestamps = [log["timestamp"] for log in result]
    assert timestamps == sorted(timestamps)


# =====================================================================
# Test: 边界场景 (2 tests)
# =====================================================================


def test_clear_logs(integration, mock_log_collector):
    """测试清空日志"""
    integration.clear_logs()

    mock_log_collector.clear.assert_called_once()


def test_export_logs_json(integration, mock_log_collector):
    """测试导出日志为JSON"""
    mock_log_collector.export_json.return_value = '[{"level": "INFO"}]'

    result = integration.export_logs_json(indent=4)

    mock_log_collector.export_json.assert_called_once_with(indent=4)
    assert result == '[{"level": "INFO"}]'

"""ContextInjectionManager 单元测试

Phase 34.12: 上下文注入管理器提取
- 测试设计: TDD驱动，8-10个测试覆盖所有注入方法
- 覆盖范围: 注入类型映射、日志查询、向后兼容性
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_injection_manager():
    """Mock ContextInjectionManager"""
    manager = MagicMock()

    # Mock inject methods
    manager.add_injection.return_value = MagicMock(
        session_id="test_session",
        injection_type="WARNING",
        content="test content",
    )
    manager.inject_warning.return_value = MagicMock()
    manager.inject_intervention.return_value = MagicMock()
    manager.inject_memory.return_value = MagicMock()
    manager.inject_observation.return_value = MagicMock()

    return manager


@pytest.fixture
def mock_injection_logger():
    """Mock InjectionLogger"""
    logger = MagicMock()
    logger.get_logs.return_value = [
        {"session_id": "session1", "content": "log1"},
        {"session_id": "session2", "content": "log2"},
    ]
    logger.get_logs_by_session.return_value = [
        {"session_id": "session1", "content": "log1"},
    ]
    return logger


@pytest.fixture
def manager(mock_injection_manager, mock_injection_logger):
    """创建 ContextInjectionManager 实例"""
    from src.domain.services.context_injection_manager import ContextInjectionManager

    return ContextInjectionManager(
        injection_manager=mock_injection_manager,
        injection_logger=mock_injection_logger,
    )


# ==================== 测试1: 初始化 ====================


def test_manager_initialization(mock_injection_manager, mock_injection_logger):
    """测试管理器初始化"""
    from src.domain.services.context_injection_manager import ContextInjectionManager

    manager = ContextInjectionManager(
        injection_manager=mock_injection_manager,
        injection_logger=mock_injection_logger,
    )

    assert manager._injection_manager == mock_injection_manager
    assert manager._injection_logger == mock_injection_logger


# ==================== 测试2-3: inject_context 与类型映射 ====================


def test_inject_context_with_warning_type(manager, mock_injection_manager):
    """测试注入 WARNING 类型，映射到 PRE_THINKING 注入点"""
    from src.domain.services.context_injection import InjectionPoint, InjectionType

    manager.inject_context(
        session_id="test_session",
        injection_type=InjectionType.WARNING,
        content="Warning message",
        reason="Test warning",
        priority=10,
    )

    # 验证调用了 add_injection
    mock_injection_manager.add_injection.assert_called_once()

    # 验证注入对象的属性
    call_args = mock_injection_manager.add_injection.call_args[0][0]
    assert call_args.session_id == "test_session"
    assert call_args.injection_type == InjectionType.WARNING
    assert call_args.injection_point == InjectionPoint.PRE_THINKING
    assert call_args.content == "Warning message"
    assert call_args.source == "coordinator"
    assert call_args.reason == "Test warning"
    assert call_args.priority == 10


def test_inject_context_with_intervention_type(manager, mock_injection_manager):
    """测试注入 INTERVENTION 类型，映射到 INTERVENTION 注入点"""
    from src.domain.services.context_injection import InjectionPoint, InjectionType

    manager.inject_context(
        session_id="test_session",
        injection_type=InjectionType.INTERVENTION,
        content="Intervention message",
        reason="Test intervention",
        priority=5,
    )

    call_args = mock_injection_manager.add_injection.call_args[0][0]
    assert call_args.injection_type == InjectionType.INTERVENTION
    assert call_args.injection_point == InjectionPoint.INTERVENTION


def test_inject_context_with_default_type(manager, mock_injection_manager):
    """测试注入其他类型，默认映射到 PRE_LOOP 注入点"""
    from src.domain.services.context_injection import InjectionPoint, InjectionType

    manager.inject_context(
        session_id="test_session",
        injection_type=InjectionType.SUPPLEMENT,
        content="Supplement message",
        reason="Test supplement",
    )

    call_args = mock_injection_manager.add_injection.call_args[0][0]
    assert call_args.injection_type == InjectionType.SUPPLEMENT
    assert call_args.injection_point == InjectionPoint.PRE_LOOP


# ==================== 测试4-7: 四类专用注入方法 ====================


def test_inject_warning(manager, mock_injection_manager):
    """测试 inject_warning 方法"""
    manager.inject_warning(
        session_id="test_session",
        warning_message="Test warning",
        rule_id="rule_001",
    )

    mock_injection_manager.inject_warning.assert_called_once_with(
        session_id="test_session",
        content="Test warning",
        source="coordinator",
        reason="规则 rule_001 触发",
    )


def test_inject_warning_without_rule_id(manager, mock_injection_manager):
    """测试 inject_warning 无 rule_id 时使用默认原因"""
    manager.inject_warning(
        session_id="test_session",
        warning_message="Test warning",
        rule_id=None,
    )

    mock_injection_manager.inject_warning.assert_called_once_with(
        session_id="test_session",
        content="Test warning",
        source="coordinator",
        reason="安全检测",
    )


def test_inject_intervention(manager, mock_injection_manager):
    """测试 inject_intervention 方法"""
    manager.inject_intervention(
        session_id="test_session",
        intervention_message="Test intervention",
        reason="Custom reason",
    )

    mock_injection_manager.inject_intervention.assert_called_once_with(
        session_id="test_session",
        content="Test intervention",
        source="coordinator",
        reason="Custom reason",
    )


def test_inject_memory(manager, mock_injection_manager):
    """测试 inject_memory 方法"""
    manager.inject_memory(
        session_id="test_session",
        memory_content="Test memory",
        relevance_score=0.85,
    )

    mock_injection_manager.inject_memory.assert_called_once_with(
        session_id="test_session",
        content="Test memory",
        source="memory_system",
        relevance_score=0.85,
    )


def test_inject_observation(manager, mock_injection_manager):
    """测试 inject_observation 方法"""
    manager.inject_observation(
        session_id="test_session",
        observation="Test observation",
        source="custom_monitor",
    )

    mock_injection_manager.inject_observation.assert_called_once_with(
        session_id="test_session",
        content="Test observation",
        source="custom_monitor",
    )


def test_inject_observation_with_default_source(manager, mock_injection_manager):
    """测试 inject_observation 使用默认 source"""
    manager.inject_observation(
        session_id="test_session",
        observation="Test observation",
    )

    mock_injection_manager.inject_observation.assert_called_once_with(
        session_id="test_session",
        content="Test observation",
        source="monitor",
    )


# ==================== 测试8-9: 日志查询方法 ====================


def test_get_injection_logs(manager, mock_injection_logger):
    """测试获取所有注入日志"""
    logs = manager.get_injection_logs()

    assert len(logs) == 2
    assert logs[0]["session_id"] == "session1"
    assert logs[1]["session_id"] == "session2"

    mock_injection_logger.get_logs.assert_called_once()


def test_get_injection_logs_by_session(manager, mock_injection_logger):
    """测试按会话获取注入日志"""
    logs = manager.get_injection_logs_by_session("session1")

    assert len(logs) == 1
    assert logs[0]["session_id"] == "session1"

    mock_injection_logger.get_logs_by_session.assert_called_once_with("session1")


# ==================== 测试10: 边界场景 ====================


def test_inject_context_with_default_priority(manager, mock_injection_manager):
    """测试注入上下文使用默认优先级（30）"""
    from src.domain.services.context_injection import InjectionType

    manager.inject_context(
        session_id="test_session",
        injection_type=InjectionType.WARNING,
        content="Test content",
        reason="Test reason",
        # 不传 priority 参数
    )

    call_args = mock_injection_manager.add_injection.call_args[0][0]
    assert call_args.priority == 30

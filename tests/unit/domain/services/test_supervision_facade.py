"""SupervisionFacade 单元测试

Phase 34.13: 监督模块提取
- 测试设计: TDD驱动，10-12个测试覆盖所有监督功能
- 覆盖范围: 上下文监督、保存请求监督、决策链监督、干预执行、日志查询
"""

from unittest.mock import MagicMock, call

import pytest


@pytest.fixture
def mock_supervision_module():
    """Mock SupervisionModule"""
    from src.domain.services.supervision_module import SupervisionAction, SupervisionInfo

    module = MagicMock()

    # analyze_* methods return list[SupervisionInfo], not dict
    module.analyze_context.return_value = []
    module.analyze_save_request.return_value = []
    module.analyze_decision_chain.return_value = [
        SupervisionInfo(
            session_id="test_session",
            action=SupervisionAction.WARNING,
            content="decision chain warning",
            trigger_rule="rule_001",
            trigger_condition="test condition",
        )
    ]
    return module


@pytest.fixture
def mock_supervision_logger():
    """Mock SupervisionLogger"""
    logger = MagicMock()
    logger.get_logs.return_value = [
        {"session_id": "s1", "action": "context_analyzed"},
        {"session_id": "s2", "action": "request_blocked"},
    ]
    logger.get_logs_by_session.return_value = [
        {"session_id": "s1", "action": "context_analyzed"},
    ]
    return logger


@pytest.fixture
def mock_supervision_coordinator():
    """Mock SupervisionCoordinator"""
    from datetime import datetime

    coordinator = MagicMock()
    coordinator.conversation_supervision = MagicMock()
    coordinator.strategy_repository = MagicMock()
    coordinator.efficiency_monitor = MagicMock()
    coordinator.record_intervention.return_value = None

    # Mock event object with attributes
    mock_event = MagicMock()
    mock_event.intervention_type = "bias_check"
    mock_event.reason = "test reason"
    mock_event.source = "conversation_supervision"
    mock_event.target_id = "user_input"
    mock_event.severity = "warning"
    mock_event.timestamp = datetime(2025, 12, 11, 10, 0, 0)

    coordinator.get_intervention_events.return_value = [mock_event]
    return coordinator


@pytest.fixture
def mock_context_injection_manager():
    """Mock ContextInjectionManager"""
    manager = MagicMock()
    manager.inject_warning.return_value = MagicMock(id="inj_001")
    manager.inject_intervention.return_value = MagicMock(id="inj_002")
    manager.add_injection.return_value = None
    return manager


@pytest.fixture
def mock_log_collector():
    """Mock UnifiedLogCollector"""
    collector = MagicMock()
    return collector


@pytest.fixture
def facade(
    mock_supervision_module,
    mock_supervision_logger,
    mock_supervision_coordinator,
    mock_context_injection_manager,
    mock_log_collector,
):
    """创建 SupervisionFacade 实例"""
    from src.domain.services.supervision_facade import SupervisionFacade

    return SupervisionFacade(
        supervision_module=mock_supervision_module,
        supervision_logger=mock_supervision_logger,
        supervision_coordinator=mock_supervision_coordinator,
        context_injection_manager=mock_context_injection_manager,
        log_collector=mock_log_collector,
    )


# ==================== 测试1: 初始化 ====================


def test_facade_initialization(
    mock_supervision_module,
    mock_supervision_logger,
    mock_supervision_coordinator,
    mock_context_injection_manager,
    mock_log_collector,
):
    """测试 Facade 初始化"""
    from src.domain.services.supervision_facade import SupervisionFacade

    facade = SupervisionFacade(
        supervision_module=mock_supervision_module,
        supervision_logger=mock_supervision_logger,
        supervision_coordinator=mock_supervision_coordinator,
        context_injection_manager=mock_context_injection_manager,
        log_collector=mock_log_collector,
    )

    assert facade._supervision_module == mock_supervision_module
    assert facade._supervision_logger == mock_supervision_logger
    assert facade._supervision_coordinator == mock_supervision_coordinator
    assert facade._context_injection_manager == mock_context_injection_manager
    assert facade._log_collector == mock_log_collector


def test_facade_exposes_coordinator_aliases(facade, mock_supervision_coordinator):
    """测试 Facade 暴露 SupervisionCoordinator 的子模块别名"""
    assert facade.conversation_supervision == mock_supervision_coordinator.conversation_supervision
    assert facade.strategy_repository == mock_supervision_coordinator.strategy_repository
    assert facade.efficiency_monitor == mock_supervision_coordinator.efficiency_monitor


# ==================== 测试2-4: 三个 supervise_* 方法 ====================


def test_supervise_context(facade, mock_supervision_module):
    """测试监督上下文"""
    context = {"user_input": "test query", "history": []}

    result = facade.supervise_context(context)

    assert result == []  # Returns list, not dict
    mock_supervision_module.analyze_context.assert_called_once_with(context)


def test_supervise_save_request(facade, mock_supervision_module):
    """测试监督保存请求"""
    save_request = {"path": "/tmp/test.txt", "content": "data"}

    result = facade.supervise_save_request(save_request)

    assert result == []  # Returns list, not dict
    mock_supervision_module.analyze_save_request.assert_called_once_with(save_request)


def test_supervise_decision_chain(facade, mock_supervision_module):
    """测试监督决策链"""
    decisions = [{"step": 1, "action": "query_db"}]
    session_id = "test_session"

    result = facade.supervise_decision_chain(decisions, session_id)

    # Returns list[SupervisionInfo]
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].session_id == "test_session"
    assert result[0].content == "decision chain warning"
    mock_supervision_module.analyze_decision_chain.assert_called_once_with(decisions, session_id)


# ==================== 测试5-7: execute_intervention 三种 action ====================


def test_execute_intervention_warning_action(
    facade, mock_context_injection_manager, mock_supervision_logger, mock_log_collector
):
    """测试执行 WARNING 干预动作"""
    from src.domain.services.supervision_module import SupervisionAction, SupervisionInfo

    supervision_info = SupervisionInfo(
        session_id="test_session",
        action=SupervisionAction.WARNING,
        content="test warning content",
        trigger_rule="rule_001",
        trigger_condition="Potential security risk",
    )

    facade.execute_intervention(supervision_info)

    # 验证调用了 inject_warning
    mock_context_injection_manager.inject_warning.assert_called_once_with(
        session_id="test_session",
        warning_message="test warning content",
        rule_id=None,
    )

    # 验证记录了监督日志 - 使用位置参数检查
    mock_supervision_logger.log_intervention.assert_called_once()
    log_call_args = mock_supervision_logger.log_intervention.call_args[0]  # Positional args
    assert log_call_args[0] == supervision_info  # First arg is SupervisionInfo
    assert log_call_args[1] == "warning_injected"  # Second arg is status

    # 验证记录了审计日志级别
    mock_log_collector.log.assert_called_once()
    log_call = mock_log_collector.log.call_args[1]
    assert log_call["level"] == "info"


def test_execute_intervention_replace_action(
    facade, mock_context_injection_manager, mock_supervision_logger, mock_log_collector
):
    """测试执行 REPLACE 干预动作"""
    from src.domain.services.supervision_module import SupervisionAction, SupervisionInfo

    supervision_info = SupervisionInfo(
        session_id="test_session",
        action=SupervisionAction.REPLACE,
        content="替换后的安全内容",
        trigger_rule="rule_002",
        trigger_condition="Content policy violation",
    )

    facade.execute_intervention(supervision_info)

    # 验证记录了审计日志级别
    mock_log_collector.log.assert_called_once()
    log_call = mock_log_collector.log.call_args[1]
    assert log_call["level"] == "warning"

    # 验证调用了 add_injection（通过 _create_supplement_injection）
    mock_context_injection_manager.add_injection.assert_called_once()
    injection_arg = mock_context_injection_manager.add_injection.call_args[0][0]
    assert injection_arg.session_id == "test_session"
    assert injection_arg.content == "替换后的安全内容"
    # 验证是 SUPPLEMENT 类型，PRE_THINKING 注入点
    from src.domain.services.context_injection import InjectionPoint, InjectionType

    assert injection_arg.injection_type == InjectionType.SUPPLEMENT
    assert injection_arg.injection_point == InjectionPoint.PRE_THINKING

    # 验证记录了监督日志 - 使用位置参数检查
    mock_supervision_logger.log_intervention.assert_called_once()
    log_call_args = mock_supervision_logger.log_intervention.call_args[0]  # Positional args
    assert log_call_args[0] == supervision_info  # First arg is SupervisionInfo
    assert log_call_args[1] == "content_replaced"  # Second arg is status


def test_execute_intervention_terminate_action(
    facade, mock_context_injection_manager, mock_supervision_logger, mock_log_collector
):
    """测试执行 TERMINATE 干预动作"""
    from src.domain.services.supervision_module import SupervisionAction, SupervisionInfo

    supervision_info = SupervisionInfo(
        session_id="test_session",
        action=SupervisionAction.TERMINATE,
        content="任务已终止",
        trigger_rule="rule_003",
        trigger_condition="Critical safety violation",
    )

    facade.execute_intervention(supervision_info)

    # 验证记录了审计日志级别
    mock_log_collector.log.assert_called_once()
    log_call = mock_log_collector.log.call_args[1]
    assert log_call["level"] == "error"

    # 验证调用了 inject_intervention
    mock_context_injection_manager.inject_intervention.assert_called_once_with(
        session_id="test_session",
        intervention_message="任务已终止",
        reason="Critical safety violation",
    )

    # 验证记录了监督日志 - 使用位置参数检查
    mock_supervision_logger.log_intervention.assert_called_once()
    log_call_args = mock_supervision_logger.log_intervention.call_args[0]  # Positional args
    assert log_call_args[0] == supervision_info  # First arg is SupervisionInfo
    assert log_call_args[1] == "task_terminated"  # Second arg is status


def test_execute_intervention_unknown_action_defaults_to_unknown_action(
    facade, mock_context_injection_manager, mock_supervision_logger, mock_log_collector
):
    """测试 execute_intervention 未知 action 分支（防御性覆盖未来扩展/非法注入）"""
    from enum import Enum

    from src.domain.services.supervision_module import SupervisionInfo

    class DummyAction(str, Enum):
        UNKNOWN = "unknown"

    supervision_info = SupervisionInfo(
        session_id="test_session",
        action=DummyAction.UNKNOWN,  # 非 SupervisionAction，用于覆盖 else 分支
        content="some content",
        trigger_rule="rule_unknown",
        trigger_condition="unknown condition",
    )

    result = facade.execute_intervention(supervision_info)

    assert result["success"] is False
    assert result["action"] == "unknown"
    assert result["intervention_type"] == "unknown_action"

    mock_context_injection_manager.inject_warning.assert_not_called()
    mock_context_injection_manager.add_injection.assert_not_called()
    mock_context_injection_manager.inject_intervention.assert_not_called()

    mock_supervision_logger.log_intervention.assert_called_once_with(
        supervision_info, "unknown_action"
    )
    mock_log_collector.log.assert_called_once()
    log_call = mock_log_collector.log.call_args[1]
    assert log_call["level"] == "error"


# ==================== 测试8-9: 日志查询方法 ====================


def test_get_supervision_logs(facade, mock_supervision_logger):
    """测试获取所有监督日志"""
    logs = facade.get_supervision_logs()

    assert len(logs) == 2
    assert logs[0]["session_id"] == "s1"
    assert logs[1]["session_id"] == "s2"

    mock_supervision_logger.get_logs.assert_called_once()


def test_get_supervision_logs_by_session(facade, mock_supervision_logger):
    """测试按会话获取监督日志"""
    logs = facade.get_supervision_logs_by_session("s1")

    assert len(logs) == 1
    assert logs[0]["session_id"] == "s1"

    mock_supervision_logger.get_logs_by_session.assert_called_once_with("s1")


# ==================== 测试10: _create_supplement_injection 辅助方法 ====================


def test_create_supplement_injection(facade):
    """测试创建 SUPPLEMENT 注入对象"""
    session_id = "test_session"
    content = "补充内容"
    reason = "监督模块替换"

    injection = facade._create_supplement_injection(session_id, content, reason)

    from src.domain.services.context_injection import InjectionPoint, InjectionType

    assert injection.session_id == session_id
    assert injection.content == content
    assert injection.reason == reason
    assert injection.injection_type == InjectionType.SUPPLEMENT
    assert injection.injection_point == InjectionPoint.PRE_THINKING
    assert injection.source == "coordinator"
    assert injection.priority == 40  # 监督模块优先级


# ==================== 测试11: supervise_input 输入检查 ====================


def test_supervise_input_passes(facade, mock_supervision_coordinator, mock_supervision_logger):
    """测试 supervise_input 检查通过场景"""
    user_input = "正常的用户输入"

    # Mock check_all 返回 ComprehensiveCheckResult
    from src.domain.services.supervision import ComprehensiveCheckResult

    mock_result = ComprehensiveCheckResult(
        passed=True,
        issues=[],
        action="allow",
    )
    mock_supervision_coordinator.conversation_supervision.check_all.return_value = mock_result

    result = facade.supervise_input(user_input)

    assert result == {"passed": True, "issues": [], "action": "allow"}
    mock_supervision_coordinator.conversation_supervision.check_all.assert_called_once_with(
        user_input
    )
    # 不应记录 intervention
    mock_supervision_coordinator.record_intervention.assert_not_called()


def test_supervise_input_fails_with_issues(
    facade, mock_supervision_coordinator, mock_supervision_logger
):
    """测试 supervise_input 检查失败场景"""
    user_input = "违规内容"

    # Mock check_all 返回 ComprehensiveCheckResult with issues
    from src.domain.services.supervision import ComprehensiveCheckResult, DetectionResult

    issue = DetectionResult(
        detected=True,
        category="profanity_check",
        severity="high",
        message="包含敏感词",
    )
    mock_result = ComprehensiveCheckResult(
        passed=False,
        issues=[issue],
        action="block",
    )
    mock_supervision_coordinator.conversation_supervision.check_all.return_value = mock_result

    # 不传 session_id，不应触发 record_intervention
    result = facade.supervise_input(user_input)

    assert result["passed"] is False
    assert len(result["issues"]) == 1
    assert result["issues"][0]["category"] == "profanity_check"
    assert result["action"] == "block"
    # 没有 session_id，不应记录 intervention
    mock_supervision_coordinator.record_intervention.assert_not_called()


def test_supervise_input_records_intervention_when_session_id_provided(
    facade, mock_supervision_coordinator
):
    """测试 supervise_input 在提供 session_id 时会记录干预事件（多 issue）"""
    user_input = "违规内容"
    session_id = "test_session"

    from src.domain.services.supervision import ComprehensiveCheckResult, DetectionResult

    issue_1 = DetectionResult(
        detected=True,
        category="profanity_check",
        severity="high",
        message="包含敏感词",
    )
    issue_2 = DetectionResult(
        detected=True,
        category="bias_check",
        severity="medium",
        message="存在偏见倾向",
    )
    mock_result = ComprehensiveCheckResult(
        passed=False,
        issues=[issue_1, issue_2],
        action="block",
    )
    mock_supervision_coordinator.conversation_supervision.check_all.return_value = mock_result

    facade.supervise_input(user_input, session_id=session_id)

    assert mock_supervision_coordinator.record_intervention.call_count == 2
    mock_supervision_coordinator.record_intervention.assert_has_calls(
        [
            call(
                intervention_type="profanity_check",
                reason="包含敏感词",
                source="conversation_supervision",
                target_id="user_input",
                severity="high",
                session_id="test_session",
            ),
            call(
                intervention_type="bias_check",
                reason="存在偏见倾向",
                source="conversation_supervision",
                target_id="user_input",
                severity="medium",
                session_id="test_session",
            ),
        ]
    )


# ==================== 测试12: 策略管理与事件查询 ====================


def test_add_supervision_strategy(facade, mock_supervision_coordinator, mock_log_collector):
    """测试添加监督策略"""
    strategy_name = "custom_rule_001"
    trigger_conditions = ["bias", "harmful"]
    action = "warn"
    priority = 15

    # Mock register to return a strategy_id
    mock_supervision_coordinator.strategy_repository.register.return_value = "strategy_001"

    result = facade.add_supervision_strategy(
        name=strategy_name,
        trigger_conditions=trigger_conditions,
        action=action,
        priority=priority,
    )

    # 验证返回值
    assert result == "strategy_001"

    # 验证调用了 register with correct parameters
    mock_supervision_coordinator.strategy_repository.register.assert_called_once_with(
        name=strategy_name,
        trigger_conditions=trigger_conditions,
        action=action,
        priority=priority,
    )

    # 验证记录了 info 日志
    mock_log_collector.log.assert_called_once()
    log_call = mock_log_collector.log.call_args[1]
    assert log_call["level"] == "info"
    assert log_call["source"] == "supervision_facade"
    assert strategy_name in log_call["message"]
    assert log_call["context"]["strategy_id"] == "strategy_001"
    assert log_call["context"]["trigger_conditions"] == trigger_conditions
    assert log_call["context"]["action"] == action


def test_get_intervention_events(facade, mock_supervision_coordinator):
    """测试获取干预事件历史"""
    events = facade.get_intervention_events()

    assert len(events) == 1
    assert events[0]["intervention_type"] == "bias_check"
    assert events[0]["reason"] == "test reason"
    assert events[0]["source"] == "conversation_supervision"
    assert events[0]["target_id"] == "user_input"
    assert events[0]["severity"] == "warning"
    assert events[0]["timestamp"] == "2025-12-11T10:00:00"

    mock_supervision_coordinator.get_intervention_events.assert_called_once()

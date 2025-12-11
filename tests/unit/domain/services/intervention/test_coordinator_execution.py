"""InterventionCoordinator 执行测试

Phase 35.0: 测试 REPLACE/TERMINATE 级别的实际执行逻辑
"""

from unittest.mock import MagicMock

import pytest

from src.domain.services.intervention import (
    InterventionCoordinator,
    InterventionLevel,
    ModificationResult,
    NodeReplacementRequest,
    TaskTerminationRequest,
    TerminationResult,
)


@pytest.fixture
def mock_workflow_modifier():
    """Mock WorkflowModifier"""
    modifier = MagicMock()
    # 默认返回成功的修改结果（直接创建 ModificationResult 实例）
    mock_result = ModificationResult(
        success=True,
        modified_workflow={"nodes": []},
        original_node_id="node-001",
        replacement_node_id="node-002",
    )
    modifier.replace_node.return_value = mock_result
    return modifier


@pytest.fixture
def mock_task_terminator():
    """Mock TaskTerminator"""
    terminator = MagicMock()
    # 默认返回成功的终止结果（直接创建 TerminationResult 实例）
    mock_result = TerminationResult(
        success=True,
        session_id="test-session",
        notified_agents=["conversation", "workflow"],
        user_notified=True,
    )
    terminator.terminate.return_value = mock_result
    return terminator


@pytest.fixture
def coordinator(mock_workflow_modifier, mock_task_terminator):
    """创建 InterventionCoordinator 实例"""
    return InterventionCoordinator(
        workflow_modifier=mock_workflow_modifier,
        task_terminator=mock_task_terminator,
    )


# ==================== REPLACE 级别执行测试 ====================


def test_replace_level_calls_workflow_modifier(coordinator, mock_workflow_modifier):
    """REPLACE 级别应调用 WorkflowModifier.replace_node()"""
    context = {
        "session_id": "test-session",
        "workflow_id": "wf-001",
        "node_id": "node-001",
        "replacement_config": {"type": "new_node"},
        "reason": "Test replacement",
        "workflow_definition": {"nodes": []},
    }

    result = coordinator.handle_intervention(InterventionLevel.REPLACE, context)

    # 验证 WorkflowModifier.replace_node 被调用
    assert mock_workflow_modifier.replace_node.called
    call_args = mock_workflow_modifier.replace_node.call_args

    # 验证传入的参数
    workflow_def = call_args[0][0]
    request = call_args[0][1]
    assert workflow_def == {"nodes": []}
    assert isinstance(request, NodeReplacementRequest)
    assert request.workflow_id == "wf-001"
    assert request.original_node_id == "node-001"

    # 验证返回结果
    assert result.success is True
    assert result.action_taken == "node_replaced"
    assert "modification" in result.details
    # 验证 details 包含 ModificationResult 的关键信息
    assert result.details["modification"]["success"] is True


def test_replace_level_handles_failure(coordinator, mock_workflow_modifier):
    """REPLACE 级别应正确处理修改失败的情况"""
    # 模拟修改失败（直接创建失败的 ModificationResult）
    mock_result = ModificationResult(
        success=False,
        error="Node not found",
        original_node_id="node-001",
    )
    mock_workflow_modifier.replace_node.return_value = mock_result

    context = {
        "session_id": "test-session",
        "workflow_id": "wf-001",
        "node_id": "node-001",
        "workflow_definition": {"nodes": []},
    }

    result = coordinator.handle_intervention(InterventionLevel.REPLACE, context)

    # 验证返回失败结果
    assert result.success is False
    assert result.action_taken == "node_replaced"
    assert "modification" in result.details
    assert result.details["modification"]["success"] is False


def test_replace_level_with_minimal_context(coordinator, mock_workflow_modifier):
    """REPLACE 级别应处理最小化上下文参数"""
    context = {
        "session_id": "test-session",
        # 缺少其他必要参数，应使用默认值
    }

    result = coordinator.handle_intervention(InterventionLevel.REPLACE, context)

    # 验证仍然调用了 replace_node（使用默认值）
    assert mock_workflow_modifier.replace_node.called
    call_args = mock_workflow_modifier.replace_node.call_args
    request = call_args[0][1]
    assert request.workflow_id == ""
    assert request.original_node_id == ""
    assert request.reason == "Intervention triggered"


def test_replace_level_logs_intervention(coordinator, mock_workflow_modifier):
    """REPLACE 级别应记录日志"""
    context = {
        "session_id": "test-session",
        "workflow_id": "wf-001",
        "node_id": "node-001",
        "workflow_definition": {"nodes": []},
    }

    coordinator.handle_intervention(InterventionLevel.REPLACE, context)

    # 验证日志被记录
    logs = coordinator.intervention_logger.get_logs()
    assert len(logs) > 0
    last_log = logs[-1]
    assert last_log["level"] == InterventionLevel.REPLACE
    assert last_log["session_id"] == "test-session"


def test_replace_level_without_workflow_definition(coordinator, mock_workflow_modifier):
    """REPLACE 级别应处理缺少 workflow_definition 的情况"""
    context = {
        "session_id": "test-session",
        "workflow_id": "wf-001",
        "node_id": "node-001",
        # 缺少 workflow_definition
    }

    result = coordinator.handle_intervention(InterventionLevel.REPLACE, context)

    # 验证仍然调用了 replace_node（使用空字典）
    assert mock_workflow_modifier.replace_node.called
    call_args = mock_workflow_modifier.replace_node.call_args
    workflow_def = call_args[0][0]
    assert workflow_def == {}


# ==================== TERMINATE 级别执行测试 ====================


def test_terminate_level_calls_task_terminator(coordinator, mock_task_terminator):
    """TERMINATE 级别应调用 TaskTerminator.terminate()"""
    context = {
        "session_id": "test-session",
        "reason": "Test termination",
        "error_code": "TEST_ERROR",
        "notify_agents": ["conversation", "workflow"],
        "notify_user": True,
    }

    result = coordinator.handle_intervention(InterventionLevel.TERMINATE, context)

    # 验证 TaskTerminator.terminate 被调用
    assert mock_task_terminator.terminate.called
    call_args = mock_task_terminator.terminate.call_args

    # 验证传入的参数
    request = call_args[0][0]
    assert isinstance(request, TaskTerminationRequest)
    assert request.session_id == "test-session"
    assert request.reason == "Test termination"
    assert request.error_code == "TEST_ERROR"

    # 验证返回结果
    assert result.success is True
    assert result.action_taken == "task_terminated"
    assert "termination" in result.details
    # 验证 details 包含 TerminationResult 的关键信息
    assert result.details["termination"]["success"] is True
    assert result.details["termination"]["session_id"] == "test-session"


def test_terminate_level_handles_failure(coordinator, mock_task_terminator):
    """TERMINATE 级别应正确处理终止失败的情况"""
    # 模拟终止失败（直接创建失败的 TerminationResult）
    mock_result = TerminationResult(
        success=False,
        session_id="test-session",
    )
    mock_task_terminator.terminate.return_value = mock_result

    context = {
        "session_id": "test-session",
        "reason": "Test termination",
    }

    result = coordinator.handle_intervention(InterventionLevel.TERMINATE, context)

    # 验证返回失败结果
    assert result.success is False
    assert result.action_taken == "task_terminated"
    assert "termination" in result.details
    assert result.details["termination"]["success"] is False


def test_terminate_level_with_minimal_context(coordinator, mock_task_terminator):
    """TERMINATE 级别应处理最小化上下文参数"""
    context = {
        "session_id": "test-session",
        # 缺少其他参数，应使用默认值
    }

    result = coordinator.handle_intervention(InterventionLevel.TERMINATE, context)

    # 验证仍然调用了 terminate（使用默认值）
    assert mock_task_terminator.terminate.called
    call_args = mock_task_terminator.terminate.call_args
    request = call_args[0][0]
    assert request.session_id == "test-session"
    assert request.reason == "Intervention triggered"
    assert request.error_code == "INTERVENTION_TERMINATE"
    assert request.notify_agents == ["conversation", "workflow"]
    assert request.notify_user is True


def test_terminate_level_logs_intervention(coordinator, mock_task_terminator):
    """TERMINATE 级别应记录日志"""
    context = {
        "session_id": "test-session",
        "reason": "Test termination",
    }

    coordinator.handle_intervention(InterventionLevel.TERMINATE, context)

    # 验证日志被记录
    logs = coordinator.intervention_logger.get_logs()
    assert len(logs) > 0
    last_log = logs[-1]
    assert last_log["level"] == InterventionLevel.TERMINATE
    assert last_log["session_id"] == "test-session"


def test_terminate_level_default_notify_settings(coordinator, mock_task_terminator):
    """TERMINATE 级别应使用默认通知设置"""
    context = {
        "session_id": "test-session",
        # 不指定 notify_agents 和 notify_user
    }

    coordinator.handle_intervention(InterventionLevel.TERMINATE, context)

    call_args = mock_task_terminator.terminate.call_args
    request = call_args[0][0]
    # 验证默认值
    assert request.notify_agents == ["conversation", "workflow"]
    assert request.notify_user is True

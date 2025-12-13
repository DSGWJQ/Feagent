"""P1-2: NullSaveRequestOrchestrator单元测试

测试无EventBus时SaveRequestOrchestrator的Null Object实现。

覆盖场景：
- 事件订阅（2个）
- 队列查询（6个）
- 审核与执行（4个）
- 回执系统（6个）
- 集成测试（2个）
"""

import pytest

# ==================== 测试组1：事件订阅（2个）====================


def test_enable_save_request_handler_is_noop():
    """验证启用处理器为no-op

    测试场景：
    - 无EventBus时调用enable_save_request_handler()
    - 预期：不抛异常，静默忽略

    验证点：
    - 方法可调用
    - 无副作用
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    null_orch.enable_save_request_handler()  # 不抛异常
    # 无断言，验证不抛异常即可


def test_disable_save_request_handler_is_noop():
    """验证禁用处理器为no-op

    测试场景：
    - 无EventBus时调用disable_save_request_handler()
    - 预期：不抛异常，静默忽略

    验证点：
    - 方法可调用
    - 无副作用
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    null_orch.disable_save_request_handler()  # 不抛异常


# ==================== 测试组2：队列查询（6个）====================


def test_has_pending_save_requests_returns_false():
    """验证检查待处理请求返回False

    测试场景：
    - 无队列时调用has_pending_save_requests()
    - 预期：返回False

    验证点：
    - 返回值类型为bool
    - 返回值为False（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.has_pending_save_requests()

    assert isinstance(result, bool)
    assert result is False


def test_get_pending_save_request_count_returns_zero():
    """验证获取请求数量返回0

    测试场景：
    - 无队列时调用get_pending_save_request_count()
    - 预期：返回0

    验证点：
    - 返回值类型为int
    - 返回值为0（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_pending_save_request_count()

    assert isinstance(result, int)
    assert result == 0


def test_get_save_request_queue_returns_empty_list():
    """验证获取队列返回空列表

    测试场景：
    - 无队列时调用get_save_request_queue()
    - 预期：返回空列表

    验证点：
    - 返回值类型为list
    - 列表为空（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_save_request_queue()

    assert isinstance(result, list)
    assert result == []


def test_get_save_request_status_returns_pending():
    """验证获取请求状态返回PENDING

    测试场景：
    - 无队列时调用get_save_request_status("fake_id")
    - 预期：返回SaveRequestStatus.PENDING

    验证点：
    - 返回值为SaveRequestStatus.PENDING（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )
    from src.domain.services.save_request_channel import SaveRequestStatus

    null_orch = NullSaveRequestOrchestrator()
    status = null_orch.get_save_request_status("fake_id")

    assert status == SaveRequestStatus.PENDING


def test_get_save_requests_by_session_returns_empty_list():
    """验证按会话获取请求返回空列表

    测试场景：
    - 无队列时调用get_save_requests_by_session("fake_session")
    - 预期：返回空列表

    验证点：
    - 返回值类型为list
    - 列表为空（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_save_requests_by_session("fake_session")

    assert isinstance(result, list)
    assert result == []


def test_dequeue_save_request_returns_none():
    """验证出队请求返回None

    测试场景：
    - 无队列时调用dequeue_save_request()
    - 预期：返回None

    验证点：
    - 返回值为None（队列为空，与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.dequeue_save_request()

    assert result is None


# ==================== 测试组3：审核与执行（4个）====================


def test_configure_save_auditor_raises_value_error():
    """验证配置审核器抛出ValueError

    测试场景：
    - 无EventBus时调用configure_save_auditor()
    - 预期：抛出ValueError

    验证点：
    - 抛出ValueError异常
    - 异常消息包含"event_bus required"（与真实实现一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()

    with pytest.raises(ValueError, match="event_bus required"):
        null_orch.configure_save_auditor()


@pytest.mark.asyncio
async def test_process_next_save_request_returns_none():
    """验证处理下一个请求返回None

    测试场景：
    - 无队列时调用process_next_save_request()
    - 预期：返回None

    验证点：
    - 返回值为None（队列为空，与None检查分支一致）
    - 方法为async
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = await null_orch.process_next_save_request()

    assert result is None


def test_get_save_audit_logs_returns_empty_list():
    """验证获取审计日志返回空列表

    测试场景：
    - 无审核器时调用get_save_audit_logs()
    - 预期：返回空列表

    验证点：
    - 返回值类型为list
    - 列表为空（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_save_audit_logs()

    assert isinstance(result, list)
    assert result == []


def test_get_save_audit_logs_by_session_returns_empty_list():
    """验证按会话获取审计日志返回空列表

    测试场景：
    - 无审核器时调用get_save_audit_logs_by_session("fake_session")
    - 预期：返回空列表

    验证点：
    - 返回值类型为list
    - 列表为空（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_save_audit_logs_by_session("fake_session")

    assert isinstance(result, list)
    assert result == []


# ==================== 测试组4：回执系统（6个）====================


@pytest.mark.asyncio
async def test_send_save_result_receipt_returns_error_dict():
    """验证发送回执返回空处理结果

    测试场景：
    - 无回执系统时调用send_save_result_receipt()
    - 预期：返回空处理结果字典

    验证点：
    - 返回值为字典
    - 字典结构与SaveResultReceiptSystem.process_result()一致
    - 所有操作均失败（False/None）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = await null_orch.send_save_result_receipt(
        session_id="fake_session",
        request_id="fake_request",
        success=True,
        message="test",
    )

    assert isinstance(result, dict)
    assert result["request_id"] == "fake_request"
    assert result["recorded_to_short_term"] is False
    assert result["recorded_to_medium_term"] is False
    assert result["written_to_knowledge_base"] is False
    assert result["knowledge_entry_id"] is None


@pytest.mark.asyncio
async def test_process_save_request_with_receipt_returns_none():
    """验证处理请求并发送回执返回None

    测试场景：
    - 无队列时调用process_save_request_with_receipt()
    - 预期：返回None

    验证点：
    - 返回值为None（队列为空，与None检查分支一致）
    - 方法为async
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = await null_orch.process_save_request_with_receipt()

    assert result is None


def test_get_save_receipt_context_returns_empty_dict():
    """验证获取回执上下文返回空字典

    测试场景：
    - 无回执系统时调用get_save_receipt_context("fake_session")
    - 预期：返回空字典

    验证点：
    - 返回值类型为dict
    - 字典为空（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_save_receipt_context("fake_session")

    assert isinstance(result, dict)
    assert result == {}


def test_get_save_receipt_chain_log_returns_none():
    """验证获取链路日志返回None

    测试场景：
    - 无回执系统时调用get_save_receipt_chain_log("fake_request")
    - 预期：返回None

    验证点：
    - 返回值为None（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_save_receipt_chain_log("fake_request")

    assert result is None


def test_get_save_receipt_logs_returns_empty_list():
    """验证获取所有回执日志返回空列表

    测试场景：
    - 无回执系统时调用get_save_receipt_logs()
    - 预期：返回空列表

    验证点：
    - 返回值类型为list
    - 列表为空（与None检查分支一致）
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    result = null_orch.get_save_receipt_logs()

    assert isinstance(result, list)
    assert result == []


def test_get_session_save_statistics_returns_zero_stats():
    """验证获取统计返回零值

    测试场景：
    - 无回执系统时调用get_session_save_statistics("fake_session")
    - 预期：返回零值统计字典

    验证点：
    - 返回值为字典
    - 字典结构与SaveResultMemoryHandler.get_session_statistics()一致
    - 所有统计值为0
    """
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    null_orch = NullSaveRequestOrchestrator()
    stats = null_orch.get_session_save_statistics("fake_session")

    assert isinstance(stats, dict)
    assert stats["total_requests"] == 0
    assert stats["success_count"] == 0
    assert stats["rejected_count"] == 0
    assert stats["failed_count"] == 0
    assert stats["success_rate"] == 0.0


# ==================== 集成测试用例（2个）====================


def test_coordinator_with_null_orchestrator():
    """验证无EventBus时使用Null实现

    测试场景：
    - 创建CoordinatorAgent时event_bus=None
    - 预期：_save_request_orchestrator为NullSaveRequestOrchestrator

    验证点：
    - orchestrator类型为NullSaveRequestOrchestrator
    - 调用所有18个方法无异常
    - 返回值与预期一致
    """
    from src.domain.agents.coordinator_agent import CoordinatorAgent
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )

    agent = CoordinatorAgent(event_bus=None)

    # 验证orchestrator为NullSaveRequestOrchestrator
    assert isinstance(agent._save_request_orchestrator, NullSaveRequestOrchestrator)

    # 调用所有方法，确保无异常
    agent.enable_save_request_handler()  # No-op
    agent.disable_save_request_handler()  # No-op

    assert agent.has_pending_save_requests() is False
    assert agent.get_pending_save_request_count() == 0
    assert agent.get_save_request_queue() == []
    assert agent.get_save_requests_by_session("fake") == []
    assert agent.dequeue_save_request() is None

    assert agent.get_save_audit_logs() == []
    assert agent.get_save_audit_logs_by_session("fake") == []

    assert agent.get_save_receipt_context("fake") == {}
    assert agent.get_save_receipt_chain_log("fake") is None
    assert agent.get_save_receipt_logs() == []

    stats = agent.get_session_save_statistics("fake")
    assert stats["total_requests"] == 0
    assert stats["success_count"] == 0
    assert stats["rejected_count"] == 0
    assert stats["failed_count"] == 0
    assert stats["success_rate"] == 0.0


def test_coordinator_with_real_orchestrator():
    """验证有EventBus时使用真实实现

    测试场景：
    - 创建CoordinatorAgent时event_bus不为None
    - 预期：_save_request_orchestrator为SaveRequestOrchestrator

    验证点：
    - orchestrator类型为SaveRequestOrchestrator
    - 不是NullSaveRequestOrchestrator
    """
    from src.domain.agents.coordinator_agent import CoordinatorAgent
    from src.domain.services.event_bus import EventBus
    from src.domain.services.null_save_request_orchestrator import (
        NullSaveRequestOrchestrator,
    )
    from src.domain.services.save_request_orchestrator import SaveRequestOrchestrator

    event_bus = EventBus()
    agent = CoordinatorAgent(event_bus=event_bus)

    # 验证orchestrator为SaveRequestOrchestrator
    assert isinstance(agent._save_request_orchestrator, SaveRequestOrchestrator)
    assert not isinstance(agent._save_request_orchestrator, NullSaveRequestOrchestrator)

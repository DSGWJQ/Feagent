"""SaveRequestOrchestrator 单元测试

测试覆盖：
- 初始化与依赖验证
- 事件订阅/取消订阅
- 队列操作（入队、出队、状态查询、会话过滤）
- 审核流程（通过/拒绝路径）
- 执行流程（成功/失败路径）
- 回执生成与事件发布
- 审计日志查询
- 边缘情况（空队列、缺失审核器、重复订阅等）

总测试数：33
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.save_request_audit import AuditResult, AuditStatus, ExecutionResult
from src.domain.services.save_request_channel import (
    SaveRequest,
    SaveRequestPriority,
    SaveRequestStatus,
)
from src.domain.services.save_request_orchestrator import SaveRequestOrchestrator
from src.domain.services.save_request_receipt import SaveRequestResultEvent, SaveResultStatus

# ==================== Fixtures ====================


@pytest.fixture
def event_bus():
    """Mock EventBus with all required methods."""
    bus = MagicMock()
    bus.subscribe = MagicMock()
    bus.publish = AsyncMock()
    bus.unsubscribe = MagicMock()
    return bus


@pytest.fixture
def knowledge_manager():
    """Mock KnowledgeManager."""
    manager = MagicMock()
    manager.create = MagicMock(return_value="kb-1")
    return manager


@pytest.fixture
def orchestrator(event_bus, knowledge_manager):
    """Create orchestrator with mocked dependencies."""
    return SaveRequestOrchestrator(
        event_bus=event_bus,
        knowledge_manager=knowledge_manager,
        log_collector=MagicMock(),
    )


@pytest.fixture
def save_request():
    """Create a basic SaveRequest fixture."""
    return SaveRequest(
        target_path="/tmp/file.txt",
        content="hello",
        session_id="session-1",
    )


# ==================== Initialization Tests ====================


def test_init_requires_event_bus(knowledge_manager):
    """测试初始化时必须提供 event_bus"""
    with pytest.raises(ValueError, match="event_bus is required"):
        SaveRequestOrchestrator(event_bus=None, knowledge_manager=knowledge_manager)


def test_init_sets_dependencies(event_bus, knowledge_manager):
    """测试初始化正确设置依赖"""
    orchestrator = SaveRequestOrchestrator(
        event_bus=event_bus,
        knowledge_manager=knowledge_manager,
        log_collector="collector",
    )

    assert orchestrator.event_bus is event_bus
    assert orchestrator.knowledge_manager is knowledge_manager
    assert orchestrator.log_collector == "collector"


# ==================== Event Subscription Tests ====================


def test_enable_save_request_handler_subscribes_once(orchestrator, event_bus):
    """测试启用处理器订阅事件"""
    orchestrator.enable_save_request_handler()

    event_bus.subscribe.assert_called_once()
    subscribed_type, handler = event_bus.subscribe.call_args[0]
    assert handler == orchestrator._handle_save_request
    assert subscribed_type.__name__ == "SaveRequest"
    assert orchestrator._is_listening_save_requests is True


def test_enable_save_request_handler_idempotent(orchestrator, event_bus):
    """测试重复启用处理器是幂等的"""
    orchestrator.enable_save_request_handler()
    orchestrator.enable_save_request_handler()

    event_bus.subscribe.assert_called_once()
    assert orchestrator._is_listening_save_requests is True


def test_disable_save_request_handler_toggles_flag(orchestrator):
    """测试禁用处理器切换标志"""
    orchestrator.enable_save_request_handler()
    orchestrator.disable_save_request_handler()

    assert orchestrator._save_request_handler_enabled is False


def test_disable_save_request_handler_unsubscribes(orchestrator, event_bus):
    """测试禁用处理器时会取消订阅"""
    orchestrator.enable_save_request_handler()
    orchestrator.disable_save_request_handler()

    event_bus.unsubscribe.assert_called_once()


# ==================== Event Handler Tests ====================


@pytest.mark.asyncio
async def test_handle_save_request_enqueue_and_publish_received_event(
    orchestrator, event_bus, save_request
):
    """测试处理SaveRequest事件入队并发布确认事件"""
    orchestrator.enable_save_request_handler()

    await orchestrator._handle_save_request(save_request)

    assert orchestrator.get_pending_save_request_count() == 1
    event_bus.publish.assert_awaited_once()
    published_event = event_bus.publish.call_args[0][0]
    assert published_event.request_id == save_request.request_id
    assert published_event.queue_position == 1


@pytest.mark.asyncio
async def test_handle_save_request_ignores_invalid_event(orchestrator, event_bus):
    """测试处理器忽略非SaveRequest事件"""
    await orchestrator._handle_save_request(object())

    assert orchestrator.get_pending_save_request_count() == 0
    event_bus.publish.assert_not_awaited()


# ==================== Queue Query Tests ====================


@pytest.mark.asyncio
async def test_has_pending_save_requests(orchestrator, save_request):
    """测试检查是否有待处理请求"""
    assert orchestrator.has_pending_save_requests() is False

    await orchestrator._handle_save_request(save_request)

    assert orchestrator.has_pending_save_requests() is True


@pytest.mark.asyncio
async def test_get_pending_save_request_count(orchestrator, save_request):
    """测试获取待处理请求数量"""
    await orchestrator._handle_save_request(save_request)
    await orchestrator._handle_save_request(
        SaveRequest(target_path="/tmp/other.txt", content="more", session_id="session-2")
    )

    assert orchestrator.get_pending_save_request_count() == 2


@pytest.mark.asyncio
async def test_get_save_request_queue_sorted_by_priority(orchestrator):
    """测试队列按优先级排序"""
    low = SaveRequest(
        target_path="/tmp/low.txt",
        content="l",
        session_id="session-1",
        priority=SaveRequestPriority.LOW,
    )
    critical = SaveRequest(
        target_path="/tmp/critical.txt",
        content="c",
        session_id="session-1",
        priority=SaveRequestPriority.CRITICAL,
    )
    normal = SaveRequest(
        target_path="/tmp/normal.txt",
        content="n",
        session_id="session-1",
        priority=SaveRequestPriority.NORMAL,
    )

    await orchestrator._handle_save_request(low)
    await orchestrator._handle_save_request(critical)
    await orchestrator._handle_save_request(normal)

    queue = orchestrator.get_save_request_queue()
    assert queue[0].request_id == critical.request_id
    assert queue[1].request_id == normal.request_id
    assert queue[2].request_id == low.request_id


@pytest.mark.asyncio
async def test_get_save_requests_by_session_filters(orchestrator):
    """测试按会话ID过滤请求"""
    target_session = SaveRequest(target_path="/tmp/a.txt", content="a", session_id="session-a")
    other_session = SaveRequest(target_path="/tmp/b.txt", content="b", session_id="session-b")

    await orchestrator._handle_save_request(target_session)
    await orchestrator._handle_save_request(other_session)

    filtered = orchestrator.get_save_requests_by_session("session-a")
    assert len(filtered) == 1
    assert filtered[0].request_id == target_session.request_id


def test_get_save_request_status_defaults_pending_when_missing(orchestrator):
    """测试缺失状态时默认返回PENDING"""
    assert orchestrator.get_save_request_status("missing") == SaveRequestStatus.PENDING


@pytest.mark.asyncio
async def test_dequeue_save_request_returns_highest_priority(orchestrator):
    """测试出队返回最高优先级请求"""
    critical = SaveRequest(
        target_path="/tmp/critical.txt",
        content="c",
        session_id="s1",
        priority=SaveRequestPriority.CRITICAL,
    )
    low = SaveRequest(
        target_path="/tmp/low.txt",
        content="l",
        session_id="s1",
        priority=SaveRequestPriority.LOW,
    )

    await orchestrator._handle_save_request(low)
    await orchestrator._handle_save_request(critical)

    dequeued = orchestrator.dequeue_save_request()
    assert dequeued.request_id == critical.request_id
    assert orchestrator.get_pending_save_request_count() == 1


# ==================== Auditor Configuration Tests ====================


def test_configure_save_auditor_sets_components(orchestrator):
    """测试配置审核器设置组件"""
    orchestrator.configure_save_auditor(enable_rate_limit=False)

    assert orchestrator._save_auditor is not None
    assert orchestrator._save_executor is not None
    assert orchestrator._save_audit_logger is not None
    assert any(rule.rule_id == "content_size" for rule in orchestrator._save_auditor.rules)


# ==================== Processing Tests ====================


@pytest.mark.asyncio
async def test_process_next_save_request_returns_none_when_queue_empty(orchestrator, event_bus):
    """测试空队列时返回None"""
    result = await orchestrator.process_next_save_request()

    assert result is None
    event_bus.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_next_save_request_auto_configures_when_missing(orchestrator, save_request):
    """测试缺失审核器时自动配置"""
    orchestrator._save_auditor = None

    # Mock configure_save_auditor to set up the auditor after being called
    def mock_configure():
        orchestrator._save_auditor = MagicMock(
            audit=MagicMock(
                return_value=AuditResult(
                    request_id=save_request.request_id,
                    status=AuditStatus.APPROVED,
                )
            )
        )
        orchestrator._save_executor = MagicMock(
            execute=MagicMock(
                return_value=ExecutionResult(
                    request_id=save_request.request_id,
                    success=True,
                    bytes_written=5,
                )
            )
        )
        orchestrator._save_audit_logger = MagicMock()

    orchestrator.configure_save_auditor = MagicMock(side_effect=mock_configure)
    orchestrator.event_bus = AsyncMock()

    # 直接入队，避免事件发布干扰
    orchestrator._save_request_queue.enqueue(save_request)

    await orchestrator.process_next_save_request()

    orchestrator.configure_save_auditor.assert_called_once()


@pytest.mark.asyncio
async def test_process_next_save_request_rejected_path(orchestrator, save_request):
    """测试审核拒绝路径"""
    # Mock 事件总线避免发布干扰
    orchestrator.event_bus = AsyncMock()

    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.REJECTED,
                reason="blocked",
            )
        )
    )
    orchestrator._save_executor = MagicMock()
    orchestrator._save_audit_logger = MagicMock()

    # 直接入队
    orchestrator._save_request_queue.enqueue(save_request)

    result = await orchestrator.process_next_save_request()

    assert result.success is False
    assert result.audit_status == AuditStatus.REJECTED
    orchestrator.event_bus.publish.assert_awaited_once()
    published = orchestrator.event_bus.publish.call_args[0][0]
    assert published.success is False
    assert published.audit_status == AuditStatus.REJECTED.value


@pytest.mark.asyncio
async def test_process_next_save_request_execution_success(orchestrator, save_request):
    """测试执行成功路径"""
    orchestrator.event_bus = AsyncMock()

    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.APPROVED,
                reason="ok",
            )
        )
    )
    orchestrator._save_executor = MagicMock(
        execute=MagicMock(
            return_value=ExecutionResult(
                request_id=save_request.request_id,
                success=True,
                bytes_written=5,
            )
        )
    )
    orchestrator._save_audit_logger = MagicMock()
    orchestrator._save_request_queue.enqueue(save_request)

    result = await orchestrator.process_next_save_request()

    assert result.success is True
    assert result.bytes_written == 5
    orchestrator.event_bus.publish.assert_awaited_once()
    published = orchestrator.event_bus.publish.call_args[0][0]
    assert published.success is True
    assert published.bytes_written == 5


@pytest.mark.asyncio
async def test_process_next_save_request_execution_failure(orchestrator, save_request):
    """测试执行失败路径"""
    orchestrator.event_bus = AsyncMock()

    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.APPROVED,
            )
        )
    )
    orchestrator._save_executor = MagicMock(
        execute=MagicMock(
            return_value=ExecutionResult(
                request_id=save_request.request_id,
                success=False,
                error_message="disk full",
            )
        )
    )
    orchestrator._save_audit_logger = MagicMock()
    orchestrator._save_request_queue.enqueue(save_request)

    result = await orchestrator.process_next_save_request()

    assert result.success is False
    assert result.error_message == "disk full"
    orchestrator.event_bus.publish.assert_awaited_once()
    assert orchestrator.event_bus.publish.call_args[0][0].success is False


@pytest.mark.asyncio
async def test_process_updates_queue_status_on_success(orchestrator, save_request):
    """处理成功后更新队列状态为 COMPLETED"""
    orchestrator.event_bus = AsyncMock()

    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.APPROVED,
            )
        )
    )
    orchestrator._save_executor = MagicMock(
        execute=MagicMock(
            return_value=ExecutionResult(
                request_id=save_request.request_id,
                success=True,
                bytes_written=10,
            )
        )
    )
    orchestrator._save_audit_logger = MagicMock()
    orchestrator._save_request_queue.enqueue(save_request)

    await orchestrator.process_next_save_request()

    status = orchestrator._save_request_queue.get_status(save_request.request_id)
    assert status == SaveRequestStatus.COMPLETED


@pytest.mark.asyncio
async def test_process_updates_queue_status_on_failure(orchestrator, save_request):
    """执行失败后更新队列状态为 FAILED"""
    orchestrator.event_bus = AsyncMock()

    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.APPROVED,
            )
        )
    )
    orchestrator._save_executor = MagicMock(
        execute=MagicMock(
            return_value=ExecutionResult(
                request_id=save_request.request_id,
                success=False,
                error_message="boom",
            )
        )
    )
    orchestrator._save_audit_logger = MagicMock()
    orchestrator._save_request_queue.enqueue(save_request)

    await orchestrator.process_next_save_request()

    status = orchestrator._save_request_queue.get_status(save_request.request_id)
    assert status == SaveRequestStatus.FAILED


# ==================== Audit Logs Tests ====================


def test_get_save_audit_logs_empty_when_not_configured(orchestrator):
    """测试未配置时返回空列表"""
    orchestrator._save_audit_logger = None

    assert orchestrator.get_save_audit_logs() == []


def test_get_save_audit_logs_by_session_filters(orchestrator):
    """测试按会话过滤审计日志"""
    orchestrator._save_audit_logger = MagicMock(
        get_logs_by_session=MagicMock(return_value=[{"session_id": "session-1"}])
    )

    logs = orchestrator.get_save_audit_logs_by_session("session-1")

    assert logs == [{"session_id": "session-1"}]


# ==================== Receipt System Tests ====================


@pytest.mark.asyncio
async def test_send_save_result_receipt_success_path(orchestrator, event_bus):
    """测试发送成功回执"""
    orchestrator.save_receipt_system = MagicMock(
        process_result=MagicMock(return_value={"ok": True, "written_to_knowledge_base": True}),
        receipt_logger=MagicMock(),
    )

    result = await orchestrator.send_save_result_receipt(
        session_id="s-1",
        request_id="req-1",
        success=True,
        message="done",
    )

    assert result == {"ok": True, "written_to_knowledge_base": True}
    orchestrator.save_receipt_system.receipt_logger.log_request_received.assert_called_once()
    orchestrator.save_receipt_system.receipt_logger.log_audit_completed.assert_called_once()
    event_bus.publish.assert_awaited_once()
    published_event = event_bus.publish.call_args[0][0]
    assert isinstance(published_event, SaveRequestResultEvent)
    assert published_event.result.status == SaveResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_send_save_result_receipt_rejected_sets_status(orchestrator, event_bus):
    """测试拒绝回执设置REJECTED状态"""
    orchestrator.save_receipt_system = MagicMock(
        process_result=MagicMock(return_value={"ok": True, "written_to_knowledge_base": False}),
        receipt_logger=MagicMock(),
    )

    await orchestrator.send_save_result_receipt(
        session_id="s-1",
        request_id="req-1",
        success=False,
        message="rule violation",
        violation_severity="high",
    )

    published_event = event_bus.publish.call_args[0][0]
    assert published_event.result.status == SaveResultStatus.REJECTED


@pytest.mark.asyncio
async def test_send_save_result_receipt_failure_sets_status_failed(orchestrator, event_bus):
    """测试失败回执设置FAILED状态"""
    orchestrator.save_receipt_system = MagicMock(
        process_result=MagicMock(return_value={"ok": True, "written_to_knowledge_base": False}),
        receipt_logger=MagicMock(),
    )

    await orchestrator.send_save_result_receipt(
        session_id="s-1",
        request_id="req-1",
        success=False,
        message="io failed",
    )

    published_event = event_bus.publish.call_args[0][0]
    assert published_event.result.status == SaveResultStatus.FAILED


def test_receipt_logger_unified(orchestrator):
    """测试回执日志记录器统一"""
    logger_from_system = orchestrator.save_receipt_system.receipt_logger
    logs = orchestrator.get_save_receipt_logs()

    # 验证使用统一日志记录器
    assert logs == logger_from_system.get_all_logs()


# ==================== Full Flow with Receipt Tests ====================


@pytest.mark.asyncio
async def test_process_save_request_with_receipt_returns_none_when_queue_empty(orchestrator):
    """测试空队列时返回None"""
    assert await orchestrator.process_save_request_with_receipt() is None


@pytest.mark.asyncio
async def test_process_save_request_with_receipt_rejected_flow(
    orchestrator, event_bus, save_request
):
    """测试带回执的拒绝流程"""
    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.REJECTED,
                reason="dangerous path",
                rule_id="blacklist_rule",
            )
        )
    )
    orchestrator._save_executor = MagicMock()
    orchestrator._save_audit_logger = MagicMock()
    orchestrator.save_receipt_system = MagicMock(
        process_result=MagicMock(return_value={"ok": True, "written_to_knowledge_base": False}),
        receipt_logger=MagicMock(),
    )
    orchestrator._save_request_queue.enqueue(save_request)

    result = await orchestrator.process_save_request_with_receipt()

    assert result == {"ok": True, "written_to_knowledge_base": False}
    event_bus.publish.assert_awaited_once()
    published_event = event_bus.publish.call_args[0][0]
    assert published_event.result.status == SaveResultStatus.REJECTED
    assert published_event.session_id == save_request.session_id


@pytest.mark.asyncio
async def test_process_save_request_with_receipt_execution_success(
    orchestrator, event_bus, save_request
):
    """测试带回执的执行成功流程"""
    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.APPROVED,
                reason="ok",
            )
        )
    )
    orchestrator._save_executor = MagicMock(
        execute=MagicMock(
            return_value=ExecutionResult(
                request_id=save_request.request_id,
                success=True,
                bytes_written=10,
            )
        )
    )
    orchestrator._save_audit_logger = MagicMock()
    orchestrator.save_receipt_system = MagicMock(
        process_result=MagicMock(return_value={"ok": True, "written_to_knowledge_base": True}),
        receipt_logger=MagicMock(),
    )
    orchestrator._save_request_queue.enqueue(save_request)

    await orchestrator.process_save_request_with_receipt()

    event_bus.publish.assert_awaited_once()
    published_event = event_bus.publish.call_args[0][0]
    assert published_event.result.status == SaveResultStatus.SUCCESS
    assert any(trail.get("step") == "executed" for trail in published_event.result.audit_trail)


@pytest.mark.asyncio
async def test_process_save_request_with_receipt_execution_failure(
    orchestrator, event_bus, save_request
):
    """测试带回执的执行失败流程"""
    orchestrator._save_auditor = MagicMock(
        audit=MagicMock(
            return_value=AuditResult(
                request_id=save_request.request_id,
                status=AuditStatus.APPROVED,
            )
        )
    )
    orchestrator._save_executor = MagicMock(
        execute=MagicMock(
            return_value=ExecutionResult(
                request_id=save_request.request_id,
                success=False,
                error_message="io error",
            )
        )
    )
    orchestrator._save_audit_logger = MagicMock()
    orchestrator.save_receipt_system = MagicMock(
        process_result=MagicMock(return_value={"ok": True, "written_to_knowledge_base": False}),
        receipt_logger=MagicMock(),
    )
    orchestrator._save_request_queue.enqueue(save_request)

    await orchestrator.process_save_request_with_receipt()

    published_event = event_bus.publish.call_args[0][0]
    assert published_event.result.status == SaveResultStatus.FAILED


# ==================== Context Query Tests ====================


def test_get_save_receipt_context_delegates(orchestrator):
    """测试获取回执上下文委托"""
    orchestrator.save_receipt_system = MagicMock(
        generate_context_for_agent=MagicMock(return_value={"ctx": True})
    )

    assert orchestrator.get_save_receipt_context("s-1") == {"ctx": True}


def test_get_session_save_statistics_delegates(orchestrator):
    """测试获取会话统计委托"""
    mock_memory_handler = MagicMock(
        get_session_statistics=MagicMock(return_value={"total_requests": 2})
    )
    orchestrator.save_receipt_system = MagicMock()
    orchestrator.save_receipt_system.memory_handler = mock_memory_handler

    assert orchestrator.get_session_save_statistics("s-1") == {"total_requests": 2}

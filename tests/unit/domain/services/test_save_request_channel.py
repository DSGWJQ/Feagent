"""保存请求通道测试 (Save Request Channel Tests)

TDD 测试用例，验证：
1. SaveRequest 事件数据结构
2. SaveRequestType 操作类型枚举
3. SaveRequestPriority 优先级枚举
4. ConversationAgent 发送 SaveRequest 而非直接写文件
5. Coordinator 接收并排队 SaveRequest

测试日期：2025-12-07
"""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

# =============================================================================
# 测试辅助类：简化的同步事件总线（仅用于测试）
# =============================================================================


class SyncEventBus:
    """同步事件总线（测试用）

    简化版事件总线，支持同步发布和订阅。
    """

    def __init__(self):
        self._subscribers: dict[type, list] = {}
        self._event_log: list = []

    def subscribe(self, event_type: type, handler) -> None:
        """订阅事件类型"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        """同步发布事件"""
        self._event_log.append(event)
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            handler(event)

    @property
    def event_log(self) -> list:
        return self._event_log


# =============================================================================
# 测试辅助函数
# =============================================================================


def create_test_global_context():
    """创建测试用全局上下文"""
    from src.domain.services.context_manager import GlobalContext

    return GlobalContext(
        user_id="test-user",
        user_preferences={"language": "zh-CN"},
        system_config={"max_tokens": 4096},
    )


def create_test_session_context(session_id: str = "test-session"):
    """创建测试用会话上下文"""
    from src.domain.services.context_manager import SessionContext

    global_context = create_test_global_context()
    return SessionContext(session_id=session_id, global_context=global_context)


# =============================================================================
# 第一部分：SaveRequest 数据结构测试
# =============================================================================


class TestSaveRequestTypeEnum:
    """SaveRequestType 枚举测试"""

    def test_file_write_type_exists(self):
        """测试：FILE_WRITE 类型存在"""
        from src.domain.services.save_request_channel import SaveRequestType

        assert SaveRequestType.FILE_WRITE == "file_write"

    def test_file_append_type_exists(self):
        """测试：FILE_APPEND 类型存在"""
        from src.domain.services.save_request_channel import SaveRequestType

        assert SaveRequestType.FILE_APPEND == "file_append"

    def test_file_delete_type_exists(self):
        """测试：FILE_DELETE 类型存在"""
        from src.domain.services.save_request_channel import SaveRequestType

        assert SaveRequestType.FILE_DELETE == "file_delete"

    def test_config_update_type_exists(self):
        """测试：CONFIG_UPDATE 类型存在"""
        from src.domain.services.save_request_channel import SaveRequestType

        assert SaveRequestType.CONFIG_UPDATE == "config_update"


class TestSaveRequestPriorityEnum:
    """SaveRequestPriority 枚举测试"""

    def test_low_priority_exists(self):
        """测试：LOW 优先级存在"""
        from src.domain.services.save_request_channel import SaveRequestPriority

        assert SaveRequestPriority.LOW == "low"

    def test_normal_priority_exists(self):
        """测试：NORMAL 优先级存在"""
        from src.domain.services.save_request_channel import SaveRequestPriority

        assert SaveRequestPriority.NORMAL == "normal"

    def test_high_priority_exists(self):
        """测试：HIGH 优先级存在"""
        from src.domain.services.save_request_channel import SaveRequestPriority

        assert SaveRequestPriority.HIGH == "high"

    def test_critical_priority_exists(self):
        """测试：CRITICAL 优先级存在"""
        from src.domain.services.save_request_channel import SaveRequestPriority

        assert SaveRequestPriority.CRITICAL == "critical"

    def test_priority_ordering(self):
        """测试：优先级可排序（CRITICAL > HIGH > NORMAL > LOW）"""
        from src.domain.services.save_request_channel import SaveRequestPriority

        priorities = [
            SaveRequestPriority.LOW,
            SaveRequestPriority.NORMAL,
            SaveRequestPriority.HIGH,
            SaveRequestPriority.CRITICAL,
        ]
        # 验证枚举值可用于比较
        assert SaveRequestPriority.get_priority_order(
            SaveRequestPriority.CRITICAL
        ) > SaveRequestPriority.get_priority_order(SaveRequestPriority.HIGH)
        assert SaveRequestPriority.get_priority_order(
            SaveRequestPriority.HIGH
        ) > SaveRequestPriority.get_priority_order(SaveRequestPriority.NORMAL)
        assert SaveRequestPriority.get_priority_order(
            SaveRequestPriority.NORMAL
        ) > SaveRequestPriority.get_priority_order(SaveRequestPriority.LOW)


class TestSaveRequestEvent:
    """SaveRequest 事件测试"""

    def test_create_save_request_with_required_fields(self):
        """测试：创建 SaveRequest 需要必填字段"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="Hello, World!",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="User requested to save file",
        )

        assert request.target_path == "/tmp/test.txt"
        assert request.content == "Hello, World!"
        assert request.operation_type == SaveRequestType.FILE_WRITE
        assert request.session_id == "session-001"
        assert request.reason == "User requested to save file"

    def test_save_request_has_auto_generated_id(self):
        """测试：SaveRequest 自动生成唯一 ID"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        request1 = SaveRequest(
            target_path="/tmp/test1.txt",
            content="content1",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )
        request2 = SaveRequest(
            target_path="/tmp/test2.txt",
            content="content2",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        assert request1.request_id is not None
        assert request2.request_id is not None
        assert request1.request_id != request2.request_id

    def test_save_request_has_timestamp(self):
        """测试：SaveRequest 包含时间戳"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        before = datetime.now()
        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )
        after = datetime.now()

        assert request.timestamp is not None
        assert before <= request.timestamp <= after

    def test_save_request_default_priority_is_normal(self):
        """测试：SaveRequest 默认优先级为 NORMAL"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
            SaveRequestType,
        )

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        assert request.priority == SaveRequestPriority.NORMAL

    def test_save_request_with_custom_priority(self):
        """测试：SaveRequest 可设置自定义优先级"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
            SaveRequestType,
        )

        request = SaveRequest(
            target_path="/tmp/critical.txt",
            content="important data",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="Critical save",
            priority=SaveRequestPriority.CRITICAL,
        )

        assert request.priority == SaveRequestPriority.CRITICAL

    def test_save_request_to_dict(self):
        """测试：SaveRequest 可序列化为字典"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
            SaveRequestType,
        )

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
            priority=SaveRequestPriority.HIGH,
        )

        data = request.to_dict()

        assert data["target_path"] == "/tmp/test.txt"
        assert data["content"] == "content"
        assert data["operation_type"] == "file_write"
        assert data["session_id"] == "session-001"
        assert data["reason"] == "test"
        assert data["priority"] == "high"
        assert "request_id" in data
        assert "timestamp" in data

    def test_save_request_from_dict(self):
        """测试：SaveRequest 可从字典反序列化"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
            SaveRequestType,
        )

        data = {
            "request_id": "req-12345",
            "target_path": "/tmp/test.txt",
            "content": "content",
            "operation_type": "file_write",
            "session_id": "session-001",
            "reason": "test",
            "priority": "high",
            "timestamp": "2025-12-07T10:00:00",
        }

        request = SaveRequest.from_dict(data)

        assert request.request_id == "req-12345"
        assert request.target_path == "/tmp/test.txt"
        assert request.operation_type == SaveRequestType.FILE_WRITE
        assert request.priority == SaveRequestPriority.HIGH

    def test_save_request_is_event_subclass(self):
        """测试：SaveRequest 是 Event 的子类"""
        from src.domain.services.event_bus import Event
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        assert isinstance(request, Event)

    def test_save_request_event_type(self):
        """测试：SaveRequest 的 event_type 为 'save_request'"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        assert request.event_type == "save_request"


class TestSaveRequestValidation:
    """SaveRequest 验证测试"""

    def test_empty_path_raises_error(self):
        """测试：空路径抛出错误"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
            SaveRequestValidationError,
        )

        with pytest.raises(SaveRequestValidationError, match="target_path"):
            SaveRequest(
                target_path="",
                content="content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
            )

    def test_empty_session_id_raises_error(self):
        """测试：空 session_id 抛出错误"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
            SaveRequestValidationError,
        )

        with pytest.raises(SaveRequestValidationError, match="session_id"):
            SaveRequest(
                target_path="/tmp/test.txt",
                content="content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="",
                reason="test",
            )

    def test_delete_operation_allows_empty_content(self):
        """测试：DELETE 操作允许空内容"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="",
            operation_type=SaveRequestType.FILE_DELETE,
            session_id="session-001",
            reason="Delete file",
        )

        assert request.content == ""

    def test_write_operation_with_empty_content_raises_warning(self):
        """测试：WRITE 操作空内容会记录警告但不抛错"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        # 空内容的写操作应该成功但标记警告
        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="Write empty file",
        )

        assert request.has_warning is True
        assert "empty content" in request.warnings[0].lower()


# =============================================================================
# 第二部分：ConversationAgent 保存请求能力测试
# =============================================================================


class TestConversationAgentSaveRequestGeneration:
    """ConversationAgent 生成保存请求测试"""

    def test_detect_save_intent_from_user_input(self):
        """测试：从用户输入检测保存意图"""
        from src.domain.services.save_request_channel import SaveIntentDetector

        detector = SaveIntentDetector()

        # 明确的保存请求
        result = detector.detect("请帮我把这段代码保存到 /tmp/code.py")
        assert result.has_save_intent is True
        assert result.suggested_path == "/tmp/code.py"

        # 无保存意图
        result = detector.detect("请帮我解释这段代码")
        assert result.has_save_intent is False

    def test_detect_save_intent_with_various_expressions(self):
        """测试：检测多种保存表达方式"""
        from src.domain.services.save_request_channel import SaveIntentDetector

        detector = SaveIntentDetector()

        save_expressions = [
            "保存到文件",
            "写入文件",
            "存储到",
            "save to",
            "write to file",
            "导出到",
            "输出到文件",
        ]

        for expr in save_expressions:
            result = detector.detect(f"请{expr} /tmp/test.txt")
            assert result.has_save_intent is True, f"Should detect: {expr}"

    def test_conversation_agent_generates_save_request_instead_of_writing(self):
        """测试：ConversationAgent 生成 SaveRequest 而非直接写文件"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.save_request_channel import SaveRequest

        # 创建 mock LLM
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content='{"action": "save_file", "path": "/tmp/result.txt", "content": "Hello"}'
        )

        # 创建同步事件总线并记录发布的事件
        event_bus = SyncEventBus()
        published_events = []
        event_bus.subscribe(SaveRequest, lambda e: published_events.append(e))

        # 创建会话上下文
        session_context = create_test_session_context("test-session")

        # 创建 ConversationAgent
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )

        # 启用保存请求模式
        agent.enable_save_request_channel()

        # 模拟需要保存的场景
        agent.request_save(
            target_path="/tmp/result.txt",
            content="Hello, World!",
            reason="User requested save",
        )

        # 验证发布了 SaveRequest 事件
        assert len(published_events) == 1
        assert isinstance(published_events[0], SaveRequest)
        assert published_events[0].target_path == "/tmp/result.txt"
        assert published_events[0].content == "Hello, World!"
        assert published_events[0].session_id == "test-session"

    def test_conversation_agent_does_not_write_file_directly(self):
        """测试：ConversationAgent 不直接写入文件"""
        import os
        import tempfile

        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        event_bus = SyncEventBus()
        session_context = create_test_session_context("test-session")

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        agent.enable_save_request_channel()

        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "should_not_exist.txt")

            # 请求保存
            agent.request_save(
                target_path=target_path,
                content="This should not be written directly",
                reason="Test",
            )

            # 验证文件没有被直接创建
            assert not os.path.exists(
                target_path
            ), "ConversationAgent should NOT write file directly"

    def test_save_request_includes_source_agent_info(self):
        """测试：SaveRequest 包含来源 Agent 信息"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.save_request_channel import SaveRequest

        mock_llm = MagicMock()
        event_bus = SyncEventBus()
        published_events = []
        event_bus.subscribe(SaveRequest, lambda e: published_events.append(e))
        session_context = create_test_session_context("test-session")

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        agent.enable_save_request_channel()

        agent.request_save(
            target_path="/tmp/test.txt",
            content="content",
            reason="test",
        )

        assert len(published_events) == 1
        request = published_events[0]
        assert request.source_agent == "ConversationAgent"
        assert request.session_id == "test-session"


# =============================================================================
# 第三部分：Coordinator 保存请求处理测试
# =============================================================================


class TestCoordinatorSaveRequestQueue:
    """Coordinator 保存请求队列测试"""

    def test_coordinator_receives_save_request(self):
        """测试：Coordinator 接收 SaveRequest"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 启用保存请求处理
        coordinator.enable_save_request_handler()

        # 发布 SaveRequest
        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )
        event_bus.publish(request)

        # 验证 Coordinator 收到请求
        assert coordinator.has_pending_save_requests()
        assert coordinator.get_pending_save_request_count() == 1

    def test_coordinator_queues_save_requests_by_priority(self):
        """测试：Coordinator 按优先级排队 SaveRequest"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        # 发布不同优先级的请求
        low_request = SaveRequest(
            target_path="/tmp/low.txt",
            content="low priority",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="low",
            priority=SaveRequestPriority.LOW,
        )
        critical_request = SaveRequest(
            target_path="/tmp/critical.txt",
            content="critical priority",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="critical",
            priority=SaveRequestPriority.CRITICAL,
        )
        normal_request = SaveRequest(
            target_path="/tmp/normal.txt",
            content="normal priority",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="normal",
            priority=SaveRequestPriority.NORMAL,
        )

        # 按顺序发布：low -> critical -> normal
        event_bus.publish(low_request)
        event_bus.publish(critical_request)
        event_bus.publish(normal_request)

        # 获取队列顺序应为：critical -> normal -> low
        queue = coordinator.get_save_request_queue()
        assert queue[0].priority == SaveRequestPriority.CRITICAL
        assert queue[1].priority == SaveRequestPriority.NORMAL
        assert queue[2].priority == SaveRequestPriority.LOW

    def test_coordinator_tracks_save_request_status(self):
        """测试：Coordinator 跟踪 SaveRequest 状态"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestStatus,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )
        event_bus.publish(request)

        # 入队后状态应为 QUEUED（由队列管理器设置）或 PENDING
        status = coordinator.get_save_request_status(request.request_id)
        assert status in (SaveRequestStatus.PENDING, SaveRequestStatus.QUEUED)

    def test_coordinator_emits_save_request_received_event(self):
        """测试：Coordinator 发布 SaveRequestReceived 事件"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestReceivedEvent,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        received_events = []
        event_bus.subscribe(SaveRequestReceivedEvent, lambda e: received_events.append(e))

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )
        event_bus.publish(request)

        assert len(received_events) == 1
        assert isinstance(received_events[0], SaveRequestReceivedEvent)
        assert received_events[0].request_id == request.request_id


class TestSaveRequestQueueManager:
    """SaveRequestQueueManager 测试"""

    def test_queue_manager_initialization(self):
        """测试：队列管理器初始化"""
        from src.domain.services.save_request_channel import SaveRequestQueueManager

        manager = SaveRequestQueueManager()
        assert manager.queue_size() == 0
        assert manager.is_empty()

    def test_queue_manager_enqueue(self):
        """测试：队列管理器入队"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestQueueManager,
            SaveRequestType,
        )

        manager = SaveRequestQueueManager()
        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        manager.enqueue(request)

        assert manager.queue_size() == 1
        assert not manager.is_empty()

    def test_queue_manager_dequeue_by_priority(self):
        """测试：队列管理器按优先级出队"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
            SaveRequestQueueManager,
            SaveRequestType,
        )

        manager = SaveRequestQueueManager()

        # 入队不同优先级
        low = SaveRequest(
            target_path="/tmp/low.txt",
            content="low",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="s1",
            reason="low",
            priority=SaveRequestPriority.LOW,
        )
        high = SaveRequest(
            target_path="/tmp/high.txt",
            content="high",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="s1",
            reason="high",
            priority=SaveRequestPriority.HIGH,
        )

        manager.enqueue(low)
        manager.enqueue(high)

        # 高优先级先出队
        first = manager.dequeue()
        assert first.priority == SaveRequestPriority.HIGH

        second = manager.dequeue()
        assert second.priority == SaveRequestPriority.LOW

    def test_queue_manager_peek(self):
        """测试：队列管理器查看队首"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestQueueManager,
            SaveRequestType,
        )

        manager = SaveRequestQueueManager()
        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        manager.enqueue(request)

        # peek 不移除元素
        peeked = manager.peek()
        assert peeked.request_id == request.request_id
        assert manager.queue_size() == 1

    def test_queue_manager_get_by_session(self):
        """测试：队列管理器按会话获取请求"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestQueueManager,
            SaveRequestType,
        )

        manager = SaveRequestQueueManager()

        req1 = SaveRequest(
            target_path="/tmp/1.txt",
            content="1",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-A",
            reason="1",
        )
        req2 = SaveRequest(
            target_path="/tmp/2.txt",
            content="2",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-B",
            reason="2",
        )
        req3 = SaveRequest(
            target_path="/tmp/3.txt",
            content="3",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-A",
            reason="3",
        )

        manager.enqueue(req1)
        manager.enqueue(req2)
        manager.enqueue(req3)

        session_a_requests = manager.get_by_session("session-A")
        assert len(session_a_requests) == 2

    def test_queue_manager_max_size_limit(self):
        """测试：队列管理器最大容量限制"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestQueueFullError,
            SaveRequestQueueManager,
            SaveRequestType,
        )

        manager = SaveRequestQueueManager(max_size=2)

        for i in range(2):
            manager.enqueue(
                SaveRequest(
                    target_path=f"/tmp/{i}.txt",
                    content=str(i),
                    operation_type=SaveRequestType.FILE_WRITE,
                    session_id="s1",
                    reason=str(i),
                )
            )

        # 第三个应该抛出错误
        with pytest.raises(SaveRequestQueueFullError):
            manager.enqueue(
                SaveRequest(
                    target_path="/tmp/overflow.txt",
                    content="overflow",
                    operation_type=SaveRequestType.FILE_WRITE,
                    session_id="s1",
                    reason="overflow",
                )
            )


# =============================================================================
# 第四部分：端到端场景测试
# =============================================================================


class TestSaveRequestEndToEndScenarios:
    """端到端场景测试"""

    def test_complete_save_request_flow(self):
        """测试：完整的保存请求流程"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        # 设置
        event_bus = SyncEventBus()
        mock_llm = MagicMock()
        session_context = create_test_session_context("user-session-001")

        conversation_agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        conversation_agent.enable_save_request_channel()

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        # ConversationAgent 发起保存请求
        conversation_agent.request_save(
            target_path="/data/output/result.json",
            content='{"status": "success"}',
            reason="保存处理结果",
        )

        # 验证 Coordinator 收到请求
        assert coordinator.has_pending_save_requests()

        # 获取请求
        pending = coordinator.get_save_request_queue()
        assert len(pending) == 1
        assert pending[0].target_path == "/data/output/result.json"
        assert pending[0].session_id == "user-session-001"
        assert pending[0].source_agent == "ConversationAgent"

    def test_multiple_agents_save_requests_isolated(self):
        """测试：多个 Agent 的保存请求相互隔离"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        event_bus = SyncEventBus()
        mock_llm = MagicMock()

        # 创建两个 ConversationAgent（不同会话）
        session_context_a = create_test_session_context("session-A")
        agent1 = ConversationAgent(
            session_context=session_context_a,
            llm=mock_llm,
            event_bus=event_bus,
        )
        agent1.enable_save_request_channel()

        session_context_b = create_test_session_context("session-B")
        agent2 = ConversationAgent(
            session_context=session_context_b,
            llm=mock_llm,
            event_bus=event_bus,
        )
        agent2.enable_save_request_channel()

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        # 各自发送保存请求
        agent1.request_save("/tmp/a.txt", "content A", "from A")
        agent2.request_save("/tmp/b.txt", "content B", "from B")

        # 验证按会话隔离
        session_a = coordinator.get_save_requests_by_session("session-A")
        session_b = coordinator.get_save_requests_by_session("session-B")

        assert len(session_a) == 1
        assert len(session_b) == 1
        assert session_a[0].target_path == "/tmp/a.txt"
        assert session_b[0].target_path == "/tmp/b.txt"

    def test_save_request_with_binary_content(self):
        """测试：二进制内容的保存请求"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00"

        request = SaveRequest(
            target_path="/tmp/image.png",
            content=binary_content,
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="Save image",
            is_binary=True,
        )

        assert request.is_binary is True
        assert request.content == binary_content

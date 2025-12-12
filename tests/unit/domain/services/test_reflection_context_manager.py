"""ReflectionContextManager 单元测试 - Phase 35.4

TDD Red Phase: 测试 ReflectionContextManager 模块的核心功能
- 反思监听与事件处理
- 压缩集成
- 取消订阅bug修复验证
"""

import pytest

from src.domain.services.event_bus import EventBus


@pytest.fixture
def event_bus():
    """EventBus fixture"""
    return EventBus()


@pytest.fixture
def reflection_contexts():
    """共享的 reflection_contexts 字典"""
    return {}


@pytest.fixture
def compressed_contexts():
    """共享的 compressed_contexts 字典"""
    return {}


@pytest.fixture
def manager(event_bus, reflection_contexts, compressed_contexts):
    """ReflectionContextManager fixture"""
    from src.domain.services.reflection_context_manager import ReflectionContextManager

    return ReflectionContextManager(
        event_bus=event_bus,
        reflection_contexts=reflection_contexts,
        compressed_contexts=compressed_contexts,
    )


class TestReflectionContextManagerInit:
    """测试：ReflectionContextManager 初始化"""

    def test_manager_initialization(self, event_bus, reflection_contexts, compressed_contexts):
        """测试：初始化应成功并设置属性"""
        from src.domain.services.reflection_context_manager import ReflectionContextManager

        manager = ReflectionContextManager(
            event_bus=event_bus,
            reflection_contexts=reflection_contexts,
            compressed_contexts=compressed_contexts,
        )

        assert manager.event_bus is event_bus
        assert manager.reflection_contexts is reflection_contexts
        assert manager._compressed_contexts is compressed_contexts
        assert manager._is_listening_reflections is False
        assert manager._current_reflection_handler is None  # Bug修复关键

    def test_manager_allows_none_event_bus(self, reflection_contexts, compressed_contexts):
        """测试：允许 event_bus=None 以支持延迟初始化"""
        from src.domain.services.reflection_context_manager import ReflectionContextManager

        manager = ReflectionContextManager(
            event_bus=None,
            reflection_contexts=reflection_contexts,
            compressed_contexts=compressed_contexts,
        )

        assert manager.event_bus is None


class TestReflectionListening:
    """测试：反思监听功能"""

    def test_start_listening_subscribes_to_event(self, manager, event_bus):
        """测试：start_reflection_listening 应订阅事件"""
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        manager.start_reflection_listening()

        assert WorkflowReflectionCompletedEvent in event_bus._subscribers
        assert manager._is_listening_reflections is True
        assert manager._current_reflection_handler is not None  # 关键：记录handler

    def test_start_listening_raises_when_no_event_bus(
        self, reflection_contexts, compressed_contexts
    ):
        """测试：event_bus=None 时 start 应抛异常"""
        from src.domain.services.reflection_context_manager import ReflectionContextManager

        manager = ReflectionContextManager(
            event_bus=None,
            reflection_contexts=reflection_contexts,
            compressed_contexts=compressed_contexts,
        )

        with pytest.raises(ValueError, match="EventBus is required"):
            manager.start_reflection_listening()

    def test_stop_listening_uses_correct_handler(self, manager, event_bus):
        """测试：stop 应使用记录的 handler 取消订阅（bug修复验证）"""
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        manager.start_reflection_listening()

        manager.stop_reflection_listening()

        # 验证使用正确的 handler 取消订阅
        assert manager._current_reflection_handler is None
        assert manager._is_listening_reflections is False
        # EventBus 应该没有残留订阅
        assert (
            WorkflowReflectionCompletedEvent not in event_bus._subscribers
            or len(event_bus._subscribers.get(WorkflowReflectionCompletedEvent, [])) == 0
        )

    def test_start_is_idempotent(self, manager, event_bus):
        """测试：重复 start 不应重复订阅"""
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        manager.start_reflection_listening()
        manager.start_reflection_listening()

        subscribers = event_bus._subscribers.get(WorkflowReflectionCompletedEvent, [])
        assert len(subscribers) == 1


class TestReflectionEventHandling:
    """测试：反思事件处理"""

    @pytest.mark.asyncio
    async def test_handle_reflection_event_creates_new_context(
        self, manager, event_bus, reflection_contexts
    ):
        """测试：处理事件应创建新反思上下文"""
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        manager.start_reflection_listening()

        event = WorkflowReflectionCompletedEvent(
            source="test",
            workflow_id="wf_1",
            assessment="良好",
            should_retry=False,
            confidence=0.85,
        )

        await event_bus.publish(event)

        # 验证上下文创建
        assert "wf_1" in reflection_contexts
        context = reflection_contexts["wf_1"]
        assert context["workflow_id"] == "wf_1"
        assert context["assessment"] == "良好"
        assert context["should_retry"] is False
        assert context["confidence"] == 0.85
        assert len(context["history"]) == 1

    @pytest.mark.asyncio
    async def test_handle_reflection_event_updates_existing_context(
        self, manager, event_bus, reflection_contexts
    ):
        """测试：处理事件应更新现有上下文"""
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        manager.start_reflection_listening()

        # 第一个事件
        event1 = WorkflowReflectionCompletedEvent(
            source="test",
            workflow_id="wf_1",
            assessment="良好",
            should_retry=False,
            confidence=0.85,
        )
        await event_bus.publish(event1)

        # 第二个事件
        event2 = WorkflowReflectionCompletedEvent(
            source="test",
            workflow_id="wf_1",
            assessment="需要改进",
            should_retry=True,
            confidence=0.65,
        )
        await event_bus.publish(event2)

        # 验证上下文更新
        context = reflection_contexts["wf_1"]
        assert context["assessment"] == "需要改进"
        assert context["should_retry"] is True
        assert context["confidence"] == 0.65
        assert len(context["history"]) == 2


class TestReflectionSummary:
    """测试：反思摘要功能"""

    def test_get_reflection_summary_returns_none_for_missing_workflow(self, manager):
        """测试：不存在的 workflow 应返回 None"""
        summary = manager.get_reflection_summary("nonexistent")
        assert summary is None

    def test_get_reflection_summary_returns_correct_data(self, manager, reflection_contexts):
        """测试：应返回正确的摘要数据"""
        # 手动添加上下文
        reflection_contexts["wf_1"] = {
            "workflow_id": "wf_1",
            "assessment": "良好",
            "should_retry": False,
            "confidence": 0.85,
            "timestamp": "2025-12-12T10:00:00",
            "history": [{"assessment": "良好"}],
        }

        summary = manager.get_reflection_summary("wf_1")

        assert summary is not None
        assert summary["workflow_id"] == "wf_1"
        assert summary["assessment"] == "良好"
        assert summary["should_retry"] is False
        assert summary["confidence"] == 0.85
        assert summary["total_reflections"] == 1


class TestCompressionIntegration:
    """测试：压缩集成功能"""

    def test_start_compression_enables_flag(self, manager):
        """测试：start_context_compression 应启用压缩"""
        manager.start_context_compression()
        assert manager._is_compressing_context is True

    def test_stop_compression_disables_flag(self, manager):
        """测试：stop_context_compression 应禁用压缩"""
        manager.start_context_compression()
        manager.stop_context_compression()
        assert manager._is_compressing_context is False

    def test_get_compressed_context_returns_none_when_missing(self, manager):
        """测试：不存在的压缩上下文应返回 None"""
        result = manager.get_compressed_context("nonexistent")
        assert result is None


class TestBugFixes:
    """测试：Bug 修复验证"""

    def test_subscription_handler_mismatch_bug_fixed(self, manager, event_bus):
        """测试：验证取消订阅 bug 已修复

        之前的bug：start 时可能订阅 handler_A，但 stop 时总是用 handler_B 取消，
        导致订阅残留。修复后应使用 _current_reflection_handler 记录。
        """
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        # 启动监听（不带压缩）
        manager.start_reflection_listening(enable_compression=False)

        # 停止监听
        manager.stop_reflection_listening()

        # 验证：应该没有残留订阅
        assert (
            WorkflowReflectionCompletedEvent not in event_bus._subscribers
            or len(event_bus._subscribers.get(WorkflowReflectionCompletedEvent, [])) == 0
        )
        assert manager._current_reflection_handler is None

    def test_compression_mode_handler_unsubscribe_correctly(self, manager, event_bus):
        """测试：压缩模式下的 handler 也能正确取消订阅"""
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        # 启动监听（带压缩）
        manager.start_reflection_listening(enable_compression=True)
        assert manager._is_compressing_context is True

        # 停止监听
        manager.stop_reflection_listening()

        # 验证：应该没有残留订阅
        assert (
            WorkflowReflectionCompletedEvent not in event_bus._subscribers
            or len(event_bus._subscribers.get(WorkflowReflectionCompletedEvent, [])) == 0
        )

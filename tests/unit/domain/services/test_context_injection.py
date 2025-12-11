"""上下文注入机制测试 (Context Injection Tests)

TDD 测试用例：
1. InjectionType 枚举测试
2. InjectionPoint 枚举测试
3. ContextInjection 数据结构测试
4. ContextInjectionManager 测试
5. 注入事件测试
6. 注入日志测试
7. CoordinatorAgent 集成测试
8. ConversationAgent 集成测试
9. 端到端注入影响决策测试

测试日期：2025-12-08
"""


# =============================================================================
# 测试辅助类
# =============================================================================


class SyncEventBus:
    """同步事件总线（测试用）"""

    def __init__(self):
        self._handlers: dict[str, list] = {}
        self._events: list = []

    def subscribe(self, event_type: str, handler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event) -> None:
        self._events.append(event)
        event_type = getattr(event, "event_type", type(event).__name__)
        for handler in self._handlers.get(event_type, []):
            handler(event)

    def get_events(self) -> list:
        return self._events.copy()

    def clear(self) -> None:
        self._events.clear()


# =============================================================================
# 1. InjectionType 枚举测试
# =============================================================================


class TestInjectionType:
    """InjectionType 枚举测试"""

    def test_injection_type_instruction(self):
        """测试 INSTRUCTION 类型"""
        from src.domain.services.context_injection import InjectionType

        assert InjectionType.INSTRUCTION.value == "instruction"

    def test_injection_type_observation(self):
        """测试 OBSERVATION 类型"""
        from src.domain.services.context_injection import InjectionType

        assert InjectionType.OBSERVATION.value == "observation"

    def test_injection_type_memory(self):
        """测试 MEMORY 类型"""
        from src.domain.services.context_injection import InjectionType

        assert InjectionType.MEMORY.value == "memory"

    def test_injection_type_warning(self):
        """测试 WARNING 类型"""
        from src.domain.services.context_injection import InjectionType

        assert InjectionType.WARNING.value == "warning"

    def test_injection_type_supplement(self):
        """测试 SUPPLEMENT 类型"""
        from src.domain.services.context_injection import InjectionType

        assert InjectionType.SUPPLEMENT.value == "supplement"

    def test_injection_type_intervention(self):
        """测试 INTERVENTION 类型"""
        from src.domain.services.context_injection import InjectionType

        assert InjectionType.INTERVENTION.value == "intervention"


# =============================================================================
# 2. InjectionPoint 枚举测试
# =============================================================================


class TestInjectionPoint:
    """InjectionPoint 枚举测试"""

    def test_injection_point_pre_loop(self):
        """测试 PRE_LOOP 注入点"""
        from src.domain.services.context_injection import InjectionPoint

        assert InjectionPoint.PRE_LOOP.value == "pre_loop"

    def test_injection_point_pre_thinking(self):
        """测试 PRE_THINKING 注入点"""
        from src.domain.services.context_injection import InjectionPoint

        assert InjectionPoint.PRE_THINKING.value == "pre_thinking"

    def test_injection_point_post_thinking(self):
        """测试 POST_THINKING 注入点"""
        from src.domain.services.context_injection import InjectionPoint

        assert InjectionPoint.POST_THINKING.value == "post_thinking"

    def test_injection_point_intervention(self):
        """测试 INTERVENTION 注入点"""
        from src.domain.services.context_injection import InjectionPoint

        assert InjectionPoint.INTERVENTION.value == "intervention"


# =============================================================================
# 3. ContextInjection 数据结构测试
# =============================================================================


class TestContextInjection:
    """ContextInjection 数据结构测试"""

    def test_context_injection_creation(self):
        """测试 ContextInjection 创建"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.WARNING,
            injection_point=InjectionPoint.PRE_THINKING,
            content="注意：检测到潜在安全风险",
            source="supervisor",
            reason="敏感操作检测",
        )

        assert injection.session_id == "session-001"
        assert injection.injection_type == InjectionType.WARNING
        assert injection.injection_point == InjectionPoint.PRE_THINKING
        assert injection.content == "注意：检测到潜在安全风险"
        assert injection.source == "supervisor"
        assert injection.reason == "敏感操作检测"
        assert injection.injection_id is not None
        assert injection.priority == 0  # 默认优先级

    def test_context_injection_with_priority(self):
        """测试带优先级的 ContextInjection"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.INTERVENTION,
            injection_point=InjectionPoint.INTERVENTION,
            content="紧急干预：停止当前操作",
            source="coordinator",
            reason="规则违反",
            priority=100,
        )

        assert injection.priority == 100

    def test_context_injection_with_metadata(self):
        """测试带元数据的 ContextInjection"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.MEMORY,
            injection_point=InjectionPoint.PRE_LOOP,
            content="用户偏好：简洁回复",
            source="memory_system",
            reason="长期记忆",
            metadata={"memory_id": "mem-123", "relevance_score": 0.95},
        )

        assert injection.metadata["memory_id"] == "mem-123"
        assert injection.metadata["relevance_score"] == 0.95

    def test_context_injection_to_dict(self):
        """测试 to_dict 序列化"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.INSTRUCTION,
            injection_point=InjectionPoint.PRE_LOOP,
            content="新指令",
            source="coordinator",
            reason="指令更新",
        )

        data = injection.to_dict()

        assert data["session_id"] == "session-001"
        assert data["injection_type"] == "instruction"
        assert data["injection_point"] == "pre_loop"
        assert data["content"] == "新指令"
        assert "timestamp" in data

    def test_context_injection_to_prompt_format(self):
        """测试 to_prompt_format 生成提示词格式"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.WARNING,
            injection_point=InjectionPoint.PRE_THINKING,
            content="注意安全风险",
            source="supervisor",
            reason="检测到敏感操作",
        )

        prompt = injection.to_prompt_format()

        assert "[WARNING]" in prompt or "[警告]" in prompt
        assert "注意安全风险" in prompt


# =============================================================================
# 4. ContextInjectionManager 测试
# =============================================================================


class TestContextInjectionManager:
    """ContextInjectionManager 测试"""

    def test_manager_creation(self):
        """测试管理器创建"""
        from src.domain.services.context_injection import ContextInjectionManager

        manager = ContextInjectionManager()
        assert manager is not None

    def test_add_injection(self):
        """测试添加注入"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.INSTRUCTION,
            injection_point=InjectionPoint.PRE_LOOP,
            content="测试指令",
            source="test",
            reason="测试",
        )

        manager.add_injection(injection)

        pending = manager.get_pending_injections("session-001", InjectionPoint.PRE_LOOP)
        assert len(pending) == 1
        assert pending[0].content == "测试指令"

    def test_get_pending_by_point(self):
        """测试按注入点获取待处理注入"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        # 添加不同注入点的注入
        manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.MEMORY,
                injection_point=InjectionPoint.PRE_LOOP,
                content="长期记忆",
                source="memory",
                reason="recall",
            )
        )

        manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.WARNING,
                injection_point=InjectionPoint.PRE_THINKING,
                content="警告信息",
                source="supervisor",
                reason="检测",
            )
        )

        # 按注入点获取
        pre_loop = manager.get_pending_injections("session-001", InjectionPoint.PRE_LOOP)
        pre_thinking = manager.get_pending_injections("session-001", InjectionPoint.PRE_THINKING)

        assert len(pre_loop) == 1
        assert len(pre_thinking) == 1
        assert pre_loop[0].content == "长期记忆"
        assert pre_thinking[0].content == "警告信息"

    def test_mark_as_applied(self):
        """测试标记注入已应用"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.INSTRUCTION,
            injection_point=InjectionPoint.PRE_LOOP,
            content="测试指令",
            source="test",
            reason="测试",
        )

        manager.add_injection(injection)

        # 标记已应用
        manager.mark_as_applied(injection.injection_id)

        # 再次获取应为空
        pending = manager.get_pending_injections("session-001", InjectionPoint.PRE_LOOP)
        assert len(pending) == 0

    def test_clear_session_injections(self):
        """测试清除会话注入"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.INSTRUCTION,
                injection_point=InjectionPoint.PRE_LOOP,
                content="指令1",
                source="test",
                reason="test",
            )
        )

        manager.add_injection(
            ContextInjection(
                session_id="session-002",
                injection_type=InjectionType.INSTRUCTION,
                injection_point=InjectionPoint.PRE_LOOP,
                content="指令2",
                source="test",
                reason="test",
            )
        )

        # 清除 session-001
        manager.clear_session("session-001")

        assert len(manager.get_pending_injections("session-001", InjectionPoint.PRE_LOOP)) == 0
        assert len(manager.get_pending_injections("session-002", InjectionPoint.PRE_LOOP)) == 1

    def test_priority_ordering(self):
        """测试优先级排序"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        # 添加不同优先级的注入
        manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.INSTRUCTION,
                injection_point=InjectionPoint.PRE_LOOP,
                content="低优先级",
                source="test",
                reason="test",
                priority=1,
            )
        )

        manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.INTERVENTION,
                injection_point=InjectionPoint.PRE_LOOP,
                content="高优先级",
                source="test",
                reason="test",
                priority=100,
            )
        )

        manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.WARNING,
                injection_point=InjectionPoint.PRE_LOOP,
                content="中优先级",
                source="test",
                reason="test",
                priority=50,
            )
        )

        # 获取时应按优先级排序（高优先级在前）
        pending = manager.get_pending_injections("session-001", InjectionPoint.PRE_LOOP)

        assert pending[0].content == "高优先级"
        assert pending[1].content == "中优先级"
        assert pending[2].content == "低优先级"

    def test_inject_memory(self):
        """测试注入长期记忆的便捷方法"""
        from src.domain.services.context_injection import (
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        manager.inject_memory(
            session_id="session-001",
            content="用户偏好：简洁回复",
            source="memory_system",
            relevance_score=0.9,
        )

        pending = manager.get_pending_injections("session-001", InjectionPoint.PRE_LOOP)
        assert len(pending) == 1
        assert pending[0].injection_type == InjectionType.MEMORY
        assert pending[0].content == "用户偏好：简洁回复"

    def test_inject_warning(self):
        """测试注入警告的便捷方法"""
        from src.domain.services.context_injection import (
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        manager.inject_warning(
            session_id="session-001",
            content="检测到敏感操作",
            source="supervisor",
            reason="安全检查",
        )

        pending = manager.get_pending_injections("session-001", InjectionPoint.PRE_THINKING)
        assert len(pending) == 1
        assert pending[0].injection_type == InjectionType.WARNING

    def test_inject_intervention(self):
        """测试注入干预的便捷方法"""
        from src.domain.services.context_injection import (
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        manager = ContextInjectionManager()

        manager.inject_intervention(
            session_id="session-001",
            content="停止当前操作，等待审批",
            source="coordinator",
            reason="需要人工审核",
        )

        pending = manager.get_pending_injections("session-001", InjectionPoint.INTERVENTION)
        assert len(pending) == 1
        assert pending[0].injection_type == InjectionType.INTERVENTION
        assert pending[0].priority == 100  # 干预优先级最高


# =============================================================================
# 5. 注入事件测试
# =============================================================================


class TestInjectionEvents:
    """注入事件测试"""

    def test_context_injection_event(self):
        """测试 ContextInjectionEvent 创建"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionEvent,
            InjectionPoint,
            InjectionType,
        )

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.WARNING,
            injection_point=InjectionPoint.PRE_THINKING,
            content="警告内容",
            source="supervisor",
            reason="测试",
        )

        event = ContextInjectionEvent(injection=injection)

        assert event.event_type == "context_injection"
        assert event.injection.content == "警告内容"

    def test_injection_applied_event(self):
        """测试 InjectionAppliedEvent 创建"""
        from src.domain.services.context_injection import InjectionAppliedEvent

        event = InjectionAppliedEvent(
            injection_id="inj-001",
            session_id="session-001",
            applied_at_iteration=2,
        )

        assert event.event_type == "injection_applied"
        assert event.injection_id == "inj-001"
        assert event.applied_at_iteration == 2

    def test_event_bus_integration(self):
        """测试事件总线集成"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionEvent,
            InjectionPoint,
            InjectionType,
        )

        bus = SyncEventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe("context_injection", handler)

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.WARNING,
            injection_point=InjectionPoint.PRE_THINKING,
            content="警告",
            source="test",
            reason="test",
        )

        event = ContextInjectionEvent(injection=injection)
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].injection.content == "警告"


# =============================================================================
# 6. 注入日志测试
# =============================================================================


class TestInjectionLogger:
    """注入日志测试"""

    def test_logger_creation(self):
        """测试日志记录器创建"""
        from src.domain.services.context_injection import InjectionLogger

        logger = InjectionLogger()
        assert logger is not None

    def test_log_injection(self):
        """测试记录注入"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionLogger,
            InjectionPoint,
            InjectionType,
        )

        logger = InjectionLogger()

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.WARNING,
            injection_point=InjectionPoint.PRE_THINKING,
            content="警告内容",
            source="supervisor",
            reason="安全检测",
        )

        logger.log_injection(injection)

        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["type"] == "injection"
        assert logs[0]["injection_type"] == "warning"
        assert logs[0]["content"] == "警告内容"

    def test_log_applied(self):
        """测试记录注入已应用"""
        from src.domain.services.context_injection import InjectionLogger

        logger = InjectionLogger()

        logger.log_applied(
            injection_id="inj-001",
            session_id="session-001",
            iteration=2,
        )

        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["type"] == "applied"
        assert logs[0]["injection_id"] == "inj-001"
        assert logs[0]["iteration"] == 2

    def test_get_logs_by_session(self):
        """测试按会话获取日志"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionLogger,
            InjectionPoint,
            InjectionType,
        )

        logger = InjectionLogger()

        # 添加不同会话的日志
        logger.log_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.WARNING,
                injection_point=InjectionPoint.PRE_THINKING,
                content="会话1警告",
                source="test",
                reason="test",
            )
        )

        logger.log_injection(
            ContextInjection(
                session_id="session-002",
                injection_type=InjectionType.WARNING,
                injection_point=InjectionPoint.PRE_THINKING,
                content="会话2警告",
                source="test",
                reason="test",
            )
        )

        logs_1 = logger.get_logs_by_session("session-001")
        logs_2 = logger.get_logs_by_session("session-002")

        assert len(logs_1) == 1
        assert len(logs_2) == 1
        assert logs_1[0]["content"] == "会话1警告"


# =============================================================================
# 7. CoordinatorAgent 集成测试
# =============================================================================


class TestCoordinatorIntegration:
    """CoordinatorAgent 集成测试"""

    def test_coordinator_has_injection_manager(self):
        """测试 Coordinator 有注入管理器"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=bus)

        assert hasattr(coordinator, "injection_manager")
        assert coordinator.injection_manager is not None

    def test_coordinator_inject_to_session(self):
        """测试 Coordinator 向会话注入上下文"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_injection import InjectionPoint, InjectionType
        from src.domain.services.event_bus import EventBus

        bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=bus)

        # 注入指令
        coordinator.inject_context(
            session_id="session-001",
            injection_type=InjectionType.INSTRUCTION,
            content="请使用简洁的回复风格",
            reason="用户偏好设置",
        )

        # 验证注入已添加
        pending = coordinator.injection_manager.get_pending_injections(
            "session-001", InjectionPoint.PRE_LOOP
        )
        assert len(pending) == 1
        assert pending[0].content == "请使用简洁的回复风格"

    def test_coordinator_inject_warning_on_rule_violation(self):
        """测试 Coordinator 在规则违反时注入警告"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_injection import InjectionPoint
        from src.domain.services.event_bus import EventBus

        bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=bus)

        # 模拟规则违反触发警告
        coordinator.inject_warning(
            session_id="session-001",
            warning_message="检测到尝试访问系统文件",
            rule_id="path_blacklist",
        )

        pending = coordinator.injection_manager.get_pending_injections(
            "session-001", InjectionPoint.PRE_THINKING
        )
        assert len(pending) == 1
        assert "系统文件" in pending[0].content

    def test_coordinator_inject_intervention(self):
        """测试 Coordinator 注入干预"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_injection import InjectionPoint
        from src.domain.services.event_bus import EventBus

        bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=bus)

        # 注入干预
        coordinator.inject_intervention(
            session_id="session-001",
            intervention_message="操作需要人工审批，请等待",
            reason="高风险操作",
        )

        pending = coordinator.injection_manager.get_pending_injections(
            "session-001", InjectionPoint.INTERVENTION
        )
        assert len(pending) == 1
        assert pending[0].priority == 100  # 高优先级


# =============================================================================
# 8. ConversationAgent 集成测试
# =============================================================================


class TestConversationAgentIntegration:
    """ConversationAgent 集成测试"""

    def test_conversation_agent_receives_injections(self):
        """测试 ConversationAgent 接收注入"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        # 创建注入管理器
        injection_manager = ContextInjectionManager()

        # 添加注入
        injection_manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.INSTRUCTION,
                injection_point=InjectionPoint.PRE_LOOP,
                content="请简洁回复",
                source="coordinator",
                reason="用户偏好",
            )
        )

        # 验证可以获取注入
        injections = injection_manager.get_pending_injections(
            "session-001", InjectionPoint.PRE_LOOP
        )
        assert len(injections) == 1
        assert injections[0].content == "请简洁回复"

    def test_conversation_agent_applies_pre_loop_injection(self):
        """测试 ConversationAgent 在循环前应用注入"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        injection_manager = ContextInjectionManager()

        # 添加循环前注入
        injection_manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.MEMORY,
                injection_point=InjectionPoint.PRE_LOOP,
                content="[长期记忆] 用户是技术专家",
                source="memory_system",
                reason="记忆召回",
            )
        )

        # 获取注入并验证格式化
        injections = injection_manager.get_pending_injections(
            "session-001", InjectionPoint.PRE_LOOP
        )

        # 模拟构建注入上下文
        injected_context = "\n".join([inj.to_prompt_format() for inj in injections])

        assert "用户是技术专家" in injected_context
        assert "[记忆]" in injected_context


# =============================================================================
# 9. 端到端注入影响决策测试
# =============================================================================


class TestEndToEndInjectionInfluence:
    """端到端注入影响决策测试"""

    def test_warning_injection_influences_decision(self):
        """测试警告注入影响决策"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        injection_manager = ContextInjectionManager()

        # 注入警告
        injection_manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.WARNING,
                injection_point=InjectionPoint.PRE_THINKING,
                content="[警告] 检测到危险操作，请谨慎处理",
                source="supervisor",
                reason="安全检测",
            )
        )

        # 获取注入
        injections = injection_manager.get_pending_injections(
            "session-001", InjectionPoint.PRE_THINKING
        )

        # 构建注入上下文
        injected_context = "\n".join([inj.to_prompt_format() for inj in injections])

        # 验证警告在上下文中
        assert "危险操作" in injected_context
        assert "[警告]" in injected_context

    def test_intervention_has_highest_priority(self):
        """测试干预注入具有最高优先级"""
        from src.domain.services.context_injection import (
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        injection_manager = ContextInjectionManager()

        # 注入干预
        intervention = injection_manager.inject_intervention(
            session_id="session-001",
            content="[干预] 操作已被暂停，等待人工审批",
            source="coordinator",
            reason="需要审批",
        )

        # 验证干预有最高优先级
        assert intervention.priority == 100
        assert intervention.injection_type == InjectionType.INTERVENTION

        # 获取干预注入
        pending = injection_manager.get_pending_injections(
            "session-001", InjectionPoint.INTERVENTION
        )
        assert len(pending) == 1
        assert "暂停" in pending[0].content

    def test_memory_injection_provides_context(self):
        """测试记忆注入提供上下文"""
        from src.domain.services.context_injection import (
            ContextInjectionManager,
            InjectionPoint,
            InjectionType,
        )

        injection_manager = ContextInjectionManager()

        # 注入长期记忆
        memory = injection_manager.inject_memory(
            session_id="session-001",
            content="用户是Python专家，偏好详细技术解释",
            source="memory_system",
            relevance_score=0.95,
        )

        # 验证记忆注入
        assert memory.injection_type == InjectionType.MEMORY
        assert memory.injection_point == InjectionPoint.PRE_LOOP
        assert memory.metadata["relevance_score"] == 0.95

        # 获取注入并格式化
        injections = injection_manager.get_pending_injections(
            "session-001", InjectionPoint.PRE_LOOP
        )
        injected_context = "\n".join([inj.to_prompt_format() for inj in injections])

        assert "Python专家" in injected_context

    def test_multiple_injections_combined(self):
        """测试多个注入组合"""
        from src.domain.services.context_injection import (
            ContextInjectionManager,
            InjectionPoint,
        )

        injection_manager = ContextInjectionManager()

        # 添加多个注入
        injection_manager.inject_memory(
            session_id="session-001",
            content="[记忆] 用户背景信息",
            source="memory",
        )

        injection_manager.inject_observation(
            session_id="session-001",
            content="[观察] 系统当前状态",
            source="monitor",
        )

        injection_manager.inject_instruction(
            session_id="session-001",
            content="[指令] 请使用简洁风格",
            source="coordinator",
        )

        # 获取所有循环前注入
        injections = injection_manager.get_pending_injections(
            "session-001", InjectionPoint.PRE_LOOP
        )

        # 验证有 3 个注入
        assert len(injections) == 3

        # 验证按优先级排序（指令30 > 观察20 > 记忆10）
        assert "[指令]" in injections[0].content
        assert "[观察]" in injections[1].content
        assert "[记忆]" in injections[2].content


# =============================================================================
# 10. 日志记录测试
# =============================================================================


class TestInjectionLogging:
    """注入日志记录测试"""

    def test_injection_creates_log_entry(self):
        """测试注入创建日志条目"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionLogger,
            InjectionPoint,
            InjectionType,
        )

        logger = InjectionLogger()
        manager = ContextInjectionManager(logger=logger)

        manager.add_injection(
            ContextInjection(
                session_id="session-001",
                injection_type=InjectionType.WARNING,
                injection_point=InjectionPoint.PRE_THINKING,
                content="测试警告",
                source="test",
                reason="测试原因",
            )
        )

        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["reason"] == "测试原因"

    def test_applied_creates_log_entry(self):
        """测试应用注入创建日志条目"""
        from src.domain.services.context_injection import (
            ContextInjection,
            ContextInjectionManager,
            InjectionLogger,
            InjectionPoint,
            InjectionType,
        )

        logger = InjectionLogger()
        manager = ContextInjectionManager(logger=logger)

        injection = ContextInjection(
            session_id="session-001",
            injection_type=InjectionType.WARNING,
            injection_point=InjectionPoint.PRE_THINKING,
            content="测试警告",
            source="test",
            reason="测试",
        )

        manager.add_injection(injection)
        manager.mark_as_applied(injection.injection_id, iteration=3)

        logs = logger.get_logs()
        assert len(logs) == 2  # 一个注入日志，一个应用日志

        applied_log = [l for l in logs if l["type"] == "applied"][0]
        assert applied_log["iteration"] == 3

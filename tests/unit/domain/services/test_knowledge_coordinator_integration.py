"""测试协调者知识库集成 - Step 5: 检索与监督整合

测试目标:
1. Coordinator 应该能够检索相关笔记并注入给 ConversationAgent
2. Coordinator 应该记录 notes_injected 列表
3. Coordinator 应该使用 DeviationDetector 检测偏离
4. 当检测到偏离时应该触发告警
5. 支持查询注入历史和偏离历史
"""

from src.domain.services.knowledge_coordinator_integration import (
    DeviationRecord,
    InjectionRecord,
    KnowledgeCoordinator,
)
from src.domain.services.knowledge_deviation_alert import (
    AlertType,
)
from src.domain.services.knowledge_note import KnowledgeNote, NoteType


class TestKnowledgeCoordinator:
    """测试知识协调器"""

    def test_create_knowledge_coordinator_should_succeed(self):
        """测试: 创建知识协调器应该成功"""
        coordinator = KnowledgeCoordinator()

        assert coordinator is not None
        assert hasattr(coordinator, "inject_notes")
        assert hasattr(coordinator, "check_deviation")

    def test_inject_notes_should_retrieve_and_record(self):
        """测试: 注入笔记应该检索并记录"""
        coordinator = KnowledgeCoordinator()

        # 创建笔记库
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="数据库连接失败",
                owner="user_123",
                tags=["database"],
            ),
            KnowledgeNote.create(
                type=NoteType.NEXT_ACTION,
                content="优化查询性能",
                owner="user_123",
                tags=["performance"],
            ),
        ]

        # 注入笔记
        result = coordinator.inject_notes(
            query="database",
            available_notes=notes,
            session_id="session_001",
        )

        assert result is not None
        assert len(result.notes) > 0
        assert result.notes[0].type == NoteType.BLOCKER  # blocker 优先级最高

    def test_inject_notes_should_record_injection_history(self):
        """测试: 注入笔记应该记录注入历史"""
        coordinator = KnowledgeCoordinator()

        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="API 限流",
                owner="user_123",
                tags=["api"],
            ),
        ]

        coordinator.inject_notes(
            query="api",
            available_notes=notes,
            session_id="session_001",
        )

        # 查询注入历史
        history = coordinator.get_injection_history(session_id="session_001")

        assert len(history) == 1
        assert history[0].session_id == "session_001"
        assert len(history[0].injected_notes) > 0

    def test_check_deviation_should_detect_ignored_notes(self):
        """测试: 检查偏离应该检测被忽视的笔记"""
        coordinator = KnowledgeCoordinator()

        # 创建并注入笔记
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )

        coordinator.inject_notes(
            query="database",
            available_notes=[blocker],
            session_id="session_001",
        )

        # 模拟 agent 行动 (忽视了 blocker)
        agent_actions = [
            {"type": "decision", "content": "实现用户认证功能"},
        ]

        # 检查偏离
        alert = coordinator.check_deviation(
            session_id="session_001",
            agent_actions=agent_actions,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.REPLAN_REQUIRED
        assert len(alert.ignored_notes) == 1

    def test_check_deviation_should_return_none_when_no_deviation(self):
        """测试: 没有偏离时应该返回 None"""
        coordinator = KnowledgeCoordinator()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )

        coordinator.inject_notes(
            query="database",
            available_notes=[blocker],
            session_id="session_001",
        )

        # 模拟 agent 行动 (提到了 database)
        agent_actions = [
            {"type": "decision", "content": "解决数据库连接问题"},
        ]

        alert = coordinator.check_deviation(
            session_id="session_001",
            agent_actions=agent_actions,
        )

        assert alert is None

    def test_check_deviation_should_record_deviation_history(self):
        """测试: 检查偏离应该记录偏离历史"""
        coordinator = KnowledgeCoordinator()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="API 限流",
            owner="user_123",
            tags=["api"],
        )

        coordinator.inject_notes(
            query="api",
            available_notes=[blocker],
            session_id="session_001",
        )

        agent_actions = [
            {"type": "decision", "content": "实现缓存功能"},
        ]

        coordinator.check_deviation(
            session_id="session_001",
            agent_actions=agent_actions,
        )

        # 查询偏离历史
        history = coordinator.get_deviation_history(session_id="session_001")

        assert len(history) == 1
        assert history[0].session_id == "session_001"
        assert history[0].alert is not None

    def test_get_session_summary_should_return_statistics(self):
        """测试: 获取会话摘要应该返回统计信息"""
        coordinator = KnowledgeCoordinator()

        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="问题1",
                owner="user_123",
            ),
            KnowledgeNote.create(
                type=NoteType.NEXT_ACTION,
                content="计划1",
                owner="user_123",
            ),
        ]

        coordinator.inject_notes(
            query="test",
            available_notes=notes,
            session_id="session_001",
        )

        summary = coordinator.get_session_summary(session_id="session_001")

        assert "total_injections" in summary
        assert "total_deviations" in summary
        assert summary["total_injections"] == 1

    def test_inject_notes_should_limit_to_6_notes(self):
        """测试: 注入笔记应该限制为 6 条"""
        coordinator = KnowledgeCoordinator()

        # 创建 10 条笔记
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content=f"问题 {i}",
                owner="user_123",
                tags=["test"],
            )
            for i in range(10)
        ]

        result = coordinator.inject_notes(
            query="test",
            available_notes=notes,
            session_id="session_001",
        )

        assert len(result.notes) <= 6

    def test_inject_notes_should_prioritize_by_type_weight(self):
        """测试: 注入笔记应该按类型权重优先"""
        coordinator = KnowledgeCoordinator()

        notes = [
            KnowledgeNote.create(
                type=NoteType.CONCLUSION,
                content="结论",
                owner="user_123",
                tags=["test"],
            ),
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="阻塞",
                owner="user_123",
                tags=["test"],
            ),
            KnowledgeNote.create(
                type=NoteType.NEXT_ACTION,
                content="计划",
                owner="user_123",
                tags=["test"],
            ),
        ]

        result = coordinator.inject_notes(
            query="test",
            available_notes=notes,
            session_id="session_001",
        )

        # blocker 应该排在第一位
        assert result.notes[0].type == NoteType.BLOCKER


class TestInjectionRecord:
    """测试注入记录数据结构"""

    def test_create_injection_record_should_succeed(self):
        """测试: 创建注入记录应该成功"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="测试",
            owner="user_123",
        )

        record = InjectionRecord(
            session_id="session_001",
            query="test",
            injected_notes=[note],
        )

        assert record.session_id == "session_001"
        assert record.query == "test"
        assert len(record.injected_notes) == 1

    def test_injection_record_should_have_timestamp(self):
        """测试: 注入记录应该有时间戳"""
        record = InjectionRecord.create(
            session_id="session_001",
            query="test",
            injected_notes=[],
        )

        assert hasattr(record, "timestamp")
        assert record.timestamp is not None


class TestDeviationRecord:
    """测试偏离记录数据结构"""

    def test_create_deviation_record_should_succeed(self):
        """测试: 创建偏离记录应该成功"""
        from src.domain.services.knowledge_deviation_alert import DeviationAlert

        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="测试",
            owner="user_123",
        )

        alert = DeviationAlert.create(
            alert_type=AlertType.REPLAN_REQUIRED,
            ignored_notes=[note],
            reason="测试",
        )

        record = DeviationRecord(
            session_id="session_001",
            alert=alert,
        )

        assert record.session_id == "session_001"
        assert record.alert is not None

    def test_deviation_record_should_have_timestamp(self):
        """测试: 偏离记录应该有时间戳"""
        from src.domain.services.knowledge_deviation_alert import DeviationAlert

        alert = DeviationAlert.create(
            alert_type=AlertType.WARNING,
            ignored_notes=[],
            reason="测试",
        )

        record = DeviationRecord.create(
            session_id="session_001",
            alert=alert,
        )

        assert hasattr(record, "timestamp")
        assert record.timestamp is not None


class TestKnowledgeCoordinatorIntegration:
    """测试知识协调器集成"""

    def test_complete_workflow_should_succeed(self):
        """测试: 完整工作流应该成功"""
        coordinator = KnowledgeCoordinator()

        # 1. 创建笔记
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )
        next_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="实现缓存机制",
            owner="user_123",
            tags=["cache"],
        )

        # 2. 注入笔记
        result = coordinator.inject_notes(
            query="database",
            available_notes=[blocker, next_action],
            session_id="session_001",
        )

        assert len(result.notes) > 0

        # 3. 模拟 agent 行动 (忽视了 blocker)
        agent_actions = [
            {"type": "decision", "content": "实现缓存机制"},
        ]

        # 4. 检查偏离
        alert = coordinator.check_deviation(
            session_id="session_001",
            agent_actions=agent_actions,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.REPLAN_REQUIRED

        # 5. 查询历史
        injection_history = coordinator.get_injection_history(session_id="session_001")
        deviation_history = coordinator.get_deviation_history(session_id="session_001")

        assert len(injection_history) == 1
        assert len(deviation_history) == 1

        # 6. 获取摘要
        summary = coordinator.get_session_summary(session_id="session_001")

        assert summary["total_injections"] == 1
        assert summary["total_deviations"] == 1

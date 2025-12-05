"""测试 DeviationAlert（偏离告警）- Step 5: 检索与监督整合

测试目标：
1. DeviationAlert 应该包含告警类型、被忽视的笔记、原因、严重程度
2. DeviationDetector 应该检测 ConversationAgent 是否忽视高优先级笔记
3. 忽视 blocker 应该触发 REPLAN_REQUIRED 告警
4. 忽视 next_action 应该触发 WARNING 告警
5. 严重程度应该基于被忽视笔记的权重计算
"""

from src.domain.services.knowledge_deviation_alert import (
    AlertSeverity,
    AlertType,
    DeviationAlert,
    DeviationDetector,
)
from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteType,
)


class TestDeviationAlert:
    """测试偏离告警数据结构"""

    def test_create_deviation_alert_should_succeed(self):
        """测试：创建偏离告警应该成功"""
        ignored_note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
        )

        alert = DeviationAlert(
            alert_type=AlertType.REPLAN_REQUIRED,
            ignored_notes=[ignored_note],
            reason="ConversationAgent 忽视了高优先级 blocker",
            severity=AlertSeverity.HIGH,
        )

        assert alert.alert_type == AlertType.REPLAN_REQUIRED
        assert len(alert.ignored_notes) == 1
        assert alert.reason is not None
        assert alert.severity == AlertSeverity.HIGH

    def test_alert_type_should_have_two_types(self):
        """测试：AlertType 应该有两种类型"""
        types = list(AlertType)

        assert len(types) == 2
        assert AlertType.WARNING in types
        assert AlertType.REPLAN_REQUIRED in types

    def test_alert_severity_should_have_three_levels(self):
        """测试：AlertSeverity 应该有三个级别"""
        severities = list(AlertSeverity)

        assert len(severities) == 3
        assert AlertSeverity.LOW in severities
        assert AlertSeverity.MEDIUM in severities
        assert AlertSeverity.HIGH in severities

    def test_alert_should_have_timestamp(self):
        """测试：告警应该有时间戳"""
        alert = DeviationAlert.create(
            alert_type=AlertType.WARNING,
            ignored_notes=[],
            reason="测试",
        )

        assert hasattr(alert, "timestamp")
        assert alert.timestamp is not None

    def test_to_dict_should_return_serializable_dict(self):
        """测试：to_dict 应该返回可序列化的字典"""
        ignored_note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="测试",
            owner="user_123",
        )

        alert = DeviationAlert.create(
            alert_type=AlertType.REPLAN_REQUIRED,
            ignored_notes=[ignored_note],
            reason="测试原因",
        )

        data = alert.to_dict()

        assert data["alert_type"] == "replan_required"
        assert "ignored_notes" in data
        assert data["reason"] == "测试原因"
        assert "severity" in data
        assert "timestamp" in data


class TestDeviationDetector:
    """测试偏离检测器"""

    def test_create_deviation_detector_should_succeed(self):
        """测试：创建偏离检测器应该成功"""
        detector = DeviationDetector()

        assert detector is not None
        assert hasattr(detector, "detect_deviation")

    def test_detect_deviation_with_no_ignored_notes_should_return_none(self):
        """测试：没有被忽视的笔记应该返回 None"""
        detector = DeviationDetector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )

        # 模拟 agent 行动提到了 blocker
        agent_actions = [
            {"type": "decision", "content": "解决数据库连接失败问题"},
        ]

        alert = detector.detect_deviation(
            injected_notes=[blocker],
            agent_actions=agent_actions,
        )

        assert alert is None

    def test_detect_deviation_with_ignored_blocker_should_return_replan_alert(self):
        """测试：忽视 blocker 应该返回 REPLAN_REQUIRED 告警"""
        detector = DeviationDetector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )

        # 模拟 agent 行动完全没有提到 blocker
        agent_actions = [
            {"type": "decision", "content": "实现用户认证功能"},
        ]

        alert = detector.detect_deviation(
            injected_notes=[blocker],
            agent_actions=agent_actions,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.REPLAN_REQUIRED
        assert len(alert.ignored_notes) == 1
        assert alert.severity == AlertSeverity.HIGH

    def test_detect_deviation_with_ignored_next_action_should_return_warning(self):
        """测试：忽视 next_action 应该返回 WARNING 告警"""
        detector = DeviationDetector()

        next_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="优化数据库查询性能",
            owner="user_123",
            tags=["database", "performance"],
        )

        # 模拟 agent 行动没有提到 next_action
        agent_actions = [
            {"type": "decision", "content": "实现用户认证功能"},
        ]

        alert = detector.detect_deviation(
            injected_notes=[next_action],
            agent_actions=agent_actions,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.WARNING
        assert len(alert.ignored_notes) == 1
        assert alert.severity == AlertSeverity.MEDIUM

    def test_is_note_ignored_should_detect_ignored_notes(self):
        """测试：is_note_ignored 应该检测被忽视的笔记"""
        detector = DeviationDetector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )

        # 行动中没有提到数据库
        agent_actions = [
            {"type": "decision", "content": "实现用户认证"},
        ]

        is_ignored = detector.is_note_ignored(blocker, agent_actions)

        assert is_ignored is True

    def test_is_note_ignored_should_detect_mentioned_notes(self):
        """测试：is_note_ignored 应该检测被提到的笔记"""
        detector = DeviationDetector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )

        # 行动中提到了数据库
        agent_actions = [
            {"type": "decision", "content": "解决数据库连接问题"},
        ]

        is_ignored = detector.is_note_ignored(blocker, agent_actions)

        assert is_ignored is False

    def test_calculate_severity_should_return_high_for_blocker(self):
        """测试：blocker 被忽视应该返回 HIGH 严重程度"""
        detector = DeviationDetector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="阻塞问题",
            owner="user_123",
        )

        severity = detector.calculate_severity([blocker])

        assert severity == AlertSeverity.HIGH

    def test_calculate_severity_should_return_medium_for_next_action(self):
        """测试：next_action 被忽视应该返回 MEDIUM 严重程度"""
        detector = DeviationDetector()

        next_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="计划任务",
            owner="user_123",
        )

        severity = detector.calculate_severity([next_action])

        assert severity == AlertSeverity.MEDIUM

    def test_calculate_severity_should_return_low_for_conclusion(self):
        """测试：conclusion 被忽视应该返回 LOW 严重程度"""
        detector = DeviationDetector()

        conclusion = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论",
            owner="user_123",
        )

        severity = detector.calculate_severity([conclusion])

        assert severity == AlertSeverity.LOW

    def test_calculate_severity_with_multiple_notes_should_use_highest(self):
        """测试：多个笔记被忽视应该使用最高严重程度"""
        detector = DeviationDetector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="阻塞",
            owner="user_123",
        )
        conclusion = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论",
            owner="user_123",
        )

        severity = detector.calculate_severity([blocker, conclusion])

        assert severity == AlertSeverity.HIGH

    def test_detect_deviation_should_check_all_injected_notes(self):
        """测试：偏离检测应该检查所有注入的笔记"""
        detector = DeviationDetector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )
        next_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="优化查询性能",
            owner="user_123",
            tags=["performance"],
        )

        # 只提到了性能，没有提到数据库
        agent_actions = [
            {"type": "decision", "content": "优化查询性能"},
        ]

        alert = detector.detect_deviation(
            injected_notes=[blocker, next_action],
            agent_actions=agent_actions,
        )

        # 应该检测到 blocker 被忽视
        assert alert is not None
        assert len(alert.ignored_notes) == 1
        assert alert.ignored_notes[0].type == NoteType.BLOCKER

    def test_get_alert_message_should_return_formatted_message(self):
        """测试：获取告警消息应该返回格式化的消息"""
        ignored_note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
        )

        alert = DeviationAlert.create(
            alert_type=AlertType.REPLAN_REQUIRED,
            ignored_notes=[ignored_note],
            reason="忽视了高优先级 blocker",
        )

        message = alert.get_alert_message()

        assert isinstance(message, str)
        assert "REPLAN_REQUIRED" in message or "重新规划" in message
        assert "blocker" in message.lower() or "阻塞" in message


class TestDeviationDetectionIntegration:
    """测试偏离检测与其他组件的集成"""

    def test_complete_detection_workflow_should_succeed(self):
        """测试：完整的偏离检测工作流应该成功"""
        from src.domain.services.knowledge_vault_retriever import VaultRetriever

        # 创建笔记
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="API 限流问题",
            owner="user_123",
            tags=["api", "blocker"],
        )
        next_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="实现缓存机制",
            owner="user_123",
            tags=["cache"],
        )

        # 检索笔记
        retriever = VaultRetriever()
        result = retriever.fetch(query="api", notes=[blocker, next_action])

        # 模拟 agent 行动（忽视了 blocker）
        agent_actions = [
            {"type": "decision", "content": "实现缓存机制"},
        ]

        # 检测偏离
        detector = DeviationDetector()
        alert = detector.detect_deviation(
            injected_notes=result.notes,
            agent_actions=agent_actions,
        )

        # 应该检测到偏离
        assert alert is not None
        assert alert.alert_type == AlertType.REPLAN_REQUIRED
        assert any(n.type == NoteType.BLOCKER for n in alert.ignored_notes)

"""测试 KnowledgeAuditLog（知识审计日志）- Step 4: 长期知识库治理

测试目标：
1. 审计日志应该记录所有笔记的状态变更
2. 记录谁在何时执行了什么操作
3. 支持按笔记ID、操作类型、操作者查询
4. 记录批准、拒绝、归档等关键操作
5. 审计日志不可修改（只能追加）
"""

from datetime import datetime

from src.domain.services.knowledge_audit_log import (
    AuditAction,
    AuditLog,
    AuditLogManager,
)
from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteType,
)


class TestAuditLog:
    """测试审计日志数据结构"""

    def test_create_audit_log_with_all_fields_should_succeed(self):
        """测试：创建包含所有字段的审计日志应该成功"""
        log = AuditLog(
            log_id="log_001",
            note_id="note_001",
            action=AuditAction.APPROVED,
            actor="admin_456",
            timestamp=datetime.now(),
            metadata={"reason": "内容完整"},
        )

        assert log.log_id == "log_001"
        assert log.note_id == "note_001"
        assert log.action == AuditAction.APPROVED
        assert log.actor == "admin_456"
        assert isinstance(log.timestamp, datetime)
        assert log.metadata == {"reason": "内容完整"}

    def test_audit_action_should_have_all_actions(self):
        """测试：AuditAction 应该包含所有操作类型"""
        actions = list(AuditAction)

        assert AuditAction.CREATED in actions
        assert AuditAction.SUBMITTED in actions
        assert AuditAction.APPROVED in actions
        assert AuditAction.REJECTED in actions
        assert AuditAction.ARCHIVED in actions
        assert AuditAction.UPDATED in actions

    def test_create_audit_log_should_auto_generate_id_and_timestamp(self):
        """测试：创建审计日志应该自动生成ID和时间戳"""
        log = AuditLog.create(
            note_id="note_001",
            action=AuditAction.CREATED,
            actor="user_123",
        )

        assert log.log_id is not None
        assert log.log_id.startswith("log_")
        assert isinstance(log.timestamp, datetime)

    def test_to_dict_should_return_serializable_dict(self):
        """测试：to_dict 应该返回可序列化的字典"""
        log = AuditLog.create(
            note_id="note_001",
            action=AuditAction.APPROVED,
            actor="admin_456",
            metadata={"comment": "批准通过"},
        )

        data = log.to_dict()

        assert data["log_id"] is not None
        assert data["note_id"] == "note_001"
        assert data["action"] == "approved"
        assert data["actor"] == "admin_456"
        assert "timestamp" in data
        assert data["metadata"] == {"comment": "批准通过"}

    def test_from_dict_should_reconstruct_audit_log(self):
        """测试：from_dict 应该能够重建审计日志"""
        data = {
            "log_id": "log_001",
            "note_id": "note_001",
            "action": "created",
            "actor": "user_123",
            "timestamp": "2025-01-22T10:00:00",
            "metadata": {},
        }

        log = AuditLog.from_dict(data)

        assert log.log_id == "log_001"
        assert log.note_id == "note_001"
        assert log.action == AuditAction.CREATED
        assert log.actor == "user_123"


class TestAuditLogManager:
    """测试审计日志管理器"""

    def test_log_note_creation_should_record_created_action(self):
        """测试：记录笔记创建应该记录 CREATED 操作"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展内容",
            owner="user_123",
        )

        manager = AuditLogManager()
        log = manager.log_note_creation(note)

        assert log.note_id == note.note_id
        assert log.action == AuditAction.CREATED
        assert log.actor == note.owner

    def test_log_note_submission_should_record_submitted_action(self):
        """测试：记录笔记提交应该记录 SUBMITTED 操作"""
        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论内容",
            owner="user_123",
        )

        manager = AuditLogManager()
        log = manager.log_note_submission(note)

        assert log.note_id == note.note_id
        assert log.action == AuditAction.SUBMITTED
        assert log.actor == note.owner

    def test_log_note_approval_should_record_approved_action(self):
        """测试：记录笔记批准应该记录 APPROVED 操作"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="阻塞内容",
            owner="user_123",
        )

        manager = AuditLogManager()
        log = manager.log_note_approval(note, approved_by="admin_456")

        assert log.note_id == note.note_id
        assert log.action == AuditAction.APPROVED
        assert log.actor == "admin_456"

    def test_log_note_rejection_should_record_rejected_action(self):
        """测试：记录笔记拒绝应该记录 REJECTED 操作"""
        note = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="行动内容",
            owner="user_123",
        )

        manager = AuditLogManager()
        log = manager.log_note_rejection(note, rejected_by="admin_456", reason="内容不完整")

        assert log.note_id == note.note_id
        assert log.action == AuditAction.REJECTED
        assert log.actor == "admin_456"
        assert log.metadata["reason"] == "内容不完整"

    def test_log_note_archival_should_record_archived_action(self):
        """测试：记录笔记归档应该记录 ARCHIVED 操作"""
        note = KnowledgeNote.create(
            type=NoteType.REFERENCE,
            content="参考内容",
            owner="user_123",
        )

        manager = AuditLogManager()
        log = manager.log_note_archival(note, archived_by="admin_456")

        assert log.note_id == note.note_id
        assert log.action == AuditAction.ARCHIVED
        assert log.actor == "admin_456"

    def test_get_logs_by_note_id_should_return_all_logs_for_note(self):
        """测试：按笔记ID获取日志应该返回该笔记的所有日志"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = AuditLogManager()
        manager.log_note_creation(note)
        manager.log_note_submission(note)
        manager.log_note_approval(note, approved_by="admin_456")

        logs = manager.get_logs_by_note_id(note.note_id)

        assert len(logs) == 3
        assert logs[0].action == AuditAction.CREATED
        assert logs[1].action == AuditAction.SUBMITTED
        assert logs[2].action == AuditAction.APPROVED

    def test_get_logs_by_actor_should_return_all_logs_by_actor(self):
        """测试：按操作者获取日志应该返回该操作者的所有日志"""
        note1 = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展1",
            owner="user_123",
        )
        note2 = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论2",
            owner="user_456",
        )

        manager = AuditLogManager()
        manager.log_note_approval(note1, approved_by="admin_789")
        manager.log_note_approval(note2, approved_by="admin_789")

        logs = manager.get_logs_by_actor("admin_789")

        assert len(logs) == 2
        assert all(log.actor == "admin_789" for log in logs)

    def test_get_logs_by_action_should_return_all_logs_of_action_type(self):
        """测试：按操作类型获取日志应该返回该类型的所有日志"""
        note1 = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展1",
            owner="user_123",
        )
        note2 = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论2",
            owner="user_456",
        )

        manager = AuditLogManager()
        manager.log_note_approval(note1, approved_by="admin_789")
        manager.log_note_approval(note2, approved_by="admin_789")
        manager.log_note_rejection(note1, rejected_by="admin_789", reason="测试")

        logs = manager.get_logs_by_action(AuditAction.APPROVED)

        assert len(logs) == 2
        assert all(log.action == AuditAction.APPROVED for log in logs)

    def test_get_logs_in_time_range_should_return_logs_within_range(self):
        """测试：按时间范围获取日志应该返回范围内的日志"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = AuditLogManager()
        start_time = datetime.now()
        manager.log_note_creation(note)
        manager.log_note_submission(note)
        end_time = datetime.now()

        logs = manager.get_logs_in_time_range(start_time, end_time)

        assert len(logs) >= 2

    def test_get_approval_history_should_return_who_approved_when(self):
        """测试：获取批准历史应该返回谁在何时批准"""
        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论",
            owner="user_123",
        )

        manager = AuditLogManager()
        manager.log_note_creation(note)
        manager.log_note_submission(note)
        manager.log_note_approval(note, approved_by="admin_456")

        history = manager.get_approval_history(note.note_id)

        assert len(history) == 1
        assert history[0]["actor"] == "admin_456"
        assert history[0]["action"] == "approved"
        assert "timestamp" in history[0]

    def test_audit_log_should_be_immutable(self):
        """测试：审计日志应该是不可变的"""
        log = AuditLog.create(
            note_id="note_001",
            action=AuditAction.CREATED,
            actor="user_123",
        )

        # 尝试修改日志应该失败（通过不提供修改方法来保证不可变性）
        assert not hasattr(log, "update")
        assert not hasattr(log, "modify")

    def test_get_all_logs_should_return_logs_in_chronological_order(self):
        """测试：获取所有日志应该按时间顺序返回"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = AuditLogManager()
        manager.log_note_creation(note)
        manager.log_note_submission(note)
        manager.log_note_approval(note, approved_by="admin_456")

        all_logs = manager.get_all_logs()

        assert len(all_logs) >= 3
        # 验证时间顺序
        for i in range(len(all_logs) - 1):
            assert all_logs[i].timestamp <= all_logs[i + 1].timestamp

    def test_count_logs_by_action_should_return_correct_counts(self):
        """测试：按操作类型统计日志数量应该返回正确的计数"""
        note1 = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展1",
            owner="user_123",
        )
        note2 = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论2",
            owner="user_456",
        )

        manager = AuditLogManager()
        manager.log_note_creation(note1)
        manager.log_note_creation(note2)
        manager.log_note_approval(note1, approved_by="admin_789")

        counts = manager.count_logs_by_action()

        assert counts[AuditAction.CREATED] == 2
        assert counts[AuditAction.APPROVED] == 1

    def test_get_recent_logs_should_return_latest_logs(self):
        """测试：获取最近日志应该返回最新的日志"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = AuditLogManager()
        manager.log_note_creation(note)
        manager.log_note_submission(note)
        manager.log_note_approval(note, approved_by="admin_456")

        recent_logs = manager.get_recent_logs(limit=2)

        assert len(recent_logs) == 2
        # 最新的日志应该在前面
        assert recent_logs[0].action == AuditAction.APPROVED
        assert recent_logs[1].action == AuditAction.SUBMITTED


class TestAuditLogIntegration:
    """测试审计日志与生命周期管理的集成"""

    def test_complete_lifecycle_should_generate_complete_audit_trail(self):
        """测试：完整生命周期应该生成完整的审计轨迹"""
        from src.domain.services.knowledge_note_lifecycle import NoteLifecycleManager

        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论内容",
            owner="user_123",
        )

        audit_manager = AuditLogManager()
        lifecycle_manager = NoteLifecycleManager()

        # 创建
        audit_manager.log_note_creation(note)

        # 提交审批
        lifecycle_manager.submit_for_approval(note)
        audit_manager.log_note_submission(note)

        # 批准
        lifecycle_manager.approve_note(note, approved_by="admin_456")
        audit_manager.log_note_approval(note, approved_by="admin_456")

        # 归档
        lifecycle_manager.archive_note(note)
        audit_manager.log_note_archival(note, archived_by="admin_456")

        # 验证审计轨迹
        logs = audit_manager.get_logs_by_note_id(note.note_id)

        assert len(logs) == 4
        assert logs[0].action == AuditAction.CREATED
        assert logs[1].action == AuditAction.SUBMITTED
        assert logs[2].action == AuditAction.APPROVED
        assert logs[3].action == AuditAction.ARCHIVED

        # 验证批准历史
        approval_history = audit_manager.get_approval_history(note.note_id)
        assert len(approval_history) == 1
        assert approval_history[0]["actor"] == "admin_456"

"""测试 KnowledgeNote 生命周期管理 - Step 4: 长期知识库治理

测试目标：
1. 笔记生命周期：draft → pending_user → approved → archived
2. 状态转换验证（只允许合法的状态转换）
3. 用户确认流程（需要记录确认者和时间）
4. 批准后的笔记不可修改（不可变性）
5. 归档操作
"""

from datetime import datetime

import pytest

from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteStatus,
    NoteType,
)
from src.domain.services.knowledge_note_lifecycle import (
    LifecycleTransitionError,
    NoteImmutableError,
    NoteLifecycleManager,
)


class TestNoteLifecycle:
    """测试笔记生命周期管理"""

    def test_new_note_should_start_as_draft(self):
        """测试：新笔记应该以 draft 状态开始"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="测试内容",
            owner="user_123",
        )

        assert note.status == NoteStatus.DRAFT
        assert note.is_draft() is True

    def test_submit_for_approval_should_change_status_to_pending_user(self):
        """测试：提交审批应该将状态改为 pending_user"""
        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论内容",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)

        assert note.status == NoteStatus.PENDING_USER

    def test_approve_note_should_change_status_to_approved(self):
        """测试：批准笔记应该将状态改为 approved"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="阻塞问题",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.approve_note(note, approved_by="admin_456")

        assert note.status == NoteStatus.APPROVED
        assert note.is_approved() is True
        assert note.approved_by == "admin_456"
        assert note.approved_at is not None
        assert isinstance(note.approved_at, datetime)

    def test_archive_note_should_change_status_to_archived(self):
        """测试：归档笔记应该将状态改为 archived"""
        note = KnowledgeNote.create(
            type=NoteType.REFERENCE,
            content="参考资料",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.approve_note(note, approved_by="admin_456")
        manager.archive_note(note)

        assert note.status == NoteStatus.ARCHIVED
        assert note.is_archived() is True

    def test_invalid_transition_from_draft_to_approved_should_raise_error(self):
        """测试：从 draft 直接到 approved 的非法转换应该抛出错误"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = NoteLifecycleManager()

        with pytest.raises(LifecycleTransitionError, match="draft.*approved"):
            manager.approve_note(note, approved_by="admin_456")

    def test_invalid_transition_from_draft_to_archived_should_raise_error(self):
        """测试：从 draft 直接到 archived 的非法转换应该抛出错误"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = NoteLifecycleManager()

        with pytest.raises(LifecycleTransitionError, match="draft.*archived"):
            manager.archive_note(note)

    def test_approve_without_approver_should_raise_error(self):
        """测试：批准时未指定批准者应该抛出错误"""
        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)

        with pytest.raises(ValueError, match="approved_by|批准者"):
            manager.approve_note(note, approved_by="")

    def test_reject_note_should_change_status_back_to_draft(self):
        """测试：拒绝笔记应该将状态改回 draft"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="阻塞",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.reject_note(note, reason="内容不完整")

        assert note.status == NoteStatus.DRAFT

    def test_complete_lifecycle_draft_to_archived_should_succeed(self):
        """测试：完整生命周期 draft → pending_user → approved → archived 应该成功"""
        note = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="下一步行动",
            owner="user_123",
        )

        manager = NoteLifecycleManager()

        # draft → pending_user
        manager.submit_for_approval(note)
        assert note.status == NoteStatus.PENDING_USER

        # pending_user → approved
        manager.approve_note(note, approved_by="admin_456")
        assert note.status == NoteStatus.APPROVED

        # approved → archived
        manager.archive_note(note)
        assert note.status == NoteStatus.ARCHIVED

    def test_get_valid_transitions_should_return_allowed_next_states(self):
        """测试：获取有效转换应该返回允许的下一个状态"""
        manager = NoteLifecycleManager()

        # draft 可以转换到 pending_user
        draft_transitions = manager.get_valid_transitions(NoteStatus.DRAFT)
        assert NoteStatus.PENDING_USER in draft_transitions

        # pending_user 可以转换到 approved 或 draft
        pending_transitions = manager.get_valid_transitions(NoteStatus.PENDING_USER)
        assert NoteStatus.APPROVED in pending_transitions
        assert NoteStatus.DRAFT in pending_transitions

        # approved 可以转换到 archived
        approved_transitions = manager.get_valid_transitions(NoteStatus.APPROVED)
        assert NoteStatus.ARCHIVED in approved_transitions

    def test_can_transition_should_return_true_for_valid_transitions(self):
        """测试：can_transition 应该对有效转换返回 True"""
        manager = NoteLifecycleManager()

        assert manager.can_transition(NoteStatus.DRAFT, NoteStatus.PENDING_USER) is True
        assert manager.can_transition(NoteStatus.PENDING_USER, NoteStatus.APPROVED) is True
        assert manager.can_transition(NoteStatus.PENDING_USER, NoteStatus.DRAFT) is True
        assert manager.can_transition(NoteStatus.APPROVED, NoteStatus.ARCHIVED) is True

    def test_can_transition_should_return_false_for_invalid_transitions(self):
        """测试：can_transition 应该对无效转换返回 False"""
        manager = NoteLifecycleManager()

        assert manager.can_transition(NoteStatus.DRAFT, NoteStatus.APPROVED) is False
        assert manager.can_transition(NoteStatus.DRAFT, NoteStatus.ARCHIVED) is False
        assert manager.can_transition(NoteStatus.ARCHIVED, NoteStatus.DRAFT) is False


class TestNoteImmutability:
    """测试笔记不可变性"""

    def test_modify_approved_note_content_should_raise_error(self):
        """测试：修改已批准笔记的内容应该抛出错误"""
        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="原始结论",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.approve_note(note, approved_by="admin_456")

        with pytest.raises(NoteImmutableError, match="approved|已批准"):
            manager.update_note_content(note, "修改后的结论")

    def test_modify_draft_note_content_should_succeed(self):
        """测试：修改草稿笔记的内容应该成功"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="原始进展",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.update_note_content(note, "修改后的进展")

        assert note.content == "修改后的进展"

    def test_modify_pending_note_content_should_succeed(self):
        """测试：修改待审批笔记的内容应该成功"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="原始阻塞",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.update_note_content(note, "修改后的阻塞")

        assert note.content == "修改后的阻塞"

    def test_add_tag_to_approved_note_should_raise_error(self):
        """测试：给已批准笔记添加标签应该抛出错误"""
        note = KnowledgeNote.create(
            type=NoteType.REFERENCE,
            content="参考",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.approve_note(note, approved_by="admin_456")

        with pytest.raises(NoteImmutableError, match="approved|已批准"):
            manager.add_tag_to_note(note, "new_tag")

    def test_create_new_version_from_approved_note_should_succeed(self):
        """测试：从已批准笔记创建新版本应该成功"""
        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="原始结论",
            owner="user_123",
            tags=["important"],
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.approve_note(note, approved_by="admin_456")

        # 创建新版本
        new_version = manager.create_new_version(note, new_content="更新后的结论")

        assert new_version.version == note.version + 1
        assert new_version.content == "更新后的结论"
        assert new_version.status == NoteStatus.DRAFT
        assert new_version.tags == note.tags  # 继承标签
        assert new_version.owner == note.owner  # 继承所有者
        assert new_version.approved_at is None  # 新版本未批准
        assert new_version.approved_by is None


class TestUserConfirmationFlow:
    """测试用户确认流程"""

    def test_submit_for_approval_should_record_submission_time(self):
        """测试：提交审批应该记录提交时间"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        before_submit = datetime.now()
        manager.submit_for_approval(note)
        after_submit = datetime.now()

        assert note.updated_at >= before_submit
        assert note.updated_at <= after_submit

    def test_approve_note_should_record_approver_and_time(self):
        """测试：批准笔记应该记录批准者和时间"""
        note = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="结论",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)

        before_approve = datetime.now()
        manager.approve_note(note, approved_by="admin_456")
        after_approve = datetime.now()

        assert note.approved_by == "admin_456"
        assert note.approved_at is not None
        assert note.approved_at >= before_approve
        assert note.approved_at <= after_approve

    def test_reject_note_should_clear_approval_info(self):
        """测试：拒绝笔记应该清除批准信息"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="阻塞",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)

        # 模拟之前有批准信息（虽然正常流程不会这样）
        note.approved_by = "someone"
        note.approved_at = datetime.now()

        manager.reject_note(note, reason="需要修改")

        # 拒绝后应该清除批准信息
        assert note.approved_by is None
        assert note.approved_at is None

    def test_get_approval_info_should_return_approval_details(self):
        """测试：获取批准信息应该返回批准详情"""
        note = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="行动",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        manager.submit_for_approval(note)
        manager.approve_note(note, approved_by="admin_456")

        approval_info = manager.get_approval_info(note)

        assert approval_info["approved"] is True
        assert approval_info["approved_by"] == "admin_456"
        assert approval_info["approved_at"] is not None
        assert isinstance(approval_info["approved_at"], datetime)

    def test_get_approval_info_for_unapproved_note_should_return_not_approved(self):
        """测试：获取未批准笔记的批准信息应该返回未批准"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        manager = NoteLifecycleManager()
        approval_info = manager.get_approval_info(note)

        assert approval_info["approved"] is False
        assert approval_info["approved_by"] is None
        assert approval_info["approved_at"] is None

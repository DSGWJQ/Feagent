"""测试 KnowledgeNote（知识笔记）- Step 4: 长期知识库治理

测试目标：
1. KnowledgeNote 应该包含 type/status/version/tags/owner 字段
2. 支持五种笔记类型：progress, conclusion, blocker, next_action, reference
3. 支持四种状态：draft, pending_user, approved, archived
4. 应该能够序列化和反序列化
5. 应该能够验证笔记的完整性
"""

from datetime import datetime

import pytest

from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteStatus,
    NoteType,
)


class TestKnowledgeNote:
    """测试 KnowledgeNote 数据结构"""

    def test_create_note_with_all_fields_should_succeed(self):
        """测试：创建包含所有字段的笔记应该成功"""
        note = KnowledgeNote(
            note_id="note_001",
            type=NoteType.PROGRESS,
            status=NoteStatus.DRAFT,
            content="项目进展：完成了用户认证模块",
            version=1,
            tags=["authentication", "backend"],
            owner="user_123",
        )

        assert note.note_id == "note_001"
        assert note.type == NoteType.PROGRESS
        assert note.status == NoteStatus.DRAFT
        assert note.content == "项目进展：完成了用户认证模块"
        assert note.version == 1
        assert note.tags == ["authentication", "backend"]
        assert note.owner == "user_123"

    def test_note_should_have_timestamp_fields(self):
        """测试：笔记应该有时间戳字段"""
        note = KnowledgeNote(
            note_id="note_001",
            type=NoteType.PROGRESS,
            status=NoteStatus.DRAFT,
            content="测试内容",
            owner="user_123",
        )

        assert hasattr(note, "created_at")
        assert hasattr(note, "updated_at")
        assert hasattr(note, "approved_at")
        assert hasattr(note, "approved_by")
        assert isinstance(note.created_at, datetime)
        assert note.approved_at is None  # 初始状态未批准
        assert note.approved_by is None

    def test_create_note_with_default_values_should_succeed(self):
        """测试：使用默认值创建笔记应该成功"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
        )

        assert note.note_id is not None
        assert note.type == NoteType.BLOCKER
        assert note.status == NoteStatus.DRAFT  # 默认状态
        assert note.version == 1  # 默认版本
        assert note.tags == []  # 默认空标签
        assert note.owner == "user_123"

    def test_note_type_should_have_five_types(self):
        """测试：NoteType 应该有五种类型"""
        types = list(NoteType)

        assert len(types) == 5
        assert NoteType.PROGRESS in types
        assert NoteType.CONCLUSION in types
        assert NoteType.BLOCKER in types
        assert NoteType.NEXT_ACTION in types
        assert NoteType.REFERENCE in types

    def test_note_status_should_have_four_statuses(self):
        """测试：NoteStatus 应该有四种状态"""
        statuses = list(NoteStatus)

        assert len(statuses) == 4
        assert NoteStatus.DRAFT in statuses
        assert NoteStatus.PENDING_USER in statuses
        assert NoteStatus.APPROVED in statuses
        assert NoteStatus.ARCHIVED in statuses

    def test_to_dict_should_return_serializable_dict(self):
        """测试：to_dict 应该返回可序列化的字典"""
        note = KnowledgeNote(
            note_id="note_001",
            type=NoteType.CONCLUSION,
            status=NoteStatus.APPROVED,
            content="结论：使用 PostgreSQL 作为主数据库",
            version=2,
            tags=["database", "architecture"],
            owner="user_123",
        )

        data = note.to_dict()

        assert data["note_id"] == "note_001"
        assert data["type"] == "conclusion"
        assert data["status"] == "approved"
        assert data["content"] == "结论：使用 PostgreSQL 作为主数据库"
        assert data["version"] == 2
        assert data["tags"] == ["database", "architecture"]
        assert data["owner"] == "user_123"
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict_should_reconstruct_note(self):
        """测试：from_dict 应该能够重建笔记"""
        data = {
            "note_id": "note_001",
            "type": "progress",
            "status": "draft",
            "content": "测试内容",
            "version": 1,
            "tags": ["test"],
            "owner": "user_123",
            "created_at": "2025-01-22T10:00:00",
            "updated_at": "2025-01-22T10:00:00",
            "approved_at": None,
            "approved_by": None,
        }

        note = KnowledgeNote.from_dict(data)

        assert note.note_id == "note_001"
        assert note.type == NoteType.PROGRESS
        assert note.status == NoteStatus.DRAFT
        assert note.content == "测试内容"
        assert note.version == 1
        assert note.tags == ["test"]
        assert note.owner == "user_123"

    def test_create_note_without_content_should_raise_error(self):
        """测试：创建笔记时缺少内容应该抛出错误"""
        with pytest.raises(ValueError, match="content|内容"):
            KnowledgeNote.create(
                type=NoteType.PROGRESS,
                content="",
                owner="user_123",
            )

    def test_create_note_without_owner_should_raise_error(self):
        """测试：创建笔记时缺少所有者应该抛出错误"""
        with pytest.raises(ValueError, match="owner|所有者"):
            KnowledgeNote.create(
                type=NoteType.PROGRESS,
                content="测试内容",
                owner="",
            )

    def test_add_tag_should_append_to_tags_list(self):
        """测试：添加标签应该追加到标签列表"""
        note = KnowledgeNote.create(
            type=NoteType.REFERENCE,
            content="参考文档",
            owner="user_123",
        )

        note.add_tag("documentation")
        note.add_tag("api")

        assert "documentation" in note.tags
        assert "api" in note.tags
        assert len(note.tags) == 2

    def test_add_duplicate_tag_should_not_duplicate(self):
        """测试：添加重复标签不应该重复"""
        note = KnowledgeNote.create(
            type=NoteType.REFERENCE,
            content="参考文档",
            owner="user_123",
            tags=["documentation"],
        )

        note.add_tag("documentation")

        assert note.tags.count("documentation") == 1

    def test_remove_tag_should_remove_from_list(self):
        """测试：移除标签应该从列表中删除"""
        note = KnowledgeNote.create(
            type=NoteType.REFERENCE,
            content="参考文档",
            owner="user_123",
            tags=["documentation", "api"],
        )

        note.remove_tag("api")

        assert "api" not in note.tags
        assert "documentation" in note.tags

    def test_has_tag_should_return_true_if_tag_exists(self):
        """测试：has_tag 应该在标签存在时返回 True"""
        note = KnowledgeNote.create(
            type=NoteType.REFERENCE,
            content="参考文档",
            owner="user_123",
            tags=["documentation"],
        )

        assert note.has_tag("documentation") is True
        assert note.has_tag("api") is False

    def test_increment_version_should_increase_version_number(self):
        """测试：增加版本号应该递增版本"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        original_version = note.version
        note.increment_version()

        assert note.version == original_version + 1

    def test_is_draft_should_return_true_for_draft_status(self):
        """测试：is_draft 应该在状态为 draft 时返回 True"""
        note = KnowledgeNote.create(
            type=NoteType.PROGRESS,
            content="进展",
            owner="user_123",
        )

        assert note.is_draft() is True

    def test_is_approved_should_return_true_for_approved_status(self):
        """测试：is_approved 应该在状态为 approved 时返回 True"""
        note = KnowledgeNote(
            note_id="note_001",
            type=NoteType.CONCLUSION,
            status=NoteStatus.APPROVED,
            content="结论",
            owner="user_123",
        )

        assert note.is_approved() is True

    def test_is_archived_should_return_true_for_archived_status(self):
        """测试：is_archived 应该在状态为 archived 时返回 True"""
        note = KnowledgeNote(
            note_id="note_001",
            type=NoteType.REFERENCE,
            status=NoteStatus.ARCHIVED,
            content="参考",
            owner="user_123",
        )

        assert note.is_archived() is True


class TestNoteTypeAndStatus:
    """测试 NoteType 和 NoteStatus 枚举"""

    def test_note_type_values_should_be_strings(self):
        """测试：NoteType 的值应该是字符串"""
        for note_type in NoteType:
            assert isinstance(note_type.value, str)

    def test_note_status_values_should_be_strings(self):
        """测试：NoteStatus 的值应该是字符串"""
        for status in NoteStatus:
            assert isinstance(status.value, str)

    def test_note_type_should_have_correct_values(self):
        """测试：NoteType 应该有正确的值"""
        assert NoteType.PROGRESS.value == "progress"
        assert NoteType.CONCLUSION.value == "conclusion"
        assert NoteType.BLOCKER.value == "blocker"
        assert NoteType.NEXT_ACTION.value == "next_action"
        assert NoteType.REFERENCE.value == "reference"

    def test_note_status_should_have_correct_values(self):
        """测试：NoteStatus 应该有正确的值"""
        assert NoteStatus.DRAFT.value == "draft"
        assert NoteStatus.PENDING_USER.value == "pending_user"
        assert NoteStatus.APPROVED.value == "approved"
        assert NoteStatus.ARCHIVED.value == "archived"

"""知识笔记生命周期管理 (KnowledgeNote Lifecycle) - Step 4: 长期知识库治理

业务定义：
- 管理笔记的生命周期状态转换
- 确保只允许合法的状态转换
- 记录用户确认流程（批准者、时间）
- 保证已批准笔记的不可变性

设计原则：
- 状态机模式：明确定义状态转换规则
- 不可变性：批准后的笔记不可修改，只能创建新版本
- 可追溯性：记录所有状态变更和批准信息
- 防御性编程：验证所有状态转换的合法性

状态转换规则：
- draft → pending_user (提交审批)
- pending_user → approved (批准)
- pending_user → draft (拒绝)
- approved → archived (归档)
"""

from datetime import datetime
from typing import Any

from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteStatus,
)


class LifecycleTransitionError(Exception):
    """生命周期转换错误"""

    pass


class NoteImmutableError(Exception):
    """笔记不可变错误（已批准的笔记不可修改）"""

    pass


class NoteLifecycleManager:
    """笔记生命周期管理器

    职责：
    - 管理笔记状态转换
    - 验证转换合法性
    - 记录批准信息
    - 保护已批准笔记的不可变性
    """

    # 状态转换规则：当前状态 → 允许的下一个状态列表
    VALID_TRANSITIONS = {
        NoteStatus.DRAFT: [NoteStatus.PENDING_USER],
        NoteStatus.PENDING_USER: [NoteStatus.APPROVED, NoteStatus.DRAFT],
        NoteStatus.APPROVED: [NoteStatus.ARCHIVED],
        NoteStatus.ARCHIVED: [],  # 归档后不能再转换
    }

    def submit_for_approval(self, note: KnowledgeNote) -> None:
        """提交审批

        将笔记从 draft 状态转换为 pending_user 状态。

        参数：
            note: 笔记实例

        异常：
            LifecycleTransitionError: 如果当前状态不允许提交审批
        """
        self._validate_transition(note.status, NoteStatus.PENDING_USER)
        note.status = NoteStatus.PENDING_USER
        note.updated_at = datetime.now()

    def approve_note(self, note: KnowledgeNote, approved_by: str) -> None:
        """批准笔记

        将笔记从 pending_user 状态转换为 approved 状态，
        并记录批准者和批准时间。

        参数：
            note: 笔记实例
            approved_by: 批准者ID

        异常：
            LifecycleTransitionError: 如果当前状态不允许批准
            ValueError: 如果批准者为空
        """
        if not approved_by or not approved_by.strip():
            raise ValueError("批准者不能为空 (approved_by cannot be empty)")

        self._validate_transition(note.status, NoteStatus.APPROVED)
        note.status = NoteStatus.APPROVED
        note.approved_by = approved_by.strip()
        note.approved_at = datetime.now()
        note.updated_at = datetime.now()

    def reject_note(self, note: KnowledgeNote, reason: str | None = None) -> None:
        """拒绝笔记

        将笔记从 pending_user 状态转换回 draft 状态，
        清除批准信息。

        参数：
            note: 笔记实例
            reason: 拒绝原因（可选）

        异常：
            LifecycleTransitionError: 如果当前状态不允许拒绝
        """
        self._validate_transition(note.status, NoteStatus.DRAFT)
        note.status = NoteStatus.DRAFT
        note.approved_by = None
        note.approved_at = None
        note.updated_at = datetime.now()

    def archive_note(self, note: KnowledgeNote) -> None:
        """归档笔记

        将笔记从 approved 状态转换为 archived 状态。

        参数：
            note: 笔记实例

        异常：
            LifecycleTransitionError: 如果当前状态不允许归档
        """
        self._validate_transition(note.status, NoteStatus.ARCHIVED)
        note.status = NoteStatus.ARCHIVED
        note.updated_at = datetime.now()

    def update_note_content(self, note: KnowledgeNote, new_content: str) -> None:
        """更新笔记内容

        只允许修改 draft 或 pending_user 状态的笔记。
        已批准的笔记不可修改。

        参数：
            note: 笔记实例
            new_content: 新内容

        异常：
            NoteImmutableError: 如果笔记已批准
        """
        if note.status == NoteStatus.APPROVED:
            raise NoteImmutableError("已批准的笔记不可修改 (approved notes are immutable)")

        if note.status == NoteStatus.ARCHIVED:
            raise NoteImmutableError("已归档的笔记不可修改 (archived notes are immutable)")

        note.content = new_content
        note.updated_at = datetime.now()

    def add_tag_to_note(self, note: KnowledgeNote, tag: str) -> None:
        """给笔记添加标签

        只允许修改 draft 或 pending_user 状态的笔记。

        参数：
            note: 笔记实例
            tag: 标签名称

        异常：
            NoteImmutableError: 如果笔记已批准
        """
        if note.status == NoteStatus.APPROVED:
            raise NoteImmutableError("已批准的笔记不可修改 (approved notes are immutable)")

        if note.status == NoteStatus.ARCHIVED:
            raise NoteImmutableError("已归档的笔记不可修改 (archived notes are immutable)")

        note.add_tag(tag)

    def create_new_version(self, note: KnowledgeNote, new_content: str) -> KnowledgeNote:
        """从已批准笔记创建新版本

        创建一个新的草稿笔记，版本号递增，继承原笔记的标签和所有者。

        参数：
            note: 原笔记实例
            new_content: 新版本的内容

        返回：
            新版本的笔记实例
        """
        new_note = KnowledgeNote.create(
            type=note.type,
            content=new_content,
            owner=note.owner,
            tags=note.tags.copy(),
            version=note.version + 1,
        )

        return new_note

    def get_approval_info(self, note: KnowledgeNote) -> dict[str, Any]:
        """获取批准信息

        参数：
            note: 笔记实例

        返回：
            包含批准信息的字典
        """
        return {
            "approved": note.is_approved(),
            "approved_by": note.approved_by,
            "approved_at": note.approved_at,
        }

    def can_transition(self, current_status: NoteStatus, target_status: NoteStatus) -> bool:
        """判断是否可以转换到目标状态

        参数：
            current_status: 当前状态
            target_status: 目标状态

        返回：
            是否可以转换
        """
        valid_targets = self.VALID_TRANSITIONS.get(current_status, [])
        return target_status in valid_targets

    def get_valid_transitions(self, current_status: NoteStatus) -> list[NoteStatus]:
        """获取当前状态允许的下一个状态列表

        参数：
            current_status: 当前状态

        返回：
            允许的下一个状态列表
        """
        return self.VALID_TRANSITIONS.get(current_status, [])

    def _validate_transition(self, current_status: NoteStatus, target_status: NoteStatus) -> None:
        """验证状态转换是否合法

        参数：
            current_status: 当前状态
            target_status: 目标状态

        异常：
            LifecycleTransitionError: 如果转换不合法
        """
        if not self.can_transition(current_status, target_status):
            raise LifecycleTransitionError(
                f"不允许从 {current_status.value} 转换到 {target_status.value} "
                f"(transition from {current_status.value} to {target_status.value} is not allowed)"
            )


# 导出
__all__ = [
    "NoteLifecycleManager",
    "LifecycleTransitionError",
    "NoteImmutableError",
]

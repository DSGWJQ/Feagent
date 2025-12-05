"""协调者知识库巡检 (CoordinatorInspector) - Step 4: 长期知识库治理

业务定义：
- 协调者定期巡检知识库中的笔记
- 将已解决的 blocker 转为 conclusion
- 归档或更新过期的 next_action 计划
- 记录所有巡检操作到审计日志

设计原则：
- 自动化：定期自动执行巡检任务
- 智能化：基于规则和关键词识别笔记状态
- 可追溯：所有操作记录到审计日志
- 可配置：支持自定义巡检规则和阈值

巡检规则：
1. Blocker 检测：
   - 内容包含"已解决"、"已修复"、"解决方案"、"完成"等关键词
   - 标签包含"resolved"
   - 转换为 conclusion 类型

2. Next Action 检测：
   - 创建时间超过 30 天（可配置）
   - 归档或提醒更新
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from src.domain.services.knowledge_audit_log import AuditLogManager
from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteStatus,
    NoteType,
)
from src.domain.services.knowledge_note_lifecycle import NoteLifecycleManager


class InspectionAction(str, Enum):
    """巡检操作类型枚举"""

    KEEP = "keep"  # 保持不变
    CONVERT_TO_CONCLUSION = "convert_to_conclusion"  # 转为结论
    ARCHIVE = "archive"  # 归档
    UPDATE = "update"  # 更新


@dataclass
class InspectionResult:
    """巡检结果

    属性：
        note_id: 笔记ID
        action: 建议的操作
        reason: 操作原因
        metadata: 额外元数据
    """

    note_id: str
    action: InspectionAction
    reason: str | None = None
    metadata: dict[str, Any] | None = None


class CoordinatorInspector:
    """协调者巡检器

    职责：
    - 巡检 blocker 笔记，识别已解决的问题
    - 巡检 next_action 笔记，识别过期计划
    - 执行巡检操作（转换、归档等）
    - 记录巡检日志
    """

    # 解决关键词列表
    RESOLUTION_KEYWORDS = [
        "已解决",
        "已修复",
        "解决方案",
        "完成",
        "已完成",
        "解决了",
        "修复了",
        "solved",
        "resolved",
        "fixed",
        "completed",
    ]

    def __init__(self, expiration_days: int = 30):
        """初始化巡检器

        参数：
            expiration_days: 计划过期天数（默认 30 天）
        """
        self.expiration_days = expiration_days

    def inspect_blocker(self, note: KnowledgeNote) -> InspectionResult:
        """巡检 blocker 笔记

        参数：
            note: blocker 笔记

        返回：
            巡检结果
        """
        if note.type != NoteType.BLOCKER:
            return InspectionResult(
                note_id=note.note_id,
                action=InspectionAction.KEEP,
                reason="不是 blocker 类型",
            )

        if self.is_blocker_resolved(note):
            return InspectionResult(
                note_id=note.note_id,
                action=InspectionAction.CONVERT_TO_CONCLUSION,
                reason="Blocker 已解决，建议转为 conclusion",
            )

        return InspectionResult(
            note_id=note.note_id,
            action=InspectionAction.KEEP,
            reason="Blocker 未解决，保持不变",
        )

    def inspect_next_action(self, note: KnowledgeNote) -> InspectionResult:
        """巡检 next_action 笔记

        参数：
            note: next_action 笔记

        返回：
            巡检结果
        """
        if note.type != NoteType.NEXT_ACTION:
            return InspectionResult(
                note_id=note.note_id,
                action=InspectionAction.KEEP,
                reason="不是 next_action 类型",
            )

        if self.is_plan_expired(note, days=self.expiration_days):
            return InspectionResult(
                note_id=note.note_id,
                action=InspectionAction.ARCHIVE,
                reason=f"计划已过期（超过 {self.expiration_days} 天），建议归档",
            )

        return InspectionResult(
            note_id=note.note_id,
            action=InspectionAction.KEEP,
            reason="计划未过期，保持不变",
        )

    def inspect_all_notes(self, notes: list[KnowledgeNote]) -> list[InspectionResult]:
        """巡检所有笔记

        参数：
            notes: 笔记列表

        返回：
            巡检结果列表
        """
        results = []

        for note in notes:
            if note.type == NoteType.BLOCKER:
                result = self.inspect_blocker(note)
            elif note.type == NoteType.NEXT_ACTION:
                result = self.inspect_next_action(note)
            else:
                result = InspectionResult(
                    note_id=note.note_id,
                    action=InspectionAction.KEEP,
                    reason=f"类型 {note.type.value} 不需要巡检",
                )

            results.append(result)

        return results

    def is_blocker_resolved(self, note: KnowledgeNote) -> bool:
        """判断 blocker 是否已解决

        参数：
            note: blocker 笔记

        返回：
            是否已解决
        """
        # 检查内容中是否包含解决关键词
        content_lower = note.content.lower()
        for keyword in self.RESOLUTION_KEYWORDS:
            if keyword.lower() in content_lower:
                return True

        # 检查标签中是否包含 "resolved"
        if note.has_tag("resolved"):
            return True

        return False

    def is_plan_expired(self, note: KnowledgeNote, days: int = 30) -> bool:
        """判断计划是否过期

        参数：
            note: next_action 笔记
            days: 过期天数阈值

        返回：
            是否过期
        """
        expiration_date = datetime.now() - timedelta(days=days)
        return note.created_at < expiration_date

    def convert_blocker_to_conclusion(self, blocker: KnowledgeNote) -> KnowledgeNote:
        """将 blocker 转为 conclusion

        参数：
            blocker: blocker 笔记

        返回：
            新的 conclusion 笔记
        """
        # 创建新的 conclusion 笔记
        conclusion_content = f"【从 Blocker 转换】{blocker.content}"

        conclusion = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content=conclusion_content,
            owner=blocker.owner,
            tags=blocker.tags.copy(),
        )

        return conclusion

    def archive_expired_plan(
        self, note: KnowledgeNote, lifecycle_manager: NoteLifecycleManager
    ) -> None:
        """归档过期计划

        参数：
            note: next_action 笔记
            lifecycle_manager: 生命周期管理器
        """
        if note.status == NoteStatus.APPROVED:
            lifecycle_manager.archive_note(note)

    def execute_inspection_actions(
        self,
        results: list[InspectionResult],
        lifecycle_manager: NoteLifecycleManager,
        audit_manager: AuditLogManager,
        notes_map: dict[str, KnowledgeNote] | None = None,
    ) -> list[KnowledgeNote]:
        """执行巡检操作

        参数：
            results: 巡检结果列表
            lifecycle_manager: 生命周期管理器
            audit_manager: 审计日志管理器
            notes_map: 笔记ID到笔记实例的映射（可选）

        返回：
            新创建的笔记列表
        """
        new_notes = []

        for result in results:
            if result.action == InspectionAction.CONVERT_TO_CONCLUSION:
                # 需要找到原始笔记来转换
                if notes_map and result.note_id in notes_map:
                    blocker = notes_map[result.note_id]
                    conclusion = self.convert_blocker_to_conclusion(blocker)
                    new_notes.append(conclusion)

                    # 记录审计日志
                    audit_manager.log_note_creation(conclusion)

            elif result.action == InspectionAction.ARCHIVE:
                # 归档操作
                if notes_map and result.note_id in notes_map:
                    note = notes_map[result.note_id]
                    if note.status == NoteStatus.APPROVED:
                        lifecycle_manager.archive_note(note)
                        audit_manager.log_note_archival(note, archived_by="coordinator")
            # KEEP 和 UPDATE 不需要立即操作

        return new_notes

    def get_inspection_summary(self, results: list[InspectionResult]) -> dict[str, Any]:
        """获取巡检摘要

        参数：
            results: 巡检结果列表

        返回：
            巡检摘要统计
        """
        summary = {
            "total_inspected": len(results),
            "actions_to_convert": 0,
            "actions_to_archive": 0,
            "actions_to_update": 0,
            "actions_to_keep": 0,
        }

        for result in results:
            if result.action == InspectionAction.CONVERT_TO_CONCLUSION:
                summary["actions_to_convert"] += 1
            elif result.action == InspectionAction.ARCHIVE:
                summary["actions_to_archive"] += 1
            elif result.action == InspectionAction.UPDATE:
                summary["actions_to_update"] += 1
            elif result.action == InspectionAction.KEEP:
                summary["actions_to_keep"] += 1

        return summary


# 导出
__all__ = [
    "CoordinatorInspector",
    "InspectionResult",
    "InspectionAction",
]

"""知识审计日志 (KnowledgeAuditLog) - Step 4: 长期知识库治理

业务定义：
- 审计日志记录所有笔记的状态变更和操作
- 记录谁在何时执行了什么操作
- 支持按笔记ID、操作类型、操作者查询
- 审计日志不可修改（只能追加）

设计原则：
- 不可变性：日志一旦创建不可修改
- 完整性：记录所有关键操作
- 可追溯性：支持完整的审计轨迹
- 可查询性：支持多维度查询

操作类型：
1. CREATED: 笔记创建
2. SUBMITTED: 提交审批
3. APPROVED: 批准
4. REJECTED: 拒绝
5. ARCHIVED: 归档
6. UPDATED: 更新（仅限草稿和待审批状态）
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from src.domain.services.knowledge_note import KnowledgeNote


class AuditAction(str, Enum):
    """审计操作类型枚举"""

    CREATED = "created"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    UPDATED = "updated"


@dataclass
class AuditLog:
    """审计日志

    属性：
        log_id: 日志唯一标识
        note_id: 笔记ID
        action: 操作类型
        actor: 操作者ID
        timestamp: 操作时间
        metadata: 额外元数据（如拒绝原因等）
    """

    log_id: str
    note_id: str
    action: AuditAction
    actor: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create(
        note_id: str,
        action: AuditAction,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> "AuditLog":
        """创建审计日志

        参数：
            note_id: 笔记ID
            action: 操作类型
            actor: 操作者ID
            metadata: 额外元数据（可选）

        返回：
            AuditLog 实例
        """
        return AuditLog(
            log_id=f"log_{uuid4().hex[:12]}",
            note_id=note_id,
            action=action,
            actor=actor,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）

        返回：
            包含所有字段的字典
        """
        return {
            "log_id": self.log_id,
            "note_id": self.note_id,
            "action": self.action.value,
            "actor": self.actor,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata.copy(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AuditLog":
        """从字典重建审计日志（用于反序列化）

        参数：
            data: 包含日志数据的字典

        返回：
            AuditLog 实例
        """
        # 解析时间戳
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        # 解析枚举
        raw_action = data.get("action")
        if isinstance(raw_action, AuditAction):
            action = raw_action
        elif isinstance(raw_action, str):
            action = AuditAction(raw_action)
        else:
            action = AuditAction.CREATED

        actor = data.get("actor") or "unknown"

        return AuditLog(
            log_id=data.get("log_id", f"log_{uuid4().hex[:12]}"),
            note_id=data.get("note_id", ""),
            action=action,
            actor=actor,
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )


class AuditLogManager:
    """审计日志管理器

    职责：
    - 记录所有笔记操作
    - 提供多维度查询
    - 生成审计报告
    - 保证日志不可变性
    """

    def __init__(self):
        """初始化审计日志管理器"""
        self._logs: list[AuditLog] = []

    def log_note_creation(self, note: KnowledgeNote) -> AuditLog:
        """记录笔记创建

        参数：
            note: 笔记实例

        返回：
            创建的审计日志
        """
        log = AuditLog.create(
            note_id=note.note_id,
            action=AuditAction.CREATED,
            actor=note.owner,
            metadata={"note_type": note.type.value},
        )
        self._logs.append(log)
        return log

    def log_note_submission(self, note: KnowledgeNote) -> AuditLog:
        """记录笔记提交审批

        参数：
            note: 笔记实例

        返回：
            创建的审计日志
        """
        log = AuditLog.create(
            note_id=note.note_id,
            action=AuditAction.SUBMITTED,
            actor=note.owner,
        )
        self._logs.append(log)
        return log

    def log_note_approval(self, note: KnowledgeNote, approved_by: str) -> AuditLog:
        """记录笔记批准

        参数：
            note: 笔记实例
            approved_by: 批准者ID

        返回：
            创建的审计日志
        """
        log = AuditLog.create(
            note_id=note.note_id,
            action=AuditAction.APPROVED,
            actor=approved_by,
        )
        self._logs.append(log)
        return log

    def log_note_rejection(
        self, note: KnowledgeNote, rejected_by: str, reason: str | None = None
    ) -> AuditLog:
        """记录笔记拒绝

        参数：
            note: 笔记实例
            rejected_by: 拒绝者ID
            reason: 拒绝原因（可选）

        返回：
            创建的审计日志
        """
        metadata = {}
        if reason:
            metadata["reason"] = reason

        log = AuditLog.create(
            note_id=note.note_id,
            action=AuditAction.REJECTED,
            actor=rejected_by,
            metadata=metadata,
        )
        self._logs.append(log)
        return log

    def log_note_archival(self, note: KnowledgeNote, archived_by: str) -> AuditLog:
        """记录笔记归档

        参数：
            note: 笔记实例
            archived_by: 归档者ID

        返回：
            创建的审计日志
        """
        log = AuditLog.create(
            note_id=note.note_id,
            action=AuditAction.ARCHIVED,
            actor=archived_by,
        )
        self._logs.append(log)
        return log

    def log_note_update(
        self, note: KnowledgeNote, updated_by: str, changes: dict[str, Any]
    ) -> AuditLog:
        """记录笔记更新

        参数：
            note: 笔记实例
            updated_by: 更新者ID
            changes: 变更内容

        返回：
            创建的审计日志
        """
        log = AuditLog.create(
            note_id=note.note_id,
            action=AuditAction.UPDATED,
            actor=updated_by,
            metadata={"changes": changes},
        )
        self._logs.append(log)
        return log

    def get_logs_by_note_id(self, note_id: str) -> list[AuditLog]:
        """按笔记ID获取日志

        参数：
            note_id: 笔记ID

        返回：
            该笔记的所有日志（按时间顺序）
        """
        return [log for log in self._logs if log.note_id == note_id]

    def get_logs_by_actor(self, actor: str) -> list[AuditLog]:
        """按操作者获取日志

        参数：
            actor: 操作者ID

        返回：
            该操作者的所有日志
        """
        return [log for log in self._logs if log.actor == actor]

    def get_logs_by_action(self, action: AuditAction) -> list[AuditLog]:
        """按操作类型获取日志

        参数：
            action: 操作类型

        返回：
            该类型的所有日志
        """
        return [log for log in self._logs if log.action == action]

    def get_logs_in_time_range(self, start_time: datetime, end_time: datetime) -> list[AuditLog]:
        """按时间范围获取日志

        参数：
            start_time: 开始时间
            end_time: 结束时间

        返回：
            时间范围内的所有日志
        """
        return [log for log in self._logs if start_time <= log.timestamp <= end_time]

    def get_approval_history(self, note_id: str) -> list[dict[str, Any]]:
        """获取批准历史

        参数：
            note_id: 笔记ID

        返回：
            批准历史列表（包含批准者和时间）
        """
        approval_logs = [
            log
            for log in self._logs
            if log.note_id == note_id and log.action == AuditAction.APPROVED
        ]

        return [
            {
                "actor": log.actor,
                "action": log.action.value,
                "timestamp": log.timestamp,
            }
            for log in approval_logs
        ]

    def get_all_logs(self) -> list[AuditLog]:
        """获取所有日志（按时间顺序）

        返回：
            所有日志列表
        """
        return sorted(self._logs, key=lambda log: log.timestamp)

    def count_logs_by_action(self) -> dict[AuditAction, int]:
        """按操作类型统计日志数量

        返回：
            操作类型到数量的映射
        """
        counts: dict[AuditAction, int] = {}
        for log in self._logs:
            counts[log.action] = counts.get(log.action, 0) + 1
        return counts

    def get_recent_logs(self, limit: int = 10) -> list[AuditLog]:
        """获取最近的日志

        参数：
            limit: 返回的日志数量（默认 10）

        返回：
            最近的日志列表（最新的在前）
        """
        sorted_logs = sorted(self._logs, key=lambda log: log.timestamp, reverse=True)
        return sorted_logs[:limit]


# 导出
__all__ = [
    "AuditLog",
    "AuditAction",
    "AuditLogManager",
]

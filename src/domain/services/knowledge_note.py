"""知识笔记 (KnowledgeNote) - Step 4: 长期知识库治理

业务定义：
- 知识笔记是知识库的基本单元
- 支持五种类型：进展、结论、阻塞、下一步行动、参考
- 支持四种状态：草稿、待用户确认、已批准、已归档
- 支持版本管理和标签分类

设计原则：
- 不可变性：批准后的笔记不可修改，只能创建新版本
- 可追溯性：记录创建者、批准者、时间戳
- 可查询性：支持按标签、版本、类型查询
- 生命周期管理：draft → pending_user → approved → archived

笔记类型：
1. progress: 进展笔记 - 记录项目进展和里程碑
2. conclusion: 结论笔记 - 记录决策结论和最终方案
3. blocker: 阻塞笔记 - 记录遇到的问题和阻塞
4. next_action: 下一步行动 - 记录待办事项和行动计划
5. reference: 参考笔记 - 记录参考资料和文档链接
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class NoteType(str, Enum):
    """笔记类型枚举"""

    PROGRESS = "progress"
    CONCLUSION = "conclusion"
    BLOCKER = "blocker"
    NEXT_ACTION = "next_action"
    REFERENCE = "reference"


class NoteStatus(str, Enum):
    """笔记状态枚举"""

    DRAFT = "draft"
    PENDING_USER = "pending_user"
    APPROVED = "approved"
    ARCHIVED = "archived"


@dataclass
class KnowledgeNote:
    """知识笔记

    属性：
        note_id: 笔记唯一标识
        type: 笔记类型
        status: 笔记状态
        content: 笔记内容
        version: 版本号
        tags: 标签列表
        owner: 所有者（创建者）
        created_at: 创建时间
        updated_at: 更新时间
        approved_at: 批准时间
        approved_by: 批准者
    """

    note_id: str
    type: NoteType
    status: NoteStatus
    content: str
    owner: str
    version: int = 1
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    approved_at: datetime | None = None
    approved_by: str | None = None

    @staticmethod
    def create(
        type: NoteType,
        content: str,
        owner: str,
        tags: list[str] | None = None,
        version: int = 1,
    ) -> "KnowledgeNote":
        """创建新笔记

        参数：
            type: 笔记类型
            content: 笔记内容
            owner: 所有者
            tags: 标签列表（可选）
            version: 版本号（默认 1）

        返回：
            KnowledgeNote 实例

        异常：
            ValueError: 如果内容或所有者为空
        """
        if not content or not content.strip():
            raise ValueError("笔记内容不能为空 (content cannot be empty)")

        if not owner or not owner.strip():
            raise ValueError("笔记所有者不能为空 (owner cannot be empty)")

        return KnowledgeNote(
            note_id=f"note_{uuid4().hex[:12]}",
            type=type,
            status=NoteStatus.DRAFT,
            content=content.strip(),
            owner=owner.strip(),
            version=version,
            tags=tags or [],
        )

    def add_tag(self, tag: str) -> None:
        """添加标签

        参数：
            tag: 标签名称
        """
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()

    def remove_tag(self, tag: str) -> None:
        """移除标签

        参数：
            tag: 标签名称
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()

    def has_tag(self, tag: str) -> bool:
        """判断是否有指定标签

        参数：
            tag: 标签名称

        返回：
            是否存在该标签
        """
        return tag in self.tags

    def increment_version(self) -> None:
        """增加版本号"""
        self.version += 1
        self.updated_at = datetime.now()

    def is_draft(self) -> bool:
        """判断是否为草稿状态

        返回：
            是否为草稿
        """
        return self.status == NoteStatus.DRAFT

    def is_approved(self) -> bool:
        """判断是否已批准

        返回：
            是否已批准
        """
        return self.status == NoteStatus.APPROVED

    def is_archived(self) -> bool:
        """判断是否已归档

        返回：
            是否已归档
        """
        return self.status == NoteStatus.ARCHIVED

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）

        返回：
            包含所有字段的字典
        """
        return {
            "note_id": self.note_id,
            "type": self.type.value,
            "status": self.status.value,
            "content": self.content,
            "version": self.version,
            "tags": self.tags.copy(),
            "owner": self.owner,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "KnowledgeNote":
        """从字典重建笔记（用于反序列化）

        参数：
            data: 包含笔记数据的字典

        返回：
            KnowledgeNote 实例
        """
        # 解析时间戳
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now()

        approved_at = data.get("approved_at")
        if isinstance(approved_at, str):
            approved_at = datetime.fromisoformat(approved_at)

        # 解析枚举
        raw_type = data.get("type")
        if isinstance(raw_type, NoteType):
            note_type = raw_type
        elif isinstance(raw_type, str):
            note_type = NoteType(raw_type)
        else:
            note_type = NoteType.PROGRESS

        raw_status = data.get("status")
        if isinstance(raw_status, NoteStatus):
            status = raw_status
        elif isinstance(raw_status, str):
            status = NoteStatus(raw_status)
        else:
            status = NoteStatus.DRAFT

        return KnowledgeNote(
            note_id=data.get("note_id", f"note_{uuid4().hex[:12]}"),
            type=note_type,
            status=status,
            content=data.get("content", ""),
            version=data.get("version", 1),
            tags=data.get("tags", []),
            owner=data.get("owner", ""),
            created_at=created_at,
            updated_at=updated_at,
            approved_at=approved_at,
            approved_by=data.get("approved_by"),
        )


# 导出
__all__ = [
    "KnowledgeNote",
    "NoteType",
    "NoteStatus",
]

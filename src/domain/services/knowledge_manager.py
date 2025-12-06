"""知识库管理器

提供知识条目的 CRUD 操作：
- Create: 创建知识条目
- Read: 读取、列表、搜索条目
- Update: 更新条目内容
- Delete: 删除条目

用法：
    manager = KnowledgeManager()

    # 创建
    entry_id = manager.create(
        title="Python 异常处理",
        content="使用 try-except 块...",
        category="programming",
        tags=["python", "exception"]
    )

    # 读取
    entry = manager.get(entry_id)
    all_entries = manager.list_all()
    results = manager.search("异常")

    # 更新
    manager.update(entry_id, content="更新后的内容")

    # 删除
    manager.delete(entry_id)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class KnowledgeEntry:
    """知识条目"""

    id: str
    title: str
    content: str
    category: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class KnowledgeManager:
    """知识库管理器

    提供知识条目的完整 CRUD 操作。
    """

    def __init__(self) -> None:
        """初始化知识库管理器"""
        self.entries: dict[str, KnowledgeEntry] = {}

    def create(
        self,
        title: str,
        content: str,
        category: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """创建知识条目

        参数：
            title: 标题
            content: 内容
            category: 类别
            tags: 标签列表（可选）
            metadata: 元数据（可选）

        返回：
            新创建条目的 ID
        """
        entry_id = f"knowledge_{uuid.uuid4().hex[:12]}"

        entry = KnowledgeEntry(
            id=entry_id,
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            metadata=metadata or {},
        )

        self.entries[entry_id] = entry
        return entry_id

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """获取知识条目

        参数：
            entry_id: 条目 ID

        返回：
            条目字典，如果不存在返回 None
        """
        entry = self.entries.get(entry_id)
        if entry is None:
            return None
        return entry.to_dict()

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有条目

        返回：
            所有条目的列表
        """
        return [entry.to_dict() for entry in self.entries.values()]

    def filter_by_category(self, category: str) -> list[dict[str, Any]]:
        """按类别过滤条目

        参数：
            category: 类别名称

        返回：
            匹配的条目列表
        """
        return [entry.to_dict() for entry in self.entries.values() if entry.category == category]

    def search(self, keyword: str) -> list[dict[str, Any]]:
        """按关键词搜索条目

        在标题、内容、标签中搜索关键词。

        参数：
            keyword: 搜索关键词

        返回：
            匹配的条目列表
        """
        results = []
        keyword_lower = keyword.lower()

        for entry in self.entries.values():
            # 在标题中搜索
            if keyword_lower in entry.title.lower():
                results.append(entry.to_dict())
                continue

            # 在内容中搜索
            if keyword_lower in entry.content.lower():
                results.append(entry.to_dict())
                continue

            # 在标签中搜索
            for tag in entry.tags:
                if keyword_lower in tag.lower():
                    results.append(entry.to_dict())
                    break

        return results

    def update(
        self,
        entry_id: str,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """更新知识条目

        只更新提供的字段，未提供的字段保持不变。

        参数：
            entry_id: 条目 ID
            title: 新标题（可选）
            content: 新内容（可选）
            category: 新类别（可选）
            tags: 新标签（可选）
            metadata: 新元数据（可选）

        返回：
            是否更新成功
        """
        entry = self.entries.get(entry_id)
        if entry is None:
            return False

        if title is not None:
            entry.title = title
        if content is not None:
            entry.content = content
        if category is not None:
            entry.category = category
        if tags is not None:
            entry.tags = tags
        if metadata is not None:
            entry.metadata = metadata

        entry.updated_at = datetime.now()
        return True

    def delete(self, entry_id: str) -> bool:
        """删除知识条目

        参数：
            entry_id: 条目 ID

        返回：
            是否删除成功
        """
        if entry_id not in self.entries:
            return False

        del self.entries[entry_id]
        return True

    def get_statistics(self) -> dict[str, Any]:
        """获取知识库统计信息

        返回：
            统计信息字典
        """
        categories: dict[str, int] = {}
        total_tags = 0

        for entry in self.entries.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1
            total_tags += len(entry.tags)

        return {
            "total_entries": len(self.entries),
            "categories": categories,
            "total_tags": total_tags,
        }

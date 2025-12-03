"""知识引用 (Knowledge Reference) - Phase 5 阶段1

业务定义：
- 知识引用表示从知识库/RAG检索到的相关知识片段
- 用于在上下文压缩时附带相关知识信息
- 支持多种来源（知识库、错误文档、目标相关文档）

设计原则：
- 纯Python实现，不依赖框架
- 支持序列化/反序列化
- 支持去重和合并
- 与 CompressedContext 集成

数据结构：
- KnowledgeReference: 单个知识引用
- KnowledgeReferences: 知识引用集合
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class KnowledgeReference:
    """知识引用

    表示从知识库检索到的一条相关知识。

    属性：
    - source_id: 来源唯一标识
    - title: 标题
    - content_preview: 内容预览（截断）
    - relevance_score: 相关度分数 (0-1)
    - document_id: 文档ID（可选）
    - chunk_id: 文档块ID（可选）
    - source_type: 来源类型（knowledge_base/error_solution/goal_related等）
    - retrieved_at: 检索时间
    - metadata: 额外元数据
    """

    source_id: str
    title: str
    content_preview: str
    relevance_score: float
    document_id: str | None = None
    chunk_id: str | None = None
    source_type: str = "unknown"
    retrieved_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典

        返回：
            字典表示
        """
        return {
            "source_id": self.source_id,
            "title": self.title,
            "content_preview": self.content_preview,
            "relevance_score": self.relevance_score,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "source_type": self.source_type,
            "retrieved_at": self.retrieved_at.isoformat()
            if isinstance(self.retrieved_at, datetime)
            else self.retrieved_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeReference":
        """从字典反序列化

        参数：
            data: 字典数据

        返回：
            KnowledgeReference 实例
        """
        retrieved_at = data.get("retrieved_at")
        if isinstance(retrieved_at, str):
            try:
                retrieved_at = datetime.fromisoformat(retrieved_at)
            except ValueError:
                retrieved_at = datetime.now()
        elif retrieved_at is None:
            retrieved_at = datetime.now()

        return cls(
            source_id=data.get("source_id", ""),
            title=data.get("title", ""),
            content_preview=data.get("content_preview", ""),
            relevance_score=data.get("relevance_score", 0.0),
            document_id=data.get("document_id"),
            chunk_id=data.get("chunk_id"),
            source_type=data.get("source_type", "unknown"),
            retrieved_at=retrieved_at,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_rag_source(cls, rag_source: dict[str, Any]) -> "KnowledgeReference":
        """从 RAG 结果创建引用

        参数：
            rag_source: RAG 来源字典，包含 document_id, title, source, relevance_score, preview

        返回：
            KnowledgeReference 实例
        """
        return cls(
            source_id=rag_source.get("document_id", ""),
            document_id=rag_source.get("document_id"),
            title=rag_source.get("title", ""),
            content_preview=rag_source.get("preview", rag_source.get("chunk_preview", "")),
            relevance_score=rag_source.get("relevance_score", 0.0),
            source_type=rag_source.get("source", "knowledge_base"),
            metadata=rag_source.get("metadata", {}),
        )

    @classmethod
    def from_error_doc(cls, error_doc: dict[str, Any]) -> "KnowledgeReference":
        """从错误文档创建引用

        参数：
            error_doc: 错误文档字典，包含 error_type, solution_title, solution_preview, confidence

        返回：
            KnowledgeReference 实例
        """
        error_type = error_doc.get("error_type", "unknown")
        return cls(
            source_id=f"error_{error_type}",
            title=error_doc.get("solution_title", ""),
            content_preview=error_doc.get("solution_preview", ""),
            relevance_score=error_doc.get("confidence", 0.0),
            source_type="error_solution",
            metadata={"error_type": error_type},
        )

    @classmethod
    def from_goal_doc(cls, goal_doc: dict[str, Any]) -> "KnowledgeReference":
        """从目标相关文档创建引用

        参数：
            goal_doc: 目标文档字典，包含 goal_keyword, related_doc_id, doc_title, preview, match_score

        返回：
            KnowledgeReference 实例
        """
        return cls(
            source_id=goal_doc.get("related_doc_id", ""),
            document_id=goal_doc.get("related_doc_id"),
            title=goal_doc.get("doc_title", ""),
            content_preview=goal_doc.get("preview", ""),
            relevance_score=goal_doc.get("match_score", 0.0),
            source_type="goal_related",
            metadata={"goal_keyword": goal_doc.get("goal_keyword", "")},
        )


class KnowledgeReferences:
    """知识引用集合

    管理多个知识引用，支持添加、过滤、去重、合并。

    使用示例：
        refs = KnowledgeReferences()
        refs.add(KnowledgeReference(...))
        top_refs = refs.get_top(3)
    """

    def __init__(self):
        """初始化空集合"""
        self._references: list[KnowledgeReference] = []

    def __len__(self) -> int:
        """返回引用数量"""
        return len(self._references)

    def is_empty(self) -> bool:
        """检查是否为空"""
        return len(self._references) == 0

    def add(self, ref: KnowledgeReference) -> None:
        """添加引用

        参数：
            ref: 知识引用
        """
        self._references.append(ref)

    def to_list(self) -> list[KnowledgeReference]:
        """转换为列表

        返回：
            引用列表
        """
        return list(self._references)

    def to_dict_list(self) -> list[dict[str, Any]]:
        """序列化为字典列表

        返回：
            字典列表
        """
        return [ref.to_dict() for ref in self._references]

    @classmethod
    def from_dict_list(cls, data: list[dict[str, Any]]) -> "KnowledgeReferences":
        """从字典列表创建集合

        参数：
            data: 字典列表

        返回：
            KnowledgeReferences 实例
        """
        refs = cls()
        for item in data:
            refs.add(KnowledgeReference.from_dict(item))
        return refs

    def get_top(self, n: int) -> list[KnowledgeReference]:
        """获取相关度最高的前N个引用

        参数：
            n: 数量

        返回：
            按相关度降序排列的引用列表
        """
        sorted_refs = sorted(self._references, key=lambda r: r.relevance_score, reverse=True)
        return sorted_refs[:n]

    def filter_by_source_type(self, source_type: str) -> list[KnowledgeReference]:
        """按来源类型过滤

        参数：
            source_type: 来源类型

        返回：
            匹配的引用列表
        """
        return [ref for ref in self._references if ref.source_type == source_type]

    def get_summary_text(self, max_refs: int = 5) -> str:
        """获取摘要文本

        参数：
            max_refs: 最大包含的引用数

        返回：
            人类可读的摘要文本
        """
        if self.is_empty():
            return "无知识引用"

        top_refs = self.get_top(max_refs)
        parts = []
        for ref in top_refs:
            score_pct = f"{ref.relevance_score * 100:.0f}%"
            parts.append(f"- {ref.title} ({score_pct})")

        return f"知识引用 ({len(self._references)} 条):\n" + "\n".join(parts)

    def deduplicate(self) -> "KnowledgeReferences":
        """去重

        按 source_id 去重，保留相关度更高的版本。

        返回：
            去重后的新集合
        """
        seen: dict[str, KnowledgeReference] = {}

        for ref in self._references:
            existing = seen.get(ref.source_id)
            if existing is None or ref.relevance_score > existing.relevance_score:
                seen[ref.source_id] = ref

        result = KnowledgeReferences()
        for ref in seen.values():
            result.add(ref)
        return result

    def merge(
        self, other: "KnowledgeReferences", deduplicate: bool = False
    ) -> "KnowledgeReferences":
        """合并两个集合

        参数：
            other: 另一个集合
            deduplicate: 是否去重

        返回：
            合并后的新集合
        """
        result = KnowledgeReferences()

        for ref in self._references:
            result.add(ref)
        for ref in other._references:
            result.add(ref)

        if deduplicate:
            return result.deduplicate()
        return result


# 导出
__all__ = [
    "KnowledgeReference",
    "KnowledgeReferences",
]

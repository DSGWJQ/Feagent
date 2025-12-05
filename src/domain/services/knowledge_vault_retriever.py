"""知识库检索器 (VaultRetriever) - Step 5: 检索与监督整合

业务定义：
- 从知识库中检索相关笔记
- 加权评分：blocker > next_action > conclusion
- 限制注入数量 ≤6 条
- 记录注入的笔记供 Coordinator 使用

设计原则：
- 相关性优先：基于查询内容计算相关性得分
- 类型加权：不同类型笔记有不同权重
- 配额管理：限制注入数量，避免上下文过载
- 可追溯性：记录所有注入操作

评分公式：
final_score = relevance_score * type_weight

类型权重：
- blocker: 3.0 (最高优先级)
- next_action: 2.0 (中等优先级)
- conclusion: 1.0 (基础优先级)
- progress: 0.8
- reference: 0.5
"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteStatus,
    NoteType,
)


@dataclass
class ScoredNote:
    """评分笔记

    属性：
        note: 笔记实例
        score: 得分（0-1之间）
        relevance_score: 相关性得分
        type_weight: 类型权重
    """

    note: KnowledgeNote
    score: float
    relevance_score: float = 0.0
    type_weight: float = 1.0


@dataclass
class RetrievalResult:
    """检索结果

    属性：
        notes: 检索到的笔记列表
        total_found: 找到的总数
        total_returned: 返回的总数
        query: 查询字符串
        metadata: 额外元数据
    """

    notes: list[KnowledgeNote]
    total_found: int
    total_returned: int
    query: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_metadata(self) -> dict[str, Any]:
        """获取元数据

        返回：
            包含检索元数据的字典
        """
        return {
            "total_found": self.total_found,
            "total_returned": self.total_returned,
            "query": self.query,
            **self.metadata,
        }


class VaultRetriever:
    """知识库检索器

    职责：
    - 从知识库中检索相关笔记
    - 计算加权得分
    - 限制注入数量
    - 提供检索结果
    """

    # 类型权重配置
    TYPE_WEIGHTS = {
        NoteType.BLOCKER: 3.0,  # 最高优先级
        NoteType.NEXT_ACTION: 2.0,  # 中等优先级
        NoteType.CONCLUSION: 1.0,  # 基础优先级
        NoteType.PROGRESS: 0.8,
        NoteType.REFERENCE: 0.5,
    }

    def __init__(self, default_max_total: int = 6):
        """初始化检索器

        参数：
            default_max_total: 默认最大注入数量
        """
        self.default_max_total = default_max_total

    def fetch(
        self,
        query: str,
        notes: list[KnowledgeNote],
        limit_per_type: int | None = None,
        max_total: int | None = None,
        only_approved: bool = False,
    ) -> RetrievalResult:
        """检索相关笔记

        参数：
            query: 查询字符串
            notes: 笔记列表
            limit_per_type: 每种类型的最大数量（可选）
            max_total: 最大总数（可选，默认 6）
            only_approved: 是否只返回已批准的笔记

        返回：
            检索结果
        """
        if max_total is None:
            max_total = self.default_max_total

        # 过滤笔记
        filtered_notes = notes
        if only_approved:
            filtered_notes = [n for n in notes if n.status == NoteStatus.APPROVED]

        # 计算得分
        scored_notes = []
        for note in filtered_notes:
            score = self.calculate_score(note, query)
            relevance_score = self._calculate_relevance(note, query)
            type_weight = self.TYPE_WEIGHTS.get(note.type, 1.0)

            scored_notes.append(
                ScoredNote(
                    note=note,
                    score=score,
                    relevance_score=relevance_score,
                    type_weight=type_weight,
                )
            )

        # 按得分降序排序
        scored_notes.sort(key=lambda x: x.score, reverse=True)

        # 应用每种类型的限制
        if limit_per_type is not None:
            scored_notes = self._apply_per_type_limit(scored_notes, limit_per_type)

        # 限制总数
        limited_notes = scored_notes[:max_total]

        # 提取笔记
        result_notes = [sn.note for sn in limited_notes]

        return RetrievalResult(
            notes=result_notes,
            total_found=len(scored_notes),
            total_returned=len(result_notes),
            query=query,
            metadata={
                "limit_per_type": limit_per_type,
                "max_total": max_total,
                "only_approved": only_approved,
            },
        )

    def calculate_score(self, note: KnowledgeNote, query: str) -> float:
        """计算笔记得分

        参数：
            note: 笔记实例
            query: 查询字符串

        返回：
            得分（0-1之间）
        """
        # 计算相关性得分
        relevance_score = self._calculate_relevance(note, query)

        # 获取类型权重
        type_weight = self.TYPE_WEIGHTS.get(note.type, 1.0)

        # 最终得分 = 相关性 * 类型权重
        # 归一化到 0-1 范围
        final_score = relevance_score * type_weight
        max_possible_score = 1.0 * max(self.TYPE_WEIGHTS.values())
        normalized_score = min(final_score / max_possible_score, 1.0)

        return normalized_score

    def _calculate_relevance(self, note: KnowledgeNote, query: str) -> float:
        """计算相关性得分

        参数：
            note: 笔记实例
            query: 查询字符串

        返回：
            相关性得分（0-1之间）
        """
        if not query:
            return 0.5  # 无查询时返回中等得分

        query_lower = query.lower()
        score = 0.0

        # 检查内容匹配
        content_lower = note.content.lower()
        if query_lower in content_lower:
            score += 0.5

        # 检查标签匹配
        for tag in note.tags:
            if query_lower in tag.lower():
                score += 0.3
                break

        # 检查部分匹配
        query_words = query_lower.split()
        for word in query_words:
            if len(word) > 2 and word in content_lower:
                score += 0.1

        # 归一化到 0-1
        return min(score, 1.0)

    def _apply_per_type_limit(self, scored_notes: list[ScoredNote], limit: int) -> list[ScoredNote]:
        """应用每种类型的限制

        参数：
            scored_notes: 评分笔记列表
            limit: 每种类型的最大数量

        返回：
            限制后的评分笔记列表
        """
        type_counts: dict[NoteType, int] = {}
        result = []

        for scored_note in scored_notes:
            note_type = scored_note.note.type
            current_count = type_counts.get(note_type, 0)

            if current_count < limit:
                result.append(scored_note)
                type_counts[note_type] = current_count + 1

        return result

    def limit_injection(
        self, notes: list[KnowledgeNote], max_total: int = 6
    ) -> list[KnowledgeNote]:
        """限制注入数量

        参数：
            notes: 笔记列表
            max_total: 最大总数

        返回：
            限制后的笔记列表
        """
        return notes[:max_total]


# 导出
__all__ = [
    "VaultRetriever",
    "ScoredNote",
    "RetrievalResult",
]

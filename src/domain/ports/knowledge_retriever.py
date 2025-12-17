"""Knowledge Retriever Port (Domain)

定义 Domain 层对"知识检索能力"的端口抽象与数据结构。
Application/Infrastructure 通过适配器实现该端口，避免 Domain 反向依赖上层实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class KnowledgeReference:
    """统一的知识引用（Domain 数据结构）"""

    source_id: str
    title: str = ""
    content_preview: str = ""
    relevance_score: float = 0.0
    document_id: str | None = None
    source_type: str | None = None


class KnowledgeRetriever(Protocol):
    """知识检索器端口（Domain Port）"""

    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[KnowledgeReference]:
        """按查询检索知识"""
        ...

    async def retrieve_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> list[KnowledgeReference]:
        """按错误类型检索解决方案"""
        ...

    async def retrieve_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> list[KnowledgeReference]:
        """按目标检索相关知识"""
        ...


# Backward-compatible alias
KnowledgeRetrieverPort = KnowledgeRetriever


class MockKnowledgeRetriever(KnowledgeRetriever):
    """Mock 知识检索器（Domain 内用于测试）"""

    def __init__(self) -> None:
        self._query_results: dict[tuple[str, str | None], list[KnowledgeReference]] = {}
        self._error_solutions: dict[str, KnowledgeReference] = {}
        self._goal_knowledge: dict[str, KnowledgeReference] = {}

    def add_mock_result(
        self,
        query: str,
        results: list[KnowledgeReference],
        workflow_id: str | None = None,
    ) -> None:
        key = (query, workflow_id)
        self._query_results[key] = results

    def add_error_solution(self, error_type: str, solution: KnowledgeReference) -> None:
        self._error_solutions[error_type] = solution

    def add_goal_knowledge(self, keyword: str, knowledge: KnowledgeReference) -> None:
        self._goal_knowledge[keyword] = knowledge

    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[KnowledgeReference]:
        key = (query, workflow_id)
        if key in self._query_results:
            return self._query_results[key][:top_k]

        if workflow_id is not None:
            key_no_wf = (query, None)
            if key_no_wf in self._query_results:
                return self._query_results[key_no_wf][:top_k]

        return []

    async def retrieve_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> list[KnowledgeReference]:
        _ = (error_message, top_k)
        if error_type in self._error_solutions:
            return [self._error_solutions[error_type]]
        return []

    async def retrieve_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> list[KnowledgeReference]:
        _ = workflow_id
        results: list[KnowledgeReference] = []
        for keyword, knowledge in self._goal_knowledge.items():
            if keyword in goal_text:
                results.append(knowledge)
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]


__all__ = [
    "KnowledgeReference",
    "KnowledgeRetriever",
    "KnowledgeRetrieverPort",
    "MockKnowledgeRetriever",
]

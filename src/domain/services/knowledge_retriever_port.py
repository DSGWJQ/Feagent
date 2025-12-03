"""知识检索器端口 (Knowledge Retriever Port) - Phase 5 阶段2

业务定义：
- 定义 Coordinator 与知识库/RAG 的接口
- 支持按查询、错误类型、目标检索知识
- 提供 Mock 实现用于测试

设计原则：
- 使用 Protocol 定义接口（依赖倒置）
- 异步方法支持高并发
- 返回统一格式的知识引用
"""

from abc import ABC, abstractmethod
from typing import Any


class KnowledgeRetrieverPort(ABC):
    """知识检索器端口

    定义 Coordinator 访问知识库的接口。
    具体实现可以是 RAG 服务、向量数据库、或其他知识源。
    """

    @abstractmethod
    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """按查询检索知识

        参数：
            query: 查询文本
            workflow_id: 工作流ID（可选，用于过滤）
            top_k: 返回结果数量

        返回：
            知识引用字典列表，每个包含:
            - source_id: 来源ID
            - title: 标题
            - content_preview: 内容预览
            - relevance_score: 相关度分数
        """
        pass

    @abstractmethod
    async def retrieve_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """按错误类型检索解决方案

        参数：
            error_type: 错误类型名称
            error_message: 错误消息（可选）
            top_k: 返回结果数量

        返回：
            错误解决方案字典列表
        """
        pass

    @abstractmethod
    async def retrieve_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """按目标检索相关知识

        参数：
            goal_text: 目标描述文本
            workflow_id: 工作流ID（可选）
            top_k: 返回结果数量

        返回：
            目标相关知识字典列表
        """
        pass


class MockKnowledgeRetriever(KnowledgeRetrieverPort):
    """Mock 知识检索器

    用于测试，支持预设检索结果。

    使用示例：
        retriever = MockKnowledgeRetriever()
        retriever.add_mock_result("查询", [{"source_id": "d1", ...}])
        results = await retriever.retrieve_by_query("查询")
    """

    def __init__(self):
        """初始化 Mock 检索器"""
        # 查询结果映射：(query, workflow_id) -> results
        self._query_results: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
        # 错误解决方案映射：error_type -> solution
        self._error_solutions: dict[str, dict[str, Any]] = {}
        # 目标知识映射：keyword -> knowledge
        self._goal_knowledge: dict[str, dict[str, Any]] = {}

    def add_mock_result(
        self,
        query: str,
        results: list[dict[str, Any]],
        workflow_id: str | None = None,
    ) -> None:
        """添加 Mock 查询结果

        参数：
            query: 查询文本
            results: 结果列表
            workflow_id: 工作流ID（可选）
        """
        key = (query, workflow_id)
        self._query_results[key] = results

    def add_error_solution(
        self,
        error_type: str,
        solution: dict[str, Any],
    ) -> None:
        """添加错误解决方案

        参数：
            error_type: 错误类型
            solution: 解决方案字典，包含 title, preview, confidence
        """
        self._error_solutions[error_type] = solution

    def add_goal_knowledge(
        self,
        keyword: str,
        knowledge: dict[str, Any],
    ) -> None:
        """添加目标相关知识

        参数：
            keyword: 关键词
            knowledge: 知识字典，包含 doc_id, title, preview, match_score
        """
        self._goal_knowledge[keyword] = knowledge

    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """按查询检索（Mock 实现）"""
        # 先尝试精确匹配
        key = (query, workflow_id)
        if key in self._query_results:
            return self._query_results[key][:top_k]

        # 尝试不限定 workflow_id 的匹配
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
    ) -> list[dict[str, Any]]:
        """按错误类型检索（Mock 实现）"""
        if error_type in self._error_solutions:
            solution = self._error_solutions[error_type]
            return [
                {
                    "source_id": f"error_{error_type}",
                    "title": solution.get("title", f"{error_type} 解决方案"),
                    "content_preview": solution.get("preview", ""),
                    "relevance_score": solution.get("confidence", 0.8),
                    "source_type": "error_solution",
                }
            ]
        return []

    async def retrieve_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """按目标检索（Mock 实现）"""
        results = []

        # 简单的关键词匹配
        for keyword, knowledge in self._goal_knowledge.items():
            if keyword in goal_text:
                results.append(
                    {
                        "source_id": knowledge.get("doc_id", f"goal_{keyword}"),
                        "document_id": knowledge.get("doc_id"),
                        "title": knowledge.get("title", ""),
                        "content_preview": knowledge.get("preview", ""),
                        "relevance_score": knowledge.get("match_score", 0.7),
                        "source_type": "goal_related",
                    }
                )

        # 按相关度排序
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return results[:top_k]


class RAGServiceAdapter(KnowledgeRetrieverPort):
    """RAG 服务适配器

    将现有的 RAGService 适配到 KnowledgeRetrieverPort 接口。

    使用示例：
        from src.application.services.rag_service import RAGService
        adapter = RAGServiceAdapter(rag_service)
        results = await adapter.retrieve_by_query("查询")
    """

    def __init__(self, rag_service: Any):
        """初始化适配器

        参数：
            rag_service: RAGService 实例
        """
        self._rag_service = rag_service

    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """通过 RAGService 检索"""
        from src.application.services.rag_service import QueryContext

        query_context = QueryContext(
            query=query,
            workflow_id=workflow_id,
            top_k=top_k,
        )

        context = await self._rag_service.retrieve_context(query_context)

        # 转换格式
        results = []
        for source in context.sources:
            results.append(
                {
                    "source_id": source.get("document_id", ""),
                    "document_id": source.get("document_id"),
                    "title": source.get("title", ""),
                    "content_preview": source.get("chunk_preview", source.get("preview", "")),
                    "relevance_score": source.get("relevance_score", 0.0),
                    "source_type": source.get("source", "knowledge_base"),
                }
            )

        return results

    async def retrieve_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """通过 RAGService 检索错误相关知识"""
        # 构建错误查询
        query = f"{error_type}"
        if error_message:
            query = f"{error_type}: {error_message}"

        return await self.retrieve_by_query(query, top_k=top_k)

    async def retrieve_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """通过 RAGService 检索目标相关知识"""
        return await self.retrieve_by_query(goal_text, workflow_id, top_k)


# 导出
__all__ = [
    "KnowledgeRetrieverPort",
    "MockKnowledgeRetriever",
    "RAGServiceAdapter",
]

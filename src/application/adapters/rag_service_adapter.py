"""RAGService Adapter - Application Adapter

适配器职责：
将 Application 层的 RAGService 适配为 Domain 层的 KnowledgeRetriever 端口。

架构位置：
    Domain (KnowledgeRetriever Port) ← Application Adapter ← RAGService (Application)

设计原则：
- 适配器模式：使得 Domain 可以通过端口调用 RAGService 而无需直接依赖
- 数据转换：将 RAGService 的返回类型转换为 Domain 的 KnowledgeReference
- 错误处理：适配器内捕获应用层异常，返回空列表或抛出 Domain 异常
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.application.services.rag_service import QueryContext
from src.domain.ports.knowledge_retriever import KnowledgeReference, KnowledgeRetriever

if TYPE_CHECKING:
    from src.application.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class RAGServiceAdapter(KnowledgeRetriever):
    """RAG服务适配器

    将 RAGService 适配为 KnowledgeRetriever 端口。

    使用示例：
        rag_service = RAGService(knowledge_repository, retriever_service)
        adapter = RAGServiceAdapter(rag_service)
        results = await adapter.retrieve_by_query("Python 异步编程", top_k=5)
    """

    def __init__(self, rag_service: RAGService) -> None:
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
    ) -> list[KnowledgeReference]:
        """按查询检索知识

        参数：
            query: 查询文本
            workflow_id: 工作流 ID（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReference 列表
        """
        try:
            # 构建查询上下文
            query_context = QueryContext(
                query=query,
                workflow_id=workflow_id,
                top_k=top_k,
                max_context_length=4000,
            )

            # 调用 RAGService 检索
            context = await self._rag_service.retrieve_context(query_context)

            # 转换为 KnowledgeReference 列表
            return self._convert_sources_to_references(context.sources)

        except Exception as e:
            logger.error(f"Failed to retrieve by query: {str(e)}")
            return []

    async def retrieve_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> list[KnowledgeReference]:
        """按错误类型检索解决方案

        策略：
        使用错误类型和错误消息构造查询文本，调用 retrieve_by_query。

        参数：
            error_type: 错误类型（如 "ValueError", "ConnectionError"）
            error_message: 错误消息（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReference 列表
        """
        # 构造查询文本：结合错误类型和错误消息
        query_parts = [f"错误类型: {error_type}"]
        if error_message:
            query_parts.append(f"错误信息: {error_message}")

        query = " ".join(query_parts)

        # 复用 retrieve_by_query
        return await self.retrieve_by_query(query=query, top_k=top_k)

    async def retrieve_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> list[KnowledgeReference]:
        """按目标检索相关知识

        策略：
        使用目标文本作为查询，调用 retrieve_by_query。

        参数：
            goal_text: 目标描述文本
            workflow_id: 工作流 ID（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReference 列表
        """
        return await self.retrieve_by_query(
            query=goal_text,
            workflow_id=workflow_id,
            top_k=top_k,
        )

    def _convert_sources_to_references(
        self, sources: list[dict[str, str | float]]
    ) -> list[KnowledgeReference]:
        """转换 RAGService 来源为 KnowledgeReference

        参数：
            sources: RAGService 返回的来源列表

        返回：
            KnowledgeReference 列表
        """
        references: list[KnowledgeReference] = []

        for source in sources:
            try:
                references.append(
                    KnowledgeReference(
                        source_id=str(source.get("document_id", "")),
                        title=str(source.get("title", "")),
                        content_preview=str(source.get("chunk_preview", "")),
                        relevance_score=float(source.get("relevance_score", 0.0)),
                        document_id=str(source.get("document_id", "")),
                        source_type=str(source.get("source", "")),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to convert source to KnowledgeReference: {str(e)}")
                continue

        return references


__all__ = ["RAGServiceAdapter"]

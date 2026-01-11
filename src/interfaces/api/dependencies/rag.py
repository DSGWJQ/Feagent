"""RAG相关依赖

提供RAG服务的初始化和依赖注入
通过 Ports and Adapters 模式解耦接口层与基础设施层

Author: Claude Code (Updated)
Date: 2025-12-17 (P1-1 Fix: Ports/Adapters Compliance)
"""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from src.application.services.rag_service import RAGService
from src.config import settings
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.domain.knowledge_base.ports.retriever_service import RetrieverService
from src.domain.ports.rag_service_port import RAGServicePort
from src.infrastructure.knowledge_base.rag_config_manager import RAGConfigManager
from src.infrastructure.knowledge_base.sqlite_knowledge_repository import SQLiteKnowledgeRepository

logger = logging.getLogger(__name__)

# 全局RAG服务实例
_rag_service: RAGService | None = None
_initialized = False


async def _create_rag_service_impl() -> RAGService:
    """创建RAG服务实现（内部工厂函数）"""
    global _rag_service, _initialized

    if not _initialized:
        logger.info("初始化RAG服务...")

        try:
            # 验证配置
            config_errors = RAGConfigManager.validate_config()
            if config_errors:
                if settings.env == "production":
                    logger.error(f"RAG配置错误: {config_errors}")
                    raise RuntimeError(f"RAG配置无效: {'; '.join(config_errors)}")
                logger.warning(
                    "RAG配置无效，已降级为 NoOpRetrieverService（非生产环境）",
                    extra={"config_errors": list(config_errors)},
                )
                RAGConfigManager.ensure_directories_exist()
                knowledge_repository = SQLiteKnowledgeRepository(
                    db_path=settings.sqlite_vector_db_path
                )
                retriever_service: RetrieverService = NoOpRetrieverService()
                _rag_service = RAGService(
                    knowledge_repository=knowledge_repository,
                    retriever_service=retriever_service,
                )
                _initialized = True
                return _rag_service

            # 确保目录存在
            RAGConfigManager.ensure_directories_exist()

            # 初始化向量存储
            if not await RAGConfigManager.initialize_vector_store():
                logger.error("向量存储初始化失败")
                raise RuntimeError("向量存储初始化失败")

            vector_config = RAGConfigManager.get_vector_store_config()
            vector_type = vector_config["type"]

            # 创建知识库仓储（目前统一使用SQLite存储元数据）
            if vector_type in {"sqlite", "chroma"}:
                db_path = (
                    vector_config.get("db_path", settings.sqlite_vector_db_path)
                    if vector_type == "sqlite"
                    else settings.sqlite_vector_db_path
                )
                knowledge_repository = SQLiteKnowledgeRepository(db_path=db_path)
            else:
                # 对于其他向量存储类型，创建相应的仓储
                # 这里可以扩展为QdrantRepository, FAISSRepository等
                raise NotImplementedError(f"暂不支持向量存储类型: {vector_type}")

            # 创建检索服务
            embedding_config = RAGConfigManager.get_embedding_config()
            if vector_type == "chroma":
                try:
                    from src.infrastructure.knowledge_base.chroma_retriever_service import (
                        ChromaRetrieverService,
                    )
                except ImportError as e:
                    raise RuntimeError(
                        "Chroma retriever not available; install with `pip install '.[rag-chroma]'`."
                    ) from e

                retriever_service: RetrieverService = ChromaRetrieverService(
                    knowledge_repository=knowledge_repository,
                    openai_api_key=embedding_config.get("api_key"),
                    model_name=embedding_config.get("model", "text-embedding-3-small"),
                    chroma_path=vector_config["path"],
                    chunk_size=settings.rag_chunk_size,
                    chunk_overlap=settings.rag_chunk_overlap,
                )
            elif vector_type == "sqlite":
                # 对于SQLite向量存储，使用SQLite仓储的自定义检索方法
                # 这里可以实现SQLiteVectorRetrieverService
                retriever_service = NoOpRetrieverService()
            else:
                retriever_service = NoOpRetrieverService()

            # 创建RAG服务
            _rag_service = RAGService(
                knowledge_repository=knowledge_repository, retriever_service=retriever_service
            )

            _initialized = True
            logger.info("RAG服务初始化成功")

        except Exception as e:
            logger.error(f"RAG服务初始化失败: {str(e)}")
            raise

        if not _rag_service:
            raise RuntimeError("RAG服务未能正确初始化")

    service = _rag_service
    if service is None:
        raise RuntimeError("RAG服务未能正确初始化")

    return service


async def get_rag_service() -> AsyncGenerator[RAGServicePort, None]:
    """
    获取RAG服务（通过端口协议）

    Returns:
        RAGServicePort 实例

    架构说明:
        Interface Layer → RAGServicePort (Domain Port)
                         ↑
                 RAGService (Application Layer)

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/api/rag/test")
        >>> async def test(rag: RAGServicePort = Depends(get_rag_service)):
        ...     stats = await rag.get_document_stats()
        ...     return stats
    """
    service = await _create_rag_service_impl()
    try:
        yield service
    finally:
        # 清理资源（如果需要）
        pass


async def check_rag_health() -> dict:
    """检查RAG系统健康状态"""
    try:
        health_status = await RAGConfigManager.health_check()

        # Normalize structure for tests/clients expecting a stable schema.
        if "timestamp" not in health_status:
            health_status["timestamp"] = datetime.now(UTC).isoformat()

        components = health_status.get("components")
        if isinstance(components, dict):
            allowed = {"healthy", "unhealthy", "configured", "missing", "error"}

            for _name, info in components.items():
                if not isinstance(info, dict):
                    continue
                status = info.get("status")
                if status in allowed:
                    continue
                if isinstance(status, str):
                    lowered = status.lower()
                    if lowered.startswith("missing"):
                        info["status"] = "missing"
                        continue
                    if lowered.startswith("config"):
                        info["status"] = "configured"
                        continue
                    if lowered in {"degraded", "warning"}:
                        info["status"] = "unhealthy"
                        continue
                info["status"] = "error"

        return health_status
    except Exception as e:
        logger.error(f"RAG健康检查失败: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(UTC).isoformat(),
        }


def is_rag_enabled() -> bool:
    """检查RAG功能是否启用"""
    return (settings.kb_global_enabled or settings.kb_per_workflow_enabled) and _initialized


def get_rag_config() -> dict:
    """获取RAG配置信息"""
    vector_store = RAGConfigManager.get_vector_store_config()
    embedding = RAGConfigManager.get_embedding_config()
    return {
        # Compatibility keys (tests/clients expect these flat fields).
        "enabled": is_rag_enabled(),
        "vector_store_type": vector_store.get("type"),
        "embedding_provider": embedding.get("provider"),
        # Health is computed via async `check_rag_health`; keep a stable placeholder here.
        "health_status": "unknown",
        # Detailed config (preferred by newer callers).
        "vector_store": vector_store,
        "embedding": embedding,
        "retrieval": RAGConfigManager.get_retrieval_config(),
        "document_processing": RAGConfigManager.get_document_processing_config(),
        "features": {
            "global_kb": settings.kb_global_enabled,
            "workflow_kb": settings.kb_per_workflow_enabled,
            "auto_indexing": settings.kb_auto_indexing,
            "cache": settings.rag_cache_enabled,
            "metrics": settings.rag_metrics_enabled,
        },
    }


class NoOpRetrieverService(RetrieverService):
    """占位检索服务，用于暂不支持的向量存储类型。"""

    async def generate_embedding(self, text: str) -> list[float]:
        return []

    async def chunk_document(
        self,
        content: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> list[str]:
        return [content]

    async def retrieve_relevant_chunks(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
        filters: dict[str, object] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        return []

    async def rerank_chunks(
        self,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        return []

    async def get_context_for_query(
        self,
        query: str,
        workflow_id: str | None = None,
        max_tokens: int = 4000,
    ) -> str:
        return ""

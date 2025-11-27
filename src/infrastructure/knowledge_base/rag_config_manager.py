"""RAG配置管理器

管理RAG相关配置和初始化
"""

import logging
from pathlib import Path

from src.config import settings
from src.infrastructure.knowledge_base.sqlite_knowledge_repository import SQLiteKnowledgeRepository

logger = logging.getLogger(__name__)


class RAGConfigManager:
    """RAG配置管理器"""

    @staticmethod
    def get_vector_store_config() -> dict:
        """获取向量存储配置"""
        config = {
            "type": settings.vector_store_type,
            "enabled": True,
        }

        if settings.vector_store_type == "sqlite":
            config.update(
                {
                    "db_path": settings.sqlite_vector_db_path,
                    "extension": settings.sqlite_vector_extension,
                }
            )
        elif settings.vector_store_type == "chroma":
            config.update(
                {
                    "path": settings.chroma_path,
                    "host": settings.chroma_host,
                    "port": settings.chroma_port,
                }
            )
        elif settings.vector_store_type in ["qdrant", "faiss"]:
            config.update(
                {
                    "url": settings.vector_store_url,
                    "api_key": settings.vector_store_api_key,
                }
            )

        return config

    @staticmethod
    def get_embedding_config() -> dict:
        """获取嵌入模型配置"""
        config = {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimension": settings.embedding_dimension,
            "batch_size": settings.embedding_batch_size,
        }

        # 根据提供商添加特定配置
        if settings.embedding_provider == "openai":
            config["api_key"] = settings.openai_api_key
            config["base_url"] = settings.openai_base_url
        # 可以添加其他提供商的配置

        return config

    @staticmethod
    def get_retrieval_config() -> dict:
        """获取检索配置"""
        return {
            "top_k": settings.rag_top_k,
            "similarity_threshold": settings.rag_similarity_threshold,
            "max_context_tokens": settings.rag_max_context_tokens,
            "chunk_size": settings.rag_chunk_size,
            "chunk_overlap": settings.rag_chunk_overlap,
        }

    @staticmethod
    def get_document_processing_config() -> dict:
        """获取文档处理配置"""
        return {
            "max_size_mb": settings.max_document_size_mb,
            "supported_types": settings.supported_document_types,
            "auto_indexing": settings.kb_auto_indexing,
        }

    @staticmethod
    def ensure_directories_exist() -> None:
        """确保必要的目录存在"""
        directories = [
            Path(settings.sqlite_vector_db_path).parent,
            Path(settings.chroma_path),
            Path("uploads"),
            Path("data"),
        ]

        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"确保目录存在: {directory}")
            except Exception as e:
                logger.error(f"创建目录失败 {directory}: {str(e)}")

    @staticmethod
    async def initialize_vector_store() -> bool:
        """初始化向量存储"""
        try:
            config = RAGConfigManager.get_vector_store_config()

            if config["type"] == "sqlite":
                # 初始化SQLite向量存储
                db_path = config["db_path"]
                repo = SQLiteKnowledgeRepository(db_path)

                # 创建必要的表（如果不存在）
                # 注意：实际的表创建应该通过alembic迁移完成

                logger.info(f"SQLite向量存储初始化成功: {db_path}")
                return True

            elif config["type"] == "chroma":
                # 初始化ChromaDB
                from chromadb.config import Settings as ChromaSettings

                chroma_settings = ChromaSettings(
                    persist_directory=config["path"],
                    anonymized_telemetry=False,
                    allow_reset=False,
                )

                # 创建测试集合来验证连接
                import chromadb

                client = chromadb.PersistentClient(path=config["path"], settings=chroma_settings)

                logger.info(f"ChromaDB初始化成功: {config['path']}")
                return True

        except Exception as e:
            logger.error(f"向量存储初始化失败: {str(e)}")
            return False

    @staticmethod
    async def health_check() -> dict:
        """RAG健康检查"""
        health = {"status": "unhealthy", "components": {}, "details": {}}

        try:
            # 检查向量存储
            vector_config = RAGConfigManager.get_vector_store_config()
            health["components"]["vector_store"] = {
                "type": vector_config["type"],
                "status": "unknown",
            }

            # 测试向量存储连接
            if vector_config["type"] == "sqlite":
                try:
                    db_path = vector_config["db_path"]
                    repo = SQLiteKnowledgeRepository(db_path)
                    # 尝试创建测试知识库
                    from src.domain.knowledge_base.entities.knowledge_base import KnowledgeBase
                    from src.domain.value_objects.knowledge_base_type import KnowledgeBaseType

                    test_kb = KnowledgeBase.create(
                        name="Health Check",
                        description="Health check knowledge base",
                        type=KnowledgeBaseType.SYSTEM,
                    )
                    await repo.save_knowledge_base(test_kb)

                    health["components"]["vector_store"]["status"] = "healthy"
                    health["components"]["vector_store"]["details"] = f"SQLite: {db_path}"
                except Exception as e:
                    health["components"]["vector_store"]["status"] = "unhealthy"
                    health["components"]["vector_store"]["error"] = str(e)

            elif vector_config["type"] == "chroma":
                try:
                    import chromadb

                    client = chromadb.PersistentClient(path=vector_config["path"])
                    # 获取或创建测试集合
                    client.get_or_create_collection("health_check")
                    health["components"]["vector_store"]["status"] = "healthy"
                    health["components"]["vector_store"]["details"] = (
                        f"ChromaDB: {vector_config['path']}"
                    )
                except Exception as e:
                    health["components"]["vector_store"]["status"] = "unhealthy"
                    health["components"]["vector_store"]["error"] = str(e)

            # 检查嵌入模型配置
            embedding_config = RAGConfigManager.get_embedding_config()
            health["components"]["embedding"] = {
                "provider": embedding_config["provider"],
                "model": embedding_config["model"],
                "status": "configured" if embedding_config.get("api_key") else "missing_api_key",
            }

            # 检查知识库功能
            health["components"]["knowledge_base"] = {
                "global_enabled": settings.kb_global_enabled,
                "per_workflow_enabled": settings.kb_per_workflow_enabled,
                "auto_indexing": settings.kb_auto_indexing,
                "status": "enabled",
            }

            # 整体健康状态
            all_healthy = all(
                comp.get("status") == "healthy"
                or comp.get("status") == "configured"
                or comp.get("status") == "enabled"
                for comp in health["components"].values()
            )
            health["status"] = "healthy" if all_healthy else "degraded"

        except Exception as e:
            health["error"] = str(e)
            logger.error(f"RAG健康检查失败: {str(e)}")

        return health

    @staticmethod
    def validate_config() -> list[str]:
        """验证RAG配置，返回错误列表"""
        errors = []

        # 检查必需的环境变量
        if settings.embedding_provider == "openai" and not settings.openai_api_key:
            errors.append("OPENAI_API_KEY 未配置，OpenAI嵌入模型需要此密钥")

        # 检查向量存储配置
        if settings.vector_store_type == "chroma":
            if not settings.chroma_path:
                errors.append("CHROMA_PATH 未配置，ChromaDB需要指定存储路径")

        elif settings.vector_store_type in ["qdrant", "faiss"]:
            if not settings.vector_store_url:
                errors.append(f"{settings.vector_store_type.upper()}_URL 未配置")

        # 检查数值范围
        if settings.rag_top_k <= 0:
            errors.append("RAG_TOP_K 必须大于0")

        if not 0 < settings.rag_similarity_threshold <= 1:
            errors.append("RAG_SIMILARITY_THRESHOLD 必须在0和1之间")

        if settings.rag_max_context_tokens <= 0:
            errors.append("RAG_MAX_CONTEXT_TOKENS 必须大于0")

        return errors

    @staticmethod
    def get_rag_env_template() -> str:
        """获取RAG环境变量模板"""
        return """
# RAG / Knowledge Base Configuration

# Vector Store Type: sqlite, chroma, qdrant, faiss
VECTOR_STORE_TYPE=sqlite

# SQLite Vector DB (for SQLite type)
SQLITE_VECTOR_DB_PATH=data/knowledge_base.db

# ChromaDB (for Chroma type)
CHROMA_PATH=data/chroma_db
CHROMA_HOST=localhost
CHROMA_PORT=8000

# External Vector Store (for Qdrant/FAISS type)
VECTOR_STORE_URL=
VECTOR_STORE_API_KEY=

# Embedding Model
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# RAG Retrieval Settings
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7
RAG_MAX_CONTEXT_TOKENS=4000
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200

# Knowledge Base Management
KB_GLOBAL_ENABLED=true
KB_PER_WORKFLOW_ENABLED=true
KB_AUTO_INDEXING=true
"""

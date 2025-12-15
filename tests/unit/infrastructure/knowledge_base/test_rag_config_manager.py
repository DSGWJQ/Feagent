"""RAGConfigManager单元测试

测试范围:
1. Config getters: vector_store, embedding, retrieval, document_processing
2. Validation: validate_config() with various error conditions
3. Directory operations: ensure_directories_exist()
4. Initialization: initialize_vector_store() for sqlite/unknown types
5. Health check: health_check() with sqlite success + missing API key degraded status

测试原则:
- 使用 monkeypatch 隔离 settings 依赖
- 使用 tmp_path + chdir 避免污染项目目录（uploads/data 等相对路径）
- SQLiteKnowledgeRepository：health_check 使用真实实例；initialize 使用 mock 验证构造参数
- Async tests use pytest.mark.asyncio

覆盖目标: 0% → 70-85% (P0 tests)
测试数量: 10 tests (P0)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import settings
from src.infrastructure.knowledge_base.rag_config_manager import RAGConfigManager

# ====================
# Helpers
# ====================


def set_settings(monkeypatch: pytest.MonkeyPatch, **kwargs) -> None:
    """批量设置 settings 字段（测试专用）"""
    for key, value in kwargs.items():
        monkeypatch.setattr(settings, key, value, raising=False)


# ====================
# Fixtures
# ====================


@pytest.fixture
def tmp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """创建临时配置（设置 tmp paths + chdir）

    Given: 使用 tmp_path 作为测试隔离目录
    When: monkeypatch settings 到可控值，并切换 CWD 到 tmp_path
    Then: 所有目录创建与相对路径都不会污染项目根目录
    """
    monkeypatch.chdir(tmp_path)

    set_settings(
        monkeypatch,
        # Vector store defaults (sqlite for most tests)
        vector_store_type="sqlite",
        sqlite_vector_db_path=str(tmp_path / "kb.db"),
        sqlite_vector_extension="sqlite-vec",
        chroma_path=str(tmp_path / "chroma_db"),
        chroma_host="localhost",
        chroma_port=8000,
        vector_store_url="http://localhost:6333",
        vector_store_api_key="",
        # Embedding defaults (valid by default; some tests override)
        embedding_provider="openai",
        openai_api_key="test-openai-key",
        openai_base_url="https://example.invalid/v1",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        embedding_batch_size=100,
        # Retrieval defaults
        rag_top_k=5,
        rag_similarity_threshold=0.7,
        rag_max_context_tokens=4000,
        rag_chunk_size=1000,
        rag_chunk_overlap=200,
        # Document processing defaults
        max_document_size_mb=50,
        supported_document_types=["pdf", "md"],
        kb_auto_indexing=True,
        # KB flags
        kb_global_enabled=True,
        kb_per_workflow_enabled=True,
    )

    yield settings


# ====================
# Tests
# ====================


class TestConfigGetters:
    """测试配置 getter 方法"""

    def test_get_vector_store_config_sqlite_returns_db_path_and_extension(self, tmp_settings):
        """测试：sqlite vector store 配置应包含 db_path 和 extension

        Given: settings.vector_store_type=sqlite
        When: 调用 get_vector_store_config()
        Then: 返回 dict 包含 type/enabled/db_path/extension
        """
        # Given
        assert settings.vector_store_type == "sqlite"

        # When
        config = RAGConfigManager.get_vector_store_config()

        # Then
        assert config["type"] == "sqlite"
        assert config["enabled"] is True
        assert config["db_path"] == settings.sqlite_vector_db_path
        assert config["extension"] == settings.sqlite_vector_extension

    def test_get_vector_store_config_chroma_returns_path_host_port(self, tmp_settings, monkeypatch):
        """测试：chroma vector store 配置应包含 path/host/port

        Given: settings.vector_store_type=chroma
        When: 调用 get_vector_store_config()
        Then: 返回 dict 包含 path/host/port
        """
        # Given
        set_settings(
            monkeypatch,
            vector_store_type="chroma",
            chroma_host="127.0.0.1",
            chroma_port=9000,
        )

        # When
        config = RAGConfigManager.get_vector_store_config()

        # Then
        assert config["type"] == "chroma"
        assert config["enabled"] is True
        assert config["path"] == settings.chroma_path
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 9000

    def test_get_embedding_config_openai_includes_api_key_and_base_url(
        self, tmp_settings, monkeypatch
    ):
        """测试：openai embedding 配置应包含 api_key 和 base_url

        Given: settings.embedding_provider=openai 且 openai_api_key/base_url 已设置
        When: 调用 get_embedding_config()
        Then: 返回 dict 包含 api_key/base_url 字段
        """
        # Given
        set_settings(
            monkeypatch,
            embedding_provider="openai",
            openai_api_key="k",
            openai_base_url="https://b",
        )

        # When
        config = RAGConfigManager.get_embedding_config()

        # Then
        assert config["provider"] == "openai"
        assert config["api_key"] == "k"
        assert config["base_url"] == "https://b"

    def test_get_retrieval_config_returns_values_from_settings(self, tmp_settings, monkeypatch):
        """测试：get_retrieval_config 应反映 settings 中的检索配置

        Given: 自定义 rag_* 配置
        When: 调用 get_retrieval_config()
        Then: 返回 dict 值应与 settings 一致
        """
        # Given
        set_settings(
            monkeypatch,
            rag_top_k=7,
            rag_similarity_threshold=0.55,
            rag_max_context_tokens=1234,
            rag_chunk_size=777,
            rag_chunk_overlap=33,
        )

        # When
        config = RAGConfigManager.get_retrieval_config()

        # Then
        assert config == {
            "top_k": 7,
            "similarity_threshold": 0.55,
            "max_context_tokens": 1234,
            "chunk_size": 777,
            "chunk_overlap": 33,
        }

    def test_get_document_processing_config_returns_values_from_settings(
        self, tmp_settings, monkeypatch
    ):
        """测试：get_document_processing_config 应反映 settings 中的文档处理配置

        Given: 自定义文档处理配置
        When: 调用 get_document_processing_config()
        Then: 返回 dict 值应与 settings 一致
        """
        # Given
        set_settings(
            monkeypatch,
            max_document_size_mb=12,
            supported_document_types=["txt", "md"],
            kb_auto_indexing=False,
        )

        # When
        config = RAGConfigManager.get_document_processing_config()

        # Then
        assert config == {
            "max_size_mb": 12,
            "supported_types": ["txt", "md"],
            "auto_indexing": False,
        }


class TestValidation:
    """测试配置验证"""

    def test_validate_config_returns_errors_for_missing_openai_key_and_invalid_numbers(
        self, tmp_settings, monkeypatch
    ):
        """测试：validate_config 应返回所有配置错误（缺少 key + 数值非法）

        Given: embedding_provider=openai 且 openai_api_key 为空，并设置非法 rag 数值
        When: 调用 validate_config()
        Then: 返回 errors 列表包含所有预期错误信息
        """
        # Given
        set_settings(
            monkeypatch,
            embedding_provider="openai",
            openai_api_key="",
            rag_top_k=0,
            rag_similarity_threshold=2.0,
            rag_max_context_tokens=0,
        )

        # When
        errors = RAGConfigManager.validate_config()

        # Then
        assert "OPENAI_API_KEY 未配置，OpenAI嵌入模型需要此密钥" in errors
        assert "RAG_TOP_K 必须大于0" in errors
        assert "RAG_SIMILARITY_THRESHOLD 必须在0和1之间" in errors
        assert "RAG_MAX_CONTEXT_TOKENS 必须大于0" in errors

    def test_validate_config_chroma_missing_path_returns_error(self, tmp_settings, monkeypatch):
        """测试：chroma vector store 缺少 path 应返回错误

        Given: vector_store_type=chroma 且 chroma_path 为空
        When: 调用 validate_config()
        Then: 返回 error 包含 CHROMA_PATH 未配置
        """
        # Given
        set_settings(
            monkeypatch,
            vector_store_type="chroma",
            chroma_path="",
        )

        # When
        errors = RAGConfigManager.validate_config()

        # Then
        assert "CHROMA_PATH 未配置，ChromaDB需要指定存储路径" in errors

    def test_validate_config_qdrant_missing_url_returns_error(self, tmp_settings, monkeypatch):
        """测试：qdrant vector store 缺少 url 应返回错误

        Given: vector_store_type=qdrant 且 vector_store_url 为空
        When: 调用 validate_config()
        Then: 返回 error 包含 QDRANT_URL 未配置
        """
        # Given
        set_settings(
            monkeypatch,
            vector_store_type="qdrant",
            vector_store_url="",
        )

        # When
        errors = RAGConfigManager.validate_config()

        # Then
        assert "QDRANT_URL 未配置" in errors

    def test_validate_config_similarity_threshold_lower_bound_returns_error(
        self, tmp_settings, monkeypatch
    ):
        """测试：similarity threshold 下界（<= 0）应返回错误

        Given: rag_similarity_threshold=0
        When: 调用 validate_config()
        Then: 返回 error 包含必须在0和1之间
        """
        # Given
        set_settings(
            monkeypatch,
            rag_similarity_threshold=0.0,
        )

        # When
        errors = RAGConfigManager.validate_config()

        # Then
        assert "RAG_SIMILARITY_THRESHOLD 必须在0和1之间" in errors


class TestDirectories:
    """测试目录创建"""

    def test_ensure_directories_exist_creates_expected_dirs_under_tmp_cwd(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：ensure_directories_exist 应在 tmp CWD 下创建必要目录

        Given: CWD 已切换到 tmp_path，并设置 sqlite/chroma 路径到 tmp_path 下
        When: 调用 ensure_directories_exist()
        Then: sqlite db 父目录、chroma 目录、uploads、data 均存在
        """
        # Given
        sqlite_db_path = tmp_path / "nested" / "kb.db"
        chroma_path = tmp_path / "nested_chroma"
        set_settings(
            monkeypatch,
            sqlite_vector_db_path=str(sqlite_db_path),
            chroma_path=str(chroma_path),
        )

        assert (tmp_path / "uploads").exists() is False
        assert (tmp_path / "data").exists() is False
        assert sqlite_db_path.parent.exists() is False
        assert chroma_path.exists() is False

        # When
        RAGConfigManager.ensure_directories_exist()

        # Then
        assert sqlite_db_path.parent.exists() is True
        assert chroma_path.exists() is True
        assert (tmp_path / "uploads").exists() is True
        assert (tmp_path / "data").exists() is True


class TestInitialization:
    """测试向量存储初始化"""

    @pytest.mark.asyncio
    async def test_initialize_vector_store_sqlite_returns_true_and_instantiates_repo(
        self, tmp_settings, monkeypatch
    ):
        """测试：sqlite 初始化应返回 True 且会构造 SQLiteKnowledgeRepository

        Given: vector_store_type=sqlite，并指定 db_path
        When: await initialize_vector_store()
        Then: 返回 True，且 SQLiteKnowledgeRepository 被以 db_path 构造
        """
        # Given
        db_path = settings.sqlite_vector_db_path
        set_settings(monkeypatch, vector_store_type="sqlite", sqlite_vector_db_path=db_path)

        # When
        with patch(
            "src.infrastructure.knowledge_base.rag_config_manager.SQLiteKnowledgeRepository"
        ) as repo_cls:
            result = await RAGConfigManager.initialize_vector_store()

        # Then
        assert result is True
        repo_cls.assert_called_once_with(db_path)

    @pytest.mark.asyncio
    async def test_initialize_vector_store_unknown_type_returns_false(
        self, tmp_settings, monkeypatch
    ):
        """测试：未知 vector store type 应返回 False

        Given: settings.vector_store_type 设置为未知值
        When: await initialize_vector_store()
        Then: 返回 False（不抛异常）
        """
        # Given
        set_settings(monkeypatch, vector_store_type="unknown")

        # When
        result = await RAGConfigManager.initialize_vector_store()

        # Then
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_vector_store_sqlite_exception_returns_false(
        self, tmp_settings, monkeypatch
    ):
        """测试：sqlite repo 构造抛异常时应返回 False

        Given: vector_store_type=sqlite，但 SQLiteKnowledgeRepository 抛异常
        When: await initialize_vector_store()
        Then: 返回 False（异常被捕获）
        """
        # Given
        set_settings(
            monkeypatch,
            vector_store_type="sqlite",
            sqlite_vector_db_path="/invalid/path.db",
        )

        # When
        with patch(
            "src.infrastructure.knowledge_base.rag_config_manager.SQLiteKnowledgeRepository",
            side_effect=RuntimeError("DB init failed"),
        ):
            result = await RAGConfigManager.initialize_vector_store()

        # Then
        assert result is False


class TestHealthCheck:
    """测试健康检查"""

    @pytest.mark.asyncio
    async def test_health_check_sqlite_marks_vector_store_healthy_and_overall_status_degraded_without_api_key(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：sqlite 健康但缺失 API key 时整体应为 degraded

        Given:
          - vector_store_type=sqlite
          - openai_api_key 为空（embedding 缺失 key）
          - sqlite db_path 指向 tmp_path 下的文件（父目录存在）
        When: await health_check()
        Then:
          - vector_store.status == healthy
          - embedding.status == missing_api_key
          - overall status == degraded
        """
        # Given
        db_path = str(tmp_path / "health.db")
        set_settings(
            monkeypatch,
            vector_store_type="sqlite",
            sqlite_vector_db_path=db_path,
            embedding_provider="openai",
            openai_api_key="",
        )

        # When
        health = await RAGConfigManager.health_check()

        # Then
        assert health["components"]["vector_store"]["type"] == "sqlite"
        assert health["components"]["vector_store"]["status"] == "healthy"
        assert "SQLite:" in health["components"]["vector_store"]["details"]

        assert health["components"]["embedding"]["provider"] == settings.embedding_provider
        assert health["components"]["embedding"]["status"] == "missing_api_key"

        assert health["components"]["knowledge_base"]["status"] == "enabled"
        assert health["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_sqlite_repo_exception_marks_vector_store_unhealthy(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：sqlite repo 初始化失败时 vector_store 应标记为 unhealthy

        Given: vector_store_type=sqlite，但 SQLiteKnowledgeRepository 抛异常
        When: await health_check()
        Then:
          - vector_store.status == unhealthy
          - vector_store.error 包含异常信息
          - overall status == unhealthy 或 degraded
        """
        # Given
        db_path = str(tmp_path / "health_fail.db")
        set_settings(
            monkeypatch,
            vector_store_type="sqlite",
            sqlite_vector_db_path=db_path,
            embedding_provider="openai",
            openai_api_key="valid-key",
        )

        # When
        with patch(
            "src.infrastructure.knowledge_base.rag_config_manager.SQLiteKnowledgeRepository",
            side_effect=RuntimeError("DB connection failed"),
        ):
            health = await RAGConfigManager.health_check()

        # Then
        assert health["components"]["vector_store"]["status"] == "unhealthy"
        assert "DB connection failed" in health["components"]["vector_store"]["error"]
        assert health["status"] in ["unhealthy", "degraded"]

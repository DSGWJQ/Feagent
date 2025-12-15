"""RAGConfigManager单元测试

测试范围:
1. Config getters: vector_store (sqlite/chroma/qdrant/faiss), embedding (openai/non-openai), retrieval, document_processing
2. Validation: validate_config() with various error conditions + valid config success path
3. Directory operations: ensure_directories_exist() + mkdir exception handling
4. Initialization: initialize_vector_store() for sqlite/chroma (success + exception paths) + unknown types
5. Health check: health_check() with sqlite/chroma (healthy/unhealthy), overall healthy status, top-level exception

测试原则:
- 使用 monkeypatch 隔离 settings 依赖
- 使用 tmp_path + chdir 避免污染项目目录（uploads/data 等相对路径）
- SQLiteKnowledgeRepository：health_check 使用真实实例；initialize 使用 mock 验证构造参数
- ChromaDB：使用 patch.dict("sys.modules") 注入 fake 模块，避免真实依赖
- Async tests use pytest.mark.asyncio

覆盖目标: 20.5% → 100.0% (P0 tests achieved)
测试数量: 29 tests (15 original + 14 new P0 tests, including 1 parametrized)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

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

    @pytest.mark.parametrize("store_type", ["qdrant", "faiss"])
    def test_get_vector_store_config_qdrant_and_faiss_returns_url_and_api_key(
        self, tmp_settings, monkeypatch, store_type: str
    ):
        """测试：qdrant/faiss vector store 配置应包含 url 和 api_key

        Given: settings.vector_store_type 为 qdrant/faiss 且配置了 vector_store_url/api_key
        When: 调用 get_vector_store_config()
        Then: 返回 dict 包含 url/api_key 字段
        """
        # Given
        set_settings(
            monkeypatch,
            vector_store_type=store_type,
            vector_store_url="http://localhost:6333",
            vector_store_api_key="k",
        )

        # When
        config = RAGConfigManager.get_vector_store_config()

        # Then
        assert config["type"] == store_type
        assert config["enabled"] is True
        assert config["url"] == "http://localhost:6333"
        assert config["api_key"] == "k"

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

    def test_get_embedding_config_non_openai_does_not_include_api_key_or_base_url(
        self, tmp_settings, monkeypatch
    ):
        """测试：非 openai provider 时 embedding 配置不应包含 api_key/base_url

        Given: settings.embedding_provider != openai（即使 openai_api_key/base_url 已设）
        When: 调用 get_embedding_config()
        Then: 返回 dict 不包含 api_key/base_url 字段
        """
        # Given
        set_settings(
            monkeypatch,
            embedding_provider="local",
            openai_api_key="should-not-be-used",
            openai_base_url="https://should-not-be-used",
            embedding_model="m",
            embedding_dimension=128,
            embedding_batch_size=7,
        )

        # When
        config = RAGConfigManager.get_embedding_config()

        # Then
        assert config["provider"] == "local"
        assert "api_key" not in config
        assert "base_url" not in config

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

    def test_validate_config_valid_config_returns_empty_list(self, tmp_settings):
        """测试：配置完全正确时 validate_config 应返回空列表

        Given: tmp_settings 提供一组合法配置（默认有效）
        When: 调用 validate_config()
        Then: 返回 []
        """
        # Given
        # tmp_settings 默认已设置为有效配置

        # When
        errors = RAGConfigManager.validate_config()

        # Then
        assert errors == []

    def test_validate_config_faiss_missing_url_returns_error(self, tmp_settings, monkeypatch):
        """测试：faiss vector store 缺少 url 应返回错误

        Given: vector_store_type=faiss 且 vector_store_url 为空
        When: 调用 validate_config()
        Then: 返回 error 包含 FAISS_URL 未配置
        """
        # Given
        set_settings(
            monkeypatch,
            vector_store_type="faiss",
            vector_store_url="",
        )

        # When
        errors = RAGConfigManager.validate_config()

        # Then
        assert "FAISS_URL 未配置" in errors


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

    def test_ensure_directories_exist_logs_error_on_mkdir_exception_and_continues(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：ensure_directories_exist 在 mkdir 失败时应记录错误并继续

        Given: Path.mkdir() 第一次调用抛出 OSError，后续调用正常
        When: 调用 ensure_directories_exist()
        Then: logger.error 被调用一次，mkdir 被调用 4 次（循环继续）
        """
        # Given
        from unittest.mock import Mock

        original_mkdir = Path.mkdir
        mkdir_call_count = 0

        def failing_mkdir(self, *args, **kwargs):
            nonlocal mkdir_call_count
            mkdir_call_count += 1
            if mkdir_call_count == 1:
                raise OSError("Permission denied")
            return original_mkdir(self, *args, **kwargs)

        mock_logger = Mock()
        monkeypatch.setattr(Path, "mkdir", failing_mkdir)
        monkeypatch.setattr(
            "src.infrastructure.knowledge_base.rag_config_manager.logger", mock_logger
        )

        # When
        RAGConfigManager.ensure_directories_exist()

        # Then
        assert mkdir_call_count == 4
        assert mock_logger.error.call_count == 1


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

    @pytest.mark.asyncio
    async def test_initialize_vector_store_chroma_returns_true_and_creates_client(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：chroma 初始化应返回 True 且会构造 PersistentClient

        Given: vector_store_type=chroma，chroma_path 指向有效路径
        When: await initialize_vector_store()
        Then: 返回 True，且 PersistentClient 被以 path/settings 构造
        """
        # Given
        from unittest.mock import Mock, patch

        chroma_path = str(tmp_path / "chroma_db")
        set_settings(
            monkeypatch,
            vector_store_type="chroma",
            chroma_path=chroma_path,
        )

        mock_settings_cls = Mock()
        mock_client_cls = Mock()
        mock_collection = Mock()
        mock_client_cls.return_value.get_or_create_collection.return_value = mock_collection

        # When
        with patch.dict(
            "sys.modules",
            {
                "chromadb": Mock(PersistentClient=mock_client_cls),
                "chromadb.config": Mock(Settings=mock_settings_cls),
            },
        ):
            result = await RAGConfigManager.initialize_vector_store()

        # Then
        assert result is True
        # 验证 Settings 被调用，且 anonymized_telemetry=False
        assert mock_settings_cls.call_count == 1
        call_kwargs = mock_settings_cls.call_args.kwargs
        assert call_kwargs["anonymized_telemetry"] is False
        # 验证 PersistentClient 被调用
        mock_client_cls.assert_called_once()
        client_kwargs = mock_client_cls.call_args.kwargs
        assert client_kwargs["path"] == chroma_path
        assert client_kwargs["settings"] == mock_settings_cls.return_value

    @pytest.mark.asyncio
    async def test_initialize_vector_store_chroma_exception_returns_false(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：chroma 初始化失败时应返回 False

        Given: vector_store_type=chroma，但 PersistentClient 抛异常
        When: await initialize_vector_store()
        Then: 返回 False（异常被捕获）
        """
        # Given
        from unittest.mock import Mock, patch

        set_settings(
            monkeypatch,
            vector_store_type="chroma",
            chroma_path=str(tmp_path / "chroma_db"),
        )

        mock_client_cls = Mock(side_effect=RuntimeError("Chroma init failed"))

        # When
        with patch.dict(
            "sys.modules",
            {
                "chromadb": Mock(PersistentClient=mock_client_cls),
                "chromadb.config": Mock(Settings=Mock()),
            },
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

    @pytest.mark.asyncio
    async def test_health_check_chroma_marks_vector_store_healthy_and_overall_status_degraded_without_api_key(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：chroma 健康但缺失 API key 时整体应为 degraded

        Given:
          - vector_store_type=chroma
          - openai_api_key 为空（embedding 缺失 key）
          - chroma_path 指向 tmp_path 下的目录
        When: await health_check()
        Then:
          - vector_store.status == healthy
          - embedding.status == missing_api_key
          - overall status == degraded
        """
        # Given
        from unittest.mock import Mock, patch

        chroma_path = str(tmp_path / "chroma_db")
        set_settings(
            monkeypatch,
            vector_store_type="chroma",
            chroma_path=chroma_path,
            embedding_provider="openai",
            openai_api_key="",
        )

        mock_collection = Mock()
        mock_collection.count.return_value = 42
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection

        # When
        with patch.dict(
            "sys.modules",
            {
                "chromadb": Mock(PersistentClient=Mock(return_value=mock_client)),
                "chromadb.config": Mock(Settings=Mock()),
            },
        ):
            health = await RAGConfigManager.health_check()

        # Then
        assert health["components"]["vector_store"]["type"] == "chroma"
        assert health["components"]["vector_store"]["status"] == "healthy"
        assert "ChromaDB:" in health["components"]["vector_store"]["details"]

        assert health["components"]["embedding"]["status"] == "missing_api_key"
        assert health["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_chroma_collection_exception_marks_vector_store_unhealthy(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：chroma collection 操作失败时 vector_store 应标记为 unhealthy

        Given: vector_store_type=chroma，但 get_or_create_collection 抛异常
        When: await health_check()
        Then:
          - vector_store.status == unhealthy
          - vector_store.error 包含异常信息
        """
        # Given
        from unittest.mock import Mock, patch

        set_settings(
            monkeypatch,
            vector_store_type="chroma",
            chroma_path=str(tmp_path / "chroma_db"),
            embedding_provider="openai",
            openai_api_key="valid-key",
        )

        mock_client = Mock()
        mock_client.get_or_create_collection.side_effect = RuntimeError("Collection error")

        # When
        with patch.dict(
            "sys.modules",
            {
                "chromadb": Mock(PersistentClient=Mock(return_value=mock_client)),
                "chromadb.config": Mock(Settings=Mock()),
            },
        ):
            health = await RAGConfigManager.health_check()

        # Then
        assert health["components"]["vector_store"]["status"] == "unhealthy"
        assert "Collection error" in health["components"]["vector_store"]["error"]

    @pytest.mark.asyncio
    async def test_health_check_overall_healthy_when_all_components_green(
        self, tmp_settings, monkeypatch, tmp_path: Path
    ):
        """测试：所有组件健康时整体状态应为 healthy

        Given:
          - vector_store_type=sqlite，健康
          - openai_api_key 已配置（embedding configured）
          - knowledge_base enabled
        When: await health_check()
        Then:
          - vector_store.status == healthy
          - embedding.status == configured
          - knowledge_base.status == enabled
          - overall status == healthy
        """
        # Given
        db_path = str(tmp_path / "healthy.db")
        set_settings(
            monkeypatch,
            vector_store_type="sqlite",
            sqlite_vector_db_path=db_path,
            embedding_provider="openai",
            openai_api_key="valid-api-key",
        )

        # When
        health = await RAGConfigManager.health_check()

        # Then
        assert health["components"]["vector_store"]["status"] == "healthy"
        assert health["components"]["embedding"]["status"] == "configured"
        assert health["components"]["knowledge_base"]["status"] == "enabled"
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_unknown_vector_store_type_returns_degraded(
        self, tmp_settings, monkeypatch
    ):
        """测试：未知 vector_store_type 应返回 degraded 状态

        Given: settings.vector_store_type 为 None（无法识别的类型）
        When: await health_check()
        Then:
          - vector_store.status == unknown
          - overall status == degraded
        """
        # Given
        monkeypatch.setattr(settings, "vector_store_type", None)

        # When
        health = await RAGConfigManager.health_check()

        # Then
        assert health["components"]["vector_store"]["status"] == "unknown"
        assert health["status"] in ["unhealthy", "degraded"]

    @pytest.mark.asyncio
    async def test_health_check_top_level_exception_returns_unhealthy_with_error(
        self, tmp_settings, monkeypatch
    ):
        """测试：health_check 顶层异常应返回 unhealthy 状态并记录错误

        Given: monkeypatch get_vector_store_config 抛出异常
        When: await health_check()
        Then:
          - overall status == unhealthy
          - health["error"] 包含异常信息
          - logger.error 被调用
        """
        # Given
        mock_logger = Mock()
        monkeypatch.setattr(
            "src.infrastructure.knowledge_base.rag_config_manager.logger", mock_logger
        )
        monkeypatch.setattr(
            RAGConfigManager,
            "get_vector_store_config",
            Mock(side_effect=RuntimeError("Config explosion")),
        )

        # When
        health = await RAGConfigManager.health_check()

        # Then
        assert health["status"] == "unhealthy"
        assert "error" in health
        assert "Config explosion" in health["error"]
        assert mock_logger.error.call_count == 1


class TestUtility:
    """测试工具方法"""

    def test_get_rag_env_template_returns_all_required_keys(self):
        """测试：get_rag_env_template 应返回完整的环境变量模板

        Given: 无前置条件
        When: 调用 get_rag_env_template()
        Then: 返回字符串包含所有必需的 RAG 配置项
        """
        # When
        template = RAGConfigManager.get_rag_env_template()

        # Then: 验证返回字符串类型
        assert isinstance(template, str)

        # Then: 验证关键配置项存在
        assert "VECTOR_STORE_TYPE" in template
        assert "EMBEDDING_PROVIDER" in template
        assert "EMBEDDING_MODEL" in template
        assert "RAG_TOP_K" in template
        assert "RAG_SIMILARITY_THRESHOLD" in template
        assert "RAG_MAX_CONTEXT_TOKENS" in template
        assert "RAG_CHUNK_SIZE" in template
        assert "KB_GLOBAL_ENABLED" in template

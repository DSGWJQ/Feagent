"""ChromaRetrieverService 单元测试（P0）

测试范围:
1. 初始化：Chroma/Embeddings/Tokenizer/Collection wiring（使用 monkeypatch 隔离外部依赖）
2. 生成向量：generate_embedding 委托调用验证
3. 文档切分：chunk_document 参数回退与 length_function wiring
4. 检索：where clause 构建、空结果处理、距离→相似度、排序、metadata 清洗与 chunk_index 兜底、错误分支
5. 重排序：跳过无 embedding 的 chunk、余弦相似度排序与 top_k 截断
6. 上下文构建：token budget 跳过逻辑、格式化输出、多 chunk 连接、全部超限处理
7. 写入/删除/更新：空输入 no-op、metadata 补全、删除两分支、删除后条件性重写入

测试原则:
- 单元测试不依赖真实 OpenAI/ChromaDB（全部 mock/fake）
- 使用 AsyncMock 覆盖 embeddings 的 async 调用
- Given/When/Then 中文说明，便于审阅与维护

覆盖目标: 20.4% → 99.1%（P0 tests）
测试数量: 22 tests（P0）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

import src.infrastructure.knowledge_base.chroma_retriever_service as chroma_mod
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.infrastructure.knowledge_base.chroma_retriever_service import ChromaRetrieverService

# ====================
# Fakes
# ====================


class FakeTokenizer:
    """确定性 tokenizer：token 数量等于文本长度（仅用于测试 token budget 行为）。"""

    def encode(self, text: str) -> list[int]:
        return list(range(len(text)))


@dataclass
class QueryCall:
    query_embeddings: list[list[float]]
    n_results: int
    where: dict[str, object] | None
    include: list[str]


class FakeCollection:
    """Fake Chroma collection：记录调用参数，并返回可配置的结果。"""

    def __init__(self) -> None:
        self.query_calls: list[QueryCall] = []
        self.add_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

        self.query_result: dict[str, object] = {}
        self.get_result: dict[str, object] = {"ids": []}

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict[str, object] | None,
        include: list[str],
    ) -> dict[str, object]:
        self.query_calls.append(
            QueryCall(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                include=include,
            )
        )
        return self.query_result

    def add(
        self,
        *,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, object]],
    ) -> None:
        self.add_calls.append(
            {
                "ids": ids,
                "documents": documents,
                "embeddings": embeddings,
                "metadatas": metadatas,
            }
        )

    def get(self, *, where: dict[str, object], include: list[str]) -> dict[str, object]:
        self.get_calls.append({"where": where, "include": include})
        return self.get_result

    def delete(self, *, ids: list[object]) -> None:
        self.delete_calls.append({"ids": ids})


class FakeSettings:
    """替代 chromadb.config.Settings，便于断言 anonymized_telemetry。"""

    def __init__(self, *, anonymized_telemetry: bool) -> None:
        self.anonymized_telemetry = anonymized_telemetry


class FakePersistentClient:
    """替代 chromadb.PersistentClient。"""

    def __init__(self, *, path: str, settings: object) -> None:
        self.path = path
        self.settings = settings
        self.created_collections: list[dict[str, object]] = []
        self._collection = FakeCollection()

    def get_or_create_collection(self, *, name: str, metadata: dict[str, object]) -> FakeCollection:
        self.created_collections.append({"name": name, "metadata": metadata})
        return self._collection


class FakeEmbeddings:
    """替代 langchain_openai.OpenAIEmbeddings。"""

    def __init__(self, *, model: str, api_key: SecretStr | None) -> None:
        self.model = model
        self.api_key = api_key
        self.aembed_query = AsyncMock(return_value=[0.01, 0.02, 0.03])


class FakeSplitter:
    """替代 RecursiveCharacterTextSplitter，记录构造参数并可控返回。"""

    def __init__(
        self,
        *,
        chunk_size: int,
        chunk_overlap: int,
        length_function,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function
        self._chunks_to_return: list[str] = []

    def split_text(self, content: str) -> list[str]:
        if self._chunks_to_return:
            return list(self._chunks_to_return)
        return [content]


# ====================
# Fixtures
# ====================


@pytest.fixture
def fake_collection() -> FakeCollection:
    return FakeCollection()


@pytest.fixture
def service(fake_collection: FakeCollection) -> ChromaRetrieverService:
    """创建不走 __init__ 的 service（隔离重依赖）"""
    svc = ChromaRetrieverService.__new__(ChromaRetrieverService)
    svc.repository = object()
    svc.model_name = "text-embedding-3-small"
    svc.chunk_size = 1000
    svc.chunk_overlap = 200
    svc.tokenizer = FakeTokenizer()
    svc.embeddings = SimpleNamespace(aembed_query=AsyncMock(return_value=[0.01, 0.02, 0.03]))
    svc.collection = fake_collection
    return svc


# ====================
# Tests: __init__
# ====================


class TestInit:
    """测试初始化 wiring（不触发真实外部依赖）。"""

    def test_init_wires_dependencies_and_collection(self, monkeypatch: pytest.MonkeyPatch):
        """测试：初始化应创建 chroma client 并 get_or_create_collection

        Given: monkeypatch 掉 OpenAIEmbeddings / encoding_for_model / PersistentClient / Settings / Splitter
        When: 构造 ChromaRetrieverService
        Then: PersistentClient 使用 path/settings；collection 使用 name/metadata
        """
        # Given
        monkeypatch.setattr(chroma_mod, "OpenAIEmbeddings", FakeEmbeddings)
        monkeypatch.setattr(chroma_mod, "encoding_for_model", lambda _model: FakeTokenizer())
        monkeypatch.setattr(chroma_mod, "Settings", FakeSettings)
        monkeypatch.setattr(chroma_mod, "RecursiveCharacterTextSplitter", FakeSplitter)
        monkeypatch.setattr(chroma_mod.chromadb, "PersistentClient", FakePersistentClient)

        # When
        svc = ChromaRetrieverService(
            knowledge_repository=object(),
            openai_api_key="explicit-key",
            model_name="text-embedding-3-small",
            chroma_path="tmp/chroma_db",
        )

        # Then
        assert isinstance(svc.chroma_client, FakePersistentClient)
        assert svc.chroma_client.path == "tmp/chroma_db"
        assert isinstance(svc.chroma_client.settings, FakeSettings)
        assert svc.chroma_client.settings.anonymized_telemetry is False
        assert svc.chroma_client.created_collections == [
            {"name": "document_chunks", "metadata": {"hnsw:space": "cosine"}}
        ]
        assert isinstance(svc.collection, FakeCollection)

    def test_init_uses_env_var_when_openai_api_key_omitted(self, monkeypatch: pytest.MonkeyPatch):
        """测试：未显式传 openai_api_key 时应读取 OPENAI_API_KEY 并传入 embeddings

        Given: OPENAI_API_KEY 已设置，且 embeddings 构造器可记录 api_key
        When: 构造 ChromaRetrieverService(openai_api_key=None)
        Then: embeddings.api_key 为 SecretStr 且值为 env key
        """
        # Given
        monkeypatch.setenv("OPENAI_API_KEY", "env-key-123")
        monkeypatch.setattr(chroma_mod, "OpenAIEmbeddings", FakeEmbeddings)
        monkeypatch.setattr(chroma_mod, "encoding_for_model", lambda _model: FakeTokenizer())
        monkeypatch.setattr(chroma_mod, "Settings", FakeSettings)
        monkeypatch.setattr(chroma_mod, "RecursiveCharacterTextSplitter", FakeSplitter)
        monkeypatch.setattr(chroma_mod.chromadb, "PersistentClient", FakePersistentClient)

        # When
        svc = ChromaRetrieverService(
            knowledge_repository=object(),
            openai_api_key=None,
            chroma_path="tmp/chroma_db",
        )

        # Then
        assert isinstance(svc.embeddings, FakeEmbeddings)
        assert isinstance(svc.embeddings.api_key, SecretStr)
        assert svc.embeddings.api_key.get_secret_value() == "env-key-123"


# ====================
# Tests: generate_embedding
# ====================


class TestGenerateEmbedding:
    """测试 embeddings 委托调用"""

    @pytest.mark.asyncio
    async def test_generate_embedding_delegates_to_embeddings_aembed_query(
        self, service: ChromaRetrieverService
    ):
        """测试：generate_embedding 应委托调用 embeddings.aembed_query

        Given: embeddings.aembed_query 为 AsyncMock
        When: 调用 generate_embedding
        Then: aembed_query 被以 text 参数调用一次
        """
        # Given
        service.embeddings.aembed_query = AsyncMock(return_value=[0.9, 0.8])

        # When
        _ = await service.generate_embedding("hello")

        # Then
        service.embeddings.aembed_query.assert_awaited_once_with("hello")

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_expected_vector(
        self, service: ChromaRetrieverService
    ):
        """测试：generate_embedding 应返回 embeddings.aembed_query 的结果

        Given: embeddings.aembed_query 返回固定向量
        When: 调用 generate_embedding
        Then: 返回值等于该向量
        """
        # Given
        expected = [0.01, 0.02, 0.03]
        service.embeddings.aembed_query = AsyncMock(return_value=expected)

        # When
        embedding = await service.generate_embedding("q")

        # Then
        assert embedding == expected


# ====================
# Tests: chunk_document
# ====================


class TestChunkDocument:
    """测试文档切分（参数回退 + length_function wiring）"""

    @pytest.mark.asyncio
    async def test_chunk_document_uses_default_params_and_wires_length_function(
        self, service: ChromaRetrieverService, monkeypatch: pytest.MonkeyPatch
    ):
        """测试：chunk_document 默认使用 self.chunk_size/self.chunk_overlap，并传入 length_function=self._count_tokens

        Given:
          - monkeypatch RecursiveCharacterTextSplitter 为可记录构造参数的 factory
          - splitter.split_text 返回固定 chunks
        When: 调用 chunk_document(content)（不传 chunk_size/overlap）
        Then:
          - splitter 使用默认 chunk_size/chunk_overlap
          - length_function 绑定到 service 的 _count_tokens
          - 返回 chunks
        """
        # Given
        created: dict[str, object] = {}

        def splitter_factory(*, chunk_size: int, chunk_overlap: int, length_function):
            s = FakeSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=length_function
            )
            s._chunks_to_return = ["c1", "c2"]
            created["splitter"] = s
            return s

        monkeypatch.setattr(chroma_mod, "RecursiveCharacterTextSplitter", splitter_factory)

        # When
        chunks = await service.chunk_document(content="hello world")

        # Then
        assert chunks == ["c1", "c2"]

        splitter = created["splitter"]
        assert isinstance(splitter, FakeSplitter)
        assert splitter.chunk_size == service.chunk_size
        assert splitter.chunk_overlap == service.chunk_overlap
        assert splitter.length_function.__self__ is service
        assert splitter.length_function.__func__ is ChromaRetrieverService._count_tokens

    @pytest.mark.asyncio
    async def test_chunk_document_uses_override_params(
        self, service: ChromaRetrieverService, monkeypatch: pytest.MonkeyPatch
    ):
        """测试：chunk_document 传入 chunk_size/chunk_overlap 时应使用覆盖值

        Given: monkeypatch RecursiveCharacterTextSplitter 为可记录构造参数的 factory
        When: 调用 chunk_document(content, chunk_size=..., chunk_overlap=...)
        Then: splitter 使用覆盖值，并返回 split_text 的结果
        """
        # Given
        created: dict[str, object] = {}

        def splitter_factory(*, chunk_size: int, chunk_overlap: int, length_function):
            s = FakeSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=length_function
            )
            s._chunks_to_return = ["only"]
            created["splitter"] = s
            return s

        monkeypatch.setattr(chroma_mod, "RecursiveCharacterTextSplitter", splitter_factory)

        # When
        chunks = await service.chunk_document(content="x", chunk_size=10, chunk_overlap=1)

        # Then
        assert chunks == ["only"]
        splitter = created["splitter"]
        assert isinstance(splitter, FakeSplitter)
        assert splitter.chunk_size == 10
        assert splitter.chunk_overlap == 1


# ====================
# Tests: retrieve_relevant_chunks
# ====================


class TestRetrieveRelevantChunks:
    """测试检索结果转换逻辑（where clause / metadata 清洗 / 排序）。"""

    @pytest.mark.asyncio
    async def test_retrieve_relevant_chunks_passes_where_none_when_no_filters(
        self, service: ChromaRetrieverService, fake_collection: FakeCollection
    ):
        """测试：无 workflow_id 且无 filters 时 where 应为 None

        Given: collection.query 可记录 where 参数，且 query_result 为空
        When: 调用 retrieve_relevant_chunks(workflow_id=None, filters=None)
        Then: collection.query(where=None)
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        fake_collection.query_result = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
            "embeddings": [[]],
        }

        # When
        result = await service.retrieve_relevant_chunks(query="q", workflow_id=None, filters=None)

        # Then
        assert result == []
        assert len(fake_collection.query_calls) == 1
        assert fake_collection.query_calls[0].where is None

    @pytest.mark.asyncio
    async def test_retrieve_relevant_chunks_merges_workflow_id_and_filters_into_where(
        self, service: ChromaRetrieverService, fake_collection: FakeCollection
    ):
        """测试：workflow_id 与 filters 应合并到 where_clause

        Given: workflow_id 与 filters 均提供
        When: 调用 retrieve_relevant_chunks
        Then: where_clause == {"workflow_id": ..., **filters}
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        fake_collection.query_result = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
            "embeddings": [[]],
        }

        # When
        _ = await service.retrieve_relevant_chunks(
            query="q",
            workflow_id="wf_1",
            filters={"source": "upload"},
        )

        # Then
        assert len(fake_collection.query_calls) == 1
        assert fake_collection.query_calls[0].where == {"workflow_id": "wf_1", "source": "upload"}

    @pytest.mark.asyncio
    async def test_retrieve_relevant_chunks_returns_empty_when_ids_empty(
        self, service: ChromaRetrieverService, fake_collection: FakeCollection
    ):
        """测试：Chroma 返回空 ids 时应返回 []

        Given: results.ids == [[]]
        When: 调用 retrieve_relevant_chunks
        Then: 返回 []
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[0.1])
        fake_collection.query_result = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
            "embeddings": [[]],
        }

        # When
        result = await service.retrieve_relevant_chunks(query="q")

        # Then
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_relevant_chunks_builds_document_chunk_with_sanitized_metadata_and_chunk_index_fallback(
        self,
        service: ChromaRetrieverService,
        fake_collection: FakeCollection,
    ):
        """测试：metadata 应过滤非标量值，chunk_index 非数值时应回退为 0

        Given:
          - metadata 包含 dict/list 等不可序列化值
          - chunk_index 为字符串 "3"
        When: 调用 retrieve_relevant_chunks
        Then:
          - chunk.chunk_index == 0（因为非 int/float）
          - chunk.metadata 不包含 dict/list 项
          - chunk.metadata 保留标量/None（包含 "chunk_index": "3" 字符串）
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[0.1])
        metadata = {
            "document_id": "doc_1",
            "chunk_index": "3",
            "ok": "x",
            "n": 1,
            "b": True,
            "none": None,
            "bad_dict": {"k": "v"},
            "bad_list": [1, 2],
        }
        fake_collection.query_result = {
            "ids": [["c1"]],
            "documents": [["hello"]],
            "metadatas": [[metadata]],
            "distances": [[0.2]],
            "embeddings": [[[0.1, 0.2, 0.3]]],
        }

        # When
        chunks_with_scores = await service.retrieve_relevant_chunks(query="q")

        # Then
        assert len(chunks_with_scores) == 1
        chunk, score = chunks_with_scores[0]
        assert chunk.document_id == "doc_1"
        assert chunk.chunk_index == 0
        assert score == pytest.approx(0.8)

        assert chunk.metadata is not None
        assert "bad_dict" not in chunk.metadata
        assert "bad_list" not in chunk.metadata
        assert chunk.metadata["ok"] == "x"
        assert chunk.metadata["n"] == 1
        assert chunk.metadata["b"] is True
        assert chunk.metadata["none"] is None
        assert chunk.metadata["chunk_index"] == "3"

    @pytest.mark.asyncio
    async def test_retrieve_relevant_chunks_converts_distance_to_similarity_and_sorts_descending(
        self,
        service: ChromaRetrieverService,
        fake_collection: FakeCollection,
    ):
        """测试：distance 应转换为 similarity=1-distance，并按 similarity 降序排序

        Given: 两条结果，distance 分别为 0.8 与 0.2（相似度分别 0.2 与 0.8）
        When: 调用 retrieve_relevant_chunks
        Then: 返回顺序应为 similarity 0.8 的在前
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[0.1])
        fake_collection.query_result = {
            "ids": [["c1", "c2"]],
            "documents": [["low_sim", "high_sim"]],
            "metadatas": [
                [
                    {"document_id": "doc_low", "chunk_index": 0},
                    {"document_id": "doc_high", "chunk_index": 1},
                ]
            ],
            "distances": [[0.8, 0.2]],
            "embeddings": [[[0.1, 0.2], [0.3, 0.4]]],
        }

        # When
        chunks_with_scores = await service.retrieve_relevant_chunks(query="q")

        # Then
        assert [score for _chunk, score in chunks_with_scores] == [
            pytest.approx(0.8),
            pytest.approx(0.2),
        ]
        assert [chunk.document_id for chunk, _score in chunks_with_scores] == [
            "doc_high",
            "doc_low",
        ]

    @pytest.mark.asyncio
    async def test_retrieve_relevant_chunks_raises_when_embeddings_missing_or_empty(
        self,
        service: ChromaRetrieverService,
        fake_collection: FakeCollection,
    ):
        """测试：当 Chroma query 未返回 embeddings 时应抛出 ValueError

        Given:
          - ids/documents/metadatas/distances 存在
          - embeddings 为空（无法构建 DocumentChunk）
        When: 调用 retrieve_relevant_chunks
        Then: 抛出 ValueError，提示 embeddings 缺失
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[0.1])
        fake_collection.query_result = {
            "ids": [["c1"]],
            "documents": [["hello"]],
            "metadatas": [[{"document_id": "doc_1", "chunk_index": 0}]],
            "distances": [[0.2]],
            "embeddings": [[]],
        }

        # When / Then
        with pytest.raises(ValueError, match="did not return embeddings"):
            await service.retrieve_relevant_chunks(query="q")


# ====================
# Tests: rerank_chunks
# ====================


class TestRerankChunks:
    """测试重排序逻辑（余弦相似度 + top_k）。"""

    @pytest.mark.asyncio
    async def test_rerank_chunks_skips_chunks_without_embedding(
        self, service: ChromaRetrieverService
    ):
        """测试：chunk.embedding 为空时应跳过

        Given: chunks 中包含 embedding=[] 与 embedding=[...] 的条目
        When: 调用 rerank_chunks
        Then: 返回仅包含有 embedding 的 chunk
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[1.0, 0.0])
        chunks = [
            DocumentChunk(
                id="c_empty",
                document_id="doc",
                content="empty",
                embedding=[],
                chunk_index=0,
                created_at=datetime(2025, 1, 1, 0, 0, 0),
                metadata={},
            ),
            DocumentChunk(
                id="c_ok",
                document_id="doc",
                content="ok",
                embedding=[1.0, 0.0],
                chunk_index=1,
                created_at=datetime(2025, 1, 1, 0, 0, 0),
                metadata={},
            ),
        ]

        # When
        ranked = await service.rerank_chunks(query="q", chunks=chunks, top_k=5)

        # Then
        assert len(ranked) == 1
        assert ranked[0][0].id == "c_ok"

    @pytest.mark.asyncio
    async def test_rerank_chunks_returns_top_k_sorted_by_cosine_similarity(
        self, service: ChromaRetrieverService
    ):
        """测试：应按余弦相似度排序并截断 top_k

        Given: query 向量为 [1,0]，chunk1=[1,0] 相似度更高，chunk2=[0,1] 更低
        When: top_k=1 调用 rerank_chunks
        Then: 只返回 chunk1
        """
        # Given
        service.generate_embedding = AsyncMock(return_value=[1.0, 0.0])
        chunk1 = DocumentChunk(
            id="c1",
            document_id="doc",
            content="c1",
            embedding=[1.0, 0.0],
            chunk_index=0,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        chunk2 = DocumentChunk(
            id="c2",
            document_id="doc",
            content="c2",
            embedding=[0.0, 1.0],
            chunk_index=1,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )

        # When
        ranked = await service.rerank_chunks(query="q", chunks=[chunk2, chunk1], top_k=1)

        # Then
        assert len(ranked) == 1
        assert ranked[0][0].id == "c1"
        assert ranked[0][1] == pytest.approx(1.0)


# ====================
# Tests: get_context_for_query
# ====================


class TestGetContextForQuery:
    """测试上下文构建（token budget + 格式化）。"""

    @pytest.mark.asyncio
    async def test_get_context_for_query_respects_token_budget_and_skips_oversized_chunks(
        self, service: ChromaRetrieverService
    ):
        """测试：超过 max_tokens 的 chunk 应被跳过

        Given:
          - retrieve_relevant_chunks 返回 [big(4 tokens), small(2 tokens)]
          - max_tokens=3
        When: 调用 get_context_for_query
        Then: 仅 small 被加入上下文，且包含固定前缀格式
        """
        # Given
        big = DocumentChunk(
            id="big",
            document_id="doc",
            content="bbbb",  # 4 tokens (FakeTokenizer: len)
            embedding=[0.1],
            chunk_index=0,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        small = DocumentChunk(
            id="small",
            document_id="doc",
            content="aa",  # 2 tokens
            embedding=[0.1],
            chunk_index=1,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        service.retrieve_relevant_chunks = AsyncMock(return_value=[(big, 0.9), (small, 0.8)])

        # When
        context = await service.get_context_for_query(query="q", workflow_id="wf", max_tokens=3)

        # Then
        assert context == "[文档片段] aa"

    @pytest.mark.asyncio
    async def test_get_context_for_query_joins_multiple_chunks_with_separator(
        self, service: ChromaRetrieverService
    ):
        """测试：多个 chunk 应使用 \\n\\n---\\n\\n 连接

        Given:
          - retrieve_relevant_chunks 返回两个可用 chunk
          - max_tokens 足够容纳两者
        When: 调用 get_context_for_query
        Then: 返回值包含两个片段并以分隔符连接
        """
        # Given
        c1 = DocumentChunk(
            id="c1",
            document_id="doc",
            content="a",
            embedding=[0.1],
            chunk_index=0,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        c2 = DocumentChunk(
            id="c2",
            document_id="doc",
            content="bb",
            embedding=[0.1],
            chunk_index=1,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        service.retrieve_relevant_chunks = AsyncMock(return_value=[(c1, 0.9), (c2, 0.8)])

        # When
        context = await service.get_context_for_query(query="q", workflow_id=None, max_tokens=10)

        # Then
        assert context == "[文档片段] a\n\n---\n\n[文档片段] bb"

    @pytest.mark.asyncio
    async def test_get_context_for_query_returns_empty_when_all_chunks_exceed_budget(
        self, service: ChromaRetrieverService
    ):
        """测试：当所有 chunk 都超过 token budget 时应返回空字符串

        Given:
          - retrieve_relevant_chunks 返回两个 chunk，但都超过 max_tokens
        When: 调用 get_context_for_query(max_tokens=3)
        Then: 返回 ""
        """
        # Given
        big1 = DocumentChunk(
            id="b1",
            document_id="doc",
            content="bbbb",  # 4 tokens (FakeTokenizer: len)
            embedding=[0.1],
            chunk_index=0,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        big2 = DocumentChunk(
            id="b2",
            document_id="doc",
            content="ccccc",  # 5 tokens
            embedding=[0.1],
            chunk_index=1,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        service.retrieve_relevant_chunks = AsyncMock(return_value=[(big1, 0.9), (big2, 0.8)])

        # When
        context = await service.get_context_for_query(query="q", workflow_id=None, max_tokens=3)

        # Then
        assert context == ""


# ====================
# Tests: add/delete/update document chunks
# ====================


class TestPersistenceOperations:
    """测试与 collection 的交互（add/get/delete + update orchestration）。"""

    @pytest.mark.asyncio
    async def test_add_document_chunks_noops_on_empty_list(
        self, service: ChromaRetrieverService, fake_collection: FakeCollection
    ):
        """测试：add_document_chunks([]) 应直接返回且不调用 collection.add

        Given: 空 chunks 列表
        When: 调用 add_document_chunks
        Then: collection.add_calls 仍为空
        """
        # Given / When
        await service.add_document_chunks([])

        # Then
        assert fake_collection.add_calls == []

    @pytest.mark.asyncio
    async def test_add_document_chunks_calls_collection_add_and_enriches_metadata(
        self, service: ChromaRetrieverService, fake_collection: FakeCollection
    ):
        """测试：add_document_chunks 应调用 collection.add，并补全 metadata 字段（含 token_count）

        Given:
          - 两个 DocumentChunk，包含基础 metadata
          - FakeTokenizer: token_count == len(content)
        When: 调用 add_document_chunks
        Then:
          - collection.add 被调用一次
          - ids/documents/embeddings 正确
          - metadatas 包含 document_id/chunk_index/created_at/token_count 且 token_count 正确
        """
        # Given
        chunks = [
            DocumentChunk(
                id="c1",
                document_id="doc1",
                content="abcd",  # 4 tokens (FakeTokenizer: len)
                embedding=[0.1, 0.2],
                chunk_index=0,
                created_at=datetime(2025, 1, 1, 0, 0, 0),
                metadata={"source": "upload"},
            ),
            DocumentChunk(
                id="c2",
                document_id="doc2",
                content="xy",  # 2 tokens
                embedding=[0.3, 0.4],
                chunk_index=1,
                created_at=datetime(2025, 1, 2, 0, 0, 0),
                metadata={},
            ),
        ]

        # When
        await service.add_document_chunks(chunks)

        # Then
        assert len(fake_collection.add_calls) == 1
        call = fake_collection.add_calls[0]
        assert call["ids"] == ["c1", "c2"]
        assert call["documents"] == ["abcd", "xy"]
        assert call["embeddings"] == [[0.1, 0.2], [0.3, 0.4]]

        metadatas = call["metadatas"]
        assert isinstance(metadatas, list)
        assert len(metadatas) == 2

        m1 = metadatas[0]
        assert m1["source"] == "upload"
        assert m1["document_id"] == "doc1"
        assert m1["chunk_index"] == 0
        assert m1["created_at"] == "2025-01-01T00:00:00"
        assert m1["token_count"] == 4

        m2 = metadatas[1]
        assert m2["document_id"] == "doc2"
        assert m2["chunk_index"] == 1
        assert m2["created_at"] == "2025-01-02T00:00:00"
        assert m2["token_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_document_chunks_noops_when_get_returns_no_ids(
        self, service: ChromaRetrieverService, fake_collection: FakeCollection
    ):
        """测试：delete_document_chunks 在 get 返回无 ids 时不应调用 delete

        Given: collection.get_result.ids 为空
        When: 调用 delete_document_chunks
        Then: 不调用 collection.delete
        """
        # Given
        fake_collection.get_result = {"ids": []}

        # When
        await service.delete_document_chunks("doc_x")

        # Then
        assert fake_collection.get_calls == [
            {"where": {"document_id": "doc_x"}, "include": ["metadatas"]}
        ]
        assert fake_collection.delete_calls == []

    @pytest.mark.asyncio
    async def test_delete_document_chunks_calls_delete_when_ids_exist(
        self, service: ChromaRetrieverService, fake_collection: FakeCollection
    ):
        """测试：delete_document_chunks 在 get 返回 ids 时应调用 delete

        Given: collection.get_result.ids 为非空列表
        When: 调用 delete_document_chunks
        Then: collection.delete(ids=...) 被调用一次
        """
        # Given
        fake_collection.get_result = {"ids": ["c1", "c2"]}

        # When
        await service.delete_document_chunks("doc_1")

        # Then
        assert fake_collection.get_calls == [
            {"where": {"document_id": "doc_1"}, "include": ["metadatas"]}
        ]
        assert fake_collection.delete_calls == [{"ids": ["c1", "c2"]}]

    @pytest.mark.asyncio
    async def test_update_document_chunk_deletes_then_conditionally_readds_based_on_embedding(
        self, service: ChromaRetrieverService
    ):
        """测试：update_document_chunk 应先 delete，再根据 embedding 是否存在决定是否 add

        Given:
          - chunk_a.embedding=[]
          - chunk_b.embedding=[...]
        When: 分别调用 update_document_chunk
        Then:
          - 两次均调用 delete_document_chunks
          - 仅 chunk_b 触发 add_document_chunks
        """
        # Given
        service.delete_document_chunks = AsyncMock()
        service.add_document_chunks = AsyncMock()

        chunk_a = DocumentChunk(
            id="a",
            document_id="doc_a",
            content="a",
            embedding=[],
            chunk_index=0,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )
        chunk_b = DocumentChunk(
            id="b",
            document_id="doc_b",
            content="b",
            embedding=[0.1],
            chunk_index=0,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            metadata={},
        )

        # When
        await service.update_document_chunk(chunk_a)
        await service.update_document_chunk(chunk_b)

        # Then
        assert service.delete_document_chunks.await_count == 2
        service.delete_document_chunks.assert_any_await("doc_a")
        service.delete_document_chunks.assert_any_await("doc_b")

        assert service.add_document_chunks.await_count == 1
        service.add_document_chunks.assert_awaited_with([chunk_b])

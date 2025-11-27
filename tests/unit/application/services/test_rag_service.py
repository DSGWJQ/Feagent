"""RAG Service unit tests"""

from unittest.mock import AsyncMock

import pytest

from src.application.services.rag_service import QueryContext, RAGService, RetrievedContext
from src.domain.knowledge_base.entities.document import Document
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.domain.knowledge_base.ports.knowledge_repository import KnowledgeRepository
from src.domain.knowledge_base.ports.retriever_service import RetrieverService
from src.domain.value_objects.document_source import DocumentSource


class TestRAGService:
    """RAG服务单元测试"""

    @pytest.fixture
    def mock_repository(self):
        """模拟知识库仓储"""
        repo = AsyncMock(spec=KnowledgeRepository)
        return repo

    @pytest.fixture
    def mock_retriever(self):
        """模拟检索服务"""
        retriever = AsyncMock(spec=RetrieverService)
        return retriever

    @pytest.fixture
    def rag_service(self, mock_repository, mock_retriever):
        """RAG服务实例"""
        return RAGService(knowledge_repository=mock_repository, retriever_service=mock_retriever)

    @pytest.fixture
    def sample_document(self):
        """示例文档"""
        return Document.create(
            title="AI基础",
            content="人工智能是计算机科学的一个分支，它致力于创建能够执行通常需要人类智能的任务的系统。",
            source=DocumentSource.UPLOAD,
            workflow_id="test_workflow",
        )

    @pytest.fixture
    def sample_chunks(self):
        """示例文档块"""
        chunk1 = DocumentChunk.create(
            document_id="doc1",
            content="人工智能是计算机科学的一个分支",
            embedding=[0.1] * 10,
            chunk_index=0,
        )
        chunk2 = DocumentChunk.create(
            document_id="doc1",
            content="它致力于创建能够执行通常需要人类智能的任务的系统",
            embedding=[0.2] * 10,
            chunk_index=1,
        )
        return [chunk1, chunk2]

    @pytest.mark.asyncio
    async def test_ingest_document_should_succeed(
        self, rag_service, mock_repository, mock_retriever, sample_document
    ):
        """测试���摄入文档应该成功"""
        # Arrange
        doc_id = "test_doc_123"

        # Mock the chunking and embedding generation
        mock_retriever.chunk_document.return_value = ["chunk1", "chunk2"]
        mock_retriever.generate_embedding.side_effect = [[0.1] * 10, [0.2] * 10]

        # Mock repository save
        mock_repository.save_document.return_value = None
        mock_retriever.add_document_chunks.return_value = None

        # Act
        result = await rag_service.ingest_document(
            title=sample_document.title,
            content=sample_document.content,
            source=sample_document.source,
            workflow_id=sample_document.workflow_id,
        )

        # Assert
        assert result is not None
        assert isinstance(result, str)

        # Verify repository was called
        mock_repository.save_document.assert_called_once()

        # Verify retriever was called for chunking and embedding
        mock_retriever.chunk_document.assert_called_once_with(sample_document.content)
        assert mock_retriever.generate_embedding.call_count == 2
        mock_retriever.add_document_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_context_should_return_formatted_context(
        self, rag_service, mock_retriever, sample_chunks
    ):
        """测试：检索上下文应该返回格式化上下文"""
        # Arrange
        query_context = QueryContext(
            query="什么是AI", workflow_id="test_workflow", max_context_length=1000, top_k=5
        )

        # Mock retriever to return sample chunks with scores
        mock_chunks_with_scores = [(chunk, 0.9) for chunk in sample_chunks]
        mock_retriever.retrieve_relevant_chunks.return_value = mock_chunks_with_scores

        # Mock repository for document lookup
        mock_repository.find_document_by_id.return_value = Document.create(
            title="AI文档", content="完整内容", source=DocumentSource.UPLOAD
        )

        # Act
        result = await rag_service.retrieve_context(query_context)

        # Assert
        assert isinstance(result, RetrievedContext)
        assert len(result.chunks) == 2
        assert result.query == query_context.query
        assert len(result.sources) == 2
        assert result.total_tokens > 0
        assert result.formatted_context is not None
        assert "人工智能" in result.formatted_context

    @pytest.mark.asyncio
    async def test_retrieve_context_with_no_results_should_return_empty(
        self, rag_service, mock_retriever
    ):
        """测试：检索无结果时应该返回空上下文"""
        # Arrange
        query_context = QueryContext(
            query="不存在的主题", workflow_id="test_workflow", max_context_length=1000, top_k=5
        )

        # Mock retriever to return no results
        mock_retriever.retrieve_relevant_chunks.return_value = []

        # Act
        result = await rag_service.retrieve_context(query_context)

        # Assert
        assert isinstance(result, RetrievedContext)
        assert len(result.chunks) == 0
        assert len(result.sources) == 0
        assert result.total_tokens == 0
        assert result.formatted_context == ""

    @pytest.mark.asyncio
    async def test_search_documents_should_return_documents(self, rag_service, mock_repository):
        """测试：搜索文档应该返回文档列表"""
        # Arrange
        workflow_id = "test_workflow"
        query = "AI"
        limit = 10
        threshold = 0.7

        sample_doc1 = Document.create(
            title="AI基础",
            content="人工智能介绍",
            source=DocumentSource.UPLOAD,
            workflow_id=workflow_id,
        )
        sample_doc2 = Document.create(
            title="机器学习",
            content="机器学习基础",
            source=DocumentSource.WEB,
            workflow_id=workflow_id,
        )

        mock_repository.find_documents_by_workflow_id.return_value = [sample_doc1, sample_doc2]

        # Act
        result = await rag_service.search_documents(query, workflow_id, limit, threshold)

        # Assert
        assert len(result) == 2
        assert result[0].title == "AI基础"
        assert result[1].title == "机器学习"

        # Verify repository was called correctly
        mock_repository.find_documents_by_workflow_id.assert_called_once_with(workflow_id)

    @pytest.mark.asyncio
    async def test_delete_document_should_remove_from_both_stores(
        self, rag_service, mock_repository, mock_retriever
    ):
        """测试：删除文档应该从两个存储中都删除"""
        # Arrange
        document_id = "test_doc_123"

        mock_repository.delete_document.return_value = None
        mock_retriever.delete_document_chunks.return_value = None

        # Act
        result = await rag_service.delete_document(document_id)

        # Assert
        assert result is True

        # Verify both repositories were called
        mock_repository.delete_document.assert_called_once_with(document_id)
        mock_retriever.delete_document_chunks.assert_called_once_with(document_id)

    @pytest.mark.asyncio
    async def test_get_document_stats_should_return_correct_stats(
        self, rag_service, mock_repository
    ):
        """测试：获取文档统计应该返回正确统计信息"""
        # Arrange
        workflow_id = "test_workflow"

        mock_repository.count_documents_by_workflow.return_value = 5

        # Act
        result = await rag_service.get_document_stats(workflow_id)

        # Assert
        assert result["total_documents"] == 5
        assert result["workflow_id"] == workflow_id

        # Verify repository was called
        mock_repository.count_documents_by_workflow.assert_called_once_with(workflow_id)

    @pytest.mark.asyncio
    async def test_ingest_document_with_error_should_handle_gracefully(
        self, rag_service, mock_repository
    ):
        """测试：摄入文档出错应该优雅处理"""
        # Arrange
        mock_repository.save_document.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            await rag_service.ingest_document(
                title="测试文档", content="测试内容", source=DocumentSource.UPLOAD
            )

    def test_query_context_validation(self):
        """测试：QueryContext验证"""
        # Valid context should not raise exception
        valid_context = QueryContext(
            query="测试查询", workflow_id="test_workflow", max_context_length=1000, top_k=5
        )
        assert valid_context.query == "测试查询"
        assert valid_context.workflow_id == "test_workflow"

        # Test default values
        default_context = QueryContext(query="测试")
        assert default_context.max_context_length == 4000
        assert default_context.top_k == 5

    def test_retrieved_context_creation(self, sample_chunks):
        """测试：RetrievedContext创建"""
        sources = [
            {
                "document_id": chunk.document_id,
                "title": "测试文档",
                "source": "upload",
                "relevance_score": 0.9,
                "chunk_preview": chunk.content[:50],
            }
            for chunk in sample_chunks
        ]

        context = RetrievedContext(
            query="测试查询",
            chunks=sample_chunks,
            formatted_context="格式化上下文",
            sources=sources,
            total_tokens=100,
        )

        assert context.query == "测试查询"
        assert len(context.chunks) == 2
        assert context.formatted_context == "格式化上下文"
        assert len(context.sources) == 2
        assert context.total_tokens == 100

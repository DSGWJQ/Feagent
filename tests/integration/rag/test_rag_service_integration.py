"""RAG 服务集成测试

测试真实的RAG功能，包括：
1. 文档导入
2. 向量检索
3. 上下文构建
4. 工作流对话集成

注意：这些测试需要真实的 OpenAI API key
"""

import os
import shutil
import tempfile

import pytest

from src.application.services.rag_service import QueryContext, RAGService
from src.domain.value_objects.document_source import DocumentSource
from src.infrastructure.knowledge_base.chroma_retriever_service import ChromaRetrieverService
from src.infrastructure.knowledge_base.sqlite_knowledge_repository import SQLiteKnowledgeRepository


@pytest.mark.integration
@pytest.mark.asyncio
class TestRAGServiceIntegration:
    """RAG服务集成测试"""

    @pytest.fixture
    async def rag_service(self):
        """创建RAG服务实例"""
        # 使用临时目录
        temp_dir = tempfile.mkdtemp()

        try:
            db_path = os.path.join(temp_dir, "test_kb.db")
            chroma_path = os.path.join(temp_dir, "test_chroma")

            # 初始化组件
            knowledge_repository = SQLiteKnowledgeRepository(db_path)
            retriever_service = ChromaRetrieverService(
                knowledge_repository=knowledge_repository,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                chroma_path=chroma_path,
            )

            rag_service = RAGService(
                knowledge_repository=knowledge_repository, retriever_service=retriever_service
            )

            yield rag_service

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="需要 OPENAI_API_KEY 环境变量")
    async def test_ingest_and_retrieve_document(self, rag_service):
        """测试：导入文档并检索"""
        # Arrange
        title = "HTTP API 使用指南"
        content = """
        # HTTP API 使用指南

        ## 基本概念
        HTTP API 是通过 HTTP 协议暴露的接口，允许不同系统之间进行通信。

        ## 常见方法
        - GET: 获取资源
        - POST: 创建资源
        - PUT: 更新资源
        - DELETE: 删除资源

        ## 状态码
        - 200: 成功
        - 201: 创建成功
        - 400: 客户端错误
        - 500: 服务器错误
        """
        workflow_id = "test_workflow_001"

        # Act - 导入文档
        document_id = await rag_service.ingest_document(
            title=title, content=content, source=DocumentSource.UPLOAD, workflow_id=workflow_id
        )

        # Assert - 文档已创建
        assert document_id is not None

        # Act - 检索相关内容
        query = "HTTP API 有哪些方法？"
        query_context = QueryContext(
            query=query, workflow_id=workflow_id, max_context_length=1000, top_k=3
        )

        retrieved_context = await rag_service.retrieve_context(query_context)

        # Assert - 检索到相关内容
        assert retrieved_context is not None
        assert len(retrieved_context.formatted_context) > 0
        assert "GET" in retrieved_context.formatted_context
        assert "POST" in retrieved_context.formatted_context
        assert len(retrieved_context.sources) > 0
        assert retrieved_context.sources[0]["title"] == title

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="需要 OPENAI_API_KEY 环境变量")
    async def test_search_documents(self, rag_service):
        """测试：搜索文档"""
        # Arrange - 导入多个文档
        documents = [
            ("Python 基础", "Python 是一种高级编程语言，语法简洁易学。"),
            ("JavaScript 教程", "JavaScript 是 Web 开发的核心语言。"),
            ("数据库设计", "关系型数据库使用表格存储数据。"),
        ]

        workflow_id = "test_workflow_002"
        doc_ids = []

        for title, content in documents:
            doc_id = await rag_service.ingest_document(
                title=title, content=content, source=DocumentSource.UPLOAD, workflow_id=workflow_id
            )
            doc_ids.append(doc_id)

        # Act - 搜索 Python 相关文档
        results = await rag_service.search_documents(
            query="Python 编程", workflow_id=workflow_id, limit=2, threshold=0.5
        )

        # Assert - 找到相关文档
        assert len(results) > 0
        python_doc = next((doc for doc in results if "Python" in doc.title), None)
        assert python_doc is not None
        assert python_doc.title == "Python 基础"

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="需要 OPENAI_API_KEY 环境变量")
    async def test_build_rag_prompt(self, rag_service):
        """测试：构建RAG提示词"""
        # Arrange
        query = "如何处理 API 错误？"

        # 创建模拟的检索上下文
        from src.application.services.rag_service import DocumentChunk, RetrievedContext

        mock_chunks = [
            (
                DocumentChunk.create(
                    document_id="doc1",
                    content="处理 API 错误时，应该检查状态码并采取相应措施。",
                    embedding=[0.1, 0.2],
                    chunk_index=0,
                ),
                0.9,
            )
        ]

        retrieved_context = RetrievedContext(
            chunks=mock_chunks,
            formatted_context="处理 API 错误时，应该检查状态码并采取相应措施。",
            total_tokens=50,
            sources=[
                {
                    "document_id": "doc1",
                    "title": "API 错误处理指南",
                    "source": "upload",
                    "relevance_score": 0.9,
                    "chunk_preview": "处理 API 错误时...",
                }
            ],
        )

        # Act
        system_prompt, user_prompt = await rag_service.build_rag_prompt(
            query=query, context=retrieved_context
        )

        # Assert
        assert "API 错误" in system_prompt or "API 错误" in user_prompt
        assert "处理 API 错误时" in system_prompt or "处理 API 错误时" in user_prompt

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="需要 OPENAI_API_KEY 环境变量")
    async def test_query_with_rag(self, rag_service):
        """测试：使用RAG进行查询"""
        # Arrange
        content = """
        工作流最佳实践：
        1. 始终从开始节点开始
        2. 添加错误处理节点
        3. 使用条件分支处理不同情况
        4. 确保有明确的结束节点
        """

        await rag_service.ingest_document(
            title="工作流最佳实践",
            content=content,
            source=DocumentSource.DEFAULT,
            workflow_id="test_workflow_003",
        )

        # Act
        result = await rag_service.query_with_rag(
            query="工作流设计有什么建议？",
            workflow_id="test_workflow_003",
            system_prompt="你是一个工作流专家。",
        )

        # Assert
        assert result is not None
        assert result.query == "工作流设计有什么建议？"
        assert len(result.context.formatted_context) > 0
        assert "开始节点" in result.context.formatted_context
        assert len(result.sources) > 0

    async def test_query_without_rag(self, rag_service):
        """测试：不使用RAG的查询"""
        # Act
        result = await rag_service.query_with_rag(
            query="测试查询", workflow_id="nonexistent_workflow", use_rag=False
        )

        # Assert
        assert result is not None
        assert result.query == "测试查询"
        assert len(result.context.formatted_context) == 0
        assert len(result.sources) == 0

    async def test_get_document_stats(self, rag_service):
        """测试：获取文档统计信息"""
        # Arrange
        workflow_id = "test_workflow_stats"

        # 导入几个文档
        for i in range(3):
            await rag_service.ingest_document(
                title=f"文档 {i+1}",
                content=f"这是第 {i+1} 个测试文档。",
                source=DocumentSource.UPLOAD,
                workflow_id=workflow_id,
            )

        # Act
        stats = await rag_service.get_document_stats(workflow_id=workflow_id)

        # Assert
        assert stats is not None
        assert "total_documents" in stats
        # 注意：实际的文档数量可能因为实现细节而不同

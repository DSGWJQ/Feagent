"""RAGService - 检索增强生成服务

应用层服务，协调：
- 知识库检索
- 上下文构建
- 与LLM的交互
"""

import logging
from dataclasses import dataclass, field

from src.domain.knowledge_base.entities.document import Document
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.domain.knowledge_base.ports.knowledge_repository import KnowledgeRepository
from src.domain.knowledge_base.ports.retriever_service import RetrieverService
from src.domain.value_objects.document_source import DocumentSource

logger = logging.getLogger(__name__)


@dataclass
class QueryContext:
    """查询上下文"""

    query: str
    workflow_id: str | None = None
    max_context_length: int = 4000
    top_k: int = 5
    filters: dict[str, str] | None = None


@dataclass
class RetrievedContext:
    """检索到的上下文"""

    chunks: list[tuple[DocumentChunk, float]]
    formatted_context: str
    total_tokens: int
    sources: list[dict[str, str | float]]


@dataclass
class RAGResult:
    """RAG结果"""

    query: str
    context: RetrievedContext
    response: str | None = None
    sources: list[dict[str, str | float]] = field(default_factory=list)


class RAGService:
    """检索增强生成服务

    职责：
    1. 从知识库检索相关文档
    2. 构建查询上下文
    3. 提供检索结果供LLM使用
    """

    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        retriever_service: RetrieverService,
    ):
        """初始化RAG服务

        参数：
            knowledge_repository: 知识库仓储
            retriever_service: 检索服务
        """
        self.repository = knowledge_repository
        self.retriever = retriever_service

    async def retrieve_context(self, query_context: QueryContext) -> RetrievedContext:
        """检索查询上下文

        参数：
            query_context: 查询上下文

        返回：
            检索到的上下文
        """
        logger.info(f"Retrieving context for query: {query_context.query[:50]}...")

        # 检索相关文档块
        chunks_with_scores = await self.retriever.retrieve_relevant_chunks(
            query=query_context.query,
            workflow_id=query_context.workflow_id,
            top_k=query_context.top_k,
            filters=query_context.filters,
        )

        # 获取格式化的上下文
        formatted_context = await self.retriever.get_context_for_query(
            query=query_context.query,
            workflow_id=query_context.workflow_id,
            max_tokens=query_context.max_context_length,
        )

        # 计算token数（简化计算，实际应该使用tokenizer）
        total_tokens = len(formatted_context.split())

        # 收集来源信息
        sources = []
        for chunk, score in chunks_with_scores:
            # 获取文档信息
            doc = await self.repository.find_document_by_id(chunk.document_id)
            if doc:
                sources.append(
                    {
                        "document_id": doc.id,
                        "title": doc.title,
                        "source": doc.source.value,
                        "relevance_score": score,
                        "chunk_preview": chunk.content[:100] + "..."
                        if len(chunk.content) > 100
                        else chunk.content,
                    }
                )

        logger.info(f"Retrieved {len(chunks_with_scores)} chunks, {total_tokens} tokens")

        return RetrievedContext(
            chunks=chunks_with_scores,
            formatted_context=formatted_context,
            total_tokens=total_tokens,
            sources=sources,
        )

    async def search_documents(
        self,
        query: str,
        workflow_id: str | None = None,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[Document]:
        """搜索文档

        参数：
            query: 查询文本
            workflow_id: 可选的工作流ID
            limit: 返回数量限制
            threshold: 相似度阈值

        返回：
            相关文档列表
        """
        # 生成查询向量
        query_embedding = await self.retriever.generate_embedding(query)

        # 搜索相似的文档块
        similar_chunks = await self.repository.search_similar_chunks(
            query_embedding=query_embedding,
            workflow_id=workflow_id,
            limit=limit,
            threshold=threshold,
        )

        # 获取去重后的文档
        document_ids = set()
        documents = []
        for chunk, _score in similar_chunks:
            if chunk.document_id not in document_ids:
                doc = await self.repository.find_document_by_id(chunk.document_id)
                if doc:
                    documents.append(doc)
                    document_ids.add(chunk.document_id)

        return documents

    async def ingest_document(
        self,
        title: str,
        content: str,
        source: DocumentSource,
        workflow_id: str | None = None,
        metadata: dict | None = None,
        file_path: str | None = None,
    ) -> str:
        """导入文档到知识库

        参数：
            title: 文档标题
            content: 文档内容
            source: 文档来源
            workflow_id: 工作流ID（可选）
            metadata: 元数据（可选）
            file_path: 文件路径（可选）

        返回：
            文档ID
        """
        logger.info(f"Ingesting document: {title}")

        # 创建文档
        document = Document.create(
            title=title,
            content=content,
            source=source,
            workflow_id=workflow_id,
            metadata=metadata,
            file_path=file_path,
        )

        # 保存文档
        await self.repository.save_document(document)

        # 切分文档
        chunk_texts = await self.retriever.chunk_document(content)

        # 为每个块生成嵌入
        chunk_embeddings = []
        for chunk_text in chunk_texts:
            embedding = await self.retriever.generate_embedding(chunk_text)
            chunk_embeddings.append(embedding)

        # 保存文档块
        for i, (chunk_text, embedding) in enumerate(
            zip(chunk_texts, chunk_embeddings, strict=False)
        ):
            chunk = DocumentChunk.create(
                document_id=document.id,
                content=chunk_text,
                embedding=embedding,
                chunk_index=i,
            )
            await self.repository.save_document_chunk(chunk)

        # 更新文档状态
        document.mark_processed()
        await self.repository.update_document(document)

        logger.info(f"Successfully ingested document {document.id} with {len(chunk_texts)} chunks")
        return document.id

    async def delete_document(self, document_id: str) -> bool:
        """删除文档

        参数：
            document_id: 文档ID

        返回：
            是否成功删除
        """
        try:
            # 删除文档（会级联删除文档块）
            await self.repository.delete_document(document_id)
            logger.info(f"Successfully deleted document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {str(e)}")
            return False

    async def get_document_stats(self, workflow_id: str | None = None) -> dict:
        """获取文档统计信息

        参数：
            workflow_id: 可选的工作流ID

        返回：
            统计信息字典
        """
        stats = {
            "total_documents": 0,
            "total_chunks": 0,
            "by_status": {},
            "by_source": {},
        }

        if workflow_id:
            # 统计特定工作流的文档
            documents = await self.repository.find_documents_by_workflow_id(workflow_id)
            stats["total_documents"] = len(documents)

            # 统计每个文档的块数
            for doc in documents:
                chunks = await self.repository.find_chunks_by_document_id(doc.id)
                stats["total_chunks"] += len(chunks)

        # TODO: 实现全局统计
        # 这需要在仓储中添加更多的查询方法

        return stats

    async def build_rag_prompt(
        self,
        query: str,
        context: RetrievedContext,
        system_prompt: str | None = None,
    ) -> tuple[str, str]:
        """构建RAG提示词

        参数：
            query: 用户查询
            context: 检索到的上下文
            system_prompt: 可选的系统提示词

        返回：
            (系统提示词, 用户提示词)
        """
        # 默认系统提示词
        if not system_prompt:
            system_prompt = """你是一个智能助手，能够根据提供的上下文信息回答用户的问题。

请注意：
1. 基于提供的上下文信息回答问题
2. 如果上下文中没有相关信息，请诚实说明
3. 可以结合多个上下文片段进行推理
4. 保持回答简洁、准确
5. 引用具体的上下文来源时，使用【来源X】的格式"""

        # 构建用户提示词
        user_prompt = f"""用户问题：{query}

相关上下文信息：
{context.formatted_context}

请基于以上信息回答用户的问题。"""

        return system_prompt, user_prompt

    async def query_with_rag(
        self,
        query: str,
        workflow_id: str | None = None,
        system_prompt: str | None = None,
        max_context_length: int = 4000,
    ) -> RAGResult:
        """使用RAG进行查询

        参数：
            query: 用户查询
            workflow_id: 可选的工作流ID
            system_prompt: 可选的系统提示词
            max_context_length: 最大上下文长度

        返回：
            RAG结果
        """
        # 构建查询上下文
        query_context = QueryContext(
            query=query,
            workflow_id=workflow_id,
            max_context_length=max_context_length,
        )

        # 检索上下文
        context = await self.retrieve_context(query_context)

        # 构建提示词
        system_prompt, user_prompt = await self.build_rag_prompt(
            query=query,
            context=context,
            system_prompt=system_prompt,
        )

        # 返回RAG结果（实际的LLM调用由调用方完成）
        return RAGResult(
            query=query,
            context=context,
            sources=[
                {
                    "document_id": source["document_id"],
                    "title": source["title"],
                    "source": source["source"],
                    "relevance_score": source["relevance_score"],
                    "preview": source["chunk_preview"],
                }
                for source in context.sources
            ],
        )

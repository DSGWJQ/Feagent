"""ChromaRetrieverService - 使用ChromaDB实现检索服务

也可以使用sqlite-vec实现，这里作为备选方案
"""

import os
from typing import Any

import chromadb
import numpy as np
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import SecretStr
from tiktoken import encoding_for_model

from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.domain.knowledge_base.ports.knowledge_repository import KnowledgeRepository
from src.domain.knowledge_base.ports.retriever_service import RetrieverService


class ChromaRetrieverService(RetrieverService):
    """使用ChromaDB实现的检索服务"""

    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        openai_api_key: str | None = None,
        model_name: str = "text-embedding-3-small",
        chroma_path: str = "data/chroma_db",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """初始化检索服务

        参数：
            knowledge_repository: 知识库仓储
            openai_api_key: OpenAI API密钥
            model_name: 嵌入模型名称
            chroma_path: ChromaDB存储路径
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
        """
        self.repository = knowledge_repository
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 初始化嵌入模型
        api_key_value = openai_api_key or os.getenv("OPENAI_API_KEY")
        api_key_secret = SecretStr(api_key_value) if api_key_value else None
        self.embeddings = OpenAIEmbeddings(model=model_name, api_key=api_key_secret)

        # 初始化文本切分器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

        # 初始化tokenizer用于计算tokens
        self.tokenizer = encoding_for_model(model_name)

        # 初始化ChromaDB客户端
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path, settings=Settings(anonymized_telemetry=False)
        )

        # 获取或创建集合
        self.collection: Any = self.chroma_client.get_or_create_collection(
            name="document_chunks", metadata={"hnsw:space": "cosine"}
        )

    def _count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return len(self.tokenizer.encode(text))

    async def generate_embedding(self, text: str) -> list[float]:
        """生成文本的向量嵌入"""
        embedding = await self.embeddings.aembed_query(text)
        return embedding

    async def chunk_document(
        self,
        content: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[str]:
        """将文档切分为多个块"""
        # 使用指定的参数或默认参数
        chunk_size = chunk_size or self.chunk_size
        chunk_overlap = chunk_overlap or self.chunk_overlap

        # 创建新的切分器
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self._count_tokens,
        )

        chunks = splitter.split_text(content)
        return chunks

    async def retrieve_relevant_chunks(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
        filters: dict[str, str] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """检索相关的文档块"""
        # 生成查询向量
        query_embedding = await self.generate_embedding(query)

        # 构建过滤条件
        where_clause = {}
        if workflow_id:
            where_clause["workflow_id"] = workflow_id
        if filters:
            where_clause.update(filters)

        # 在ChromaDB中搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause if where_clause else None,
            include=["documents", "metadatas", "distances"],
        )

        # 转换结果
        chunks_with_scores: list[tuple[DocumentChunk, float]] = []
        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        distances = results.get("distances") or []

        if ids and ids[0]:
            for i, _chunk_id in enumerate(ids[0]):
                # 获取文档内容
                content = documents[0][i]
                metadata = metadatas[0][i] or {}
                distance = distances[0][i]

                # 转换距离为相似度分数（余弦距离）
                similarity = 1 - distance

                document_id = str(metadata.get("document_id", ""))
                chunk_index_value = metadata.get("chunk_index", 0)
                chunk_index = (
                    int(chunk_index_value) if isinstance(chunk_index_value, int | float) else 0
                )
                safe_metadata = {
                    str(key): value
                    for key, value in metadata.items()
                    if isinstance(value, str | int | float | bool) or value is None
                }

                # 创建DocumentChunk对象
                chunk = DocumentChunk.create(
                    document_id=document_id,
                    content=content,
                    embedding=[],  # 不需要返回嵌入向量
                    chunk_index=chunk_index,
                    metadata=safe_metadata,
                )

                chunks_with_scores.append((chunk, similarity))

        # 按相似度排序
        chunks_with_scores.sort(key=lambda x: x[1], reverse=True)
        return chunks_with_scores

    async def rerank_chunks(
        self,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        """对文档块进行重排序

        这里使用简单的余弦相似度重排序
        实际项目中可以使用更复杂的重排序模型
        """
        # 生成查询向量
        query_embedding = await self.generate_embedding(query)
        query_array = np.array(query_embedding)

        chunks_with_scores = []
        for chunk in chunks[: top_k * 2]:  # 获取更多候选
            if chunk.embedding:
                chunk_array = np.array(chunk.embedding)
                # 计算余弦相似度
                similarity = np.dot(query_array, chunk_array) / (
                    np.linalg.norm(query_array) * np.linalg.norm(chunk_array)
                )
                chunks_with_scores.append((chunk, float(similarity)))

        # 按相似度排序并返回top_k
        chunks_with_scores.sort(key=lambda x: x[1], reverse=True)
        return chunks_with_scores[:top_k]

    async def get_context_for_query(
        self,
        query: str,
        workflow_id: str | None = None,
        max_tokens: int = 4000,
    ) -> str:
        """为查询获取上下文"""
        # 检索相关文档块
        chunks_with_scores = await self.retrieve_relevant_chunks(
            query=query,
            workflow_id=workflow_id,
            top_k=10,  # 获取更多候选以便筛选
        )

        # 构建上下文
        context_parts: list[str] = []
        current_tokens = 0

        for chunk, _score in chunks_with_scores:
            chunk_tokens = self._count_tokens(chunk.content)

            # 如果添加这个块会超过限制，跳过
            if current_tokens + chunk_tokens > max_tokens:
                continue

            # 添加文档块到上下文
            context_parts.append(f"[文档片段] {chunk.content}")
            current_tokens += chunk_tokens

        # 如果上下文太长，进行截断
        if current_tokens > max_tokens:
            # 保留前3/4的内容
            context_parts = context_parts[: int(len(context_parts) * 0.75)]

        return "\n\n---\n\n".join(context_parts)

    async def add_document_chunks(self, chunks: list[DocumentChunk]) -> None:
        """添加文档块到ChromaDB"""
        if not chunks:
            return

        # 准备数据
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        embeddings = [chunk.embedding for chunk in chunks]
        metadatas = []

        for chunk in chunks:
            metadata = chunk.metadata or {}
            metadata.update(
                {
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "created_at": chunk.created_at.isoformat(),
                    "token_count": self._count_tokens(chunk.content),
                }
            )
            metadatas.append(metadata)

        # 批量添加到ChromaDB
        self.collection.add(
            ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
        )

    async def delete_document_chunks(self, document_id: str) -> None:
        """删除指定文档的所有块"""
        # 查找所有相关的块
        results = self.collection.get(where={"document_id": document_id}, include=["metadatas"])

        if results["ids"]:
            # 删除这些块
            self.collection.delete(ids=results["ids"])

    async def update_document_chunk(self, chunk: DocumentChunk) -> None:
        """更新文档块"""
        # 先删除旧的块
        await self.delete_document_chunks(chunk.document_id)

        # 如果有块列表，重新添加
        if chunk.embedding:
            await self.add_document_chunks([chunk])

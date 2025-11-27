"""KnowledgeRepository port - 知识库仓储接口

DDD规则：
- 使用Protocol定义接口
- 定义所有与知识库持久化相关的操作
"""

from abc import ABC, abstractmethod

from src.domain.knowledge_base.entities.document import Document
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.domain.knowledge_base.entities.knowledge_base import KnowledgeBase


class KnowledgeRepository(ABC):
    """知识库仓储接口

    定义知识库相关的持久化操作
    """

    @abstractmethod
    async def save_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        """保存知识库"""
        pass

    @abstractmethod
    async def find_knowledge_base_by_id(self, id: str) -> KnowledgeBase | None:
        """根据ID查找��识库"""
        pass

    @abstractmethod
    async def find_knowledge_bases_by_owner(self, owner_id: str) -> list[KnowledgeBase]:
        """查找指定所有者的知识库"""
        pass

    @abstractmethod
    async def save_document(self, document: Document) -> None:
        """保存文档"""
        pass

    @abstractmethod
    async def find_document_by_id(self, id: str) -> Document | None:
        """根据ID查找文档"""
        pass

    @abstractmethod
    async def find_documents_by_workflow_id(self, workflow_id: str) -> list[Document]:
        """查找指定工作流的所有文档"""
        pass

    @abstractmethod
    async def update_document(self, document: Document) -> None:
        """更新文档"""
        pass

    @abstractmethod
    async def delete_document(self, id: str) -> None:
        """删除文档"""
        pass

    @abstractmethod
    async def save_document_chunk(self, chunk: DocumentChunk) -> None:
        """保存文档分块"""
        pass

    @abstractmethod
    async def find_chunks_by_document_id(self, document_id: str) -> list[DocumentChunk]:
        """查找指定文档的所有分块"""
        pass

    @abstractmethod
    async def search_similar_chunks(
        self,
        query_embedding: list[float],
        workflow_id: str | None = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[DocumentChunk, float]]:
        """搜索相似的文档分块

        参数：
            query_embedding: 查询向量
            workflow_id: 可选的工作流ID，用于限定搜索范围
            limit: 返回结果数量限制
            threshold: 相似度阈值

        返回：
            (DocumentChunk, 相似度分数) 的列表
        """
        pass

    @abstractmethod
    async def count_documents_by_workflow(self, workflow_id: str) -> int:
        """统计指定工作流的文档数量"""
        pass

    @abstractmethod
    async def delete_chunks_by_document_id(self, document_id: str) -> None:
        """删除指定文档的所有分块"""
        pass

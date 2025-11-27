"""RetrieverService port - 检索服务接口

DDD规则：
- 使用Protocol定义接口
- 定义文档检索和向量嵌入相关的操作
"""

from abc import ABC, abstractmethod
from typing import Any

from src.domain.knowledge_base.entities.document_chunk import DocumentChunk


class RetrieverService(ABC):
    """检索服务接口

    定义文档检索、向量嵌入等功能
    """

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """生成文本的向量嵌入

        参数：
            text: 输入文本

        返回：
            向量嵌入列表
        """
        pass

    @abstractmethod
    async def chunk_document(
        self,
        content: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> list[str]:
        """将文档切分为多个块

        参数：
            content: 文档内容
            chunk_size: 每个块的大小（字符数）
            chunk_overlap: 块之间的重叠大小（字符数）

        返回：
            文档块列表
        """
        pass

    @abstractmethod
    async def retrieve_relevant_chunks(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """检索相关的文档块

        参数：
            query: 查询文本
            workflow_id: 可选的工作流ID，用于限定搜索范围
            top_k: 返回的最相关块数量
            filters: 可选的过滤条件

        返回：
            (DocumentChunk, 相关性分数) 的列表，按相关性降序排列
        """
        pass

    @abstractmethod
    async def rerank_chunks(
        self,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        """对文档块进行重排序

        参数：
            query: 查询文本
            chunks: 候选文档块列表
            top_k: 返回的最终结果数量

        返回：
            (DocumentChunk, 重���序分数) 的列表
        """
        pass

    @abstractmethod
    async def get_context_for_query(
        self,
        query: str,
        workflow_id: str | None = None,
        max_tokens: int = 4000,
    ) -> str:
        """为查询获取上下文

        参数：
            query: 查询文本
            workflow_id: 可选的工作流ID
            max_tokens: 最大token数

        返回：
            拼接后的上下文字符串
        """
        pass

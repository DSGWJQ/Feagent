"""RAG Service Port

定义RAG服务的端口协议（Protocol），供接口层依赖注入使用。
遵循 Ports and Adapters 架构模式，实现 Domain 层与 Infrastructure 层的解耦。

Author: Claude Code
Date: 2025-12-17
"""

from typing import Any, Protocol

from src.domain.knowledge_base.entities.document import Document
from src.domain.value_objects.document_source import DocumentSource


class RAGServicePort(Protocol):
    """RAG服务端口协议

    定义RAG服务必须实现的接口方法。
    实现类: RAGService (Application Layer)

    架构说明:
        Interface Layer (dependencies) → RAGServicePort (Domain Port)
                                        ↑
                            RAGService (Application Layer)
    """

    async def retrieve_context(self, query_context: Any) -> Any:
        """检索查询上下文

        Args:
            query_context: 查询上下文字典，包含:
                - query: 查询文本
                - workflow_id: 工作流ID (可选)
                - max_context_length: 最大上下文长度
                - top_k: 返回结果数量

        Returns:
            检索到的上下文字典:
            - chunks: 文档块列表
            - formatted_context: 格式化的上下文文本
            - total_tokens: token总数
            - sources: 来源信息列表
        """
        ...

    async def search_documents(
        self,
        query: str,
        workflow_id: str | None = None,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[Document]:
        """搜索文档

        Args:
            query: 查询文本
            workflow_id: 可选的工作流ID
            limit: 返回数量限制
            threshold: 相似度阈值

        Returns:
            相关文档列表
        """
        ...

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

        Args:
            title: 文档标题
            content: 文档内容
            source: 文档来源
            workflow_id: 工作流ID（可选）
            metadata: 元数据（可选）
            file_path: 文件路径（可选）

        Returns:
            文档ID
        """
        ...

    async def delete_document(self, document_id: str) -> bool:
        """删除文档

        Args:
            document_id: 文档ID

        Returns:
            是否成功删除
        """
        ...

    async def get_document_stats(self, workflow_id: str | None = None) -> dict:
        """获取文档统计信息

        Args:
            workflow_id: 可选的工作流ID

        Returns:
            统计信息字典
        """
        ...

    async def query_with_rag(
        self,
        query: str,
        workflow_id: str | None = None,
        system_prompt: str | None = None,
        max_context_length: int = 4000,
    ) -> Any:
        """使用RAG进行查询

        Args:
            query: 用户查询
            workflow_id: 可选的工作流ID
            system_prompt: 可选的系统提示词
            max_context_length: 最大上下文长度

        Returns:
            RAG结果字典:
            - query: 用户查询
            - context: 检索到的上下文
            - response: LLM响应（可选）
            - sources: 来源信息列表
        """
        ...

"""DocumentChunk entity - 文档分块实体

DDD规则：
- 纯Python实现，不依赖任何框架
- 使用dataclass定义属性
- 包含业务逻辑和验证
"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import DomainError


@dataclass
class DocumentChunk:
    """文档分块实体

    表示文档的一个分块，包含分块内容和向量嵌入
    """

    id: str
    document_id: str
    content: str
    embedding: list[float]
    chunk_index: int
    created_at: datetime
    metadata: dict | None = None

    @staticmethod
    def create(
        document_id: str,
        content: str,
        embedding: list[float],
        chunk_index: int,
        metadata: dict | None = None,
    ) -> "DocumentChunk":
        """创建新的文档分块

        参数：
            document_id: 文档ID
            content: 分块内容
            embedding: 向量嵌入
            chunk_index: 分块索引
            metadata: 元数据（可选）

        返回：
            DocumentChunk实体

        抛出：
            DomainError: 当必填字段为空时
        """
        # 验证必填字段
        if not document_id or not document_id.strip():
            raise DomainError("文档ID不能为空")

        if not content or not content.strip():
            raise DomainError("分块内容不能为空")

        if not embedding:
            raise DomainError("向量嵌入不能为空")

        if chunk_index < 0:
            raise DomainError("分块索引不能小于0")

        # 生成ID
        import uuid

        chunk_id = str(uuid.uuid4())

        return DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            content=content,
            embedding=embedding,
            chunk_index=chunk_index,
            created_at=datetime.utcnow(),
            metadata=metadata or {},
        )

    def update_embedding(self, new_embedding: list[float]) -> None:
        """更新向量嵌入

        参数：
            new_embedding: 新的向量嵌入

        抛出：
            DomainError: 当新嵌入为空时
        """
        if not new_embedding:
            raise DomainError("向量嵌入不能为空")

        self.embedding = new_embedding

    def to_dict(self) -> dict:
        """转换为字典格式

        返回：
            分块字典表示
        """
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

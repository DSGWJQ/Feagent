"""测试 DocumentChunk 实体

遵循 TDD 原则
"""

from datetime import datetime

import pytest

from src.domain.exceptions import DomainError
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk


class TestDocumentChunk:
    """DocumentChunk 实体测试"""

    def test_create_chunk_with_valid_inputs_should_succeed(self):
        """测试：使用有效输入创建文档块应该成功"""
        # Arrange
        document_id = "doc_123"
        content = "这是一个文档块内容"
        embedding = [0.1, 0.2, 0.3, 0.4]
        chunk_index = 0

        # Act
        chunk = DocumentChunk.create(
            document_id=document_id, content=content, embedding=embedding, chunk_index=chunk_index
        )

        # Assert
        assert chunk.id is not None
        assert chunk.document_id == document_id
        assert chunk.content == content
        assert chunk.embedding == embedding
        assert chunk.chunk_index == chunk_index
        assert chunk.created_at is not None
        assert isinstance(chunk.created_at, datetime)
        assert chunk.metadata == {}

    def test_create_chunk_with_empty_document_id_should_raise_error(self):
        """测试：创建文档块时文档ID为空应该抛出异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainError, match="文档ID不能为空"):
            DocumentChunk.create(
                document_id="", content="内容", embedding=[0.1, 0.2], chunk_index=0
            )

    def test_create_chunk_with_empty_content_should_raise_error(self):
        """测试：创建文档块时内容为空应该抛出异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainError, match="分块内容不能为空"):
            DocumentChunk.create(
                document_id="doc_123", content="", embedding=[0.1, 0.2], chunk_index=0
            )

    def test_create_chunk_with_empty_embedding_should_raise_error(self):
        """测试：创建文档块时向量为空应该抛出异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainError, match="向量嵌入不能为空"):
            DocumentChunk.create(document_id="doc_123", content="内容", embedding=[], chunk_index=0)

    def test_create_chunk_with_negative_index_should_raise_error(self):
        """测试：创建文档块时索引为负数应该抛出异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainError, match="分块索引不能小于0"):
            DocumentChunk.create(
                document_id="doc_123", content="内容", embedding=[0.1, 0.2], chunk_index=-1
            )

    def test_update_embedding_with_valid_embedding_should_succeed(self):
        """测试：更新有效向量应该成功"""
        # Arrange
        chunk = DocumentChunk.create(
            document_id="doc_123", content="内容", embedding=[0.1, 0.2, 0.3], chunk_index=0
        )
        new_embedding = [0.4, 0.5, 0.6, 0.7]

        # Act
        chunk.update_embedding(new_embedding)

        # Assert
        assert chunk.embedding == new_embedding

    def test_update_embedding_with_empty_embedding_should_raise_error(self):
        """测试：更新空向量应该抛出异常"""
        # Arrange
        chunk = DocumentChunk.create(
            document_id="doc_123", content="内容", embedding=[0.1, 0.2], chunk_index=0
        )

        # Act & Assert
        with pytest.raises(DomainError, match="向量嵌入不能为空"):
            chunk.update_embedding([])

    def test_to_dict_should_return_correct_representation(self):
        """测试：转换为字典应该返回正确的表示"""
        # Arrange
        chunk = DocumentChunk.create(
            document_id="doc_123",
            content="测试内容",
            embedding=[0.1, 0.2, 0.3],
            chunk_index=2,
            metadata={"token_count": 100},
        )

        # Act
        chunk_dict = chunk.to_dict()

        # Assert
        assert chunk_dict["id"] == chunk.id
        assert chunk_dict["document_id"] == "doc_123"
        assert chunk_dict["content"] == "测试内容"
        assert chunk_dict["chunk_index"] == 2
        assert chunk_dict["metadata"] == {"token_count": 100}
        assert "created_at" in chunk_dict
        # 注意：embedding 不应该出现在字典中（太大且通常不需要序列化）
        assert "embedding" not in chunk_dict

    def test_create_chunk_with_metadata(self):
        """测试：创建文档块时包含元数据"""
        # Arrange
        metadata = {"token_count": 150, "source": "page_1"}

        # Act
        chunk = DocumentChunk.create(
            document_id="doc_123",
            content="内容",
            embedding=[0.1, 0.2],
            chunk_index=0,
            metadata=metadata,
        )

        # Assert
        assert chunk.metadata == metadata
        assert chunk.metadata["token_count"] == 150
        assert chunk.metadata["source"] == "page_1"

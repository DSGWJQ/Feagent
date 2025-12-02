"""测试 Document 实体

遵循 TDD 原则：
1. 先写测试（Red）
2. 实现最小功能使测试通过（Green）
3. 重构代码（Refactor）
"""

from datetime import datetime

import pytest

from src.domain.exceptions import DomainError
from src.domain.knowledge_base.entities.document import Document
from src.domain.value_objects.document_source import DocumentSource
from src.domain.value_objects.document_status import DocumentStatus


class TestDocument:
    """Document 实体测试"""

    def test_create_document_with_valid_inputs_should_succeed(self):
        """测试：使用有效输入创建文档应该成功"""
        # Arrange
        title = "测试文档"
        content = "这是一个测试文档内容"
        source = DocumentSource.UPLOAD

        # Act
        document = Document.create(title=title, content=content, source=source)

        # Assert
        assert document.id is not None
        assert document.title == title
        assert document.content == content
        assert document.source == source
        assert document.status == DocumentStatus.PENDING
        assert document.created_at is not None
        assert isinstance(document.created_at, datetime)
        assert document.metadata == {}

    def test_create_document_with_empty_title_should_raise_error(self):
        """测试：创建文档时标题为空应该抛出异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainError, match="文档标题不能为空"):
            Document.create(title="", content="内容", source=DocumentSource.UPLOAD)

    def test_create_document_with_empty_content_should_raise_error(self):
        """测试：创建文档时内容为空应该抛出异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainError, match="文档内容不能为空"):
            Document.create(title="标题", content="", source=DocumentSource.UPLOAD)

    def test_create_document_with_whitespace_only_title_should_raise_error(self):
        """测试：创建文档时标题只有空格应该抛出异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainError, match="文档标题不能为空"):
            Document.create(title="   ", content="内容", source=DocumentSource.UPLOAD)

    def test_mark_processed_should_update_status_and_timestamp(self):
        """测试：标记文档已处理应该更新状态和时间戳"""
        # Arrange
        document = Document.create(title="测试", content="内容", source=DocumentSource.UPLOAD)
        original_updated_at = document.updated_at
        original_status = document.status

        # Act
        document.mark_processed()

        # Assert
        assert document.status == DocumentStatus.PROCESSED
        assert document.updated_at is not None
        assert document.updated_at != original_updated_at
        assert document.status != original_status

    def test_mark_failed_should_update_status_and_reason(self):
        """测试：标记文档失败应该更新状态和原因"""
        # Arrange
        document = Document.create(title="测试", content="内容", source=DocumentSource.UPLOAD)
        failure_reason = "处理失败：格式不支持"

        # Act
        document.mark_failed(failure_reason)

        # Assert
        assert document.status == DocumentStatus.FAILED
        assert document.updated_at is not None
        assert document.metadata is not None
        assert document.metadata["failure_reason"] == failure_reason

    def test_update_content_with_valid_content_should_succeed(self):
        """测试：更新有效内容应该成功"""
        # Arrange
        document = Document.create(title="测试", content="原内容", source=DocumentSource.UPLOAD)
        new_content = "更新后的内容"

        # Act
        document.update_content(new_content)

        # Assert
        assert document.content == new_content
        assert document.status == DocumentStatus.PENDING
        assert document.updated_at is not None

    def test_update_content_with_empty_content_should_raise_error(self):
        """测试：更新空内容应该抛出异常"""
        # Arrange
        document = Document.create(title="测试", content="原内容", source=DocumentSource.UPLOAD)

        # Act & Assert
        with pytest.raises(DomainError, match="新内容不能为空"):
            document.update_content("")

    def test_to_dict_should_return_correct_representation(self):
        """测试：转换为字典应该返回正确的表示"""
        # Arrange
        document = Document.create(
            title="测试文档",
            content="内容",
            source=DocumentSource.UPLOAD,
            workflow_id="wf_123",
            metadata={"key": "value"},
        )

        # Act
        doc_dict = document.to_dict()

        # Assert
        assert doc_dict["id"] == document.id
        assert doc_dict["title"] == "测试文档"
        assert doc_dict["content"] == "内容"
        assert doc_dict["source"] == "upload"
        assert doc_dict["status"] == "pending"
        assert doc_dict["workflow_id"] == "wf_123"
        assert doc_dict["metadata"] == {"key": "value"}
        assert "created_at" in doc_dict
        assert doc_dict["updated_at"] is None

    def test_create_document_with_all_optional_fields(self):
        """测试：创建文档时包含所有可选字段"""
        # Arrange
        metadata = {"author": "test", "tags": ["test", "doc"]}

        # Act
        document = Document.create(
            title="完整文档",
            content="完整内容",
            source=DocumentSource.FILESYSTEM,
            file_path="/path/to/file.txt",
            workflow_id="wf_456",
            metadata=metadata,
        )

        # Assert
        assert document.title == "完整文档"
        assert document.content == "完整内容"
        assert document.source == DocumentSource.FILESYSTEM
        assert document.file_path == "/path/to/file.txt"
        assert document.workflow_id == "wf_456"
        assert document.metadata == metadata

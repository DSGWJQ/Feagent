"""Document entity - 知识库文档实体

DDD规则：
- 纯Python实现，不依赖任何框架
- 使用dataclass定义属性
- 包含业务逻辑和验证
"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import DomainError
from src.domain.value_objects.document_source import DocumentSource
from src.domain.value_objects.document_status import DocumentStatus


@dataclass
class Document:
    """知识库文档实体

    表示知识库中的一个完整文档，可以是PDF、Word、Markdown、HTML等格式
    """

    id: str
    title: str
    content: str
    source: DocumentSource
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict | None = None
    file_path: str | None = None
    workflow_id: str | None = None

    @staticmethod
    def create(
        title: str,
        content: str,
        source: DocumentSource,
        file_path: str | None = None,
        workflow_id: str | None = None,
        metadata: dict | None = None,
    ) -> "Document":
        """创建新文档

        参数：
            title: 文档标题
            content: 文档内容
            source: 文档来源
            file_path: 文件路径（可选）
            workflow_id: 关联的工作流ID（可选）
            metadata: 元数据（可选）

        返回：
            Document实体

        抛出：
            DomainError: 当必填字段为空时
        """
        # 验证必填字段
        if not title or not title.strip():
            raise DomainError("文档标题不能为空")

        if not content or not content.strip():
            raise DomainError("文档内容不能为空")

        # 生成ID
        import uuid

        doc_id = str(uuid.uuid4())

        return Document(
            id=doc_id,
            title=title.strip(),
            content=content,
            source=source,
            status=DocumentStatus.PENDING,
            created_at=datetime.utcnow(),
            metadata=metadata or {},
            file_path=file_path,
            workflow_id=workflow_id,
        )

    def mark_processed(self) -> None:
        """标记文档已处理"""
        self.status = DocumentStatus.PROCESSED
        self.updated_at = datetime.utcnow()

    def mark_failed(self, reason: str) -> None:
        """标记文档处理失败"""
        self.status = DocumentStatus.FAILED
        self.updated_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
        self.metadata["failure_reason"] = reason

    def update_content(self, new_content: str) -> None:
        """更新文档内容

        参数：
            new_content: 新的文档内容

        抛出：
            DomainError: 当新内容为空时
        """
        if not new_content or not new_content.strip():
            raise DomainError("新内容不能为空")

        self.content = new_content
        self.status = DocumentStatus.PENDING
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """转换为字典格式

        返回：
            文档字典表示
        """
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
            "file_path": self.file_path,
            "workflow_id": self.workflow_id,
        }

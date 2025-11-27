"""KnowledgeBase entity - 知识库聚合根

DDD规则：
- 纯Python实现，不依赖任何框架
- 使用dataclass定义属性
- 包含业务逻辑和验证
"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import DomainError
from src.domain.value_objects.knowledge_base_type import KnowledgeBaseType


@dataclass
class KnowledgeBase:
    """知识库聚合根

    表示一个完整的知识库，包含多个文档
    """

    id: str
    name: str
    description: str
    type: KnowledgeBaseType
    created_at: datetime
    updated_at: datetime | None = None
    owner_id: str | None = None

    @staticmethod
    def create(
        name: str,
        description: str,
        type: KnowledgeBaseType,
        owner_id: str | None = None,
    ) -> "KnowledgeBase":
        """创建新的知识库

        参数：
            name: 知识库名称
            description: 知识库描述
            type: 知识库类型
            owner_id: 所有者ID（可选）

        返回：
            KnowledgeBase实体

        抛出：
            DomainError: 当必填字段为空时
        """
        # 验证必填字段
        if not name or not name.strip():
            raise DomainError("知识库名称不能为空")

        # 生成ID
        import uuid

        kb_id = str(uuid.uuid4())

        return KnowledgeBase(
            id=kb_id,
            name=name.strip(),
            description=description.strip(),
            type=type,
            created_at=datetime.utcnow(),
            owner_id=owner_id,
        )

    def update_name(self, new_name: str) -> None:
        """更新知识库名称

        参数：
            new_name: 新名称

        抛出：
            DomainError: 当新名称为空时
        """
        if not new_name or not new_name.strip():
            raise DomainError("知识库名称不能为空")

        self.name = new_name.strip()
        self.updated_at = datetime.utcnow()

    def update_description(self, new_description: str) -> None:
        """更新知识���描述

        参数：
            new_description: 新描述
        """
        self.description = new_description.strip()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """转换为字典格式

        返回：
            知识库字典表示
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "owner_id": self.owner_id,
        }

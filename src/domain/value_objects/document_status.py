"""DocumentStatus value object - 文档状态枚举"""

from enum import Enum


class DocumentStatus(str, Enum):
    """文档状态枚举

    定义文档的处理状态
    """

    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    PROCESSED = "processed"  # 已处理
    FAILED = "failed"  # 处理失败
    ARCHIVED = "archived"  # 已归档

    @classmethod
    def get_all_values(cls) -> list[str]:
        """获取所有枚举值"""
        return [value.value for value in cls]

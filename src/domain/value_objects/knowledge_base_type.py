"""KnowledgeBaseType value object - 知识库类型枚举"""

from enum import Enum


class KnowledgeBaseType(str, Enum):
    """知识库类型枚举

    定义不同类型的知识库
    """

    GLOBAL = "global"  # 全局知识库
    WORKFLOW = "workflow"  # 工作流专属知识库
    USER = "user"  # 用户私有知识库
    SYSTEM = "system"  # 系统知识库

    @classmethod
    def get_all_values(cls) -> list[str]:
        """获取所有枚举值"""
        return [value.value for value in cls]

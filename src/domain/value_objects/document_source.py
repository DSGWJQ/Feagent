"""DocumentSource value object - 文档来源枚举"""

from enum import Enum


class DocumentSource(str, Enum):
    """文档来源枚举

    定义文档的各种来源类型
    """

    UPLOAD = "upload"  # 用户上传
    URL = "url"  # 网络URL
    FILESYSTEM = "filesystem"  # 本地文件系统
    WORKFLOW = "workflow"  # 工作流生成
    DEFAULT = "default"  # 默认知识库

    @classmethod
    def get_all_values(cls) -> list[str]:
        """获取所有枚举值"""
        return [value.value for value in cls]

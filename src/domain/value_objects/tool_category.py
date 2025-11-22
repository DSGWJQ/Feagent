"""ToolCategory 枚举 - 工具分类

业务定义：
- ToolCategory 定义工具的功能分类
- 方便工具的查找、过滤和组织
- 不同分类的工具可能有不同的实现方式和配置要求

设计原则：
- 使用枚举确保分类的一致性
- 继承 str 方便序列化和数据库存储
"""

from enum import Enum


class ToolCategory(str, Enum):
    """工具分类枚举

    为什么继承 str？
    1. 序列化友好：可以直接转换为 JSON
    2. 数据库友好：可以直接存储为字符串
    3. 兼容性好：可以和字符串比较

    支持的工具分类：
    - HTTP: HTTP 请求工具（GET/POST/PUT/DELETE等）
    - DATABASE: 数据库操作工具（查询、插入、更新等）
    - FILE: 文件处理工具（读取、写入、移动等）
    - AI: AI 相关工具（文本生成、图像生成、向量检索等）
    - NOTIFICATION: 通知工具（邮件、短信、Webhook等）
    - CUSTOM: 用户自定义工具（JavaScript/Python代码）
    """

    # HTTP 请求工具
    HTTP = "http"

    # 数据库操作工具
    DATABASE = "database"

    # 文件处理工具
    FILE = "file"

    # AI 相关工具
    AI = "ai"

    # 通知工具
    NOTIFICATION = "notification"

    # 用户自定义工具
    CUSTOM = "custom"

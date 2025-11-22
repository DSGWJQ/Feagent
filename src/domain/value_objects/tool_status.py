"""ToolStatus 枚举 - 工具状态

业务定义：
- ToolStatus 定义工具的生命周期状态
- 从 DRAFT（草稿）开始，经历 TESTING（测试），最终 PUBLISHED（发布）
- 发布后可以 DEPRECATED（废弃）

设计原则：
- 使用枚举确保状态值的一致性
- 继承 str 方便序列化和数据库存储
"""

from enum import Enum


class ToolStatus(str, Enum):
    """工具状态枚举

    为什么继承 str？
    1. 序列化友好：可以直接转换为 JSON
    2. 数据库友好：可以直接存储为字符串
    3. 兼容性好：可以和字符串比较

    生命周期：
    DRAFT(草稿) → TESTING(测试) → PUBLISHED(发布) → DEPRECATED(废弃)
    """

    # 草稿状态：工具刚创建，还在编辑阶段
    DRAFT = "draft"

    # 测试状态：工具已完成编辑，进入测试阶段
    TESTING = "testing"

    # 已发布：工具通过测试，可以在生产环境使用
    PUBLISHED = "published"

    # 已废弃：工具已淘汰，不再使用（但历史数据保留）
    DEPRECATED = "deprecated"

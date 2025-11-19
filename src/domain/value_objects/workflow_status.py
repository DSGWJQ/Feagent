"""WorkflowStatus 枚举 - 工作流状态

业务定义：
- WorkflowStatus 定义工作流的生命周期状态
- 用于控制工作流的执行和编辑权限

设计原则：
- 使用枚举确保类型安全
- 继承 str 方便序列化
"""

from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流状态枚举

    为什么继承 str？
    1. 序列化友好：可以直接转换为 JSON
    2. 数据库友好：可以直接存储为字符串
    3. 兼容性好：可以和字符串比较

    状态说明：
    - DRAFT: 草稿状态（可编辑）
    - PUBLISHED: 已发布状态（可执行，不可编辑）
    - ARCHIVED: 已归档状态（不可执行，不可编辑）

    状态转换：
    DRAFT → PUBLISHED → ARCHIVED
    PUBLISHED → DRAFT（取消发布）
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

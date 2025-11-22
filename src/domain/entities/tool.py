"""Tool 实体 - 工具聚合根

业务定义：
- Tool 是工具的聚合根
- 支持工具的生命周期管理（DRAFT → TESTING → PUBLISHED → DEPRECATED）
- 支持多种工具分类和实现方式
- 追踪工具使用统计

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
- 维护工具的不变式（状态转移、参数有效性等）
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List

from src.domain.exceptions import DomainError
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus


@dataclass
class ToolParameter:
    """工具参数定义

    描述工具的输入参数要求

    属性说明：
    - name: 参数名称
    - type: 参数类型（string, number, boolean, object, array）
    - description: 参数描述
    - required: 是否必需
    - default: 默认值
    - enum: 枚举值列表（可选）
    """

    name: str
    type: str  # string, number, boolean, object, array
    description: str
    required: bool = False
    default: Any = None
    enum: List[str] | None = None  # 枚举值列表


@dataclass
class Tool:
    """Tool 实体（聚合根）

    属性说明：
    - id: 唯一标识符（tool_ 前缀）
    - name: 工具名称（用户可见）
    - description: 工具描述
    - category: 工具分类
    - status: 工具状态（DRAFT/TESTING/PUBLISHED/DEPRECATED）
    - version: 语义化版本号（e.g., "1.0.0"）

    工具定义：
    - parameters: 工具的输入参数列表
    - returns: 工具的返回值 schema

    实现方式：
    - implementation_type: 实现类型（builtin, http, javascript, python）
    - implementation_config: 实现配置（URL、代码、连接参数等）

    元数据：
    - author: 工具创建者
    - tags: 工具标签列表
    - icon: 工具图标 URL

    使用统计：
    - usage_count: 使用次数
    - last_used_at: 最后使用时间

    时间戳：
    - created_at: 创建时间
    - updated_at: 最后更新时间
    - published_at: 发布时间

    为什么是聚合根？
    1. Tool 管理 ToolParameter 的生命周期
    2. 外部只能通过 Tool 操作参数
    3. Tool 维护工具状态和生命周期的一致性
    """

    id: str
    name: str
    description: str
    category: ToolCategory
    status: ToolStatus
    version: str
    parameters: List[ToolParameter] = field(default_factory=list)
    returns: Dict[str, Any] = field(default_factory=dict)
    implementation_type: str = "builtin"
    implementation_config: Dict[str, Any] = field(default_factory=dict)
    author: str = ""
    tags: List[str] = field(default_factory=list)
    icon: str | None = None
    usage_count: int = 0
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    published_at: datetime | None = None

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        category: ToolCategory,
        author: str,
        **kwargs,
    ) -> "Tool":
        """创建 Tool 的工厂方法

        为什么使用工厂方法？
        1. 封装创建逻辑：自动生成 ID、设置默认值、初始化状态
        2. 验证业务规则：确保 name 不为空
        3. 符合 DDD 聚合根创建模式

        参数：
            name: 工具名称（必需）
            description: 工具描述
            category: 工具分类
            author: 工具创建者
            **kwargs: 其他可选参数（parameters, returns, implementation_type等）

        返回：
            Tool 实例（状态为 DRAFT）

        抛出：
            DomainError: 当验证失败时
        """
        # 验证业务规则
        if not name or not name.strip():
            raise DomainError("工具名称不能为空")

        # 使用 UUIDv4 生成 ID
        from uuid import uuid4

        return cls(
            id=f"tool_{uuid4().hex[:8]}",
            name=name.strip(),
            description=description.strip() if description else "",
            category=category,
            status=ToolStatus.DRAFT,
            version="0.1.0",
            author=author,
            created_at=datetime.now(UTC),
            **kwargs,
        )

    def publish(self) -> None:
        """发布工具

        业务规则：
        - 只有 TESTING 状态的工具才能发布
        - 发布后状态变为 PUBLISHED
        - 记录发布时间

        抛出：
            DomainError: 当工具不在 TESTING 状态时
        """
        if self.status != ToolStatus.TESTING:
            raise DomainError("只有测试通过的工具才能发布")

        self.status = ToolStatus.PUBLISHED
        self.published_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def deprecate(self, reason: str) -> None:
        """废弃工具

        业务规则：
        - 将状态设置为 DEPRECATED
        - 记录废弃原因（保存在 implementation_config 中）
        - 更新时间戳

        参数：
            reason: 废弃原因（字符串）
        """
        self.status = ToolStatus.DEPRECATED
        self.implementation_config["deprecation_reason"] = reason
        self.updated_at = datetime.now(UTC)

    def increment_usage(self) -> None:
        """增加使用计数

        业务规则：
        - 每次工具被使用时调用此方法
        - 增加 usage_count
        - 更新 last_used_at 时间戳
        """
        self.usage_count += 1
        self.last_used_at = datetime.now(UTC)

    def update_version(self, new_version: str) -> None:
        """更新工具版本

        参数：
            new_version: 新的版本号（语义化版本）
        """
        if not new_version or not new_version.strip():
            raise DomainError("版本号不能为空")

        self.version = new_version.strip()
        self.updated_at = datetime.now(UTC)

    def add_parameter(self, param: ToolParameter) -> None:
        """添加参数

        参数：
            param: 工具参数
        """
        self.parameters.append(param)
        self.updated_at = datetime.now(UTC)

    def set_implementation(
        self, implementation_type: str, config: Dict[str, Any]
    ) -> None:
        """设置工具实现

        参数：
            implementation_type: 实现类型（builtin, http, javascript, python）
            config: 实现配置
        """
        self.implementation_type = implementation_type
        self.implementation_config = config
        self.updated_at = datetime.now(UTC)

"""CreateToolUseCase - 创建工具用例

V2新功能：支持用户创建自定义工具

业务场景：
用户定义工具的名称、分类、参数和实现方式，系统创建工具实体

职责：
1. 接收输入参数（name, description, category, author等）
2. 调用 Tool.create() 创建领域实体
3. 调用 Repository.save() 持久化实体
4. 返回创建的 Tool

第一性原则：
- 用例是业务逻辑的编排者，不包含业务规则
- 业务规则在 Domain 层（Tool.create() 中）
- 用例只负责协调各个组件
"""

from dataclasses import dataclass
from typing import Any

from src.domain.entities.tool import Tool, ToolParameter
from src.domain.ports.tool_repository import ToolRepository
from src.domain.value_objects.tool_category import ToolCategory


@dataclass
class CreateToolInput:
    """创建工具的输入参数

    属性说明：
    - name: 工具名称（必需）
    - description: 工具描述
    - category: 工具分类
    - author: 工具创建者
    - parameters: 工具参数列表（可选）
    - implementation_type: 实现类型（builtin, http, javascript, python）
    - implementation_config: 实现配置
    """

    name: str
    description: str
    category: str  # 字符串，将转换为 ToolCategory
    author: str
    parameters: list[dict[str, Any]] | None = None
    implementation_type: str = "builtin"
    implementation_config: dict[str, Any] | None = None


class CreateToolUseCase:
    """创建工具用例

    职责：
    1. 接收 CreateToolInput 输入
    2. 调用 Tool.create() 创建领域实体
    3. 调用 Repository.save() 持久化实体
    4. 返回创建的 Tool

    依赖：
    - ToolRepository: Tool 仓储接口（通过构造函数注入）

    执行流程：
    1. 转换参数（category 字符串 → ToolCategory 枚举）
    2. 调用 Tool.create() 创建实体
    3. 调用 Repository.save() 持久化
    4. 返回 Tool 实体
    """

    def __init__(self, tool_repository: ToolRepository):
        """初始化用例

        参数：
            tool_repository: Tool 仓储接口
        """
        self.tool_repository = tool_repository

    def execute(self, input_data: CreateToolInput) -> Tool:
        """执行创建工具用例

        参数：
            input_data: CreateToolInput 输入参数

        返回：
            Tool 实体

        抛出：
            DomainError: 当验证失败时（从 Domain 层传播）
        """
        # 1. 转换 category 字符串为枚举
        category = ToolCategory(input_data.category)

        # 2. 转换 parameters（如果提供）
        parameters = []
        if input_data.parameters:
            parameters = [
                ToolParameter(
                    name=p["name"],
                    type=p["type"],
                    description=p.get("description", ""),
                    required=p.get("required", False),
                    default=p.get("default"),
                    enum=p.get("enum"),
                )
                for p in input_data.parameters
            ]

        # 3. 调用 Domain 层创建 Tool 实体
        tool = Tool.create(
            name=input_data.name,
            description=input_data.description,
            category=category,
            author=input_data.author,
            parameters=parameters,
            implementation_type=input_data.implementation_type,
            implementation_config=input_data.implementation_config or {},
        )

        # 4. 持久化 Tool
        self.tool_repository.save(tool)

        # 5. 返回创建的 Tool
        return tool

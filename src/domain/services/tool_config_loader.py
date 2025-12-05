"""工具配置加载器 - 阶段 1

业务定义：
- 解析 YAML 格式的工具配置文件
- 验证配置的有效性
- 将配置转换为 Tool 实体
- 支持批量加载和导出功能

设计原则：
- 纯 Python 实现，不依赖数据库框架
- 使用 dataclass 定义 Schema
- 提供详细的验证错误信息
"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from src.domain.entities.tool import Tool, ToolParameter
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus

# =============================================================================
# 枚举定义
# =============================================================================


class ShareableScope(str, Enum):
    """工具可共享范围枚举

    定义工具可以被共享的范围：
    - PRIVATE: 仅创建者可见（默认）
    - TEAM: 团队内可见
    - PUBLIC: 所有人可见（工具市场）
    """

    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


# =============================================================================
# Schema 数据类
# =============================================================================


@dataclass
class ToolParameterSchema:
    """工具参数 Schema

    对应 YAML 配置中的 parameters 列表项

    属性说明：
    - name: 参数名称（必需）
    - type: 参数类型（必需）：string, number, boolean, object, array
    - description: 参数描述（必需）
    - required: 是否必需（默认 False）
    - default: 默认值（可选）
    - enum: 枚举值列表（可选）
    """

    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolConfigSchema:
    """工具配置 Schema

    对应 YAML 配置文件的完整结构

    必需字段：
    - name: 工具名称
    - description: 工具描述
    - category: 工具分类
    - entry: 入口配置（type + 对应的配置）

    可选字段：
    - version: 版本号（默认 "1.0.0"）
    - author: 作者
    - tags: 标签列表
    - icon: 图标
    - shareable_scope: 可共享范围（默认 PRIVATE）
    - parameters: 参数列表
    - returns: 返回值 Schema
    """

    name: str
    description: str
    category: str
    entry: dict[str, Any]
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = dataclass_field(default_factory=list)
    icon: str | None = None
    shareable_scope: ShareableScope = ShareableScope.PRIVATE
    parameters: list[ToolParameterSchema] = dataclass_field(default_factory=list)
    returns: dict[str, Any] = dataclass_field(default_factory=dict)


# =============================================================================
# 异常定义
# =============================================================================


class ToolConfigValidationError(Exception):
    """工具配置验证错误

    当配置验证失败时抛出，包含详细的错误信息
    """

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


# =============================================================================
# 配置加载器
# =============================================================================


class ToolConfigLoader:
    """工具配置加载器

    功能：
    1. 解析 YAML 格式的工具配置
    2. 验证配置的有效性
    3. 将配置转换为 Tool 实体
    4. 批量加载工具配置
    5. 导出 Tool 实体为 YAML

    支持的入口类型（entry.type）：
    - builtin: 内置工具
    - http: HTTP 请求
    - javascript: JavaScript 代码
    - python: Python 模块

    支持的参数类型：
    - string, number, boolean, object, array, any
    """

    # 有效的入口类型
    VALID_ENTRY_TYPES = {"builtin", "http", "javascript", "python"}

    # 有效的参数类型
    VALID_PARAM_TYPES = {"string", "number", "boolean", "object", "array", "any"}

    # 有效的分类（基于 ToolCategory 枚举）
    VALID_CATEGORIES = {c.value for c in ToolCategory}

    def parse_yaml(self, yaml_content: str) -> ToolConfigSchema:
        """从 YAML 字符串解析工具配置

        参数：
            yaml_content: YAML 格式的配置字符串

        返回：
            ToolConfigSchema 实例

        抛出：
            ToolConfigValidationError: 当验证失败时
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ToolConfigValidationError(f"YAML 解析错误: {e}") from e

        if not isinstance(data, dict):
            raise ToolConfigValidationError("配置必须是一个字典")

        return self._parse_dict(data)

    def load_from_file(self, file_path: str) -> ToolConfigSchema:
        """从文件加载工具配置

        参数：
            file_path: YAML 文件路径

        返回：
            ToolConfigSchema 实例

        抛出：
            ToolConfigValidationError: 当验证失败时
            FileNotFoundError: 当文件不存在时
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {file_path}")

        yaml_content = path.read_text(encoding="utf-8")
        return self.parse_yaml(yaml_content)

    def load_from_directory(self, dir_path: str) -> list[ToolConfigSchema]:
        """从目录加载所有工具配置

        只加载 .yaml 和 .yml 扩展名的文件，跳过无效配置

        参数：
            dir_path: 目录路径

        返回：
            成功加载的 ToolConfigSchema 列表
        """
        configs, _ = self.load_from_directory_with_errors(dir_path)
        return configs

    def load_from_directory_with_errors(
        self, dir_path: str
    ) -> tuple[list[ToolConfigSchema], list[tuple[str, str]]]:
        """从目录加载所有工具配置（带错误信息）

        只加载 .yaml 和 .yml 扩展名的文件

        参数：
            dir_path: 目录路径

        返回：
            (成功加载的配置列表, 失败的文件列表[(文件名, 错误信息)])
        """
        path = Path(dir_path)
        if not path.exists():
            return [], []

        configs: list[ToolConfigSchema] = []
        errors: list[tuple[str, str]] = []

        for file_path in path.iterdir():
            if file_path.is_file() and file_path.suffix in {".yaml", ".yml"}:
                try:
                    config = self.load_from_file(str(file_path))
                    configs.append(config)
                except (ToolConfigValidationError, Exception) as e:
                    errors.append((file_path.name, str(e)))

        return configs, errors

    def to_tool_entity(self, config: ToolConfigSchema) -> Tool:
        """将配置转换为 Tool 实体

        参数：
            config: ToolConfigSchema 实例

        返回：
            Tool 实体实例
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        # 转换参数
        parameters = [
            ToolParameter(
                name=p.name,
                type=p.type,
                description=p.description,
                required=p.required,
                default=p.default,
                enum=p.enum,
            )
            for p in config.parameters
        ]

        # 转换入口为实现配置
        entry = config.entry.copy()
        implementation_type = entry.pop("type")
        implementation_config = entry  # 剩余字段作为配置

        # 直接创建 Tool 实体（不使用 Tool.create() 以支持自定义 version）
        return Tool(
            id=f"tool_{uuid4().hex[:8]}",
            name=config.name,
            description=config.description,
            category=ToolCategory(config.category),
            status=ToolStatus.DRAFT,
            version=config.version,
            parameters=parameters,
            returns=config.returns,
            implementation_type=implementation_type,
            implementation_config=implementation_config,
            author=config.author,
            tags=config.tags,
            icon=config.icon,
            created_at=datetime.now(UTC),
        )

    def export_to_yaml(
        self,
        tool: Tool,
        shareable_scope: ShareableScope = ShareableScope.PRIVATE,
    ) -> str:
        """将 Tool 实体导出为 YAML

        参数：
            tool: Tool 实体
            shareable_scope: 可共享范围

        返回：
            YAML 格式的字符串
        """
        # 构建入口配置
        entry = {"type": tool.implementation_type}
        entry.update(tool.implementation_config)

        # 构建参数列表
        parameters = []
        for p in tool.parameters:
            param_dict: dict[str, Any] = {
                "name": p.name,
                "type": p.type,
                "description": p.description,
                "required": p.required,
            }
            if p.default is not None:
                param_dict["default"] = p.default
            if p.enum is not None:
                param_dict["enum"] = p.enum
            parameters.append(param_dict)

        # 构建配置字典
        config_dict: dict[str, Any] = {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category.value,
            "version": tool.version,
        }

        if tool.author:
            config_dict["author"] = tool.author
        if tool.tags:
            config_dict["tags"] = tool.tags
        if tool.icon:
            config_dict["icon"] = tool.icon
        if shareable_scope != ShareableScope.PRIVATE:
            config_dict["shareable_scope"] = shareable_scope.value

        config_dict["entry"] = entry

        if parameters:
            config_dict["parameters"] = parameters
        if tool.returns:
            config_dict["returns"] = tool.returns

        result = yaml.dump(
            config_dict,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        return str(result) if result else ""

    # =========================================================================
    # 私有方法
    # =========================================================================

    def _parse_dict(self, data: dict[str, Any]) -> ToolConfigSchema:
        """从字典解析配置

        参数：
            data: 配置字典

        返回：
            ToolConfigSchema 实例

        抛出：
            ToolConfigValidationError: 当验证失败时
        """
        # 验证必需字段
        self._validate_required_field(data, "name")
        self._validate_required_field(data, "description")
        self._validate_required_field(data, "category")
        self._validate_required_field(data, "entry")

        # 验证 name 非空
        if not data["name"] or not str(data["name"]).strip():
            raise ToolConfigValidationError("name 不能为空", field="name")

        # 验证分类
        category = str(data["category"]).lower()
        if category not in self.VALID_CATEGORIES:
            valid_categories = ", ".join(sorted(self.VALID_CATEGORIES))
            raise ToolConfigValidationError(
                f"无效的 category '{category}'，有效值: {valid_categories}",
                field="category",
            )

        # 验证入口
        entry = data["entry"]
        if not isinstance(entry, dict):
            raise ToolConfigValidationError("entry 必须是一个字典", field="entry")

        if "type" not in entry:
            raise ToolConfigValidationError("entry.type 是必需的", field="entry.type")

        entry_type = str(entry["type"]).lower()
        if entry_type not in self.VALID_ENTRY_TYPES:
            valid_types = ", ".join(sorted(self.VALID_ENTRY_TYPES))
            raise ToolConfigValidationError(
                f"无效的 entry.type '{entry_type}'，有效值: {valid_types}",
                field="entry.type",
            )

        # 解析参数
        parameters = self._parse_parameters(data.get("parameters", []))

        # 解析可共享范围
        shareable_scope = self._parse_shareable_scope(data.get("shareable_scope", "private"))

        # 版本处理：确保是字符串
        version = str(data.get("version", "1.0.0"))

        return ToolConfigSchema(
            name=str(data["name"]).strip(),
            description=str(data["description"]).strip(),
            category=category,
            entry=entry,
            version=version,
            author=str(data.get("author", "")),
            tags=data.get("tags", []),
            icon=data.get("icon"),
            shareable_scope=shareable_scope,
            parameters=parameters,
            returns=data.get("returns", {}),
        )

    def _validate_required_field(self, data: dict[str, Any], field: str) -> None:
        """验证必需字段

        参数：
            data: 配置字典
            field: 字段名

        抛出：
            ToolConfigValidationError: 当字段缺失时
        """
        if field not in data:
            raise ToolConfigValidationError(f"缺少必需字段: {field}", field=field)

    def _parse_parameters(self, params_data: list[dict[str, Any]]) -> list[ToolParameterSchema]:
        """解析参数列表

        参数：
            params_data: 参数配置列表

        返回：
            ToolParameterSchema 列表

        抛出：
            ToolConfigValidationError: 当验证失败时
        """
        if not isinstance(params_data, list):
            return []

        parameters: list[ToolParameterSchema] = []
        for i, param in enumerate(params_data):
            if not isinstance(param, dict):
                continue

            # 验证必需字段
            for field_name in ["name", "type", "description"]:
                if field_name not in param:
                    raise ToolConfigValidationError(
                        f"参数 {i} 缺少必需字段: {field_name}",
                        field=f"parameters[{i}].{field_name}",
                    )

            # 验证参数类型
            param_type = str(param["type"]).lower()
            if param_type not in self.VALID_PARAM_TYPES:
                valid_types = ", ".join(sorted(self.VALID_PARAM_TYPES))
                raise ToolConfigValidationError(
                    f"参数 '{param['name']}' 的 type '{param_type}' 无效，有效值: {valid_types}",
                    field=f"parameters[{i}].type",
                )

            parameters.append(
                ToolParameterSchema(
                    name=str(param["name"]),
                    type=param_type,
                    description=str(param["description"]),
                    required=bool(param.get("required", False)),
                    default=param.get("default"),
                    enum=param.get("enum"),
                )
            )

        return parameters

    def _parse_shareable_scope(self, scope_value: str) -> ShareableScope:
        """解析可共享范围

        参数：
            scope_value: 范围字符串

        返回：
            ShareableScope 枚举值
        """
        scope_map = {
            "private": ShareableScope.PRIVATE,
            "team": ShareableScope.TEAM,
            "public": ShareableScope.PUBLIC,
        }
        return scope_map.get(str(scope_value).lower(), ShareableScope.PRIVATE)

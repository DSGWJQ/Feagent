"""统一定义系统 - ToolEngine 与 NodeRegistry 打通

业务定义：
- 统一 Schema 格式，支持节点和工具
- 统一注册中心，管理所有定义
- 统一验证器，共享验证逻辑
- 统一执行器适配器，桥接现有执行器

设计原则：
- 向后兼容现有 NodeRegistry 和 ToolEngine
- 共享 Schema、验证逻辑、执行器
- 支持 YAML 定义加载
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import yaml

# =============================================================================
# 枚举定义
# =============================================================================


class DefinitionKind(str, Enum):
    """定义类型枚举

    - NODE: 工作流节点
    - TOOL: 独立工具
    """

    NODE = "node"
    TOOL = "tool"


# =============================================================================
# 统一参数定义
# =============================================================================


@dataclass
class UnifiedParameter:
    """统一参数定义

    属性：
    - name: 参数名称
    - type: 参数类型 (string, number, boolean, object, array, any)
    - description: 参数描述
    - required: 是否必填
    - default: 默认值
    - enum: 枚举值列表
    - constraints: 约束条件 (min, max, pattern 等)
    """

    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None
    enum: list[str] | None = None
    constraints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        data: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            data["default"] = self.default
        if self.enum is not None:
            data["enum"] = self.enum
        if self.constraints:
            data["constraints"] = self.constraints
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedParameter":
        """从字典反序列化"""
        return cls(
            name=data["name"],
            type=data.get("type", "any"),
            description=data.get("description", ""),
            required=data.get("required", False),
            default=data.get("default"),
            enum=data.get("enum"),
            constraints=data.get("constraints", {}),
        )


# =============================================================================
# 统一定义
# =============================================================================


@dataclass
class UnifiedDefinition:
    """统一定义

    支持节点和工具的统一 Schema 格式。

    属性：
    - name: 定义名称（唯一标识）
    - kind: 定义类型（NODE 或 TOOL）
    - description: 描述
    - version: 版本号
    - parameters: 参数列表
    - returns: 返回值 Schema
    - executor_type: 执行器类型
    - category: 分类（仅工具）
    - tags: 标签列表
    - allowed_child_types: 允许的子节点类型（仅节点）
    - implementation_config: 实现配置
    """

    name: str
    kind: DefinitionKind
    description: str
    version: str
    parameters: list[dict[str, Any]] = field(default_factory=list)
    returns: dict[str, Any] = field(default_factory=dict)
    executor_type: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    allowed_child_types: list[str] = field(default_factory=list)
    implementation_config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """初始化后处理：将 UnifiedParameter 转换为字典"""
        normalized_params: list[dict[str, Any]] = []
        for p in self.parameters:
            if isinstance(p, dict):
                normalized_params.append(p)
            elif isinstance(p, UnifiedParameter):
                normalized_params.append(p.to_dict())
            else:
                # 尝试转换为字典
                normalized_params.append(dict(p))  # type: ignore[arg-type]
        self.parameters = normalized_params

    def get_parameter(self, name: str) -> dict[str, Any] | None:
        """获取参数定义"""
        for p in self.parameters:
            if p.get("name") == name:
                return p
        return None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        data: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind.value,
            "description": self.description,
            "version": self.version,
            "parameters": self.parameters,
            "executor_type": self.executor_type,
        }
        if self.returns:
            data["returns"] = self.returns
        if self.category:
            data["category"] = self.category
        if self.tags:
            data["tags"] = self.tags
        if self.allowed_child_types:
            data["allowed_child_types"] = self.allowed_child_types
        if self.implementation_config:
            data["implementation_config"] = self.implementation_config
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedDefinition":
        """从字典反序列化"""
        kind_str = data.get("kind", "tool")
        kind = DefinitionKind(kind_str) if isinstance(kind_str, str) else kind_str

        return cls(
            name=data["name"],
            kind=kind,
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            parameters=data.get("parameters", []),
            returns=data.get("returns", {}),
            executor_type=data.get("executor_type", ""),
            category=data.get("category", ""),
            tags=data.get("tags", []),
            allowed_child_types=data.get("allowed_child_types", []),
            implementation_config=data.get("implementation_config", {}),
        )


# =============================================================================
# 统一注册中心
# =============================================================================


class UnifiedDefinitionRegistry:
    """统一定义注册中心

    管理所有节点和工具定义。

    功能：
    1. 注册/获取定义
    2. 按类型/分类/标签查询
    3. 支持覆盖注册
    """

    def __init__(self):
        """初始化注册中心"""
        self._definitions: dict[str, UnifiedDefinition] = {}
        self._by_kind: dict[DefinitionKind, list[str]] = {
            DefinitionKind.NODE: [],
            DefinitionKind.TOOL: [],
        }
        self._by_category: dict[str, list[str]] = {}
        self._by_tag: dict[str, list[str]] = {}

    def register(self, definition: UnifiedDefinition, overwrite: bool = False) -> None:
        """注册定义

        参数：
            definition: 统一定义
            overwrite: 是否覆盖已存在的定义

        异常：
            ValueError: 定义已存在且不允许覆盖
        """
        if definition.name in self._definitions and not overwrite:
            raise ValueError(f"定义 '{definition.name}' 已存在")

        # 如果是覆盖，先清理旧索引
        if definition.name in self._definitions:
            self._remove_from_indices(definition.name)

        # 注册定义
        self._definitions[definition.name] = definition

        # 更新索引
        self._by_kind[definition.kind].append(definition.name)

        if definition.category:
            if definition.category not in self._by_category:
                self._by_category[definition.category] = []
            self._by_category[definition.category].append(definition.name)

        for tag in definition.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = []
            self._by_tag[tag].append(definition.name)

    def _remove_from_indices(self, name: str) -> None:
        """从索引中移除定义"""
        definition = self._definitions.get(name)
        if not definition:
            return

        if name in self._by_kind[definition.kind]:
            self._by_kind[definition.kind].remove(name)

        if definition.category and name in self._by_category.get(definition.category, []):
            self._by_category[definition.category].remove(name)

        for tag in definition.tags:
            if name in self._by_tag.get(tag, []):
                self._by_tag[tag].remove(name)

    def get(self, name: str) -> UnifiedDefinition | None:
        """获取定义"""
        return self._definitions.get(name)

    def has(self, name: str) -> bool:
        """检查定义是否存在"""
        return name in self._definitions

    def list_all(self) -> list[UnifiedDefinition]:
        """列出所有定义"""
        return list(self._definitions.values())

    def list_by_kind(self, kind: DefinitionKind) -> list[UnifiedDefinition]:
        """按类型列出定义"""
        names = self._by_kind.get(kind, [])
        return [self._definitions[n] for n in names if n in self._definitions]

    def list_by_category(self, category: str) -> list[UnifiedDefinition]:
        """按分类列出定义"""
        names = self._by_category.get(category, [])
        return [self._definitions[n] for n in names if n in self._definitions]

    def search_by_tag(self, tag: str) -> list[UnifiedDefinition]:
        """按标签搜索定义"""
        names = self._by_tag.get(tag, [])
        return [self._definitions[n] for n in names if n in self._definitions]


# =============================================================================
# 验证结果
# =============================================================================


@dataclass
class UnifiedValidationResult:
    """统一验证结果"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    validated_params: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 统一验证器
# =============================================================================


class UnifiedValidator:
    """统一验证器

    验证参数是否符合定义的 Schema。

    功能：
    1. 验证必填参数
    2. 验证类型匹配
    3. 验证枚举约束
    4. 验证范围约束
    5. 填充默认值
    6. 严格模式检测多余参数
    """

    # 类型映射
    TYPE_VALIDATORS = {
        "string": lambda v: isinstance(v, str),
        "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "any": lambda v: True,
    }

    def __init__(self, strict_mode: bool = False):
        """初始化验证器

        参数：
            strict_mode: 严格模式，检测多余参数
        """
        self._strict_mode = strict_mode

    def validate(
        self, definition: UnifiedDefinition, params: dict[str, Any]
    ) -> UnifiedValidationResult:
        """验证参数

        参数：
            definition: 统一定义
            params: 调用参数

        返回：
            验证结果
        """
        errors: list[str] = []
        validated_params: dict[str, Any] = {}

        # 构建参数定义映射
        param_defs: dict[str, dict[str, Any]] = {p["name"]: p for p in definition.parameters}

        # 1. 检查必填参数
        for param in definition.parameters:
            name = param["name"]
            required = param.get("required", False)
            default = param.get("default")

            if required and name not in params:
                if default is None:
                    errors.append(f"缺少必填参数: {name}")

        # 2. 验证已提供的参数
        for name, value in params.items():
            if name not in param_defs:
                if self._strict_mode:
                    errors.append(f"未定义的参数: {name}")
                continue

            param_def = param_defs[name]

            # 跳过 None 值的可选参数
            if value is None and not param_def.get("required", False):
                continue

            # 检查类型
            expected_type = param_def.get("type", "any")
            if value is not None and not self._check_type(value, expected_type):
                actual_type = type(value).__name__
                errors.append(f"参数 '{name}' 类型错误: 期望 {expected_type}, 实际 {actual_type}")
                continue

            # 检查枚举
            enum_values = param_def.get("enum")
            if enum_values is not None and value not in enum_values:
                errors.append(f"参数 '{name}' 的值 '{value}' 不在枚举列表 {enum_values} 中")
                continue

            # 检查范围约束
            constraints = param_def.get("constraints", {})
            if constraints:
                constraint_error = self._check_constraints(name, value, constraints)
                if constraint_error:
                    errors.append(constraint_error)
                    continue

            validated_params[name] = value

        # 3. 填充默认值
        for param in definition.parameters:
            name = param["name"]
            if name not in validated_params:
                default = param.get("default")
                if default is not None:
                    validated_params[name] = default

        return UnifiedValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            validated_params=validated_params if len(errors) == 0 else {},
        )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型"""
        validator = self.TYPE_VALIDATORS.get(expected_type.lower())
        if validator is None:
            return True
        return validator(value)

    def _check_constraints(self, name: str, value: Any, constraints: dict[str, Any]) -> str | None:
        """检查约束条件"""
        min_val = constraints.get("min")
        max_val = constraints.get("max")

        if min_val is not None and value < min_val:
            return f"参数 '{name}' 的值 {value} 小于最小值 {min_val}"

        if max_val is not None and value > max_val:
            return f"参数 '{name}' 的值 {value} 大于最大值 {max_val}"

        return None


# =============================================================================
# 执行器协议
# =============================================================================


class UnifiedExecutorProtocol(Protocol):
    """统一执行器协议"""

    async def execute(
        self,
        definition: UnifiedDefinition,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """执行定义"""
        ...


# =============================================================================
# 统一执行器适配器
# =============================================================================


class UnifiedExecutorAdapter:
    """统一执行器适配器

    桥接现有的 NodeExecutor 和 ToolExecutor。
    """

    def __init__(self):
        """初始化适配器"""
        self._executors: dict[str, Any] = {}

    def register_executor(self, executor_type: str, executor: Any) -> None:
        """注册执行器

        参数：
            executor_type: 执行器类型
            executor: 执行器实例
        """
        self._executors[executor_type] = executor

    def has_executor(self, executor_type: str) -> bool:
        """检查执行器是否存在"""
        return executor_type in self._executors

    async def execute(
        self,
        definition: UnifiedDefinition,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """执行定义

        参数：
            definition: 统一定义
            params: 参数
            context: 上下文

        返回：
            执行结果

        异常：
            ValueError: 执行器未找到
        """
        executor = self._executors.get(definition.executor_type)
        if executor is None:
            raise ValueError(f"执行器 '{definition.executor_type}' 未找到")

        # 调用执行器
        return await executor.execute(definition, params, context)


# =============================================================================
# 转换函数：从 NodeRegistry 转换
# =============================================================================


def convert_node_schema_to_unified(
    node_type: Any,  # NodeType
    schema: dict[str, Any],
    description: str = "",
) -> UnifiedDefinition:
    """从 NodeRegistry Schema 转换为统一定义

    参数：
        node_type: 节点类型枚举
        schema: 节点 Schema
        description: 描述

    返回：
        统一定义
    """
    # 提取参数
    parameters = []
    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])

    for prop_name, prop_def in properties.items():
        param: dict[str, Any] = {
            "name": prop_name,
            "type": prop_def.get("type", "any"),
            "description": prop_def.get("description", ""),
            "required": prop_name in required_fields or prop_def.get("required", False),
        }
        if "default" in prop_def:
            param["default"] = prop_def["default"]
        parameters.append(param)

    # 获取节点类型名称
    type_name = node_type.value if hasattr(node_type, "value") else str(node_type)

    return UnifiedDefinition(
        name=type_name,
        kind=DefinitionKind.NODE,
        description=description,
        version="1.0.0",
        parameters=parameters,
        executor_type=type_name,
    )


def convert_node_schema_registry_to_unified(
    node_schema_registry: Any,  # NodeSchemaRegistry
) -> list[UnifiedDefinition]:
    """从 NodeSchemaRegistry 转换所有定义

    参数：
        node_schema_registry: NodeSchemaRegistry 实例

    返回：
        统一定义列表
    """
    definitions = []

    for schema in node_schema_registry.list_all():
        # 提取参数
        parameters = []
        input_schema = schema.input_schema
        properties = input_schema.get("properties", {})
        required_fields = input_schema.get("required", [])

        for prop_name, prop_def in properties.items():
            param: dict[str, Any] = {
                "name": prop_name,
                "type": prop_def.get("type", "any"),
                "description": "",
                "required": prop_name in required_fields,
            }
            if "default" in prop_def:
                param["default"] = prop_def["default"]
            parameters.append(param)

        definition = UnifiedDefinition(
            name=schema.node_type,
            kind=DefinitionKind.NODE,
            description=schema.description,
            version="1.0.0",
            parameters=parameters,
            returns=schema.output_schema,
            executor_type=schema.node_type,
            allowed_child_types=schema.allowed_child_types,
        )
        definitions.append(definition)

    return definitions


# =============================================================================
# 转换函数：从 Tool 实体转换
# =============================================================================


def convert_tool_to_unified(tool: Any) -> UnifiedDefinition:
    """从 Tool 实体转换为统一定义

    参数：
        tool: Tool 实体

    返回：
        统一定义
    """
    # 转换参数
    parameters = []
    for p in tool.parameters:
        param: dict[str, Any] = {
            "name": p.name,
            "type": p.type,
            "description": p.description,
            "required": p.required,
        }
        if p.default is not None:
            param["default"] = p.default
        if p.enum is not None:
            param["enum"] = p.enum
        parameters.append(param)

    # 获取分类名称
    category = tool.category.value if hasattr(tool.category, "value") else str(tool.category)

    return UnifiedDefinition(
        name=tool.name,
        kind=DefinitionKind.TOOL,
        description=tool.description,
        version=tool.version,
        parameters=parameters,
        returns=tool.returns or {},
        executor_type=tool.implementation_type,
        category=category,
        tags=tool.tags or [],
        implementation_config=tool.implementation_config or {},
    )


# =============================================================================
# 导入函数：从 NodeRegistry 导入
# =============================================================================


def import_from_node_registry(
    node_registry: Any,  # NodeRegistry
    unified_registry: UnifiedDefinitionRegistry,
) -> None:
    """从 NodeRegistry 导入定义到统一注册中心

    参数：
        node_registry: NodeRegistry 实例
        unified_registry: 统一注册中心
    """

    # 节点描述映射
    descriptions = {
        "start": "工作流起始节点",
        "end": "工作流结束节点",
        "llm": "大语言模型调用节点",
        "condition": "条件分支节点",
        "loop": "循环节点",
        "parallel": "并行执行节点",
        "api": "HTTP API 调用节点",
        "code": "代码执行节点",
        "mcp": "MCP 工具调用节点",
        "knowledge": "知识库检索节点",
        "classify": "分类节点",
        "template": "模板渲染节点",
        "generic": "通用容器节点",
    }

    for node_type in node_registry.get_all_types():
        schema = node_registry.get_schema(node_type)
        type_name = node_type.value if hasattr(node_type, "value") else str(node_type)

        definition = convert_node_schema_to_unified(
            node_type=node_type,
            schema=schema,
            description=descriptions.get(type_name, ""),
        )

        unified_registry.register(definition, overwrite=True)


# =============================================================================
# YAML 加载器
# =============================================================================


class UnifiedYAMLLoader:
    """统一 YAML 加载器

    从 YAML 文件加载统一定义。
    """

    def parse(self, yaml_content: str) -> UnifiedDefinition:
        """解析 YAML 内容

        参数：
            yaml_content: YAML 字符串

        返回：
            统一定义

        异常：
            ValueError: YAML 内容无效
        """
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            raise ValueError("YAML 内容必须是字典格式")
        return UnifiedDefinition.from_dict(data)

    def load_from_file(self, file_path: str) -> UnifiedDefinition:
        """从文件加载定义

        参数：
            file_path: 文件路径

        返回：
            统一定义
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return self.parse(content)

    def load_from_directory(self, dir_path: str) -> list[UnifiedDefinition]:
        """从目录加载所有定义

        参数：
            dir_path: 目录路径

        返回：
            统一定义列表
        """
        path = Path(dir_path)
        definitions = []

        for file_path in path.iterdir():
            if file_path.is_file() and file_path.suffix in {".yaml", ".yml"}:
                try:
                    definition = self.load_from_file(str(file_path))
                    definitions.append(definition)
                except Exception:
                    # 跳过无效文件
                    pass

        return definitions


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    # 枚举
    "DefinitionKind",
    # 数据类
    "UnifiedParameter",
    "UnifiedDefinition",
    "UnifiedValidationResult",
    # 注册中心
    "UnifiedDefinitionRegistry",
    # 验证器
    "UnifiedValidator",
    # 执行器
    "UnifiedExecutorProtocol",
    "UnifiedExecutorAdapter",
    # 转换函数
    "convert_node_schema_to_unified",
    "convert_node_schema_registry_to_unified",
    "convert_tool_to_unified",
    "import_from_node_registry",
    # 加载器
    "UnifiedYAMLLoader",
]

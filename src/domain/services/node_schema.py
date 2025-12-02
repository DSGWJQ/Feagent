"""通用节点Schema约束 - 阶段6

业务定义：
- 定义输入/输出类型
- 允许的子节点类型
- WorkflowAgent创建节点时执行schema校验
- 父子节点展开保持类型一致

设计原则：
- 类型安全：严格的输入输出类型校验
- 层次约束：控制父子节点类型关系
- 文档化：Schema可生成文档

核心功能：
- NodeSchema: 节点Schema定义
- NodeSchemaRegistry: Schema注册表
- NodeSchemaValidator: Schema校验器
- SchemaValidatingWorkflowAgent: 带校验的工作流Agent
"""

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ==================== Schema约束 ====================


@dataclass
class SchemaConstraint:
    """Schema约束

    属性：
    - field_name: 字段名
    - constraint_type: 约束类型（range, enum, pattern, etc.）
    - min_value: 最小值（用于range）
    - max_value: 最大值（用于range）
    - allowed_values: 允许的值列表（用于enum）
    - pattern: 正则模式（用于pattern）
    """

    field_name: str
    constraint_type: str
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[Any] = field(default_factory=list)
    pattern: str | None = None


# ==================== 节点Schema ====================


@dataclass
class NodeSchema:
    """节点Schema

    定义节点的输入输出类型和约束。

    属性：
    - node_type: 节点类型
    - input_schema: 输入Schema（JSON Schema格式）
    - output_schema: 输出Schema（JSON Schema格式）
    - allowed_child_types: 允许的子节点类型列表
    - constraints: 额外约束列表
    - description: 描述
    """

    node_type: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    allowed_child_types: list[str] = field(default_factory=list)
    constraints: list[SchemaConstraint] = field(default_factory=list)
    description: str = ""


# ==================== 校验结果 ====================


@dataclass
class SchemaValidationResult:
    """Schema校验结果"""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)


# ==================== 预定义Schema ====================


def _create_predefined_schemas() -> dict[str, NodeSchema]:
    """创建预定义节点Schema"""
    schemas = {}

    # START节点
    schemas["start"] = NodeSchema(
        node_type="start",
        input_schema={
            "type": "object",
            "properties": {
                "trigger_type": {"type": "string", "default": "manual"},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "triggered": {"type": "boolean"},
                "timestamp": {"type": "string"},
            },
        },
        allowed_child_types=[],  # 叶子节点
        description="工作流起始节点",
    )

    # END节点
    schemas["end"] = NodeSchema(
        node_type="end",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "completed": {"type": "boolean"},
            },
        },
        allowed_child_types=[],
        description="工作流结束节点",
    )

    # LLM节点
    schemas["llm"] = NodeSchema(
        node_type="llm",
        input_schema={
            "type": "object",
            "properties": {
                "model": {"type": "string", "default": "gpt-4"},
                "temperature": {"type": "number", "default": 0.7},
                "max_tokens": {"type": "integer"},
                "system_prompt": {"type": "string"},
                "user_prompt": {"type": "string"},
            },
            "required": ["user_prompt"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "tokens_used": {"type": "integer"},
            },
            "required": ["content"],
        },
        allowed_child_types=[],
        constraints=[
            SchemaConstraint(
                field_name="temperature",
                constraint_type="range",
                min_value=0.0,
                max_value=2.0,
            )
        ],
        description="大语言模型调用节点",
    )

    # API节点
    schemas["api"] = NodeSchema(
        node_type="api",
        input_schema={
            "type": "object",
            "properties": {
                "method": {"type": "string", "default": "GET"},
                "url": {"type": "string"},
                "headers": {"type": "object", "default": {}},
                "body": {"type": "object"},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "integer"},
                "data": {"type": "object"},
            },
        },
        allowed_child_types=[],
        description="HTTP API调用节点",
    )

    # CODE节点
    schemas["code"] = NodeSchema(
        node_type="code",
        input_schema={
            "type": "object",
            "properties": {
                "language": {"type": "string", "default": "python"},
                "code": {"type": "string"},
                "inputs": {"type": "array", "default": []},
                "outputs": {"type": "array", "default": []},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "object"},
                "stdout": {"type": "string"},
            },
        },
        allowed_child_types=[],
        description="代码执行节点",
    )

    # CONDITION节点
    schemas["condition"] = NodeSchema(
        node_type="condition",
        input_schema={
            "type": "object",
            "properties": {
                "condition_type": {"type": "string", "default": "expression"},
                "expression": {"type": "string"},
                "branches": {"type": "array", "default": []},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "branch": {"type": "string"},
                "result": {"type": "boolean"},
            },
        },
        allowed_child_types=[],
        description="条件分支节点",
    )

    # LOOP节点
    schemas["loop"] = NodeSchema(
        node_type="loop",
        input_schema={
            "type": "object",
            "properties": {
                "loop_type": {"type": "string", "default": "for_each"},
                "max_iterations": {"type": "integer", "default": 100},
                "collection": {"type": "string"},
                "condition": {"type": "string"},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "iterations": {"type": "integer"},
                "results": {"type": "array"},
            },
        },
        allowed_child_types=[],
        description="循环节点",
    )

    # PARALLEL节点
    schemas["parallel"] = NodeSchema(
        node_type="parallel",
        input_schema={
            "type": "object",
            "properties": {
                "branches": {"type": "array", "default": []},
                "wait_all": {"type": "boolean", "default": True},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "results": {"type": "array"},
            },
        },
        allowed_child_types=[],
        description="并行执行节点",
    )

    # KNOWLEDGE节点
    schemas["knowledge"] = NodeSchema(
        node_type="knowledge",
        input_schema={
            "type": "object",
            "properties": {
                "knowledge_base_id": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "documents": {"type": "array"},
                "scores": {"type": "array"},
            },
        },
        allowed_child_types=[],
        description="知识库检索节点",
    )

    # CLASSIFY节点
    schemas["classify"] = NodeSchema(
        node_type="classify",
        input_schema={
            "type": "object",
            "properties": {
                "categories": {"type": "array", "default": []},
                "input": {"type": "string"},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
        allowed_child_types=[],
        description="分类节点",
    )

    # TEMPLATE节点
    schemas["template"] = NodeSchema(
        node_type="template",
        input_schema={
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "variables": {"type": "object", "default": {}},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "rendered": {"type": "string"},
            },
        },
        allowed_child_types=[],
        description="模板渲染节点",
    )

    # MCP节点
    schemas["mcp"] = NodeSchema(
        node_type="mcp",
        input_schema={
            "type": "object",
            "properties": {
                "server": {"type": "string"},
                "tool": {"type": "string"},
                "arguments": {"type": "object", "default": {}},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "object"},
            },
        },
        allowed_child_types=[],
        description="MCP工具调用节点",
    )

    # GENERIC节点（可包含子节点）
    schemas["generic"] = NodeSchema(
        node_type="generic",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": [],
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "object"},
            },
        },
        allowed_child_types=[
            "llm",
            "api",
            "code",
            "condition",
            "loop",
            "parallel",
            "knowledge",
            "classify",
            "template",
            "mcp",
            "generic",  # 允许嵌套
        ],
        description="通用容器节点，可包含子节点",
    )

    return schemas


PREDEFINED_SCHEMAS = _create_predefined_schemas()


# ==================== Schema注册表 ====================


class NodeSchemaRegistry:
    """节点Schema注册表

    职责：
    1. 管理节点Schema
    2. 提供预定义Schema
    3. 支持自定义Schema注册

    使用示例：
        registry = NodeSchemaRegistry()
        schema = registry.get_schema("llm")
        registry.register(custom_schema)
    """

    def __init__(self):
        """初始化注册表"""
        self._schemas: dict[str, NodeSchema] = {}
        self._register_predefined()

    def _register_predefined(self) -> None:
        """注册预定义Schema"""
        for node_type, schema in PREDEFINED_SCHEMAS.items():
            self._schemas[node_type] = schema

    def register(self, schema: NodeSchema) -> None:
        """注册Schema

        参数：
            schema: 节点Schema
        """
        self._schemas[schema.node_type] = schema

    def get_schema(self, node_type: str) -> NodeSchema | None:
        """获取Schema

        参数：
            node_type: 节点类型

        返回：
            节点Schema，不存在返回None
        """
        return self._schemas.get(node_type)

    def has_schema(self, node_type: str) -> bool:
        """检查Schema是否存在

        参数：
            node_type: 节点类型

        返回：
            是否存在
        """
        return node_type in self._schemas

    def list_all(self) -> list[NodeSchema]:
        """列出所有Schema

        返回：
            Schema列表
        """
        return list(self._schemas.values())


# ==================== Schema校验器 ====================


class NodeSchemaValidator:
    """节点Schema校验器

    职责：
    1. 验证输入配置
    2. 验证输出结构
    3. 检查子节点类型

    使用示例：
        validator = NodeSchemaValidator(schema)
        result = validator.validate_input(config)
        is_allowed = validator.is_child_type_allowed("llm")
    """

    def __init__(self, schema: NodeSchema):
        """初始化校验器

        参数：
            schema: 节点Schema
        """
        self.schema = schema

    def validate_input(self, config: dict[str, Any]) -> SchemaValidationResult:
        """验证输入配置

        参数：
            config: 配置字典

        返回：
            校验结果
        """
        errors = []
        input_schema = self.schema.input_schema

        # 检查必需字段
        required = input_schema.get("required", [])
        for field_name in required:
            if field_name not in config:
                errors.append(f"缺少必需字段: {field_name}")

        # 检查字段类型
        properties = input_schema.get("properties", {})
        for field_name, value in config.items():
            if field_name in properties:
                prop_def = properties[field_name]
                expected_type = prop_def.get("type")
                if not self._check_type(value, expected_type):
                    errors.append(
                        f"字段 {field_name} 类型错误: 期望 {expected_type}, 实际 {type(value).__name__}"
                    )

        # 检查约束
        for constraint in self.schema.constraints:
            error = self._check_constraint(config, constraint)
            if error:
                errors.append(error)

        return SchemaValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate_output(self, output: dict[str, Any]) -> SchemaValidationResult:
        """验证输出结构

        参数：
            output: 输出字典

        返回：
            校验结果
        """
        errors = []
        output_schema = self.schema.output_schema

        # 检查必需字段
        required = output_schema.get("required", [])
        for field_name in required:
            if field_name not in output:
                errors.append(f"输出缺少必需字段: {field_name}")

        return SchemaValidationResult(is_valid=len(errors) == 0, errors=errors)

    def is_child_type_allowed(self, child_type: str) -> bool:
        """检查子节点类型是否允许

        参数：
            child_type: 子节点类型

        返回：
            是否允许
        """
        return child_type in self.schema.allowed_child_types

    def can_have_children(self) -> bool:
        """检查是否可以有子节点

        返回：
            是否可以有子节点
        """
        return len(self.schema.allowed_child_types) > 0

    def _check_type(self, value: Any, expected_type: str | None) -> bool:
        """检查值类型

        参数：
            value: 实际值
            expected_type: 期望类型

        返回：
            是否匹配
        """
        if expected_type is None:
            return True

        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_mapping.get(expected_type)
        if expected is None:
            return True

        return isinstance(value, expected)

    def _check_constraint(self, config: dict[str, Any], constraint: SchemaConstraint) -> str | None:
        """检查约束

        参数：
            config: 配置
            constraint: 约束

        返回：
            错误信息，无错误返回None
        """
        value = config.get(constraint.field_name)
        if value is None:
            return None

        if constraint.constraint_type == "range":
            if constraint.min_value is not None and value < constraint.min_value:
                return f"字段 {constraint.field_name} 值 {value} 小于最小值 {constraint.min_value}"
            if constraint.max_value is not None and value > constraint.max_value:
                return f"字段 {constraint.field_name} 值 {value} 大于最大值 {constraint.max_value}"

        elif constraint.constraint_type == "enum":
            if value not in constraint.allowed_values:
                return f"字段 {constraint.field_name} 值 {value} 不在允许列表中"

        return None


# ==================== 带校验的WorkflowAgent ====================


@dataclass
class ValidatedNode:
    """已校验的节点"""

    id: str
    type: str
    config: dict[str, Any]
    children: list["ValidatedNode"] = field(default_factory=list)
    collapsed: bool = True


class SchemaValidatingWorkflowAgent:
    """带Schema校验的工作流Agent

    职责：
    1. 创建节点时验证Schema
    2. 添加子节点时验证类型
    3. 维护节点类型一致性

    使用示例：
        agent = SchemaValidatingWorkflowAgent()
        result = agent.create_node_with_validation(node_type="llm", config={...})
        result = agent.add_child_with_validation(parent_id, child_type, child_config)
    """

    def __init__(self, registry: NodeSchemaRegistry | None = None):
        """初始化

        参数：
            registry: Schema注册表
        """
        self.registry = registry or NodeSchemaRegistry()
        self._nodes: dict[str, ValidatedNode] = {}
        self._parent_map: dict[str, str] = {}  # child_id -> parent_id

    def create_node_with_validation(self, node_type: str, config: dict[str, Any]) -> dict[str, Any]:
        """创建并验证节点

        参数：
            node_type: 节点类型
            config: 节点配置

        返回：
            {success: bool, node: ValidatedNode | None, errors: list}
        """
        schema = self.registry.get_schema(node_type)
        if not schema:
            return {
                "success": False,
                "node": None,
                "errors": [f"未知节点类型: {node_type}"],
            }

        # 验证配置
        validator = NodeSchemaValidator(schema)
        result = validator.validate_input(config)

        if not result.is_valid:
            return {
                "success": False,
                "node": None,
                "errors": result.errors,
            }

        # 创建节点
        node = ValidatedNode(
            id=str(uuid4()),
            type=node_type,
            config=config,
        )

        self._nodes[node.id] = node

        return {
            "success": True,
            "node": node,
            "errors": [],
        }

    def add_child_with_validation(
        self,
        parent_id: str,
        child_type: str,
        child_config: dict[str, Any],
    ) -> dict[str, Any]:
        """添加并验证子节点

        参数：
            parent_id: 父节点ID
            child_type: 子节点类型
            child_config: 子节点配置

        返回：
            {success: bool, child_id: str | None, errors: list}
        """
        parent = self._nodes.get(parent_id)
        if not parent:
            return {
                "success": False,
                "child_id": None,
                "errors": [f"父节点不存在: {parent_id}"],
            }

        # 检查父节点是否允许子节点
        parent_schema = self.registry.get_schema(parent.type)
        if not parent_schema:
            return {
                "success": False,
                "child_id": None,
                "errors": [f"父节点Schema不存在: {parent.type}"],
            }

        validator = NodeSchemaValidator(parent_schema)

        if not validator.can_have_children():
            return {
                "success": False,
                "child_id": None,
                "errors": [f"节点类型 {parent.type} 不允许添加子节点"],
            }

        if not validator.is_child_type_allowed(child_type):
            return {
                "success": False,
                "child_id": None,
                "errors": [f"节点类型 {parent.type} 不允许子节点类型 {child_type}"],
            }

        # 验证子节点配置
        child_schema = self.registry.get_schema(child_type)
        if not child_schema:
            return {
                "success": False,
                "child_id": None,
                "errors": [f"未知子节点类型: {child_type}"],
            }

        child_validator = NodeSchemaValidator(child_schema)
        config_result = child_validator.validate_input(child_config)

        if not config_result.is_valid:
            return {
                "success": False,
                "child_id": None,
                "errors": config_result.errors,
            }

        # 创建子节点
        child = ValidatedNode(
            id=str(uuid4()),
            type=child_type,
            config=child_config,
        )

        parent.children.append(child)
        self._nodes[child.id] = child
        self._parent_map[child.id] = parent_id

        return {
            "success": True,
            "child_id": child.id,
            "errors": [],
        }

    def expand_node(self, node_id: str) -> dict[str, Any]:
        """展开节点

        参数：
            node_id: 节点ID

        返回：
            展开的节点结构
        """
        node = self._nodes.get(node_id)
        if not node:
            return {"error": f"节点不存在: {node_id}"}

        node.collapsed = False

        return {
            "id": node.id,
            "type": node.type,
            "config": node.config,
            "collapsed": node.collapsed,
            "children": [
                {
                    "id": c.id,
                    "type": c.type,
                    "config": c.config,
                }
                for c in node.children
            ],
        }

    def collapse_node(self, node_id: str) -> dict[str, Any]:
        """折叠节点

        参数：
            node_id: 节点ID

        返回：
            折叠的节点结构
        """
        node = self._nodes.get(node_id)
        if not node:
            return {"error": f"节点不存在: {node_id}"}

        node.collapsed = True

        return {
            "id": node.id,
            "type": node.type,
            "collapsed": node.collapsed,
            "child_count": len(node.children),
        }

    def expand_node_recursive(self, node_id: str) -> dict[str, Any]:
        """递归展开节点

        参数：
            node_id: 节点ID

        返回：
            完整的嵌套结构
        """
        node = self._nodes.get(node_id)
        if not node:
            return {"error": f"节点不存在: {node_id}"}

        node.collapsed = False

        def expand_child(child: ValidatedNode) -> dict[str, Any]:
            child.collapsed = False
            return {
                "id": child.id,
                "type": child.type,
                "config": child.config,
                "collapsed": child.collapsed,
                "children": [expand_child(c) for c in child.children],
            }

        return {
            "id": node.id,
            "type": node.type,
            "config": node.config,
            "collapsed": node.collapsed,
            "children": [expand_child(c) for c in node.children],
        }

    def get_node(self, node_id: str) -> ValidatedNode | None:
        """获取节点

        参数：
            node_id: 节点ID

        返回：
            节点
        """
        return self._nodes.get(node_id)


# ==================== Schema文档生成器 ====================


class SchemaDocGenerator:
    """Schema文档生成器

    职责：
    1. 生成单个Schema文档
    2. 生成完整Schema文档

    使用示例：
        generator = SchemaDocGenerator(registry)
        doc = generator.generate_doc("llm")
        full_doc = generator.generate_all()
    """

    def __init__(self, registry: NodeSchemaRegistry):
        """初始化

        参数：
            registry: Schema注册表
        """
        self.registry = registry

    def generate_doc(self, node_type: str) -> str:
        """生成单个节点的Schema文档

        参数：
            node_type: 节点类型

        返回：
            Markdown格式的文档
        """
        schema = self.registry.get_schema(node_type)
        if not schema:
            return f"# {node_type}\n\n未找到该节点类型的Schema。\n"

        lines = []
        lines.append(f"# {node_type.upper()} 节点")
        lines.append("")
        lines.append(f"**描述**: {schema.description}")
        lines.append("")

        # 输入Schema
        lines.append("## 输入 (Input)")
        lines.append("")
        self._format_properties(lines, schema.input_schema)

        # 输出Schema
        lines.append("")
        lines.append("## 输出 (Output)")
        lines.append("")
        self._format_properties(lines, schema.output_schema)

        # 约束
        if schema.constraints:
            lines.append("")
            lines.append("## 约束 (Constraints)")
            lines.append("")
            for c in schema.constraints:
                if c.constraint_type == "range":
                    lines.append(f"- **{c.field_name}**: 范围 [{c.min_value}, {c.max_value}]")
                elif c.constraint_type == "enum":
                    lines.append(f"- **{c.field_name}**: 可选值 {c.allowed_values}")

        # 子节点
        if schema.allowed_child_types:
            lines.append("")
            lines.append("## 允许的子节点类型")
            lines.append("")
            for child_type in schema.allowed_child_types:
                lines.append(f"- `{child_type}`")

        return "\n".join(lines)

    def _format_properties(self, lines: list[str], schema: dict[str, Any]) -> None:
        """格式化属性"""
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if not properties:
            lines.append("*无属性*")
            return

        lines.append("| 字段 | 类型 | 必需 | 默认值 |")
        lines.append("|------|------|------|--------|")

        for name, prop in properties.items():
            prop_type = prop.get("type", "any")
            is_required = "是" if name in required else "否"
            default = prop.get("default", "-")
            lines.append(f"| {name} | {prop_type} | {is_required} | {default} |")

    def generate_all(self) -> str:
        """生成完整的Schema文档

        返回：
            Markdown格式的完整文档
        """
        lines = []
        lines.append("# 节点Schema文档")
        lines.append("")
        lines.append("本文档描述了所有可用节点类型的Schema定义。")
        lines.append("")
        lines.append("---")
        lines.append("")

        for schema in self.registry.list_all():
            lines.append(self.generate_doc(schema.node_type))
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)


# 导出
__all__ = [
    # 数据结构
    "SchemaConstraint",
    "NodeSchema",
    "SchemaValidationResult",
    "ValidatedNode",
    # 注册表
    "NodeSchemaRegistry",
    "PREDEFINED_SCHEMAS",
    # 校验器
    "NodeSchemaValidator",
    # Agent
    "SchemaValidatingWorkflowAgent",
    # 文档生成
    "SchemaDocGenerator",
]

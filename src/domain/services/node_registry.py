"""节点注册中心 (Node Registry) - 多Agent协作系统的节点管理

业务定义：
- NodeRegistry 管理所有可用的节点类型
- 对话Agent通过注册中心获取节点模板和创建节点
- 支持预定义节点类型和动态注册节点类型

设计原则：
- 预定义13种核心节点类型
- 每种节点有配置Schema和默认模板
- 支持配置验证
- 节点有生命周期管理

核心概念：
- NodeType: 节点类型枚举
- NodeRegistry: 节点注册中心
- NodeFactory: 节点工厂
- Node: 节点实例
- NodeLifecycle: 节点生命周期
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class NodeType(str, Enum):
    """节点类型枚举

    预定义16种核心节点类型：
    - 基础节点：START, END
    - 控制流节点：CONDITION, LOOP, PARALLEL
    - AI能力节点：LLM, KNOWLEDGE, CLASSIFY, TEMPLATE
    - 执行节点：API, CODE, MCP, FILE, TRANSFORM
    - 交互节点：HUMAN
    - 通用节点：GENERIC
    """

    # 基础节点
    START = "start"
    END = "end"

    # 控制流节点
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"

    # AI能力节点
    LLM = "llm"
    KNOWLEDGE = "knowledge"
    CLASSIFY = "classify"
    TEMPLATE = "template"

    # 执行节点
    API = "api"
    CODE = "code"
    MCP = "mcp"
    FILE = "file"  # 文件操作节点
    TRANSFORM = "transform"  # 数据转换节点

    # 交互节点
    HUMAN = "human"  # 人机交互节点

    # 通用节点
    GENERIC = "generic"


class NodeLifecycle(str, Enum):
    """节点生命周期

    生命周期转换路径：
    TEMPORARY → PERSISTED → TEMPLATE → GLOBAL

    - TEMPORARY: 临时节点，对话Agent创建，执行完销毁
    - PERSISTED: 持久化节点，保存到工作流中
    - TEMPLATE: 模板节点，可被复用
    - GLOBAL: 全局节点，系统级共享
    """

    TEMPORARY = "temporary"
    PERSISTED = "persisted"
    TEMPLATE = "template"
    GLOBAL = "global"


# 有效的生命周期转换路径
VALID_LIFECYCLE_TRANSITIONS = {
    NodeLifecycle.TEMPORARY: [NodeLifecycle.PERSISTED],
    NodeLifecycle.PERSISTED: [NodeLifecycle.TEMPLATE],
    NodeLifecycle.TEMPLATE: [NodeLifecycle.GLOBAL],
    NodeLifecycle.GLOBAL: [],  # 全局节点不能再提升
}


# ==================== 阶段 4：节点生命周期与模板复用 ====================


class NodeScope(str, Enum):
    """节点作用域（阶段4新增）

    定义节点的可见性和复用范围：
    - WORKFLOW: 仅在当前工作流可用
    - TEMPLATE: 可被其他工作流复用（模板）
    - GLOBAL: 系统级全局可用
    """

    WORKFLOW = "workflow"
    TEMPLATE = "template"
    GLOBAL = "global"


class PromotionStatus(str, Enum):
    """升级状态（阶段4新增）

    表示节点的升级状态：
    - DRAFT: 草稿状态
    - PROMOTED: 已升级为模板
    - PUBLISHED: 已发布为全局
    """

    DRAFT = "draft"
    PROMOTED = "promoted"
    PUBLISHED = "published"


class NodeConfigError(Exception):
    """节点配置错误异常

    当节点配置验证失败时抛出。
    """

    pass


MAX_NODE_DEPTH = 5  # 最大嵌套深度限制


@dataclass
class Node:
    """节点实例

    属性：
    - id: 节点唯一标识
    - type: 节点类型
    - config: 节点配置
    - lifecycle: 生命周期
    - children: 子节点列表（仅GENERIC类型）
    - collapsed: 是否折叠（仅GENERIC类型）
    - parent_id: 父节点ID（Phase 9 新增）
    - scope: 作用域（阶段4新增）
    - version: 版本号（阶段4新增）
    - promotion_status: 升级状态（阶段4新增）
    - template_name: 模板名称（阶段4新增）
    - source_template_id: 来源模板ID（阶段4新增）

    使用示例：
        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"model": "gpt-4", "user_prompt": "分析数据"}
        )
    """

    id: str
    type: NodeType
    config: dict[str, Any] = field(default_factory=dict)
    lifecycle: NodeLifecycle = NodeLifecycle.TEMPORARY
    children: list["Node"] = field(default_factory=list)
    collapsed: bool = True  # GENERIC节点默认折叠
    parent_id: str | None = None  # Phase 9: 父节点引用

    # 阶段4新增字段
    scope: NodeScope = NodeScope.WORKFLOW
    version: int = 1
    promotion_status: PromotionStatus = PromotionStatus.DRAFT
    template_name: str | None = None
    source_template_id: str | None = None

    # 内部引用，用于层级遍历（不序列化）
    _parent: "Node | None" = field(default=None, repr=False, compare=False)

    def promote(self, target_lifecycle: NodeLifecycle) -> None:
        """提升节点生命周期

        参数：
            target_lifecycle: 目标生命周期

        异常：
            ValueError: 如果转换路径无效

        转换规则：
        - TEMPORARY → PERSISTED（只能这一步）
        - PERSISTED → TEMPLATE
        - TEMPLATE → GLOBAL
        - 不能跳级
        """
        valid_targets = VALID_LIFECYCLE_TRANSITIONS.get(self.lifecycle, [])

        if target_lifecycle not in valid_targets:
            raise ValueError(
                f"Invalid lifecycle transition: {self.lifecycle.value} → {target_lifecycle.value}. "
                f"Valid transitions: {[t.value for t in valid_targets]}"
            )

        self.lifecycle = target_lifecycle

    def promote_to_template(self, template_name: str) -> None:
        """升级为模板（阶段4新增）

        将工作流节点升级为可复用的模板。

        参数：
            template_name: 模板名称

        异常：
            ValueError: 如果当前状态不允许升级
        """
        if self.scope == NodeScope.GLOBAL:
            raise ValueError("全局节点不能再升级")

        if self.scope == NodeScope.TEMPLATE:
            raise ValueError("已经是模板节点")

        self.scope = NodeScope.TEMPLATE
        self.promotion_status = PromotionStatus.PROMOTED
        self.template_name = template_name

    def promote_to_global(self) -> None:
        """升级为全局节点（阶段4新增）

        将模板升级为系统级全局可用。

        异常：
            ValueError: 如果当前不是模板状态
        """
        if self.scope == NodeScope.WORKFLOW:
            raise ValueError("必须先升级为模板，才能升级为全局")

        if self.scope == NodeScope.GLOBAL:
            raise ValueError("已经是全局节点")

        self.scope = NodeScope.GLOBAL
        self.promotion_status = PromotionStatus.PUBLISHED

    def add_child(self, child: "Node") -> None:
        """添加子节点（仅GENERIC类型）

        参数：
            child: 子节点

        异常：
            ValueError: 如果不是 GENERIC 类型，或创建循环，或超过深度限制
        """
        # 验证：只有 GENERIC 节点可以有子节点
        if self.type != NodeType.GENERIC:
            raise ValueError(
                f"Only GENERIC nodes can have children. Current type: {self.type.value}"
            )

        # 验证：不能添加自己为子节点
        if child.id == self.id:
            raise ValueError("Cannot add node as its own child")

        # 验证：不能创建循环层级
        if self._would_create_cycle(child):
            raise ValueError("Circular hierarchy detected: child is an ancestor of parent")

        # 验证：深度限制
        current_depth = self.get_depth()
        if current_depth >= MAX_NODE_DEPTH:
            raise ValueError(
                f"Max depth ({MAX_NODE_DEPTH}) exceeded. Current depth: {current_depth}"
            )

        # 设置父子关系
        child.parent_id = self.id
        child._parent = self
        self.children.append(child)

    def _would_create_cycle(self, potential_child: "Node") -> bool:
        """检查添加子节点是否会创建循环"""
        # 检查 potential_child 是否是当前节点的祖先
        current = self._parent
        while current is not None:
            if current.id == potential_child.id:
                return True
            current = current._parent
        return False

    def remove_child(self, child_id: str) -> None:
        """移除子节点

        参数：
            child_id: 子节点ID
        """
        for i, child in enumerate(self.children):
            if child.id == child_id:
                child.parent_id = None
                child._parent = None
                self.children.pop(i)
                return

    def expand(self) -> None:
        """展开节点（仅GENERIC类型）"""
        self.collapsed = False

    def collapse(self) -> None:
        """折叠节点（仅GENERIC类型）"""
        self.collapsed = True

    def get_visible_children(self) -> list["Node"]:
        """获取可见子节点

        如果节点折叠，返回空列表；否则返回所有子节点。

        返回：
            可见子节点列表
        """
        if self.collapsed:
            return []
        return list(self.children)

    def get_depth(self) -> int:
        """获取当前节点深度

        根节点深度为 0，每层子节点深度 +1。

        返回：
            节点深度
        """
        depth = 0
        current = self._parent
        while current is not None:
            depth += 1
            current = current._parent
        return depth

    def get_root(self) -> "Node":
        """获取根节点

        返回：
            根节点（如果自己就是根，返回自己）
        """
        current = self
        while current._parent is not None:
            current = current._parent
        return current

    def get_ancestors(self) -> list["Node"]:
        """获取所有祖先节点

        返回：
            祖先列表，从直接父节点到根节点
        """
        ancestors = []
        current = self._parent
        while current is not None:
            ancestors.append(current)
            current = current._parent
        return ancestors

    def get_all_descendants(self) -> list["Node"]:
        """获取所有后代节点

        返回：
            后代列表（深度优先遍历）
        """
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典

        返回：
            包含节点所有信息的字典
        """
        return {
            "id": self.id,
            "type": self.type.value,
            "config": self.config,
            "lifecycle": self.lifecycle.value,
            "collapsed": self.collapsed,
            "parent_id": self.parent_id,
            "scope": self.scope.value,
            "version": self.version,
            "promotion_status": self.promotion_status.value,
            "template_name": self.template_name,
            "source_template_id": self.source_template_id,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        """从字典反序列化

        参数：
            data: 节点数据字典

        返回：
            Node 实例
        """
        # 解析枚举类型
        node_type = NodeType(data.get("type", "generic"))
        lifecycle = NodeLifecycle(data.get("lifecycle", "temporary"))
        scope = NodeScope(data.get("scope", "workflow"))
        promotion_status = PromotionStatus(data.get("promotion_status", "draft"))

        # 创建节点
        node = cls(
            id=data.get("id", ""),
            type=node_type,
            config=data.get("config", {}),
            lifecycle=lifecycle,
            collapsed=data.get("collapsed", True),
            parent_id=data.get("parent_id"),
            scope=scope,
            version=data.get("version", 1),
            promotion_status=promotion_status,
            template_name=data.get("template_name"),
            source_template_id=data.get("source_template_id"),
        )

        # 递归解析子节点
        children_data = data.get("children", [])
        for child_data in children_data:
            child = cls.from_dict(child_data)
            child.parent_id = node.id
            child._parent = node
            node.children.append(child)

        return node


# 预定义节点的默认Schema
PREDEFINED_SCHEMAS: dict[NodeType, dict[str, Any]] = {
    NodeType.START: {
        "type": "object",
        "properties": {"trigger_type": {"type": "string", "default": "manual"}},
        "required": [],
    },
    NodeType.END: {"type": "object", "properties": {}, "required": []},
    NodeType.LLM: {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "gpt-4"},
            "temperature": {"type": "number", "default": 0.7},
            "max_tokens": {"type": "integer"},
            "system_prompt": {"type": "string"},
            "user_prompt": {"type": "string", "required": True},
        },
        "required": ["user_prompt"],
    },
    NodeType.CONDITION: {
        "type": "object",
        "properties": {
            "condition_type": {"type": "string", "default": "expression"},
            "expression": {"type": "string"},
            "branches": {"type": "array", "default": []},
        },
        "required": [],
    },
    NodeType.LOOP: {
        "type": "object",
        "properties": {
            "loop_type": {"type": "string", "default": "for_each"},
            "max_iterations": {"type": "integer", "default": 100},
            # 推荐字段：从上游节点输出中提取集合的字段名
            "collection_field": {"type": "string"},
            # 兼容旧字段：直接指定集合名称
            "collection": {"type": "string"},
            # map类型专用：转换表达式
            "transform_expression": {"type": "string"},
            # filter类型专用：过滤条件表达式
            "filter_condition": {"type": "string"},
            # while类型专用：循环条件
            "condition": {"type": "string"},
            # for_each类型专用：迭代时注入的变量名
            "item_variable": {"type": "string", "default": "current_item"},
        },
        "required": [],
    },
    NodeType.PARALLEL: {
        "type": "object",
        "properties": {
            "branches": {"type": "array", "default": []},
            "wait_all": {"type": "boolean", "default": True},
        },
        "required": [],
    },
    NodeType.API: {
        "type": "object",
        "properties": {
            "method": {"type": "string", "default": "GET"},
            "url": {"type": "string"},
            "headers": {"type": "object", "default": {}},
            "body": {"type": "object"},
        },
        "required": [],
    },
    NodeType.CODE: {
        "type": "object",
        "properties": {
            "language": {"type": "string", "default": "python"},
            "code": {"type": "string"},
            "inputs": {"type": "array", "default": []},
            "outputs": {"type": "array", "default": []},
        },
        "required": [],
    },
    NodeType.MCP: {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "tool": {"type": "string"},
            "arguments": {"type": "object", "default": {}},
        },
        "required": [],
    },
    NodeType.KNOWLEDGE: {
        "type": "object",
        "properties": {
            "knowledge_base_id": {"type": "string"},
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 5},
        },
        "required": [],
    },
    NodeType.CLASSIFY: {
        "type": "object",
        "properties": {"categories": {"type": "array", "default": []}, "input": {"type": "string"}},
        "required": [],
    },
    NodeType.TEMPLATE: {
        "type": "object",
        "properties": {
            "template": {"type": "string"},
            "variables": {"type": "object", "default": {}},
        },
        "required": [],
    },
    NodeType.GENERIC: {
        "type": "object",
        "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
        "required": [],
    },
    NodeType.FILE: {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["read", "write", "append", "delete", "list"],
                "default": "read",
            },
            "path": {"type": "string"},
            "content": {"type": "string", "default": ""},
            "encoding": {"type": "string", "default": "utf-8"},
        },
        "required": ["operation", "path"],
        "allOf": [
            {
                "if": {"properties": {"operation": {"const": "write"}}},
                "then": {"required": ["content"]},
            },
            {
                "if": {"properties": {"operation": {"const": "append"}}},
                "then": {"required": ["content"]},
            },
        ],
    },
    NodeType.TRANSFORM: {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "field_mapping",
                    "type_conversion",
                    "field_extraction",
                    "array_mapping",
                    "filtering",
                    "aggregation",
                    "custom",
                ],
            },
            "mapping": {"type": "object"},
            "conversions": {"type": "object"},
            "fields": {"type": ["array", "string"]},
            "element_transform": {"type": "object"},
            "condition": {"type": "string"},
            "aggregation": {"type": "object"},
            "config": {"type": "object"},
        },
        "required": ["type"],
        "allOf": [
            {
                "if": {"properties": {"type": {"const": "field_mapping"}}},
                "then": {"required": ["mapping"]},
            },
            {
                "if": {"properties": {"type": {"const": "type_conversion"}}},
                "then": {"required": ["conversions"]},
            },
            {
                "if": {"properties": {"type": {"const": "field_extraction"}}},
                "then": {"required": ["fields"]},
            },
            {
                "if": {"properties": {"type": {"const": "array_mapping"}}},
                "then": {"required": ["element_transform"]},
            },
            {
                "if": {"properties": {"type": {"const": "filtering"}}},
                "then": {"required": ["condition"]},
            },
            {
                "if": {"properties": {"type": {"const": "aggregation"}}},
                "then": {"required": ["aggregation"]},
            },
        ],
    },
    NodeType.HUMAN: {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "expected_inputs": {"type": "array", "items": {"type": "string"}, "default": []},
            "timeout_seconds": {"type": "integer", "minimum": 1, "default": 300},
            "metadata": {"type": "object"},
        },
        "required": ["prompt"],
    },
}


class NodeRegistry:
    """节点注册中心

    职责：
    1. 管理节点类型和Schema
    2. 提供节点模板
    3. 验证节点配置
    4. 初始化时注册所有预定义类型

    使用示例：
        registry = NodeRegistry()
        template = registry.get_template(NodeType.LLM)
        is_valid, errors = registry.validate_config(NodeType.LLM, config)
    """

    def __init__(self):
        """初始化节点注册中心

        自动注册所有预定义节点类型。
        """
        self._schemas: dict[NodeType, dict[str, Any]] = {}
        self._templates: dict[NodeType, dict[str, Any]] = {}

        # 自动注册所有预定义类型
        self._register_predefined_types()

    def _register_predefined_types(self) -> None:
        """注册所有预定义节点类型"""
        for node_type, schema in PREDEFINED_SCHEMAS.items():
            self.register(node_type, schema)

    def register(self, node_type: NodeType, schema: dict[str, Any]) -> None:
        """注册节点类型

        参数：
            node_type: 节点类型
            schema: 配置Schema
        """
        self._schemas[node_type] = schema
        # 从Schema生成默认模板
        self._templates[node_type] = self._generate_template(schema)

    def _generate_template(self, schema: dict[str, Any]) -> dict[str, Any]:
        """从Schema生成默认模板

        提取所有属性的默认值。
        """
        template = {}
        properties = schema.get("properties", {})

        for prop_name, prop_def in properties.items():
            if "default" in prop_def:
                template[prop_name] = prop_def["default"]

        return template

    def is_registered(self, node_type: NodeType) -> bool:
        """检查节点类型是否已注册

        参数：
            node_type: 节点类型

        返回：
            是否已注册
        """
        return node_type in self._schemas

    def get_schema(self, node_type: NodeType) -> dict[str, Any]:
        """获取节点类型的Schema

        参数：
            node_type: 节点类型

        返回：
            配置Schema
        """
        return self._schemas.get(node_type, {})

    def get_all_types(self) -> list[NodeType]:
        """获取所有已注册的节点类型

        返回：
            节点类型列表
        """
        return list(self._schemas.keys())

    def get_template(self, node_type: NodeType) -> dict[str, Any]:
        """获取节点模板

        模板包含所有字段的默认值。

        参数：
            node_type: 节点类型

        返回：
            配置模板
        """
        return self._templates.get(node_type, {}).copy()

    def validate_config(
        self, node_type: NodeType, config: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """验证节点配置

        参数：
            node_type: 节点类型
            config: 节点配置

        返回：
            (是否有效, 错误列表)
        """
        errors = []
        schema = self._schemas.get(node_type)

        if not schema:
            errors.append(f"Unknown node type: {node_type}")
            return False, errors

        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        # 检查必需字段
        for field_name in required_fields:
            if field_name not in config:
                errors.append(f"Missing required field: {field_name}")

        # 检查字段类型和枚举约束
        for field_name, value in config.items():
            if field_name in properties:
                prop_schema = properties[field_name]

                # 类型检查
                expected_type = prop_schema.get("type")
                if not self._check_type(value, expected_type):
                    errors.append(
                        f"Invalid type for {field_name}: expected {expected_type}, "
                        f"got {type(value).__name__}"
                    )

                # 枚举检查
                enum_values = prop_schema.get("enum")
                if enum_values and value not in enum_values:
                    errors.append(f"Invalid value for {field_name}: {value!r} not in {enum_values}")

        # 检查条件约束（if/then/allOf）
        conditional_rules = schema.get("allOf", [])
        for rule in conditional_rules:
            if "if" in rule and "then" in rule:
                # 检查if条件是否匹配
                match = self._check_condition(config, rule["if"])
                if match:
                    # 如果匹配，检查then中的必需字段
                    then_required = rule["then"].get("required", [])
                    for field_name in then_required:
                        if field_name not in config:
                            errors.append(f"Missing required field under condition: {field_name}")

        return len(errors) == 0, errors

    def _check_condition(self, config: dict[str, Any], condition: dict[str, Any]) -> bool:
        """检查条件是否匹配

        参数：
            config: 节点配置
            condition: if条件（JSON Schema格式）

        返回：
            是否匹配
        """
        # 检查properties中的const约束
        condition_props = condition.get("properties", {})
        for prop, prop_schema in condition_props.items():
            if "const" in prop_schema:
                if config.get(prop) != prop_schema["const"]:
                    return False
        return True

    def _check_type(self, value: Any, expected_type: str | list[str] | None) -> bool:
        """检查值类型是否匹配

        参数：
            value: 实际值
            expected_type: 期望类型（可以是字符串或类型列表）

        返回：
            是否匹配
        """
        if expected_type is None:
            return True

        # 支持多类型（如 ["array", "string"]）
        if isinstance(expected_type, list):
            return any(self._check_type(value, t) for t in expected_type)

        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True

        return isinstance(value, expected_python_type)


class NodeFactory:
    """节点工厂

    职责：
    1. 根据类型和配置创建节点实例
    2. 应用默认值
    3. 验证配置

    使用示例：
        factory = NodeFactory(registry)
        node = factory.create(NodeType.LLM, {"user_prompt": "分析数据"})
    """

    def __init__(self, registry: NodeRegistry):
        """初始化节点工厂

        参数：
            registry: 节点注册中心
        """
        self.registry = registry

    def create(
        self, node_type: NodeType, config: dict[str, Any], node_id: str | None = None
    ) -> Node:
        """创建节点实例

        参数：
            node_type: 节点类型
            config: 节点配置
            node_id: 可选，节点ID（不提供则自动生成）

        返回：
            节点实例

        异常：
            NodeConfigError: 配置验证失败
        """
        # 合并默认值
        template = self.registry.get_template(node_type)
        merged_config = {**template, **config}

        # 验证配置
        is_valid, errors = self.registry.validate_config(node_type, merged_config)

        if not is_valid:
            raise NodeConfigError(f"Invalid config for {node_type.value}: {', '.join(errors)}")

        # 创建节点
        return Node(
            id=node_id or str(uuid4()),
            type=node_type,
            config=merged_config,
            lifecycle=NodeLifecycle.TEMPORARY,
        )


# 导出
__all__ = [
    "NodeType",
    "NodeLifecycle",
    "NodeConfigError",
    "Node",
    "NodeRegistry",
    "NodeFactory",
    "PREDEFINED_SCHEMAS",
    "VALID_LIFECYCLE_TRANSITIONS",
    # 阶段4新增
    "NodeScope",
    "PromotionStatus",
]

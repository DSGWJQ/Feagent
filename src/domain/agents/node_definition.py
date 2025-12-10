"""节点定义 (NodeDefinition) - Phase 8.1 + Phase 4 层次化扩展

业务定义：
- 节点定义是 Agent 自定义节点功能的数据结构
- 支持多种节点类型：Python、LLM、HTTP、Database 等
- 包含验证逻辑确保节点配置完整
- Phase 4: 支持父子层次结构、折叠状态、容器执行

设计原则：
- 类型安全：每种节点类型有明确的必填字段
- 可序列化：支持 to_dict/from_dict 便于存储和传输
- 可扩展：通过 config 字典支持额外配置
- 层次化：支持父子关系和折叠状态

使用示例：
    node = NodeDefinition(
        node_type=NodeType.PYTHON,
        name="数据处理",
        code="return process(data)",
        input_schema={"data": "dict"},
    )
    errors = node.validate()

    # 层次化示例
    parent = NodeDefinition(node_type=NodeType.GENERIC, name="父节点")
    child = NodeDefinition(node_type=NodeType.PYTHON, name="子节点", code="pass")
    parent.add_child(child)
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

# Phase 4: 层次化深度限制
MAX_NODE_DEFINITION_DEPTH = 5


class NodeType(str, Enum):
    """节点类型"""

    PYTHON = "python"  # Python 代码执行
    LLM = "llm"  # LLM 调用
    HTTP = "http"  # HTTP 请求
    DATABASE = "database"  # 数据库查询
    GENERIC = "generic"  # 通用节点
    CONDITION = "condition"  # 条件分支
    LOOP = "loop"  # 循环
    PARALLEL = "parallel"  # 并行执行
    CONTAINER = "container"  # Phase 4: 容器执行
    FILE = "file"  # 文件操作节点
    DATA_PROCESS = "data_process"  # 数据处理节点
    HUMAN = "human"  # 人机交互节点


@dataclass
class NodeDefinition:
    """节点定义

    Agent 可通过此类定义节点的具体功能。

    属性：
        id: 节点唯一标识
        node_type: 节点类型
        name: 节点名称
        description: 节点描述
        code: Python 节点的代码
        prompt: LLM 节点的 Prompt 模板
        url: HTTP 节点的 URL
        method: HTTP 节点的请求方法
        query: Database 节点的 SQL 查询
        config: 额外配置
        input_schema: 输入参数 Schema
        output_schema: 输出参数 Schema
    """

    node_type: NodeType
    name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    # 类型特定字段
    code: str | None = None  # PYTHON
    prompt: str | None = None  # LLM
    url: str | None = None  # HTTP
    method: str = "GET"  # HTTP
    query: str | None = None  # DATABASE
    # 通用配置
    config: dict[str, Any] = field(default_factory=dict)
    input_schema: dict[str, str] = field(default_factory=dict)
    output_schema: dict[str, str] = field(default_factory=dict)
    # Phase 4: 层次化字段
    parent_id: str | None = None
    children: list["NodeDefinition"] = field(default_factory=list)
    collapsed: bool = True  # GENERIC 节点默认折叠
    # Phase 4: 容器执行字段
    is_container: bool = False
    container_config: dict[str, Any] = field(default_factory=dict)
    # Phase 4: 内部深度跟踪（用于深度限制检查）
    _depth: int = 0
    # Phase 8.2: 错误策略
    error_strategy: dict[str, Any] | None = None
    # Phase 9: 父节点策略继承字段
    resource_limits: dict[str, Any] = field(default_factory=dict)
    inherited_strategy: bool = False

    def __post_init__(self):
        """dataclass初始化后验证

        自动调用验证逻辑，确保节点定义在创建时就是有效的。

        注意：为了向后兼容，此方法仅验证新增的控制流节点（CONDITION/LOOP）。
        其他节点类型的验证需要显式调用 validate() 方法。
        这样可以避免破坏现有的增量构建节点定义的工作流。

        如果验证失败，抛出 ValueError 异常。
        """
        # 仅对 CONDITION/LOOP 节点进行强制验证（新功能）
        # 其他节点类型保持向后兼容，允许增量构建
        if self.node_type in (NodeType.CONDITION, NodeType.LOOP):
            errors = self.validate()
            if errors:
                raise ValueError(f"节点定义验证失败: {'; '.join(errors)}")

    def validate(self) -> list[str]:
        """验证节点定义完整性

        返回：
            错误列表，空列表表示验证通过
        """
        errors = []

        # 验证名称
        if not self.name or not self.name.strip():
            errors.append("节点 name 不能为空")

        # 根据类型验证必填字段
        if self.node_type == NodeType.PYTHON:
            if not self.code:
                errors.append("Python 节点需要 code 字段")

        elif self.node_type == NodeType.LLM:
            if not self.prompt:
                errors.append("LLM 节点需要 prompt 字段")

        elif self.node_type == NodeType.HTTP:
            if not self.url:
                errors.append("HTTP 节点需要 url 字段")

        elif self.node_type == NodeType.DATABASE:
            if not self.query:
                errors.append("Database 节点需要 query 字段")

        elif self.node_type == NodeType.CONTAINER:
            if not self.code:
                errors.append("Container 节点需要 code 字段")

        # CONDITION 节点验证：必须有可执行的表达式
        elif self.node_type == NodeType.CONDITION:
            expression = self.config.get("expression") if self.config else None
            if not expression or not str(expression).strip():
                errors.append("Condition 节点需要 config.expression 字段（用于条件判断）")

        # LOOP 节点验证：必须明确集合来源和循环类型特定要求
        elif self.node_type == NodeType.LOOP:
            # 验证集合来源（collection_field 或 collection 至少有一个）
            collection_field = self.config.get("collection_field") if self.config else None
            collection_legacy = self.config.get("collection") if self.config else None
            if not (collection_field or collection_legacy):
                errors.append(
                    "Loop 节点需要 config.collection_field 或 config.collection 字段（指定集合来源）"
                )

            # 根据 loop_type 验证特定字段
            loop_type = self.config.get("loop_type", "for_each") if self.config else "for_each"
            if loop_type == "map":
                transform_expr = self.config.get("transform_expression") if self.config else None
                if not transform_expr or not str(transform_expr).strip():
                    errors.append("Loop(map) 节点需要 config.transform_expression 字段（用于转换）")
            elif loop_type == "filter":
                filter_cond = self.config.get("filter_condition") if self.config else None
                if not filter_cond or not str(filter_cond).strip():
                    errors.append("Loop(filter) 节点需要 config.filter_condition 字段（用于过滤）")

        # FILE 节点验证：必须有 operation 和 path
        elif self.node_type == NodeType.FILE:
            operation = self.config.get("operation") if self.config else None
            if not operation or operation not in ["read", "write", "append", "delete", "list"]:
                errors.append(
                    "File 节点需要合法的 config.operation（read/write/append/delete/list）"
                )
            path = self.config.get("path") if self.config else None
            if not path:
                errors.append("File 节点需要 config.path")

        # DATA_PROCESS 节点验证：必须有 type
        elif self.node_type == NodeType.DATA_PROCESS:
            process_type = self.config.get("type") if self.config else None
            if not process_type:
                errors.append(
                    "DataProcess 节点需要 config.type（field_mapping/type_conversion/...）"
                )

        # HUMAN 节点验证：必须有 prompt
        elif self.node_type == NodeType.HUMAN:
            prompt = self.config.get("prompt") if self.config else None
            if not prompt or not str(prompt).strip():
                errors.append("Human 交互节点需要 config.prompt")

        # GENERIC、PARALLEL 类型无特殊要求

        # Phase 9: 父节点策略验证
        # 父节点（GENERIC 类型且有子节点）必须定义 error_strategy 和 resource_limits
        if self.node_type == NodeType.GENERIC and self.children:
            if not self.error_strategy:
                errors.append("父节点必须定义 error_strategy")
            if not self.resource_limits:
                errors.append("父节点必须定义 resource_limits")

        return errors

    # === Phase 4: 层次化方法 ===

    def _get_depth(self) -> int:
        """计算当前节点深度

        返回：
            当前节点在层次树中的深度（根节点为0）
        """
        depth = 0
        current = self
        # 通过 parent_id 计算深度（需要在 add_child 中维护）
        # 这里简单计算 children 链的深度
        while current.children:
            depth += 1
            current = current.children[0]
        return 0  # 当前节点本身的深度需要从根追溯

    def _calculate_depth_from_root(self) -> int:
        """从根节点计算当前节点深度

        通过递归查找所有祖先节点计算深度。
        由于没有 _parent 引用，这里返回0作为默认。
        实际深度在 add_child 时检查。
        """
        return 0

    def add_child(self, child: "NodeDefinition") -> None:
        """添加子节点

        只有 GENERIC 类型节点可以添加子节点。
        子节点深度不能超过 MAX_NODE_DEFINITION_DEPTH。

        参数：
            child: 要添加的子节点

        异常：
            ValueError: 如果当前节点不是 GENERIC 类型
            ValueError: 如果超过最大深度限制
        """
        if self.node_type != NodeType.GENERIC:
            raise ValueError("Only GENERIC nodes can have children")

        # 检查深度限制：子节点深度 = 当前深度 + 1
        child_depth = self._depth + 1
        if child_depth > MAX_NODE_DEFINITION_DEPTH:
            raise ValueError(f"Max depth ({MAX_NODE_DEFINITION_DEPTH}) exceeded")

        # 添加子节点并设置深度
        child.parent_id = self.id
        child._depth = child_depth
        self.children.append(child)

    def _count_ancestors(self) -> int:
        """计算祖先节点数量（即当前深度）

        返回：
            从根到当前节点的深度
        """
        # 简化实现：通过 children 链计算最大深度
        # 实际使用中，可以维护 _parent 引用
        max_child_depth = 0
        for child in self.children:
            child_depth = child._count_ancestors() + 1
            max_child_depth = max(max_child_depth, child_depth)
        return max_child_depth

    def remove_child(self, child_id: str) -> None:
        """移除子节点

        参数：
            child_id: 要移除的子节点ID
        """
        for i, child in enumerate(self.children):
            if child.id == child_id:
                child.parent_id = None
                self.children.pop(i)
                return

    def expand(self) -> None:
        """展开节点，显示子节点"""
        self.collapsed = False

    def collapse(self) -> None:
        """折叠节点，隐藏子节点"""
        self.collapsed = True

    def toggle_collapsed(self) -> None:
        """切换折叠状态"""
        self.collapsed = not self.collapsed

    # === Phase 9: 策略传播方法 ===

    def propagate_strategy_to_children(self) -> None:
        """将策略传播给所有子节点（递归）

        将父节点的 error_strategy 和 resource_limits 强制传播给所有子节点。
        子节点的 inherited_strategy 标志会被设置为 True。
        策略会递归传播到所有后代节点。
        """
        if not self.children:
            return

        for child in self.children:
            # 强制覆盖子节点策略
            child.error_strategy = self.error_strategy
            child.resource_limits = self.resource_limits.copy()  # 深拷贝
            child.inherited_strategy = True

            # 递归传播到子节点的子节点
            child.propagate_strategy_to_children()

    # === 父节点 Schema 加载方法 ===

    @classmethod
    def from_parent_schema(
        cls,
        schema: dict[str, Any],
        registry: dict[str, "NodeDefinition"] | None = None,
        validator: Any | None = None,
    ) -> "NodeDefinition":
        """从父节点 Schema 创建 NodeDefinition

        参数:
            schema: 父节点 schema 字典
            registry: 子节点注册表 (ref -> NodeDefinition)
            validator: 可选的验证器实例

        返回:
            NodeDefinition 实例
        """
        if validator is None:
            from src.domain.services.parent_node_schema import ParentNodeValidator

            validator = ParentNodeValidator()

        # 验证 schema
        validation_result = validator.validate(schema)
        # 检查是否为ValidationResult对象
        if hasattr(validation_result, "is_valid"):
            if not validation_result.is_valid:
                raise ValueError(f"Invalid parent schema: {validation_result.errors}")
        elif validation_result:  # 如果是简单的错误列表
            raise ValueError(f"Invalid parent schema: {validation_result}")

        # 如果有 inherit_from，解析继承链
        if "inherit_from" in schema:
            # 需要schema的name作为node_id
            node_id = schema.get("name", "unknown")
            # 先将schema注册到validator的registry中
            if node_id not in validator.registry:
                validator.registry[node_id] = schema
            # 解析继承得到完整schema
            resolved_schema = validator.resolve_inheritance(node_id)
            # 清理临时注册
            if node_id in validator.registry and validator.registry[node_id] == schema:
                del validator.registry[node_id]
        else:
            resolved_schema = schema

        # 创建父节点
        parent = cls(
            node_type=NodeType.GENERIC,
            name=resolved_schema.get("name", ""),
            description=resolved_schema.get("description", ""),
        )

        # 应用继承配置（优先从 resolved_schema 读取，已经过继承合并）
        inherit = resolved_schema.get("inherit", {})
        if inherit:
            parent.error_strategy = inherit.get("error_strategy")
            parent.resource_limits = inherit.get("resources", {})

            # 同时设置 config["resources"] 以兼容旧代码
            if "resources" in inherit:
                parent.config["resources"] = inherit["resources"]

            # 保存参数和返回值到 input/output schema
            if "parameters" in inherit:
                parent.config["parameters"] = inherit["parameters"]
                # 转换为 input_schema
                for param_name, param_def in inherit["parameters"].items():
                    if isinstance(param_def, dict):
                        parent.input_schema[param_name] = param_def.get("type", "any")

            if "returns" in inherit:
                parent.config["returns"] = inherit["returns"]
                # 转换为 output_schema
                if isinstance(inherit["returns"], dict):
                    for return_name, return_def in inherit["returns"].items():
                        # 如果 return_def 是字典，提取 type 字段；否则直接使用
                        if isinstance(return_def, dict):
                            parent.output_schema[return_name] = return_def.get("type", "any")
                        else:
                            parent.output_schema[return_name] = return_def

            if "tags" in inherit:
                parent.config["tags"] = inherit["tags"]
        else:
            # 如果没有 inherit 块，直接从 resolved_schema 读取策略和资源
            if "error_strategy" in resolved_schema:
                parent.error_strategy = resolved_schema["error_strategy"]
            if "resources" in resolved_schema:
                parent.resource_limits = resolved_schema["resources"]
                parent.config["resources"] = resolved_schema["resources"]

        # 展开子节点
        if "children" in resolved_schema and registry:
            parent._expand_children_from_schema(resolved_schema["children"], registry)

        return parent

    def _expand_children_from_schema(
        self, children_config: list[dict], registry: dict[str, "NodeDefinition"], depth: int = 0
    ) -> None:
        """从 schema 中展开子节点"""
        for child_spec in children_config:
            ref = child_spec.get("ref")
            if not ref:
                raise ValueError("Child spec must have 'ref' field")

            if ref not in registry:
                raise KeyError(f"Child ref '{ref}' not found in registry")

            # 检查深度限制
            if depth + 1 > MAX_NODE_DEFINITION_DEPTH:
                raise ValueError(f"Max depth ({MAX_NODE_DEFINITION_DEPTH}) exceeded")

            # 复制子节点
            child_template = registry[ref]
            child = NodeDefinition.from_dict(child_template.to_dict())

            # 设置深度
            child._depth = depth + 1

            # 应用 override
            if "override" in child_spec:
                override = child_spec["override"]
                if "resources" in override:
                    child.config.setdefault("resources", {}).update(override["resources"])
                if "error_strategy" in override:
                    if not child.error_strategy:
                        child.error_strategy = override["error_strategy"]
                    else:
                        # 合并 error_strategy（override 优先）
                        child.error_strategy.update(override["error_strategy"])

            # 设置 alias
            if "alias" in child_spec:
                child.config["alias"] = child_spec["alias"]

            # 添加子节点
            self.children.append(child)
            child.parent_id = self.id

    def expand_children(
        self, registry: dict[str, "NodeDefinition"], depth: int | None = None
    ) -> list["NodeDefinition"]:
        """展开子节点（从配置中的 ref 引用展开为实际 NodeDefinition）

        参数:
            registry: 子节点注册表 (ref -> NodeDefinition)
            depth: 当前深度（用于深度限制）

        返回:
            展开后的子节点列表
        """
        children_config = self.config.get("children", [])
        if not children_config:
            return []

        if depth is None:
            depth = self._depth

        self.children = []  # 清空现有子节点
        self._expand_children_from_schema(children_config, registry, depth)
        return self.children

    def apply_inherited_strategy(
        self,
        parent_strategy: dict[str, Any] | None = None,
        parent_resources: dict[str, Any] | None = None,
    ) -> None:
        """应用继承的策略（合并父节点和子节点配置）

        参数:
            parent_strategy: 父节点的错误策略
            parent_resources: 父节点的资源配置
        """
        # 首先从config中读取子节点自己的策略和资源（如果存在）
        if not self.error_strategy and self.config.get("error_strategy"):
            self.error_strategy = self.config["error_strategy"]

        if not self.resource_limits and self.config.get("resources"):
            self.resource_limits = self.config["resources"]

        # 合并错误策略（子节点优先，父节点补充）
        if parent_strategy:
            if not self.error_strategy:
                # 没有子节点策略，直接使用父策略
                self.error_strategy = parent_strategy.copy()
            else:
                # 有子节点策略，合并父子策略（子节点字段优先）
                # 先复制父策略，再用子策略覆盖
                merged_strategy = {}
                merged_strategy.update(parent_strategy)
                merged_strategy.update(self.error_strategy)
                self.error_strategy = merged_strategy

        # 合并资源配置（子节点优先，父节点补充）
        if parent_resources:
            if not self.resource_limits:
                # 没有子节点资源，直接使用父资源
                self.resource_limits = parent_resources.copy()
            else:
                # 有子节点资源，合并父子资源（子节点字段优先）
                # 先复制父资源，再用子资源覆盖
                merged_resources = {}
                merged_resources.update(parent_resources)
                merged_resources.update(self.resource_limits)
                self.resource_limits = merged_resources

    def get_inherited_error_strategy(self) -> dict[str, Any]:
        """获取继承的错误策略"""
        return self.error_strategy or {}

    def get_inherited_resources(self) -> dict[str, Any]:
        """获取继承的资源配置"""
        return self.resource_limits or self.config.get("resources", {})

    def get_child_by_name(self, name: str) -> "NodeDefinition | None":
        """按名称查找子节点"""
        for child in self.children:
            if child.name == name:
                return child
        return None

    def get_child_by_alias(self, alias: str) -> "NodeDefinition | None":
        """按别名查找子节点"""
        for child in self.children:
            if child.config.get("alias") == alias:
                return child
        return None

    def get_visible_children(self) -> list["NodeDefinition"]:
        """获取可见的子节点

        如果节点折叠，返回空列表；否则返回所有子节点。

        返回：
            可见的子节点列表
        """
        if self.collapsed:
            return []
        return self.children.copy()

    def get_all_descendants(self) -> list["NodeDefinition"]:
        """获取所有后代节点

        递归获取所有子节点及其后代。

        返回：
            所有后代节点列表
        """
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典

        返回:
            包含所有字段的字典（包含层次化信息）
        """
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "prompt": self.prompt,
            "url": self.url,
            "method": self.method,
            "query": self.query,
            "config": self.config,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            # Phase 4: 层次化字段
            "parent_id": self.parent_id,
            "children": [child.to_dict() for child in self.children],
            "collapsed": self.collapsed,
            "is_container": self.is_container,
            "container_config": self.container_config,
            # Phase 8.2: 错误策略
            "error_strategy": self.error_strategy,
            # Phase 9: 策略继承字段
            "resource_limits": self.resource_limits,
            "inherited_strategy": self.inherited_strategy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeDefinition":
        """从字典反序列化

        参数：
            data: 包含节点定义的字典

        返回：
            NodeDefinition 实例（包含层次化结构）
        """
        node_type_str = data.get("node_type", "generic")
        try:
            node_type = NodeType(node_type_str)
        except ValueError:
            node_type = NodeType.GENERIC

        # 创建节点
        node = cls(
            id=data.get("id", str(uuid4())),
            node_type=node_type,
            name=data.get("name", ""),
            description=data.get("description", ""),
            code=data.get("code"),
            prompt=data.get("prompt"),
            url=data.get("url"),
            method=data.get("method", "GET"),
            query=data.get("query"),
            config=data.get("config", {}),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            # Phase 4: 层次化字段
            parent_id=data.get("parent_id"),
            collapsed=data.get("collapsed", True),
            is_container=data.get("is_container", False),
            container_config=data.get("container_config", {}),
            # Phase 8.2: 错误策略
            error_strategy=data.get("error_strategy"),
            # Phase 9: 策略继承字段
            resource_limits=data.get("resource_limits", {}),
            inherited_strategy=data.get("inherited_strategy", False),
        )

        # Phase 4: 递归恢复子节点
        children_data = data.get("children", [])
        for child_data in children_data:
            child = cls.from_dict(child_data)
            child.parent_id = node.id  # 设置父节点ID
            node.children.append(child)

        return node

    # ========== Phase 8.1 扩展: YAML 解析与序列化 ==========

    # 执行器类型映射
    EXECUTOR_TYPE_MAP = {
        "python": NodeType.PYTHON,
        "code": NodeType.PYTHON,  # code 是 python 的别名
        "llm": NodeType.LLM,
        "http": NodeType.HTTP,
        "database": NodeType.DATABASE,
        "container": NodeType.CONTAINER,
        "condition": NodeType.CONDITION,
        "loop": NodeType.LOOP,
        "parallel": NodeType.PARALLEL,
        "generic": NodeType.GENERIC,
        "api": NodeType.HTTP,  # api 映射到 HTTP
        "file": NodeType.FILE,  # 文件操作
        "transform": NodeType.DATA_PROCESS,  # 数据转换
        "data_process": NodeType.DATA_PROCESS,  # 数据处理
        "human": NodeType.HUMAN,  # 人机交互
    }

    @classmethod
    def from_yaml(cls, yaml_content: str | dict[str, Any], depth: int = 0) -> "NodeDefinition":
        """从 YAML 字符串或字典解析 NodeDefinition

        参数：
            yaml_content: YAML 内容字符串或已解析的字典
            depth: 当前嵌套深度（用于深度限制检查）

        返回：
            NodeDefinition 实例

        异常：
            ValueError: YAML 解析错误或缺少必填字段
        """
        # 如果传入的是字典，直接使用
        if isinstance(yaml_content, dict):
            return cls._from_yaml_data(yaml_content, depth)

        # 否则解析YAML字符串
        if not yaml_content or not yaml_content.strip():
            raise ValueError("YAML content is empty")

        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error: {e}") from e

        if data is None:
            raise ValueError("YAML content is empty or contains only comments")

        return cls._from_yaml_data(data, depth)

    @classmethod
    def _from_yaml_data(cls, data: dict[str, Any], depth: int = 0) -> "NodeDefinition":
        """从解析后的 YAML 数据创建 NodeDefinition

        参数：
            data: 解析后的 YAML 数据字典
            depth: 当前嵌套深度

        返回：
            NodeDefinition 实例
        """
        # 校验必填字段（支持 type 或 executor_type）
        if "name" not in data or not data["name"]:
            raise ValueError("Missing required field: name")

        # 支持 type 或 executor_type 字段
        node_type_field = data.get("type") or data.get("executor_type")
        if not node_type_field:
            raise ValueError("Missing required field: type or executor_type")

        # 解析执行器类型
        executor_type_str = str(node_type_field).lower()
        node_type = cls.EXECUTOR_TYPE_MAP.get(executor_type_str, NodeType.GENERIC)

        # 解析参数到 input_schema
        input_schema = {}
        parameters = data.get("parameters", [])
        if isinstance(parameters, list):
            for param in parameters:
                if isinstance(param, dict) and "name" in param:
                    param_name = param["name"]
                    param_type = param.get("type", "any")
                    input_schema[param_name] = param_type

        # 解析返回值到 output_schema
        output_schema = {}
        returns = data.get("returns", {})
        if isinstance(returns, dict):
            properties = returns.get("properties", {})
            for prop_name, prop_def in properties.items():
                if isinstance(prop_def, dict):
                    output_schema[prop_name] = prop_def.get("type", "any")
                else:
                    output_schema[prop_name] = "any"

        # 构建 config（保存元数据和其他配置）
        config = {}

        # 首先合并传入的config字段（如果有）
        if "config" in data and isinstance(data["config"], dict):
            config.update(data["config"])

        # 保存元数据（优先使用顶层字段，回退到config中的值）
        if "author" in data:
            config["author"] = data["author"]
        if "tags" in data:
            config["tags"] = data["tags"]
        if "category" in data:
            config["category"] = data["category"]
        if "version" in data:
            config["version"] = data["version"]
        if "kind" in data:
            config["kind"] = data["kind"]

        # 保存错误策略
        if "error_strategy" in data:
            config["error_strategy"] = data["error_strategy"]

        # 保存动态代码
        if "dynamic_code" in data:
            config["dynamic_code"] = data["dynamic_code"]

        # 保存执行配置
        if "execution" in data:
            config["execution"] = data["execution"]

        # 保存原始参数定义（用于验证）
        if parameters:
            config["parameters"] = parameters

        # 保存原始返回值定义（用于验证）
        if returns:
            config["returns"] = returns

        # 提取类型特定字段
        code = data.get("code")
        prompt = data.get("prompt")
        url = data.get("url")
        method = data.get("method", "GET")
        query = data.get("query")

        # 创建节点
        node = cls(
            node_type=node_type,
            name=data.get("name", ""),
            description=data.get("description", ""),
            code=code,
            prompt=prompt,
            url=url,
            method=method,
            query=query,
            config=config,
            input_schema=input_schema,
            output_schema=output_schema,
        )
        node._depth = depth

        # 解析嵌套节点
        nested = data.get("nested", {})
        if isinstance(nested, dict):
            # 保存 parallel 标志
            if nested.get("parallel"):
                node.config["nested_parallel"] = True

            # 检查深度限制
            children_data = nested.get("children", [])
            if children_data and depth >= MAX_NODE_DEFINITION_DEPTH:
                raise ValueError(
                    f"Nested depth exceeded maximum allowed ({MAX_NODE_DEFINITION_DEPTH})"
                )

            # 递归解析子节点
            if isinstance(children_data, list):
                for child_data in children_data:
                    if isinstance(child_data, dict):
                        child = cls._from_yaml_data(child_data, depth + 1)
                        child.parent_id = node.id
                        child._depth = depth + 1
                        node.children.append(child)

        return node

    @classmethod
    def from_yaml_file(cls, file_path: Path | str) -> "NodeDefinition":
        """从 YAML 文件加载 NodeDefinition

        参数：
            file_path: YAML 文件路径

        返回：
            NodeDefinition 实例

        异常：
            ValueError: 文件不存在或解析错误
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        # 尝试多种编码
        yaml_content = None
        for encoding in ["utf-8", "utf-8-sig", "gbk", "latin-1"]:
            try:
                with open(file_path, encoding=encoding) as f:
                    yaml_content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if yaml_content is None:
            raise ValueError(f"Failed to decode file: {file_path}")

        return cls.from_yaml(yaml_content)

    @classmethod
    def from_yaml_directory(cls, dir_path: Path | str) -> list["NodeDefinition"]:
        """从目录加载所有 YAML 文件

        参数：
            dir_path: 目录路径

        返回：
            NodeDefinition 列表
        """
        dir_path = Path(dir_path)
        nodes = []

        for yaml_file in dir_path.glob("*.yaml"):
            try:
                node = cls.from_yaml_file(yaml_file)
                nodes.append(node)
            except ValueError:
                continue  # 跳过无效文件

        for yml_file in dir_path.glob("*.yml"):
            try:
                node = cls.from_yaml_file(yml_file)
                nodes.append(node)
            except ValueError:
                continue

        return nodes

    def to_yaml_dict(self) -> dict[str, Any]:
        """序列化为 YAML 数据字典

        返回：
            YAML 数据字典
        """
        # 为默认值设置
        kind = self.config.get("kind", "node")
        version = self.config.get("version", "1.0.0")

        data = {
            "name": self.name,
            "kind": kind,
            "version": version,
            "type": self.node_type.value,  # 使用 type 而非 executor_type 保持一致性
            "description": self.description,
        }

        # 添加类型特定字段
        if self.code:
            data["code"] = self.code
        if self.prompt:
            data["prompt"] = self.prompt
        if self.url:
            data["url"] = self.url
            data["method"] = self.method
        if self.query:
            data["query"] = self.query

        # 添加 config 字段（包含所有配置，但排除默认的kind和version）
        if self.config:
            # 过滤掉已经在顶层的元数据字段
            config_to_export = {
                k: v
                for k, v in self.config.items()
                if k
                not in [
                    "kind",
                    "version",
                    "author",
                    "tags",
                    "category",
                    "parameters",
                    "returns",
                    "error_strategy",
                    "dynamic_code",
                ]
                # 排除默认值
                and not (k == "kind" and v == "node")
                and not (k == "version" and v == "1.0.0")
            }
            if config_to_export:
                data["config"] = config_to_export

        # 添加元数据
        if self.config.get("author"):
            data["author"] = self.config["author"]
        if self.config.get("tags"):
            data["tags"] = self.config["tags"]
        if self.config.get("category"):
            data["category"] = self.config["category"]

        # 添加参数
        if self.config.get("parameters"):
            data["parameters"] = self.config["parameters"]

        # 添加返回值
        if self.config.get("returns"):
            data["returns"] = self.config["returns"]

        # 添加错误策略
        if self.config.get("error_strategy"):
            data["error_strategy"] = self.config["error_strategy"]

        # 添加动态代码
        if self.config.get("dynamic_code"):
            data["dynamic_code"] = self.config["dynamic_code"]

        # 添加嵌套节点
        if self.children:
            nested = {"children": []}
            if self.config.get("nested_parallel"):
                nested["parallel"] = True
            for child in self.children:
                child_yaml = child.to_yaml_dict()
                nested["children"].append(child_yaml)
            data["nested"] = nested

        return data

    def to_yaml(self) -> str:
        """序列化为 YAML 字符串

        返回：
            YAML 格式字符串
        """
        data = self.to_yaml_dict()
        return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # ========== Phase 8.1 扩展: DAG 操作 ==========

    def find_node_by_name(self, name: str) -> "NodeDefinition | None":
        """按名称查找节点（包括后代）

        参数：
            name: 节点名称

        返回：
            找到的节点或 None
        """
        if self.name == name:
            return self

        for child in self.children:
            found = child.find_node_by_name(name)
            if found:
                return found

        return None

    def get_execution_order(self) -> list["NodeDefinition"]:
        """获取执行顺序（拓扑排序）

        返回：
            按执行顺序排列的节点列表
        """
        # 简单实现：先返回所有子节点，再返回自己
        # 如果有 depends_on，需要进行拓扑排序

        # 构建依赖图
        nodes = {self.name: self}
        for child in self.children:
            nodes[child.name] = child

        # 检查依赖关系
        dependencies: dict[str, list[str]] = {}
        for child in self.children:
            depends_on = child.config.get("depends_on", [])
            dependencies[child.name] = depends_on

        # 简单拓扑排序
        visited = set()
        result = []

        def visit(node_name: str) -> None:
            if node_name in visited:
                return
            visited.add(node_name)

            # 先访问依赖
            for dep in dependencies.get(node_name, []):
                if dep in nodes:
                    visit(dep)

            if node_name in nodes:
                result.append(nodes[node_name])

        for child in self.children:
            visit(child.name)

        return result

    # ========== Phase 8.1 扩展: 输入输出验证 ==========

    def validate_input(self, input_data: dict[str, Any]) -> list[str]:
        """验证输入数据

        参数：
            input_data: 输入数据字典

        返回：
            错误消息列表（空列表表示验证通过）
        """
        errors = []
        parameters = self.config.get("parameters", [])

        if not isinstance(parameters, list):
            return errors

        for param in parameters:
            if not isinstance(param, dict):
                continue

            param_name = param.get("name")
            if not param_name:
                continue

            param_type = param.get("type", "any")
            required = param.get("required", False)
            constraints = param.get("constraints", {})

            # 检查必填
            if required and param_name not in input_data:
                errors.append(f"Missing required parameter: {param_name}")
                continue

            if param_name not in input_data:
                continue

            value = input_data[param_name]

            # 类型检查
            type_error = self._check_type(value, param_type, param_name)
            if type_error:
                errors.append(type_error)
                continue

            # 约束检查
            constraint_errors = self._check_constraints(value, constraints, param_name)
            errors.extend(constraint_errors)

        return errors

    def _check_type(self, value: Any, expected_type: str, param_name: str) -> str | None:
        """检查值类型"""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_map.get(expected_type)
        if expected and not isinstance(value, expected):
            return f"Type mismatch for {param_name}: expected {expected_type}, got {type(value).__name__}"

        return None

    def _check_constraints(
        self, value: Any, constraints: dict[str, Any], param_name: str
    ) -> list[str]:
        """检查约束"""
        errors = []

        if not isinstance(constraints, dict):
            return errors

        if "min" in constraints and isinstance(value, int | float):
            if value < constraints["min"]:
                errors.append(
                    f"Constraint violation for {param_name}: value {value} is less than min {constraints['min']}"
                )

        if "max" in constraints and isinstance(value, int | float):
            if value > constraints["max"]:
                errors.append(
                    f"Constraint violation for {param_name}: value {value} exceeds max {constraints['max']}"
                )

        if "pattern" in constraints and isinstance(value, str):
            import re

            pattern = constraints["pattern"]
            if not re.match(pattern, value):
                errors.append(
                    f"Constraint violation for {param_name}: value does not match pattern {pattern}"
                )

        return errors

    def validate_output(self, output_data: dict[str, Any]) -> list[str]:
        """验证输出数据

        参数：
            output_data: 输出数据字典

        返回：
            错误消息列表（空列表表示验证通过）
        """
        errors = []
        returns = self.config.get("returns", {})

        if not isinstance(returns, dict):
            return errors

        properties = returns.get("properties", {})
        for prop_name, prop_def in properties.items():
            if prop_name not in output_data:
                # 输出字段不是必须的，跳过
                continue

            if isinstance(prop_def, dict):
                expected_type = prop_def.get("type", "any")
                value = output_data[prop_name]
                type_error = self._check_type(value, expected_type, prop_name)
                if type_error:
                    errors.append(type_error)

        return errors


class NodeDefinitionFactory:
    """节点定义工厂

    提供便捷方法创建各类型节点定义。
    """

    @staticmethod
    def create_python_node(
        name: str,
        code: str,
        description: str = "",
        input_schema: dict[str, str] | None = None,
        output_schema: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> NodeDefinition:
        """创建 Python 节点定义

        参数：
            name: 节点名称
            code: Python 代码
            description: 节点描述
            input_schema: 输入 Schema
            output_schema: 输出 Schema
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例
        """
        return NodeDefinition(
            node_type=NodeType.PYTHON,
            name=name,
            code=code,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            config=kwargs,
        )

    @staticmethod
    def create_llm_node(
        name: str,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        description: str = "",
        **kwargs: Any,
    ) -> NodeDefinition:
        """创建 LLM 节点定义

        参数：
            name: 节点名称
            prompt: Prompt 模板
            model: 模型名称
            temperature: 温度参数
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例
        """
        config = {
            "model": model,
            "temperature": temperature,
            **kwargs,
        }
        return NodeDefinition(
            node_type=NodeType.LLM,
            name=name,
            prompt=prompt,
            description=description,
            config=config,
        )

    @staticmethod
    def create_http_node(
        name: str,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        description: str = "",
        **kwargs: Any,
    ) -> NodeDefinition:
        """创建 HTTP 节点定义

        参数：
            name: 节点名称
            url: 请求 URL
            method: 请求方法
            headers: 请求头
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例
        """
        config = {
            "headers": headers or {},
            **kwargs,
        }
        return NodeDefinition(
            node_type=NodeType.HTTP,
            name=name,
            url=url,
            method=method,
            description=description,
            config=config,
        )

    @staticmethod
    def create_database_node(
        name: str,
        query: str,
        database: str = "default",
        description: str = "",
        **kwargs: Any,
    ) -> NodeDefinition:
        """创建 Database 节点定义

        参数：
            name: 节点名称
            query: SQL 查询
            database: 数据库名称
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例
        """
        config = {
            "database": database,
            **kwargs,
        }
        return NodeDefinition(
            node_type=NodeType.DATABASE,
            name=name,
            query=query,
            description=description,
            config=config,
        )

    @staticmethod
    def create_container_node(
        name: str,
        code: str,
        image: str = "python:3.11-slim",
        timeout: int = 60,
        memory_limit: str = "256m",
        pip_packages: list[str] | None = None,
        environment: dict[str, str] | None = None,
        description: str = "",
        **kwargs: Any,
    ) -> "NodeDefinition":
        """创建容器执行节点定义 (Phase 4)

        参数：
            name: 节点名称
            code: Python 代码
            image: Docker 镜像
            timeout: 超时时间（秒）
            memory_limit: 内存限制
            pip_packages: pip 依赖包列表
            environment: 环境变量
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例
        """
        container_config = {
            "image": image,
            "timeout": timeout,
            "memory_limit": memory_limit,
            "pip_packages": pip_packages or [],
            "environment": environment or {},
            **kwargs,
        }
        return NodeDefinition(
            node_type=NodeType.CONTAINER,
            name=name,
            code=code,
            description=description,
            is_container=True,
            container_config=container_config,
        )

    # ========== Phase 8.3: 场景化节点模板 ==========

    @staticmethod
    def create_data_collection_node(
        name: str,
        table: str | None = None,
        query: str | None = None,
        time_range: str | None = None,
        filters: dict[str, Any] | None = None,
        database: str = "default",
        description: str = "",
        **kwargs: Any,
    ) -> "NodeDefinition":
        """创建数据采集节点定义（DATABASE 类型）

        用于从数据库获取数据的场景。

        参数：
            name: 节点名称
            table: 数据表名
            query: 自定义 SQL 查询（优先于 table）
            time_range: 时间范围（如 "3 months", "90 days"）
            filters: 过滤条件字典
            database: 数据库名称
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例

        示例：
            # 使用表名和时间范围
            node = create_data_collection_node(
                name="获取销售数据",
                table="sales",
                time_range="3 months",
                filters={"status": "completed"}
            )

            # 使用自定义查询
            node = create_data_collection_node(
                name="复杂查询",
                query="SELECT * FROM sales WHERE amount > 1000"
            )
        """
        # 生成 SQL 查询
        if query:
            # 使用自定义查询
            sql_query = query
        elif table:
            # 构建基础查询
            sql_query = f"SELECT * FROM {table}"

            # 添加时间范围条件
            conditions = []
            if time_range:
                # 解析时间范围
                if "month" in time_range.lower():
                    num_months = (
                        int(time_range.split()[0]) if time_range.split()[0].isdigit() else 3
                    )
                    conditions.append(f"date >= DATE_SUB(NOW(), INTERVAL {num_months} MONTH)")
                elif "day" in time_range.lower():
                    num_days = int(time_range.split()[0]) if time_range.split()[0].isdigit() else 90
                    conditions.append(f"date >= DATE_SUB(NOW(), INTERVAL {num_days} DAY)")

            # 添加过滤条件
            if filters:
                for key, value in filters.items():
                    if isinstance(value, str):
                        conditions.append(f"{key} = '{value}'")
                    else:
                        conditions.append(f"{key} = {value}")

            # 组合条件
            if conditions:
                sql_query += " WHERE " + " AND ".join(conditions)
        else:
            raise ValueError("Either 'table' or 'query' must be provided")

        # 配置
        config = {
            "database": database,
            "table": table,
            "time_range": time_range,
            "filters": filters or {},
            **kwargs,
        }

        return NodeDefinition(
            node_type=NodeType.DATABASE,
            name=name,
            query=sql_query,
            description=description or f"从 {table or 'database'} 采集数据",
            config=config,
            input_schema={},
            output_schema={"data": "list[dict]"},
        )

    @staticmethod
    def create_metric_calculation_node(
        name: str,
        metrics: list[str],
        group_by: str | None = None,
        description: str = "",
        **kwargs: Any,
    ) -> "NodeDefinition":
        """创建指标计算节点定义（PYTHON 类型）

        用于计算统计指标的场景（使用 pandas）。

        参数：
            name: 节点名称
            metrics: 指标列表，如 ["sum", "avg", "max", "min", "count", "trend"]
            group_by: 分组字段
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例

        示例：
            node = create_metric_calculation_node(
                name="计算月度销售额",
                metrics=["sum", "avg", "trend"],
                group_by="month"
            )
        """
        # 生成 pandas 计算代码
        code_lines = [
            "import pandas as pd",
            "import numpy as np",
            "",
            "# 获取输入数据",
            "data = input_data.get('data', [])",
            "df = pd.DataFrame(data)",
            "",
        ]

        # 分组逻辑
        if group_by:
            code_lines.append(f"# 按 {group_by} 分组计算")
            code_lines.append(f"grouped = df.groupby('{group_by}')")
            code_lines.append("")
            code_lines.append("# 计算指标")
            code_lines.append("metrics = {}")

            for metric in metrics:
                if metric.lower() == "sum":
                    code_lines.append(
                        f"metrics['{group_by}_sum'] = grouped['amount'].sum().to_dict()"
                    )
                elif metric.lower() in ["avg", "mean"]:
                    code_lines.append(
                        f"metrics['{group_by}_avg'] = grouped['amount'].mean().to_dict()"
                    )
                elif metric.lower() == "max":
                    code_lines.append(
                        f"metrics['{group_by}_max'] = grouped['amount'].max().to_dict()"
                    )
                elif metric.lower() == "min":
                    code_lines.append(
                        f"metrics['{group_by}_min'] = grouped['amount'].min().to_dict()"
                    )
                elif metric.lower() == "count":
                    code_lines.append(f"metrics['{group_by}_count'] = grouped.size().to_dict()")
        else:
            code_lines.append("# 计算全局指标")
            code_lines.append("metrics = {}")

            for metric in metrics:
                if metric.lower() == "sum":
                    code_lines.append("metrics['total_sum'] = df['amount'].sum()")
                elif metric.lower() in ["avg", "mean"]:
                    code_lines.append("metrics['avg'] = df['amount'].mean()")
                elif metric.lower() == "max":
                    code_lines.append("metrics['max'] = df['amount'].max()")
                elif metric.lower() == "min":
                    code_lines.append("metrics['min'] = df['amount'].min()")
                elif metric.lower() == "count":
                    code_lines.append("metrics['count'] = len(df)")

        # 趋势计算
        if "trend" in [m.lower() for m in metrics]:
            code_lines.append("")
            code_lines.append("# 计算趋势")
            code_lines.append("if len(df) > 1:")
            code_lines.append("    first_value = df['amount'].iloc[0]")
            code_lines.append("    last_value = df['amount'].iloc[-1]")
            code_lines.append(
                "    metrics['trend'] = '上升' if last_value > first_value else '下降'"
            )

        code_lines.append("")
        code_lines.append("# 返回结果")
        code_lines.append("output = {'metrics': metrics}")

        code = "\n".join(code_lines)

        config = {
            "metrics": metrics,
            "group_by": group_by,
            **kwargs,
        }

        return NodeDefinition(
            node_type=NodeType.PYTHON,
            name=name,
            code=code,
            description=description or f"计算 {', '.join(metrics)} 指标",
            config=config,
            input_schema={"data": "list[dict]", "input_data": "dict"},
            output_schema={"metrics": "dict"},
        )

    @staticmethod
    def create_chart_generation_node(
        name: str,
        chart_type: str,
        title: str,
        x_label: str = "",
        y_label: str = "",
        figsize: tuple[int, int] = (10, 6),
        color: str | None = None,
        description: str = "",
        **kwargs: Any,
    ) -> "NodeDefinition":
        """创建图表生成节点定义（PYTHON 类型）

        用于生成可视化图表的场景（使用 matplotlib）。

        参数：
            name: 节点名称
            chart_type: 图表类型（"line", "bar", "pie"）
            title: 图表标题
            x_label: X 轴标签
            y_label: Y 轴标签
            figsize: 图表尺寸 (width, height)
            color: 图表颜色
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例

        示例：
            node = create_chart_generation_node(
                name="生成销售趋势图",
                chart_type="line",
                title="月度销售趋势",
                x_label="月份",
                y_label="销售额（元）"
            )
        """
        # 生成 matplotlib 绘图代码
        code_lines = [
            "import matplotlib.pyplot as plt",
            "import matplotlib",
            "matplotlib.use('Agg')  # 无图形界面后端",
            "",
            "# 获取输入数据",
            "metrics = input_data.get('metrics', {})",
            "",
            "# 准备绘图数据",
        ]

        if chart_type.lower() == "line":
            code_lines.extend(
                [
                    "x_data = list(metrics.keys())",
                    "y_data = list(metrics.values())",
                    "",
                    "# 创建折线图",
                    f"plt.figure(figsize={figsize})",
                ]
            )
            if color:
                code_lines.append(f"plt.plot(x_data, y_data, marker='o', color='{color}')")
            else:
                code_lines.append("plt.plot(x_data, y_data, marker='o')")

        elif chart_type.lower() == "bar":
            code_lines.extend(
                [
                    "x_data = list(metrics.keys())",
                    "y_data = list(metrics.values())",
                    "",
                    "# 创建柱状图",
                    f"plt.figure(figsize={figsize})",
                ]
            )
            if color:
                code_lines.append(f"plt.bar(x_data, y_data, color='{color}')")
            else:
                code_lines.append("plt.bar(x_data, y_data)")

        elif chart_type.lower() == "pie":
            code_lines.extend(
                [
                    "labels = list(metrics.keys())",
                    "sizes = list(metrics.values())",
                    "",
                    "# 创建饼图",
                    f"plt.figure(figsize={figsize})",
                    "plt.pie(sizes, labels=labels, autopct='%1.1f%%')",
                ]
            )

        # 添加标题和标签
        code_lines.extend(
            [
                "",
                f"plt.title('{title}')",
            ]
        )
        if x_label and chart_type.lower() != "pie":
            code_lines.append(f"plt.xlabel('{x_label}')")
        if y_label and chart_type.lower() != "pie":
            code_lines.append(f"plt.ylabel('{y_label}')")

        # 保存图表
        code_lines.extend(
            [
                "plt.grid(True, alpha=0.3)",
                "plt.tight_layout()",
                "",
                "# 保存图表",
                "output_path = '/tmp/chart.png'",
                "plt.savefig(output_path, dpi=300, bbox_inches='tight')",
                "plt.close()",
                "",
                "# 返回结果",
                "output = {",
                "    'chart_path': output_path,",
                f"    'chart_type': '{chart_type}',",
                "    'status': 'success'",
                "}",
            ]
        )

        code = "\n".join(code_lines)

        config = {
            "chart_type": chart_type,
            "title": title,
            "x_label": x_label,
            "y_label": y_label,
            "figsize": figsize,
            "color": color,
            **kwargs,
        }

        return NodeDefinition(
            node_type=NodeType.PYTHON,
            name=name,
            code=code,
            description=description or f"生成 {chart_type} 类型图表",
            config=config,
            input_schema={"metrics": "dict", "input_data": "dict"},
            output_schema={"chart_path": "str", "status": "str"},
        )

    @staticmethod
    def create_data_analysis_node(
        name: str,
        analysis_type: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        description: str = "",
        **kwargs: Any,
    ) -> "NodeDefinition":
        """创建数据分析节点定义（LLM 类型）

        用于 LLM 分析数据并生成报告的场景。

        参数：
            name: 节点名称
            analysis_type: 分析类型（"summary", "insight", "recommendation"）
            model: LLM 模型名称
            temperature: 温度参数
            description: 节点描述
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例

        示例：
            node = create_data_analysis_node(
                name="生成销售分析报告",
                analysis_type="summary",
                model="gpt-4-turbo"
            )
        """
        # 根据分析类型生成 prompt
        if analysis_type.lower() == "summary":
            prompt = """请基于以下数据生成简洁的总结报告（Summary Report）：

数据概览：
{data}

指标统计：
{metrics}

趋势分析：
{trend}

要求：
1. 概括主要数据特征
2. 突出关键指标
3. 说明整体趋势
4. 使用清晰的 Markdown 格式
"""
        elif analysis_type.lower() == "insight":
            prompt = """请基于以下数据进行深度洞察分析（Insight Analysis）：

数据：
{data}

指标：
{metrics}

要求：
1. 发现数据中的模式和规律
2. 识别异常值或特殊情况
3. 分析潜在的因果关系
4. 提供数据驱动的洞察
5. 使用 Markdown 格式，包含具体数据引用
"""
        elif analysis_type.lower() == "recommendation":
            prompt = """请基于以下数据生成可执行的建议（Recommendation）：

当前数据：
{data}

指标表现：
{metrics}

趋势：
{trend}

要求：
1. 基于数据分析提出3-5条建议
2. 每条建议包含：目标、理由、预期效果
3. 按优先级排序
4. 使用 Markdown 格式
"""
        else:
            # 通用分析 prompt
            prompt = """请分析以下数据并生成报告：

{data}

{metrics}

请提供详细的分析结果。"""

        config = {
            "model": model,
            "temperature": temperature,
            "analysis_type": analysis_type,
            **kwargs,
        }

        return NodeDefinition(
            node_type=NodeType.LLM,
            name=name,
            prompt=prompt,
            description=description or f"生成 {analysis_type} 类型分析",
            config=config,
            input_schema={"data": "any", "metrics": "dict", "trend": "str"},
            output_schema={"report": "str"},
        )


# 导出
__all__ = [
    "MAX_NODE_DEFINITION_DEPTH",
    "NodeType",
    "NodeDefinition",
    "NodeDefinitionFactory",
]

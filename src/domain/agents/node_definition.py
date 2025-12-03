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
from typing import Any
from uuid import uuid4

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

        # GENERIC、CONDITION、LOOP、PARALLEL 类型无特殊要求

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

        返回：
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
        )

        # Phase 4: 递归恢复子节点
        children_data = data.get("children", [])
        for child_data in children_data:
            child = cls.from_dict(child_data)
            child.parent_id = node.id  # 设置父节点ID
            node.children.append(child)

        return node


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


# 导出
__all__ = [
    "MAX_NODE_DEFINITION_DEPTH",
    "NodeType",
    "NodeDefinition",
    "NodeDefinitionFactory",
]

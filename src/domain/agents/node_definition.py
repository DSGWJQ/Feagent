"""节点定义 (NodeDefinition) - Phase 8.1

业务定义：
- 节点定义是 Agent 自定义节点功能的数据结构
- 支持多种节点类型：Python、LLM、HTTP、Database 等
- 包含验证逻辑确保节点配置完整

设计原则：
- 类型安全：每种节点类型有明确的必填字段
- 可序列化：支持 to_dict/from_dict 便于存储和传输
- 可扩展：通过 config 字典支持额外配置

使用示例：
    node = NodeDefinition(
        node_type=NodeType.PYTHON,
        name="数据处理",
        code="return process(data)",
        input_schema={"data": "dict"},
    )
    errors = node.validate()
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


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

        # GENERIC、CONDITION、LOOP、PARALLEL 类型无特殊要求

        return errors

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典

        返回：
            包含所有字段的字典
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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeDefinition":
        """从字典反序列化

        参数：
            data: 包含节点定义的字典

        返回：
            NodeDefinition 实例
        """
        node_type_str = data.get("node_type", "generic")
        try:
            node_type = NodeType(node_type_str)
        except ValueError:
            node_type = NodeType.GENERIC

        return cls(
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
        )


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


# 导出
__all__ = [
    "NodeType",
    "NodeDefinition",
    "NodeDefinitionFactory",
]

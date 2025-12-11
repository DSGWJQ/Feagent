"""Schema 自动推断服务 - GAP-003

业务定义：
- 从样本数据自动推断 JSON Schema
- 从 Python 代码推断输出 Schema
- 检查节点间 Schema 兼容性

设计原则：
- 支持基本类型和复合类型推断
- 支持嵌套对象和数组
- 支持代码静态分析

使用示例：
    service = SchemaInference()
    schema = service.infer_from_data({"name": "test", "value": 123})
    # -> {"type": "object", "properties": {...}}
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from src.domain.agents.node_definition import NodeDefinition
    from src.domain.agents.workflow_plan import WorkflowPlan


class SchemaInference:
    """Schema 自动推断服务

    提供以下功能：
    1. 从样本数据推断 JSON Schema
    2. 从 Python 代码推断输出 Schema
    3. 检查 Schema 兼容性
    4. 验证工作流中的 Schema 流
    """

    def infer_from_data(self, data: Any) -> dict[str, Any]:
        """从样本数据推断 JSON Schema

        参数：
            data: 样本数据

        返回：
            推断出的 JSON Schema
        """
        if data is None:
            return {"type": "null"}

        if isinstance(data, bool):
            # bool 必须在 int 之前检查，因为 bool 是 int 的子类
            return {"type": "boolean"}

        if isinstance(data, int):
            return {"type": "integer"}

        if isinstance(data, float):
            return {"type": "number"}

        if isinstance(data, str):
            return {"type": "string"}

        if isinstance(data, list):
            return self._infer_array_schema(data)

        if isinstance(data, dict):
            return self._infer_object_schema(data)

        # 其他类型作为字符串处理
        return {"type": "string"}

    def _infer_array_schema(self, data: list[Any]) -> dict[str, Any]:
        """推断数组 Schema

        参数：
            data: 数组数据

        返回：
            数组的 JSON Schema
        """
        if not data:
            # 空数组
            return {"type": "array", "items": {}}

        # 收集所有元素的类型
        item_schemas = [self.infer_from_data(item) for item in data]

        # 检查是否所有元素类型相同
        types = set(s.get("type") for s in item_schemas)

        if len(types) == 1:
            # 所有元素类型相同
            return {"type": "array", "items": item_schemas[0]}
        else:
            # 混合类型，使用 anyOf
            unique_schemas = []
            seen_types = set()
            for schema in item_schemas:
                schema_type = schema.get("type")
                if schema_type not in seen_types:
                    seen_types.add(schema_type)
                    unique_schemas.append(schema)

            return {"type": "array", "items": {"anyOf": unique_schemas}}

    def _infer_object_schema(self, data: dict[str, Any]) -> dict[str, Any]:
        """推断对象 Schema

        参数：
            data: 对象数据

        返回：
            对象的 JSON Schema
        """
        properties = {}
        for key, value in data.items():
            properties[key] = self.infer_from_data(value)

        return {
            "type": "object",
            "properties": properties,
        }

    def infer_from_code(self, code: str) -> dict[str, Any] | None:
        """从 Python 代码推断输出 Schema

        通过解析代码中的 return 语句和类型提示来推断。

        参数：
            code: Python 代码字符串

        返回：
            推断出的 JSON Schema，或 None
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        # 查找函数定义和返回语句
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检查类型提示
                schema = self._infer_from_type_hint(node)
                if schema:
                    return schema

                # 检查返回语句
                schema = self._infer_from_returns(node)
                if schema:
                    return schema

        return {"type": "object"}

    def _infer_from_type_hint(self, func_node: ast.FunctionDef) -> dict[str, Any] | None:
        """从函数类型提示推断 Schema

        参数：
            func_node: 函数 AST 节点

        返回：
            推断的 Schema 或 None
        """
        if func_node.returns is None:
            return None

        return self._ast_annotation_to_schema(func_node.returns)

    def _ast_annotation_to_schema(self, annotation: ast.expr) -> dict[str, Any]:
        """将 AST 类型注解转换为 Schema

        参数：
            annotation: AST 注解节点

        返回：
            JSON Schema
        """
        if isinstance(annotation, ast.Name):
            name = annotation.id
            type_map = {
                "str": {"type": "string"},
                "int": {"type": "integer"},
                "float": {"type": "number"},
                "bool": {"type": "boolean"},
                "list": {"type": "array"},
                "dict": {"type": "object"},
                "None": {"type": "null"},
            }
            return type_map.get(name, {"type": "object"})

        if isinstance(annotation, ast.Subscript):
            # 处理泛型类型，如 dict[str, int], list[str]
            if isinstance(annotation.value, ast.Name):
                base_type = annotation.value.id
                if base_type == "dict":
                    return {"type": "object"}
                if base_type == "list":
                    return {"type": "array"}

        return {"type": "object"}

    def _infer_from_returns(self, func_node: ast.FunctionDef) -> dict[str, Any] | None:
        """从函数返回语句推断 Schema

        参数：
            func_node: 函数 AST 节点

        返回：
            推断的 Schema 或 None
        """
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value is not None:
                return self._infer_from_ast_value(node.value)
        return None

    def _infer_from_ast_value(self, value: ast.expr) -> dict[str, Any]:
        """从 AST 值节点推断 Schema

        参数：
            value: AST 值节点

        返回：
            JSON Schema
        """
        if isinstance(value, ast.Dict):
            # 字典字面量
            properties = {}
            for key, val in zip(value.keys, value.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    properties[key.value] = self._infer_from_ast_value(val)
            return {"type": "object", "properties": properties}

        if isinstance(value, ast.List):
            # 列表字面量
            return {"type": "array"}

        if isinstance(value, ast.Constant):
            # 常量值
            return self.infer_from_data(value.value)

        if isinstance(value, ast.Call):
            # 函数调用，可能是 dataclass 构造
            if isinstance(value.func, ast.Name):
                return {"type": "object"}

        # 默认为对象
        return {"type": "object"}

    def check_compatibility(
        self,
        output_schema: dict[str, Any],
        input_schema: dict[str, Any],
    ) -> bool:
        """检查两个 Schema 是否兼容

        判断输出 Schema 是否能满足输入 Schema 的要求。

        参数：
            output_schema: 上游节点的输出 Schema
            input_schema: 下游节点的输入 Schema

        返回：
            True 如果兼容，False 如果不兼容
        """
        # 获取输入所需的字段
        required_fields = input_schema.get("required", [])
        input_properties = input_schema.get("properties", {})
        output_properties = output_schema.get("properties", {})

        # 检查必需字段是否存在
        for field in required_fields:
            if field not in output_properties:
                return False

            # 检查类型是否匹配
            if field in input_properties:
                output_type = output_properties[field].get("type")
                input_type = input_properties[field].get("type")

                if output_type != input_type:
                    # 检查类型兼容性（integer 可以兼容 number）
                    if not self._types_compatible(output_type, input_type):
                        return False

        return True

    def _types_compatible(self, output_type: str | None, input_type: str | None) -> bool:
        """检查两个类型是否兼容

        参数：
            output_type: 输出类型
            input_type: 输入类型

        返回：
            True 如果兼容
        """
        if output_type == input_type:
            return True

        # integer 可以兼容 number
        if output_type == "integer" and input_type == "number":
            return True

        return False

    def validate_workflow_schema_flow(
        self,
        plan: "WorkflowPlan",
    ) -> list[str]:
        """验证工作流中的 Schema 流

        检查每条边的源节点输出是否与目标节点输入兼容。

        参数：
            plan: 工作流规划

        返回：
            错误列表，空列表表示无错误
        """
        errors = []

        # 构建节点名称到节点的映射
        node_map = {node.name: node for node in plan.nodes}

        # 检查每条边
        for edge in plan.edges:
            source_node = node_map.get(edge.source_node)
            target_node = node_map.get(edge.target_node)

            if not source_node or not target_node:
                continue

            # 获取 Schema
            output_schema = getattr(source_node, "output_schema", None)
            input_schema = getattr(target_node, "input_schema", None)

            if output_schema and input_schema:
                if not self.check_compatibility(output_schema, input_schema):
                    errors.append(
                        f"Schema 不匹配: {edge.source_node} -> {edge.target_node}"
                    )

        return errors

    def infer_node_output_schema(
        self,
        node: "NodeDefinition",
    ) -> dict[str, Any] | None:
        """自动推断节点的输出 Schema

        从节点代码推断输出 Schema。

        参数：
            node: 节点定义

        返回：
            推断的 JSON Schema 或 None
        """
        code = getattr(node, "code", None)
        if not code:
            return None

        return self.infer_from_code(code)


# 导出
__all__ = ["SchemaInference"]

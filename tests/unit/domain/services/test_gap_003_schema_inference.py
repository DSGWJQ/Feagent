"""GAP-003: Schema 自动推断测试

测试目标：验证 SchemaInference 服务能够自动推断 JSON Schema
- 从样本数据推断 Schema
- 从 Python 代码推断输出 Schema
- 节点间 Schema 兼容性检查

TDD 阶段：Red（测试先行）
"""

import pytest
from typing import Any


class TestSchemaInferenceFromData:
    """从数据推断 Schema 测试"""

    def test_schema_inference_service_exists(self):
        """测试 SchemaInference 服务存在"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        assert service is not None

    def test_infer_string_type(self):
        """测试推断字符串类型"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        schema = service.infer_from_data("hello world")

        assert schema["type"] == "string"

    def test_infer_integer_type(self):
        """测试推断整数类型"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        schema = service.infer_from_data(42)

        assert schema["type"] == "integer"

    def test_infer_number_type(self):
        """测试推断浮点数类型"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        schema = service.infer_from_data(3.14)

        assert schema["type"] == "number"

    def test_infer_boolean_type(self):
        """测试推断布尔类型"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        schema = service.infer_from_data(True)

        assert schema["type"] == "boolean"

    def test_infer_array_type(self):
        """测试推断数组类型"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        schema = service.infer_from_data([1, 2, 3])

        assert schema["type"] == "array"
        assert "items" in schema
        assert schema["items"]["type"] == "integer"

    def test_infer_object_type(self):
        """测试推断对象类型"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        data = {"name": "test", "value": 123}
        schema = service.infer_from_data(data)

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "value" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["value"]["type"] == "integer"

    def test_infer_nested_object(self):
        """测试推断嵌套对象"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        data = {
            "user": {
                "name": "Alice",
                "age": 30
            },
            "active": True
        }
        schema = service.infer_from_data(data)

        assert schema["type"] == "object"
        assert schema["properties"]["user"]["type"] == "object"
        assert schema["properties"]["user"]["properties"]["name"]["type"] == "string"

    def test_infer_mixed_array(self):
        """测试推断混合类型数组"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        data = [1, "two", 3.0]
        schema = service.infer_from_data(data)

        assert schema["type"] == "array"
        # 混合类型应该用 anyOf 或更宽泛的类型
        assert "items" in schema

    def test_infer_null_value(self):
        """测试推断 null 值"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        schema = service.infer_from_data(None)

        assert schema["type"] == "null" or schema.get("nullable") is True


class TestSchemaInferenceFromCode:
    """从代码推断 Schema 测试"""

    def test_infer_from_simple_return(self):
        """测试从简单返回语句推断"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        code = '''
def process(data):
    return {"result": 123, "status": "ok"}
'''
        schema = service.infer_from_code(code)

        assert schema is not None
        assert schema["type"] == "object"
        assert "result" in schema.get("properties", {})

    def test_infer_from_type_hints(self):
        """测试从类型提示推断"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        code = '''
def process(data: dict) -> dict[str, int]:
    return {"count": len(data)}
'''
        schema = service.infer_from_code(code)

        assert schema is not None
        assert schema["type"] == "object"

    def test_infer_from_dataclass_return(self):
        """测试从 dataclass 返回类型推断"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()
        code = '''
from dataclasses import dataclass

@dataclass
class Result:
    value: int
    message: str

def process() -> Result:
    return Result(value=42, message="done")
'''
        schema = service.infer_from_code(code)

        assert schema is not None
        # 应该推断出 value 和 message 字段
        if "properties" in schema:
            assert "value" in schema["properties"] or "message" in schema["properties"]


class TestSchemaCompatibility:
    """Schema 兼容性检查测试"""

    def test_check_compatible_schemas(self):
        """测试兼容的 Schema"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()

        output_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "array"},
                "count": {"type": "integer"}
            }
        }

        input_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "array"}
            },
            "required": ["data"]
        }

        is_compatible = service.check_compatibility(output_schema, input_schema)
        assert is_compatible is True, "输出包含输入所需字段，应该兼容"

    def test_check_incompatible_schemas(self):
        """测试不兼容的 Schema"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()

        output_schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            }
        }

        input_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "array"}
            },
            "required": ["data"]
        }

        is_compatible = service.check_compatibility(output_schema, input_schema)
        assert is_compatible is False, "输出缺少必需的 data 字段，应该不兼容"

    def test_check_type_mismatch(self):
        """测试类型不匹配"""
        from src.domain.services.schema_inference import SchemaInference

        service = SchemaInference()

        output_schema = {
            "type": "object",
            "properties": {
                "value": {"type": "string"}  # 字符串
            }
        }

        input_schema = {
            "type": "object",
            "properties": {
                "value": {"type": "integer"}  # 期望整数
            },
            "required": ["value"]
        }

        is_compatible = service.check_compatibility(output_schema, input_schema)
        assert is_compatible is False, "类型不匹配，应该不兼容"


class TestNodeSchemaValidation:
    """节点 Schema 验证测试"""

    def test_validate_workflow_schema_flow(self):
        """测试工作流中的 Schema 流验证"""
        from src.domain.services.schema_inference import SchemaInference
        from src.domain.agents.workflow_plan import WorkflowPlan, EdgeDefinition
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        service = SchemaInference()

        # 创建两个节点
        node1 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="producer",
            code="return {'data': [1,2,3]}",
            output_schema={
                "type": "object",
                "properties": {"data": {"type": "array"}}
            }
        )

        node2 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="consumer",
            code="return sum(data)",
            input_schema={
                "type": "object",
                "properties": {"data": {"type": "array"}},
                "required": ["data"]
            }
        )

        plan = WorkflowPlan(
            name="test",
            goal="test",
            nodes=[node1, node2],
            edges=[EdgeDefinition(source_node="producer", target_node="consumer")]
        )

        # 验证 Schema 流
        schema_errors = service.validate_workflow_schema_flow(plan)
        assert len(schema_errors) == 0, "Schema 应该兼容，无错误"

    def test_detect_schema_mismatch_in_workflow(self):
        """测试检测工作流中的 Schema 不匹配"""
        from src.domain.services.schema_inference import SchemaInference
        from src.domain.agents.workflow_plan import WorkflowPlan, EdgeDefinition
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        service = SchemaInference()

        node1 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="producer",
            code="return {'result': 'text'}",
            output_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}}
            }
        )

        node2 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="consumer",
            code="return data * 2",
            input_schema={
                "type": "object",
                "properties": {"data": {"type": "array"}},  # 期望 array
                "required": ["data"]
            }
        )

        plan = WorkflowPlan(
            name="test",
            goal="test",
            nodes=[node1, node2],
            edges=[EdgeDefinition(source_node="producer", target_node="consumer")]
        )

        schema_errors = service.validate_workflow_schema_flow(plan)
        assert len(schema_errors) > 0, "应该检测到 Schema 不匹配"


class TestAutoSchemaInference:
    """自动 Schema 推断集成测试"""

    def test_auto_infer_node_output_schema(self):
        """测试自动推断节点输出 Schema"""
        from src.domain.services.schema_inference import SchemaInference
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        service = SchemaInference()

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test",
            code='''
def execute(input_data):
    return {
        "total": sum(input_data),
        "count": len(input_data),
        "average": sum(input_data) / len(input_data)
    }
'''
        )

        # 自动推断输出 Schema
        inferred_schema = service.infer_node_output_schema(node)

        assert inferred_schema is not None
        assert inferred_schema["type"] == "object"

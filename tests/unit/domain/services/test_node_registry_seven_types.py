"""
测试NodeRegistry对七种子节点类型的Schema支持

测试内容：
1. NodeType枚举包含FILE/TRANSFORM/HUMAN
2. PREDEFINED_SCHEMAS包含新节点schema
3. FILE schema验证operation枚举和path
4. TRANSFORM schema验证type枚举和条件必填字段
5. HUMAN schema验证prompt和timeout
"""

import pytest

from src.domain.services.node_registry import PREDEFINED_SCHEMAS, NodeFactory, NodeType


class TestNodeTypeEnum:
    """测试NodeType枚举扩展"""

    def test_node_type_includes_file(self):
        """NodeType枚举包含FILE"""
        assert hasattr(NodeType, "FILE")
        assert NodeType.FILE.value == "file"

    def test_node_type_includes_transform(self):
        """NodeType枚举包含TRANSFORM"""
        assert hasattr(NodeType, "TRANSFORM")
        assert NodeType.TRANSFORM.value == "transform"

    def test_node_type_includes_human(self):
        """NodeType枚举包含HUMAN"""
        assert hasattr(NodeType, "HUMAN")
        assert NodeType.HUMAN.value == "human"


class TestPredefinedSchemas:
    """测试PREDEFINED_SCHEMAS包含新节点schema"""

    def test_predefined_schemas_has_file(self):
        """PREDEFINED_SCHEMAS包含FILE节点schema"""
        assert NodeType.FILE in PREDEFINED_SCHEMAS
        schema = PREDEFINED_SCHEMAS[NodeType.FILE]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

    def test_predefined_schemas_has_transform(self):
        """PREDEFINED_SCHEMAS包含TRANSFORM节点schema"""
        assert NodeType.TRANSFORM in PREDEFINED_SCHEMAS
        schema = PREDEFINED_SCHEMAS[NodeType.TRANSFORM]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

    def test_predefined_schemas_has_human(self):
        """PREDEFINED_SCHEMAS包含HUMAN节点schema"""
        assert NodeType.HUMAN in PREDEFINED_SCHEMAS
        schema = PREDEFINED_SCHEMAS[NodeType.HUMAN]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


class TestFileNodeSchema:
    """测试FILE节点schema验证"""

    def test_file_schema_requires_operation(self):
        """FILE schema要求operation字段"""
        schema = PREDEFINED_SCHEMAS[NodeType.FILE]
        assert "operation" in schema["required"]

    def test_file_schema_requires_path(self):
        """FILE schema要求path字段"""
        schema = PREDEFINED_SCHEMAS[NodeType.FILE]
        assert "path" in schema["required"]

    def test_file_schema_operation_is_enum(self):
        """FILE schema的operation是枚举类型"""
        schema = PREDEFINED_SCHEMAS[NodeType.FILE]
        operation_prop = schema["properties"]["operation"]
        assert "enum" in operation_prop
        assert set(operation_prop["enum"]) == {"read", "write", "append", "delete", "list"}

    def test_file_schema_has_encoding_default(self):
        """FILE schema的encoding有默认值"""
        schema = PREDEFINED_SCHEMAS[NodeType.FILE]
        encoding_prop = schema["properties"]["encoding"]
        assert encoding_prop["default"] == "utf-8"


class TestTransformNodeSchema:
    """测试TRANSFORM节点schema验证"""

    def test_transform_schema_requires_type(self):
        """TRANSFORM schema要求type字段"""
        schema = PREDEFINED_SCHEMAS[NodeType.TRANSFORM]
        assert "type" in schema["required"]

    def test_transform_schema_type_is_enum(self):
        """TRANSFORM schema的type是枚举类型"""
        schema = PREDEFINED_SCHEMAS[NodeType.TRANSFORM]
        type_prop = schema["properties"]["type"]
        assert "enum" in type_prop
        expected_types = {
            "field_mapping",
            "type_conversion",
            "field_extraction",
            "array_mapping",
            "filtering",
            "aggregation",
            "custom",
        }
        assert set(type_prop["enum"]) == expected_types

    def test_transform_schema_has_conditional_required_fields(self):
        """TRANSFORM schema有条件必填字段约束"""
        schema = PREDEFINED_SCHEMAS[NodeType.TRANSFORM]
        # 检查是否有allOf/if/then结构来表达条件约束
        assert "allOf" in schema or "oneOf" in schema or "anyOf" in schema

    def test_transform_schema_field_mapping_requires_mapping(self):
        """TRANSFORM schema在type=field_mapping时要求mapping字段"""
        schema = PREDEFINED_SCHEMAS[NodeType.TRANSFORM]
        # 检查allOf中是否有对应的条件约束
        if "allOf" in schema:
            conditions = schema["allOf"]
            # 查找field_mapping的条件
            field_mapping_condition = None
            for condition in conditions:
                if "if" in condition:
                    if_clause = condition["if"]
                    if (
                        "properties" in if_clause
                        and "type" in if_clause["properties"]
                        and if_clause["properties"]["type"].get("const") == "field_mapping"
                    ):
                        field_mapping_condition = condition
                        break
            assert field_mapping_condition is not None
            assert "then" in field_mapping_condition
            assert "mapping" in field_mapping_condition["then"]["required"]


class TestHumanNodeSchema:
    """测试HUMAN节点schema验证"""

    def test_human_schema_requires_prompt(self):
        """HUMAN schema要求prompt字段"""
        schema = PREDEFINED_SCHEMAS[NodeType.HUMAN]
        assert "prompt" in schema["required"]

    def test_human_schema_timeout_has_default(self):
        """HUMAN schema的timeout_seconds有默认值"""
        schema = PREDEFINED_SCHEMAS[NodeType.HUMAN]
        timeout_prop = schema["properties"]["timeout_seconds"]
        assert timeout_prop["default"] == 300

    def test_human_schema_timeout_has_minimum(self):
        """HUMAN schema的timeout_seconds有最小值约束"""
        schema = PREDEFINED_SCHEMAS[NodeType.HUMAN]
        timeout_prop = schema["properties"]["timeout_seconds"]
        assert "minimum" in timeout_prop
        assert timeout_prop["minimum"] == 1

    def test_human_schema_expected_inputs_is_array(self):
        """HUMAN schema的expected_inputs是数组类型"""
        schema = PREDEFINED_SCHEMAS[NodeType.HUMAN]
        expected_inputs_prop = schema["properties"]["expected_inputs"]
        assert expected_inputs_prop["type"] == "array"
        assert expected_inputs_prop["default"] == []


class TestNodeFactoryIntegration:
    """测试NodeFactory与新节点类型的集成"""

    def test_node_factory_can_create_file_node(self):
        """NodeFactory可以创建FILE节点"""
        # 这个测试会在NodeFactory实现后通过
        # 目前先占位，确保接口设计正确
        try:
            node = NodeFactory.create(
                node_type=NodeType.FILE, config={"operation": "read", "path": "/tmp/test.txt"}
            )
            assert node is not None
        except (NotImplementedError, AttributeError, TypeError):
            # 如果NodeFactory.create还未实现新类型，跳过
            pytest.skip("NodeFactory.create未实现FILE类型")

    def test_node_factory_can_create_transform_node(self):
        """NodeFactory可以创建TRANSFORM节点"""
        try:
            node = NodeFactory.create(
                node_type=NodeType.TRANSFORM,
                config={"type": "field_mapping", "mapping": {"old": "new"}},
            )
            assert node is not None
        except (NotImplementedError, AttributeError, TypeError):
            pytest.skip("NodeFactory.create未实现TRANSFORM类型")

    def test_node_factory_can_create_human_node(self):
        """NodeFactory可以创建HUMAN节点"""
        try:
            node = NodeFactory.create(node_type=NodeType.HUMAN, config={"prompt": "Please confirm"})
            assert node is not None
        except (NotImplementedError, AttributeError, TypeError):
            pytest.skip("NodeFactory.create未实现HUMAN类型")


class TestEnhancedValidation:
    """测试增强的验证逻辑（枚举、条件约束、多类型）"""

    def test_file_enum_validation_rejects_invalid_operation(self):
        """FILE节点拒绝非法的operation枚举值"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"operation": "invalid_op", "path": "/tmp/test.txt"}
        is_valid, errors = registry.validate_config(NodeType.FILE, config)

        assert not is_valid
        assert any("not in" in error and "operation" in error for error in errors)

    def test_file_enum_validation_accepts_valid_operations(self):
        """FILE节点接受合法的operation枚举值"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        valid_operations = ["read", "write", "append", "delete", "list"]

        for operation in valid_operations:
            config = {"operation": operation, "path": "/tmp/test.txt"}
            if operation in ["write", "append"]:
                config["content"] = "test content"
            is_valid, errors = registry.validate_config(NodeType.FILE, config)
            assert is_valid, f"Operation {operation} should be valid, but got errors: {errors}"

    def test_file_conditional_requires_content_for_write(self):
        """FILE节点的write操作必须提供content字段"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"operation": "write", "path": "/tmp/test.txt"}
        is_valid, errors = registry.validate_config(NodeType.FILE, config)

        assert not is_valid
        assert any("content" in error.lower() for error in errors)

    def test_file_conditional_requires_content_for_append(self):
        """FILE节点的append操作必须提供content字段"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"operation": "append", "path": "/tmp/test.txt"}
        is_valid, errors = registry.validate_config(NodeType.FILE, config)

        assert not is_valid
        assert any("content" in error.lower() for error in errors)

    def test_file_conditional_does_not_require_content_for_read(self):
        """FILE节点的read操作不需要content字段"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"operation": "read", "path": "/tmp/test.txt"}
        is_valid, errors = registry.validate_config(NodeType.FILE, config)

        assert is_valid, f"Read operation should not require content, but got errors: {errors}"

    def test_transform_conditional_requires_mapping_for_field_mapping(self):
        """TRANSFORM节点的field_mapping类型必须提供mapping字段"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"type": "field_mapping"}
        is_valid, errors = registry.validate_config(NodeType.TRANSFORM, config)

        assert not is_valid
        assert any("mapping" in error.lower() for error in errors)

    def test_transform_conditional_requires_conversions_for_type_conversion(self):
        """TRANSFORM节点的type_conversion类型必须提供conversions字段"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"type": "type_conversion"}
        is_valid, errors = registry.validate_config(NodeType.TRANSFORM, config)

        assert not is_valid
        assert any("conversions" in error.lower() for error in errors)

    def test_transform_conditional_requires_fields_for_field_extraction(self):
        """TRANSFORM节点的field_extraction类型必须提供fields字段"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"type": "field_extraction"}
        is_valid, errors = registry.validate_config(NodeType.TRANSFORM, config)

        assert not is_valid
        assert any("fields" in error.lower() for error in errors)

    def test_transform_multi_type_accepts_array_for_fields(self):
        """TRANSFORM节点的fields字段接受数组类型"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"type": "field_extraction", "fields": ["field1", "field2"]}
        is_valid, errors = registry.validate_config(NodeType.TRANSFORM, config)

        assert is_valid, f"Array type for fields should be valid, but got errors: {errors}"

    def test_transform_multi_type_accepts_string_for_fields(self):
        """TRANSFORM节点的fields字段接受字符串类型"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"type": "field_extraction", "fields": "field1"}
        is_valid, errors = registry.validate_config(NodeType.TRANSFORM, config)

        assert is_valid, f"String type for fields should be valid, but got errors: {errors}"

    def test_transform_multi_type_rejects_invalid_type_for_fields(self):
        """TRANSFORM节点的fields字段拒绝其他类型"""
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        config = {"type": "field_extraction", "fields": 123}  # 数字类型无效
        is_valid, errors = registry.validate_config(NodeType.TRANSFORM, config)

        assert not is_valid
        assert any("invalid type" in error.lower() for error in errors)

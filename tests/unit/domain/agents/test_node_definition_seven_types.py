"""
测试NodeDefinition对七种子节点类型的支持

测试内容：
1. FILE节点validate需要operation和path
2. DATA_PROCESS节点validate需要type
3. HUMAN节点validate需要prompt
4. EXECUTOR_TYPE_MAP正确映射file/transform/human
5. from_yaml/to_yaml支持新配置
"""

from src.domain.agents.node_definition import NodeDefinition, NodeType


class TestFileNodeValidation:
    """测试FILE节点验证逻辑"""

    def test_file_node_requires_operation(self):
        """FILE节点必须有config.operation字段"""
        node = NodeDefinition(
            node_type=NodeType.FILE, name="test_file_node", config={"path": "/tmp/test.txt"}
        )
        errors = node.validate()
        assert any("operation" in error.lower() for error in errors)

    def test_file_node_requires_path(self):
        """FILE节点必须有config.path字段"""
        node = NodeDefinition(
            node_type=NodeType.FILE, name="test_file_node", config={"operation": "read"}
        )
        errors = node.validate()
        assert any("path" in error.lower() for error in errors)

    def test_file_node_requires_valid_operation(self):
        """FILE节点的operation必须是合法值"""
        node = NodeDefinition(
            node_type=NodeType.FILE,
            name="test_file_node",
            config={"operation": "invalid_op", "path": "/tmp/test.txt"},
        )
        errors = node.validate()
        assert any("operation" in error.lower() for error in errors)

    def test_file_node_valid_config(self):
        """FILE节点配置正确时通过验证"""
        for operation in ["read", "write", "append", "delete", "list"]:
            node = NodeDefinition(
                node_type=NodeType.FILE,
                name="test_file_node",
                config={"operation": operation, "path": "/tmp/test.txt"},
            )
            errors = node.validate()
            assert not errors


class TestDataProcessNodeValidation:
    """测试DATA_PROCESS节点验证逻辑"""

    def test_data_process_node_requires_type(self):
        """DATA_PROCESS节点必须有config.type字段"""
        node = NodeDefinition(node_type=NodeType.DATA_PROCESS, name="test_data_node", config={})
        errors = node.validate()
        assert any("type" in error.lower() for error in errors)

    def test_data_process_node_valid_config(self):
        """DATA_PROCESS节点配置正确时通过验证"""
        valid_types = [
            "field_mapping",
            "type_conversion",
            "field_extraction",
            "array_mapping",
            "filtering",
            "aggregation",
            "custom",
        ]
        for process_type in valid_types:
            node = NodeDefinition(
                node_type=NodeType.DATA_PROCESS,
                name="test_data_node",
                config={"type": process_type},
            )
            errors = node.validate()
            assert not errors


class TestHumanNodeValidation:
    """测试HUMAN节点验证逻辑"""

    def test_human_node_requires_prompt(self):
        """HUMAN节点必须有config.prompt字段"""
        node = NodeDefinition(node_type=NodeType.HUMAN, name="test_human_node", config={})
        errors = node.validate()
        assert any("prompt" in error.lower() for error in errors)

    def test_human_node_valid_config(self):
        """HUMAN节点配置正确时通过验证"""
        node = NodeDefinition(
            node_type=NodeType.HUMAN,
            name="test_human_node",
            config={"prompt": "Please confirm the action"},
        )
        errors = node.validate()
        assert not errors

    def test_human_node_with_optional_fields(self):
        """HUMAN节点支持可选字段"""
        node = NodeDefinition(
            node_type=NodeType.HUMAN,
            name="test_human_node",
            config={
                "prompt": "Please provide input",
                "expected_inputs": ["name", "age"],
                "timeout_seconds": 300,
            },
        )
        errors = node.validate()
        assert not errors


class TestExecutorTypeMapping:
    """测试EXECUTOR_TYPE_MAP映射"""

    def test_file_executor_mapping(self):
        """file executor类型映射到FILE节点"""
        assert NodeDefinition.EXECUTOR_TYPE_MAP.get("file") == NodeType.FILE

    def test_transform_executor_mapping(self):
        """transform executor类型映射到DATA_PROCESS节点"""
        assert NodeDefinition.EXECUTOR_TYPE_MAP.get("transform") == NodeType.DATA_PROCESS

    def test_data_process_executor_mapping(self):
        """data_process executor类型映射到DATA_PROCESS节点"""
        assert NodeDefinition.EXECUTOR_TYPE_MAP.get("data_process") == NodeType.DATA_PROCESS

    def test_human_executor_mapping(self):
        """human executor类型映射到HUMAN节点"""
        assert NodeDefinition.EXECUTOR_TYPE_MAP.get("human") == NodeType.HUMAN


class TestYamlSerialization:
    """测试YAML序列化支持"""

    def test_file_node_to_yaml(self):
        """FILE节点可以序列化为YAML"""
        node = NodeDefinition(
            node_type=NodeType.FILE,
            name="read_file",
            config={"operation": "read", "path": "/tmp/data.txt", "encoding": "utf-8"},
        )
        yaml_data = node.to_yaml_dict()
        assert yaml_data["type"] == "file"
        assert yaml_data["name"] == "read_file"
        assert yaml_data["config"]["operation"] == "read"

    def test_file_node_from_yaml(self):
        """FILE节点可以从YAML反序列化"""
        yaml_data = {
            "type": "file",
            "name": "write_log",
            "config": {"operation": "write", "path": "/var/log/app.log", "content": "Log entry"},
        }
        node = NodeDefinition.from_yaml(yaml_data)
        assert node.node_type == NodeType.FILE
        assert node.name == "write_log"
        assert node.config["operation"] == "write"

    def test_data_process_node_to_yaml(self):
        """DATA_PROCESS节点可以序列化为YAML"""
        node = NodeDefinition(
            node_type=NodeType.DATA_PROCESS,
            name="transform_data",
            config={"type": "field_mapping", "mapping": {"old_field": "new_field"}},
        )
        yaml_data = node.to_yaml_dict()
        assert yaml_data["type"] == "data_process"
        assert yaml_data["config"]["type"] == "field_mapping"

    def test_human_node_to_yaml(self):
        """HUMAN节点可以序列化为YAML"""
        node = NodeDefinition(
            node_type=NodeType.HUMAN,
            name="user_confirmation",
            config={"prompt": "Please confirm deletion", "timeout_seconds": 60},
        )
        yaml_data = node.to_yaml_dict()
        assert yaml_data["type"] == "human"
        assert yaml_data["config"]["prompt"] == "Please confirm deletion"

    def test_roundtrip_file_node(self):
        """FILE节点可以完成YAML往返序列化"""
        original = NodeDefinition(
            node_type=NodeType.FILE,
            name="test_roundtrip",
            config={"operation": "list", "path": "/tmp"},
        )
        yaml_data = original.to_yaml_dict()
        restored = NodeDefinition.from_yaml(yaml_data)
        assert restored.node_type == original.node_type
        assert restored.name == original.name
        # config会包含额外的默认值字段，但核心字段应保持一致
        assert restored.config["operation"] == original.config["operation"]
        assert restored.config["path"] == original.config["path"]

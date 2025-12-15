"""
Unit tests for NodeDefinition (P3-Task5)

Focus on:
- Node validation for all types
- Parent-child relationships and depth limits
- Strategy propagation
- Serialization (to_dict/from_dict)
- YAML operations
"""

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def node_definition_module():
    """Import node_definition module"""
    import importlib

    return importlib.import_module("src.domain.agents.node_definition")


# =============================================================================
# Class 1: TestNodeDefinitionCreation (4 tests)
# =============================================================================


class TestNodeDefinitionCreation:
    """Test node creation with required fields"""

    def test_create_python_node_with_required_fields(self, node_definition_module):
        """Test: PYTHON node created with code field"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="python_node",
            code="print('hello')",
        )

        assert node.node_type == NodeType.PYTHON
        assert node.name == "python_node"
        assert node.code == "print('hello')"
        assert node.id is not None  # Auto-generated UUID

    def test_create_llm_node_with_required_fields(self, node_definition_module):
        """Test: LLM node created with prompt field"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(
            node_type=NodeType.LLM,
            name="llm_node",
            prompt="What is AI?",
        )

        assert node.node_type == NodeType.LLM
        assert node.prompt == "What is AI?"

    def test_create_generic_node_minimal(self, node_definition_module):
        """Test: GENERIC node created with minimal fields"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="generic_node",
        )

        assert node.node_type == NodeType.GENERIC
        assert node.children == []
        assert node.collapsed is True  # Default for GENERIC

    def test_post_init_validates_condition_loop_nodes(self, node_definition_module):
        """Test: __post_init__ validates CONDITION/LOOP nodes on creation"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        # CONDITION node without expression should raise ValueError
        with pytest.raises(ValueError, match="节点定义验证失败|Condition 节点需要"):
            NodeDefinition(
                node_type=NodeType.CONDITION,
                name="condition_node",
            )


# =============================================================================
# Class 2: TestNodeValidation (8 tests)
# =============================================================================


class TestNodeValidation:
    """Test validate() method for all node types"""

    def test_validate_python_node_missing_code(self, node_definition_module):
        """Test: Python node validation fails without code"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(node_type=NodeType.PYTHON, name="python_node")
        errors = node.validate()

        assert len(errors) > 0
        assert any("code" in err.lower() for err in errors)

    def test_validate_llm_node_missing_prompt(self, node_definition_module):
        """Test: LLM node validation fails without prompt"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(node_type=NodeType.LLM, name="llm_node")
        errors = node.validate()

        assert len(errors) > 0
        assert any("prompt" in err.lower() for err in errors)

    def test_validate_http_node_missing_url(self, node_definition_module):
        """Test: HTTP node validation fails without url"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(node_type=NodeType.HTTP, name="http_node")
        errors = node.validate()

        assert len(errors) > 0
        assert any("url" in err.lower() for err in errors)

    def test_validate_database_node_missing_query(self, node_definition_module):
        """Test: DATABASE node validation fails without query"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(node_type=NodeType.DATABASE, name="db_node")
        errors = node.validate()

        assert len(errors) > 0
        assert any("query" in err.lower() for err in errors)

    def test_validate_condition_node_missing_expression(self, node_definition_module):
        """Test: CONDITION node validation fails without config.expression"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        # Create node bypassing __post_init__ by setting node_type after creation
        node = NodeDefinition.__new__(NodeDefinition)
        node.node_type = NodeType.CONDITION
        node.name = "condition_node"
        node.config = {}
        node.id = "test-id"
        node.description = ""
        node.code = None
        node.prompt = None
        node.url = None
        node.method = "GET"
        node.query = None
        node.input_schema = {}
        node.output_schema = {}
        node.parent_id = None
        node.children = []
        node.collapsed = True
        node.is_container = False
        node.container_config = {}
        node._depth = 0
        node.error_strategy = None
        node.resource_limits = {}
        node.inherited_strategy = False

        errors = node.validate()

        assert len(errors) > 0
        assert any("expression" in err.lower() for err in errors)

    def test_validate_loop_node_missing_collection(self, node_definition_module):
        """Test: LOOP node validation fails without collection_field/collection"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        # Create node bypassing __post_init__
        node = NodeDefinition.__new__(NodeDefinition)
        node.node_type = NodeType.LOOP
        node.name = "loop_node"
        node.config = {}
        node.id = "test-id"
        node.description = ""
        node.code = None
        node.prompt = None
        node.url = None
        node.method = "GET"
        node.query = None
        node.input_schema = {}
        node.output_schema = {}
        node.parent_id = None
        node.children = []
        node.collapsed = True
        node.is_container = False
        node.container_config = {}
        node._depth = 0
        node.error_strategy = None
        node.resource_limits = {}
        node.inherited_strategy = False

        errors = node.validate()

        assert len(errors) > 0
        assert any("collection" in err.lower() for err in errors)

    def test_validate_file_node_invalid_operation(self, node_definition_module):
        """Test: FILE node validation fails with invalid operation"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(
            node_type=NodeType.FILE,
            name="file_node",
            config={"operation": "invalid_op", "path": "/tmp/file.txt"},
        )
        errors = node.validate()

        assert len(errors) > 0
        assert any("operation" in err.lower() for err in errors)

    def test_validate_empty_name_fails(self, node_definition_module):
        """Test: Validation fails when name is empty or whitespace"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(node_type=NodeType.GENERIC, name="   ")
        errors = node.validate()

        assert len(errors) > 0
        assert any("name" in err.lower() for err in errors)


# =============================================================================
# Class 3: TestParentChildRelationships (4 tests)
# =============================================================================


class TestParentChildRelationships:
    """Test parent-child relationship management"""

    def test_add_child_updates_parent_id(self, node_definition_module):
        """Test: add_child sets child.parent_id to parent.id"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")
        child = NodeDefinition(node_type=NodeType.PYTHON, name="child", code="print('child')")

        parent.add_child(child)

        assert child.parent_id == parent.id
        assert child in parent.children

    def test_remove_child_clears_parent_id(self, node_definition_module):
        """Test: remove_child clears child.parent_id"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")
        child = NodeDefinition(node_type=NodeType.PYTHON, name="child", code="print('child')")
        parent.add_child(child)

        parent.remove_child(child.id)

        assert child.parent_id is None
        assert child not in parent.children

    def test_max_depth_limit_enforced(self, node_definition_module):
        """Test: Depth limit (MAX_NODE_DEFINITION_DEPTH = 5) enforced"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType
        MAX_NODE_DEFINITION_DEPTH = node_definition_module.MAX_NODE_DEFINITION_DEPTH

        # Create a chain of nodes at MAX_NODE_DEFINITION_DEPTH
        root = NodeDefinition(node_type=NodeType.GENERIC, name="root")
        current = root

        # Create MAX_NODE_DEFINITION_DEPTH children (root._depth=0, children go 1..5)
        for i in range(MAX_NODE_DEFINITION_DEPTH):
            child = NodeDefinition(node_type=NodeType.GENERIC, name=f"level_{i+1}")
            current.add_child(child)
            current = child

        # Now current._depth = 5 (MAX_NODE_DEFINITION_DEPTH)
        # Attempting to add one more level (depth 6) should raise ValueError
        too_deep_child = NodeDefinition(node_type=NodeType.GENERIC, name="too_deep")

        with pytest.raises(ValueError, match="超过最大深度|[Mm]ax depth|exceeded"):
            current.add_child(too_deep_child)

    def test_get_child_by_name_returns_correct_node(self, node_definition_module):
        """Test: get_child_by_name finds child by name"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")
        child1 = NodeDefinition(node_type=NodeType.PYTHON, name="child1", code="pass")
        child2 = NodeDefinition(node_type=NodeType.PYTHON, name="child2", code="pass")
        parent.add_child(child1)
        parent.add_child(child2)

        found = parent.get_child_by_name("child2")

        assert found is not None
        assert found.name == "child2"
        assert found.id == child2.id


# =============================================================================
# Class 4: TestStrategyPropagation (3 tests)
# =============================================================================


class TestStrategyPropagation:
    """Test strategy propagation to children"""

    def test_propagate_strategy_to_children_copies_error_strategy(self, node_definition_module):
        """Test: propagate_strategy_to_children copies error_strategy to children"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"type": "retry", "max_attempts": 3},
        )
        child = NodeDefinition(node_type=NodeType.PYTHON, name="child", code="pass")
        parent.add_child(child)

        parent.propagate_strategy_to_children()

        assert child.error_strategy == {"type": "retry", "max_attempts": 3}

    def test_propagate_strategy_to_children_copies_resource_limits(self, node_definition_module):
        """Test: propagate_strategy_to_children copies resource_limits to children"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            resource_limits={"timeout": 60},
        )
        child = NodeDefinition(node_type=NodeType.PYTHON, name="child", code="pass")
        parent.add_child(child)

        parent.propagate_strategy_to_children()

        assert child.resource_limits == {"timeout": 60}

    def test_apply_inherited_strategy_merges_strategies(self, node_definition_module):
        """Test: apply_inherited_strategy merges parent strategies into node"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(node_type=NodeType.PYTHON, name="node", code="pass")
        inherited_error_strategy = {"type": "abort"}
        inherited_resource_limits = {"memory": "512MB"}

        node.apply_inherited_strategy(inherited_error_strategy, inherited_resource_limits)

        # Verify strategies are merged (not flag setting)
        assert node.error_strategy == {"type": "abort"}
        assert node.resource_limits == {"memory": "512MB"}


# =============================================================================
# Class 5: TestSerialization (2 tests)
# =============================================================================


class TestSerialization:
    """Test to_dict/from_dict serialization"""

    def test_to_dict_from_dict_round_trip(self, node_definition_module):
        """Test: to_dict/from_dict preserves node data"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        original = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test_node",
            code="print('test')",
            description="Test description",
            config={"key": "value"},
        )

        # Round-trip: node -> dict -> node
        node_dict = original.to_dict()
        restored = NodeDefinition.from_dict(node_dict)

        assert restored.node_type == original.node_type
        assert restored.name == original.name
        assert restored.code == original.code
        assert restored.description == original.description
        assert restored.config == original.config

    def test_to_dict_includes_children(self, node_definition_module):
        """Test: to_dict includes children in output"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")
        child = NodeDefinition(node_type=NodeType.PYTHON, name="child", code="pass")
        parent.add_child(child)

        parent_dict = parent.to_dict()

        assert "children" in parent_dict
        assert len(parent_dict["children"]) == 1
        assert parent_dict["children"][0]["name"] == "child"


# =============================================================================
# Class 6: TestYAMLOperations (1 test)
# =============================================================================


class TestYAMLOperations:
    """Test YAML serialization"""

    def test_from_yaml_to_yaml_round_trip(self, node_definition_module):
        """Test: from_yaml/to_yaml preserves node data"""
        NodeDefinition = node_definition_module.NodeDefinition

        yaml_content = """
type: python
name: test_node
code: |
  print('hello')
description: Test YAML node
"""

        # Parse YAML -> node -> YAML
        node = NodeDefinition.from_yaml(yaml_content)
        yaml_output = node.to_yaml()

        # Verify key fields are preserved
        assert node.name == "test_node"
        assert "python" in yaml_output.lower()
        assert "test_node" in yaml_output

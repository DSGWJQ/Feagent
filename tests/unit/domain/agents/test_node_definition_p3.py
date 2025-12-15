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


# =============================================================================
# Class 7: TestFactoryScenarioTemplates (4 tests) - P0 Priority
# =============================================================================


class TestFactoryScenarioTemplates:
    """Test NodeDefinitionFactory scenario template methods"""

    def test_factory_create_data_collection_node_with_query(self, node_definition_module):
        """Test: create_data_collection_node with direct query"""
        NodeDefinitionFactory = node_definition_module.NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_collection_node(
            name="data_collector",
            query="SELECT * FROM users WHERE active = 1",
            database="prod",
        )

        assert node.node_type.value == "database"
        assert node.name == "data_collector"
        assert node.query == "SELECT * FROM users WHERE active = 1"
        assert node.config["database"] == "prod"

    def test_factory_create_data_collection_node_with_table_and_filters(
        self, node_definition_module
    ):
        """Test: create_data_collection_node with table + time_range + filters"""
        NodeDefinitionFactory = node_definition_module.NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_collection_node(
            name="sales_data",
            table="sales",
            time_range="last_month",
            filters={"region": "North", "amount": 1000},
            database="analytics",
        )

        assert node.node_type.value == "database"
        assert "FROM sales" in node.query
        assert "WHERE" in node.query
        # Verify filters are in query
        assert "region" in node.query or "amount" in node.query

    def test_factory_create_metric_calculation_node_with_group_by(self, node_definition_module):
        """Test: create_metric_calculation_node with metrics and group_by"""
        NodeDefinitionFactory = node_definition_module.NodeDefinitionFactory

        node = NodeDefinitionFactory.create_metric_calculation_node(
            name="revenue_metrics",
            metrics=["sum", "avg", "trend"],
            group_by="region",
        )

        assert node.node_type.value == "python"
        assert node.name == "revenue_metrics"
        # Verify pandas code includes groupby
        assert "groupby" in node.code or "group_by" in node.code
        assert node.config["metrics"] == ["sum", "avg", "trend"]

    @pytest.mark.parametrize(
        "chart_type,expected_code",
        [
            ("line", "plt.plot"),
            ("bar", "plt.bar"),
            ("pie", "plt.pie"),
        ],
    )
    def test_factory_create_chart_generation_node_variants(
        self, node_definition_module, chart_type, expected_code
    ):
        """Test: create_chart_generation_node for line/bar/pie charts"""
        NodeDefinitionFactory = node_definition_module.NodeDefinitionFactory

        node = NodeDefinitionFactory.create_chart_generation_node(
            name="chart",
            chart_type=chart_type,
            title="Test Chart",
            x_label="X",
            y_label="Y",
        )

        assert node.node_type.value == "python"
        assert expected_code in node.code
        assert node.config["chart_type"] == chart_type
        assert "plt." in node.code  # Verify matplotlib usage


# =============================================================================
# Class 8: TestYAMLFileDirectoryIO (3 tests) - P0 Priority
# =============================================================================


class TestYAMLFileDirectoryIO:
    """Test YAML file and directory I/O operations"""

    def test_from_yaml_file_success(self, node_definition_module, tmp_path):
        """Test: from_yaml_file reads and parses YAML file"""
        NodeDefinition = node_definition_module.NodeDefinition

        # Create temporary YAML file
        yaml_file = tmp_path / "test_node.yaml"
        yaml_file.write_text(
            """
type: python
name: test_file_node
code: print('from file')
description: Test node from file
"""
        )

        node = NodeDefinition.from_yaml_file(yaml_file)

        assert node.name == "test_file_node"
        assert node.code == "print('from file')"
        assert node.description == "Test node from file"

    def test_from_yaml_file_not_found_raises(self, node_definition_module):
        """Test: from_yaml_file raises ValueError for missing file"""
        NodeDefinition = node_definition_module.NodeDefinition

        # Implementation raises ValueError, not FileNotFoundError
        with pytest.raises(ValueError, match="文件不存在|not found|does not exist"):
            NodeDefinition.from_yaml_file("nonexistent_file.yaml")

    def test_from_yaml_directory_loads_multiple_files(self, node_definition_module, tmp_path):
        """Test: from_yaml_directory loads all .yaml/.yml files in directory"""
        NodeDefinition = node_definition_module.NodeDefinition

        # Create directory with multiple YAML files
        (tmp_path / "node1.yaml").write_text(
            """
type: python
name: node1
code: pass
"""
        )
        (tmp_path / "node2.yml").write_text(
            """
type: llm
name: node2
prompt: test prompt
"""
        )
        # Create a non-YAML file (should be skipped)
        (tmp_path / "readme.txt").write_text("This is not YAML")

        nodes = NodeDefinition.from_yaml_directory(tmp_path)

        assert len(nodes) == 2
        node_names = {n.name for n in nodes}
        assert "node1" in node_names
        assert "node2" in node_names


# =============================================================================
# Class 9: TestDAGAndIOValidation (3 tests) - P1 Priority
# =============================================================================


class TestDAGAndIOValidation:
    """Test DAG traversal and input/output validation"""

    def test_find_node_by_name_recursive(self, node_definition_module):
        """Test: find_node_by_name searches recursively in tree"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        # Build 3-level tree
        root = NodeDefinition(node_type=NodeType.GENERIC, name="root")
        child1 = NodeDefinition(node_type=NodeType.GENERIC, name="child1")
        grandchild = NodeDefinition(node_type=NodeType.PYTHON, name="grandchild", code="pass")
        root.add_child(child1)
        child1.add_child(grandchild)

        # Find at different levels
        found_child = root.find_node_by_name("child1")
        found_grandchild = root.find_node_by_name("grandchild")
        not_found = root.find_node_by_name("nonexistent")

        assert found_child is not None
        assert found_child.name == "child1"
        assert found_grandchild is not None
        assert found_grandchild.name == "grandchild"
        assert not_found is None

    def test_validate_input_checks_required_and_type(self, node_definition_module):
        """Test: validate_input checks required fields and types"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        # config.parameters expects LIST format (not dict)
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="validator",
            code="pass",
            config={
                "parameters": [
                    {"name": "x", "type": "integer", "required": True},
                    {"name": "y", "type": "string"},
                ]
            },
        )

        # Missing required field
        errors = node.validate_input({"y": "hello"})
        assert len(errors) > 0
        assert any("x" in err.lower() for err in errors)

        # Wrong type
        errors = node.validate_input({"x": "not_an_int", "y": "hello"})
        assert len(errors) > 0

        # Valid input
        errors = node.validate_input({"x": 42, "y": "hello"})
        assert len(errors) == 0

    def test_validate_output_checks_return_types(self, node_definition_module):
        """Test: validate_output checks return value types"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="validator",
            code="pass",
            config={"returns": {"properties": {"result": {"type": "integer"}}}},
        )

        # Wrong return type
        errors = node.validate_output({"result": "not_an_int"})
        assert len(errors) > 0

        # Valid return
        errors = node.validate_output({"result": 42})
        assert len(errors) == 0


# =============================================================================
# Class 10: TestAdditionalFactoryTemplates (1 test) - P0 Priority
# =============================================================================


class TestAdditionalFactoryTemplates:
    """Test additional Factory template methods"""

    @pytest.mark.parametrize(
        "analysis_type",
        ["summary", "insight", "recommendation", "unknown"],
    )
    def test_factory_create_data_analysis_node_variants(
        self, node_definition_module, analysis_type
    ):
        """Test: create_data_analysis_node for different analysis types"""
        NodeDefinitionFactory = node_definition_module.NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_analysis_node(
            name="analyzer",
            analysis_type=analysis_type,
            context="Sales data analysis",
        )

        assert node.node_type.value == "llm"
        assert node.name == "analyzer"
        assert node.prompt is not None
        assert len(node.prompt) > 0
        assert node.config["analysis_type"] == analysis_type


class TestGetExecutionOrder:
    """Test Class 11: get_execution_order (DAG topological sort)"""

    def test_no_children_returns_empty_list(self, node_definition_module):
        """Test: get_execution_order returns empty list when no children"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")
        assert parent.get_execution_order() == []

    def test_topological_order_respects_depends_on_not_input_order(self, node_definition_module):
        """Test: get_execution_order sorts by dependency graph, not add order"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")

        # Create nodes with dependency chain: A <- B <- C
        node_a = NodeDefinition(node_type=NodeType.PYTHON, name="A", code="print('A')")
        node_b = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="B",
            code="print('B')",
            config={"depends_on": ["A"]},
        )
        node_c = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="C",
            code="print('C')",
            config={"depends_on": ["B"]},
        )

        # Add in reverse order to verify algorithm sorts by depends_on
        parent.add_child(node_c)
        parent.add_child(node_b)
        parent.add_child(node_a)

        order = [n.name for n in parent.get_execution_order()]
        assert order == ["A", "B", "C"]

    def test_cycle_and_parent_dependency_includes_parent(self, node_definition_module):
        """Test: Circular dependency and parent reference doesn't crash"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="P")

        # Create cyclic dependency: X depends on Y, Y depends on X and P
        node_x = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="X",
            code="print('X')",
            config={"depends_on": ["Y"]},
        )
        node_y = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="Y",
            code="print('Y')",
            config={"depends_on": ["X", "P"]},
        )

        parent.add_child(node_x)
        parent.add_child(node_y)

        order = [n.name for n in parent.get_execution_order()]

        # Should not crash, and should include parent when depended upon
        assert "P" in order
        assert "X" in order
        assert "Y" in order
        # Parent should come before Y since Y depends on it
        assert order.index("P") < order.index("Y")


class TestExpandChildrenFromSchema:
    """Test Class 12: _expand_children_from_schema (child node expansion)"""

    def test_missing_ref_raises_value_error(self, node_definition_module):
        """Test: _expand_children_from_schema raises error when ref is missing"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")

        with pytest.raises(ValueError, match="must have 'ref'"):
            parent._expand_children_from_schema(
                [{"alias": "child_alias"}], registry={"dummy": parent}
            )

    def test_unknown_ref_raises_key_error(self, node_definition_module):
        """Test: _expand_children_from_schema raises error when ref not in registry"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")

        with pytest.raises(KeyError, match="not found in registry"):
            parent._expand_children_from_schema([{"ref": "missing"}], registry={})

    def test_depth_exceeded_raises_value_error(self, node_definition_module):
        """Test: _expand_children_from_schema enforces max depth limit"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType
        MAX_DEPTH = node_definition_module.MAX_NODE_DEFINITION_DEPTH

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")
        template = NodeDefinition(node_type=NodeType.PYTHON, name="child", code="print(1)")

        with pytest.raises(ValueError, match="[Mm]ax depth|[Dd]epth.*exceed"):
            parent._expand_children_from_schema(
                [{"ref": "child"}], registry={"child": template}, depth=MAX_DEPTH
            )

    def test_applies_override_resources_error_strategy_alias_and_sets_parent_depth(
        self, node_definition_module
    ):
        """Test: _expand_children_from_schema applies overrides and sets relationships"""
        NodeDefinition = node_definition_module.NodeDefinition
        NodeType = node_definition_module.NodeType

        parent = NodeDefinition(node_type=NodeType.GENERIC, name="parent")

        # Template with existing error_strategy
        template_with_strategy = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="task1",
            code="print(1)",
            error_strategy={"retry": {"max_attempts": 1}, "on_failure": "abort"},
        )

        # Template without error_strategy
        template_no_strategy = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="task2",
            code="print(2)",
        )

        parent._expand_children_from_schema(
            [
                {
                    "ref": "task1",
                    "alias": "alias1",
                    "override": {
                        "resources": {"cpu": "2"},
                        "error_strategy": {"on_failure": "retry"},
                    },
                },
                {
                    "ref": "task2",
                    "alias": "alias2",
                    "override": {"error_strategy": {"on_failure": "abort"}},
                },
            ],
            registry={"task1": template_with_strategy, "task2": template_no_strategy},
            depth=0,
        )

        child1, child2 = parent.children

        # Verify parent-child relationships
        assert child1.parent_id == parent.id
        assert child2.parent_id == parent.id

        # Verify depth is set
        assert child1._depth == 1
        assert child2._depth == 1

        # Verify aliases
        assert child1.config["alias"] == "alias1"
        assert child2.config["alias"] == "alias2"

        # Verify resource override
        assert child1.config["resources"]["cpu"] == "2"

        # Verify error_strategy merge for existing strategy
        assert child1.error_strategy["retry"]["max_attempts"] == 1
        assert child1.error_strategy["on_failure"] == "retry"  # Overridden

        # Verify error_strategy set for non-existing strategy
        assert child2.error_strategy == {"on_failure": "abort"}


class TestFromParentSchema:
    """Test Class 13: from_parent_schema (parent schema loading)"""

    def test_applies_inherit_block_and_builds_input_output_schema(self, node_definition_module):
        """Test: from_parent_schema processes inherit block and builds schemas"""
        NodeDefinition = node_definition_module.NodeDefinition

        schema = {
            "kind": "workflow",
            "name": "parent_workflow",
            "version": "1.0",
            "inherit": {
                "error_strategy": {"on_failure": "abort"},
                "resources": {"cpu": "1", "memory": "256m"},
                "parameters": {"x": {"type": "string"}},
                "returns": {"y": {"type": "number"}, "z": "string"},
                "tags": ["tag1", "tag2"],
            },
        }

        parent = NodeDefinition.from_parent_schema(schema)

        # Verify basic properties
        assert parent.node_type.value == "generic"
        assert parent.name == "parent_workflow"

        # Verify error_strategy inheritance
        assert parent.error_strategy == {"on_failure": "abort"}

        # Verify resource_limits inheritance
        assert parent.resource_limits == {"cpu": "1", "memory": "256m"}
        assert parent.config["resources"] == {"cpu": "1", "memory": "256m"}

        # Verify parameters and returns in config
        assert parent.config["parameters"] == {"x": {"type": "string"}}
        assert parent.config["returns"] == {
            "y": {"type": "number"},
            "z": "string",
        }

        # Verify tags
        assert parent.config["tags"] == ["tag1", "tag2"]

        # Verify input_schema and output_schema conversion
        assert parent.input_schema["x"] == "string"
        assert parent.output_schema["y"] == "number"
        assert parent.output_schema["z"] == "string"

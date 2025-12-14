"""
Unit tests for WorkflowDependencyGraph

Focus on logic branches not covered by integration tests:
- _aggregate_outputs strategies
- _build_node_inputs field extraction
- _emit_event callback handling
"""

import pytest

# =============================================================================
# _aggregate_outputs tests
# =============================================================================


class TestAggregateOutputs:
    """Test WorkflowDependencyExecutor._aggregate_outputs"""

    @pytest.fixture
    def executor(self):
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        return WorkflowDependencyExecutor(
            definitions_dir=".",
            scripts_dir=None,
        )

    def test_aggregate_outputs_merge_strategy_merges_dicts(self, executor):
        """Test: merge strategy merges dict outputs"""
        node_outputs = {
            "node_a": {"key1": "value1", "key2": "value2"},
            "node_b": {"key2": "overridden", "key3": "value3"},
            "node_c": {"key4": "value4"},
        }

        result = executor._aggregate_outputs(node_outputs, "merge")

        assert result["key1"] == "value1"
        assert result["key2"] == "overridden"  # Later keys override
        assert result["key3"] == "value3"
        assert result["key4"] == "value4"

    def test_aggregate_outputs_merge_strategy_skips_non_dicts(self, executor):
        """Test: merge strategy skips non-dict outputs"""
        node_outputs = {
            "node_a": {"key1": "value1"},
            "node_b": "not_a_dict",  # Should be skipped
            "node_c": {"key2": "value2"},
        }

        result = executor._aggregate_outputs(node_outputs, "merge")

        assert result["key1"] == "value1"
        assert result["key2"] == "value2"
        assert "not_a_dict" not in result

    def test_aggregate_outputs_list_strategy_preserves_order(self, executor):
        """Test: list strategy returns results in list"""
        node_outputs = {
            "node_a": {"value": 1},
            "node_b": {"value": 2},
            "node_c": {"value": 3},
        }

        result = executor._aggregate_outputs(node_outputs, "list")

        assert "results" in result
        assert isinstance(result["results"], list)
        assert len(result["results"]) == 3

    def test_aggregate_outputs_first_strategy_returns_first_node(self, executor):
        """Test: first strategy returns first node output"""
        node_outputs = {
            "node_a": {"first": True},
            "node_b": {"second": True},
            "node_c": {"third": True},
        }

        result = executor._aggregate_outputs(node_outputs, "first")

        # Should return first node's output
        assert "first" in result
        assert result["first"] is True

    def test_aggregate_outputs_last_strategy_returns_last_node(self, executor):
        """Test: last strategy returns last node output"""
        node_outputs = {
            "node_a": {"first": True},
            "node_b": {"second": True},
            "node_c": {"third": True},
        }

        result = executor._aggregate_outputs(node_outputs, "last")

        # Should return last node's output
        assert "third" in result
        assert result["third"] is True

    def test_aggregate_outputs_first_last_empty_dict_returns_empty(self, executor):
        """Test: first/last with empty dict returns empty dict"""
        result_first = executor._aggregate_outputs({}, "first")
        result_last = executor._aggregate_outputs({}, "last")

        assert result_first == {}
        assert result_last == {}

    def test_aggregate_outputs_unknown_strategy_returns_all(self, executor):
        """Test: unknown strategy returns all node outputs"""
        node_outputs = {
            "node_a": {"a": 1},
            "node_b": {"b": 2},
        }

        result = executor._aggregate_outputs(node_outputs, "unknown_strategy")

        # Should return all node outputs as-is
        assert result == node_outputs


# =============================================================================
# _build_node_inputs tests
# =============================================================================


class TestBuildNodeInputs:
    """Test WorkflowDependencyExecutor._build_node_inputs"""

    @pytest.fixture
    def executor(self):
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        return WorkflowDependencyExecutor(
            definitions_dir=".",
            scripts_dir=None,
        )

    def test_build_node_inputs_extracts_from_dependency_output(self, executor):
        """Test: extract input from dependency node output"""
        node_def = {
            "name": "target_node",
            "inputs": {
                "input_field": {"from": "source_node.output.data"},
            },
        }

        node_outputs = {
            "source_node": {"data": {"value": 42}},
        }

        result = executor._build_node_inputs(node_def, node_outputs, {})

        assert "input_field" in result
        assert result["input_field"] == {"value": 42}

    def test_build_node_inputs_field_path_extraction(self, executor):
        """Test: extract specific field from dependency output"""
        node_def = {
            "name": "target_node",
            "inputs": {
                "specific_field": {"from": "source_node.output.data"},
            },
        }

        node_outputs = {
            "source_node": {
                "data": {"value": 100, "nested": {"deep": 200}},
                "metadata": {"info": "ignore"},
            },
        }

        result = executor._build_node_inputs(node_def, node_outputs, {})

        # Should extract just the 'data' field
        assert "specific_field" in result
        assert result["specific_field"]["value"] == 100
        assert result["specific_field"]["nested"]["deep"] == 200
        # metadata should not be included
        assert "metadata" not in result

    def test_build_node_inputs_multiple_inputs_from_different_nodes(self, executor):
        """Test: build inputs from multiple dependency nodes"""
        node_def = {
            "name": "merger",
            "inputs": {
                "from_a": {"from": "node_a.output.result_a"},
                "from_b": {"from": "node_b.output.result_b"},
                "from_c": {"from": "node_c.output"},
            },
        }

        node_outputs = {
            "node_a": {"result_a": 10},
            "node_b": {"result_b": 20},
            "node_c": {"result_c": 30},
        }

        result = executor._build_node_inputs(node_def, node_outputs, {})

        assert result["from_a"] == 10
        assert result["from_b"] == 20
        assert result["from_c"] == {"result_c": 30}

    def test_build_node_inputs_parent_reference_uses_global_inputs(self, executor):
        """Test: 'parent' reference extracts from global inputs"""
        node_def = {
            "name": "child_node",
            "inputs": {
                "global_param": {"from": "parent.output"},
            },
        }

        global_inputs = {"date_range": "2024-01-01", "region": "US"}

        result = executor._build_node_inputs(node_def, {}, global_inputs)

        # 'parent' should return entire global_inputs
        assert result["global_param"] == global_inputs

    def test_build_node_inputs_missing_dependency_node_skips_input(self, executor):
        """Test: missing dependency node results in skipped input"""
        node_def = {
            "name": "orphan",
            "inputs": {
                "missing_input": {"from": "nonexistent_node.output.value"},
            },
        }

        result = executor._build_node_inputs(node_def, {}, {})

        # Missing dependency should not appear in result
        assert "missing_input" not in result


# =============================================================================
# _emit_event tests
# =============================================================================


class TestEmitEvent:
    """Test WorkflowDependencyExecutor._emit_event"""

    def test_emit_event_calls_callback_when_provided(self):
        """Test: event callback is invoked when provided"""
        from src.domain.services.workflow_dependency_graph import (
            DependencyExecutionEvent,
            WorkflowDependencyExecutor,
        )

        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        executor = WorkflowDependencyExecutor(
            definitions_dir=".",
            scripts_dir=None,
            event_callback=capture_event,
        )

        event = DependencyExecutionEvent(
            node_name="test_node",
            status="started",
            dependencies=["dep1", "dep2"],
            execution_order=0,
        )

        executor._emit_event(event)

        assert len(events_captured) == 1
        assert events_captured[0].node_name == "test_node"
        assert events_captured[0].status == "started"
        assert events_captured[0].dependencies == ["dep1", "dep2"]

    def test_emit_event_no_op_when_callback_not_provided(self):
        """Test: no error when callback not provided"""
        from src.domain.services.workflow_dependency_graph import (
            DependencyExecutionEvent,
            WorkflowDependencyExecutor,
        )

        executor = WorkflowDependencyExecutor(
            definitions_dir=".",
            scripts_dir=None,
            event_callback=None,
        )

        event = DependencyExecutionEvent(
            node_name="test_node",
            status="completed",
        )

        # Should not raise exception
        executor._emit_event(event)

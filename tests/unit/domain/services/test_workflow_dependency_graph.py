"""
Unit tests for WorkflowDependencyGraph

Focus on logic branches not covered by integration tests:
- _aggregate_outputs strategies
- _build_node_inputs field extraction
- _emit_event callback handling

Extended coverage (Modules 1-5):
- Module 1: Data classes (DependencyExecutionEvent, WorkflowExecutionResult)
- Module 2: DependencyGraphBuilder (edge cases, invalid inputs, logging)
- Module 3: TopologicalExecutor (empty graphs, cycles, unknown nodes)
- Module 4: WorkflowDependencyExecutor.execute_workflow (file errors, execution flows)
- Module 5: Script execution (_execute_node, _execute_script)
"""

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

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


# =============================================================================
# Module 1: Data classes tests
# =============================================================================


class TestDependencyExecutionEventToDict:
    """Test DependencyExecutionEvent.to_dict()"""

    def test_to_dict_all_fields_present_and_correct(self):
        """Test: to_dict() returns all fields with correct values"""
        from src.domain.services.workflow_dependency_graph import DependencyExecutionEvent

        event = DependencyExecutionEvent(
            node_name="node_1",
            status="completed",
            dependencies=["dep_a", "dep_b"],
            execution_order=3,
            execution_time_ms=12.34,
            output_keys=["x", "y"],
        )

        data = event.to_dict()

        assert data == {
            "node_name": "node_1",
            "status": "completed",
            "dependencies": ["dep_a", "dep_b"],
            "execution_order": 3,
            "execution_time_ms": 12.34,
            "output_keys": ["x", "y"],
        }


class TestWorkflowExecutionResultConstruction:
    """Test WorkflowExecutionResult dataclass construction patterns"""

    def test_construction_defaults_expected(self):
        """Test: default values match specification"""
        from src.domain.services.workflow_dependency_graph import WorkflowExecutionResult

        result = WorkflowExecutionResult()

        assert result.success is False
        assert result.output == {}
        assert result.error is None
        assert result.children_results == {}
        assert result.aggregated_output is None
        assert result.execution_order == []
        assert result.execution_time_ms == 0.0

    def test_construction_custom_values_preserved(self):
        """Test: custom values are correctly preserved"""
        from src.domain.services.workflow_dependency_graph import WorkflowExecutionResult

        result = WorkflowExecutionResult(
            success=True,
            output={"final": 1},
            error=None,
            children_results={"a": {"success": True, "output": {"x": 1}}},
            aggregated_output={"a": {"x": 1}},
            execution_order=["a"],
            execution_time_ms=1.23,
        )

        assert result.success is True
        assert result.output == {"final": 1}
        assert result.children_results["a"]["success"] is True
        assert result.aggregated_output == {"a": {"x": 1}}
        assert result.execution_order == ["a"]
        assert result.execution_time_ms == 1.23


# =============================================================================
# Module 2: DependencyGraphBuilder edge cases and validation
# =============================================================================


class TestDependencyGraphBuilderEdgeCases:
    """Test DependencyGraphBuilder methods with edge cases and invalid inputs"""

    @pytest.fixture
    def builder(self):
        from src.domain.services.workflow_dependency_graph import DependencyGraphBuilder

        return DependencyGraphBuilder()

    def test_parse_input_references_inputs_not_dict_returns_empty(self, builder):
        """Test: inputs field not being dict returns empty references"""
        node_def = {"name": "node1", "inputs": ["not", "a", "dict"]}
        assert builder.parse_input_references(node_def) == {}

    def test_parse_input_references_input_spec_not_dict_skips(self, builder):
        """Test: input spec not being dict is skipped"""
        node_def = {"name": "node1", "inputs": {"field_a": "not-a-dict"}}
        assert builder.parse_input_references(node_def) == {}

    def test_parse_input_references_missing_from_skips(self, builder):
        """Test: input spec without 'from' field is skipped"""
        node_def = {"name": "node1", "inputs": {"field_a": {"type": "object"}}}
        assert builder.parse_input_references(node_def) == {}

    def test_parse_input_references_node_output_no_field_sets_output_path(self, builder):
        """Test: reference to node.output (no field) sets path to 'output'"""
        node_def = {"name": "node1", "inputs": {"field_a": {"from": "source.output"}}}
        refs = builder.parse_input_references(node_def)
        assert refs["field_a"] == {"node": "source", "path": "output"}

    def test_parse_input_references_invalid_format_logs_warning_and_skips(self, builder, caplog):
        """Test: invalid reference format logs warning and skips entry"""
        node_def = {"name": "node1", "inputs": {"field_a": {"from": "source.badformat"}}}

        with caplog.at_level(logging.WARNING):
            refs = builder.parse_input_references(node_def)

        assert "field_a" not in refs
        assert any("无效的输入引用格式" in record.message for record in caplog.records)

    def test_parse_output_schema_outputs_not_dict_returns_empty(self, builder):
        """Test: outputs field not being dict returns empty schema"""
        node_def = {"name": "node1", "outputs": ["not", "a", "dict"]}
        assert builder.parse_output_schema(node_def) == {}

    def test_resolve_dependencies_skips_nodes_without_name(self, builder):
        """Test: nodes without 'name' field are skipped in dependency resolution"""
        nodes = [{"executor_type": "code"}, {"name": "valid_node", "inputs": {}}]
        deps = builder.resolve_dependencies(nodes)
        assert "valid_node" in deps
        assert "" not in deps

    def test_resolve_dependencies_ignores_unknown_source_nodes(self, builder):
        """Test: references to non-existent nodes are ignored"""
        nodes = [{"name": "consumer", "inputs": {"x": {"from": "unknown.output.value"}}}]
        deps = builder.resolve_dependencies(nodes)
        assert deps["consumer"] == []

    def test_resolve_dependencies_excludes_self_reference(self, builder):
        """Test: self-references are excluded from dependencies"""
        nodes = [{"name": "self_ref", "inputs": {"x": {"from": "self_ref.output.value"}}}]
        deps = builder.resolve_dependencies(nodes)
        assert deps["self_ref"] == []

    def test_resolve_dependencies_dedupes_duplicate_references(self, builder):
        """Test: duplicate references to same node are de-duplicated"""
        nodes = [
            {"name": "source"},
            {
                "name": "consumer",
                "inputs": {
                    "x": {"from": "source.output.v1"},
                    "y": {"from": "source.output.v2"},
                },
            },
        ]
        deps = builder.resolve_dependencies(nodes)
        assert deps["consumer"] == ["source"]

    def test_create_edges_empty_nodes_returns_empty(self, builder):
        """Test: empty nodes list returns empty edges"""
        assert builder.create_edges([]) == []

    def test_wire_children_no_children_returns_empty(self, builder):
        """Test: parent node with no children returns empty edges"""
        parent_node = {"name": "parent", "nested": {"children": []}}
        assert builder.wire_children(parent_node) == []

    def test_wire_children_nested_not_dict_raises_attribute_error(self, builder):
        """Test: nested field not being dict causes AttributeError"""
        parent_node = {"name": "parent", "nested": "not-a-dict"}
        with pytest.raises(AttributeError):
            builder.wire_children(parent_node)


# =============================================================================
# Module 3: TopologicalExecutor edge cases and boundary conditions
# =============================================================================


class TestTopologicalExecutorEdgeCases:
    """Test TopologicalExecutor.topological_sort with edge cases"""

    @pytest.fixture
    def executor(self):
        from src.domain.services.workflow_dependency_graph import TopologicalExecutor

        return TopologicalExecutor()

    def test_topological_sort_empty_graph_returns_empty(self, executor):
        """Test: empty nodes and edges returns empty list"""
        assert executor.topological_sort([], []) == []

    def test_topological_sort_no_edges_preserves_input_order(self, executor):
        """Test: nodes with no edges maintains input order"""
        nodes = ["A", "B", "C"]
        assert executor.topological_sort(nodes, []) == ["A", "B", "C"]

    def test_topological_sort_unknown_edge_endpoints_ignored(self, executor):
        """Test: edges referencing unknown nodes are ignored"""
        nodes = ["A", "B"]
        edges = [("A", "B"), ("A", "UNKNOWN"), ("UNKNOWN", "B")]
        assert executor.topological_sort(nodes, edges) == ["A", "B"]

    def test_topological_sort_cycle_raises_value_error_includes_remaining(self, executor):
        """Test: circular dependencies raise ValueError with cycle info"""
        nodes = ["A", "B"]
        edges = [("A", "B"), ("B", "A")]
        with pytest.raises(ValueError) as excinfo:
            executor.topological_sort(nodes, edges)
        error_msg = str(excinfo.value)
        assert "cycle" in error_msg or "循环" in error_msg


# =============================================================================
# Module 4: WorkflowDependencyExecutor.execute_workflow core flows
# =============================================================================


class TestExecuteWorkflow:
    """Test WorkflowDependencyExecutor.execute_workflow with controlled node execution"""

    @pytest.fixture
    def make_executor(self):
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        def _make(definitions_dir: str, scripts_dir: str | None = None, event_callback=None):
            return WorkflowDependencyExecutor(
                definitions_dir=definitions_dir,
                scripts_dir=scripts_dir,
                event_callback=event_callback,
            )

        return _make

    @pytest.mark.asyncio
    async def test_execute_workflow_missing_yaml_returns_error(self, tmp_path, make_executor):
        """Test: missing workflow definition returns error result"""
        executor = make_executor(str(tmp_path))
        result = await executor.execute_workflow("does_not_exist", inputs={})
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_execute_workflow_invalid_yaml_type_returns_error_result(
        self, tmp_path, make_executor
    ):
        """Test: YAML containing non-dict returns error"""
        (tmp_path / "bad.yaml").write_text("- not-a-dict\n- still-not-a-dict\n", encoding="utf-8")
        executor = make_executor(str(tmp_path))

        result = await executor.execute_workflow("bad", inputs={})

        assert result.success is False
        assert result.error
        assert "Invalid workflow definition format" in result.error

    @pytest.mark.asyncio
    async def test_execute_workflow_yaml_parse_error_propagates(self, tmp_path, make_executor):
        """Test: malformed YAML raises YAMLError"""
        (tmp_path / "broken.yaml").write_text(":\n  [\n", encoding="utf-8")
        executor = make_executor(str(tmp_path))
        with pytest.raises(yaml.YAMLError):
            await executor.execute_workflow("broken", inputs={})

    @pytest.mark.asyncio
    async def test_execute_workflow_no_children_returns_inputs(self, tmp_path, make_executor):
        """Test: workflow with no children returns inputs as output"""
        (tmp_path / "empty_children.yaml").write_text(
            "name: empty_children\nnested:\n  children: []\n",
            encoding="utf-8",
        )
        executor = make_executor(str(tmp_path))

        result = await executor.execute_workflow("empty_children", inputs={"x": 1})

        assert result.success is True
        assert result.output == {"x": 1}

    @pytest.mark.asyncio
    async def test_execute_workflow_cycle_returns_error_result(self, tmp_path, make_executor):
        """Test: circular dependencies in children return error"""
        (tmp_path / "cycle.yaml").write_text(
            """\
name: cycle
nested:
  children:
    - name: A
      inputs:
        x:
          from: "B.output"
    - name: B
      inputs:
        y:
          from: "A.output"
""",
            encoding="utf-8",
        )
        executor = make_executor(str(tmp_path))

        result = await executor.execute_workflow("cycle", inputs={})

        assert result.success is False
        assert result.error and ("cycle" in result.error or "循环" in result.error)

    @pytest.mark.asyncio
    async def test_execute_workflow_normal_flow_emits_events_and_aggregates(
        self, tmp_path, make_executor, monkeypatch
    ):
        """Test: normal execution flow emits correct events and aggregates outputs"""
        (tmp_path / "ok.yaml").write_text(
            """\
name: ok
nested:
  children:
    - name: A
      executor_type: code
    - name: B
      executor_type: code
      inputs:
        data:
          from: "A.output"
output_aggregation: merge
""",
            encoding="utf-8",
        )

        events: list = []
        executor = make_executor(str(tmp_path), event_callback=events.append)

        async def fake_execute_node(node_name: str, inputs: dict):
            if node_name == "A":
                return {"a": 1}
            if node_name == "B":
                assert inputs["data"] == {"a": 1}
                return {"b": inputs["data"]["a"] + 1}
            raise AssertionError(f"Unexpected node: {node_name}")

        monkeypatch.setattr(executor, "_execute_node", fake_execute_node)

        result = await executor.execute_workflow("ok", inputs={"ignored": True})

        assert result.success is True
        assert result.output == {"a": 1, "b": 2}
        assert result.execution_order == ["A", "B"]
        assert result.children_results["A"]["success"] is True
        assert result.children_results["B"]["success"] is True
        assert [e.status for e in events] == ["started", "completed", "started", "completed"]
        assert [e.node_name for e in events] == ["A", "A", "B", "B"]

    @pytest.mark.asyncio
    async def test_execute_workflow_node_failure_abort_returns_partial_results(
        self, tmp_path, make_executor, monkeypatch
    ):
        """Test: node failure with abort strategy returns partial results"""
        (tmp_path / "abort.yaml").write_text(
            """\
name: abort
nested:
  children:
    - name: A
      executor_type: code
    - name: B
      executor_type: code
      inputs:
        data:
          from: "A.output"
error_strategy:
  on_failure: abort
""",
            encoding="utf-8",
        )

        events: list = []
        executor = make_executor(str(tmp_path), event_callback=events.append)

        async def fake_execute_node(node_name: str, inputs: dict):
            if node_name == "A":
                return {"a": 1}
            if node_name == "B":
                raise RuntimeError("boom")
            raise AssertionError(f"Unexpected node: {node_name}")

        monkeypatch.setattr(executor, "_execute_node", fake_execute_node)

        result = await executor.execute_workflow("abort", inputs={})

        assert result.success is False
        assert result.error and "boom" in result.error
        assert result.children_results["A"]["success"] is True
        assert result.children_results["B"]["success"] is False
        assert result.execution_order == ["A", "B"]
        assert [e.status for e in events if e.node_name == "B"] == ["started", "failed"]

    @pytest.mark.asyncio
    async def test_execute_workflow_node_failure_continue_still_runs_subsequent_nodes(
        self, tmp_path, make_executor, monkeypatch
    ):
        """Test: node failure with continue strategy allows workflow to continue"""
        (tmp_path / "continue.yaml").write_text(
            """\
name: cont
nested:
  children:
    - name: A
      executor_type: code
    - name: B
      executor_type: code
      inputs:
        data:
          from: "A.output"
    - name: C
      executor_type: code
      inputs:
        data:
          from: "A.output"
error_strategy:
  on_failure: continue
output_aggregation: merge
""",
            encoding="utf-8",
        )

        ran: list[str] = []
        executor = make_executor(str(tmp_path))

        async def fake_execute_node(node_name: str, inputs: dict):
            ran.append(node_name)
            if node_name == "A":
                return {"a": 1}
            if node_name == "B":
                raise RuntimeError("boom")
            if node_name == "C":
                return {"c": 3}
            raise AssertionError(f"Unexpected node: {node_name}")

        monkeypatch.setattr(executor, "_execute_node", fake_execute_node)

        result = await executor.execute_workflow("continue", inputs={})

        assert ran == ["A", "B", "C"]
        assert result.success is True
        assert result.children_results["B"]["success"] is False
        assert result.output.get("a") == 1
        assert result.output.get("c") == 3


# =============================================================================
# Module 5: Script execution tests (_execute_node / _execute_script)
# =============================================================================


class TestScriptExecution:
    """Test WorkflowDependencyExecutor script resolution and sandbox execution"""

    @pytest.mark.asyncio
    async def test_execute_node_no_scripts_dir_returns_inputs(self, tmp_path):
        """Test: when scripts_dir is None, node execution returns inputs unchanged"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        executor = WorkflowDependencyExecutor(definitions_dir=str(tmp_path), scripts_dir=None)
        inputs = {"k": 1}

        out = await executor._execute_node("any_node", inputs)

        assert out == inputs

    @pytest.mark.asyncio
    async def test_execute_node_script_exists_delegates_to_execute_script(
        self, tmp_path, monkeypatch
    ):
        """Test: when script exists, delegates to _execute_script"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "node_x.py").write_text("output = {'ok': True}\n", encoding="utf-8")

        executor = WorkflowDependencyExecutor(
            definitions_dir=str(tmp_path), scripts_dir=str(scripts_dir)
        )

        called = {}

        async def fake_execute_script(script_path: Path, inputs: dict):
            called["path"] = script_path
            called["inputs"] = inputs
            return {"from_script": True}

        monkeypatch.setattr(executor, "_execute_script", fake_execute_script)

        out = await executor._execute_node("node_x", {"a": 1})

        assert out == {"from_script": True}
        assert called["path"].name == "node_x.py"
        assert called["inputs"] == {"a": 1}

    @pytest.mark.asyncio
    async def test_execute_script_injected_sandbox_executor_returns_output_data(self, tmp_path):
        """Test: injected sandbox executor returns output_data correctly"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        script_path = tmp_path / "script.py"
        script_path.write_text("output = {'x': 1}\n", encoding="utf-8")

        calls = {}

        class FakeSandboxExecutor:
            def execute(self, code, config, input_data):
                calls["code"] = code
                calls["config"] = config
                calls["input_data"] = input_data
                return SimpleNamespace(output_data={"x": 1})

        executor = WorkflowDependencyExecutor(
            definitions_dir=str(tmp_path),
            scripts_dir=None,
            sandbox_executor=FakeSandboxExecutor(),
        )

        out = await executor._execute_script(script_path, {"in": 1})

        assert out == {"x": 1}
        assert "output" in calls["code"]
        assert calls["input_data"] == {"in": 1}
        assert hasattr(calls["config"], "timeout_seconds")

    @pytest.mark.asyncio
    async def test_execute_script_injected_sandbox_executor_missing_output_data_returns_empty(
        self, tmp_path
    ):
        """Test: when sandbox result lacks output_data, returns empty dict"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        script_path = tmp_path / "script.py"
        script_path.write_text("output = {'x': 1}\n", encoding="utf-8")

        class FakeSandboxExecutor:
            def execute(self, code, config, input_data):
                return SimpleNamespace()  # no output_data attribute

        executor = WorkflowDependencyExecutor(
            definitions_dir=str(tmp_path),
            scripts_dir=None,
            sandbox_executor=FakeSandboxExecutor(),
        )

        out = await executor._execute_script(script_path, {"in": 1})

        assert out == {}

    @pytest.mark.asyncio
    async def test_execute_script_fallback_internal_sandbox_executor_returns_output_data(
        self, tmp_path, monkeypatch
    ):
        """Test: fallback to internal SandboxExecutor works correctly"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor
        import src.domain.services.sandbox_executor as sandbox_mod

        script_path = tmp_path / "script.py"
        script_path.write_text("output = {'z': 3}\n", encoding="utf-8")

        calls = {}

        class FakeSandboxExecutor:
            def execute(self, code, input_data):
                calls["code"] = code
                calls["input_data"] = input_data
                return SimpleNamespace(output_data={"z": 3})

        monkeypatch.setattr(sandbox_mod, "SandboxExecutor", FakeSandboxExecutor)

        executor = WorkflowDependencyExecutor(
            definitions_dir=str(tmp_path), scripts_dir=None, sandbox_executor=None
        )

        out = await executor._execute_script(script_path, {"in": 2})

        assert out == {"z": 3}
        assert calls["input_data"] == {"in": 2}

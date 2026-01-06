"""PRD-060: Offline-first scenario baseline (6/10) testization.

Goal:
- Define 10 deterministic scenarios (data-cleaning focused).
- Run them offline with mocked LLM + deterministic tools.
- Assert auto-judged success >= 6/10 (non-CI-gate metric encoded as a unit test).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.application.use_cases.execute_workflow import ExecuteWorkflowInput, ExecuteWorkflowUseCase
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors.transform_executor import TransformExecutor


class _InMemoryWorkflowRepository:
    def __init__(self) -> None:
        self._store: dict[str, Workflow] = {}

    def save(self, workflow: Workflow) -> None:
        self._store[workflow.id] = workflow

    def get_by_id(self, workflow_id: str) -> Workflow:
        return self._store[workflow_id]


class _DeterministicToolExecutor:
    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        payload = next(iter(inputs.values())) if inputs else None
        op = (node.config or {}).get("op")
        if op == "trim_lower":
            if not isinstance(payload, dict):
                return payload
            out: dict[str, Any] = {}
            for k, v in payload.items():
                key = str(k).strip().lower()
                if isinstance(v, str):
                    out[key] = v.strip().lower()
                else:
                    out[key] = v
            return out
        if op == "echo":
            return payload
        raise RuntimeError(f"unsupported tool op: {op!r}")


class _MockLlmExecutor:
    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        return (node.config or {}).get("mock_response", {"ok": True})


@dataclass(frozen=True)
class _Scenario:
    scenario_id: str
    workflow: Workflow
    initial_input: Any
    expect_complete: bool
    expected_result: Any | None = None


async def _run_use_case_stream(
    use_case: ExecuteWorkflowUseCase, scenario: _Scenario
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    last: dict[str, Any] | None = None
    async for event in use_case.execute_streaming(
        ExecuteWorkflowInput(workflow_id=scenario.workflow.id, initial_input=scenario.initial_input)
    ):
        events.append(event)
        last = event
    assert last is not None
    return events, last


@pytest.mark.asyncio
async def test_prd060_offline_scenarios_baseline() -> None:
    repo = _InMemoryWorkflowRepository()
    registry = NodeExecutorRegistry()
    registry.register(NodeType.TRANSFORM.value, TransformExecutor())
    registry.register(NodeType.TOOL.value, _DeterministicToolExecutor())
    registry.register(NodeType.LLM.value, _MockLlmExecutor())

    def wf(nodes: list[Node], edges: list[Edge]) -> Workflow:
        workflow = Workflow.create(name="scenario", description="", nodes=nodes, edges=edges)
        repo.save(workflow)
        return workflow

    def start_node() -> Node:
        return Node.create(
            type=NodeType.START, name="start", config={}, position=Position(x=0, y=0)
        )

    def end_node(x: int = 2) -> Node:
        return Node.create(type=NodeType.END, name="end", config={}, position=Position(x=x, y=0))

    scenarios: list[_Scenario] = []

    # clean-01-field_mapping
    s = start_node()
    t = Node.create(
        type=NodeType.TRANSFORM,
        name="map",
        config={"type": "field_mapping", "mapping": {"name": "input.Name", "age": "input.Age"}},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-01-field_mapping",
            workflow=wf(
                [s, t, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=t.id),
                    Edge.create(source_node_id=t.id, target_node_id=e.id),
                ],
            ),
            initial_input={"Name": " Alice ", "Age": "30"},
            expect_complete=True,
            expected_result={"name": " Alice ", "age": "30"},
        )
    )

    # clean-02-type_conversion
    s = start_node()
    t = Node.create(
        type=NodeType.TRANSFORM,
        name="convert",
        config={"type": "type_conversion", "conversions": {"age": "int", "price": "float"}},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-02-type_conversion",
            workflow=wf(
                [s, t, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=t.id),
                    Edge.create(source_node_id=t.id, target_node_id=e.id),
                ],
            ),
            initial_input={"age": "30", "price": "12.5"},
            expect_complete=True,
            expected_result={"age": 30, "price": 12.5},
        )
    )

    # clean-03-field_extraction
    s = start_node()
    t = Node.create(
        type=NodeType.TRANSFORM,
        name="extract",
        config={"type": "field_extraction", "path": "user.profile.address.city"},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-03-field_extraction",
            workflow=wf(
                [s, t, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=t.id),
                    Edge.create(source_node_id=t.id, target_node_id=e.id),
                ],
            ),
            initial_input={"user": {"profile": {"address": {"city": "Shanghai"}}}},
            expect_complete=True,
            expected_result="Shanghai",
        )
    )

    # clean-04-array_mapping
    s = start_node()
    t = Node.create(
        type=NodeType.TRANSFORM,
        name="array_map",
        config={
            "type": "array_mapping",
            "field": "rows",
            "mapping": {"full_name": "name", "age": "age"},
        },
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-04-array_mapping",
            workflow=wf(
                [s, t, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=t.id),
                    Edge.create(source_node_id=t.id, target_node_id=e.id),
                ],
            ),
            initial_input={"rows": [{"name": "a", "age": 1}, {"name": "b", "age": 2}]},
            expect_complete=True,
            expected_result=[{"full_name": "a", "age": 1}, {"full_name": "b", "age": 2}],
        )
    )

    # clean-05-filter_invalid_rows
    s = start_node()
    t = Node.create(
        type=NodeType.TRANSFORM,
        name="filter",
        config={"type": "filtering", "field": "rows", "condition": "age >= 18"},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-05-filter_invalid_rows",
            workflow=wf(
                [s, t, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=t.id),
                    Edge.create(source_node_id=t.id, target_node_id=e.id),
                ],
            ),
            initial_input={"rows": [{"age": 10}, {"age": 20}]},
            expect_complete=True,
            expected_result=[{"age": 20}],
        )
    )

    # clean-06-aggregation_stats
    s = start_node()
    t = Node.create(
        type=NodeType.TRANSFORM,
        name="agg",
        config={"type": "aggregation", "field": "rows", "operations": ["count", "sum:amount"]},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-06-aggregation_stats",
            workflow=wf(
                [s, t, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=t.id),
                    Edge.create(source_node_id=t.id, target_node_id=e.id),
                ],
            ),
            initial_input={"rows": [{"amount": 10}, {"amount": 15}]},
            expect_complete=True,
            expected_result={"count": 2, "sum_amount": 25},
        )
    )

    # clean-07-trim_normalize_tool
    s = start_node()
    tool = Node.create(
        type=NodeType.TOOL,
        name="trim_lower",
        config={"op": "trim_lower"},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-07-trim_normalize_tool",
            workflow=wf(
                [s, tool, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=tool.id),
                    Edge.create(source_node_id=tool.id, target_node_id=e.id),
                ],
            ),
            initial_input={"Name": " Alice ", "Email": "ALICE@EXAMPLE.COM"},
            expect_complete=True,
            expected_result={"name": "alice", "email": "alice@example.com"},
        )
    )

    # clean-08-llm_rules_mocked
    s = start_node()
    llm = Node.create(
        type=NodeType.LLM,
        name="llm_rules",
        config={"mock_response": {"rules": ["trim", "lowercase"]}},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-08-llm_rules_mocked",
            workflow=wf(
                [s, llm, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=llm.id),
                    Edge.create(source_node_id=llm.id, target_node_id=e.id),
                ],
            ),
            initial_input={"raw": "ignored"},
            expect_complete=True,
            expected_result={"rules": ["trim", "lowercase"]},
        )
    )

    # clean-09-tool_echo
    s = start_node()
    tool = Node.create(
        type=NodeType.TOOL,
        name="echo",
        config={"op": "echo"},
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-09-tool_echo",
            workflow=wf(
                [s, tool, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=tool.id),
                    Edge.create(source_node_id=tool.id, target_node_id=e.id),
                ],
            ),
            initial_input={"rows": [1, 2, 3]},
            expect_complete=True,
            expected_result={"rows": [1, 2, 3]},
        )
    )

    # clean-10-expected_failure_invalid_transform
    s = start_node()
    bad = Node.create(
        type=NodeType.TRANSFORM,
        name="bad",
        config={},  # missing config.type -> should fail
        position=Position(x=1, y=0),
    )
    e = end_node()
    scenarios.append(
        _Scenario(
            scenario_id="clean-10-expected_failure_invalid_transform",
            workflow=wf(
                [s, bad, e],
                [
                    Edge.create(source_node_id=s.id, target_node_id=bad.id),
                    Edge.create(source_node_id=bad.id, target_node_id=e.id),
                ],
            ),
            initial_input={"x": 1},
            expect_complete=False,
        )
    )

    use_case = ExecuteWorkflowUseCase(workflow_repository=repo, executor_registry=registry)

    successes = 0
    for scenario in scenarios:
        events, last = await _run_use_case_stream(use_case, scenario)

        assert any(e.get("type") == "node_start" for e in events), scenario.scenario_id
        assert last.get("type") in {"workflow_complete", "workflow_error"}, scenario.scenario_id

        if scenario.expect_complete:
            assert last["type"] == "workflow_complete", scenario.scenario_id
            assert last["result"] == scenario.expected_result, scenario.scenario_id
            successes += 1
        else:
            assert last["type"] == "workflow_error", scenario.scenario_id

    assert len(scenarios) == 10
    assert successes >= 6

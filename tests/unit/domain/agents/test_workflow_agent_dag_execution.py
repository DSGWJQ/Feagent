"""
WorkflowAgent DAG Topological Sort and Workflow Execution Tests

Focus areas:
- _topological_sort() Kahn's algorithm correctness
- Dependency ordering enforcement (linear, diamond, disconnected graphs)
- Cycle detection
- execute_workflow() lifecycle (started/completed events)
- Workflow-level error handling (pending_human, node failures)
- execute_workflow_with_results() ExecutionResult integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.agents.workflow_agent import (
    WorkflowAgent,
    WorkflowExecutionCompletedEvent,
    WorkflowExecutionStartedEvent,
)
from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
from src.domain.services.event_bus import EventBus
from src.domain.services.execution_result import ErrorCode, ExecutionResult
from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType


def _make_test_agent(event_bus: EventBus | None = None) -> WorkflowAgent:
    """Create WorkflowAgent with mock executor for testing"""
    ctx = WorkflowContext(
        workflow_id="wf_dag_test",
        session_context=SessionContext(
            session_id="test_session",
            global_context=GlobalContext(user_id="test_user"),
        ),
    )

    factory = NodeFactory(NodeRegistry())
    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"executed": True})

    return WorkflowAgent(
        workflow_context=ctx,
        node_factory=factory,
        node_executor=executor,
        event_bus=event_bus,
    )


def _node_order_index(execution_order: list[str]) -> dict[str, int]:
    """Convert execution order list to position mapping"""
    return {node_id: idx for idx, node_id in enumerate(execution_order)}


# =============================================================================
# Topological Sort Algorithm Tests
# =============================================================================


class TestTopologicalSort:
    """Test _topological_sort() Kahn's algorithm implementation"""

    @pytest.mark.parametrize(
        ("edges", "must_precede"),
        [
            # Linear chain: A -> B -> C
            (
                [("A", "B"), ("B", "C")],
                [("A", "B"), ("B", "C")],
            ),
            # Fan-in: A->C, B->C (both A and B must come before C)
            (
                [("A", "C"), ("B", "C")],
                [("A", "C"), ("B", "C")],
            ),
            # Diamond: A->B, A->C, B->D, C->D
            (
                [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
                [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
            ),
            # Disconnected components: A->B exists, C and D are isolated
            (
                [("A", "B")],
                [("A", "B")],
            ),
        ],
    )
    def test_topological_sort_respects_dependency_constraints(
        self, edges: list[tuple[str, str]], must_precede: list[tuple[str, str]]
    ):
        """Test: Topological sort maintains all dependency orderings"""
        agent = _make_test_agent()

        # Create nodes for all unique IDs in edges
        node_ids = {n for edge in edges for n in edge} | {"C", "D"}
        for node_id in node_ids:
            agent.add_node(node_id, "generic", config={"name": node_id})

        for source, target in edges:
            agent.connect_nodes(source, target)

        execution_order = agent._topological_sort()
        positions = _node_order_index(execution_order)

        # Verify all nodes returned exactly once (no duplicates, no missing nodes)
        assert (
            set(execution_order) == node_ids
        ), f"Expected nodes {node_ids}, got {set(execution_order)}"
        assert len(execution_order) == len(node_ids), "Duplicate nodes detected in execution order"

        # Verify all dependencies are satisfied
        for source, target in must_precede:
            if source in positions and target in positions:
                assert (
                    positions[source] < positions[target]
                ), f"{source} must execute before {target}"

    def test_topological_sort_handles_empty_graph(self):
        """Test: Empty graph returns empty execution order"""
        agent = _make_test_agent()
        assert agent._topological_sort() == []

    def test_topological_sort_handles_single_node(self):
        """Test: Single node with no edges"""
        agent = _make_test_agent()
        agent.add_node("solo", "generic", config={})

        order = agent._topological_sort()
        assert order == ["solo"]

    def test_topological_sort_ignores_edges_to_unknown_nodes(self):
        """Test: Edges referencing nonexistent nodes are ignored"""
        agent = _make_test_agent()

        agent.add_node("A", "generic", config={})
        agent.add_node("B", "generic", config={})
        agent.connect_nodes("A", "B")

        # Add edge to unknown node (should be ignored)
        agent._edges.append(MagicMock(source_id="A", target_id="UNKNOWN"))

        order = agent._topological_sort()
        assert "A" in order
        assert "B" in order
        assert "UNKNOWN" not in order
        assert order.index("A") < order.index("B")

    def test_topological_sort_raises_on_cycle(self):
        """Test: Circular dependencies raise ValueError"""
        agent = _make_test_agent()

        agent.add_node("A", "generic", config={})
        agent.add_node("B", "generic", config={})
        agent.connect_nodes("A", "B")
        agent.connect_nodes("B", "A")  # Creates cycle

        with pytest.raises(ValueError, match="cycle"):
            agent._topological_sort()


# =============================================================================
# Workflow Execution Lifecycle Tests
# =============================================================================


class TestExecuteWorkflow:
    """Test execute_workflow() orchestration and event emission"""

    @pytest.mark.asyncio
    async def test_execute_workflow_emits_started_and_completed_events(self):
        """Test: Workflow execution emits lifecycle events"""
        event_bus = EventBus()
        agent = _make_test_agent(event_bus=event_bus)

        node1 = agent.node_factory.create(NodeType.GENERIC, {"name": "node1"})
        node2 = agent.node_factory.create(NodeType.GENERIC, {"name": "node2"})
        agent.add_node(node1)
        agent.add_node(node2)
        agent.connect_nodes(node1.id, node2.id)

        result = await agent.execute_workflow()

        assert result["status"] == "completed"
        assert node1.id in result["results"]
        assert node2.id in result["results"]

        started_events = [
            e for e in event_bus.event_log if isinstance(e, WorkflowExecutionStartedEvent)
        ]
        completed_events = [
            e for e in event_bus.event_log if isinstance(e, WorkflowExecutionCompletedEvent)
        ]

        assert len(started_events) == 1
        assert len(completed_events) == 1
        assert completed_events[0].status == "completed"

    @pytest.mark.asyncio
    async def test_execute_workflow_executes_nodes_in_topological_order(self):
        """Test: Nodes execute respecting dependency order"""
        execution_log = []

        async def mock_execute(node_id, config, inputs):
            execution_log.append(node_id)
            return {"executed": True}

        agent = _make_test_agent()
        agent.node_executor.execute = AsyncMock(side_effect=mock_execute)

        agent.add_node("first", "generic", config={})
        agent.add_node("second", "generic", config={})
        agent.add_node("third", "generic", config={})

        agent.connect_nodes("first", "second")
        agent.connect_nodes("second", "third")

        await agent.execute_workflow()

        assert execution_log == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_execute_workflow_returns_pending_on_human_input(self):
        """Test: HUMAN node pending state halts workflow execution"""
        event_bus = EventBus()
        agent = _make_test_agent(event_bus=event_bus)

        # First node returns pending_human_input status
        agent.node_executor.execute = AsyncMock(return_value={"status": "pending_human_input"})

        node = agent.node_factory.create(NodeType.GENERIC, {"name": "blocker"})
        agent.add_node(node)

        result = await agent.execute_workflow()

        assert result["status"] == "pending_human_input"
        assert node.id in result["results"]

    @pytest.mark.asyncio
    async def test_execute_workflow_returns_failed_on_node_exception(self):
        """Test: Node execution exception fails workflow"""
        agent = _make_test_agent()
        agent.node_executor.execute = AsyncMock(side_effect=RuntimeError("Node crashed"))

        node = agent.node_factory.create(NodeType.GENERIC, {"name": "faulty_node"})
        agent.add_node(node)

        result = await agent.execute_workflow()

        assert result["status"] == "failed"
        assert "Node crashed" in result["error"]


# =============================================================================
# execute_workflow_with_results() Integration Tests
# =============================================================================


class TestExecuteWorkflowWithResults:
    """Test execute_workflow_with_results() ExecutionResult wrapper"""

    @pytest.mark.asyncio
    async def test_execute_workflow_with_results_stops_on_failed_node(self):
        """Test: First failed node halts execution"""
        agent = _make_test_agent()

        # Mock execute_node_with_result to control outcomes
        agent.execute_node_with_result = AsyncMock(
            side_effect=[
                ExecutionResult.ok(output={"node_a": "done"}),
                ExecutionResult.failure(
                    error_code=ErrorCode.INTERNAL_ERROR, error_message="Node B failed"
                ),
            ]
        )

        agent.add_node("A", "generic", config={})
        agent.add_node("B", "generic", config={})
        agent.connect_nodes("A", "B")

        result = await agent.execute_workflow_with_results()

        assert result.success is False
        assert result.failed_node_id == "B"

    @pytest.mark.asyncio
    async def test_execute_workflow_with_results_detects_pending_human_status(self):
        """Test: pending_human_input in output triggers special handling"""
        agent = _make_test_agent()

        agent.execute_node_with_result = AsyncMock(
            return_value=ExecutionResult.failure(
                error_code=ErrorCode.DEPENDENCY_FAILED,
                error_message="Awaiting human input",
                output={"status": "pending_human_input"},
            )
        )

        agent.add_node("A", "generic", config={})

        result = await agent.execute_workflow_with_results()

        assert result.success is False
        assert result.metadata.get("status") == "pending_human_input"

    @pytest.mark.asyncio
    async def test_execute_workflow_with_results_success_aggregates_outputs(self):
        """Test: Successful workflow aggregates all node outputs"""
        agent = _make_test_agent()

        agent.execute_node_with_result = AsyncMock(
            side_effect=[
                ExecutionResult.ok(output={"a_result": 1}),
                ExecutionResult.ok(output={"b_result": 2}),
            ]
        )

        agent.add_node("A", "generic", config={})
        agent.add_node("B", "generic", config={})
        agent.connect_nodes("A", "B")

        result = await agent.execute_workflow_with_results()

        assert result.success is True
        # Note: workflow_agent.WorkflowExecutionResult (not execution_result.WorkflowExecutionResult)
        # stores ExecutionResult objects per node in node_results dict
        assert "A" in result.node_results
        assert "B" in result.node_results
        assert result.node_results["A"].output == {"a_result": 1}
        assert result.node_results["B"].output == {"b_result": 2}

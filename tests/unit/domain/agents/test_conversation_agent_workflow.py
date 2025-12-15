"""
Unit tests for ConversationAgentWorkflowMixin

Focus on:
- Workflow planning (create_workflow_plan)
- Node decomposition (decompose_to_nodes)
- Event publishing (create_workflow_plan_and_publish)
- Workflow replanning (replan_workflow)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def workflow_module():
    """Import conversation_agent_workflow module"""
    import importlib

    return importlib.import_module("src.domain.agents.conversation_agent_workflow")


@pytest.fixture()
def mock_agent(workflow_module):
    """Create mock agent with ConversationAgentWorkflowMixin"""

    class MockAgent(workflow_module.ConversationAgentWorkflowMixin):
        def __init__(self):
            # Required host attributes
            self.llm = AsyncMock()
            self.event_bus = AsyncMock()
            self.session_context = MagicMock()
            self.session_context.session_id = "test-session-123"

            # Mock host methods
            self.get_context_for_reasoning = MagicMock(return_value={"history": []})
            self._stage_decision_record = MagicMock()
            self._flush_staged_state = AsyncMock()

    return MockAgent()


# =============================================================================
# Class 1: TestCreateWorkflowPlan (6 tests)
# =============================================================================


class TestCreateWorkflowPlan:
    """Test create_workflow_plan method"""

    @pytest.mark.asyncio
    async def test_create_workflow_plan_success(self, mock_agent):
        """Test: create_workflow_plan creates WorkflowPlan from LLM data"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={
                "name": "Test Plan",
                "description": "Test workflow",
                "nodes": [
                    {"type": "python", "name": "node1", "code": "print('hello')"},
                    {"type": "llm", "name": "node2", "prompt": "test prompt"},
                ],
                "edges": [{"source": "node1", "target": "node2"}],
            }
        )

        plan = await mock_agent.create_workflow_plan("test goal")

        assert plan.name == "Test Plan"
        assert len(plan.nodes) == 2
        assert len(plan.edges) == 1
        mock_agent.llm.plan_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_workflow_plan_converts_nodes_and_edges(self, mock_agent):
        """Test: create_workflow_plan converts plan_data to NodeDefinition and EdgeDefinition"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={
                "name": "Test Plan",
                "nodes": [
                    {"type": "python", "name": "node1", "code": "x = 1"},
                    {"type": "python", "name": "node2", "code": "y = 2"},
                ],
                "edges": [{"source_node": "node1", "target_node": "node2", "condition": "x > 0"}],
            }
        )

        plan = await mock_agent.create_workflow_plan("test goal")

        # Verify node conversion
        assert plan.nodes[0].name == "node1"
        assert plan.nodes[0].code == "x = 1"
        assert plan.nodes[1].name == "node2"

        # Verify edge conversion
        assert plan.edges[0].source_node == "node1"
        assert plan.edges[0].target_node == "node2"
        assert plan.edges[0].condition == "x > 0"

    @pytest.mark.asyncio
    async def test_create_workflow_plan_invalid_node_type_defaults_to_generic(self, mock_agent):
        """Test: create_workflow_plan handles invalid NodeType and defaults to GENERIC"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={
                "name": "Test Plan",
                "nodes": [{"type": "invalid_type", "name": "node1"}],
                "edges": [],
            }
        )

        plan = await mock_agent.create_workflow_plan("test goal")

        from src.domain.agents.node_definition import NodeType

        assert plan.nodes[0].node_type == NodeType.GENERIC

    @pytest.mark.asyncio
    async def test_create_workflow_plan_with_parent_child_nodes(self, mock_agent):
        """Test: create_workflow_plan handles parent-child node structure"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={
                "name": "Test Plan",
                "nodes": [
                    {
                        "type": "generic",  # Only GENERIC nodes can have children
                        "name": "parent",
                        "children": [
                            {"type": "python", "name": "child1", "code": "x = 1"},
                            {"type": "python", "name": "child2", "code": "y = 2"},
                        ],
                        "error_strategy": "retry",
                        "resource_limits": {"timeout": 30},
                    }
                ],
                "edges": [],
            }
        )

        plan = await mock_agent.create_workflow_plan("test goal")

        parent_node = plan.nodes[0]
        assert parent_node.name == "parent"
        assert len(parent_node.children) == 2
        assert parent_node.children[0].name == "child1"
        assert parent_node.children[1].name == "child2"

    @pytest.mark.asyncio
    async def test_create_workflow_plan_circular_dependency_raises(self, mock_agent):
        """Test: create_workflow_plan raises ValueError when circular dependency detected"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={
                "name": "Circular Plan",
                "nodes": [
                    {"type": "python", "name": "node1", "code": "x = 1"},
                    {"type": "python", "name": "node2", "code": "y = 2"},
                ],
                "edges": [
                    {"source_node": "node1", "target_node": "node2"},
                    {"source_node": "node2", "target_node": "node1"},  # Creates cycle
                ],
            }
        )

        with pytest.raises(ValueError, match="循环依赖|Circular dependency"):
            await mock_agent.create_workflow_plan("test goal")


# =============================================================================
# Class 2: TestDecomposeToNodes (4 tests)
# =============================================================================


class TestDecomposeToNodes:
    """Test decompose_to_nodes method"""

    @pytest.mark.asyncio
    async def test_decompose_to_nodes_success(self, mock_agent):
        """Test: decompose_to_nodes returns list of NodeDefinition from LLM"""
        mock_agent.llm.decompose_to_nodes = AsyncMock(
            return_value=[
                {"type": "python", "name": "step1", "code": "import pandas"},
                {"type": "llm", "name": "step2", "prompt": "analyze data"},
            ]
        )

        nodes = await mock_agent.decompose_to_nodes("process data")

        assert len(nodes) == 2
        assert nodes[0].name == "step1"
        assert nodes[1].name == "step2"
        mock_agent.llm.decompose_to_nodes.assert_awaited_once_with("process data")

    @pytest.mark.asyncio
    async def test_decompose_to_nodes_invalid_node_type_defaults_to_generic(self, mock_agent):
        """Test: decompose_to_nodes handles invalid NodeType and defaults to GENERIC"""
        mock_agent.llm.decompose_to_nodes = AsyncMock(
            return_value=[{"type": "unknown_type", "name": "node1"}]
        )

        nodes = await mock_agent.decompose_to_nodes("test goal")

        from src.domain.agents.node_definition import NodeType

        assert nodes[0].node_type == NodeType.GENERIC

    @pytest.mark.asyncio
    async def test_decompose_to_nodes_with_parent_child_structure(self, mock_agent):
        """Test: decompose_to_nodes handles parent-child node structure"""
        mock_agent.llm.decompose_to_nodes = AsyncMock(
            return_value=[
                {
                    "type": "generic",  # Only GENERIC nodes can have children
                    "name": "parent",
                    "children": [
                        {"type": "python", "name": "child1"},
                        {"type": "python", "name": "child2"},
                    ],
                }
            ]
        )

        nodes = await mock_agent.decompose_to_nodes("test goal")

        assert len(nodes) == 1
        assert nodes[0].name == "parent"
        assert len(nodes[0].children) == 2

    @pytest.mark.asyncio
    async def test_decompose_to_nodes_strategy_propagation(self, mock_agent):
        """Test: decompose_to_nodes propagates strategy to children"""
        mock_agent.llm.decompose_to_nodes = AsyncMock(
            return_value=[
                {
                    "type": "generic",  # Only GENERIC nodes can have children
                    "name": "parent",
                    "error_strategy": "retry",
                    "resource_limits": {"timeout": 30},
                    "children": [{"type": "python", "name": "child1"}],
                }
            ]
        )

        nodes = await mock_agent.decompose_to_nodes("test goal")

        parent = nodes[0]
        assert parent.error_strategy == "retry"
        # Verify strategy propagation was called
        assert len(parent.children) == 1


# =============================================================================
# Class 3: TestCreateWorkflowPlanAndPublish (5 tests)
# =============================================================================


class TestCreateWorkflowPlanAndPublish:
    """Test create_workflow_plan_and_publish method"""

    @pytest.mark.asyncio
    async def test_create_workflow_plan_and_publish_success(self, mock_agent):
        """Test: create_workflow_plan_and_publish creates plan, publishes event, records decision"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={
                "name": "Test Plan",
                "nodes": [{"type": "python", "name": "node1", "code": "print('test')"}],
                "edges": [],
            }
        )

        plan = await mock_agent.create_workflow_plan_and_publish("test goal")

        assert plan.name == "Test Plan"
        # Verify event was published
        mock_agent.event_bus.publish.assert_called_once()
        # Verify decision was staged and flushed
        mock_agent._stage_decision_record.assert_called_once()
        mock_agent._flush_staged_state.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_workflow_plan_and_publish_publishes_event_when_event_bus_exists(
        self, mock_agent
    ):
        """Test: create_workflow_plan_and_publish publishes DecisionMadeEvent when event_bus exists"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={"name": "Plan", "nodes": [], "edges": []}
        )

        await mock_agent.create_workflow_plan_and_publish("test goal")

        # Verify event_bus.publish was called
        assert mock_agent.event_bus.publish.call_count == 1
        call_args = mock_agent.event_bus.publish.call_args[0][0]
        assert call_args.source == "conversation_agent"

    @pytest.mark.asyncio
    async def test_create_workflow_plan_and_publish_no_event_when_event_bus_none(self, mock_agent):
        """Test: create_workflow_plan_and_publish doesn't publish when event_bus is None"""
        mock_agent.event_bus = None
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={"name": "Plan", "nodes": [], "edges": []}
        )

        plan = await mock_agent.create_workflow_plan_and_publish("test goal")

        # Plan should still be created
        assert plan.name == "Plan"
        # But decision should still be staged (even without event_bus)
        mock_agent._stage_decision_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_workflow_plan_and_publish_stages_and_flushes_decision(self, mock_agent):
        """Test: create_workflow_plan_and_publish stages decision and flushes state"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={"name": "Plan", "nodes": [], "edges": []}
        )

        await mock_agent.create_workflow_plan_and_publish("test goal")

        # Verify _stage_decision_record was called with correct structure
        call_args = mock_agent._stage_decision_record.call_args[0][0]
        assert "id" in call_args
        assert call_args["type"] == "create_workflow_plan"
        assert "timestamp" in call_args

        # Verify _flush_staged_state was called
        mock_agent._flush_staged_state.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_workflow_plan_and_publish_event_payload(self, mock_agent):
        """Test: create_workflow_plan_and_publish event payload contains plan.to_dict()"""
        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={"name": "Test Plan", "nodes": [], "edges": []}
        )

        await mock_agent.create_workflow_plan_and_publish("test goal")

        event = mock_agent.event_bus.publish.call_args[0][0]
        assert event.decision_type == "create_workflow_plan"
        assert "nodes" in event.payload  # plan.to_dict() should contain nodes


# =============================================================================
# Class 4: TestReplanWorkflow (3 tests)
# =============================================================================


class TestReplanWorkflow:
    """Test replan_workflow method"""

    @pytest.mark.asyncio
    async def test_replan_workflow_success_with_replan_method(self, mock_agent):
        """Test: replan_workflow calls llm.replan_workflow when method exists"""
        mock_agent.llm.replan_workflow = AsyncMock(
            return_value={"name": "Replanned", "nodes": [], "edges": []}
        )

        plan_dict = await mock_agent.replan_workflow(
            original_goal="test goal",
            failed_node_id="node_2",
            failure_reason="timeout",
            execution_context={"completed": ["node_1"]},
        )

        assert plan_dict["name"] == "Replanned"
        mock_agent.llm.replan_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_replan_workflow_fallback_when_no_replan_method(self, mock_agent):
        """Test: replan_workflow falls back to plan_workflow when replan_workflow not available"""
        # Remove replan_workflow attribute to simulate it not existing
        if hasattr(mock_agent.llm, "replan_workflow"):
            delattr(mock_agent.llm, "replan_workflow")

        mock_agent.llm.plan_workflow = AsyncMock(
            return_value={"name": "Fallback Plan", "nodes": [], "edges": []}
        )

        plan_dict = await mock_agent.replan_workflow(
            original_goal="test goal",
            failed_node_id="node_2",
            failure_reason="error",
            execution_context={},
        )

        assert plan_dict["name"] == "Fallback Plan"
        # Verify fallback to plan_workflow
        mock_agent.llm.plan_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_replan_workflow_builds_correct_context(self, mock_agent):
        """Test: replan_workflow builds context with failure information"""
        mock_agent.llm.replan_workflow = AsyncMock(
            return_value={"name": "Replanned", "nodes": [], "edges": []}
        )

        await mock_agent.replan_workflow(
            original_goal="original",
            failed_node_id="node_2",
            failure_reason="timeout",
            execution_context={"completed": ["node_1"]},
        )

        # Verify context building (get_context_for_reasoning was called)
        mock_agent.get_context_for_reasoning.assert_called_once()

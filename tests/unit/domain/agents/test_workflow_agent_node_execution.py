"""
WorkflowAgent Node Execution Flow Tests

Focus areas:
- execute_node() dispatcher logic (custom/node_executor/default fallback)
- Input collection from upstream nodes
- Event emission (NodeExecutionEvent)
- FILE node validation with coordinator
- HUMAN node pending state handling
- execute_node_with_result() structured error handling and retry logic
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.agents.workflow_agent import (
    HumanInputRequestedEvent,
    NodeExecutionEvent,
    WorkflowAgent,
)
from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
from src.domain.services.event_bus import EventBus
from src.domain.services.execution_result import (
    ErrorCode,
    ExecutionResult,
    OutputValidator,
    RetryPolicy,
)
from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType


def _make_context(workflow_id: str = "wf_test") -> WorkflowContext:
    """Create test WorkflowContext with minimal setup"""
    global_ctx = GlobalContext(
        user_id="test_user",
        system_config={"threshold": 0.8},
        user_preferences={"lang": "zh"},
    )
    session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)
    return WorkflowContext(workflow_id=workflow_id, session_context=session_ctx)


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def node_factory() -> NodeFactory:
    return NodeFactory(NodeRegistry())


@pytest.fixture
def workflow_context() -> WorkflowContext:
    return _make_context()


def _filter_events(bus: EventBus, event_type: type) -> list:
    """Filter events by type from event bus log"""
    return [e for e in bus.event_log if isinstance(e, event_type)]


# =============================================================================
# Node Execution Core Flow
# =============================================================================


class TestExecuteNodeDispatcher:
    """Test execute_node() executor dispatch logic"""

    @pytest.mark.asyncio
    async def test_execute_node_raises_when_node_missing(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Missing node raises ValueError"""
        agent = WorkflowAgent(workflow_context=workflow_context, node_factory=node_factory)

        with pytest.raises(ValueError, match="Node not found"):
            await agent.execute_node("nonexistent_node_id")

    @pytest.mark.asyncio
    async def test_execute_node_uses_node_executor_when_provided(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory, event_bus: EventBus
    ):
        """Test: node_executor is used when provided"""
        node_executor = MagicMock()
        node_executor.execute = AsyncMock(return_value={"result": "from_node_executor"})

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            node_executor=node_executor,
            event_bus=event_bus,
        )

        node = node_factory.create(NodeType.GENERIC, {"name": "test_node"})
        agent.add_node(node)

        output = await agent.execute_node(node.id)

        assert output["result"] == "from_node_executor"
        assert workflow_context.get_node_output(node.id) == output

    @pytest.mark.asyncio
    async def test_execute_node_uses_custom_executor_for_custom_type(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory, event_bus: EventBus
    ):
        """Test: Custom node type uses its own executor"""

        class CustomExecutor:
            async def execute(self, config, inputs):
                return {"custom": True, "config": config, "inputs": inputs}

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            event_bus=event_bus,
        )

        agent.define_custom_node_type(
            "custom_type",
            schema={"field": {"required": True}},
            executor_class=CustomExecutor,
        )

        node = agent.create_node(
            {
                "node_type": "custom_type",
                "config": {"field": "value"},
            }
        )
        agent.add_node(node)

        output = await agent.execute_node(node.id)

        assert output["custom"] is True
        assert output["config"]["field"] == "value"

    @pytest.mark.asyncio
    async def test_execute_node_uses_default_fallback_when_no_executor(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Default executor returns success when no custom executor"""
        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            node_executor=None,
        )

        node = node_factory.create(NodeType.GENERIC, {"name": "fallback_node"})
        agent.add_node(node)

        output = await agent.execute_node(node.id)

        assert output["status"] == "success"
        assert output["executed"] is True

    @pytest.mark.asyncio
    async def test_execute_node_collects_inputs_from_upstream_nodes(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Node receives outputs from all upstream dependencies"""
        node_executor = MagicMock()
        node_executor.execute = AsyncMock(return_value={"merged": True})

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            node_executor=node_executor,
        )

        node_a = node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = node_factory.create(NodeType.GENERIC, {"name": "node_b"})
        node_c = node_factory.create(NodeType.GENERIC, {"name": "node_c"})

        agent.add_node(node_a)
        agent.add_node(node_b)
        agent.add_node(node_c)

        agent.connect_nodes(node_a.id, node_c.id)
        agent.connect_nodes(node_b.id, node_c.id)

        workflow_context.set_node_output(node_a.id, {"a_data": 1})
        workflow_context.set_node_output(node_b.id, {"b_data": 2})

        await agent.execute_node(node_c.id)

        # Verify executor received inputs from upstream nodes
        # Production code calls: node_executor.execute(node_id, config, inputs)
        call_args = node_executor.execute.call_args
        assert call_args.args[0] == node_c.id  # First arg: node_id
        inputs = call_args.args[2]  # Third arg: inputs dict

        # Check complete inputs structure
        assert node_a.id in inputs
        assert node_b.id in inputs
        assert inputs[node_a.id] == {"a_data": 1}
        assert inputs[node_b.id] == {"b_data": 2}

    @pytest.mark.asyncio
    async def test_execute_node_emits_started_and_completed_events(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory, event_bus: EventBus
    ):
        """Test: Execution emits proper lifecycle events"""
        node_executor = MagicMock()
        node_executor.execute = AsyncMock(return_value={"done": True})

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            node_executor=node_executor,
            event_bus=event_bus,
        )

        node = node_factory.create(NodeType.GENERIC, {"name": "event_node"})
        agent.add_node(node)

        await agent.execute_node(node.id)

        events = _filter_events(event_bus, NodeExecutionEvent)
        statuses = [e.status for e in events]

        assert "running" in statuses
        assert "completed" in statuses
        assert all(e.node_id == node.id for e in events)
        assert all(e.workflow_id == workflow_context.workflow_id for e in events)


# =============================================================================
# FILE and HUMAN Node Guards
# =============================================================================


class TestFileNodeValidation:
    """Test FILE node security validation"""

    @pytest.mark.asyncio
    async def test_validate_file_node_noop_for_non_file_nodes(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Non-FILE nodes skip validation"""
        agent = WorkflowAgent(workflow_context=workflow_context, node_factory=node_factory)
        node = node_factory.create(NodeType.GENERIC, {"name": "generic"})

        await agent._validate_file_node(node)  # Should not raise

    @pytest.mark.asyncio
    async def test_validate_file_node_emits_failed_event_on_rejection(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory, event_bus: EventBus
    ):
        """Test: Rejected FILE operations emit failure event"""

        class MockValidation:
            is_valid = False
            errors = ["Access denied to file"]

        coordinator = MagicMock()
        coordinator.validate_file_operation = AsyncMock(return_value=MockValidation())

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            coordinator_agent=coordinator,
            event_bus=event_bus,
        )

        node = node_factory.create(NodeType.FILE, {"operation": "read", "path": "secret.txt"})

        with pytest.raises(PermissionError, match="Access denied"):
            await agent._validate_file_node(node)

        events = _filter_events(event_bus, NodeExecutionEvent)
        assert len(events) == 1
        assert events[0].status == "failed"
        assert "Access denied" in (events[0].error or "")


class TestHumanNodeHandling:
    """Test HUMAN node pending state logic"""

    @pytest.mark.asyncio
    async def test_handle_human_node_request_noop_for_non_human_nodes(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Non-HUMAN nodes return None"""
        agent = WorkflowAgent(workflow_context=workflow_context, node_factory=node_factory)
        node = node_factory.create(NodeType.GENERIC, {"name": "generic"})

        result = await agent._handle_human_node_request(node)
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_node_for_human_emits_request_event_and_returns_pending(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory, event_bus: EventBus
    ):
        """Test: HUMAN node execution triggers input request event"""
        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            event_bus=event_bus,
        )

        node = node_factory.create(
            NodeType.HUMAN,
            {
                "prompt": "Please provide input",
                "expected_inputs": ["user_choice"],
                "timeout_seconds": 60,
            },
        )
        agent.add_node(node)

        output = await agent.execute_node(node.id)

        assert output["status"] == "pending_human_input"
        assert workflow_context.get_node_output(node.id)["status"] == "pending_human_input"

        request_events = _filter_events(event_bus, HumanInputRequestedEvent)
        assert len(request_events) == 1
        assert request_events[0].node_id == node.id


# =============================================================================
# execute_node_with_result() Structured Error Handling
# =============================================================================


class TestExecuteNodeWithResult:
    """Test execute_node_with_result() with ExecutionResult wrapper"""

    @pytest.mark.asyncio
    async def test_execute_node_with_result_returns_failure_for_missing_node(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Missing node returns INTERNAL_ERROR ExecutionResult"""
        agent = WorkflowAgent(workflow_context=workflow_context, node_factory=node_factory)

        result = await agent.execute_node_with_result("missing_id")

        assert isinstance(result, ExecutionResult)
        assert result.success is False
        assert result.error_code == ErrorCode.INTERNAL_ERROR

    @pytest.mark.asyncio
    async def test_execute_node_with_result_returns_dependency_failed_for_human_pending(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory, event_bus: EventBus
    ):
        """Test: HUMAN pending state returns DEPENDENCY_FAILED"""
        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            event_bus=event_bus,
        )

        node = node_factory.create(NodeType.HUMAN, {"prompt": "Need input"})
        agent.add_node(node)

        result = await agent.execute_node_with_result(node.id)

        assert result.success is False
        assert result.error_code == ErrorCode.DEPENDENCY_FAILED
        assert result.output["status"] == "pending_human_input"

    @pytest.mark.asyncio
    async def test_execute_node_with_result_validates_output_schema(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Output validation failure returns VALIDATION_FAILED"""
        node_executor = MagicMock()
        node_executor.execute = AsyncMock(return_value={"value": "not_an_integer"})

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            node_executor=node_executor,
        )

        node = node_factory.create(NodeType.GENERIC, {"name": "typed_node"})
        agent.add_node(node)

        validator = OutputValidator(schema={"value": {"required": True, "type": "integer"}})
        result = await agent.execute_node_with_result(node.id, output_validator=validator)

        assert result.success is False
        assert result.error_code == ErrorCode.VALIDATION_FAILED

    @pytest.mark.asyncio
    async def test_execute_node_with_result_retries_on_transient_failure(
        self, monkeypatch, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Retry policy allows recovery from transient errors"""
        node_executor = MagicMock()
        node_executor.execute = AsyncMock(side_effect=[TimeoutError("timeout"), {"success": True}])

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            node_executor=node_executor,
        )

        node = node_factory.create(NodeType.GENERIC, {"name": "retry_node"})
        agent.add_node(node)

        sleep_mock = AsyncMock()
        monkeypatch.setattr("src.domain.agents.workflow_agent.asyncio.sleep", sleep_mock)

        policy = RetryPolicy(max_retries=1, base_delay=0.01)
        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is True
        assert result.output["success"] is True
        assert node_executor.execute.call_count == 2
        sleep_mock.assert_awaited()

    @pytest.mark.asyncio
    async def test_execute_node_with_result_exhausted_retries_returns_failure(
        self, workflow_context: WorkflowContext, node_factory: NodeFactory
    ):
        """Test: Retry exhaustion returns appropriate error code"""
        node_executor = MagicMock()
        node_executor.execute = AsyncMock(side_effect=ConnectionError("Network down"))

        agent = WorkflowAgent(
            workflow_context=workflow_context,
            node_factory=node_factory,
            node_executor=node_executor,
        )

        node = node_factory.create(NodeType.GENERIC, {"name": "failing_node"})
        agent.add_node(node)

        policy = RetryPolicy(max_retries=0)
        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is False
        assert result.error_code == ErrorCode.NETWORK_ERROR

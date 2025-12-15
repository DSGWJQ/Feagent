"""ConversationAgent ReAct core module unit tests

Coverage for src.domain.agents.conversation_agent_react_core:
- ReAct loop execution (run_async, _run_sync, execute_step, run)
- Decision making (make_decision, _record_decision, _record_decision_async)
- Decision publishing (publish_decision)

Test Strategy:
- P0: run_async (16 tests) - main async loop with all termination conditions
- P0: make_decision (4 tests) - Pydantic validation
- P0: _record_decision (2 tests) - sync/async recording
- P1: _run_sync (4 tests) - mock compatibility
- P1: publish_decision (1 test)
- P1: execute_step (1 test)

Total: 28 tests targeting ~70-80% coverage
"""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture()
def react_core_module():
    """Dynamically import react core module"""
    return importlib.import_module("src.domain.agents.conversation_agent_react_core")


@pytest.fixture()
def models_module():
    """Dynamically import models module"""
    return importlib.import_module("src.domain.agents.conversation_agent_models")


@pytest.fixture()
def mock_agent(react_core_module, models_module):
    """Create mock agent with ConversationAgentReActCoreMixin"""

    class MockAgent(react_core_module.ConversationAgentReActCoreMixin):
        def __init__(self):
            # Required attributes
            self.llm = AsyncMock()
            self.session_context = MagicMock()
            self.event_bus = AsyncMock()
            self.coordinator = None  # Default to None (no coordinator)
            self.emitter = AsyncMock()

            # Configuration
            self.max_iterations = 5
            self.timeout_seconds = 10.0
            self.max_tokens = 1000
            self.max_cost = 1.0

            # State
            self._current_input = None
            self._coordinator_context = None
            self._decision_metadata = []

            # Mock helper methods
            self.get_context_for_reasoning = MagicMock(return_value={})
            self._initialize_model_info = MagicMock()
            self._log_coordinator_context = MagicMock()
            self._log_context_warning = MagicMock()
            self._stage_token_usage = MagicMock()
            self._stage_decision_record = MagicMock()
            self._flush_staged_state = AsyncMock()

            # Session context setup
            self.session_context.context_limit = 4096
            self.session_context.is_approaching_limit = MagicMock(return_value=False)
            self.session_context.add_decision = MagicMock()
            self.session_context.resource_constraints = None

    return MockAgent()


# =============================================================================
# TestRunAsync - Main async loop (16 tests)
# =============================================================================


class TestRunAsync:
    """Test run_async main ReAct loop"""

    @pytest.mark.asyncio
    async def test_run_async_completes_on_respond_action(self, mock_agent):
        """Test: run_async completes when action_type is 'respond'"""
        mock_agent.llm.think = AsyncMock(return_value="Thinking about user request")
        mock_agent.llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "Task completed"}
        )

        result = await mock_agent.run_async("test input")

        assert result.completed is True
        assert result.final_response == "Task completed"
        assert result.iterations == 1
        assert result.terminated_by_limit is False
        mock_agent._flush_staged_state.assert_called()

    @pytest.mark.asyncio
    async def test_run_async_terminates_by_circuit_breaker(self, mock_agent):
        """Test: run_async terminates when circuit breaker is open"""
        # Set up coordinator with circuit breaker
        mock_agent.coordinator = MagicMock()
        mock_agent.coordinator.circuit_breaker = MagicMock(is_open=True)

        result = await mock_agent.run_async("test input")

        assert result.terminated_by_limit is True
        assert result.limit_type == "circuit_breaker"
        assert "熔断器已打开" in result.alert_message
        assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_run_async_terminates_by_timeout(self, mock_agent, monkeypatch):
        """Test: run_async terminates when timeout is exceeded"""
        import time

        mock_agent.timeout_seconds = 0.1
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = AsyncMock(return_value=True)

        # Force time.time() to simulate timeout
        start_time = time.time()
        call_count = [0]

        def mock_time():
            call_count[0] += 1
            if call_count[0] > 5:  # After initial checks
                return start_time + 1.0  # Exceed timeout
            return start_time

        monkeypatch.setattr(time, "time", mock_time)

        result = await mock_agent.run_async("test input")

        assert result.terminated_by_limit is True
        assert result.limit_type == "timeout"
        assert "已超时" in result.alert_message

    @pytest.mark.asyncio
    async def test_run_async_terminates_by_token_limit(self, mock_agent):
        """Test: run_async terminates when token limit is reached"""
        mock_agent.max_tokens = 100
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = AsyncMock(return_value=True)
        mock_agent.llm.get_token_usage = MagicMock(
            return_value={"prompt_tokens": 60, "completion_tokens": 60}
        )

        result = await mock_agent.run_async("test input")

        assert result.terminated_by_limit is True
        assert result.limit_type == "token_limit"
        assert result.total_tokens >= 100
        assert "token 限制" in result.alert_message

    @pytest.mark.asyncio
    async def test_run_async_terminates_by_cost_limit(self, mock_agent):
        """Test: run_async terminates when cost limit is reached"""
        mock_agent.max_cost = 0.5
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = AsyncMock(return_value=True)
        mock_agent.llm.get_token_usage = MagicMock(
            return_value={"prompt_tokens": 10, "completion_tokens": 10}
        )
        mock_agent.llm.get_cost = MagicMock(return_value=0.6)

        result = await mock_agent.run_async("test input")

        assert result.terminated_by_limit is True
        assert result.limit_type == "cost_limit"
        assert result.total_cost >= 0.5
        assert "成本限制" in result.alert_message

    @pytest.mark.asyncio
    async def test_run_async_terminates_by_max_iterations(self, mock_agent):
        """Test: run_async terminates when max iterations is reached"""
        mock_agent.max_iterations = 3
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = AsyncMock(return_value=True)

        result = await mock_agent.run_async("test input")

        assert result.terminated_by_limit is True
        assert result.limit_type == "max_iterations"
        assert result.iterations == 3
        assert "最大迭代次数限制" in result.alert_message

    @pytest.mark.asyncio
    async def test_run_async_completes_on_should_continue_false(self, mock_agent):
        """Test: run_async completes when should_continue returns False"""
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(
            return_value={"action_type": "continue", "response": "Done"}
        )
        mock_agent.llm.should_continue = AsyncMock(return_value=False)

        result = await mock_agent.run_async("test input")

        assert result.completed is True
        assert result.final_response == "Done"
        assert result.terminated_by_limit is False

    @pytest.mark.asyncio
    async def test_run_async_emits_tool_call_for_tool_call_action(self, mock_agent):
        """Test: run_async emits tool_call when action_type is 'tool_call'"""
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(
            side_effect=[
                {
                    "action_type": "tool_call",
                    "tool_name": "calculator",
                    "tool_id": "calc_1",
                    "arguments": {"a": 1, "b": 2},
                },
                {"action_type": "respond", "response": "Done"},
            ]
        )
        mock_agent.llm.should_continue = AsyncMock(return_value=True)

        result = await mock_agent.run_async("test input")

        mock_agent.emitter.emit_tool_call.assert_called_once_with(
            tool_name="calculator", tool_id="calc_1", arguments={"a": 1, "b": 2}
        )
        assert result.completed is True

    @pytest.mark.asyncio
    async def test_run_async_records_decision_for_create_node_action(self, mock_agent):
        """Test: run_async records decision for 'create_node' action"""
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(
            side_effect=[
                {"action_type": "create_node", "node_type": "python"},
                {"action_type": "respond", "response": "Done"},
            ]
        )
        mock_agent.llm.should_continue = AsyncMock(return_value=True)

        await mock_agent.run_async("test input")

        mock_agent._stage_decision_record.assert_called()
        mock_agent.event_bus.publish.assert_called()  # Decision published

    @pytest.mark.asyncio
    async def test_run_async_records_decision_for_execute_workflow_action(self, mock_agent):
        """Test: run_async records decision for 'execute_workflow' action"""
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(
            side_effect=[
                {"action_type": "execute_workflow", "workflow_id": "wf_1"},
                {"action_type": "respond", "response": "Done"},
            ]
        )
        mock_agent.llm.should_continue = AsyncMock(return_value=True)

        await mock_agent.run_async("test input")

        mock_agent._stage_decision_record.assert_called()
        mock_agent.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_async_accumulates_token_usage(self, mock_agent):
        """Test: run_async correctly accumulates token usage"""
        mock_agent.max_iterations = 2
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = AsyncMock(return_value=True)
        mock_agent.llm.get_token_usage = MagicMock(
            return_value={"prompt_tokens": 10, "completion_tokens": 20}
        )

        result = await mock_agent.run_async("test input")

        assert result.total_tokens == 60  # 2 iterations * 30 tokens
        assert mock_agent._stage_token_usage.call_count == 2

    @pytest.mark.asyncio
    async def test_run_async_accumulates_cost(self, mock_agent):
        """Test: run_async correctly accumulates cost"""
        mock_agent.max_iterations = 2
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = AsyncMock(return_value=True)
        mock_agent.llm.get_token_usage = MagicMock(return_value=10)
        mock_agent.llm.get_cost = MagicMock(return_value=0.01)

        result = await mock_agent.run_async("test input")

        assert result.total_cost == 0.02  # 2 iterations * $0.01

    @pytest.mark.asyncio
    async def test_run_async_emits_thinking_step(self, mock_agent):
        """Test: run_async emits thinking step via emitter"""
        mock_agent.llm.think = AsyncMock(return_value="I am thinking about this")
        mock_agent.llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "Done"}
        )

        await mock_agent.run_async("test input")

        mock_agent.emitter.emit_thinking.assert_called_once_with("I am thinking about this")

    @pytest.mark.asyncio
    async def test_run_async_emits_final_response_and_completes(self, mock_agent):
        """Test: run_async emits final response and completes emitter"""
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "Final answer"}
        )

        await mock_agent.run_async("test input")

        mock_agent.emitter.emit_final_response.assert_called_once_with("Final answer")
        mock_agent.emitter.complete.assert_called()

    @pytest.mark.asyncio
    async def test_run_async_emits_error_on_llm_think_exception(self, mock_agent):
        """Test: run_async emits error when llm.think raises exception"""
        mock_agent.llm.think = AsyncMock(side_effect=RuntimeError("LLM error"))

        with pytest.raises(RuntimeError, match="LLM error"):
            await mock_agent.run_async("test input")

        mock_agent.emitter.emit_error.assert_called_once_with(
            "LLM error", error_code="LLM_THINK_ERROR"
        )
        mock_agent.emitter.complete.assert_called()

    @pytest.mark.asyncio
    async def test_run_async_flushes_staged_state_each_iteration(self, mock_agent):
        """Test: run_async flushes staged state at end of each iteration"""
        mock_agent.max_iterations = 2
        mock_agent.llm.think = AsyncMock(return_value="thinking")
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = AsyncMock(return_value=True)

        await mock_agent.run_async("test input")

        # Should flush after each iteration + final flush
        assert mock_agent._flush_staged_state.call_count == 3  # 2 iterations + final


# =============================================================================
# TestMakeDecision - Decision with Pydantic validation (4 tests)
# =============================================================================


class TestMakeDecision:
    """Test make_decision with Pydantic validation"""

    def test_make_decision_creates_decision_with_valid_action(self, mock_agent, models_module):
        """Test: make_decision creates Decision for valid action_type"""
        mock_agent.llm.decide_action = AsyncMock(
            return_value={"action_type": "continue", "thought": "Continuing reasoning"}
        )

        decision = mock_agent.make_decision("test hint")

        assert decision.type == models_module.DecisionType.CONTINUE
        assert decision.payload["action_type"] == "continue"
        assert decision.payload["thought"] == "Continuing reasoning"
        mock_agent.session_context.add_decision.assert_called_once()

    def test_make_decision_records_to_session_context(self, mock_agent):
        """Test: make_decision records decision to session context"""
        mock_agent.llm.decide_action = AsyncMock(
            return_value={
                "action_type": "create_node",
                "node_type": "PYTHON",
                "node_name": "test_node",
                "config": {"script": "print('hello')"},
            }
        )

        mock_agent.make_decision("create a node")

        call_args = mock_agent.session_context.add_decision.call_args[0][0]
        assert call_args["type"] == "create_node"
        assert "timestamp" in call_args
        assert "id" in call_args

    def test_make_decision_handles_validation_error(self, mock_agent, monkeypatch):
        """Test: make_decision handles Pydantic ValidationError"""
        from pydantic import ValidationError

        mock_agent.llm.decide_action = AsyncMock(
            return_value={"action_type": "create_node"}  # Missing required fields
        )

        # Mock validate_and_enhance_decision to raise ValidationError
        def mock_validate(*args, **kwargs):
            raise ValidationError.from_exception_data(
                "test", [{"type": "missing", "loc": ("node_type",), "msg": "field required"}]
            )

        import src.domain.agents.conversation_agent_enhanced as enhanced_module

        monkeypatch.setattr(enhanced_module, "validate_and_enhance_decision", mock_validate)

        with pytest.raises(ValidationError):
            mock_agent.make_decision("create node")

        # Should record validation failure
        call_args = mock_agent.session_context.add_decision.call_args[0][0]
        assert call_args["type"] == "validation_failed"

    def test_make_decision_manages_metadata(self, mock_agent, monkeypatch):
        """Test: make_decision stores metadata in _decision_metadata"""
        mock_agent.llm.decide_action = AsyncMock(return_value={"action_type": "continue"})

        # Mock validate_and_enhance_decision to return metadata
        def mock_validate(*args, **kwargs):
            from unittest.mock import MagicMock

            payload = MagicMock()
            payload.model_dump = MagicMock(return_value={"action_type": "continue"})
            metadata = {"confidence": 0.95, "reasoning": "high confidence"}
            return payload, metadata

        import src.domain.agents.conversation_agent_enhanced as enhanced_module

        monkeypatch.setattr(enhanced_module, "validate_and_enhance_decision", mock_validate)

        mock_agent.make_decision("test")

        assert len(mock_agent._decision_metadata) == 1
        assert mock_agent._decision_metadata[0]["action_type"] == "continue"
        assert mock_agent._decision_metadata[0]["metadata"]["confidence"] == 0.95


# =============================================================================
# TestRecordDecision - Sync/Async recording (2 tests)
# =============================================================================


class TestRecordDecision:
    """Test _record_decision sync/async variants"""

    def test_record_decision_adds_to_session_context(self, mock_agent, models_module):
        """Test: _record_decision adds decision to session context"""
        decision = models_module.Decision(
            type=models_module.DecisionType.CONTINUE, payload={"action_type": "continue"}
        )

        result = mock_agent._record_decision(decision)

        assert result is decision
        mock_agent.session_context.add_decision.assert_called_once()
        call_args = mock_agent.session_context.add_decision.call_args[0][0]
        assert call_args["id"] == decision.id
        assert call_args["type"] == "continue"

    @pytest.mark.asyncio
    async def test_record_decision_async_stages_decision_record(self, mock_agent):
        """Test: _record_decision_async uses staged mechanism"""
        action = {"action_type": "create_node", "node_type": "python"}

        decision = await mock_agent._record_decision_async(action)

        assert decision.type.value == "create_node"
        mock_agent._stage_decision_record.assert_called_once()
        call_args = mock_agent._stage_decision_record.call_args[0][0]
        assert call_args["id"] == decision.id
        assert call_args["type"] == "create_node"


# =============================================================================
# TestRunSync - Mock compatibility (4 tests)
# =============================================================================


class TestRunSync:
    """Test _run_sync mock-compatible sync loop"""

    def test_run_sync_completes_on_respond_action(self, mock_agent):
        """Test: _run_sync completes when action_type is 'respond'"""
        mock_agent.llm.think = MagicMock(return_value="thinking")
        mock_agent.llm.decide_action = MagicMock(
            return_value={"action_type": "respond", "response": "Done"}
        )

        result = mock_agent._run_sync("test input")

        assert result.completed is True
        assert result.final_response == "Done"
        assert result.iterations == 1

    def test_run_sync_respects_should_continue_false(self, mock_agent):
        """Test: _run_sync terminates when should_continue returns False"""
        mock_agent.llm.think = MagicMock(return_value="thinking")
        mock_agent.llm.decide_action = MagicMock(
            return_value={"action_type": "continue", "response": "Continuing"}
        )
        mock_agent.llm.should_continue = MagicMock(return_value=False)

        result = mock_agent._run_sync("test input")

        assert result.iterations == 1
        assert result.completed is True
        assert result.final_response == "Continuing"

    def test_run_sync_terminates_by_max_iterations(self, mock_agent):
        """Test: _run_sync terminates when max iterations reached"""
        mock_agent.max_iterations = 3
        mock_agent.llm.think = MagicMock(return_value="thinking")
        mock_agent.llm.decide_action = MagicMock(return_value={"action_type": "continue"})
        mock_agent.llm.should_continue = MagicMock(return_value=True)

        result = mock_agent._run_sync("test input")

        assert result.terminated_by_limit is True
        assert result.iterations == 3

    def test_run_sync_records_decisions_for_workflow_actions(self, mock_agent, models_module):
        """Test: _run_sync records decisions for create_node/execute_workflow"""
        mock_agent.llm.think = MagicMock(return_value="thinking")
        mock_agent.llm.decide_action = MagicMock(
            return_value={
                "action_type": "create_node",
                "node_type": "PYTHON",
                "node_name": "test_node",
                "config": {"script": "print('test')"},
            }
        )
        mock_agent.llm.should_continue = MagicMock(return_value=False)

        mock_agent._run_sync("test input")

        # Verify _record_decision was called via session_context.add_decision
        mock_agent.session_context.add_decision.assert_called()


# =============================================================================
# TestPublishDecision - EventBus publishing (1 test)
# =============================================================================


class TestPublishDecision:
    """Test publish_decision EventBus integration"""

    @pytest.mark.asyncio
    async def test_publish_decision_publishes_decision_made_event(self, mock_agent, models_module):
        """Test: publish_decision publishes DecisionMadeEvent to EventBus"""
        decision = models_module.Decision(
            type=models_module.DecisionType.CREATE_NODE,
            payload={"action_type": "create_node", "node_type": "python"},
        )

        await mock_agent.publish_decision(decision)

        mock_agent.event_bus.publish.assert_called_once()
        event = mock_agent.event_bus.publish.call_args[0][0]
        assert event.source == "conversation_agent"
        assert event.decision_type == "create_node"
        assert event.decision_id == decision.id


# =============================================================================
# TestExecuteStep - Single step execution (1 test)
# =============================================================================


class TestExecuteStep:
    """Test execute_step single ReAct step"""

    def test_execute_step_returns_react_step(self, mock_agent):
        """Test: execute_step returns ReActStep with thought and action"""
        # Note: execute_step has complex event loop handling that's hard to test in isolation
        # This test covers the basic structure only
        result = mock_agent.execute_step("test input")

        assert hasattr(result, "step_type")
        assert hasattr(result, "thought")
        assert hasattr(result, "action")
        assert mock_agent._current_input == "test input"

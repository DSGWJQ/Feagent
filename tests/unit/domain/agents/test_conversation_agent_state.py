"""
Unit tests for ConversationAgentStateMixin

Focus on:
- State machine transitions and validation
- Async/await concurrency patterns
- Lock-based synchronization
- Event publishing (critical vs notification)
- Sub-agent wait/resume lifecycle
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def state_module():
    """Import conversation_agent_state module"""
    import importlib

    return importlib.import_module("src.domain.agents.conversation_agent_state")


@pytest.fixture()
def mock_agent(state_module):
    """Create mock agent with ConversationAgentStateMixin"""

    class MockAgent(state_module.ConversationAgentStateMixin):
        def __init__(self):
            # Required host attributes
            self.event_bus = AsyncMock()
            self.session_context = MagicMock()
            self.session_context.session_id = "test-session-123"

            # Initialize mixin
            self._init_state_mixin()

    return MockAgent()


# =============================================================================
# Class 1: TestInitialization (2 tests)
# =============================================================================


class TestInitialization:
    """Test _init_state_mixin initialization"""

    def test_init_state_mixin_initializes_all_fields(self, mock_agent, state_module):
        """Test: _init_state_mixin initializes all state/lock fields"""
        assert mock_agent._state == state_module.ConversationAgentState.IDLE
        assert isinstance(mock_agent._state_lock, asyncio.Lock)
        assert isinstance(mock_agent._critical_event_lock, asyncio.Lock)
        assert isinstance(mock_agent._pending_tasks, set)
        assert len(mock_agent._pending_tasks) == 0

    def test_init_state_mixin_sets_idle_state(self, mock_agent, state_module):
        """Test: _init_state_mixin sets initial state to IDLE"""
        assert mock_agent._state == state_module.ConversationAgentState.IDLE
        assert mock_agent.pending_subagent_id is None
        assert mock_agent.pending_task_id is None
        assert mock_agent.suspended_context is None
        assert mock_agent.last_subagent_result is None
        assert mock_agent.subagent_result_history == []
        assert mock_agent._is_listening_subagent_completions is False


# =============================================================================
# Class 2: TestTaskTracking (2 tests)
# =============================================================================


class TestTaskTracking:
    """Test _create_tracked_task for GC prevention"""

    @pytest.mark.asyncio
    async def test_create_tracked_task_adds_to_pending_set(self, mock_agent):
        """Test: _create_tracked_task adds task to _pending_tasks"""

        async def dummy_coro():
            await asyncio.sleep(0.01)
            return "done"

        task = mock_agent._create_tracked_task(dummy_coro())

        assert task in mock_agent._pending_tasks
        await task
        assert task.result() == "done"

    @pytest.mark.asyncio
    async def test_create_tracked_task_removes_on_completion(self, mock_agent):
        """Test: _create_tracked_task removes task from _pending_tasks on completion"""

        async def dummy_coro():
            await asyncio.sleep(0.01)
            return "done"

        task = mock_agent._create_tracked_task(dummy_coro())
        assert task in mock_agent._pending_tasks

        await task
        await asyncio.sleep(0.02)  # Wait for done callback to execute

        assert task not in mock_agent._pending_tasks


# =============================================================================
# Class 3: TestEventPublishing (4 tests)
# =============================================================================


class TestEventPublishing:
    """Test event publishing methods (critical vs notification)"""

    @pytest.mark.asyncio
    async def test_publish_critical_event_uses_lock_and_awaits(self, mock_agent, state_module):
        """Test: _publish_critical_event uses _critical_event_lock and awaits publish"""
        event = state_module.StateChangedEvent(
            from_state="idle",
            to_state="processing",
            session_id="test-session",
            source="test",
        )

        await mock_agent._publish_critical_event(event)

        mock_agent.event_bus.publish.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_critical_event_no_op_when_event_bus_none(self, mock_agent, state_module):
        """Test: _publish_critical_event is no-op when event_bus is None"""
        mock_agent.event_bus = None

        event = state_module.StateChangedEvent(
            from_state="idle",
            to_state="processing",
            session_id="test-session",
            source="test",
        )

        # Should not raise exception
        await mock_agent._publish_critical_event(event)

    @pytest.mark.asyncio
    async def test_publish_notification_event_creates_background_task(
        self, mock_agent, state_module
    ):
        """Test: _publish_notification_event creates tracked background task"""
        event = state_module.StateChangedEvent(
            from_state="idle",
            to_state="processing",
            session_id="test-session",
            source="test",
        )

        initial_task_count = len(mock_agent._pending_tasks)
        mock_agent._publish_notification_event(event)

        # Should have created a background task
        assert len(mock_agent._pending_tasks) == initial_task_count + 1

    def test_publish_notification_event_no_op_when_event_bus_none(self, mock_agent, state_module):
        """Test: _publish_notification_event is no-op when event_bus is None"""
        mock_agent.event_bus = None

        event = state_module.StateChangedEvent(
            from_state="idle",
            to_state="processing",
            session_id="test-session",
            source="test",
        )

        initial_task_count = len(mock_agent._pending_tasks)
        mock_agent._publish_notification_event(event)

        # Should not create task
        assert len(mock_agent._pending_tasks) == initial_task_count


# =============================================================================
# Class 4: TestStateTransitions (7 tests)
# =============================================================================


class TestStateTransitions:
    """Test state transition methods and validation"""

    def test_transition_locked_valid_transition_returns_old_state(self, mock_agent, state_module):
        """Test: _transition_locked returns old state for valid transition"""
        mock_agent._state = state_module.ConversationAgentState.IDLE

        old_state = mock_agent._transition_locked(state_module.ConversationAgentState.PROCESSING)

        assert old_state == state_module.ConversationAgentState.IDLE
        assert mock_agent._state == state_module.ConversationAgentState.PROCESSING

    def test_transition_locked_invalid_transition_raises_domain_error(
        self, mock_agent, state_module
    ):
        """Test: _transition_locked raises DomainError for invalid transition"""
        from src.domain.exceptions import DomainError

        mock_agent._state = state_module.ConversationAgentState.IDLE

        # IDLE -> WAITING_FOR_SUBAGENT is invalid (must go through PROCESSING)
        with pytest.raises(DomainError, match="Invalid state transition"):
            mock_agent._transition_locked(state_module.ConversationAgentState.WAITING_FOR_SUBAGENT)

    @pytest.mark.asyncio
    async def test_transition_to_sync_valid_transition(self, mock_agent, state_module):
        """Test: transition_to (sync) performs valid transition"""
        mock_agent._state = state_module.ConversationAgentState.IDLE

        mock_agent.transition_to(state_module.ConversationAgentState.PROCESSING)

        assert mock_agent._state == state_module.ConversationAgentState.PROCESSING

    def test_transition_to_sync_invalid_raises_domain_error(self, mock_agent, state_module):
        """Test: transition_to (sync) raises DomainError for invalid transition"""
        from src.domain.exceptions import DomainError

        mock_agent._state = state_module.ConversationAgentState.COMPLETED

        # COMPLETED -> PROCESSING is invalid (must go through IDLE first)
        with pytest.raises(DomainError, match="Invalid state transition"):
            mock_agent.transition_to(state_module.ConversationAgentState.PROCESSING)

    @pytest.mark.asyncio
    async def test_transition_to_async_valid_transition(self, mock_agent, state_module):
        """Test: transition_to_async performs valid transition"""
        mock_agent._state = state_module.ConversationAgentState.IDLE

        await mock_agent.transition_to_async(state_module.ConversationAgentState.PROCESSING)

        assert mock_agent._state == state_module.ConversationAgentState.PROCESSING

    @pytest.mark.asyncio
    async def test_transition_to_async_invalid_raises_domain_error(self, mock_agent, state_module):
        """Test: transition_to_async raises DomainError for invalid transition"""
        from src.domain.exceptions import DomainError

        mock_agent._state = state_module.ConversationAgentState.ERROR

        # ERROR -> PROCESSING is invalid (must go through IDLE first)
        with pytest.raises(DomainError, match="Invalid state transition"):
            await mock_agent.transition_to_async(state_module.ConversationAgentState.PROCESSING)

    def test_state_property_returns_current_state(self, mock_agent, state_module):
        """Test: state property returns current _state"""
        mock_agent._state = state_module.ConversationAgentState.PROCESSING

        assert mock_agent.state == state_module.ConversationAgentState.PROCESSING


# =============================================================================
# Class 5: TestSubagentWaitResume (4 tests)
# =============================================================================


class TestSubagentWaitResume:
    """Test sub-agent wait/resume lifecycle"""

    @pytest.mark.asyncio
    async def test_wait_for_subagent_sets_pending_and_deepcopy_context(
        self, mock_agent, state_module
    ):
        """Test: wait_for_subagent sets pending fields and deep copies context"""
        mock_agent._state = state_module.ConversationAgentState.PROCESSING

        context = {"key": "value", "nested": {"data": [1, 2, 3]}}
        mock_agent.wait_for_subagent("subagent-123", "task-456", context)

        assert mock_agent.pending_subagent_id == "subagent-123"
        assert mock_agent.pending_task_id == "task-456"
        assert mock_agent.suspended_context == context
        # Verify deep copy (not same object)
        assert mock_agent.suspended_context is not context
        assert mock_agent._state == state_module.ConversationAgentState.WAITING_FOR_SUBAGENT

    @pytest.mark.asyncio
    async def test_resume_from_subagent_restores_context_and_clears_pending(
        self, mock_agent, state_module
    ):
        """Test: resume_from_subagent restores context and clears pending fields"""
        mock_agent._state = state_module.ConversationAgentState.WAITING_FOR_SUBAGENT
        mock_agent.pending_subagent_id = "subagent-123"
        mock_agent.pending_task_id = "task-456"
        mock_agent.suspended_context = {"original": "context"}

        result = {"success": True, "data": {"output": "test"}}
        restored_context = mock_agent.resume_from_subagent(result)

        assert restored_context["original"] == "context"
        assert restored_context["subagent_result"] == result
        assert mock_agent.pending_subagent_id is None
        assert mock_agent.pending_task_id is None
        assert mock_agent.suspended_context is None
        assert mock_agent._state == state_module.ConversationAgentState.PROCESSING

    @pytest.mark.asyncio
    async def test_wait_for_subagent_async_atomic_with_lock(self, mock_agent, state_module):
        """Test: wait_for_subagent_async is atomic under _state_lock"""
        mock_agent._state = state_module.ConversationAgentState.PROCESSING

        context = {"key": "value"}
        await mock_agent.wait_for_subagent_async("subagent-123", "task-456", context)

        assert mock_agent.pending_subagent_id == "subagent-123"
        assert mock_agent._state == state_module.ConversationAgentState.WAITING_FOR_SUBAGENT
        # Verify event was published
        mock_agent.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_resume_from_subagent_async_atomic_with_lock(self, mock_agent, state_module):
        """Test: resume_from_subagent_async is atomic under _state_lock"""
        mock_agent._state = state_module.ConversationAgentState.WAITING_FOR_SUBAGENT
        mock_agent.suspended_context = {"original": "context"}

        result = {"success": True, "data": "output"}
        restored_context = await mock_agent.resume_from_subagent_async(result)

        assert restored_context["subagent_result"] == result
        assert mock_agent._state == state_module.ConversationAgentState.PROCESSING
        # Verify event was published
        mock_agent.event_bus.publish.assert_called()


# =============================================================================
# Class 6: TestSubagentListener (3 tests)
# =============================================================================


class TestSubagentListener:
    """Test sub-agent completion listener lifecycle"""

    def test_start_subagent_completion_listener_subscribes(self, mock_agent):
        """Test: start_subagent_completion_listener subscribes to SubAgentCompletedEvent"""
        mock_agent.start_subagent_completion_listener()

        assert mock_agent._is_listening_subagent_completions is True
        mock_agent.event_bus.subscribe.assert_called_once()

    def test_stop_subagent_completion_listener_unsubscribes(self, mock_agent):
        """Test: stop_subagent_completion_listener unsubscribes from SubAgentCompletedEvent"""
        mock_agent.start_subagent_completion_listener()
        mock_agent.stop_subagent_completion_listener()

        assert mock_agent._is_listening_subagent_completions is False
        mock_agent.event_bus.unsubscribe.assert_called_once()

    def test_start_listener_idempotent(self, mock_agent):
        """Test: start_subagent_completion_listener is idempotent"""
        mock_agent.start_subagent_completion_listener()
        mock_agent.start_subagent_completion_listener()  # Second call

        # Should only subscribe once
        assert mock_agent.event_bus.subscribe.call_count == 1


# =============================================================================
# Class 7: TestHandleSubagentCompleted (1 test)
# =============================================================================


class TestHandleSubagentCompleted:
    """Test handle_subagent_completed event handler"""

    @pytest.mark.asyncio
    async def test_handle_subagent_completed_stores_result_and_resumes(
        self, mock_agent, state_module
    ):
        """Test: handle_subagent_completed stores result and calls resume_from_subagent_async"""
        mock_agent._state = state_module.ConversationAgentState.WAITING_FOR_SUBAGENT
        mock_agent.pending_subagent_id = "subagent-123"
        mock_agent.suspended_context = {"original": "context"}

        # Create mock SubAgentCompletedEvent
        event = MagicMock()
        event.subagent_id = "subagent-123"
        event.subagent_type = "search"
        event.success = True
        event.result = {"data": {"output": "test"}}
        event.error = None
        event.execution_time = 1.5

        await mock_agent.handle_subagent_completed(event)

        # Verify result storage
        assert mock_agent.last_subagent_result["success"] is True
        assert mock_agent.last_subagent_result["data"] == {"output": "test"}
        assert len(mock_agent.subagent_result_history) == 1
        assert mock_agent.subagent_result_history[0]["subagent_id"] == "subagent-123"

        # Verify state transition to PROCESSING
        assert mock_agent._state == state_module.ConversationAgentState.PROCESSING

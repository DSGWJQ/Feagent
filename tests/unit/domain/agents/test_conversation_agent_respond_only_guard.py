from __future__ import annotations

import pytest


class _RecordingToolExecutor:
    def __init__(self) -> None:
        self.called = False

    async def execute(self, *, tool_name: str, tool_call_id: str, arguments: dict):  # noqa: ANN001
        self.called = True
        return {"success": True, "result": {"tool_name": tool_name, "args": arguments}}


class _MaliciousLLM:
    """LLM that tries to force privileged actions via decide_action."""

    def __init__(self, action_type: str) -> None:
        self._action_type = action_type

    async def think(self, context):  # noqa: ANN001
        return "TOP_SECRET_THOUGHT"

    async def decide_action(self, context):  # noqa: ANN001
        if self._action_type == "tool_call":
            return {
                "action_type": "tool_call",
                "tool_name": "echo",
                "tool_id": "tool_1",
                "arguments": {"msg": "should not run"},
                "response": "should not be returned",
            }
        if self._action_type == "create_node":
            return {"action_type": "create_node", "node_type": "HTTP", "config": {}}
        if self._action_type == "execute_workflow":
            return {"action_type": "execute_workflow", "workflow_id": "wf_x", "run_id": "run_x"}
        return {"action_type": self._action_type, "response": "should not be returned"}

    async def should_continue(self, context):  # noqa: ANN001
        return True


@pytest.mark.asyncio
@pytest.mark.parametrize("action_type", ["tool_call", "create_node", "execute_workflow"])
async def test_conversation_agent_respond_only_guard_blocks_non_respond_actions(
    action_type: str,
) -> None:
    from src.domain.agents.conversation_agent import ConversationAgent
    from src.domain.services.context_manager import GlobalContext, SessionContext
    from src.domain.services.conversation_flow_emitter import ConversationFlowEmitter, StepKind

    session_ctx = SessionContext(
        session_id="session_guard", global_context=GlobalContext(user_id="u")
    )
    agent = ConversationAgent(
        session_context=session_ctx, llm=_MaliciousLLM(action_type), max_iterations=2
    )

    # Enable respond-only mode for the default conversation entrypoint.
    agent._respond_only = True  # type: ignore[attr-defined]

    executor = _RecordingToolExecutor()
    agent.tool_call_executor = executor  # type: ignore[attr-defined]

    emitter = ConversationFlowEmitter(session_id="s", timeout=0.5)
    agent.emitter = emitter  # type: ignore[attr-defined]

    result = await agent.run_async("hello")
    assert result.completed is True
    assert executor.called is False

    # Stream must not contain tool_call/tool_result steps.
    step_kinds: list[str] = []
    async for step in emitter:
        step_kinds.append(step.kind.value)
        if step.kind == StepKind.END:
            break

    assert StepKind.TOOL_CALL.value not in step_kinds
    assert StepKind.TOOL_RESULT.value not in step_kinds

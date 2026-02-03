"""Factory for constructing ConversationAgent outside the Interface layer."""

from __future__ import annotations

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_config import (
    ConversationAgentConfig,
    LLMConfig,
    ReActConfig,
    StreamingConfig,
    WorkflowConfig,
)
from src.domain.entities.session_context import GlobalContext, SessionContext
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.model_metadata import ModelMetadataPort
from src.domain.services.event_bus import EventBus


def create_conversation_agent(
    *,
    event_bus: EventBus,
    model_metadata_port: ModelMetadataPort,
    coordinator: object | None = None,
    llm_port: LLMPort | None = None,
) -> ConversationAgent:
    from src.application.services.clarifier_conversation_llm import ClarifierConversationLLM

    llm = ClarifierConversationLLM(llm_port=llm_port)
    session_context = SessionContext(
        session_id="bootstrap",
        global_context=GlobalContext(user_id="anonymous"),
    )

    config = ConversationAgentConfig(
        session_context=session_context,
        llm=LLMConfig(llm=llm, model="clarifier"),
        react=ReActConfig(max_iterations=1, enable_reasoning_trace=False),
        workflow=WorkflowConfig(
            coordinator=coordinator,
            enable_subagent_spawn=False,
            enable_feedback_listening=False,
            enable_progress_events=False,
        ),
        streaming=StreamingConfig(enable_save_request_channel=True),
        event_bus=event_bus,
        model_metadata_port=model_metadata_port,
    )
    agent = ConversationAgent(config=config)
    # Contract (respond-only): conversation entrypoint must never execute tools or workflows.
    agent._respond_only = True  # type: ignore[attr-defined]

    # WFCORE-080: Inject a real, offline-safe tool executor (DIP).
    from typing import Any, cast

    from src.application.services.tool_call_executor import ToolEngineToolCallExecutor

    cast(Any, agent).tool_call_executor = ToolEngineToolCallExecutor(
        conversation_id_provider=lambda a=agent: getattr(
            getattr(a, "session_context", None), "session_id", None
        ),
        user_message_provider=lambda a=agent: getattr(a, "_current_input", None),
        workflow_id_provider=lambda a=agent: getattr(a, "_workflow_id", None),
        run_id_provider=lambda a=agent: getattr(a, "_run_id", None),
    )

    # WFCORE-090: Listen for plan/execute feedback events to enable replanning loops.
    try:
        cast(Any, agent).start_feedback_listening()
    except Exception:
        pass
    return agent

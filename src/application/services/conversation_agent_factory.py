"""Factory for constructing ConversationAgent outside the Interface layer."""

from __future__ import annotations

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_config import (
    ConversationAgentConfig,
    LLMConfig,
    StreamingConfig,
    WorkflowConfig,
)
from src.domain.entities.session_context import GlobalContext, SessionContext
from src.domain.ports.model_metadata import ModelMetadataPort
from src.domain.services.event_bus import EventBus


def create_conversation_agent(
    *,
    event_bus: EventBus,
    model_metadata_port: ModelMetadataPort,
    coordinator: object | None = None,
) -> ConversationAgent:
    from src.application.services.fallback_conversation_agent_llm import (
        FallbackConversationAgentLLM,
    )

    llm = FallbackConversationAgentLLM()
    session_context = SessionContext(
        session_id="bootstrap",
        global_context=GlobalContext(user_id="anonymous"),
    )

    config = ConversationAgentConfig(
        session_context=session_context,
        llm=LLMConfig(llm=llm, model="fallback"),
        workflow=WorkflowConfig(coordinator=coordinator),
        streaming=StreamingConfig(enable_save_request_channel=True),
        event_bus=event_bus,
        model_metadata_port=model_metadata_port,
    )
    return ConversationAgent(config=config)

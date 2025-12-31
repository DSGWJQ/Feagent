"""Factory for constructing ConversationAgent outside the Interface layer."""

from __future__ import annotations

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_config import ConversationAgentConfig, StreamingConfig
from src.domain.ports.model_metadata import ModelMetadataPort
from src.domain.services.event_bus import EventBus


def create_conversation_agent(
    *,
    event_bus: EventBus,
    model_metadata_port: ModelMetadataPort,
) -> ConversationAgent:
    config = ConversationAgentConfig(
        streaming=StreamingConfig(enable_save_request_channel=True),
        event_bus=event_bus,
        model_metadata_port=model_metadata_port,
    )
    return ConversationAgent(config=config)

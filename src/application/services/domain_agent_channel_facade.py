"""Re-export domain agent_channel types for Interface without importing src.domain.agents directly."""

from __future__ import annotations

from src.domain.agents.agent_channel import (
    AgentChannelBridge,
    AgentMessage,
    AgentMessageHandler,
    AgentWebSocketChannel,
)

__all__ = [
    "AgentChannelBridge",
    "AgentMessage",
    "AgentMessageHandler",
    "AgentWebSocketChannel",
]

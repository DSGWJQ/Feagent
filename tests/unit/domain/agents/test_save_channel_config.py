"""Test for enable_save_request_channel config application"""

from unittest.mock import MagicMock

import pytest

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_config import (
    ConversationAgentConfig,
    LLMConfig,
    StreamingConfig,
)
from src.domain.services.context_manager import SessionContext


@pytest.mark.asyncio
async def test_enable_save_request_channel_from_config():
    """Verify that StreamingConfig.enable_save_request_channel is applied to agent"""
    # Create a mock session context
    session_context = MagicMock(spec=SessionContext)
    session_context.session_id = "test-session-123"

    # Create a mock LLM
    mock_llm = MagicMock()

    # Create config with save request channel enabled
    streaming_config = StreamingConfig(enable_save_request_channel=True)
    config = ConversationAgentConfig(
        session_context=session_context,
        llm=LLMConfig(llm=mock_llm),
        streaming=streaming_config,
    )

    # Initialize agent with config
    agent = ConversationAgent(config=config)

    # Verify that save request channel is enabled
    assert agent.is_save_request_channel_enabled() is True


@pytest.mark.asyncio
async def test_disable_save_request_channel_from_config():
    """Verify that StreamingConfig.enable_save_request_channel=False is respected"""
    # Create a mock session context
    session_context = MagicMock(spec=SessionContext)
    session_context.session_id = "test-session-456"

    # Create a mock LLM
    mock_llm = MagicMock()

    # Create config with save request channel disabled (default)
    streaming_config = StreamingConfig(enable_save_request_channel=False)
    config = ConversationAgentConfig(
        session_context=session_context,
        llm=LLMConfig(llm=mock_llm),
        streaming=streaming_config,
    )

    # Initialize agent with config
    agent = ConversationAgent(config=config)

    # Verify that save request channel is disabled
    assert agent.is_save_request_channel_enabled() is False

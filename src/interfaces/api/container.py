"""API Container (composition root state holder).

This module only defines types/structure for objects created in the real
composition root (`src/interfaces/api/main.py`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.chat_message_repository import ChatMessageRepository
from src.domain.ports.llm_provider_repository import LLMProviderRepository
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.task_repository import TaskRepository
from src.domain.ports.tool_repository import ToolRepository
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.workflow_repository import WorkflowRepository


@dataclass(frozen=True, slots=True)
class ApiContainer:
    """Typed container attached to `app.state.container`."""

    executor_registry: NodeExecutorRegistry

    user_repository: Callable[[Session], UserRepository]
    agent_repository: Callable[[Session], AgentRepository]
    task_repository: Callable[[Session], TaskRepository]
    workflow_repository: Callable[[Session], WorkflowRepository]
    chat_message_repository: Callable[[Session], ChatMessageRepository]
    llm_provider_repository: Callable[[Session], LLMProviderRepository]
    tool_repository: Callable[[Session], ToolRepository]

    # Adapters without a corresponding Domain Port yet (keep typing loose).
    run_repository: Callable[[Session], Any]
    scheduled_workflow_repository: Callable[[Session], Any]

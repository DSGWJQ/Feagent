"""LangGraphWorkflowExecutorAdapter

This module exists to satisfy the wiring contract used by
`src/interfaces/api/services/workflow_executor_adapter.py`.

The implementation is intentionally minimal for now: the repository currently
ships a LangGraph workflow executor implementation, but the higher-level
Application facade may choose whether to use it.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository


class LangGraphWorkflowExecutorAdapter:
    """Infrastructure adapter placeholder for LangGraph workflow execution."""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowRepository,
        executor_registry: NodeExecutorRegistry | None = None,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._executor_registry = executor_registry

    async def execute(self, *, workflow_id: str, input_data: Any = None) -> dict[str, Any]:
        raise NotImplementedError(
            "LangGraphWorkflowExecutorAdapter.execute is not wired in this build."
        )

    async def execute_streaming(
        self, *, workflow_id: str, input_data: Any = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise NotImplementedError(
            "LangGraphWorkflowExecutorAdapter.execute_streaming is not wired in this build."
        )

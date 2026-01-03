"""LangGraphWorkflowExecutorAdapter (disabled).

WF-050 decision: workflow execution uses the Domain `WorkflowEngine` kernel.
LangGraph remains available for other agent/task execution paths, but workflow
execution must not route into a NotImplemented placeholder.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from src.domain.exceptions import DomainError
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
        raise DomainError("feature_disabled: langgraph workflow executor is not enabled")

    async def execute_streaming(
        self, *, workflow_id: str, input_data: Any = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise DomainError("feature_disabled: langgraph workflow executor is not enabled")

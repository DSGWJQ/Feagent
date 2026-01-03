"""LangGraphWorkflowExecutorAdapter (disabled).

WF-050 decision: workflow execution uses the Domain `WorkflowEngine` kernel.
LangGraph remains available for other agent/task execution paths, but workflow
execution must not route into a NotImplemented placeholder.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from src.config import settings
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository
from src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor import execute_workflow


class LangGraphWorkflowExecutorAdapter:
    """Infrastructure adapter for LangGraph workflow execution.

    注意：该路径默认关闭（通过 settings.enable_langgraph_workflow_executor 控制），
    仅用于灰度/实验；关闭时必须可一键回滚到 legacy workflow engine。
    """

    def __init__(
        self,
        *,
        workflow_repository: WorkflowRepository,
        executor_registry: NodeExecutorRegistry | None = None,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._executor_registry = executor_registry

    async def execute(self, *, workflow_id: str, input_data: Any = None) -> dict[str, Any]:
        if not settings.enable_langgraph_workflow_executor:
            raise DomainError("feature_disabled: langgraph workflow executor is not enabled")

        workflow = self._workflow_repository.get_by_id(workflow_id)
        initial_input = (
            input_data
            if isinstance(input_data, dict) or input_data is None
            else {"input": input_data}
        )
        final_state = await asyncio.to_thread(
            execute_workflow,
            workflow,
            initial_input=initial_input,
            executor_registry=self._executor_registry,
        )

        return {
            "execution_log": [],
            "final_result": final_state.get("results", final_state),
            "executor_id": "langgraph_workflow_v1",
        }

    async def execute_streaming(
        self, *, workflow_id: str, input_data: Any = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not settings.enable_langgraph_workflow_executor:
            raise DomainError("feature_disabled: langgraph workflow executor is not enabled")

        yield {
            "type": "workflow_start",
            "workflow_id": workflow_id,
            "executor_id": "langgraph_workflow_v1",
        }

        try:
            workflow = self._workflow_repository.get_by_id(workflow_id)
            initial_input = (
                input_data
                if isinstance(input_data, dict) or input_data is None
                else {"input": input_data}
            )
            final_state = await asyncio.to_thread(
                execute_workflow,
                workflow,
                initial_input=initial_input,
                executor_registry=self._executor_registry,
            )
            yield {
                "type": "workflow_complete",
                "workflow_id": workflow_id,
                "result": final_state.get("results", final_state),
                "execution_log": [],
                "executor_id": "langgraph_workflow_v1",
            }
        except Exception as exc:
            yield {
                "type": "workflow_error",
                "workflow_id": workflow_id,
                "error": str(exc),
                "executor_id": "langgraph_workflow_v1",
            }

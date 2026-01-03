"""LangGraphWorkflowExecutorAdapter - LangGraph 驱动的 workflow 执行适配器（可回滚）

目标（WF-040）：
- 当 feature flag 启用时，workflow 执行走 LangGraph；关闭时由上层回滚到 legacy DAG engine
- 对外事件契约保持与 legacy 执行一致（node_* + workflow_*）
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from src.config import settings
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository
from src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor import (
    execute_workflow_async,
)


class LangGraphWorkflowExecutorAdapter:
    """Infrastructure adapter for LangGraph workflow execution.

    注意：该路径可通过 settings.enable_langgraph_workflow_executor 控制。
    关闭时必须可一键回滚到 legacy workflow engine。
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
        final_result, execution_log = await execute_workflow_async(
            workflow,
            initial_input=input_data,
            executor_registry=self._executor_registry,
        )

        return {
            "execution_log": execution_log,
            "final_result": final_result,
        }

    async def execute_streaming(
        self, *, workflow_id: str, input_data: Any = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not settings.enable_langgraph_workflow_executor:
            raise DomainError("feature_disabled: langgraph workflow executor is not enabled")

        events: list[dict[str, Any]] = []

        try:
            workflow = self._workflow_repository.get_by_id(workflow_id)

            def _on_event(event_type: str, data: dict[str, Any]) -> None:
                events.append({"type": event_type, **data})

            final_result, execution_log = await execute_workflow_async(
                workflow,
                initial_input=input_data,
                executor_registry=self._executor_registry,
                event_callback=_on_event,
            )
        except DomainError as exc:
            for event in events:
                yield event
            yield {"type": "workflow_error", "error": str(exc)}
            return
        except Exception as exc:
            for event in events:
                yield event
            yield {"type": "workflow_error", "error": str(exc)}
            return

        for event in events:
            yield event
        yield {
            "type": "workflow_complete",
            "result": final_result,
            "execution_log": execution_log,
        }

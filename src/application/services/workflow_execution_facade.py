"""WorkflowExecutionFacade - workflow 执行门面

当前仓库中 `src/interfaces/api/services/workflow_executor_adapter.py` 需要一个稳定的
Application 层入口来执行 workflow（非流式/流式），以便在调度器/后台任务等场景复用。

KISS：该 Facade 目前仅作为 `ExecuteWorkflowUseCase` 的轻量包装，避免接口层直接依赖
Use Case 的构造细节；可在后续迭代中再引入更复杂的策略（例如 LangGraph executor）。
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from src.application.use_cases.execute_workflow import (
    WORKFLOW_EXECUTION_KERNEL_ID,
    ExecuteWorkflowInput,
    ExecuteWorkflowUseCase,
)
from src.config import settings
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _audit_langgraph_rollback_once() -> None:
    logger.warning(
        "langgraph_workflow_executor_rollback_active",
        extra={
            "audit_at_ms": int(time.time() * 1000),
            "actor": settings.langgraph_workflow_executor_rollback_actor or "unknown",
            "scope": settings.langgraph_workflow_executor_rollback_scope or "global",
            "reason": settings.langgraph_workflow_executor_rollback_reason or "",
            "env": settings.env,
        },
    )


class WorkflowExecutionFacade:
    """Workflow 执行门面（Application 层）。"""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowRepository,
        executor_registry: NodeExecutorRegistry | None = None,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._executor_registry = executor_registry

    async def execute(self, *, workflow_id: str, input_data: Any = None) -> dict[str, Any]:
        if settings.enable_langgraph_workflow_executor:
            from src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor_adapter import (
                LangGraphWorkflowExecutorAdapter,
            )

            adapter = LangGraphWorkflowExecutorAdapter(
                workflow_repository=self._workflow_repository,
                executor_registry=self._executor_registry,
            )
            result = await adapter.execute(workflow_id=workflow_id, input_data=input_data)
            result["executor_id"] = WORKFLOW_EXECUTION_KERNEL_ID
            return result

        _audit_langgraph_rollback_once()
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=self._workflow_repository,
            executor_registry=self._executor_registry,
        )
        return await use_case.execute(
            ExecuteWorkflowInput(workflow_id=workflow_id, initial_input=input_data)
        )

    async def execute_streaming(
        self, *, workflow_id: str, input_data: Any = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        if settings.enable_langgraph_workflow_executor:
            from src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor_adapter import (
                LangGraphWorkflowExecutorAdapter,
            )

            adapter = LangGraphWorkflowExecutorAdapter(
                workflow_repository=self._workflow_repository,
                executor_registry=self._executor_registry,
            )
            async for event in adapter.execute_streaming(
                workflow_id=workflow_id,
                input_data=input_data,
            ):
                yield {
                    **event,
                    "executor_id": event.get("executor_id", WORKFLOW_EXECUTION_KERNEL_ID),
                }
            return

        _audit_langgraph_rollback_once()
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=self._workflow_repository,
            executor_registry=self._executor_registry,
        )
        async for event in use_case.execute_streaming(
            ExecuteWorkflowInput(workflow_id=workflow_id, initial_input=input_data)
        ):
            yield event

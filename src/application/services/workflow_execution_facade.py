"""WorkflowExecutionFacade - workflow 执行门面

当前仓库中 `src/interfaces/api/services/workflow_executor_adapter.py` 需要一个稳定的
Application 层入口来执行 workflow（非流式/流式），以便在调度器/后台任务等场景复用。

KISS：该 Facade 目前仅作为 `ExecuteWorkflowUseCase` 的轻量包装，避免接口层直接依赖
Use Case 的构造细节。执行语义的事实源必须保持单一（避免引入第二套执行引擎）。
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator
from typing import Any

from src.application.use_cases.execute_workflow import (
    ExecuteWorkflowInput,
    ExecuteWorkflowUseCase,
)
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.event_bus import EventBus


def _supports_kwarg(callable_obj: Any, name: str) -> bool:
    """Best-effort check for whether a callable accepts a given keyword argument.

    Why:
    - Some unit tests patch ExecuteWorkflowUseCase with a simplified fake that doesn't accept
      newer keyword-only args (e.g. correlation_id).
    - We keep the facade tolerant and backward-compatible while still passing through the
      richer contract for the real use case implementation.
    """

    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        return False

    parameters = signature.parameters
    if name in parameters:
        return True

    # Accepts **kwargs
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())


class WorkflowExecutionFacade:
    """Workflow 执行门面（Application 层）。"""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowRepository,
        executor_registry: NodeExecutorRegistry | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._executor_registry = executor_registry
        self._event_bus = event_bus

    async def execute(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
    ) -> dict[str, Any]:
        uc_kwargs: dict[str, Any] = {
            "workflow_repository": self._workflow_repository,
            "executor_registry": self._executor_registry,
        }
        if self._event_bus is not None:
            uc_kwargs["event_bus"] = self._event_bus
        use_case = ExecuteWorkflowUseCase(**uc_kwargs)
        execute_input = ExecuteWorkflowInput(workflow_id=workflow_id, initial_input=input_data)
        if _supports_kwarg(use_case.execute, "correlation_id"):
            return await use_case.execute(execute_input, correlation_id=correlation_id)
        return await use_case.execute(execute_input)

    async def execute_streaming(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        uc_kwargs: dict[str, Any] = {
            "workflow_repository": self._workflow_repository,
            "executor_registry": self._executor_registry,
        }
        if self._event_bus is not None:
            uc_kwargs["event_bus"] = self._event_bus
        use_case = ExecuteWorkflowUseCase(**uc_kwargs)
        execute_input = ExecuteWorkflowInput(workflow_id=workflow_id, initial_input=input_data)
        if _supports_kwarg(use_case.execute_streaming, "correlation_id"):
            async for event in use_case.execute_streaming(
                execute_input, correlation_id=correlation_id
            ):
                yield event
        else:
            async for event in use_case.execute_streaming(execute_input):
                yield event

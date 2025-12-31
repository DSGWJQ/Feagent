"""WorkflowExecutionFacade - workflow 执行门面

当前仓库中 `src/interfaces/api/services/workflow_executor_adapter.py` 需要一个稳定的
Application 层入口来执行 workflow（非流式/流式），以便在调度器/后台任务等场景复用。

KISS：该 Facade 目前仅作为 `ExecuteWorkflowUseCase` 的轻量包装，避免接口层直接依赖
Use Case 的构造细节；可在后续迭代中再引入更复杂的策略（例如 LangGraph executor）。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from src.application.use_cases.execute_workflow import ExecuteWorkflowInput, ExecuteWorkflowUseCase
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository


class WorkflowExecutionFacade:
    """Workflow 执行门面（Application 层）。"""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowRepository,
        executor_registry: NodeExecutorRegistry | None = None,
        langgraph_executor: Any | None = None,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._executor_registry = executor_registry
        self._langgraph_executor = langgraph_executor

    async def execute(self, *, workflow_id: str, input_data: Any = None) -> dict[str, Any]:
        # 预留：后续可根据配置选择 langgraph_executor；当前保持最小可用实现。
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
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=self._workflow_repository,
            executor_registry=self._executor_registry,
        )
        async for event in use_case.execute_streaming(
            ExecuteWorkflowInput(workflow_id=workflow_id, initial_input=input_data)
        ):
            yield event

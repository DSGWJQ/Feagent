"""工作流执行器适配器

Step 3 重构：
- 实现 WorkflowExecutorPort 接口
- 内部使用 WorkflowExecutionFacade 执行
- 每次执行创建独立 session（调度器场景）

Step 6 重构：
- 注入 LangGraphWorkflowExecutorAdapter 实现 LANGGRAPH 模式
- Application 层（WorkflowExecutionFacade）不直接 import LangGraph
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from src.application.services.workflow_execution_facade import WorkflowExecutionFacade
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry
from src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor_adapter import (
    LangGraphWorkflowExecutorAdapter,
)

if TYPE_CHECKING:
    pass


class WorkflowExecutorAdapter:
    """在调度/后台任务中执行工作流

    实现协议: WorkflowExecutorPort
        - 供 ScheduleWorkflowService 调用
        - 每次执行创建独立 session 和 Facade

    Step 3 重构：
    - 统一使用 WorkflowExecutionFacade 执行
    - 确保调度器执行与 API 执行产生相同格式的 SSE 事件

    Step 6 重构：
    - 注入 LangGraphWorkflowExecutorAdapter 实现 LANGGRAPH 模式
    - Application 层不直接 import LangGraph（仅出现在 Infrastructure）
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        executor_registry: Any | None = None,
    ):
        self._session_factory = session_factory
        if executor_registry is None:
            executor_registry = create_executor_registry()
        self.executor_registry = executor_registry

    @contextmanager
    def _create_facade(self) -> Iterator[WorkflowExecutionFacade]:
        """为每次执行创建独立的 session 和 Facade

        Step 6: 同时创建 LangGraphWorkflowExecutorAdapter 注入 Facade
        """
        session = self._session_factory()
        repo = SQLAlchemyWorkflowRepository(session)

        # Step 6: 创建 LangGraph 执行器（Infrastructure 层）
        langgraph_executor = LangGraphWorkflowExecutorAdapter(
            workflow_repository=repo,
            executor_registry=self.executor_registry,
        )

        facade = WorkflowExecutionFacade(
            workflow_repository=repo,
            executor_registry=self.executor_registry,
            langgraph_executor=langgraph_executor,
        )
        try:
            yield facade
        finally:
            session.close()

    async def execute(
        self,
        workflow_id: str,
        input_data: Any = None,
    ) -> dict[str, Any]:
        """执行工作流（非流式）

        实现 WorkflowExecutorPort.execute 接口
        """
        with self._create_facade() as facade:
            return await facade.execute(
                workflow_id=workflow_id,
                input_data=input_data,
            )

    async def execute_streaming(
        self,
        workflow_id: str,
        input_data: Any = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """执行工作流（流式）

        实现 WorkflowExecutorPort.execute_streaming 接口

        注意：由于 session 生命周期需要跨越整个流式执行，
        这里不使用 contextmanager，而是手动管理 session。
        """
        session = self._session_factory()
        repo = SQLAlchemyWorkflowRepository(session)

        # Step 6: 创建 LangGraph 执行器（Infrastructure 层）
        langgraph_executor = LangGraphWorkflowExecutorAdapter(
            workflow_repository=repo,
            executor_registry=self.executor_registry,
        )

        facade = WorkflowExecutionFacade(
            workflow_repository=repo,
            executor_registry=self.executor_registry,
            langgraph_executor=langgraph_executor,
        )
        try:
            async for event in facade.execute_streaming(
                workflow_id=workflow_id,
                input_data=input_data,
            ):
                yield event
        finally:
            session.close()

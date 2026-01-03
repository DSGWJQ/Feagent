"""工作流执行器适配器

Step 3 重构：
- 实现 WorkflowExecutorPort 接口
- 内部使用 WorkflowExecutionFacade 执行
- 每次执行创建独立 session（调度器场景）
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
        """为每次执行创建独立的 session 和 Facade"""
        session = self._session_factory()
        repo = SQLAlchemyWorkflowRepository(session)

        facade = WorkflowExecutionFacade(
            workflow_repository=repo,
            executor_registry=self.executor_registry,
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

        facade = WorkflowExecutionFacade(
            workflow_repository=repo,
            executor_registry=self.executor_registry,
        )
        try:
            async for event in facade.execute_streaming(
                workflow_id=workflow_id,
                input_data=input_data,
            ):
                yield event
        finally:
            session.close()

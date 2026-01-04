"""工作流执行器适配器（调度/后台执行）

原则（WFCORE-030）：
- 当 run persistence 启用时：不得绕过 run gate / Coordinator gate，必须走 WorkflowRunExecutionEntryPort
- 当 run persistence 关闭（回滚开关）时：允许使用 legacy WorkflowExecutionFacade 执行（无 run_id）
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from src.application.services.workflow_execution_facade import WorkflowExecutionFacade
from src.config import settings
from src.domain.entities.run import Run
from src.domain.exceptions import DomainError
from src.domain.ports.run_repository import RunRepository
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.ports.workflow_run_execution_entry import WorkflowRunExecutionEntryPort
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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
        *,
        workflow_run_execution_entry_factory: Callable[[Session], WorkflowRunExecutionEntryPort]
        | None = None,
        workflow_repository_factory: Callable[[Session], WorkflowRepository] | None = None,
        run_repository_factory: Callable[[Session], RunRepository] | None = None,
    ):
        self._session_factory = session_factory
        if executor_registry is None:
            executor_registry = create_executor_registry(session_factory=session_factory)
        self.executor_registry = executor_registry
        self._workflow_run_execution_entry_factory = workflow_run_execution_entry_factory
        self._workflow_repository_factory = workflow_repository_factory
        self._run_repository_factory = run_repository_factory

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
        if not settings.disable_run_persistence:
            return await self._execute_via_run_entry(workflow_id=workflow_id, input_data=input_data)
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
        if not settings.disable_run_persistence:
            async for event in self._execute_streaming_via_run_entry(
                workflow_id=workflow_id,
                input_data=input_data,
            ):
                yield event
            return

        session = self._session_factory()
        repo = SQLAlchemyWorkflowRepository(session)
        facade = WorkflowExecutionFacade(
            workflow_repository=repo,
            executor_registry=self.executor_registry,
        )
        try:
            async for event in facade.execute_streaming(
                workflow_id=workflow_id, input_data=input_data
            ):
                yield event
        finally:
            session.close()

    def _require_run_entry_dependencies(self) -> None:
        if self._workflow_run_execution_entry_factory is None:
            raise DomainError(
                "WorkflowExecutorAdapter requires workflow_run_execution_entry_factory when run persistence is enabled"
            )
        if self._workflow_repository_factory is None:
            raise DomainError(
                "WorkflowExecutorAdapter requires workflow_repository_factory when run persistence is enabled"
            )
        if self._run_repository_factory is None:
            raise DomainError(
                "WorkflowExecutorAdapter requires run_repository_factory when run persistence is enabled"
            )

    def _create_scheduled_run(self, *, session: Session, workflow_id: str) -> Run:
        self._require_run_entry_dependencies()
        workflow = self._workflow_repository_factory(session).get_by_id(workflow_id)  # type: ignore[misc]
        project_id = getattr(workflow, "project_id", None)
        if not isinstance(project_id, str) or not project_id.strip():
            raise DomainError(
                "scheduled workflow execution requires workflow.project_id (runs require project_id)"
            )
        return Run.create(project_id=project_id, workflow_id=workflow_id)

    async def _execute_via_run_entry(self, *, workflow_id: str, input_data: Any) -> dict[str, Any]:
        session = self._session_factory()
        try:
            run = self._create_scheduled_run(session=session, workflow_id=workflow_id)
            self._run_repository_factory(session).save(run)  # type: ignore[misc]
            session.commit()
            logger.info(
                "scheduled_workflow_run_created",
                extra={"workflow_id": workflow_id, "run_id": run.id},
            )

            entry = self._workflow_run_execution_entry_factory(session)  # type: ignore[misc]
            return await entry.execute_with_results(
                workflow_id=workflow_id,
                run_id=run.id,
                input_data=input_data,
                correlation_id=run.id,
                original_decision_id=run.id,
                record_execution_events=True,
            )
        finally:
            session.close()

    async def _execute_streaming_via_run_entry(
        self,
        *,
        workflow_id: str,
        input_data: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        session = self._session_factory()
        try:
            run = self._create_scheduled_run(session=session, workflow_id=workflow_id)
            self._run_repository_factory(session).save(run)  # type: ignore[misc]
            session.commit()
            logger.info(
                "scheduled_workflow_run_created",
                extra={"workflow_id": workflow_id, "run_id": run.id},
            )

            entry = self._workflow_run_execution_entry_factory(session)  # type: ignore[misc]
            async for event in entry.execute_streaming(
                workflow_id=workflow_id,
                run_id=run.id,
                input_data=input_data,
                correlation_id=run.id,
                original_decision_id=run.id,
                record_execution_events=True,
            ):
                yield event
        finally:
            session.close()

"""工作流执行器适配器"""

import asyncio
from contextlib import contextmanager
from typing import Any, Callable

from sqlalchemy.orm import Session

from src.domain.services.workflow_executor import WorkflowExecutor
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry


class WorkflowExecutorAdapter:
    """在调度/后台任务中执行工作流."""

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
    def _workflow_repo(self) -> SQLAlchemyWorkflowRepository:
        session = self._session_factory()
        repo = SQLAlchemyWorkflowRepository(session)
        try:
            yield repo
        finally:
            session.close()

    def execute_workflow(self, workflow_id: str, input_data: dict) -> dict:
        """同步执行（供调度器调用，内部启动新的事件循环）"""
        return asyncio.run(self.execute_workflow_async(workflow_id, input_data))

    async def execute_workflow_async(self, workflow_id: str, input_data: dict) -> dict:
        """异步执行，供 API/后台协程调用。"""
        with self._workflow_repo() as workflow_repository:
            workflow = workflow_repository.find_by_id(workflow_id)
            if not workflow:
                return {
                    "status": "failure",
                    "workflow_id": workflow_id,
                    "error": f"工作流未找到: {workflow_id}",
                }

            executor = WorkflowExecutor(executor_registry=self.executor_registry)
            result = await executor.execute(workflow, initial_input=input_data)

            return {
                "status": "success",
                "workflow_id": workflow_id,
                "data": result,
                "logs": executor.execution_log,
            }

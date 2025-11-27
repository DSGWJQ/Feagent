"""工作流调度服务"""

import asyncio
from contextlib import contextmanager
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from src.infrastructure.database.repositories.scheduled_workflow_repository import (
    SQLAlchemyScheduledWorkflowRepository,
)

class ScheduleWorkflowService:
    """使用 APScheduler 管理定时工作流执行。"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        workflow_executor: Any,
    ):
        self._session_factory = session_factory
        self.executor = workflow_executor
        self.scheduler = BackgroundScheduler()
        self._is_running = False

    @contextmanager
    def _repo(self) -> SQLAlchemyScheduledWorkflowRepository:
        session = self._session_factory()
        repo = SQLAlchemyScheduledWorkflowRepository(session)
        try:
            yield repo
        finally:
            session.close()

    def start(self) -> None:
        """启动调度器并加载已存在的任务。"""
        if self._is_running:
            return

        self.scheduler.start()
        self._is_running = True

        with self._repo() as repo:
            active_workflows = repo.find_active()
            for workflow in active_workflows:
                self._add_to_scheduler(workflow)

    def stop(self) -> None:
        """停止调度器。"""
        if not self._is_running:
            return

        self.scheduler.shutdown()
        self._is_running = False

    def _add_to_scheduler(self, scheduled_workflow) -> None:
        """将定时工作流添加到调度器。"""
        try:
            trigger = CronTrigger.from_crontab(scheduled_workflow.cron_expression)

            self.scheduler.add_job(
                func=self._execute_workflow,
                trigger=trigger,
                args=[scheduled_workflow.id],
                id=scheduled_workflow.id,
                name=f"scheduled_workflow_{scheduled_workflow.id}",
                replace_existing=True,
            )
        except Exception as e:  # pragma: no cover - 日志用途
            print(f"添加调度任务失败 {scheduled_workflow.id}: {e}")

    def _execute_workflow(self, scheduled_workflow_id: str) -> None:
        """供 APScheduler 调用的同步入口。"""
        asyncio.run(self._execute_workflow_async(scheduled_workflow_id))

    async def _execute_workflow_async(self, scheduled_workflow_id: str) -> dict[str, Any]:
        """执行定时任务并记录结果。"""
        scheduled = None
        session = self._session_factory()
        repo = SQLAlchemyScheduledWorkflowRepository(session)
        try:
            scheduled = repo.get_by_id(scheduled_workflow_id)
            result = await self.executor.execute_workflow_async(
                workflow_id=scheduled.workflow_id,
                input_data={},
            )

            scheduled.record_execution_success()
            repo.save(scheduled)

            return {
                "status": scheduled.last_execution_status,
                "timestamp": scheduled.last_execution_at,
                "executor_result": result,
            }
        except Exception as e:
            if scheduled is None:
                session.close()
                return

            scheduled.record_execution_failure(str(e))
            repo.save(scheduled)
            raise
        finally:
            session.close()

    async def trigger_execution_async(self, scheduled_workflow_id: str) -> dict[str, Any]:
        """手动触发（API 调用）"""
        return await self._execute_workflow_async(scheduled_workflow_id)

    def trigger_execution(self, scheduled_workflow_id: str) -> dict[str, Any]:
        """同步触发（测试/脚本使用）"""
        return asyncio.run(self.trigger_execution_async(scheduled_workflow_id))

    def get_scheduled_job(self, scheduled_workflow_id: str) -> Any | None:
        """返回 APScheduler job 对象"""
        return self.scheduler.get_job(scheduled_workflow_id)

    def unschedule_workflow(self, scheduled_workflow_id: str) -> None:
        """删除调度任务，仅影响调度器"""
        try:
            self.scheduler.remove_job(scheduled_workflow_id)
        except Exception:
            pass

    def pause_scheduled_workflow(self, scheduled_workflow_id: str) -> None:
        """暂停任务并从调度器移除。"""
        with self._repo() as repo:
            scheduled = repo.get_by_id(scheduled_workflow_id)
            scheduled.disable()
            repo.save(scheduled)

        self.unschedule_workflow(scheduled_workflow_id)

    def resume_scheduled_workflow(self, scheduled_workflow_id: str) -> None:
        """重新启用任务并注册到调度器。"""
        with self._repo() as repo:
            scheduled = repo.get_by_id(scheduled_workflow_id)
            scheduled.enable()
            repo.save(scheduled)

        self._add_to_scheduler(scheduled)

    def add_job(self, job_id: str, cron_expression: str, workflow_id: str) -> None:
        """新增调度任务（由 UseCase 调用）"""
        try:
            trigger = CronTrigger.from_crontab(cron_expression)

            self.scheduler.add_job(
                func=self._execute_workflow,
                trigger=trigger,
                args=[job_id],
                id=job_id,
                name=f"scheduled_workflow_{job_id}",
                replace_existing=True,
            )
        except Exception as e:  # pragma: no cover
            print(f"添加调度任务失败 {job_id}: {e}")

    def remove_job(self, job_id: str) -> None:
        """移除调度任务"""
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

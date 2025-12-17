"""工作流调度服务"""

import asyncio
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.ports.scheduler_repository import SchedulerRepository


class ScheduleWorkflowService:
    """使用 APScheduler 管理定时工作流执行。

    依赖注入：
    - scheduled_workflow_repo: 定时工作流持久化仓库（必需）
    - workflow_executor: 工作流执行器（必需）
    """

    def __init__(
        self,
        scheduled_workflow_repo: SchedulerRepository,
        workflow_executor: Any,
    ):
        """初始化调度服务

        参数：
            scheduled_workflow_repo: 定时工作流仓库实例（必需）
            workflow_executor: 工作流执行器实例（必需）
        """
        self._repo = scheduled_workflow_repo
        self.executor = workflow_executor
        self.scheduler = BackgroundScheduler()
        self._is_running = False

    def start(self) -> None:
        """启动调度器并加载已存在的任务。"""
        if self._is_running:
            return

        self.scheduler.start()
        self._is_running = True

        active_workflows = self._repo.find_active()
        for workflow in active_workflows:
            self._add_to_scheduler(workflow)

    def stop(self) -> None:
        """停止调度器。"""
        if not self._is_running:
            return

        self.scheduler.shutdown()
        self._is_running = False

    def _add_to_scheduler(self, scheduled_workflow: ScheduledWorkflow) -> None:
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
        scheduled: ScheduledWorkflow | None = None
        try:
            scheduled = self._repo.get_by_id(scheduled_workflow_id)
            result = await self.executor.execute_workflow_async(
                workflow_id=scheduled.workflow_id,
                input_data={},
            )

            scheduled.record_execution_success()
            self._repo.save(scheduled)

            return {
                "status": scheduled.last_execution_status,
                "timestamp": scheduled.last_execution_at,
                "executor_result": result,
            }
        except Exception as e:
            if scheduled is None:
                return {"status": "FAILED", "error": str(e)}

            scheduled.record_execution_failure(str(e))
            self._repo.save(scheduled)
            raise

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
        scheduled = self._repo.get_by_id(scheduled_workflow_id)
        scheduled.disable()
        self._repo.save(scheduled)

        self.unschedule_workflow(scheduled_workflow_id)

    def resume_scheduled_workflow(self, scheduled_workflow_id: str) -> None:
        """重新启用任务并注册到调度器。"""
        scheduled = self._repo.get_by_id(scheduled_workflow_id)
        scheduled.enable()
        self._repo.save(scheduled)

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

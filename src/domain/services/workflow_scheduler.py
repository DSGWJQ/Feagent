"""工作流调度服务

事务边界：
- 调度器使用 session_factory 为每次操作创建独立 session
- 每次操作完成后 commit 并关闭 session
- 确保调度器执行不会阻塞事务或造成长事务问题

Step 3 重构：
- 使用 WorkflowExecutorPort 接口注入执行器
- 统一执行链路，与 API 执行保持一致
"""

import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.ports.scheduler_repository import SchedulerRepository

if TYPE_CHECKING:
    from src.domain.ports.workflow_executor_port import WorkflowExecutorPort


class ScheduleWorkflowService:
    """使用 APScheduler 管理定时工作流执行。

    依赖注入：
    - scheduled_workflow_repo: 定时工作流持久化仓库（必需）
    - workflow_executor: 工作流执行器端口（必需，实现 WorkflowExecutorPort）
    - session_factory: Session 工厂函数（可选，用于调度器执行时创建独立事务）

    事务边界：
    - 若提供 session_factory，调度器执行时会创建独立 session 并提交
    - 否则使用注入的 repo（适用于 UseCase 控制事务的场景）

    Step 3 重构：
    - workflow_executor 改为 WorkflowExecutorPort 类型
    - 统一调用 execute() 方法，与 API 执行链路一致
    """

    def __init__(
        self,
        scheduled_workflow_repo: SchedulerRepository,
        workflow_executor: "WorkflowExecutorPort",
        session_factory: Callable[[], Any] | None = None,
        repo_factory: Callable[[Any], SchedulerRepository] | None = None,
    ):
        """初始化调度服务

        参数：
            scheduled_workflow_repo: 定时工作流仓库实例（必需）
            workflow_executor: 工作流执行器（实现 WorkflowExecutorPort）
            session_factory: Session 工厂函数（可选，调度器执行时使用）
            repo_factory: Repository 工厂函数（可选，用于从 session 创建 repo）
        """
        self._repo = scheduled_workflow_repo
        self._executor = workflow_executor
        self._session_factory = session_factory
        self._repo_factory = repo_factory
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
        from src.domain.services.asyncio_compat import run_sync

        run_sync(self._execute_workflow_async(scheduled_workflow_id))

    async def _execute_workflow_async(self, scheduled_workflow_id: str) -> dict[str, Any]:
        """执行定时任务并记录结果。

        事务边界：
        - 若提供 session_factory，创建独立 session 并在操作后 commit/close
        - 确保调度器执行不会造成长事务问题
        """
        # 若有 session_factory，为本次执行创建独立事务
        if self._session_factory and self._repo_factory:
            session = self._session_factory()
            repo = self._repo_factory(session)
        else:
            session = None
            repo = self._repo

        scheduled: ScheduledWorkflow | None = None
        try:
            scheduled = repo.get_by_id(scheduled_workflow_id)

            input_data: dict[str, Any] = {}

            # Red-team: `unittest.mock.Mock` makes `hasattr()` unreliable (it returns True for any name).
            executor_dict = getattr(self._executor, "__dict__", {}) or {}
            has_execute_workflow = ("execute_workflow" in executor_dict) or callable(
                getattr(type(self._executor), "execute_workflow", None)
            )
            has_execute = ("execute" in executor_dict) or callable(
                getattr(type(self._executor), "execute", None)
            )

            execute_workflow = getattr(self._executor, "execute_workflow", None)
            execute = getattr(self._executor, "execute", None)

            # Backward-compat: many callers/tests patch `execute_workflow` directly.
            if has_execute_workflow and callable(execute_workflow):
                try:
                    maybe_result = execute_workflow(
                        workflow_id=scheduled.workflow_id,
                        input_data=input_data,
                    )
                except TypeError:
                    maybe_result = execute_workflow(scheduled.workflow_id, input_data)
            elif has_execute and callable(execute):
                maybe_result = execute(
                    workflow_id=scheduled.workflow_id,
                    input_data=input_data,
                )
            else:
                raise TypeError("workflow_executor must implement execute_workflow() or execute()")

            result = await maybe_result if inspect.isawaitable(maybe_result) else maybe_result

            scheduled.record_execution_success()
            repo.save(scheduled)

            # 若使用独立 session，提交事务
            if session is not None:
                session.commit()

            return {
                "status": scheduled.last_execution_status,
                "timestamp": scheduled.last_execution_at,
                "executor_result": result,
            }
        except Exception as e:
            if scheduled is None:
                if session is not None:
                    session.rollback()
                return {"status": "FAILED", "error": str(e)}

            scheduled.record_execution_failure(str(e))
            repo.save(scheduled)

            # 若使用独立 session，提交失败记录
            if session is not None:
                session.commit()
            raise
        finally:
            # 关闭独立 session
            if session is not None:
                session.close()

    async def trigger_execution_async(self, scheduled_workflow_id: str) -> dict[str, Any]:
        """手动触发（API 调用）"""
        return await self._execute_workflow_async(scheduled_workflow_id)

    def trigger_execution(self, scheduled_workflow_id: str) -> dict[str, Any]:
        """同步触发（测试/脚本使用）"""
        from src.domain.services.asyncio_compat import run_sync

        return run_sync(self.trigger_execution_async(scheduled_workflow_id))

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
        """暂停任务并从调度器移除。

        事务边界：
        - 若提供 session_factory，创建独立 session 并提交
        - 否则依赖外部 UseCase 控制事务
        """
        # 若有 session_factory，创建独立事务
        if self._session_factory and self._repo_factory:
            session = self._session_factory()
            repo = self._repo_factory(session)
        else:
            session = None
            repo = self._repo

        try:
            scheduled = repo.get_by_id(scheduled_workflow_id)
            scheduled.disable()
            repo.save(scheduled)

            if session is not None:
                session.commit()

            self.unschedule_workflow(scheduled_workflow_id)
        except Exception:
            if session is not None:
                session.rollback()
            raise
        finally:
            if session is not None:
                session.close()

    def resume_scheduled_workflow(self, scheduled_workflow_id: str) -> None:
        """重新启用任务并注册到调度器。

        事务边界：
        - 若提供 session_factory，创建独立 session 并提交
        - 否则依赖外部 UseCase 控制事务
        """
        # 若有 session_factory，创建独立事务
        if self._session_factory and self._repo_factory:
            session = self._session_factory()
            repo = self._repo_factory(session)
        else:
            session = None
            repo = self._repo

        try:
            scheduled = repo.get_by_id(scheduled_workflow_id)
            scheduled.enable()
            repo.save(scheduled)

            if session is not None:
                session.commit()

            self._add_to_scheduler(scheduled)
        except Exception:
            if session is not None:
                session.rollback()
            raise
        finally:
            if session is not None:
                session.close()

    def add_job(self, job_id: str, cron_expression: str, workflow_id: str) -> None:
        """新增调度任务（由 UseCase 调用）

        注意：
        - 异常会向上传播，由 UseCase 处理 rollback
        - 不再吞掉异常，确保事务一致性
        """
        trigger = CronTrigger.from_crontab(cron_expression)

        self.scheduler.add_job(
            func=self._execute_workflow,
            trigger=trigger,
            args=[job_id],
            id=job_id,
            name=f"scheduled_workflow_{job_id}",
            replace_existing=True,
        )

    def remove_job(self, job_id: str) -> None:
        """移除调度任务

        注意：
        - 移除不存在的任务不抛异常（幂等操作）
        """
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

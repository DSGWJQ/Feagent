"""工作流调度服务

职责：
1. 使用 APScheduler 管理定时工作流的执行
2. 在指定时间触发工作流执行
3. 记录执行结果到数据库
4. 支持暂停、恢复、删除调度
"""

from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.infrastructure.database.repositories.scheduled_workflow_repository import (
    SQLAlchemyScheduledWorkflowRepository,
)


class ScheduleWorkflowService:
    """工作流调度服务 - 使用 APScheduler 实现定时执行

    依赖：
    - SQLAlchemyScheduledWorkflowRepository: 访问定时工作流数据
    - workflow_executor: 执行工作流的执行器（可以是任何可调用对象）
    """

    def __init__(
        self,
        scheduled_workflow_repo: SQLAlchemyScheduledWorkflowRepository,
        workflow_executor: Any,
    ):
        """初始化调度服务

        参数：
            scheduled_workflow_repo: 定时工作流仓库
            workflow_executor: 工作流执行器（需要有 execute_workflow 方法）
        """
        self.repo = scheduled_workflow_repo
        self.executor = workflow_executor
        self.scheduler = BackgroundScheduler()
        self._is_running = False

    def start(self) -> None:
        """启动调度器

        将所有活跃的定时工作流加载到调度器中
        """
        if self._is_running:
            return

        # 启动 APScheduler
        self.scheduler.start()
        self._is_running = True

        # 加载所有活跃的定时工作流
        active_workflows = self.repo.find_active()
        for workflow in active_workflows:
            self._add_to_scheduler(workflow)

    def stop(self) -> None:
        """停止调度器

        停止所有调度的任务
        """
        if not self._is_running:
            return

        self.scheduler.shutdown()
        self._is_running = False

    def _add_to_scheduler(self, scheduled_workflow) -> None:
        """将定时工作流添加到调度器

        参数：
            scheduled_workflow: ScheduledWorkflow 实体
        """
        try:
            # 创建 cron 触发器
            trigger = CronTrigger.from_crontab(scheduled_workflow.cron_expression)

            # 添加到调度器
            self.scheduler.add_job(
                func=self._execute_workflow,
                trigger=trigger,
                args=[scheduled_workflow.id],
                id=scheduled_workflow.id,
                name=f"scheduled_workflow_{scheduled_workflow.id}",
                replace_existing=True,
            )
        except Exception as e:
            print(f"添加调度任务失败 {scheduled_workflow.id}: {e}")

    def _execute_workflow(self, scheduled_workflow_id: str) -> None:
        """执行工作流的回调函数

        流程：
        1. 从数据库获取定时工作流配置
        2. 调用执行器执行工作流
        3. 记录执行结果（成功或失败）
        4. 自动禁用如果达到失败限制

        参数：
            scheduled_workflow_id: 定时工作流 ID
        """
        scheduled = None
        try:
            # 获取定时工作流配置
            scheduled = self.repo.get_by_id(scheduled_workflow_id)

            # 调用执行器执行工作流
            self.executor.execute_workflow(
                workflow_id=scheduled.workflow_id,
                input_data={},
            )

            # 记录执行成功
            scheduled.record_execution_success()
            self.repo.save(scheduled)

        except Exception as e:
            # 记录执行失败
            if scheduled is None:
                # 如果无法获取定时工作流，则忽略（可能已删除）
                return

            scheduled.record_execution_failure(str(e))
            self.repo.save(scheduled)
            # 注意：record_execution_failure 会在失败数达到 max_retries 时自动禁用

    def trigger_execution(self, scheduled_workflow_id: str) -> dict:
        """手动触发定时工作流执行（用于测试和手动执行）

        参数：
            scheduled_workflow_id: 定时工作流 ID

        返回：
            执行结果
        """
        self._execute_workflow(scheduled_workflow_id)
        scheduled = self.repo.get_by_id(scheduled_workflow_id)
        return {
            "status": scheduled.last_execution_status,
            "timestamp": scheduled.last_execution_at,
        }

    def get_scheduled_job(self, scheduled_workflow_id: str) -> Any | None:
        """获取调度任务信息

        参数：
            scheduled_workflow_id: 定时工作流 ID

        返回：
            APScheduler job 对象，或 None 如果不存在
        """
        return self.scheduler.get_job(scheduled_workflow_id)

    def unschedule_workflow(self, scheduled_workflow_id: str) -> None:
        """从调度器中删除定时工作流

        参数：
            scheduled_workflow_id: 定时工作流 ID
        """
        try:
            self.scheduler.remove_job(scheduled_workflow_id)
        except Exception:
            # 任务不存在，忽略
            pass

    def pause_scheduled_workflow(self, scheduled_workflow_id: str) -> None:
        """暂停定时工作流（将其禁用）

        参数：
            scheduled_workflow_id: 定时工作流 ID
        """
        scheduled = self.repo.get_by_id(scheduled_workflow_id)
        scheduled.disable()
        self.repo.save(scheduled)

        # 从调度器中删除
        self.unschedule_workflow(scheduled_workflow_id)

    def resume_scheduled_workflow(self, scheduled_workflow_id: str) -> None:
        """恢复定时工作流（将其启用）

        参数：
            scheduled_workflow_id: 定时工作流 ID
        """
        scheduled = self.repo.get_by_id(scheduled_workflow_id)
        scheduled.enable()
        self.repo.save(scheduled)

        # 重新添加到调度器
        self._add_to_scheduler(scheduled)

    def add_job(self, job_id: str, cron_expression: str, workflow_id: str) -> None:
        """添加定时工作流到调度器（来自 UseCase 的接口）

        参数：
            job_id: 任务 ID（scheduled_workflow.id）
            cron_expression: Cron 表达式
            workflow_id: 工作流 ID
        """
        try:
            # 创建 cron 触发器
            trigger = CronTrigger.from_crontab(cron_expression)

            # 添加到调度器
            self.scheduler.add_job(
                func=self._execute_workflow,
                trigger=trigger,
                args=[job_id],
                id=job_id,
                name=f"scheduled_workflow_{job_id}",
                replace_existing=True,
            )
        except Exception as e:
            print(f"添加调度任务失败 {job_id}: {e}")

    def remove_job(self, job_id: str) -> None:
        """从调度器中移除任务（来自 UseCase 的接口）

        参数：
            job_id: 任务 ID（scheduled_workflow.id）
        """
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            # 任务不存在，忽略
            pass

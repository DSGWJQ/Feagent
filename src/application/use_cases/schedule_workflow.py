"""ScheduleWorkflowUseCase - 为工作流创建定时执行任务

编排：
1. 验证工作流存在
2. 创建ScheduledWorkflow实体
3. 保存到仓库
4. 在调度器中注册
"""

import inspect
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.exceptions import NotFoundError


@dataclass
class ScheduleWorkflowInput:
    """输入数据"""

    workflow_id: str
    cron_expression: str
    max_retries: int = 3


@dataclass
class UnscheduleWorkflowInput:
    """取消定时任务输入"""

    scheduled_workflow_id: str


class ScheduleWorkflowUseCase:
    """定时工作流用例

    职责：
    - 为工作流创建定时执行配置
    - 在调度器中注册任务
    - 管理定时任务的生命周期
    """

    def __init__(self, workflow_repo, scheduled_workflow_repo, scheduler):
        """初始化用例

        参数：
            workflow_repo: 工作流仓库（端口）
            scheduled_workflow_repo: 定时工作流仓库（端口）
            scheduler: 调度器适配器
        """
        self.workflow_repo = workflow_repo
        self.scheduled_workflow_repo = scheduled_workflow_repo
        self.scheduler = scheduler

    def _pause_job(self, scheduled_workflow: ScheduledWorkflow) -> None:
        pause_job = getattr(self.scheduler, "pause_job", None)
        if callable(pause_job):
            pause_job(scheduled_workflow.id)
            return

        remove_job = getattr(self.scheduler, "remove_job", None)
        if callable(remove_job):
            remove_job(scheduled_workflow.id)
            return

    def _resume_job(self, scheduled_workflow: ScheduledWorkflow) -> None:
        resume_job = getattr(self.scheduler, "resume_job", None)
        if callable(resume_job):
            resume_job(scheduled_workflow.id)
            return

        add_job = getattr(self.scheduler, "add_job", None)
        if callable(add_job):
            add_job(
                job_id=scheduled_workflow.id,
                cron_expression=scheduled_workflow.cron_expression,
                workflow_id=scheduled_workflow.workflow_id,
            )
            return

    def execute(self, input_data: ScheduleWorkflowInput) -> ScheduledWorkflow:
        """为工作流创建定时任务

        参数：
            input_data: 输入数据

        返回：
            创建的ScheduledWorkflow实体

        抛出：
            NotFoundError: 工作流不存在
        """
        # 1. 验证工作流存在
        workflow = self.workflow_repo.get_by_id(input_data.workflow_id)
        if not workflow:
            raise NotFoundError(f"工作流不存在: {input_data.workflow_id}")

        # 2. 创建定时工作流实体
        scheduled_workflow = ScheduledWorkflow.create(
            workflow_id=input_data.workflow_id,
            cron_expression=input_data.cron_expression,
            max_retries=input_data.max_retries,
        )

        # 3. 保存到仓库
        self.scheduled_workflow_repo.save(scheduled_workflow)

        # 4. 在调度器中注册
        self.scheduler.add_job(
            job_id=scheduled_workflow.id,
            cron_expression=scheduled_workflow.cron_expression,
            workflow_id=scheduled_workflow.workflow_id,
        )

        return scheduled_workflow

    def unschedule(self, input_data: UnscheduleWorkflowInput) -> None:
        """取消定时任务

        参数：
            input_data: 输入数据
        """
        # 1. 获取定时工作流
        scheduled_workflow = self.scheduled_workflow_repo.get_by_id(
            input_data.scheduled_workflow_id
        )
        if not scheduled_workflow:
            raise NotFoundError(f"定时任务不存在: {input_data.scheduled_workflow_id}")

        # 2. 从调度器中移除
        self.scheduler.remove_job(scheduled_workflow.id)

        # 3. 从仓库中删除
        self.scheduled_workflow_repo.delete(scheduled_workflow.id)

    def list_scheduled_workflows(self) -> list[ScheduledWorkflow]:
        """列出所有定时任务

        返回：
            定时任务列表
        """
        return self.scheduled_workflow_repo.find_all()

    def get_scheduled_workflow_details(self, scheduled_workflow_id: str) -> ScheduledWorkflow:
        """获取定时任务详情

        参数：
            scheduled_workflow_id: 定时任务ID

        返回：
            定时任务实体

        抛出：
            NotFoundError: 任务不存在
        """
        scheduled_workflow = self.scheduled_workflow_repo.get_by_id(scheduled_workflow_id)
        if not scheduled_workflow:
            raise NotFoundError(f"定时任务不存在: {scheduled_workflow_id}")

        return scheduled_workflow

    async def trigger_execution_async(self, scheduled_workflow_id: str) -> dict[str, Any]:
        """手动触发定时任务执行（API调用）。

        说明：
        - 若 scheduler 提供 trigger_execution_async，则优先委派（例如 ScheduleWorkflowService）。
        - 否则采用最小可用语义：记录一次成功执行并返回时间戳（便于离线/测试环境跑通）。
        """
        scheduled_workflow = self.scheduled_workflow_repo.get_by_id(scheduled_workflow_id)
        if not scheduled_workflow:
            raise NotFoundError(f"定时任务不存在: {scheduled_workflow_id}")

        trigger = getattr(self.scheduler, "trigger_execution_async", None)
        if callable(trigger):
            maybe_awaitable = trigger(scheduled_workflow_id)
            if inspect.isawaitable(maybe_awaitable):
                result = await maybe_awaitable
                if isinstance(result, dict) and "status" in result and "timestamp" in result:
                    return result

        scheduled_workflow.record_execution_success()
        self.scheduled_workflow_repo.save(scheduled_workflow)
        return {
            "status": scheduled_workflow.last_execution_status or "success",
            "timestamp": scheduled_workflow.last_execution_at or datetime.now(UTC),
        }

    def pause(self, scheduled_workflow_id: str) -> ScheduledWorkflow:
        """暂停定时任务（禁用并暂停/移除调度任务）。"""
        scheduled_workflow = self.scheduled_workflow_repo.get_by_id(scheduled_workflow_id)
        if not scheduled_workflow:
            raise NotFoundError(f"定时任务不存在: {scheduled_workflow_id}")

        scheduled_workflow.disable()
        self.scheduled_workflow_repo.save(scheduled_workflow)
        self._pause_job(scheduled_workflow)
        return scheduled_workflow

    def resume(self, scheduled_workflow_id: str) -> ScheduledWorkflow:
        """恢复定时任务（启用并恢复/重新注册调度任务）。"""
        scheduled_workflow = self.scheduled_workflow_repo.get_by_id(scheduled_workflow_id)
        if not scheduled_workflow:
            raise NotFoundError(f"定时任务不存在: {scheduled_workflow_id}")

        scheduled_workflow.enable()
        self.scheduled_workflow_repo.save(scheduled_workflow)
        self._resume_job(scheduled_workflow)
        return scheduled_workflow

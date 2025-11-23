"""ScheduleWorkflowUseCase - 为工作流创建定时执行任务

编排：
1. 验证工作流存在
2. 创建ScheduledWorkflow实体
3. 保存到仓库
4. 在调度器中注册
"""

from dataclasses import dataclass

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

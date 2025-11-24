"""Scheduled Workflows 路由

定义工作流调度相关的 API 端点：
- POST /api/workflows/{workflow_id}/schedule - 创建定时任务
- GET /api/scheduled-workflows - 列出所有定时任务
- GET /api/scheduled-workflows/{scheduled_workflow_id} - 获取定时任务详情
- DELETE /api/scheduled-workflows/{scheduled_workflow_id} - 删除定时任务
- POST /api/scheduled-workflows/{scheduled_workflow_id}/trigger - 手动触发执行
- POST /api/scheduled-workflows/{scheduled_workflow_id}/pause - 暂停定时任务
- POST /api/scheduled-workflows/{scheduled_workflow_id}/resume - 恢复定时任务
- GET /api/scheduler/status - 获取调度器状态
- GET /api/scheduler/jobs - 获取调度器中的任务列表
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.use_cases.schedule_workflow import (
    ScheduleWorkflowInput,
    ScheduleWorkflowUseCase,
    UnscheduleWorkflowInput,
)
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.dto.workflow_features_dto import (
    ScheduledWorkflowResponse,
    ScheduleWorkflowRequest,
)

# 创建路由器
router = APIRouter(tags=["Scheduled Workflows"])


def get_schedule_workflow_use_case(
    session: Session = Depends(get_db_session),
) -> ScheduleWorkflowUseCase:
    """获取 ScheduleWorkflowUseCase - 依赖注入

    注入真实的仓库和调度器服务
    """
    from src.domain.services.workflow_scheduler import ScheduleWorkflowService
    from src.infrastructure.database.repositories.scheduled_workflow_repository import (
        SQLAlchemyScheduledWorkflowRepository,
    )

    workflow_repo = SQLAlchemyWorkflowRepository(session)
    scheduled_workflow_repo = SQLAlchemyScheduledWorkflowRepository(session)

    # 创建工作流执行器（暂时使用 dummy 实现）
    # TODO: 替换为真实的工作流执行器
    from src.interfaces.api.services.workflow_executor_adapter import (
        WorkflowExecutorAdapter,
    )

    executor = WorkflowExecutorAdapter()

    # 创建调度器服务
    scheduler = ScheduleWorkflowService(
        scheduled_workflow_repo=scheduled_workflow_repo,
        workflow_executor=executor,
    )

    return ScheduleWorkflowUseCase(
        workflow_repo=workflow_repo,
        scheduled_workflow_repo=scheduled_workflow_repo,
        scheduler=scheduler,
    )


@router.post(
    "/workflows/{workflow_id}/schedule",
    status_code=status.HTTP_200_OK,
    response_model=ScheduledWorkflowResponse,
)
async def schedule_workflow(
    workflow_id: str,
    request: ScheduleWorkflowRequest,
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> ScheduledWorkflowResponse:
    """为工作流创建定时任务"""
    try:
        input_data = ScheduleWorkflowInput(
            workflow_id=workflow_id,
            cron_expression=request.cron_expression,
            max_retries=request.max_retries,
        )
        result = use_case.execute(input_data)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get(
    "/scheduled-workflows",
    status_code=status.HTTP_200_OK,
    response_model=list[ScheduledWorkflowResponse],
)
async def list_scheduled_workflows(
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> list[ScheduledWorkflowResponse]:
    """列出所有定时任务"""
    try:
        results = use_case.list_scheduled_workflows()
        return [ScheduledWorkflowResponse.from_entity(r) for r in results]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get(
    "/scheduled-workflows/{scheduled_workflow_id}",
    status_code=status.HTTP_200_OK,
    response_model=ScheduledWorkflowResponse,
)
async def get_scheduled_workflow_details(
    scheduled_workflow_id: str,
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> ScheduledWorkflowResponse:
    """获取定时任务详情"""
    try:
        result = use_case.get_scheduled_workflow_details(scheduled_workflow_id)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.delete(
    "/scheduled-workflows/{scheduled_workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unschedule_workflow(
    scheduled_workflow_id: str,
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> None:
    """删除定时任务"""
    try:
        input_data = UnscheduleWorkflowInput(scheduled_workflow_id=scheduled_workflow_id)
        use_case.unschedule(input_data)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post(
    "/scheduled-workflows/{scheduled_workflow_id}/trigger",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, Any],
)
async def trigger_scheduled_workflow(
    scheduled_workflow_id: str,
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> Dict[str, Any]:
    """手动触发定时任务执行"""
    try:
        # 通过调度器触发执行
        result = use_case.scheduler.trigger_execution(scheduled_workflow_id)
        return {
            "scheduled_workflow_id": scheduled_workflow_id,
            "execution_status": result["status"],
            "execution_timestamp": result["timestamp"],
            "message": "任务执行已触发",
        }
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post(
    "/scheduled-workflows/{scheduled_workflow_id}/pause",
    status_code=status.HTTP_200_OK,
    response_model=ScheduledWorkflowResponse,
)
async def pause_scheduled_workflow(
    scheduled_workflow_id: str,
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> ScheduledWorkflowResponse:
    """暂停定时任务"""
    try:
        use_case.scheduler.pause_scheduled_workflow(scheduled_workflow_id)

        # 获取更新后的任务状态
        result = use_case.get_scheduled_workflow_details(scheduled_workflow_id)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post(
    "/scheduled-workflows/{scheduled_workflow_id}/resume",
    status_code=status.HTTP_200_OK,
    response_model=ScheduledWorkflowResponse,
)
async def resume_scheduled_workflow(
    scheduled_workflow_id: str,
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> ScheduledWorkflowResponse:
    """恢复定时任务"""
    try:
        use_case.scheduler.resume_scheduled_workflow(scheduled_workflow_id)

        # 获取更新后的任务状态
        result = use_case.get_scheduled_workflow_details(scheduled_workflow_id)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get(
    "/scheduler/status",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, Any],
)
async def get_scheduler_status(
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> Dict[str, Any]:
    """获取调度器状态"""
    try:
        scheduler = use_case.scheduler

        # 获取调度器中的所有任务
        jobs = scheduler.scheduler.get_jobs()

        return {
            "scheduler_running": scheduler._is_running,
            "total_jobs_in_scheduler": len(jobs),
            "job_details": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
                for job in jobs
            ],
            "message": "调度器状态获取成功",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get(
    "/scheduler/jobs",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, Any],
)
async def get_scheduler_jobs(
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> Dict[str, Any]:
    """获取调度器中的任务列表"""
    try:
        scheduler = use_case.scheduler
        jobs = scheduler.scheduler.get_jobs()

        # 获取数据库中所有活跃的定时任务
        all_scheduled_workflows = use_case.list_scheduled_workflows()
        active_workflows = [w for w in all_scheduled_workflows if w.status == "active"]

        return {
            "jobs_in_scheduler": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
                for job in jobs
            ],
            "active_scheduled_workflows": [
                {
                    "id": wf.id,
                    "workflow_id": wf.workflow_id,
                    "cron_expression": wf.cron_expression,
                    "status": wf.status,
                    "last_execution_status": wf.last_execution_status,
                    "consecutive_failures": wf.consecutive_failures,
                    "max_retries": wf.max_retries,
                    "is_in_scheduler": scheduler.get_scheduled_job(wf.id) is not None,
                }
                for wf in active_workflows
            ],
            "summary": {
                "total_jobs_in_scheduler": len(jobs),
                "total_active_workflows": len(active_workflows),
                "workflows_not_in_scheduler": len([
                    wf for wf in active_workflows
                    if scheduler.get_scheduled_job(wf.id) is None
                ]),
            },
            "message": "任务列表获取成功",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e

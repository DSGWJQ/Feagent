"""Scheduled Workflows 路由"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.use_cases.schedule_workflow import (
    ScheduleWorkflowInput,
    ScheduleWorkflowUseCase,
    UnscheduleWorkflowInput,
)
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.scheduled_workflow_repository import (
    SQLAlchemyScheduledWorkflowRepository,
)
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.dependencies.scheduler import scheduler_service_dependency
from src.interfaces.api.dto.workflow_features_dto import (
    ScheduledWorkflowResponse,
    ScheduleWorkflowRequest,
)

router = APIRouter(tags=["Scheduled Workflows"])


def get_schedule_workflow_use_case(
    session: Session = Depends(get_db_session),
    scheduler=Depends(scheduler_service_dependency),
) -> ScheduleWorkflowUseCase:
    """注入仓库与全局调度服务."""

    workflow_repo = SQLAlchemyWorkflowRepository(session)
    scheduled_workflow_repo = SQLAlchemyScheduledWorkflowRepository(session)

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
    """为工作流创建定时任务."""
    try:
        input_data = ScheduleWorkflowInput(
            workflow_id=workflow_id,
            cron_expression=request.cron_expression,
            max_retries=request.max_retries,
        )
        result = use_case.execute(input_data)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
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
    """列出所有定时任务."""
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
    """获取定时任务详情."""
    try:
        result = use_case.get_scheduled_workflow_details(scheduled_workflow_id)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
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
    """删除定时任务."""
    try:
        input_data = UnscheduleWorkflowInput(scheduled_workflow_id=scheduled_workflow_id)
        use_case.unschedule(input_data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post(
    "/scheduled-workflows/{scheduled_workflow_id}/trigger",
    status_code=status.HTTP_200_OK,
    response_model=dict[str, Any],
)
async def trigger_scheduled_workflow(
    scheduled_workflow_id: str,
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> dict[str, Any]:
    """手动触发定时任务执行."""
    try:
        result = await use_case.scheduler.trigger_execution_async(scheduled_workflow_id)
        return {
            "scheduled_workflow_id": scheduled_workflow_id,
            "execution_status": result["status"],
            "execution_timestamp": result["timestamp"],
            "message": "任务执行已触发",
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
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
    """暂停定时任务."""
    try:
        use_case.scheduler.pause_scheduled_workflow(scheduled_workflow_id)
        result = use_case.get_scheduled_workflow_details(scheduled_workflow_id)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
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
    """恢复定时任务."""
    try:
        use_case.scheduler.resume_scheduled_workflow(scheduled_workflow_id)
        result = use_case.get_scheduled_workflow_details(scheduled_workflow_id)
        return ScheduledWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get(
    "/scheduler/status",
    status_code=status.HTTP_200_OK,
    response_model=dict[str, Any],
)
async def get_scheduler_status(
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> dict[str, Any]:
    """查看调度器状态."""
    try:
        scheduler = use_case.scheduler
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
    response_model=dict[str, Any],
)
async def get_scheduler_jobs(
    use_case: ScheduleWorkflowUseCase = Depends(get_schedule_workflow_use_case),
) -> dict[str, Any]:
    """列出调度器中的任务."""
    try:
        scheduler = use_case.scheduler
        jobs = scheduler.scheduler.get_jobs()
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
                "workflows_not_in_scheduler": len(
                    [wf for wf in active_workflows if scheduler.get_scheduled_job(wf.id) is None]
                ),
            },
            "message": "任务列表获取成功",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e

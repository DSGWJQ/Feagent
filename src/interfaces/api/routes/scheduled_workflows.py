"""Scheduled Workflows 路由

定义工作流调度相关的 API 端点：
- POST /api/workflows/{workflow_id}/schedule - 创建定时任务
- GET /api/scheduled-workflows - 列出所有定时任务
- GET /api/scheduled-workflows/{scheduled_workflow_id} - 获取定时任务详情
- DELETE /api/scheduled-workflows/{scheduled_workflow_id} - 删除定时任务
"""

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
    ScheduleWorkflowRequest,
    ScheduledWorkflowResponse,
)

# 创建路由器
router = APIRouter(tags=["Scheduled Workflows"])


def get_schedule_workflow_use_case(
    session: Session = Depends(get_db_session),
) -> ScheduleWorkflowUseCase:
    """获取 ScheduleWorkflowUseCase - 依赖注入函数"""
    workflow_repo = SQLAlchemyWorkflowRepository(session)
    # TODO: 注入真实的 scheduled_workflow_repo 和 scheduler
    from unittest.mock import Mock
    scheduled_workflow_repo = Mock()
    scheduler = Mock()
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
        )
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


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
        )


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
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


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
        input_data = UnscheduleWorkflowInput(
            scheduled_workflow_id=scheduled_workflow_id
        )
        use_case.unschedule(input_data)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )

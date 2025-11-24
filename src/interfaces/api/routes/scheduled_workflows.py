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

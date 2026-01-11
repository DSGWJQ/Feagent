"""Concurrent Workflows 路由

定义并发工作流相关的 API 端点：
- POST /api/workflows/execute-concurrent - 并发执行多个工作流
- GET /api/workflows/concurrent-runs/wait - 等待所有执行完成
- POST /api/workflows/concurrent-runs/cancel-all - 取消所有执行
- GET /api/runs/{run_id} - 获取执行结果
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.use_cases import execute_concurrent_workflows as execute_concurrent_uc
from src.config import settings
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dto.workflow_features_dto import (
    ExecuteConcurrentWorkflowsRequest,
    ExecutionResultResponse,
)

# 创建路由器
router = APIRouter(tags=["Concurrent Workflows"])


def _get_execute_concurrent_use_case(
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> execute_concurrent_uc.ExecuteConcurrentWorkflowsUseCase:
    workflow_repo = container.workflow_repository(db)
    run_repo = SQLAlchemyRunRepository(db)
    execution_manager = ConcurrentExecutionManager(
        max_concurrent_tasks=settings.max_concurrent_tasks
    )
    return execute_concurrent_uc.ExecuteConcurrentWorkflowsUseCase(
        workflow_repo=workflow_repo,
        execution_manager=execution_manager,
        run_repo=run_repo,
    )


@router.post(
    "/workflows/execute-concurrent",
    status_code=status.HTTP_200_OK,
    response_model=list[ExecutionResultResponse],
)
async def execute_concurrent_workflows(
    request: ExecuteConcurrentWorkflowsRequest,
    use_case: execute_concurrent_uc.ExecuteConcurrentWorkflowsUseCase = Depends(
        _get_execute_concurrent_use_case
    ),
) -> list[ExecutionResultResponse]:
    """并发执行多个工作流"""
    try:
        input_data = execute_concurrent_uc.ExecuteConcurrentWorkflowsInput(
            workflow_ids=request.workflow_ids,
            max_concurrent=request.max_concurrent,
        )
        results = use_case.execute(input_data)
        return [ExecutionResultResponse.from_entity(r) for r in results]
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
    "/workflows/concurrent-runs/wait",
    status_code=status.HTTP_200_OK,
)
async def wait_for_concurrent_completion(
    timeout: int | None = None,
    use_case: execute_concurrent_uc.ExecuteConcurrentWorkflowsUseCase = Depends(
        _get_execute_concurrent_use_case
    ),
) -> dict:
    """等待所有并发执行完成"""
    try:
        completed = use_case.wait_all_completion(timeout=timeout)
        return {"completed": completed}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post(
    "/workflows/concurrent-runs/cancel-all",
    status_code=status.HTTP_200_OK,
)
async def cancel_all_concurrent_executions(
    use_case: execute_concurrent_uc.ExecuteConcurrentWorkflowsUseCase = Depends(
        _get_execute_concurrent_use_case
    ),
) -> dict:
    """取消所有并发执行"""
    try:
        cancelled = use_case.cancel_all_executions()
        return {"cancelled": cancelled}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e

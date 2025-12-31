"""Run API 路由

端点:
    - GET /api/runs/{run_id} - 获取单个 Run
    - GET /api/projects/{project_id}/workflows/{workflow_id}/runs - 列出 Workflow 的 Run
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dto.run_dto import RunListResponse, RunResponse

# 主路由 (包含 /projects/... 端点)
router = APIRouter(tags=["runs"])

# 子路由 (包含 /runs/... 端点)
_runs_router = APIRouter(prefix="/runs", tags=["runs"])


@_runs_router.get(
    "/{run_id}",
    response_model=RunResponse,
    summary="获取 Run",
    description="获取单个 Run 的详细信息",
)
def get_run(
    run_id: str,
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> RunResponse:
    """获取单个 Run

    Args:
        run_id: Run ID
        db: 数据库 Session

    Returns:
        Run 详情

    Raises:
        404: Run 不存在
        500: 内部错误
    """
    try:
        repo = container.run_repository(db)
        run = repo.get_by_id(run_id)
        return RunResponse.from_entity(run)

    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Run 失败: {exc}",
        ) from exc


# ==================== 列出 Run (按 Workflow) ====================


@router.get(
    "/projects/{project_id}/workflows/{workflow_id}/runs",
    response_model=RunListResponse,
    summary="列出 Workflow 的 Run",
    description="列出指定工作流的所有执行记录",
)
def list_runs_by_workflow(
    project_id: str,
    workflow_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="返回数量上限"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> RunListResponse:
    """列出 Workflow 的 Run

    Args:
        project_id: 项目 ID (用于未来权限校验)
        workflow_id: 工作流 ID
        limit: 返回数量上限
        offset: 偏移量
        db: 数据库 Session

    Returns:
        Run 列表
    """
    try:
        repo = container.run_repository(db)
        runs = repo.list_by_workflow_id(workflow_id, limit=limit, offset=offset)
        total = repo.count_by_workflow_id(workflow_id)
        return RunListResponse.from_entities(runs, total=total)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出 Run 失败: {exc}",
        ) from exc


# ==================== 注册子路由 ====================

router.include_router(_runs_router)

__all__ = ["router"]

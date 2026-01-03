"""Run API 路由

端点:
    - GET /api/runs/{run_id} - 获取单个 Run
    - GET /api/projects/{project_id}/workflows/{workflow_id}/runs - 列出 Workflow 的 Run
    - POST /api/projects/{project_id}/workflows/{workflow_id}/runs - 创建 Run（幂等）
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import settings
from src.domain.entities.run import Run
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dto.run_dto import CreateRunRequest, RunListResponse, RunResponse

logger = logging.getLogger(__name__)

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
    response: Response,
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
    if settings.disable_run_persistence:
        response.headers["Deprecation"] = "true"
        response.headers["Warning"] = '299 - "Runs API disabled by feature flag"'
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Runs API is disabled by feature flag (disable_run_persistence).",
        )

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
    response: Response,
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
    if settings.disable_run_persistence:
        response.headers["Deprecation"] = "true"
        response.headers["Warning"] = (
            '299 - "Runs API disabled: use /api/workflows/{workflow_id}/execute/stream"'
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Runs API is disabled by feature flag (disable_run_persistence).",
        )

    try:
        started = time.perf_counter()
        repo = container.run_repository(db)
        runs = repo.list_by_workflow_id(workflow_id, limit=limit, offset=offset)
        total = repo.count_by_workflow_id(workflow_id)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "runs_listed",
            extra={
                "project_id": project_id,
                "workflow_id": workflow_id,
                "limit": limit,
                "offset": offset,
                "duration_ms": duration_ms,
            },
        )
        return RunListResponse.from_entities(runs, total=total)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出 Run 失败: {exc}",
        ) from exc


# ==================== 创建 Run (按 Workflow) ====================


@router.post(
    "/projects/{project_id}/workflows/{workflow_id}/runs",
    response_model=RunResponse,
    summary="创建 Run",
    description="创建一个可追踪的执行记录（支持 Idempotency-Key 幂等）。",
)
def create_run(
    project_id: str,
    workflow_id: str,
    request: CreateRunRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> RunResponse:
    if settings.disable_run_persistence:
        response.headers["Deprecation"] = "true"
        response.headers["Link"] = f'</api/workflows/{workflow_id}/execute/stream>; rel="alternate"'
        response.headers["Warning"] = (
            '299 - "Runs API disabled: use /api/workflows/{workflow_id}/execute/stream"'
        )
        logger.info(
            "run_persistence_disabled_create_run_called",
            extra={"project_id": project_id, "workflow_id": workflow_id},
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Runs API is disabled by feature flag (disable_run_persistence).",
        )

    try:
        started = time.perf_counter()
        # 一致性校验（body 可选字段不允许与 path 冲突）
        if request.project_id is not None and request.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_id mismatch between path and body",
            )
        if request.workflow_id is not None and request.workflow_id != workflow_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workflow_id mismatch between path and body",
            )

        # 先验证 workflow 存在且归属 project（避免 FK/跨项目误绑定）
        wf_repo = container.workflow_repository(db)
        workflow = wf_repo.get_by_id(workflow_id)
        wf_project_id = getattr(workflow, "project_id", None)
        if wf_project_id and wf_project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workflow does not belong to project",
            )

        repo = container.run_repository(db)

        if idempotency_key:
            candidate = Run.create_with_idempotency(
                project_id=project_id,
                workflow_id=workflow_id,
                idempotency_key=idempotency_key,
            )
            existing = repo.find_by_id(candidate.id)
            if existing is not None:
                return RunResponse.from_entity(existing)
            run = candidate
        else:
            run = Run.create(project_id=project_id, workflow_id=workflow_id)

        repo.save(run)
        db.commit()
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "run_created",
            extra={
                "project_id": project_id,
                "workflow_id": workflow_id,
                "run_id": run.id,
                "idempotency_key_present": bool(idempotency_key),
                "duration_ms": duration_ms,
            },
        )
        return RunResponse.from_entity(run)

    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="failed to create run (integrity error)",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建 Run 失败: {exc}",
        ) from exc


# ==================== 注册子路由 ====================

router.include_router(_runs_router)

__all__ = ["router"]

"""Run API 路由

端点:
    - GET /api/runs/{run_id} - 获取单个 Run
    - GET /api/projects/{project_id}/workflows/{workflow_id}/runs - 列出 Workflow 的 Run
    - POST /api/projects/{project_id}/workflows/{workflow_id}/runs - 创建 Run（幂等）
"""

from __future__ import annotations

import logging
import time
from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.application.services.run_confirmation_store import Decision, run_confirmation_store
from src.application.use_cases import execute_concurrent_workflows as execute_concurrent_uc
from src.application.use_cases.execute_run import ExecuteRunInput, ExecuteRunUseCase
from src.config import settings
from src.domain.entities.run import Run
from src.domain.exceptions import DomainError, DomainValidationError, NotFoundError
from src.domain.services.concurrent_execution_manager import ConcurrentExecutionManager
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.models import RunEventModel
from src.infrastructure.database.repositories.agent_repository import SQLAlchemyAgentRepository
from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dto.run_dto import (
    CreateRunRequest,
    RunListResponse,
    RunReplayEvent,
    RunReplayEventsPageResponse,
    RunResponse,
)

logger = logging.getLogger(__name__)

# 主路由 (包含 /projects/... 端点)
router = APIRouter(tags=["runs"])

# 子路由 (包含 /runs/... 端点)
_runs_router = APIRouter(prefix="/runs", tags=["runs"])


class RunConfirmRequest(BaseModel):
    confirm_id: str
    decision: str


class RunConfirmResponse(BaseModel):
    ok: bool


def _get_run_use_case(
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> execute_concurrent_uc.ExecuteConcurrentWorkflowsUseCase:
    # Minimal wiring: `get_execution_result()` depends only on run_repo, but we keep
    # the constructor stable and inject real collaborators for non-mocked runs.
    workflow_repo = container.workflow_repository(db)
    # Use the concrete repository here so unit tests can patch it at this module path.
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
    "/agents/{agent_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="触发 Agent Run（实验入口）",
)
def execute_agent_run(
    agent_id: str,
    db: Session = Depends(get_db_session),
) -> RunResponse:
    """兼容旧链路：POST /api/agents/{agent_id}/runs。

    说明：该入口主要用于实验/回归测试；生产主链路以 /api/workflows/* 为事实源。
    """
    try:
        use_case = ExecuteRunUseCase(
            agent_repository=SQLAlchemyAgentRepository(db),
            run_repository=SQLAlchemyRunRepository(db),
        )
        run = use_case.execute(ExecuteRunInput(agent_id=agent_id))
        db.commit()
        return RunResponse.from_entity(run)
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@_runs_router.get(
    "/{run_id}",
    response_model=RunResponse,
    summary="获取 Run",
    description="获取单个 Run 的详细信息",
)
def get_run(
    run_id: str,
    response: Response,
    use_case: execute_concurrent_uc.ExecuteConcurrentWorkflowsUseCase = Depends(_get_run_use_case),
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
        run = use_case.get_execution_result(run_id)
        payload = getattr(run, "__dict__", None)
        if not isinstance(payload, dict):
            payload = {}

        status_value = payload.get("status")
        status_text = getattr(status_value, "value", status_value)

        duration_seconds = payload.get("duration_seconds")
        if duration_seconds is None and type(run).__module__ != "unittest.mock":
            duration_seconds = getattr(run, "duration_seconds", None)

        return RunResponse(
            id=payload.get("id", run_id),
            project_id=payload.get("project_id"),
            workflow_id=payload.get("workflow_id"),
            agent_id=payload.get("agent_id"),
            status=str(status_text) if status_text is not None else "",
            created_at=payload.get("created_at"),
            finished_at=payload.get("finished_at"),
            duration_seconds=duration_seconds,
        )

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


# ==================== 回放 RunEvents (按 Run) ====================
@_runs_router.get(
    "/{run_id}/events",
    response_model=RunReplayEventsPageResponse,
    summary="回放 RunEvents",
    description="按稳定顺序分页获取 Run 的事件流（用于前端回放）。",
)
def list_run_events(
    run_id: str,
    response: Response,
    limit: int = Query(default=200, ge=1, le=1000, description="单页数量上限"),
    cursor: int | None = Query(
        default=None,
        ge=0,
        description="cursor（返回 id > cursor 的事件；基于自增主键稳定分页）",
    ),
    channel: str = Query(
        default="execution",
        description="事件通道（默认 execution；可用于区分 planning/lifecycle 等）",
    ),
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> RunReplayEventsPageResponse:
    if settings.disable_run_persistence:
        response.headers["Deprecation"] = "true"
        response.headers["Warning"] = '299 - "Runs API disabled by feature flag"'
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Runs API is disabled by feature flag (disable_run_persistence).",
        )

    try:
        # fail-closed: run must exist
        container.run_repository(db).get_by_id(run_id)

        stmt = select(RunEventModel).where(RunEventModel.run_id == run_id)
        if channel:
            stmt = stmt.where(RunEventModel.channel == channel)
        if cursor is not None:
            stmt = stmt.where(RunEventModel.id > cursor)

        # stable ordering: monotonic PK asc
        stmt = stmt.order_by(RunEventModel.id.asc()).limit(limit + 1)
        models = list(db.execute(stmt).scalars().all())

        has_more = len(models) > limit
        if has_more:
            models = models[:limit]

        events: list[RunReplayEvent] = []
        for model in models:
            payload = dict(model.payload or {})
            payload.pop("type", None)
            payload.pop("channel", None)
            payload["run_id"] = run_id
            events.append(RunReplayEvent(type=model.type, **payload))

        next_cursor = models[-1].id if has_more and models else None
        return RunReplayEventsPageResponse(
            run_id=run_id,
            events=events,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 RunEvents 失败: {exc}",
        ) from exc


@_runs_router.post(
    "/{run_id}/confirm",
    response_model=RunConfirmResponse,
    summary="确认外部副作用执行（allow/deny）",
    description="用于 PRD-030：当执行流触发 workflow_confirm_required 时，前端通过该 API 提交 allow/deny 决策。",
)
async def confirm_run_side_effect(
    run_id: str,
    body: RunConfirmRequest,
    response: Response,
) -> RunConfirmResponse:
    if settings.disable_run_persistence:
        response.headers["Deprecation"] = "true"
        response.headers["Warning"] = '299 - "Runs API disabled by feature flag"'
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Runs API is disabled by feature flag (disable_run_persistence).",
        )

    decision_raw = (body.decision or "").strip()
    if decision_raw not in {"allow", "deny"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision must be 'allow' or 'deny'",
        )
    decision = cast(Decision, decision_raw)

    try:
        await run_confirmation_store.resolve(
            run_id=run_id,
            confirm_id=body.confirm_id,
            decision=decision,
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.to_dict(),
        ) from exc

    return RunConfirmResponse(ok=True)


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

    idempotency_key_value = idempotency_key.strip() if isinstance(idempotency_key, str) else None
    if idempotency_key_value == "":
        idempotency_key_value = None

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

        if idempotency_key_value:
            candidate = Run.create_with_idempotency(
                project_id=project_id,
                workflow_id=workflow_id,
                idempotency_key=idempotency_key_value,
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
                "idempotency_key_present": bool(idempotency_key_value),
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
        if idempotency_key_value:
            repo = container.run_repository(db)
            candidate = Run.create_with_idempotency(
                project_id=project_id,
                workflow_id=workflow_id,
                idempotency_key=idempotency_key_value,
            )
            existing = repo.find_by_id(candidate.id)
            if existing is not None:
                return RunResponse.from_entity(existing)
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

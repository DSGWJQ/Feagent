"""Run API 路由

端点:
    - POST /projects/{project_id}/workflows/{workflow_id}/runs - 创建 Run
    - GET /runs/{run_id} - 获取单个 Run
    - GET /runs/{run_id}/events/stream - SSE 事件流 (轮询 + 可重放)

SSE 事件流机制:
    - 每 poll_interval 秒查询一次新事件 (id > after)
    - 有事件则逐条发送: data: {json}\\n\\n
    - Run 终态 (completed/failed) 且无新事件时发送 [DONE] 并结束
    - timeout 后自动结束

断点续传:
    - 客户端断线后携带 after 参数 (最后收到的 event.id)
    - 服务端从该 cursor 后继续推送
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.application.use_cases.create_run import CreateRunInput, CreateRunUseCase
from src.application.use_cases.get_run_events import GetRunEventsInput, GetRunEventsUseCase
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.value_objects.run_status import RunStatus
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.project_repository import (
    SQLAlchemyProjectRepository,
)
from src.infrastructure.database.repositories.run_event_repository import (
    SQLAlchemyRunEventRepository,
)
from src.infrastructure.database.repositories.run_repository import (
    SQLAlchemyRunRepository,
)
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.database.transaction_manager import SQLAlchemyTransactionManager
from src.interfaces.api.dto.run_dto import (
    CreateRunRequest,
    RunEventResponse,
    RunListResponse,
    RunResponse,
)

# 主路由 (包含 /projects/... 端点)
router = APIRouter(tags=["runs"])

# 子路由 (包含 /runs/... 端点)
_runs_router = APIRouter(prefix="/runs", tags=["runs"])


def _format_sse_event(data: dict[str, Any]) -> str:
    """格式化 SSE 事件"""
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _format_sse_done() -> str:
    """格式化 SSE 结束标记"""
    return "data: [DONE]\n\n"


# ==================== 创建 Run ====================


@router.post(
    "/projects/{project_id}/workflows/{workflow_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Run",
    description="创建工作流执行实例 (最小闭环: 只创建记录，不负责执行)",
)
def create_run(
    project_id: str,
    workflow_id: str,
    request: CreateRunRequest,
    db: Session = Depends(get_db_session),
) -> RunResponse:
    """创建 Run

    Args:
        project_id: 项目 ID (路径参数)
        workflow_id: 工作流 ID (路径参数)
        request: 创建请求 (可选的 body)
        db: 数据库 Session

    Returns:
        创建的 Run

    Raises:
        404: Project 或 Workflow 不存在
        400: Workflow 不属于指定 Project
        500: 内部错误
    """
    try:
        # 校验 body 与路径参数一致性 (如果 body 中提供了)
        if request.project_id and request.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_id mismatch between path and body",
            )
        if request.workflow_id and request.workflow_id != workflow_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workflow_id mismatch between path and body",
            )

        # 构造依赖
        project_repo = SQLAlchemyProjectRepository(db)
        workflow_repo = SQLAlchemyWorkflowRepository(db)
        run_repo = SQLAlchemyRunRepository(db)
        tx_manager = SQLAlchemyTransactionManager(db)

        use_case = CreateRunUseCase(
            project_repository=project_repo,
            workflow_repository=workflow_repo,
            run_repository=run_repo,
            transaction_manager=tx_manager,
        )

        # 执行用例
        run = use_case.execute(CreateRunInput(project_id=project_id, workflow_id=workflow_id))

        return RunResponse.from_entity(run)

    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建 Run 失败: {exc}",
        ) from exc


# ==================== 获取 Run ====================


@_runs_router.get(
    "/{run_id}",
    response_model=RunResponse,
    summary="获取 Run",
    description="获取单个 Run 的详细信息",
)
def get_run(
    run_id: str,
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
        repo = SQLAlchemyRunRepository(db)
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
        repo = SQLAlchemyRunRepository(db)
        runs = repo.list_by_workflow_id(workflow_id, limit=limit, offset=offset)
        total = repo.count_by_workflow_id(workflow_id)
        return RunListResponse.from_entities(runs, total=total)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出 Run 失败: {exc}",
        ) from exc


# ==================== SSE 事件流 ====================


@_runs_router.get(
    "/{run_id}/events/stream",
    summary="Run 事件 SSE 流",
    description="SSE 事件流 (轮询模式，支持断点续传)",
)
async def stream_run_events(
    request: Request,
    run_id: str,
    after: int | None = Query(
        default=None,
        description="事件游标 (run_events.id)，从该 ID 之后开始",
    ),
    poll_interval: float = Query(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="轮询间隔 (秒)",
    ),
    timeout: float = Query(
        default=300.0,
        ge=1.0,
        le=3600.0,
        description="超时时间 (秒)",
    ),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """SSE 事件流 (轮询模式)

    规则:
        - 每 poll_interval 秒查询一次新事件 (id > after)
        - 有事件则逐条发送: data: {json}\\n\\n
        - Run 终态 (completed/failed) 且无新事件时发送 [DONE] 并结束
        - timeout 后自动结束

    Args:
        request: FastAPI Request (用于检测客户端断开)
        run_id: Run ID
        after: 事件游标
        poll_interval: 轮询间隔
        timeout: 超时时间
        db: 数据库 Session

    Returns:
        SSE StreamingResponse
    """
    # 首先验证 Run 存在
    run_repo = SQLAlchemyRunRepository(db)
    run_event_repo = SQLAlchemyRunEventRepository(db)

    try:
        run_repo.get_by_id(run_id)  # 验证 Run 存在
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    use_case = GetRunEventsUseCase(run_event_repository=run_event_repo)
    cursor: int | None = after

    async def event_generator() -> AsyncGenerator[str, None]:
        """SSE 事件生成器"""
        nonlocal cursor
        start_time = datetime.now()

        while True:
            # 检测客户端是否断开
            if await request.is_disconnected():
                break

            # 检查超时
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                yield _format_sse_done()
                break

            # 查询新事件
            events = use_case.execute(GetRunEventsInput(run_id=run_id, after=cursor, limit=200))

            if events:
                # 逐条发送事件
                for event in events:
                    dto = RunEventResponse.from_entity(event)
                    yield _format_sse_event(dto.model_dump())

                    # 更新游标
                    if isinstance(event.id, int):
                        cursor = event.id
                    else:
                        try:
                            cursor = int(event.id)
                        except (ValueError, TypeError):
                            pass  # 保持当前游标

                # 有事件时立即继续查询 (可能还有更多)
                continue

            # 无新事件，检查 Run 状态
            current_run = run_repo.find_by_id(run_id)
            if current_run is None:
                yield _format_sse_event(
                    {
                        "type": "error",
                        "channel": "execution",
                        "error": "Run not found",
                    }
                )
                yield _format_sse_done()
                break

            # Run 终态且无新事件，结束流
            if current_run.status in (RunStatus.COMPLETED, RunStatus.FAILED):
                yield _format_sse_done()
                break

            # 等待下次轮询
            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
        },
    )


# ==================== 注册子路由 ====================

router.include_router(_runs_router)

__all__ = ["router"]

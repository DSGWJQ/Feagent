"""协调者状态 API 路由

提供协调者状态查询和 SSE 实时推送功能。

端点：
- GET /status - 获取系统状态摘要
- GET /workflows - 获取所有工作流状态
- GET /workflows/{workflow_id} - 获取单个工作流状态
- GET /workflows/{workflow_id}/stream - SSE 实时状态推送
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from src.config import settings
from src.interfaces.api.dto.coordinator_dto import (
    CompressedContextResponse,
    ContextHistoryResponse,
    ContextSnapshotItem,
    SystemStatusResponse,
    WorkflowListResponse,
    WorkflowStateResponse,
)

router = APIRouter(tags=["coordinator"])


_coordinator: Any | None = None


def get_coordinator(request: Request | None = None) -> Any | None:
    """Return coordinator instance.

    Resolution order:
    - If `request` is provided and `request.app.state.coordinator` exists, use it.
    - Otherwise fall back to module-level singleton `_coordinator` (used by tests).

    Note: Some tests mount this router on a minimal FastAPI app without running the
    main application lifespan, and directly mutate `coord_module._coordinator`.
    """
    global _coordinator

    if request is not None:
        # Test-only override: some integration tests mutate the module-level coordinator
        # to seed deterministic compressed contexts, even when the main app lifespan has
        # already initialized `app.state.coordinator`.
        if settings.env == "test" and _coordinator is not None:
            return _coordinator
        coordinator = getattr(request.app.state, "coordinator", None)
        if coordinator is not None:
            return coordinator
        return _coordinator

    if _coordinator is None:
        from src.application.services.coordinator_agent_factory import create_coordinator_agent
        from src.domain.services.event_bus import EventBus

        _coordinator = create_coordinator_agent(event_bus=EventBus())
    return _coordinator


def _require_coordinator(request: Request) -> Any:
    coordinator = get_coordinator(request)
    if coordinator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Coordinator is not initialized (lifespan not executed).",
        )
    return coordinator


def format_sse_event(data: dict[str, Any], event_type: str | None = None) -> str:
    """格式化 SSE 事件

    参数：
        data: 事件数据
        event_type: 可选的事件类型

    返回：
        格式化的 SSE 消息
    """
    message = ""
    if event_type:
        message += f"event: {event_type}\n"
    message += f"data: {json.dumps(data, default=str)}\n\n"
    return message


def format_sse_done() -> str:
    """格式化 SSE 完成事件

    返回：
        完成消息
    """
    return "data: [DONE]\n\n"


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(request: Request) -> SystemStatusResponse:
    """获取系统状态摘要

    返回协调者维护的系统状态，包括：
    - 工作流统计（总数、运行中、已完成、失败）
    - 活跃节点数
    - 决策统计
    """
    coordinator = get_coordinator(request)
    status_data = coordinator.get_system_status() if coordinator is not None else {}

    return SystemStatusResponse(
        total_workflows=status_data.get("total_workflows", 0),
        running_workflows=status_data.get("running_workflows", 0),
        completed_workflows=status_data.get("completed_workflows", 0),
        failed_workflows=status_data.get("failed_workflows", 0),
        active_nodes=status_data.get("active_nodes", 0),
        decision_statistics=status_data.get(
            "decision_statistics",
            {"total": 0, "passed": 0, "rejected": 0, "rejection_rate": 0.0},
        ),
    )


@router.get("/workflows", response_model=WorkflowListResponse)
async def get_all_workflows(request: Request) -> WorkflowListResponse:
    """获取所有工作流状态

    返回所有正在监控的工作流的状态列表。
    """
    coordinator = get_coordinator(request)
    if coordinator is None:
        return WorkflowListResponse(workflows=[], total=0)
    all_states = coordinator.get_all_workflow_states()

    workflows = []
    for wf_id, state in all_states.items():
        workflows.append(
            WorkflowStateResponse(
                workflow_id=state.get("workflow_id", wf_id),
                status=state.get("status", "unknown"),
                node_count=state.get("node_count", 0),
                executed_nodes=state.get("executed_nodes", []),
                running_nodes=state.get("running_nodes", []),
                failed_nodes=state.get("failed_nodes", []),
                node_inputs=state.get("node_inputs", {}),
                node_outputs=state.get("node_outputs", {}),
                node_errors=state.get("node_errors", {}),
                started_at=state.get("started_at"),
                completed_at=state.get("completed_at"),
                result=state.get("result"),
            )
        )

    return WorkflowListResponse(workflows=workflows, total=len(workflows))


@router.get("/workflows/{workflow_id}", response_model=WorkflowStateResponse)
async def get_workflow_state(request: Request, workflow_id: str) -> WorkflowStateResponse:
    """获取单个工作流状态

    参数：
        workflow_id: 工作流ID

    返回：
        工作流状态快照

    异常：
        404: 工作流不存在
    """
    coordinator = _require_coordinator(request)
    state = coordinator.get_workflow_state(workflow_id)

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found",
        )

    return WorkflowStateResponse(
        workflow_id=state.get("workflow_id", workflow_id),
        status=state.get("status", "unknown"),
        node_count=state.get("node_count", 0),
        executed_nodes=state.get("executed_nodes", []),
        running_nodes=state.get("running_nodes", []),
        failed_nodes=state.get("failed_nodes", []),
        node_inputs=state.get("node_inputs", {}),
        node_outputs=state.get("node_outputs", {}),
        node_errors=state.get("node_errors", {}),
        started_at=state.get("started_at"),
        completed_at=state.get("completed_at"),
        result=state.get("result"),
    )


@router.get("/workflows/{workflow_id}/stream")
async def stream_workflow_status(
    request: Request,
    workflow_id: str,
    poll_interval: float = Query(default=1.0, ge=0.1, le=10.0, description="轮询间隔（秒）"),
    timeout: float = Query(default=300.0, ge=1.0, le=3600.0, description="超时时间（秒）"),
) -> StreamingResponse:
    """SSE 实时推送工作流状态

    通过 Server-Sent Events 实时推送工作流状态变化。

    参数：
        workflow_id: 工作流ID
        poll_interval: 轮询间隔（秒），默认1秒
        timeout: 超时时间（秒），默认300秒

    返回：
        SSE 流响应

    事件格式：
        - status_update: 状态更新
        - node_started: 节点开始执行
        - node_completed: 节点执行完成
        - node_failed: 节点执行失败
        - workflow_completed: 工作流完成
    """

    coordinator = _require_coordinator(request)

    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = datetime.now()
        last_state: dict[str, Any] | None = None

        while True:
            # 检查超时
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                yield format_sse_event(
                    {"type": "timeout", "message": "Stream timeout"},
                    event_type="timeout",
                )
                yield format_sse_done()
                break

            # 获取当前状态
            current_state = coordinator.get_workflow_state(workflow_id)

            if current_state is None:
                yield format_sse_event(
                    {"type": "error", "message": f"Workflow {workflow_id} not found"},
                    event_type="error",
                )
                yield format_sse_done()
                break

            # 检测状态变化
            if last_state is None or current_state != last_state:
                # 发送状态更新
                yield format_sse_event(
                    {
                        "type": "status_update",
                        "workflow_id": workflow_id,
                        "status": current_state.get("status"),
                        "executed_nodes": current_state.get("executed_nodes", []),
                        "running_nodes": current_state.get("running_nodes", []),
                        "failed_nodes": current_state.get("failed_nodes", []),
                        "node_outputs": current_state.get("node_outputs", {}),
                        "timestamp": datetime.now().isoformat(),
                    },
                    event_type="status_update",
                )

                # 检测具体变化并发送对应事件
                if last_state:
                    # 检测新运行的节点
                    new_running = set(current_state.get("running_nodes", [])) - set(
                        last_state.get("running_nodes", [])
                    )
                    for node_id in new_running:
                        yield format_sse_event(
                            {
                                "type": "node_started",
                                "workflow_id": workflow_id,
                                "node_id": node_id,
                                "timestamp": datetime.now().isoformat(),
                            },
                            event_type="node_started",
                        )

                    # 检测完成的节点
                    new_completed = set(current_state.get("executed_nodes", [])) - set(
                        last_state.get("executed_nodes", [])
                    )
                    for node_id in new_completed:
                        yield format_sse_event(
                            {
                                "type": "node_completed",
                                "workflow_id": workflow_id,
                                "node_id": node_id,
                                "output": current_state.get("node_outputs", {}).get(node_id),
                                "timestamp": datetime.now().isoformat(),
                            },
                            event_type="node_completed",
                        )

                    # 检测失败的节点
                    new_failed = set(current_state.get("failed_nodes", [])) - set(
                        last_state.get("failed_nodes", [])
                    )
                    for node_id in new_failed:
                        yield format_sse_event(
                            {
                                "type": "node_failed",
                                "workflow_id": workflow_id,
                                "node_id": node_id,
                                "error": current_state.get("node_errors", {}).get(node_id),
                                "timestamp": datetime.now().isoformat(),
                            },
                            event_type="node_failed",
                        )

                last_state = current_state.copy()

            # 检查工作流是否完成
            if current_state.get("status") in ("completed", "failed"):
                yield format_sse_event(
                    {
                        "type": "workflow_completed",
                        "workflow_id": workflow_id,
                        "status": current_state.get("status"),
                        "result": current_state.get("result"),
                        "timestamp": datetime.now().isoformat(),
                    },
                    event_type="workflow_completed",
                )
                yield format_sse_done()
                break

            # 等待下一次轮询
            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==================== 上下文压缩 API（阶段2新增） ====================


@router.get("/workflows/{workflow_id}/context", response_model=CompressedContextResponse)
async def get_compressed_context(request: Request, workflow_id: str) -> CompressedContextResponse:
    """获取工作流的压缩上下文

    返回八段压缩结构的上下文数据。

    参数：
        workflow_id: 工作流ID

    返回：
        压缩上下文响应

    异常：
        404: 上下文不存在或压缩未启用
    """
    coordinator = _require_coordinator(request)
    context = coordinator.get_compressed_context(workflow_id)

    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Context for workflow {workflow_id} not found",
        )

    # 获取摘要文本
    summary_text = coordinator.get_context_summary_text(workflow_id) or ""

    return CompressedContextResponse(
        workflow_id=context.workflow_id,
        version=context.version,
        created_at=context.created_at.isoformat(),
        task_goal=context.task_goal,
        execution_status=context.execution_status,
        node_summary=context.node_summary,
        decision_history=context.decision_history,
        reflection_summary=context.reflection_summary,
        conversation_summary=context.conversation_summary,
        error_log=context.error_log,
        next_actions=context.next_actions,
        summary_text=summary_text,
        evidence_refs=context.evidence_refs,
    )


@router.get("/workflows/{workflow_id}/context/history", response_model=ContextHistoryResponse)
async def get_context_history(request: Request, workflow_id: str) -> ContextHistoryResponse:
    """获取工作流的上下文历史

    返回工作流的所有上下文快照列表。

    参数：
        workflow_id: 工作流ID

    返回：
        上下文历史响应
    """
    coordinator = _require_coordinator(request)

    if not coordinator.snapshot_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snapshot manager not available",
        )

    snapshots = coordinator.snapshot_manager.list_snapshots(workflow_id)

    snapshot_items = []
    for snap in snapshots:
        snapshot_items.append(
            ContextSnapshotItem(
                snapshot_id=f"snap_{snap.workflow_id}_{snap.version}",
                workflow_id=snap.workflow_id,
                version=snap.version,
                created_at=snap.created_at.isoformat(),
                task_goal=snap.task_goal,
            )
        )

    return ContextHistoryResponse(
        workflow_id=workflow_id,
        snapshots=snapshot_items,
        total=len(snapshot_items),
    )


@router.get("/workflows/{workflow_id}/context/stream")
async def stream_context_updates(
    request: Request,
    workflow_id: str,
    poll_interval: float = Query(default=1.0, ge=0.1, le=10.0, description="轮询间隔（秒）"),
    timeout: float = Query(default=60.0, ge=1.0, le=300.0, description="超时时间（秒）"),
) -> StreamingResponse:
    """SSE 实时推送上下文更新

    通过 Server-Sent Events 实时推送上下文变化。

    参数：
        workflow_id: 工作流ID
        poll_interval: 轮询间隔（秒），默认1秒
        timeout: 超时时间（秒），默认60秒

    返回：
        SSE 流响应

    事件格式：
        - context_update: 上下文更新
        - initial_context: 初始上下文
    """

    coordinator = _require_coordinator(request)

    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = datetime.now()
        last_version: int | None = None

        # 发送初始上下文
        context = coordinator.get_compressed_context(workflow_id)
        if context:
            summary_text = coordinator.get_context_summary_text(workflow_id) or ""
            yield format_sse_event(
                {
                    "type": "initial_context",
                    "workflow_id": workflow_id,
                    "version": context.version,
                    "task_goal": context.task_goal,
                    "execution_status": context.execution_status,
                    "node_summary": context.node_summary,
                    "reflection_summary": context.reflection_summary,
                    "summary_text": summary_text,
                    "timestamp": datetime.now().isoformat(),
                },
                event_type="initial_context",
            )
            last_version = context.version

        while True:
            # 检查超时
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                yield format_sse_event(
                    {"type": "timeout", "message": "Stream timeout"},
                    event_type="timeout",
                )
                yield format_sse_done()
                break

            # 获取当前上下文
            current_context = coordinator.get_compressed_context(workflow_id)

            if current_context is None:
                # 上下文不存在，发送错误并结束
                yield format_sse_event(
                    {"type": "error", "message": f"Context for {workflow_id} not found"},
                    event_type="error",
                )
                yield format_sse_done()
                break

            # 检测版本变化
            if last_version is None or current_context.version > last_version:
                summary_text = coordinator.get_context_summary_text(workflow_id) or ""
                yield format_sse_event(
                    {
                        "type": "context_update",
                        "workflow_id": workflow_id,
                        "version": current_context.version,
                        "task_goal": current_context.task_goal,
                        "execution_status": current_context.execution_status,
                        "node_summary": current_context.node_summary,
                        "reflection_summary": current_context.reflection_summary,
                        "error_log": current_context.error_log,
                        "next_actions": current_context.next_actions,
                        "summary_text": summary_text,
                        "timestamp": datetime.now().isoformat(),
                    },
                    event_type="context_update",
                )
                last_version = current_context.version

            # 检查工作流是否完成
            workflow_state = coordinator.get_workflow_state(workflow_id)
            if workflow_state and workflow_state.get("status") in ("completed", "failed"):
                yield format_sse_event(
                    {
                        "type": "workflow_completed",
                        "workflow_id": workflow_id,
                        "status": workflow_state.get("status"),
                        "timestamp": datetime.now().isoformat(),
                    },
                    event_type="workflow_completed",
                )
                yield format_sse_done()
                break

            # 等待下一次轮询
            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# 导出
__all__ = [
    "router",
    "format_sse_event",
    "format_sse_done",
]

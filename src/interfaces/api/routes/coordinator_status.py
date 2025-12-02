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

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from src.domain.agents.coordinator_agent import CoordinatorAgent
from src.domain.services.event_bus import EventBus
from src.interfaces.api.dto.coordinator_dto import (
    SystemStatusResponse,
    WorkflowListResponse,
    WorkflowStateResponse,
)

router = APIRouter(tags=["coordinator"])

# 全局协调者实例（应用启动时初始化）
_coordinator: CoordinatorAgent | None = None
_event_bus: EventBus | None = None


def init_coordinator(event_bus: EventBus) -> CoordinatorAgent:
    """初始化全局协调者

    参数：
        event_bus: 事件总线

    返回：
        协调者实例
    """
    global _coordinator, _event_bus
    _event_bus = event_bus
    _coordinator = CoordinatorAgent(event_bus=event_bus)
    _coordinator.start_monitoring()
    return _coordinator


def get_coordinator() -> CoordinatorAgent:
    """获取协调者实例

    返回：
        协调者实例

    异常：
        HTTPException: 如果协调者未初始化
    """
    global _coordinator
    if _coordinator is None:
        # 如果未初始化，创建一个默认的
        event_bus = EventBus()
        _coordinator = CoordinatorAgent(event_bus=event_bus)
        _coordinator.start_monitoring()
    return _coordinator


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
async def get_system_status() -> SystemStatusResponse:
    """获取系统状态摘要

    返回协调者维护的系统状态，包括：
    - 工作流统计（总数、运行中、已完成、失败）
    - 活跃节点数
    - 决策统计
    """
    coordinator = get_coordinator()
    status_data = coordinator.get_system_status()

    return SystemStatusResponse(
        total_workflows=status_data.get("total_workflows", 0),
        running_workflows=status_data.get("running_workflows", 0),
        completed_workflows=status_data.get("completed_workflows", 0),
        failed_workflows=status_data.get("failed_workflows", 0),
        active_nodes=status_data.get("active_nodes", 0),
        decision_statistics=status_data.get("decision_statistics", {}),
    )


@router.get("/workflows", response_model=WorkflowListResponse)
async def get_all_workflows() -> WorkflowListResponse:
    """获取所有工作流状态

    返回所有正在监控的工作流的状态列表。
    """
    coordinator = get_coordinator()
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
async def get_workflow_state(workflow_id: str) -> WorkflowStateResponse:
    """获取单个工作流状态

    参数：
        workflow_id: 工作流ID

    返回：
        工作流状态快照

    异常：
        404: 工作流不存在
    """
    coordinator = get_coordinator()
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

    async def event_generator() -> AsyncGenerator[str, None]:
        coordinator = get_coordinator()
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


# 导出
__all__ = [
    "router",
    "init_coordinator",
    "get_coordinator",
    "format_sse_event",
    "format_sse_done",
]

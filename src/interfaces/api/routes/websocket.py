"""WebSocket 路由 - Canvas 实时同步

提供工作流画布的实时同步功能：
- 节点 CRUD 同步
- 边 CRUD 同步
- 执行状态同步
- 多客户端协作

使用示例：
    # 前端连接
    const ws = new WebSocket('ws://localhost:8000/ws/workflows/wf_123');

    # 接收消息
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        switch(data.type) {
            case 'node_created': // 处理节点创建
            case 'node_updated': // 处理节点更新
            case 'node_deleted': // 处理节点删除
            case 'execution_status': // 处理执行状态
        }
    };

    # 发送消息
    ws.send(JSON.stringify({
        action: 'create_node',
        node: { id: 'node_1', type: 'llm', position: {x: 100, y: 200} }
    }));
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.websocket.canvas_sync import (
    CanvasSyncService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# 全局 Canvas 同步服务实例
_canvas_sync_service: CanvasSyncService | None = None


def get_canvas_sync_service() -> CanvasSyncService:
    """获取 Canvas 同步服务单例"""
    global _canvas_sync_service
    if _canvas_sync_service is None:
        _canvas_sync_service = CanvasSyncService()
    return _canvas_sync_service


@router.websocket("/ws/workflows/{workflow_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    workflow_id: str,
    client_id: str | None = None,
):
    """WebSocket 端点 - 工作流画布同步

    参数：
        websocket: WebSocket 连接
        workflow_id: 工作流 ID
        client_id: 客户端 ID（可选，自动生成）

    消息格式（客户端 → 服务器）：
        {
            "action": "create_node" | "update_node" | "delete_node" |
                      "move_node" | "create_edge" | "delete_edge" |
                      "start_execution",
            "node": {...},  // 创建节点时
            "node_id": "...",  // 更新/删除节点时
            "changes": {...},  // 更新节点时
            "position": {...},  // 移动节点时
            "edge": {...},  // 创建边时
            "edge_id": "..."  // 删除边时
        }

    消息格式（服务器 → 客户端）：
        {
            "type": "initial_state" | "node_created" | "node_updated" |
                    "node_deleted" | "node_moved" | "edge_created" |
                    "edge_deleted" | "execution_status" | "workflow_started" |
                    "workflow_completed" | "error",
            "workflow_id": "...",
            "timestamp": "...",
            // 其他字段根据 type 不同
        }
    """
    service = get_canvas_sync_service()

    # 连接并发送初始状态
    client = await service.connection_manager.connect(
        websocket=websocket,
        workflow_id=workflow_id,
        client_id=client_id,
        send_initial_state=True,
    )

    logger.info(f"WebSocket 连接建立: workflow={workflow_id}, client={client.client_id}")

    try:
        while True:
            # 接收客户端消息
            try:
                data = await websocket.receive_json()
            except Exception as e:
                logger.warning(f"接收消息失败: {e}")
                break

            # 处理客户端消息
            await _handle_client_message(
                service=service,
                websocket=websocket,
                workflow_id=workflow_id,
                client_id=client.client_id,
                data=data,
            )

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: workflow={workflow_id}, client={client.client_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
    finally:
        service.connection_manager.disconnect(websocket)


async def _handle_client_message(
    service: CanvasSyncService,
    websocket: WebSocket,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理客户端消息

    参数：
        service: Canvas 同步服务
        websocket: 当前 WebSocket 连接
        workflow_id: 工作流 ID
        client_id: 客户端 ID
        data: 消息数据
    """
    action = data.get("action")

    if not action:
        await _send_error(websocket, "Missing 'action' field")
        return

    try:
        if action == "create_node":
            await _handle_create_node(service, workflow_id, client_id, data)
        elif action == "update_node":
            await _handle_update_node(service, workflow_id, client_id, data)
        elif action == "delete_node":
            await _handle_delete_node(service, workflow_id, client_id, data)
        elif action == "move_node":
            await _handle_move_node(service, workflow_id, client_id, data)
        elif action == "create_edge":
            await _handle_create_edge(service, workflow_id, client_id, data)
        elif action == "delete_edge":
            await _handle_delete_edge(service, workflow_id, client_id, data)
        elif action == "start_execution":
            await _handle_start_execution(service, workflow_id, client_id, data)
        else:
            await _send_error(websocket, f"Unknown action: {action}")

    except Exception as e:
        logger.error(f"处理消息失败: action={action}, error={e}")
        await _send_error(websocket, str(e))


async def _handle_create_node(
    service: CanvasSyncService,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理创建节点"""
    node = data.get("node", {})
    node_id = node.get("id")
    node_type = node.get("type", "default")
    position = node.get("position", {"x": 0, "y": 0})
    config = node.get("config", {})

    if not node_id:
        raise ValueError("Node ID is required")

    await service.sync_node_created(
        workflow_id=workflow_id,
        node_id=node_id,
        node_type=node_type,
        position=position,
        config=config,
    )

    logger.debug(f"节点创建同步: node_id={node_id}")


async def _handle_update_node(
    service: CanvasSyncService,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理更新节点"""
    node_id = data.get("node_id")
    changes = data.get("changes", {})

    if not node_id:
        raise ValueError("Node ID is required")

    await service.sync_node_updated(
        workflow_id=workflow_id,
        node_id=node_id,
        changes=changes,
    )

    logger.debug(f"节点更新同步: node_id={node_id}")


async def _handle_delete_node(
    service: CanvasSyncService,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理删除节点"""
    node_id = data.get("node_id")

    if not node_id:
        raise ValueError("Node ID is required")

    await service.sync_node_deleted(
        workflow_id=workflow_id,
        node_id=node_id,
    )

    logger.debug(f"节点删除同步: node_id={node_id}")


async def _handle_move_node(
    service: CanvasSyncService,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理移动节点"""
    node_id = data.get("node_id")
    position = data.get("position", {})

    if not node_id:
        raise ValueError("Node ID is required")

    # 使用 node_updated 来同步位置变化
    await service.connection_manager.broadcast(
        workflow_id=workflow_id,
        message={
            "type": "node_moved",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "position": position,
            "timestamp": datetime.now().isoformat(),
        },
        exclude_client=client_id,  # 不广播给发送者自己
    )

    logger.debug(f"节点移动同步: node_id={node_id}")


async def _handle_create_edge(
    service: CanvasSyncService,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理创建边"""
    edge = data.get("edge", {})
    edge_id = edge.get("id")
    source_id = edge.get("source")
    target_id = edge.get("target")

    if not all([edge_id, source_id, target_id]):
        raise ValueError("Edge ID, source, and target are required")

    await service.sync_edge_created(
        workflow_id=workflow_id,
        edge_id=edge_id,
        source_id=source_id,
        target_id=target_id,
    )

    logger.debug(f"边创建同步: edge_id={edge_id}")


async def _handle_delete_edge(
    service: CanvasSyncService,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理删除边"""
    edge_id = data.get("edge_id")

    if not edge_id:
        raise ValueError("Edge ID is required")

    await service.sync_edge_deleted(
        workflow_id=workflow_id,
        edge_id=edge_id,
    )

    logger.debug(f"边删除同步: edge_id={edge_id}")


async def _handle_start_execution(
    service: CanvasSyncService,
    workflow_id: str,
    client_id: str,
    data: dict[str, Any],
) -> None:
    """处理开始执行"""
    # 广播工作流开始执行消息
    await service.connection_manager.broadcast(
        workflow_id=workflow_id,
        message={
            "type": "workflow_started",
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat(),
        },
    )

    logger.debug(f"工作流执行开始: workflow_id={workflow_id}")


async def _send_error(websocket: WebSocket, message: str) -> None:
    """发送错误消息"""
    try:
        await websocket.send_json(
            {
                "type": "error",
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.warning(f"发送错误消息失败: {e}")

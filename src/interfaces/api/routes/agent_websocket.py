"""Agent WebSocket 路由 - Phase 4

提供 Agent 对话/工作流互动的 WebSocket 端点：
- 客户端发送任务请求
- ConversationAgent 推送计划
- WorkflowAgent 执行并返回结果
- 实时进度反馈

使用示例：
    # 前端连接
    const ws = new WebSocket('ws://localhost:8000/ws/agent/session_123');

    # 发送任务
    ws.send(JSON.stringify({
        type: 'task_request',
        payload: { query: '帮我分析销售数据' }
    }));

    # 接收消息
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        switch(data.type) {
            case 'plan_proposed': // 计划提议
            case 'execution_started': // 开始执行
            case 'execution_progress': // 进度更新
            case 'execution_completed': // 执行完成
            case 'execution_failed': // 执行失败
        }
    };
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.domain.agents.agent_channel import (
    AgentChannelBridge,
    AgentMessage,
    AgentMessageHandler,
    AgentWebSocketChannel,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent-websocket"])

# 全局 Agent 通信信道
_agent_channel: AgentWebSocketChannel | None = None
_agent_bridge: AgentChannelBridge | None = None
_message_handler: AgentMessageHandler | None = None


def get_agent_channel() -> AgentWebSocketChannel:
    """获取 Agent 通信信道单例"""
    global _agent_channel
    if _agent_channel is None:
        _agent_channel = AgentWebSocketChannel()
    return _agent_channel


def get_agent_bridge() -> AgentChannelBridge:
    """获取 Agent 通信桥接单例"""
    global _agent_bridge
    if _agent_bridge is None:
        _agent_bridge = AgentChannelBridge(channel=get_agent_channel())
    return _agent_bridge


def get_message_handler() -> AgentMessageHandler:
    """获取消息处理器单例"""
    global _message_handler
    if _message_handler is None:
        _message_handler = AgentMessageHandler(channel=get_agent_channel())
        _setup_message_handlers(_message_handler)
    return _message_handler


def _setup_message_handlers(handler: AgentMessageHandler) -> None:
    """设置消息处理器回调"""

    async def on_task_request(session_id: str, payload: dict) -> dict:
        """处理任务请求"""
        query = payload.get("query", "")
        logger.info(f"Task request received: session={session_id}, query={query}")

        # 获取桥接器
        bridge = get_agent_bridge()

        # 模拟 ConversationAgent 处理
        # 1. 分析任务并生成计划
        plan_summary = f"任务：{query}"
        estimated_steps = 3

        # 2. 通知客户端计划
        await bridge.notify_plan_proposed(
            session_id=session_id,
            plan_summary=plan_summary,
            estimated_steps=estimated_steps,
        )

        return {"status": "plan_proposed", "task_id": f"task_{session_id}"}

    async def on_cancel_task(session_id: str, task_id: str) -> None:
        """处理取消任务"""
        logger.info(f"Task cancelled: session={session_id}, task_id={task_id}")

    async def on_plan_approved(session_id: str, plan_id: str) -> None:
        """处理计划批准 - 开始执行"""
        logger.info(f"Plan approved: session={session_id}, plan_id={plan_id}")
        bridge = get_agent_bridge()

        # 模拟 WorkflowAgent 执行
        workflow_id = f"wf_{plan_id}"

        # 1. 通知开始执行
        await bridge.notify_execution_started(
            session_id=session_id,
            workflow_id=workflow_id,
        )

        # 2. 模拟执行进度
        import asyncio

        for i in range(3):
            await asyncio.sleep(0.1)
            await bridge.report_progress(
                session_id=session_id,
                workflow_id=workflow_id,
                current_node=f"node_{i + 1}",
                progress=(i + 1) / 3,
                message=f"执行步骤 {i + 1}/3",
            )

        # 3. 完成执行
        await bridge.report_completed(
            session_id=session_id,
            workflow_id=workflow_id,
            result={"success": True, "message": "任务执行完成"},
        )

    handler.on_task_request = on_task_request
    handler.on_cancel_task = on_cancel_task
    handler.on_plan_approved = on_plan_approved


@router.websocket("/ws/agent/{session_id}")
async def agent_websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: str | None = None,
):
    """Agent WebSocket 端点

    参数：
        websocket: WebSocket 连接
        session_id: 会话 ID
        user_id: 用户 ID（可选）

    消息格式（客户端 → 服务器）：
        {
            "type": "task_request" | "cancel_task" | "plan_approved",
            "payload": {...}
        }

    消息格式（服务器 → 客户端）：
        {
            "type": "plan_proposed" | "execution_started" |
                    "execution_progress" | "execution_completed" |
                    "execution_failed",
            "session_id": "...",
            "payload": {...},
            "message_id": "...",
            "timestamp": "..."
        }
    """
    channel = get_agent_channel()
    handler = get_message_handler()

    # 接受连接
    await websocket.accept()

    # 注册会话
    await channel.register_session(
        session_id=session_id,
        websocket=websocket,
        user_id=user_id or "anonymous",
    )

    logger.info(f"Agent WebSocket 连接建立: session={session_id}")

    try:
        while True:
            # 接收消息
            try:
                data = await websocket.receive_json()
            except Exception as e:
                logger.warning(f"接收消息失败: {e}")
                break

            # 解析消息
            try:
                msg = AgentMessage.from_dict(
                    {
                        **data,
                        "session_id": session_id,
                    }
                )
            except Exception as e:
                logger.error(f"消息解析失败: {e}")
                await _send_error(websocket, f"Invalid message format: {e}")
                continue

            # 处理消息
            result = await handler.handle_message(msg)

            # 如果有返回结果，发送确认
            if result:
                await websocket.send_json(
                    {
                        "type": "ack",
                        "message_id": msg.message_id,
                        "result": result,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"Agent WebSocket 断开: session={session_id}")
    except Exception as e:
        logger.error(f"Agent WebSocket 错误: {e}")
    finally:
        await channel.unregister_session(session_id)


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


# 导出辅助函数供其他模块使用
def execute_workflow_with_feedback(
    session_id: str,
    workflow_id: str,
    plan: dict[str, Any],
):
    """执行工作流并通过 WebSocket 反馈

    这个函数可以被 WorkflowAgent 调用。

    参数：
        session_id: 会话 ID
        workflow_id: 工作流 ID
        plan: 工作流计划
    """
    import asyncio

    async def _execute():
        bridge = get_agent_bridge()

        # 开始执行
        await bridge.notify_execution_started(session_id, workflow_id)

        nodes = plan.get("nodes", [])
        total = len(nodes) or 1

        for i, node in enumerate(nodes):
            # 报告进度
            await bridge.report_progress(
                session_id=session_id,
                workflow_id=workflow_id,
                current_node=node.get("id", f"node_{i}"),
                progress=(i + 1) / total,
                message=f"执行节点: {node.get('type', 'unknown')}",
            )
            await asyncio.sleep(0.1)

        # 完成
        await bridge.report_completed(
            session_id=session_id,
            workflow_id=workflow_id,
            result={"success": True, "nodes_executed": total},
        )

    asyncio.create_task(_execute())

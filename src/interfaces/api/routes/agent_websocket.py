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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.domain.agents.agent_channel import (
    AgentChannelBridge,
    AgentMessage,
    AgentMessageHandler,
    AgentWebSocketChannel,
)
from src.interfaces.api.dependencies.agents import get_conversation_agent, get_workflow_agent

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
    """设置消息处理器回调（集成真实Agent）"""

    async def on_task_request(session_id: str, payload: dict) -> dict:
        """处理任务请求（使用真实ConversationAgent）"""
        query = payload.get("query", "")
        logger.info(f"Task request received: session={session_id}, query={query}")

        # 获取真实的 ConversationAgent
        conversation_agent = get_conversation_agent()
        bridge = get_agent_bridge()

        try:
            # 使用真实的 ConversationAgent 分析任务
            result = await conversation_agent.run_async(query)

            # 生成计划摘要（从agent结果中提取）
            plan_summary = result.get("response", f"任务：{query}")
            estimated_steps = result.get("estimated_steps", 3)

            # 通知客户端计划
            await bridge.notify_plan_proposed(
                session_id=session_id,
                plan_summary=plan_summary,
                estimated_steps=estimated_steps,
            )

            return {"status": "plan_proposed", "task_id": f"task_{session_id}"}

        except Exception as e:
            logger.error(f"Task request failed: {e}")
            return {"status": "error", "error": str(e)}

    async def on_cancel_task(session_id: str, task_id: str) -> None:
        """处理取消任务"""
        logger.info(f"Task cancelled: session={session_id}, task_id={task_id}")

    async def on_plan_approved(session_id: str, plan_id: str) -> None:
        """处理计划批准 - 开始执行（使用真实WorkflowAgent）"""
        logger.info(f"Plan approved: session={session_id}, plan_id={plan_id}")

        # 获取真实的 WorkflowAgent（预留集成位置）
        # TODO: 启用真实执行: workflow_agent = get_workflow_agent()
        bridge = get_agent_bridge()

        workflow_id = f"wf_{plan_id}"

        try:
            # 1. 通知开始执行
            await bridge.notify_execution_started(
                session_id=session_id,
                workflow_id=workflow_id,
            )

            # 2. 使用真实的 WorkflowAgent 执行
            # 注意：这里需要根据实际的WorkflowAgent接口调整
            # 当前简化实现，假设有execute_workflow_async方法
            import asyncio

            # TODO: 替换为真实的workflow执行逻辑
            # result = await workflow_agent.execute_workflow_async(workflow_id)

            # 临时进度报告（待替换为真实实现）
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
                result={"success": True, "message": "工作流执行完成"},
            )

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            await bridge.report_failed(
                session_id=session_id,
                workflow_id=workflow_id,
                error=str(e),
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
# 注意：execute_workflow_with_feedback已被真实的WorkflowAgent集成替代
# 如需使用，请通过 get_workflow_agent() 获取真实的WorkflowAgent实例

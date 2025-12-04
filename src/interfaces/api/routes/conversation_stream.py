"""Conversation Stream API - Phase 3

提供使用 ConversationFlowEmitter 的流式对话端点。

端点:
- POST /conversation/stream: 流式对话，实时输出 Thought/Tool/Result
- GET /conversation/stream/{session_id}/status: 获取会话状态

特点:
- 使用 SSE (Server-Sent Events) 传输
- 实时输出 ReAct 循环的每个步骤
- 支持断开连接检测和清理
- 支持会话重连
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.domain.services.conversation_flow_emitter import (
    ConversationFlowEmitter,
)
from src.interfaces.api.services.sse_emitter_handler import (
    get_session_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["Conversation Stream"])


class ConversationStreamRequest(BaseModel):
    """流式对话请求"""

    message: str = Field(..., description="用户消息", min_length=1)
    session_id: str | None = Field(None, description="会话 ID（可选，用于重连）")
    workflow_id: str | None = Field(None, description="工作流 ID（可选）")
    context: dict[str, Any] | None = Field(None, description="上下文信息")


class SessionStatusResponse(BaseModel):
    """会话状态响应"""

    session_id: str
    is_active: bool
    is_completed: bool
    statistics: dict[str, Any]


@router.post("/stream")
async def stream_conversation(
    request: Request,
    body: ConversationStreamRequest,
) -> StreamingResponse:
    """流式对话端点

    使用 SSE 实时输出 ReAct 循环的每个步骤：
    - thinking: 思考过程
    - tool_call: 工具调用
    - tool_result: 工具执行结果
    - final: 最终响应

    请求体:
        message: 用户消息
        session_id: 会话 ID（可选）
        workflow_id: 工作流 ID（可选）
        context: 上下文信息

    响应:
        SSE 事件流，每个事件格式为:
        data: {"type": "thinking|tool_call|tool_result|final", "content": "...", ...}

    示例响应:
        data: {"type": "thinking", "content": "分析用户请求...", "sequence": 1}
        data: {"type": "tool_call", "metadata": {"tool_name": "search", ...}, "sequence": 2}
        data: {"type": "tool_result", "metadata": {"result": {...}}, "sequence": 3}
        data: {"type": "final", "content": "这是最终响应", "sequence": 4}
        data: [DONE]
    """
    session_manager = get_session_manager()

    # 生成或使用提供的 session_id
    session_id = body.session_id or f"conv_{id(request)}_{asyncio.get_event_loop().time()}"

    # 创建会话
    emitter, handler = await session_manager.create_session(
        session_id=session_id,
        request=request,
        timeout=30.0,  # 30 秒超时
    )

    async def run_conversation():
        """运行对话逻辑"""
        try:
            # 发送开始事件
            await emitter.emit_thinking(f"收到消息：{body.message[:50]}...")

            # TODO: 这里将集成真实的 ConversationAgent
            # 目前使用模拟的 ReAct 循环
            await simulate_react_loop(emitter, body.message, body.workflow_id)

        except Exception as e:
            logger.error(f"Conversation error: {e}")
            await emitter.emit_error(str(e), error_code="CONVERSATION_ERROR")
            await emitter.complete()

    async def simulate_react_loop(
        emitter: ConversationFlowEmitter,
        message: str,
        workflow_id: str | None,
    ):
        """模拟 ReAct 循环（用于测试）

        实际实现将调用 ConversationAgent.run_async()
        """
        # 模拟思考
        await asyncio.sleep(0.1)
        await emitter.emit_thinking("正在分析您的请求...")

        # 模拟工具调用（如果涉及工作流）
        if workflow_id:
            await asyncio.sleep(0.1)
            await emitter.emit_tool_call(
                tool_name="workflow_query",
                tool_id="wf_query_1",
                arguments={"workflow_id": workflow_id, "action": "analyze"},
            )

            await asyncio.sleep(0.1)
            await emitter.emit_tool_result(
                tool_id="wf_query_1",
                result={"status": "success", "nodes_count": 5},
                success=True,
            )

        # 模拟最终响应
        await asyncio.sleep(0.1)
        await emitter.emit_final_response(
            f"已处理您的请求：{message[:100]}。"
            + (f" 工作流 {workflow_id} 包含 5 个节点。" if workflow_id else "")
        )

        await emitter.complete()

    # 启动对话任务
    asyncio.create_task(run_conversation())

    # 返回 SSE 响应
    return handler.create_response(
        headers={"X-Session-ID": session_id},
    )


@router.get("/stream/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """获取会话状态

    参数:
        session_id: 会话 ID

    返回:
        会话状态信息
    """
    session_manager = get_session_manager()
    handler = await session_manager.get_session(session_id)

    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    return SessionStatusResponse(
        session_id=session_id,
        is_active=handler.emitter.is_active,
        is_completed=handler.emitter.is_completed,
        statistics=handler.emitter.get_statistics(),
    )


@router.delete("/stream/{session_id}")
async def cancel_session(session_id: str) -> dict[str, str]:
    """取消会话

    参数:
        session_id: 会话 ID

    返回:
        取消结果
    """
    session_manager = get_session_manager()
    await session_manager.remove_session(session_id)

    return {"status": "cancelled", "session_id": session_id}


# 添加到主路由时使用的健康检查端点
@router.get("/health")
async def conversation_health() -> dict[str, Any]:
    """健康检查"""
    session_manager = get_session_manager()
    return {
        "status": "healthy",
        "active_sessions": session_manager.active_sessions,
    }


# 导出路由
__all__ = ["router"]

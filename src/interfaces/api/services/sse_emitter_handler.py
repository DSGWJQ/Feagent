"""SSE Emitter Handler - Phase 3

将 ConversationFlowEmitter 与 SSE (Server-Sent Events) 响应集成。

职责:
1. 从 emitter 的 queue 中 await 消息
2. 转换为 SSE 格式发送给前端
3. 处理断开连接和清理
4. 支持取消令牌控制

使用示例:
    from src.interfaces.api.services.sse_emitter_handler import SSEEmitterHandler

    async def stream_endpoint(request: Request):
        emitter = ConversationFlowEmitter(session_id="session_1")
        handler = SSEEmitterHandler(emitter, request)

        # 启动 agent 工作
        asyncio.create_task(run_agent(emitter))

        # 返回 SSE 响应
        return handler.create_response()
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

from src.domain.services.conversation_flow_emitter import (
    ConversationFlowEmitter,
    ConversationStep,
    StepKind,
)

logger = logging.getLogger(__name__)


class SSEEmitterHandler:
    """SSE Emitter 处理器

    将 ConversationFlowEmitter 的输出转换为 SSE 流。

    属性:
        emitter: ConversationFlowEmitter 实例
        request: FastAPI Request 对象（可选，用于检测断开）
        include_metadata: 是否在事件中包含元数据
        heartbeat_interval: 心跳间隔（秒），None 表示不发送心跳
    """

    def __init__(
        self,
        emitter: ConversationFlowEmitter,
        request: Request | None = None,
        include_metadata: bool = True,
        heartbeat_interval: float | None = None,
    ):
        """初始化 SSE 处理器

        参数:
            emitter: ConversationFlowEmitter 实例
            request: FastAPI Request 对象，用于检测客户端断开
            include_metadata: 是否包含元数据
            heartbeat_interval: 心跳间隔（秒）
        """
        self.emitter = emitter
        self.request = request
        self.include_metadata = include_metadata
        self.heartbeat_interval = heartbeat_interval

        self._cancelled = asyncio.Event()
        self._cleanup_done = asyncio.Event()

    async def _check_client_disconnect(self) -> bool:
        """检查客户端是否断开连接

        返回:
            True 如果客户端已断开
        """
        if self.request is None:
            return False

        # FastAPI/Starlette 使用 is_disconnected 检测断开
        try:
            return await self.request.is_disconnected()
        except Exception:
            return False

    def _step_to_sse_event(self, step: ConversationStep) -> dict[str, Any]:
        """将 ConversationStep 转换为 SSE 事件数据

        参数:
            step: 会话步骤

        返回:
            SSE 事件数据字典
        """
        event = {
            "type": step.kind.value,
            "content": step.content,
            "sequence": step.sequence,
            "timestamp": step.timestamp.isoformat(),
        }

        if self.include_metadata:
            event["metadata"] = step.metadata

        if step.is_delta:
            event["is_delta"] = True
            event["delta_index"] = step.delta_index

        if step.is_final:
            event["is_final"] = True

        return event

    def _format_sse_message(self, data: dict[str, Any] | str) -> str:
        """格式化 SSE 消息

        参数:
            data: 事件数据

        返回:
            SSE 格式的字符串
        """
        if isinstance(data, str):
            return f"data: {data}\n\n"

        json_str = json.dumps(data, ensure_ascii=False)
        return f"data: {json_str}\n\n"

    async def _cleanup(self, reason: str = "completed") -> None:
        """清理资源

        参数:
            reason: 清理原因
        """
        if self._cleanup_done.is_set():
            return

        logger.debug(f"SSE cleanup: {reason}, session={self.emitter.session_id}")

        try:
            if not self.emitter.is_completed:
                if reason == "client_disconnected":
                    await self.emitter.complete_with_error("Client disconnected")
                else:
                    await self.emitter.complete()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        finally:
            self._cleanup_done.set()

    async def cancel(self) -> None:
        """取消 SSE 流

        设置取消标志并触发清理。
        """
        self._cancelled.set()
        await self._cleanup("cancelled")

    async def _generate_events(self) -> AsyncGenerator[str, None]:
        """生成 SSE 事件流

        Yields:
            SSE 格式的事件字符串
        """
        heartbeat_task = None

        try:
            # 启动心跳任务（如果配置）
            if self.heartbeat_interval:
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # 从 emitter 流式输出
            async for step in self.emitter:
                # 检查是否取消
                if self._cancelled.is_set():
                    logger.debug("SSE cancelled")
                    break

                # 检查客户端是否断开
                if await self._check_client_disconnect():
                    logger.info(f"Client disconnected: session={self.emitter.session_id}")
                    await self._cleanup("client_disconnected")
                    break

                # 处理结束标记
                if step.kind == StepKind.END:
                    yield self._format_sse_message("[DONE]")
                    break

                # 处理错误步骤
                if step.kind == StepKind.ERROR:
                    event = self._step_to_sse_event(step)
                    yield self._format_sse_message(event)
                    # 错误后继续，直到收到 END
                    continue

                # 发送正常事件
                event = self._step_to_sse_event(step)
                yield self._format_sse_message(event)

        except asyncio.CancelledError:
            logger.debug("SSE generator cancelled")
            await self._cleanup("cancelled")
        except Exception as e:
            logger.error(f"SSE generator error: {e}")
            error_event = {
                "type": "error",
                "content": str(e),
                "error_code": "SSE_ERROR",
            }
            yield self._format_sse_message(error_event)
        finally:
            # 取消心跳任务
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

            await self._cleanup("completed")

    async def _heartbeat_loop(self) -> None:
        """心跳循环

        定期发送心跳以保持连接活跃。
        """
        if not self.heartbeat_interval:
            return

        while not self._cancelled.is_set() and not self.emitter.is_completed:
            await asyncio.sleep(self.heartbeat_interval)
            if not self.emitter.is_completed:
                await self.emitter._queue.put(
                    ConversationStep(kind=StepKind.OBSERVATION, content="heartbeat")
                )

    def create_response(
        self,
        headers: dict[str, str] | None = None,
    ) -> StreamingResponse:
        """创建 SSE StreamingResponse

        参数:
            headers: 额外的响应头

        返回:
            StreamingResponse 对象
        """
        default_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }

        if headers:
            default_headers.update(headers)

        return StreamingResponse(
            self._generate_events(),
            media_type="text/event-stream",
            headers=default_headers,
        )


class SSESessionManager:
    """SSE 会话管理器

    管理多个 SSE 会话，支持重连。
    """

    def __init__(self):
        self._sessions: dict[str, SSEEmitterHandler] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        session_id: str,
        request: Request | None = None,
        timeout: float | None = None,
    ) -> tuple[ConversationFlowEmitter, SSEEmitterHandler]:
        """创建新会话

        参数:
            session_id: 会话 ID
            request: FastAPI Request
            timeout: 超时时间

        返回:
            (emitter, handler) 元组
        """
        async with self._lock:
            # 清理已完成的会话
            if session_id in self._sessions:
                old_handler = self._sessions[session_id]
                if old_handler.emitter.is_completed:
                    del self._sessions[session_id]
                else:
                    # 取消旧会话
                    await old_handler.cancel()
                    del self._sessions[session_id]

            # 创建新会话
            emitter = ConversationFlowEmitter(session_id=session_id, timeout=timeout)
            handler = SSEEmitterHandler(emitter, request)
            self._sessions[session_id] = handler

            return emitter, handler

    async def get_session(self, session_id: str) -> SSEEmitterHandler | None:
        """获取会话

        参数:
            session_id: 会话 ID

        返回:
            SSEEmitterHandler 或 None
        """
        async with self._lock:
            handler = self._sessions.get(session_id)
            if handler and handler.emitter.is_completed:
                del self._sessions[session_id]
                return None
            return handler

    async def remove_session(self, session_id: str) -> None:
        """移除会话

        参数:
            session_id: 会话 ID
        """
        async with self._lock:
            if session_id in self._sessions:
                handler = self._sessions[session_id]
                await handler.cancel()
                del self._sessions[session_id]

    async def cleanup_completed(self) -> int:
        """清理已完成的会话

        返回:
            清理的会话数量
        """
        async with self._lock:
            to_remove = [
                sid for sid, handler in self._sessions.items() if handler.emitter.is_completed
            ]
            for sid in to_remove:
                del self._sessions[sid]
            return len(to_remove)

    @property
    def active_sessions(self) -> int:
        """活跃会话数量"""
        return len([h for h in self._sessions.values() if not h.emitter.is_completed])


# 全局会话管理器实例
_session_manager: SSESessionManager | None = None


def get_session_manager() -> SSESessionManager:
    """获取全局会话管理器"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SSESessionManager()
    return _session_manager


# 导出
__all__ = [
    "SSEEmitterHandler",
    "SSESessionManager",
    "get_session_manager",
]

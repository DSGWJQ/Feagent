"""Agent WebSocket 通信信道 - Phase 4

业务定义：
- AgentMessageType: Agent 间通信消息类型
- AgentMessage: 消息结构
- AgentWebSocketChannel: WebSocket 信道管理
- AgentChannelBridge: Agent 间通信桥接
- AgentMessageHandler: 消息处理器

支持场景：
1. 客户端 → 服务器：任务请求、取消任务
2. 服务器 → 客户端：计划提议、执行进度、执行结果
3. ConversationAgent → WorkflowAgent：工作流分发
4. WorkflowAgent → ConversationAgent：执行反馈

使用示例：
    channel = AgentWebSocketChannel()
    bridge = AgentChannelBridge(channel=channel)

    # 注册客户端会话
    await channel.register_session("session_1", websocket, "user_1")

    # 分发计划到 WorkflowAgent
    await bridge.dispatch_plan_to_workflow(session_id, plan)

    # 报告执行进度
    await bridge.report_progress(session_id, workflow_id, node_id, 0.5, "处理中")
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ==================== 消息类型 ====================


class AgentMessageType(str, Enum):
    """Agent 消息类型

    定义 Agent 间通信的所有消息类型。
    """

    # 客户端 → 服务器
    TASK_REQUEST = "task_request"  # 任务请求
    CANCEL_TASK = "cancel_task"  # 取消任务
    PLAN_APPROVED = "plan_approved"  # 计划批准

    # 服务器 → 客户端
    PLAN_PROPOSED = "plan_proposed"  # 计划提议
    EXECUTION_STARTED = "execution_started"  # 执行开始
    EXECUTION_PROGRESS = "execution_progress"  # 执行进度
    EXECUTION_COMPLETED = "execution_completed"  # 执行完成
    EXECUTION_FAILED = "execution_failed"  # 执行失败

    # Agent 间通信
    WORKFLOW_DISPATCH = "workflow_dispatch"  # 工作流分发
    WORKFLOW_RESULT = "workflow_result"  # 工作流结果

    # 系统消息
    ERROR = "error"  # 错误
    HEARTBEAT = "heartbeat"  # 心跳
    EXECUTION_SUMMARY = "execution_summary"  # 执行总结（Phase 5）


# ==================== 消息结构 ====================


@dataclass
class AgentMessage:
    """Agent 消息

    属性：
        type: 消息类型
        session_id: 会话ID
        payload: 消息负载
        message_id: 消息ID
        timestamp: 时间戳
    """

    type: AgentMessageType
    session_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "payload": self.payload,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        """从字典创建消息"""
        msg_type = data.get("type", "")

        # 查找匹配的枚举值
        try:
            message_type = AgentMessageType(msg_type)
        except ValueError:
            message_type = AgentMessageType.ERROR

        return cls(
            type=message_type,
            session_id=data.get("session_id", ""),
            payload=data.get("payload", {}),
            message_id=data.get("message_id", f"msg_{uuid4().hex[:12]}"),
        )


# ==================== WebSocket 信道 ====================


class AgentWebSocketChannel:
    """Agent WebSocket 信道

    管理 Agent 与客户端之间的 WebSocket 连接。
    """

    def __init__(self):
        """初始化信道"""
        self._sessions: dict[str, dict[str, Any]] = {}

    @property
    def active_sessions(self) -> dict[str, dict[str, Any]]:
        """获取活跃会话"""
        return self._sessions

    async def register_session(
        self,
        session_id: str,
        websocket: Any,
        user_id: str,
    ) -> None:
        """注册会话

        参数：
            session_id: 会话ID
            websocket: WebSocket 连接
            user_id: 用户ID
        """
        self._sessions[session_id] = {
            "websocket": websocket,
            "user_id": user_id,
            "connected_at": datetime.now(),
        }
        logger.info(f"Session registered: {session_id}, user: {user_id}")

    async def unregister_session(self, session_id: str) -> None:
        """注销会话

        参数：
            session_id: 会话ID
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session unregistered: {session_id}")

    async def send_to_session(
        self,
        session_id: str,
        message: AgentMessage,
    ) -> bool:
        """向指定会话发送消息

        参数：
            session_id: 会话ID
            message: 消息

        返回：
            是否发送成功
        """
        if session_id not in self._sessions:
            logger.warning(f"Session not found: {session_id}")
            return False

        try:
            ws = self._sessions[session_id]["websocket"]
            await ws.send_json(message.to_dict())
            logger.debug(f"Message sent to {session_id}: {message.type.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {session_id}: {e}")
            return False

    async def broadcast(
        self,
        message: AgentMessage,
        exclude_session: str | None = None,
    ) -> int:
        """广播消息到所有会话

        参数：
            message: 消息
            exclude_session: 排除的会话ID

        返回：
            成功发送的会话数
        """
        sent_count = 0

        for session_id, session_data in self._sessions.items():
            if exclude_session and session_id == exclude_session:
                continue

            try:
                ws = session_data["websocket"]
                await ws.send_json(message.to_dict())
                sent_count += 1
            except Exception as e:
                logger.error(f"Broadcast failed to {session_id}: {e}")

        logger.debug(f"Broadcast complete: {sent_count} sessions")
        return sent_count

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """获取会话信息

        参数：
            session_id: 会话ID

        返回：
            会话信息或 None
        """
        return self._sessions.get(session_id)


# ==================== 通信桥接 ====================


class AgentChannelBridge:
    """Agent 通信桥接

    提供 ConversationAgent 与 WorkflowAgent 之间的通信接口。
    """

    def __init__(self, channel: AgentWebSocketChannel):
        """初始化桥接

        参数：
            channel: WebSocket 信道
        """
        self._channel = channel
        self._workflow_handlers: dict[str, Callable] = {}

    async def dispatch_plan_to_workflow(
        self,
        session_id: str,
        plan: dict[str, Any],
    ) -> AgentMessage:
        """分发计划到 WorkflowAgent

        参数：
            session_id: 会话ID
            plan: 工作流计划

        返回：
            发送的消息
        """
        msg = AgentMessage(
            type=AgentMessageType.WORKFLOW_DISPATCH,
            session_id=session_id,
            payload=plan,
        )

        logger.info(f"Dispatching plan to workflow: session={session_id}")
        return msg

    async def notify_plan_proposed(
        self,
        session_id: str,
        plan_summary: str,
        estimated_steps: int,
    ) -> None:
        """通知客户端计划已提议

        参数：
            session_id: 会话ID
            plan_summary: 计划摘要
            estimated_steps: 预计步骤数
        """
        msg = AgentMessage(
            type=AgentMessageType.PLAN_PROPOSED,
            session_id=session_id,
            payload={
                "summary": plan_summary,
                "estimated_steps": estimated_steps,
            },
        )

        await self._channel.send_to_session(session_id, msg)
        logger.info(f"Plan proposed: session={session_id}, steps={estimated_steps}")

    async def notify_execution_started(
        self,
        session_id: str,
        workflow_id: str,
    ) -> None:
        """通知执行开始

        参数：
            session_id: 会话ID
            workflow_id: 工作流ID
        """
        msg = AgentMessage(
            type=AgentMessageType.EXECUTION_STARTED,
            session_id=session_id,
            payload={
                "workflow_id": workflow_id,
            },
        )

        await self._channel.send_to_session(session_id, msg)
        logger.info(f"Execution started: workflow={workflow_id}")

    async def report_progress(
        self,
        session_id: str,
        workflow_id: str,
        current_node: str,
        progress: float,
        message: str,
    ) -> None:
        """报告执行进度

        参数：
            session_id: 会话ID
            workflow_id: 工作流ID
            current_node: 当前节点
            progress: 进度 (0.0-1.0)
            message: 进度消息
        """
        msg = AgentMessage(
            type=AgentMessageType.EXECUTION_PROGRESS,
            session_id=session_id,
            payload={
                "workflow_id": workflow_id,
                "current_node": current_node,
                "progress": progress,
                "message": message,
            },
        )

        await self._channel.send_to_session(session_id, msg)
        logger.debug(f"Progress: {progress * 100:.0f}% - {message}")

    async def report_completed(
        self,
        session_id: str,
        workflow_id: str,
        result: dict[str, Any],
    ) -> None:
        """报告执行完成

        参数：
            session_id: 会话ID
            workflow_id: 工作流ID
            result: 执行结果
        """
        msg = AgentMessage(
            type=AgentMessageType.EXECUTION_COMPLETED,
            session_id=session_id,
            payload={
                "workflow_id": workflow_id,
                "result": result,
            },
        )

        await self._channel.send_to_session(session_id, msg)
        logger.info(f"Execution completed: workflow={workflow_id}")

    async def report_failed(
        self,
        session_id: str,
        workflow_id: str,
        error: str,
        failed_node: str | None = None,
    ) -> None:
        """报告执行失败

        参数：
            session_id: 会话ID
            workflow_id: 工作流ID
            error: 错误信息
            failed_node: 失败节点ID
        """
        msg = AgentMessage(
            type=AgentMessageType.EXECUTION_FAILED,
            session_id=session_id,
            payload={
                "workflow_id": workflow_id,
                "error": error,
                "failed_node": failed_node,
            },
        )

        await self._channel.send_to_session(session_id, msg)
        logger.error(f"Execution failed: workflow={workflow_id}, error={error}")

    async def push_execution_summary(
        self,
        session_id: str,
        summary: Any,
    ) -> None:
        """推送执行总结到客户端（Phase 5）

        参数：
            session_id: 会话ID
            summary: ExecutionSummary 实例
        """
        # 将总结转换为字典（如果有 to_dict 方法）
        if hasattr(summary, "to_dict"):
            payload = summary.to_dict()
        else:
            payload = {
                "workflow_id": getattr(summary, "workflow_id", ""),
                "session_id": getattr(summary, "session_id", ""),
                "success": getattr(summary, "success", False),
            }

        msg = AgentMessage(
            type=AgentMessageType.EXECUTION_SUMMARY,
            session_id=session_id,
            payload=payload,
        )

        await self._channel.send_to_session(session_id, msg)
        logger.info(f"Execution summary pushed: workflow={payload.get('workflow_id', '')}")


# ==================== 消息处理器 ====================


class AgentMessageHandler:
    """Agent 消息处理器

    处理接收到的 Agent 消息，调用相应的回调。
    """

    def __init__(self, channel: AgentWebSocketChannel):
        """初始化处理器

        参数：
            channel: WebSocket 信道
        """
        self._channel = channel

        # 回调函数
        self.on_task_request: Callable[[str, dict], Coroutine[Any, Any, dict]] | None = None
        self.on_cancel_task: Callable[[str, str], Coroutine[Any, Any, None]] | None = None
        self.on_plan_approved: Callable[[str, str], Coroutine[Any, Any, None]] | None = None

    async def handle_message(self, message: AgentMessage) -> dict[str, Any] | None:
        """处理消息

        参数：
            message: 接收到的消息

        返回：
            处理结果（如果有）
        """
        try:
            if message.type == AgentMessageType.TASK_REQUEST:
                return await self._handle_task_request(message)
            elif message.type == AgentMessageType.CANCEL_TASK:
                await self._handle_cancel_task(message)
            elif message.type == AgentMessageType.PLAN_APPROVED:
                await self._handle_plan_approved(message)
            else:
                logger.warning(f"Unhandled message type: {message.type}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return {"error": str(e)}

        return None

    async def _handle_task_request(self, message: AgentMessage) -> dict[str, Any]:
        """处理任务请求"""
        if self.on_task_request:
            return await self.on_task_request(message.session_id, message.payload)
        return {"status": "no_handler"}

    async def _handle_cancel_task(self, message: AgentMessage) -> None:
        """处理取消任务"""
        task_id = message.payload.get("task_id", "")
        if self.on_cancel_task:
            await self.on_cancel_task(message.session_id, task_id)

    async def _handle_plan_approved(self, message: AgentMessage) -> None:
        """处理计划批准"""
        plan_id = message.payload.get("plan_id", "")
        if self.on_plan_approved:
            await self.on_plan_approved(message.session_id, plan_id)


# 导出
__all__ = [
    "AgentMessageType",
    "AgentMessage",
    "AgentWebSocketChannel",
    "AgentChannelBridge",
    "AgentMessageHandler",
]

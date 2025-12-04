"""流式消息模型 (StreamMessage) - Phase 1 设计实现

根据 docs/architecture/conversation_flow.md 的设计实现。

业务定义：
- StreamMessage: 支持流式传输的消息数据类
- StreamMessageType: 流式消息类型枚举
- StreamMessageMetadata: 消息元数据
- StreamState: 流状态枚举
- MessageState: 单条消息处理状态

使用示例：
    msg = StreamMessage(
        type=StreamMessageType.THINKING_DELTA,
        content="正在思考...",
        is_delta=True,
    )
    json_str = msg.to_sse_format()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class StreamMessageType(str, Enum):
    """流式消息类型"""

    # 思考过程
    THINKING_START = "thinking_start"
    THINKING_DELTA = "thinking_delta"
    THINKING_END = "thinking_end"

    # 内容生成
    CONTENT_START = "content_start"
    CONTENT_DELTA = "content_delta"
    CONTENT_END = "content_end"

    # 工具调用
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT = "tool_result"

    # 状态通知
    STATUS_UPDATE = "status_update"
    ERROR = "error"

    # 流控制
    STREAM_START = "stream_start"
    STREAM_END = "stream_end"
    HEARTBEAT = "heartbeat"


class StreamState(str, Enum):
    """流状态"""

    PENDING = "pending"
    STREAMING = "streaming"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageState(str, Enum):
    """单条消息的处理状态"""

    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    ACKED = "acked"
    NACKED = "nacked"
    DROPPED = "dropped"


# 状态转换规则
VALID_STREAM_TRANSITIONS: dict[StreamState, list[StreamState]] = {
    StreamState.PENDING: [
        StreamState.STREAMING,
        StreamState.CANCELLED,
    ],
    StreamState.STREAMING: [
        StreamState.PAUSED,
        StreamState.COMPLETED,
        StreamState.FAILED,
        StreamState.CANCELLED,
    ],
    StreamState.PAUSED: [
        StreamState.STREAMING,
        StreamState.CANCELLED,
    ],
    StreamState.COMPLETED: [],
    StreamState.FAILED: [
        StreamState.PENDING,
    ],
    StreamState.CANCELLED: [],
}


def can_transition(current: StreamState, target: StreamState) -> bool:
    """检查状态转换是否合法"""
    return target in VALID_STREAM_TRANSITIONS.get(current, [])


@dataclass
class StreamMessageMetadata:
    """消息元数据"""

    # 追踪信息
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""

    # 上下文信息
    agent_id: str = ""
    node_id: str = ""
    workflow_id: str = ""

    # 性能信息
    latency_ms: int = 0
    token_count: int = 0

    # 扩展字段
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "agent_id": self.agent_id,
            "node_id": self.node_id,
            "workflow_id": self.workflow_id,
            "latency_ms": self.latency_ms,
            "token_count": self.token_count,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamMessageMetadata:
        """从字典创建"""
        return cls(
            trace_id=data.get("trace_id", ""),
            span_id=data.get("span_id", ""),
            parent_span_id=data.get("parent_span_id", ""),
            agent_id=data.get("agent_id", ""),
            node_id=data.get("node_id", ""),
            workflow_id=data.get("workflow_id", ""),
            latency_ms=data.get("latency_ms", 0),
            token_count=data.get("token_count", 0),
            extra=data.get("extra", {}),
        )


@dataclass
class StreamMessage:
    """流式消息

    统一的流式消息结构，支持增量更新和完整消息。

    属性:
        type: 消息类型
        content: 消息内容（可能是增量或完整内容）
        metadata: 消息元数据
        message_id: 消息唯一标识
        timestamp: 消息时间戳
        sequence: 消息序列号（用于排序和去重）
        is_delta: 是否为增量消息
        delta_index: 增量索引（从 0 开始）
    """

    type: StreamMessageType
    content: str = ""
    metadata: StreamMessageMetadata = field(default_factory=StreamMessageMetadata)
    message_id: str = field(default_factory=lambda: f"sm_{uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)
    sequence: int = 0
    is_delta: bool = False
    delta_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 JSON 传输）"""
        return {
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "is_delta": self.is_delta,
            "delta_index": self.delta_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamMessage:
        """从字典反序列化"""
        metadata = StreamMessageMetadata.from_dict(data.get("metadata", {}))

        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()

        return cls(
            type=StreamMessageType(data.get("type", "error")),
            content=data.get("content", ""),
            metadata=metadata,
            message_id=data.get("message_id", f"sm_{uuid4().hex[:12]}"),
            timestamp=timestamp,
            sequence=data.get("sequence", 0),
            is_delta=data.get("is_delta", False),
            delta_index=data.get("delta_index", 0),
        )

    def to_sse_format(self) -> str:
        """转换为 SSE 格式"""
        data = json.dumps(self.to_dict(), ensure_ascii=False, default=str)
        return f"event: {self.type.value}\ndata: {data}\n\n"


# 导出
__all__ = [
    "StreamMessageType",
    "StreamState",
    "MessageState",
    "StreamMessageMetadata",
    "StreamMessage",
    "VALID_STREAM_TRANSITIONS",
    "can_transition",
]

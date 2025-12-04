# 会话流生成器架构设计

> 版本: 1.0.0
> 更新日期: 2025-12-03
> 状态: 设计阶段

---

## 目录

1. [概述](#1-概述)
2. [会话流生成器职责](#2-会话流生成器职责)
3. [消息结构](#3-消息结构)
4. [状态机](#4-状态机)
5. [推送通道交互顺序图](#5-推送通道交互顺序图)
6. [消息示例](#6-消息示例)
7. [完成定义](#7-完成定义)

---

## 1. 概述

会话流生成器（ConversationFlowGenerator）是 Feagent 系统中负责实时流式消息传输的核心组件。它将 AI Agent 的思考过程、决策结果和执行状态以流式方式推送给客户端，提供类似 ChatGPT 的打字机效果体验。

### 1.1 设计目标

- **实时性**: 毫秒级延迟推送，用户可实时看到 AI 思考过程
- **可靠性**: 消息不丢失，支持重连恢复
- **可扩展性**: 支持多种消息类型和推送通道
- **低耦合**: 与具体 Agent 实现解耦

### 1.2 与现有系统的关系

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端 (Browser)                        │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ SSE / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ConversationFlowGenerator                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ SSEChannel   │  │  WSChannel   │  │ MessageQueue │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ StreamMessage
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 ConversationAgent (ReAct)                    │
│  - 意图识别 (IntentClassification)                           │
│  - 思考推理 (Thinking)                                       │
│  - 决策执行 (Action)                                         │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Event / Decision
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    CoordinatorAgent                          │
│  - 任务协调                                                  │
│  - 上下文管理                                                 │
│  - 工作流分发                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 会话流生成器职责

### 2.1 核心职责

| 职责 | 描述 | 优先级 |
|------|------|--------|
| 消息生成 | 将 Agent 输出转换为流式消息格式 | P0 |
| 增量推送 | 支持 token-by-token 的增量内容推送 | P0 |
| 通道管理 | 管理 SSE/WS 连接的生命周期 | P0 |
| 消息缓存 | 缓存未确认消息，支持重传 | P1 |
| 流量控制 | 背压处理，防止客户端过载 | P1 |
| 统计监控 | 消息吞吐量、延迟等指标 | P2 |

### 2.2 接口定义

```python
from typing import Protocol, AsyncIterator
from dataclasses import dataclass
from enum import Enum

class ConversationFlowGenerator(Protocol):
    """会话流生成器协议"""

    async def start_stream(
        self,
        session_id: str,
        conversation_id: str
    ) -> str:
        """
        开始一个新的流式会话

        参数:
            session_id: 会话标识
            conversation_id: 对话标识

        返回:
            stream_id: 流标识，用于后续操作
        """
        ...

    async def push_message(
        self,
        stream_id: str,
        message: "StreamMessage"
    ) -> bool:
        """
        推送一条消息到流

        参数:
            stream_id: 流标识
            message: 流式消息

        返回:
            是否推送成功
        """
        ...

    async def push_delta(
        self,
        stream_id: str,
        content: str,
        is_final: bool = False
    ) -> bool:
        """
        推送增量内容（打字机效果）

        参数:
            stream_id: 流标识
            content: 增量文本内容
            is_final: 是否为最后一个增量

        返回:
            是否推送成功
        """
        ...

    async def end_stream(
        self,
        stream_id: str,
        final_message: "StreamMessage | None" = None
    ) -> None:
        """
        结束流式会话

        参数:
            stream_id: 流标识
            final_message: 可选的最终消息
        """
        ...

    def stream_messages(
        self,
        stream_id: str
    ) -> AsyncIterator["StreamMessage"]:
        """
        获取消息流迭代器（用于 SSE/WS 推送）

        参数:
            stream_id: 流标识

        返回:
            异步消息迭代器
        """
        ...
```

---

## 3. 消息结构

### 3.1 StreamMessage 数据类

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

class StreamMessageType(str, Enum):
    """流式消息类型"""

    # 思考过程
    THINKING_START = "thinking_start"      # 开始思考
    THINKING_DELTA = "thinking_delta"      # 思考内容增量
    THINKING_END = "thinking_end"          # 思考结束

    # 内容生成
    CONTENT_START = "content_start"        # 开始生成内容
    CONTENT_DELTA = "content_delta"        # 内容增量（打字机效果）
    CONTENT_END = "content_end"            # 内容生成结束

    # 工具调用
    TOOL_CALL_START = "tool_call_start"    # 开始工具调用
    TOOL_CALL_ARGS = "tool_call_args"      # 工具参数（流式）
    TOOL_CALL_END = "tool_call_end"        # 工具调用结束
    TOOL_RESULT = "tool_result"            # 工具执行结果

    # 状态通知
    STATUS_UPDATE = "status_update"        # 状态更新
    ERROR = "error"                        # 错误消息

    # 流控制
    STREAM_START = "stream_start"          # 流开始
    STREAM_END = "stream_end"              # 流结束
    HEARTBEAT = "heartbeat"                # 心跳


@dataclass
class StreamMessageMetadata:
    """消息元数据"""

    # 追踪信息
    trace_id: str = ""                     # 追踪 ID，用于全链路追踪
    span_id: str = ""                      # 跨度 ID
    parent_span_id: str = ""               # 父跨度 ID

    # 上下文信息
    agent_id: str = ""                     # 产生消息的 Agent ID
    node_id: str = ""                      # 当前执行节点 ID
    workflow_id: str = ""                  # 工作流 ID

    # 性能信息
    latency_ms: int = 0                    # 消息生成延迟（毫秒）
    token_count: int = 0                   # Token 数量

    # 扩展字段
    extra: dict[str, Any] = field(default_factory=dict)


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

    设计说明:
        - message_id: 使用 UUID 前 12 位，保证唯一性
        - sequence: 单调递增，用于客户端排序
        - is_delta: 标识是否为增量消息，用于客户端拼接
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
            "metadata": {
                "trace_id": self.metadata.trace_id,
                "span_id": self.metadata.span_id,
                "parent_span_id": self.metadata.parent_span_id,
                "agent_id": self.metadata.agent_id,
                "node_id": self.metadata.node_id,
                "workflow_id": self.metadata.workflow_id,
                "latency_ms": self.metadata.latency_ms,
                "token_count": self.metadata.token_count,
                "extra": self.metadata.extra,
            },
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "is_delta": self.is_delta,
            "delta_index": self.delta_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamMessage":
        """从字典反序列化"""
        metadata_dict = data.get("metadata", {})
        metadata = StreamMessageMetadata(
            trace_id=metadata_dict.get("trace_id", ""),
            span_id=metadata_dict.get("span_id", ""),
            parent_span_id=metadata_dict.get("parent_span_id", ""),
            agent_id=metadata_dict.get("agent_id", ""),
            node_id=metadata_dict.get("node_id", ""),
            workflow_id=metadata_dict.get("workflow_id", ""),
            latency_ms=metadata_dict.get("latency_ms", 0),
            token_count=metadata_dict.get("token_count", 0),
            extra=metadata_dict.get("extra", {}),
        )

        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

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
        import json
        data = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"event: {self.type.value}\ndata: {data}\n\n"
```

### 3.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | StreamMessageType | 是 | 消息类型枚举 |
| content | str | 否 | 消息内容，增量消息时为增量部分 |
| metadata | StreamMessageMetadata | 否 | 元数据，包含追踪和上下文信息 |
| message_id | str | 是 | 消息唯一标识，格式：`sm_{uuid12}` |
| timestamp | datetime | 是 | 消息生成时间戳 |
| sequence | int | 是 | 消息序列号，单调递增 |
| is_delta | bool | 是 | 是否为增量消息 |
| delta_index | int | 否 | 增量索引，从 0 开始 |

---

## 4. 状态机

### 4.1 消息流状态（StreamState）

```python
class StreamState(str, Enum):
    """流状态"""

    PENDING = "pending"           # 等待开始
    STREAMING = "streaming"       # 正在流式传输
    PAUSED = "paused"            # 暂停（客户端背压）
    COMPLETED = "completed"       # 正常完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"       # 被取消
```

### 4.2 状态转换图

```
                    ┌───────────────────────────────────────┐
                    │                                       │
                    ▼                                       │
              ┌──────────┐                                  │
              │ PENDING  │ ◄─────────────────────┐          │
              └────┬─────┘                       │          │
                   │                             │          │
                   │ start_stream()              │          │
                   ▼                             │          │
              ┌──────────┐    pause()       ┌────┴─────┐    │
              │STREAMING │ ─────────────► │  PAUSED  │    │
              └────┬─────┘ ◄───────────── └──────────┘    │
                   │         resume()                      │
                   │                                       │
       ┌───────────┼───────────┬───────────────────────────┤
       │           │           │                           │
       │ end()     │ error     │ cancel()                  │
       ▼           ▼           ▼                           │
  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
  │COMPLETED │ │  FAILED  │ │CANCELLED │                   │
  └──────────┘ └────┬─────┘ └──────────┘                   │
                    │                                       │
                    │ retry()                              │
                    └───────────────────────────────────────┘
```

### 4.3 状态转换规则

```python
VALID_TRANSITIONS: dict[StreamState, list[StreamState]] = {
    StreamState.PENDING: [
        StreamState.STREAMING,     # start_stream()
        StreamState.CANCELLED,     # cancel()
    ],
    StreamState.STREAMING: [
        StreamState.PAUSED,        # pause()
        StreamState.COMPLETED,     # end_stream()
        StreamState.FAILED,        # error
        StreamState.CANCELLED,     # cancel()
    ],
    StreamState.PAUSED: [
        StreamState.STREAMING,     # resume()
        StreamState.CANCELLED,     # cancel()
    ],
    StreamState.COMPLETED: [],     # 终态，不可转换
    StreamState.FAILED: [
        StreamState.PENDING,       # retry()
    ],
    StreamState.CANCELLED: [],     # 终态，不可转换
}

def can_transition(
    current: StreamState,
    target: StreamState
) -> bool:
    """检查状态转换是否合法"""
    return target in VALID_TRANSITIONS.get(current, [])
```

### 4.4 消息处理状态（MessageState）

```python
class MessageState(str, Enum):
    """单条消息的处理状态"""

    QUEUED = "queued"            # 已入队，等待发送
    SENDING = "sending"          # 正在发送
    SENT = "sent"                # 已发送，等待确认
    ACKED = "acked"              # 已确认
    NACKED = "nacked"            # 未确认（需重传）
    DROPPED = "dropped"          # 已丢弃（超时/超限）
```

---

## 5. 推送通道交互顺序图

### 5.1 SSE 通道完整流程

```
┌──────────┐          ┌───────────────────┐          ┌─────────────────┐          ┌──────────┐
│  Client  │          │ ConversationFlow  │          │ Conversation    │          │   LLM    │
│          │          │    Generator      │          │    Agent        │          │          │
└────┬─────┘          └────────┬──────────┘          └────────┬────────┘          └────┬─────┘
     │                         │                              │                        │
     │ 1. GET /stream/{id}     │                              │                        │
     │ ───────────────────────►│                              │                        │
     │                         │                              │                        │
     │ 2. SSE: stream_start    │                              │                        │
     │ ◄───────────────────────│                              │                        │
     │                         │                              │                        │
     │                         │ 3. process_input()           │                        │
     │                         │ ─────────────────────────────►                        │
     │                         │                              │                        │
     │                         │                              │ 4. think()             │
     │                         │                              │ ───────────────────────►
     │                         │                              │                        │
     │                         │ 5. thinking_start            │                        │
     │ ◄───────────────────────│ ◄────────────────────────────│                        │
     │                         │                              │                        │
     │                         │                              │ 6. streaming tokens    │
     │                         │ 7. thinking_delta (N times)  │ ◄───────────────────────
     │ ◄───────────────────────│ ◄────────────────────────────│                        │
     │                         │                              │                        │
     │                         │ 8. thinking_end              │                        │
     │ ◄───────────────────────│ ◄────────────────────────────│                        │
     │                         │                              │                        │
     │                         │                              │ 9. generate_response() │
     │                         │                              │ ───────────────────────►
     │                         │                              │                        │
     │                         │ 10. content_start            │                        │
     │ ◄───────────────────────│ ◄────────────────────────────│                        │
     │                         │                              │                        │
     │                         │ 11. content_delta (N times)  │ 12. streaming tokens   │
     │ ◄───────────────────────│ ◄────────────────────────────│ ◄───────────────────────
     │                         │                              │                        │
     │                         │ 13. content_end              │                        │
     │ ◄───────────────────────│ ◄────────────────────────────│                        │
     │                         │                              │                        │
     │ 14. SSE: stream_end     │                              │                        │
     │ ◄───────────────────────│                              │                        │
     │                         │                              │                        │
```

### 5.2 WebSocket 通道完整流程

```
┌──────────┐          ┌───────────────────┐          ┌─────────────────┐
│  Client  │          │ ConversationFlow  │          │ Conversation    │
│          │          │    Generator      │          │    Agent        │
└────┬─────┘          └────────┬──────────┘          └────────┬────────┘
     │                         │                              │
     │ 1. WS Connect           │                              │
     │ ───────────────────────►│                              │
     │                         │                              │
     │ 2. WS: connected        │                              │
     │ ◄───────────────────────│                              │
     │                         │                              │
     │ 3. WS: task_request     │                              │
     │ ───────────────────────►│ 4. dispatch_task()           │
     │                         │ ─────────────────────────────►
     │                         │                              │
     │ 5. WS: stream_start     │                              │
     │ ◄───────────────────────│                              │
     │                         │                              │
     │                         │ 6. thinking_start            │
     │ ◄───────────────────────│ ◄────────────────────────────│
     │                         │                              │
     │ 7. WS: ack (seq=1)      │                              │
     │ ───────────────────────►│                              │
     │                         │                              │
     │                         │ 8. thinking_delta            │
     │ ◄───────────────────────│ ◄────────────────────────────│
     │                         │                              │
     │ 9. WS: ack (seq=2)      │                              │
     │ ───────────────────────►│                              │
     │                         │                              │
     │         ...             │        (continues)           │
     │                         │                              │
     │ N. WS: stream_end       │                              │
     │ ◄───────────────────────│                              │
     │                         │                              │
     │ N+1. WS: ack (final)    │                              │
     │ ───────────────────────►│                              │
     │                         │                              │
```

### 5.3 工具调用流程

```
┌──────────┐          ┌───────────────────┐          ┌─────────────────┐
│  Client  │          │ ConversationFlow  │          │    Agent        │
└────┬─────┘          └────────┬──────────┘          └────────┬────────┘
     │                         │                              │
     │                         │ 1. tool_call_start           │
     │ ◄───────────────────────│ ◄────────────────────────────│
     │                         │                              │
     │ {                       │                              │
     │   "type": "tool_call_start",                          │
     │   "content": "",        │                              │
     │   "metadata": {         │                              │
     │     "tool_name": "search",                            │
     │     "tool_id": "tc_001" │                              │
     │   }                     │                              │
     │ }                       │                              │
     │                         │                              │
     │                         │ 2. tool_call_args (streaming) │
     │ ◄───────────────────────│ ◄────────────────────────────│
     │                         │                              │
     │ {                       │                              │
     │   "type": "tool_call_args",                           │
     │   "content": "{\"query\":",                           │
     │   "is_delta": true      │                              │
     │ }                       │                              │
     │                         │                              │
     │ {                       │                              │
     │   "type": "tool_call_args",                           │
     │   "content": " \"Python",                             │
     │   "is_delta": true      │                              │
     │ }                       │                              │
     │                         │                              │
     │ {                       │                              │
     │   "type": "tool_call_args",                           │
     │   "content": " 教程\"}",│                              │
     │   "is_delta": true      │                              │
     │ }                       │                              │
     │                         │                              │
     │                         │ 3. tool_call_end             │
     │ ◄───────────────────────│ ◄────────────────────────────│
     │                         │                              │
     │                         │ 4. Execute tool...           │
     │                         │                              │
     │                         │ 5. tool_result               │
     │ ◄───────────────────────│ ◄────────────────────────────│
     │                         │                              │
     │ {                       │                              │
     │   "type": "tool_result",│                              │
     │   "content": "{...}",   │                              │
     │   "metadata": {         │                              │
     │     "tool_id": "tc_001",│                              │
     │     "success": true     │                              │
     │   }                     │                              │
     │ }                       │                              │
     │                         │                              │
```

---

## 6. 消息示例

### 6.1 完整对话流示例

```json
// 1. 流开始
{
  "type": "stream_start",
  "content": "",
  "message_id": "sm_a1b2c3d4e5f6",
  "timestamp": "2025-12-03T10:00:00.000Z",
  "sequence": 1,
  "is_delta": false,
  "metadata": {
    "trace_id": "tr_123456789",
    "agent_id": "conversation_agent_1"
  }
}

// 2. 开始思考
{
  "type": "thinking_start",
  "content": "",
  "message_id": "sm_a1b2c3d4e5f7",
  "timestamp": "2025-12-03T10:00:00.050Z",
  "sequence": 2,
  "is_delta": false,
  "metadata": {
    "trace_id": "tr_123456789"
  }
}

// 3. 思考内容增量
{
  "type": "thinking_delta",
  "content": "用户想要",
  "message_id": "sm_a1b2c3d4e5f8",
  "timestamp": "2025-12-03T10:00:00.100Z",
  "sequence": 3,
  "is_delta": true,
  "delta_index": 0,
  "metadata": {
    "token_count": 2
  }
}

{
  "type": "thinking_delta",
  "content": "创建一个工作流",
  "message_id": "sm_a1b2c3d4e5f9",
  "timestamp": "2025-12-03T10:00:00.150Z",
  "sequence": 4,
  "is_delta": true,
  "delta_index": 1,
  "metadata": {
    "token_count": 4
  }
}

// 4. 思考结束
{
  "type": "thinking_end",
  "content": "",
  "message_id": "sm_a1b2c3d4e5fa",
  "timestamp": "2025-12-03T10:00:00.200Z",
  "sequence": 5,
  "is_delta": false
}

// 5. 开始生成内容
{
  "type": "content_start",
  "content": "",
  "message_id": "sm_a1b2c3d4e5fb",
  "timestamp": "2025-12-03T10:00:00.250Z",
  "sequence": 6,
  "is_delta": false
}

// 6. 内容增量（打字机效果）
{
  "type": "content_delta",
  "content": "好的，",
  "message_id": "sm_a1b2c3d4e5fc",
  "timestamp": "2025-12-03T10:00:00.300Z",
  "sequence": 7,
  "is_delta": true,
  "delta_index": 0
}

{
  "type": "content_delta",
  "content": "我来帮您",
  "message_id": "sm_a1b2c3d4e5fd",
  "timestamp": "2025-12-03T10:00:00.350Z",
  "sequence": 8,
  "is_delta": true,
  "delta_index": 1
}

{
  "type": "content_delta",
  "content": "创建工作流。",
  "message_id": "sm_a1b2c3d4e5fe",
  "timestamp": "2025-12-03T10:00:00.400Z",
  "sequence": 9,
  "is_delta": true,
  "delta_index": 2
}

// 7. 内容结束
{
  "type": "content_end",
  "content": "好的，我来帮您创建工作流。",
  "message_id": "sm_a1b2c3d4e5ff",
  "timestamp": "2025-12-03T10:00:00.450Z",
  "sequence": 10,
  "is_delta": false,
  "metadata": {
    "token_count": 8,
    "latency_ms": 450
  }
}

// 8. 流结束
{
  "type": "stream_end",
  "content": "",
  "message_id": "sm_a1b2c3d4e600",
  "timestamp": "2025-12-03T10:00:00.500Z",
  "sequence": 11,
  "is_delta": false,
  "metadata": {
    "total_tokens": 14,
    "total_latency_ms": 500
  }
}
```

### 6.2 错误消息示例

```json
{
  "type": "error",
  "content": "LLM 调用超时",
  "message_id": "sm_err_001",
  "timestamp": "2025-12-03T10:00:05.000Z",
  "sequence": 99,
  "is_delta": false,
  "metadata": {
    "error_code": "LLM_TIMEOUT",
    "error_details": {
      "timeout_ms": 30000,
      "model": "gpt-4"
    },
    "recoverable": true
  }
}
```

### 6.3 状态更新示例

```json
{
  "type": "status_update",
  "content": "正在执行工作流节点: 数据处理",
  "message_id": "sm_status_001",
  "timestamp": "2025-12-03T10:00:03.000Z",
  "sequence": 50,
  "is_delta": false,
  "metadata": {
    "workflow_id": "wf_123",
    "node_id": "node_data_processing",
    "progress": 0.5,
    "extra": {
      "current_step": 2,
      "total_steps": 4
    }
  }
}
```

---

## 7. 完成定义

### 7.1 功能完成标准

| 检查项 | 完成标准 | 验证方法 |
|--------|----------|----------|
| StreamMessage 数据类 | 所有字段定义完整，序列化/反序列化正常 | 单元测试 |
| 状态机实现 | 状态转换符合规则，非法转换抛出异常 | 状态机测试 |
| SSE 通道 | 客户端能正常接收流式消息 | 集成测试 |
| WS 通道 | 双向通信正常，支持 ACK 机制 | E2E 测试 |
| 增量推送 | 打字机效果流畅，延迟 < 100ms | 性能测试 |
| 错误处理 | 错误消息格式正确，支持恢复 | 异常测试 |

### 7.2 非功能性要求

| 指标 | 要求 | 测量方法 |
|------|------|----------|
| 延迟 | P95 < 100ms | 监控系统 |
| 吞吐量 | > 1000 msg/s per stream | 压力测试 |
| 可靠性 | 消息丢失率 < 0.01% | ACK 统计 |
| 可用性 | 99.9% uptime | SLA 监控 |

### 7.3 测试覆盖要求

```python
# 单元测试覆盖
- test_stream_message_serialization()          # 消息序列化
- test_stream_message_deserialization()        # 消息反序列化
- test_message_type_enum_completeness()        # 消息类型完整性
- test_metadata_fields()                       # 元数据字段
- test_state_machine_valid_transitions()       # 有效状态转换
- test_state_machine_invalid_transitions()     # 无效状态转换

# 集成测试覆盖
- test_sse_channel_stream_flow()              # SSE 完整流程
- test_ws_channel_bidirectional()             # WS 双向通信
- test_delta_message_accumulation()           # 增量消息累积
- test_error_recovery()                       # 错误恢复
- test_stream_cancellation()                  # 流取消

# E2E 测试覆盖
- test_full_conversation_with_thinking()      # 完整对话（含思考）
- test_tool_call_streaming()                  # 工具调用流式
- test_multi_client_streams()                 # 多客户端同时流式
```

### 7.4 文档完成标准

- [x] 消息结构定义完整
- [x] 状态机转换图清晰
- [x] 交互顺序图覆盖主要场景
- [x] 消息示例可直接用于开发参考
- [x] 完成定义明确可测量

---

## 附录 A: 与现有系统的集成点

### A.1 与 AgentMessage 的关系

`StreamMessage` 专注于流式传输，而 `AgentMessage`（见 `agent_channel.py`）专注于 Agent 间通信：

| 特性 | StreamMessage | AgentMessage |
|------|---------------|--------------|
| 用途 | 流式推送给客户端 | Agent 间通信 |
| 传输方式 | SSE/WS 流式 | WS 单条消息 |
| 增量支持 | 支持 | 不支持 |
| 序列号 | 有 | 无 |

### A.2 与 EventBus 的集成

ConversationFlowGenerator 可以订阅 EventBus 事件，自动转换为 StreamMessage：

```python
# 示例：将 SimpleMessageEvent 转换为 StreamMessage
async def on_simple_message(event: SimpleMessageEvent):
    stream_msg = StreamMessage(
        type=StreamMessageType.CONTENT_END,
        content=event.response,
        metadata=StreamMessageMetadata(
            agent_id="conversation_agent",
        ),
    )
    await flow_generator.push_message(stream_id, stream_msg)
```

---

## 附录 B: 性能优化建议

1. **批量发送**: 合并小增量消息，减少网络往返
2. **压缩传输**: 对长消息启用 gzip 压缩
3. **连接复用**: WebSocket 连接复用，避免频繁握手
4. **背压处理**: 客户端处理不过来时暂停发送

---

**文档状态**: 已实现
**更新日期**: 2025-12-04

---

## 附录 C: Phase 2-3 实现详情

### C.1 ConversationFlowEmitter (Phase 2)

`src/domain/services/conversation_flow_emitter.py` 实现了 Phase 1 设计：

```python
from src.domain.services.conversation_flow_emitter import (
    ConversationFlowEmitter,
    ConversationStep,
    StepKind,
    EmitterClosedError,
)

# 使用示例
emitter = ConversationFlowEmitter(session_id="session_1", timeout=30.0)

# 发送步骤
await emitter.emit_thinking("正在分析您的请求...")
await emitter.emit_tool_call("search", "t1", {"query": "test"})
await emitter.emit_tool_result("t1", {"data": "result"}, success=True)
await emitter.emit_final_response("这是最终响应")
await emitter.complete()

# 异步迭代
async for step in emitter:
    if step.kind == StepKind.END:
        break
    print(f"{step.kind}: {step.content}")
```

### C.2 SSE Handler (Phase 3)

`src/interfaces/api/services/sse_emitter_handler.py` 提供 SSE 集成：

```python
from src.interfaces.api.services.sse_emitter_handler import (
    SSEEmitterHandler,
    SSESessionManager,
    get_session_manager,
)

# 创建 SSE 响应
handler = SSEEmitterHandler(emitter, request)
return handler.create_response()
```

### C.3 Conversation Stream API (Phase 3)

`src/interfaces/api/routes/conversation_stream.py` 提供端点：

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/conversation/stream` | POST | 流式对话，实时输出 Thought/Tool/Result |
| `/api/conversation/stream/{session_id}/status` | GET | 获取会话状态 |
| `/api/conversation/stream/{session_id}` | DELETE | 取消会话 |
| `/api/conversation/health` | GET | 健康检查 |

### C.4 测试覆盖

| 测试文件 | 测试数量 | 覆盖范围 |
|----------|----------|----------|
| `tests/unit/domain/services/test_conversation_flow_emitter.py` | 33 | Emitter 单元测试 |
| `tests/unit/domain/agents/test_conversation_agent_emitter_integration.py` | 14 | Agent 集成测试 |
| `tests/integration/api/test_sse_emitter_integration.py` | 16 | SSE 集成测试 |
| `tests/integration/api/test_conversation_stream_api.py` | 17 | API 端点测试 |

**总计: 80 个测试通过**

### C.5 测试脚本

手动验证脚本:
- `scripts/test_sse_stream.sh` - Bash 版本
- `scripts/test_sse_stream.py` - Python 版本

```bash
# 启动服务器
uvicorn src.interfaces.api.main:app --reload --port 8000

# 运行测试脚本
python scripts/test_sse_stream.py
```

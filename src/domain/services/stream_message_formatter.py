"""Phase 4: 流式消息格式化层

将 ConversationStep 内部结构化数据转换为前端可直接渲染的 JSON 格式。

设计目标:
1. 前端可直接使用，无需额外解析
2. 支持多种消息类型的差异化展示
3. 提供统一的 API 接口

输出格式:
{
    "type": "thought" | "tool_call" | "tool_result" | "final" | "error" | "status",
    "content": "消息内容",
    "metadata": {
        "tool": "工具名称",
        "tool_id": "工具ID",
        "arguments": {...},
        "result": {...},
        "success": true/false,
        "error_code": "...",
        ...
    },
    "timestamp": "ISO 格式时间戳",
    "sequence": 序列号,
    "is_streaming": true/false
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.conversation_flow_emitter import ConversationStep, StepKind


class FrontendMessageType(str, Enum):
    """前端消息类型"""

    THOUGHT = "thought"  # 思考过程
    TOOL_CALL = "tool_call"  # 工具调用
    TOOL_RESULT = "tool_result"  # 工具结果
    FINAL = "final"  # 最终响应
    ERROR = "error"  # 错误
    STATUS = "status"  # 状态更新
    DELTA = "delta"  # 增量内容
    STREAM_START = "stream_start"  # 流开始
    STREAM_END = "stream_end"  # 流结束


@dataclass
class FrontendMessage:
    """前端消息格式

    这是发送给前端的标准消息格式，前端可以直接使用。

    属性:
        type: 消息类型
        content: 消息内容
        metadata: 附加元数据
        timestamp: ISO 格式时间戳
        sequence: 消息序列号
        is_streaming: 是否为流式消息（增量）
        message_id: 消息唯一标识
    """

    type: FrontendMessageType
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    sequence: int = 0
    is_streaming: bool = False
    message_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "is_streaming": self.is_streaming,
            "message_id": self.message_id,
        }

    def to_sse(self) -> str:
        """转换为 SSE 格式"""
        import json

        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class StreamMessageFormatter:
    """流式消息格式化器

    将 ConversationStep 转换为前端可直接使用的 FrontendMessage。

    使用示例:
        formatter = StreamMessageFormatter()
        step = ConversationStep(kind=StepKind.THINKING, content="分析中...")
        frontend_msg = formatter.format(step)
        print(frontend_msg.to_dict())
    """

    # StepKind 到 FrontendMessageType 的映射
    _KIND_TO_TYPE: dict[StepKind, FrontendMessageType] = {
        StepKind.THINKING: FrontendMessageType.THOUGHT,
        StepKind.REASONING: FrontendMessageType.THOUGHT,
        StepKind.ACTION: FrontendMessageType.STATUS,
        StepKind.OBSERVATION: FrontendMessageType.STATUS,
        StepKind.TOOL_CALL: FrontendMessageType.TOOL_CALL,
        StepKind.TOOL_RESULT: FrontendMessageType.TOOL_RESULT,
        StepKind.DELTA: FrontendMessageType.DELTA,
        StepKind.FINAL: FrontendMessageType.FINAL,
        StepKind.ERROR: FrontendMessageType.ERROR,
        StepKind.END: FrontendMessageType.STREAM_END,
    }

    def format(self, step: ConversationStep) -> FrontendMessage:
        """格式化 ConversationStep 为前端消息

        参数:
            step: 会话步骤

        返回:
            FrontendMessage 实例
        """
        msg_type = self._KIND_TO_TYPE.get(step.kind, FrontendMessageType.STATUS)

        # 构建元数据
        metadata = self._build_metadata(step)

        return FrontendMessage(
            type=msg_type,
            content=step.content,
            metadata=metadata,
            timestamp=step.timestamp.isoformat(),
            sequence=step.sequence,
            is_streaming=step.is_delta,
            message_id=step.step_id,
        )

    def _build_metadata(self, step: ConversationStep) -> dict[str, Any]:
        """构建元数据

        根据不同的步骤类型提取相关元数据。
        """
        metadata: dict[str, Any] = {}

        # 复制原始元数据
        if step.metadata:
            metadata.update(step.metadata)

        # 根据类型添加特定字段
        if step.kind == StepKind.TOOL_CALL:
            # 工具调用：提取工具信息
            metadata["tool"] = step.metadata.get("tool_name", "unknown")
            metadata["tool_id"] = step.metadata.get("tool_id", "")
            metadata["arguments"] = step.metadata.get("arguments", {})

        elif step.kind == StepKind.TOOL_RESULT:
            # 工具结果：提取结果信息
            metadata["tool_id"] = step.metadata.get("tool_id", "")
            metadata["result"] = step.metadata.get("result", {})
            metadata["success"] = step.metadata.get("success", True)
            if not metadata["success"]:
                metadata["error"] = step.metadata.get("error", "")

        elif step.kind == StepKind.ERROR:
            # 错误：提取错误信息
            metadata["error_code"] = step.metadata.get("error_code", "UNKNOWN")
            metadata["recoverable"] = step.metadata.get("recoverable", False)

        elif step.kind == StepKind.FINAL:
            # 最终响应：标记为最终
            metadata["is_final"] = True

        elif step.kind == StepKind.DELTA:
            # 增量：添加索引
            metadata["delta_index"] = step.delta_index

        return metadata

    def format_stream_start(self, session_id: str) -> FrontendMessage:
        """格式化流开始消息"""
        return FrontendMessage(
            type=FrontendMessageType.STREAM_START,
            content="",
            metadata={"session_id": session_id},
            sequence=0,
        )

    def format_stream_end(self) -> FrontendMessage:
        """格式化流结束消息"""
        return FrontendMessage(
            type=FrontendMessageType.STREAM_END,
            content="",
            metadata={},
            sequence=9999,
        )

    def format_error(
        self,
        error_message: str,
        error_code: str = "UNKNOWN",
        recoverable: bool = False,
    ) -> FrontendMessage:
        """格式化错误消息"""
        return FrontendMessage(
            type=FrontendMessageType.ERROR,
            content=error_message,
            metadata={
                "error_code": error_code,
                "recoverable": recoverable,
            },
        )


class FrontendSSEEncoder:
    """前端 SSE 编码器

    将 FrontendMessage 编码为 SSE 格式的字符串。
    """

    def __init__(self, formatter: StreamMessageFormatter | None = None):
        self.formatter = formatter or StreamMessageFormatter()

    def encode_step(self, step: ConversationStep) -> str:
        """将步骤编码为 SSE 格式

        参数:
            step: 会话步骤

        返回:
            SSE 格式的字符串
        """
        msg = self.formatter.format(step)
        return msg.to_sse()

    def encode_done(self) -> str:
        """编码结束标记"""
        return "data: [DONE]\n\n"

    def encode_message(self, message: FrontendMessage) -> str:
        """编码前端消息"""
        return message.to_sse()


# 便捷函数
def format_step_for_frontend(step: ConversationStep) -> dict[str, Any]:
    """将步骤格式化为前端可用的字典

    这是一个便捷函数，直接返回字典格式。

    参数:
        step: 会话步骤

    返回:
        前端可直接使用的字典
    """
    formatter = StreamMessageFormatter()
    return formatter.format(step).to_dict()


def create_thought_message(content: str, sequence: int = 0) -> dict[str, Any]:
    """创建思考消息"""
    return FrontendMessage(
        type=FrontendMessageType.THOUGHT,
        content=content,
        sequence=sequence,
    ).to_dict()


def create_tool_call_message(
    tool_name: str,
    tool_id: str,
    arguments: dict[str, Any],
    sequence: int = 0,
) -> dict[str, Any]:
    """创建工具调用消息"""
    return FrontendMessage(
        type=FrontendMessageType.TOOL_CALL,
        content=f"调用工具: {tool_name}",
        metadata={
            "tool": tool_name,
            "tool_id": tool_id,
            "arguments": arguments,
        },
        sequence=sequence,
    ).to_dict()


def create_tool_result_message(
    tool_id: str,
    result: Any,
    success: bool = True,
    error: str | None = None,
    sequence: int = 0,
) -> dict[str, Any]:
    """创建工具结果消息"""
    metadata = {
        "tool_id": tool_id,
        "result": result,
        "success": success,
    }
    if not success and error:
        metadata["error"] = error

    return FrontendMessage(
        type=FrontendMessageType.TOOL_RESULT,
        content="工具执行完成" if success else f"工具执行失败: {error}",
        metadata=metadata,
        sequence=sequence,
    ).to_dict()


def create_final_message(content: str, sequence: int = 0) -> dict[str, Any]:
    """创建最终响应消息"""
    return FrontendMessage(
        type=FrontendMessageType.FINAL,
        content=content,
        metadata={"is_final": True},
        sequence=sequence,
    ).to_dict()


# 导出
__all__ = [
    "FrontendMessageType",
    "FrontendMessage",
    "StreamMessageFormatter",
    "FrontendSSEEncoder",
    "format_step_for_frontend",
    "create_thought_message",
    "create_tool_call_message",
    "create_tool_result_message",
    "create_final_message",
]

"""会话流发射器 (ConversationFlowEmitter) - Phase 2

业务定义：
- 接收 ConversationAgent 的步骤输出
- 将步骤转换为流式消息
- 使用 asyncio.Queue 缓存消息
- 支持关闭/错误处理

设计原则：
- 异步优先：所有 emit 方法都是异步的
- 有序传输：通过序列号保证消息顺序
- 状态管理：跟踪 emitter 的生命周期状态
- 错误恢复：支持错误发送和优雅关闭

使用示例：
    emitter = ConversationFlowEmitter(session_id="session_1")

    # 发送步骤
    await emitter.emit_thinking("正在分析...")
    await emitter.emit_delta("好的，")
    await emitter.emit_delta("我来帮您。")
    await emitter.emit_final_response("任务完成")

    # 关闭
    await emitter.complete()

    # 或者遍历所有消息
    async for step in emitter:
        print(step.content)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from src.domain.services.stream_message import (
    StreamMessage,
    StreamMessageMetadata,
    StreamMessageType,
)


class StepKind(str, Enum):
    """步骤类型枚举"""

    THINKING = "thinking"
    REASONING = "reasoning"
    ACTION = "action"
    OBSERVATION = "observation"
    PLANNING_STEP = "planning_step"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DELTA = "delta"
    FINAL = "final"
    ERROR = "error"
    END = "end"


# StepKind 到 StreamMessageType 的映射
STEP_TO_STREAM_TYPE: dict[StepKind, StreamMessageType] = {
    StepKind.THINKING: StreamMessageType.THINKING_START,
    StepKind.REASONING: StreamMessageType.THINKING_DELTA,
    StepKind.ACTION: StreamMessageType.STATUS_UPDATE,
    StepKind.OBSERVATION: StreamMessageType.STATUS_UPDATE,
    StepKind.PLANNING_STEP: StreamMessageType.STATUS_UPDATE,
    StepKind.TOOL_CALL: StreamMessageType.TOOL_CALL_START,
    StepKind.TOOL_RESULT: StreamMessageType.TOOL_RESULT,
    StepKind.DELTA: StreamMessageType.CONTENT_DELTA,
    StepKind.FINAL: StreamMessageType.CONTENT_END,
    StepKind.ERROR: StreamMessageType.ERROR,
    StepKind.END: StreamMessageType.STREAM_END,
}


class EmitterClosedError(Exception):
    """Emitter 已关闭错误

    当尝试向已关闭的 emitter 发送消息时抛出。
    """

    pass


@dataclass
class ConversationStep:
    """会话步骤

    表示 ConversationAgent 执行过程中的一个步骤。

    属性:
        kind: 步骤类型
        content: 步骤内容
        metadata: 元数据
        step_id: 步骤唯一标识
        timestamp: 时间戳
        sequence: 序列号
        is_delta: 是否为增量内容
        is_final: 是否为最终步骤
        delta_index: 增量索引
    """

    kind: StepKind
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    step_id: str = field(default_factory=lambda: f"step_{uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)
    sequence: int = 0
    is_delta: bool = False
    is_final: bool = False
    delta_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "kind": self.kind.value,
            "content": self.content,
            "metadata": self.metadata,
            "step_id": self.step_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "is_delta": self.is_delta,
            "is_final": self.is_final,
            "delta_index": self.delta_index,
        }

    def to_stream_message(self) -> StreamMessage:
        """转换为 StreamMessage"""
        msg_type = STEP_TO_STREAM_TYPE.get(self.kind, StreamMessageType.STATUS_UPDATE)

        # 构建元数据
        stream_metadata = StreamMessageMetadata(
            agent_id=self.metadata.get("agent_id", ""),
            node_id=self.metadata.get("node_id", ""),
            workflow_id=self.metadata.get("workflow_id", ""),
            extra=self.metadata,
        )

        return StreamMessage(
            type=msg_type,
            content=self.content,
            metadata=stream_metadata,
            sequence=self.sequence,
            is_delta=self.is_delta,
            delta_index=self.delta_index,
        )


class ConversationFlowEmitter:
    """会话流发射器

    负责将 ConversationAgent 的步骤输出转换为流式消息，
    并通过异步队列传输。

    属性:
        session_id: 会话标识
        timeout: 迭代超时时间（秒）
    """

    def __init__(
        self,
        session_id: str,
        timeout: float | None = None,
    ):
        """初始化发射器

        参数:
            session_id: 会话标识
            timeout: 迭代超时时间（秒），None 表示无限等待
        """
        self.session_id = session_id
        self.timeout = timeout

        # 内部状态
        self._queue: asyncio.Queue[ConversationStep] = asyncio.Queue()
        # Completion is a cross-cutting concern (agent task + SSE handler cleanup may race).
        # Guard END emission so it is sent at most once.
        self._completion_lock = asyncio.Lock()
        self._is_completed = False
        self._sequence_counter = 0
        self._delta_counter = 0
        self._accumulated_content = ""

        # 统计信息
        self._stats: dict[str, int] = {}

    @property
    def is_active(self) -> bool:
        """是否处于活跃状态"""
        return not self._is_completed

    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self._is_completed

    def _next_sequence(self) -> int:
        """获取下一个序列号"""
        self._sequence_counter += 1
        return self._sequence_counter

    def _next_delta_index(self) -> int:
        """获取下一个增量索引"""
        idx = self._delta_counter
        self._delta_counter += 1
        return idx

    def _increment_stat(self, kind: StepKind) -> None:
        """增加统计计数"""
        key = kind.value
        self._stats[key] = self._stats.get(key, 0) + 1

    async def emit_step(self, step: ConversationStep) -> None:
        """发送步骤

        参数:
            step: 会话步骤

        异常:
            EmitterClosedError: 如果 emitter 已关闭
        """
        if self._is_completed:
            raise EmitterClosedError("Emitter is closed, cannot emit new steps")

        # 设置序列号
        step.sequence = self._next_sequence()

        # 更新统计
        self._increment_stat(step.kind)

        # 如果是增量内容，累积
        if step.is_delta:
            self._accumulated_content += step.content

        # 加入队列
        await self._queue.put(step)

    async def emit_thinking(self, content: str, **metadata: Any) -> None:
        """发送思考步骤

        参数:
            content: 思考内容
            **metadata: 额外元数据
        """
        step = ConversationStep(
            kind=StepKind.THINKING,
            content=content,
            metadata=metadata,
        )
        await self.emit_step(step)

    async def emit_reasoning(self, content: str, **metadata: Any) -> None:
        """发送推理步骤

        参数:
            content: 推理内容
            **metadata: 额外元数据
        """
        step = ConversationStep(
            kind=StepKind.REASONING,
            content=content,
            metadata=metadata,
        )
        await self.emit_step(step)

    async def emit_planning_step(self, content: str = "", **metadata: Any) -> None:
        """发送规划步骤（仅用于解释/规划展示，不代表真实工具执行）。"""

        step = ConversationStep(
            kind=StepKind.PLANNING_STEP,
            content=content,
            metadata=metadata,
        )
        await self.emit_step(step)

    async def emit_delta(self, content: str, **metadata: Any) -> None:
        """发送增量内容

        参数:
            content: 增量文本
            **metadata: 额外元数据
        """
        step = ConversationStep(
            kind=StepKind.DELTA,
            content=content,
            is_delta=True,
            delta_index=self._next_delta_index(),
            metadata=metadata,
        )
        await self.emit_step(step)

    async def emit_tool_call(
        self,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        **metadata: Any,
    ) -> None:
        """发送工具调用

        参数:
            tool_name: 工具名称
            tool_id: 工具调用 ID
            arguments: 工具参数
            **metadata: 额外元数据
        """
        step = ConversationStep(
            kind=StepKind.TOOL_CALL,
            content="",
            metadata={
                "tool_name": tool_name,
                "tool_id": tool_id,
                "arguments": arguments,
                **metadata,
            },
        )
        await self.emit_step(step)

    async def emit_tool_result(
        self,
        tool_id: str,
        result: Any,
        success: bool = True,
        error: str | None = None,
        **metadata: Any,
    ) -> None:
        """发送工具执行结果

        参数:
            tool_id: 工具调用 ID
            result: 执行结果
            success: 是否成功
            error: 错误信息（失败时）
            **metadata: 额外元数据
        """
        step = ConversationStep(
            kind=StepKind.TOOL_RESULT,
            content="",
            metadata={
                "tool_id": tool_id,
                "result": result,
                "success": success,
                "error": error,
                **metadata,
            },
        )
        await self.emit_step(step)

    async def emit_final_response(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """发送最终响应

        参数:
            content: 响应内容
            metadata: 元数据
        """
        step = ConversationStep(
            kind=StepKind.FINAL,
            content=content,
            is_final=True,
            metadata=metadata or {},
        )
        await self.emit_step(step)

    async def emit_error(
        self,
        error_message: str,
        error_code: str = "",
        recoverable: bool = False,
        **metadata: Any,
    ) -> None:
        """发送错误步骤

        参数:
            error_message: 错误消息
            error_code: 错误代码
            recoverable: 是否可恢复
            **metadata: 额外元数据
        """
        step = ConversationStep(
            kind=StepKind.ERROR,
            content=error_message,
            metadata={
                "error_code": error_code,
                "recoverable": recoverable,
                **metadata,
            },
        )
        await self.emit_step(step)

    async def emit_system_notice(self, content: str, **metadata: Any) -> None:
        """发送系统通知 (Step 2: 短期记忆缓冲与饱和事件)

        用于发送系统级别的通知消息，例如上下文压缩提示。

        参数:
            content: 通知内容
            **metadata: 额外元数据
        """
        step = ConversationStep(
            kind=StepKind.ACTION,
            content=content,
            metadata={
                "notice_type": "system",
                **metadata,
            },
        )
        await self.emit_step(step)

    async def complete(self) -> None:
        """完成发射

        标记 emitter 为已完成，并发送结束标记。
        此方法是幂等的，多次调用不会有副作用。
        """
        async with self._completion_lock:
            if self._is_completed:
                return

            # Mark completed first so concurrent cleanup doesn't enqueue duplicate END.
            self._is_completed = True

            # 发送结束标记
            end_step = ConversationStep(
                kind=StepKind.END,
                content="",
                is_final=True,
                sequence=self._next_sequence(),
            )
            await self._queue.put(end_step)

    async def complete_with_error(self, error_message: str) -> None:
        """因错误完成发射

        发送错误消息并关闭 emitter（error 后必须跟随 END）。

        参数:
            error_message: 错误消息
        """
        async with self._completion_lock:
            if self._is_completed:
                return

            # 先发送错误，再发送 END，避免 SSE handler 在 error 后等待到超时。
            try:
                await self.emit_error(error_message, recoverable=False)
            finally:
                self._is_completed = True
                end_step = ConversationStep(
                    kind=StepKind.END,
                    content="",
                    is_final=True,
                    sequence=self._next_sequence(),
                )
                await self._queue.put(end_step)

    def get_statistics(self) -> dict[str, Any]:
        """获取发送统计

        返回:
            包含统计信息的字典
        """
        total = sum(self._stats.values())
        return {
            "total_steps": total,
            "by_kind": self._stats.copy(),
            "sequence": self._sequence_counter,
            "delta_count": self._delta_counter,
        }

    def get_accumulated_content(self) -> str:
        """获取累积的内容

        返回所有 delta 步骤累积的内容。

        返回:
            累积的内容字符串
        """
        return self._accumulated_content

    def __aiter__(self) -> ConversationFlowEmitter:
        """返回异步迭代器"""
        return self

    async def __anext__(self) -> ConversationStep:
        """获取下一个步骤

        返回:
            下一个 ConversationStep

        异常:
            StopAsyncIteration: 当收到结束标记时
            asyncio.TimeoutError: 当超时时
        """
        if self.timeout:
            try:
                step = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=self.timeout,
                )
            except TimeoutError:
                raise
        else:
            step = await self._queue.get()

        # 如果是结束标记，但我们要返回它让调用者知道
        # 调用者可以检查 step.kind == StepKind.END 来决定是否停止
        return step


# 导出
__all__ = [
    "StepKind",
    "ConversationStep",
    "ConversationFlowEmitter",
    "EmitterClosedError",
    "STEP_TO_STREAM_TYPE",
]

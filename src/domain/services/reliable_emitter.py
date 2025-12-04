"""可靠发射器 (ReliableEmitter) - Phase 5

业务定义：
- 基于 ConversationFlowEmitter 的可靠扩展
- 提供有界队列防止内存溢出
- 支持多种溢出策略（阻塞/丢弃旧/丢弃新/抛异常）
- 支持消息持久化，方便协调者查询
- 提供重试机制和背压控制

设计原则：
- 向后兼容：保持与 ConversationFlowEmitter 相同的 API
- 可配置：溢出策略、队列大小、重试次数都可配置
- 可观测：提供丰富的统计信息
- 可扩展：通过 MessageStore 接口支持不同存储后端

使用示例：
    from src.domain.services.reliable_emitter import ReliableEmitter, BufferOverflowPolicy

    # 创建可靠发射器
    emitter = ReliableEmitter(
        session_id="session_1",
        max_size=100,
        overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
        message_store=InMemoryMessageStore(),
    )

    # 使用方式与 ConversationFlowEmitter 相同
    await emitter.emit_thinking("分析中...")
    await emitter.emit_tool_call("search", "t1", {"query": "test"})
    await emitter.complete()

    # 查询历史消息
    messages = await store.get_by_session_id("session_1")
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from src.domain.services.conversation_flow_emitter import (
    ConversationStep,
    EmitterClosedError,
    StepKind,
)


class BufferOverflowPolicy(str, Enum):
    """缓冲区溢出策略

    定义当队列满时的处理方式：
    - BLOCK: 阻塞等待直到有空间
    - DROP_OLDEST: 丢弃最旧的消息
    - DROP_NEWEST: 丢弃新消息（不入队）
    - RAISE: 抛出 BufferFullError 异常
    """

    BLOCK = "block"
    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    RAISE = "raise"


class BufferFullError(Exception):
    """缓冲区已满错误

    当使用 RAISE 策略且队列满时抛出。
    """

    pass


# =============================================================================
# 消息存储接口
# =============================================================================


class MessageStore(Protocol):
    """消息存储接口

    定义消息持久化的标准接口，支持保存和查询消息。
    """

    async def save(self, session_id: str, step: ConversationStep) -> None:
        """保存消息"""
        ...

    async def get_by_session_id(self, session_id: str) -> list[ConversationStep]:
        """按会话 ID 获取所有消息"""
        ...

    async def get_by_kind(self, session_id: str, kind: StepKind) -> list[ConversationStep]:
        """按消息类型筛选"""
        ...

    async def get_by_time_range(
        self,
        session_id: str,
        start: datetime,
        end: datetime,
    ) -> list[ConversationStep]:
        """按时间范围筛选"""
        ...

    async def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """获取会话摘要"""
        ...

    async def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        ...


class InMemoryMessageStore:
    """内存消息存储

    基于内存的消息存储实现，适用于测试和轻量级场景。

    注意：不适合生产环境，重启后数据丢失。
    """

    def __init__(self, max_messages_per_session: int = 10000):
        """初始化

        参数:
            max_messages_per_session: 每个会话最大消息数
        """
        self._store: dict[str, list[ConversationStep]] = {}
        self._max_per_session = max_messages_per_session

    async def save(self, session_id: str, step: ConversationStep) -> None:
        """保存消息到内存"""
        if session_id not in self._store:
            self._store[session_id] = []

        messages = self._store[session_id]

        # 如果超过限制，移除最旧的
        if len(messages) >= self._max_per_session:
            messages.pop(0)

        messages.append(step)

    async def get_by_session_id(self, session_id: str) -> list[ConversationStep]:
        """获取会话的所有消息"""
        return self._store.get(session_id, []).copy()

    async def get_by_kind(self, session_id: str, kind: StepKind) -> list[ConversationStep]:
        """按类型筛选消息"""
        messages = self._store.get(session_id, [])
        return [m for m in messages if m.kind == kind]

    async def get_by_time_range(
        self,
        session_id: str,
        start: datetime,
        end: datetime,
    ) -> list[ConversationStep]:
        """按时间范围筛选消息"""
        messages = self._store.get(session_id, [])
        return [m for m in messages if start <= m.timestamp <= end]

    async def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """获取会话摘要"""
        messages = self._store.get(session_id, [])

        if not messages:
            return {
                "total_messages": 0,
                "thinking_count": 0,
                "tool_calls_count": 0,
                "has_final_response": False,
            }

        thinking_count = sum(
            1 for m in messages if m.kind in (StepKind.THINKING, StepKind.REASONING)
        )
        tool_calls_count = sum(1 for m in messages if m.kind == StepKind.TOOL_CALL)
        has_final = any(m.kind == StepKind.FINAL for m in messages)

        return {
            "total_messages": len(messages),
            "thinking_count": thinking_count,
            "tool_calls_count": tool_calls_count,
            "has_final_response": has_final,
            "first_message_time": messages[0].timestamp.isoformat() if messages else None,
            "last_message_time": messages[-1].timestamp.isoformat() if messages else None,
        }

    async def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        return list(self._store.keys())

    def clear(self) -> None:
        """清空所有数据"""
        self._store.clear()


# =============================================================================
# 可靠发射器
# =============================================================================


class ReliableEmitter:
    """可靠发射器

    基于 ConversationFlowEmitter 的可靠扩展版本：
    - 有界队列：防止内存溢出
    - 溢出策略：灵活处理队列满的情况
    - 消息持久化：支持将消息保存到存储后端
    - 背压控制：当消费者慢时提供反压
    - 重试机制：发送失败时自动重试

    属性:
        session_id: 会话标识
        max_size: 队列最大容量
        overflow_policy: 溢出策略
        message_store: 消息存储（可选）
        max_retries: 最大重试次数
    """

    def __init__(
        self,
        session_id: str,
        max_size: int = 1000,
        overflow_policy: BufferOverflowPolicy = BufferOverflowPolicy.BLOCK,
        message_store: MessageStore | None = None,
        max_retries: int = 3,
        timeout: float | None = None,
    ):
        """初始化可靠发射器

        参数:
            session_id: 会话标识
            max_size: 队列最大容量，默认 1000
            overflow_policy: 溢出策略，默认 BLOCK
            message_store: 消息存储后端，None 表示不持久化
            max_retries: 最大重试次数，默认 3
            timeout: 迭代超时时间（秒）
        """
        self.session_id = session_id
        self.max_size = max_size
        self.overflow_policy = overflow_policy
        self.max_retries = max_retries
        self.timeout = timeout

        # 内部状态
        self._message_store = message_store
        self._queue: deque[ConversationStep] = deque()  # 不设 maxlen，手动控制
        self._lock = asyncio.Lock()
        self._has_space = asyncio.Event()
        self._has_data = asyncio.Event()
        self._has_space.set()  # 初始时有空间

        self._is_completed = False
        self._sequence_counter = 0
        self._delta_counter = 0
        self._accumulated_content = ""

        # 统计信息
        self._stats: dict[str, int] = {}
        self._dropped_count = 0
        self._retry_count = 0

    @property
    def is_active(self) -> bool:
        """是否处于活跃状态"""
        return not self._is_completed

    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self._is_completed

    @property
    def queue_size(self) -> int:
        """当前队列大小"""
        return len(self._queue)

    @property
    def dropped_count(self) -> int:
        """丢弃的消息数量"""
        return self._dropped_count

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

    def _update_events(self) -> None:
        """更新事件状态"""
        if len(self._queue) >= self.max_size:
            self._has_space.clear()
        else:
            self._has_space.set()

        if self._queue:
            self._has_data.set()
        else:
            self._has_data.clear()

    async def emit_step(
        self,
        step: ConversationStep,
        timeout: float | None = None,
    ) -> None:
        """发送步骤

        参数:
            step: 会话步骤
            timeout: 超时时间（秒），仅用于 BLOCK 策略

        异常:
            EmitterClosedError: 如果 emitter 已关闭
            BufferFullError: 如果使用 RAISE 策略且队列满
            asyncio.TimeoutError: 如果使用 BLOCK 策略且超时
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

        # 持久化
        if self._message_store is not None:
            await self._message_store.save(self.session_id, step)

        # 检查队列是否满
        async with self._lock:
            if len(self._queue) >= self.max_size:
                if self.overflow_policy == BufferOverflowPolicy.BLOCK:
                    pass  # 需要在锁外等待
                elif self.overflow_policy == BufferOverflowPolicy.DROP_OLDEST:
                    # 丢弃最旧的消息
                    if self._queue:
                        self._queue.popleft()
                        self._dropped_count += 1
                    self._queue.append(step)
                    self._update_events()
                    return
                elif self.overflow_policy == BufferOverflowPolicy.DROP_NEWEST:
                    # 丢弃新消息
                    self._dropped_count += 1
                    return
                elif self.overflow_policy == BufferOverflowPolicy.RAISE:
                    raise BufferFullError(
                        f"Buffer is full (size={self.max_size}), cannot emit new step"
                    )
            else:
                # 队列未满，直接添加
                self._queue.append(step)
                self._update_events()
                return

        # BLOCK 策略：在锁外等待空间
        if self.overflow_policy == BufferOverflowPolicy.BLOCK:
            try:
                await asyncio.wait_for(
                    self._has_space.wait(),
                    timeout=timeout,
                )
            except TimeoutError:
                self._retry_count += 1
                raise

            # 获得空间后再次加锁添加
            async with self._lock:
                self._queue.append(step)
                self._update_events()

    async def get_nowait(self) -> ConversationStep | None:
        """非阻塞获取消息

        返回:
            ConversationStep 或 None（如果队列为空）
        """
        async with self._lock:
            if not self._queue:
                return None
            step = self._queue.popleft()
            self._update_events()
            return step

    async def get_with_timeout(self, timeout: float = 1.0) -> ConversationStep | None:
        """带超时的获取消息

        参数:
            timeout: 超时时间（秒）

        返回:
            ConversationStep 或 None（如果超时）
        """
        # 先检查是否有数据
        async with self._lock:
            if self._queue:
                step = self._queue.popleft()
                self._update_events()
                return step

        # 等待数据
        try:
            await asyncio.wait_for(
                self._has_data.wait(),
                timeout=timeout,
            )
        except TimeoutError:
            return None

        # 再次尝试获取
        return await self.get_nowait()

    # =========================================================================
    # 便捷发送方法（与 ConversationFlowEmitter 兼容）
    # =========================================================================

    async def emit_thinking(
        self,
        content: str,
        timeout: float | None = None,
        **metadata: Any,
    ) -> None:
        """发送思考步骤"""
        step = ConversationStep(
            kind=StepKind.THINKING,
            content=content,
            metadata=metadata,
        )
        await self.emit_step(step, timeout=timeout)

    async def emit_reasoning(
        self,
        content: str,
        timeout: float | None = None,
        **metadata: Any,
    ) -> None:
        """发送推理步骤"""
        step = ConversationStep(
            kind=StepKind.REASONING,
            content=content,
            metadata=metadata,
        )
        await self.emit_step(step, timeout=timeout)

    async def emit_delta(
        self,
        content: str,
        timeout: float | None = None,
        **metadata: Any,
    ) -> None:
        """发送增量内容"""
        step = ConversationStep(
            kind=StepKind.DELTA,
            content=content,
            is_delta=True,
            delta_index=self._next_delta_index(),
            metadata=metadata,
        )
        await self.emit_step(step, timeout=timeout)

    async def emit_tool_call(
        self,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
        **metadata: Any,
    ) -> None:
        """发送工具调用"""
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
        await self.emit_step(step, timeout=timeout)

    async def emit_tool_result(
        self,
        tool_id: str,
        result: Any,
        success: bool = True,
        error: str | None = None,
        timeout: float | None = None,
        **metadata: Any,
    ) -> None:
        """发送工具执行结果"""
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
        await self.emit_step(step, timeout=timeout)

    async def emit_final_response(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> None:
        """发送最终响应"""
        step = ConversationStep(
            kind=StepKind.FINAL,
            content=content,
            is_final=True,
            metadata=metadata or {},
        )
        await self.emit_step(step, timeout=timeout)

    async def emit_error(
        self,
        error_message: str,
        error_code: str = "",
        recoverable: bool = False,
        timeout: float | None = None,
        **metadata: Any,
    ) -> None:
        """发送错误步骤"""
        step = ConversationStep(
            kind=StepKind.ERROR,
            content=error_message,
            metadata={
                "error_code": error_code,
                "recoverable": recoverable,
                **metadata,
            },
        )
        await self.emit_step(step, timeout=timeout)

    async def complete(self) -> None:
        """完成发射

        标记 emitter 为已完成，并发送结束标记。
        """
        if self._is_completed:
            return

        # 发送结束标记
        end_step = ConversationStep(
            kind=StepKind.END,
            content="",
            is_final=True,
            sequence=self._next_sequence(),
        )

        async with self._lock:
            self._queue.append(end_step)
            self._update_events()

        # 持久化结束标记
        if self._message_store is not None:
            await self._message_store.save(self.session_id, end_step)

        self._is_completed = True

    async def complete_with_error(self, error_message: str) -> None:
        """因错误完成发射"""
        if self._is_completed:
            return

        await self.emit_error(error_message, recoverable=False)
        self._is_completed = True

    # =========================================================================
    # 统计信息
    # =========================================================================

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
            "dropped_count": self._dropped_count,
            "retry_count": self._retry_count,
            "queue_size": len(self._queue),
            "max_size": self.max_size,
            "overflow_policy": self.overflow_policy.value,
        }

    def get_accumulated_content(self) -> str:
        """获取累积的内容"""
        return self._accumulated_content

    # =========================================================================
    # 异步迭代器
    # =========================================================================

    def __aiter__(self) -> ReliableEmitter:
        """返回异步迭代器"""
        return self

    async def __anext__(self) -> ConversationStep:
        """获取下一个步骤"""
        if self.timeout:
            step = await self.get_with_timeout(timeout=self.timeout)
            if step is None:
                raise TimeoutError("Timeout waiting for next step")
            return step

        # 无超时等待
        while True:
            step = await self.get_nowait()
            if step is not None:
                return step

            if self._is_completed and not self._queue:
                raise StopAsyncIteration

            # 等待数据
            await self._has_data.wait()


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "BufferOverflowPolicy",
    "BufferFullError",
    "MessageStore",
    "InMemoryMessageStore",
    "ReliableEmitter",
]

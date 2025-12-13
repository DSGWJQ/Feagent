"""
ConversationAgent state module.

This module is the Phase-2 (Step-1) scaffold for splitting state-related concerns
out of `src/domain/agents/conversation_agent.py`.

Scope (planned):
- State machine: `ConversationAgentState`, `VALID_STATE_TRANSITIONS`
- Concurrency primitives: `_state_lock`, `_critical_event_lock`
- Task tracking: `_pending_tasks`, `_create_tracked_task`
- Event publishing helpers: `_publish_critical_event`, `_publish_notification_event`
- Sub-agent wait/resume lifecycle helpers and listeners

Note: This file intentionally contains *no logic* yet. It only defines the public
types and a mixin skeleton with method signatures to be implemented in follow-up
steps.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event, EventBus

# Public API exports for backward compatibility
__all__ = [
    "ConversationAgentState",
    "VALID_STATE_TRANSITIONS",
    "StateChangedEvent",
    "SpawnSubAgentEvent",
    "ConversationAgentStateMixin",
]


class ConversationAgentState(str, Enum):
    """ConversationAgent 状态枚举 (Phase 3)

    跟踪 Agent 执行状态，特别是子Agent等待场景。

    状态：
    - IDLE: 空闲，等待用户输入
    - PROCESSING: 正在处理（ReAct循环中）
    - WAITING_FOR_SUBAGENT: 等待子Agent结果
    - COMPLETED: 处理完成
    - ERROR: 发生错误
    """

    IDLE = "idle"
    PROCESSING = "processing"
    WAITING_FOR_SUBAGENT = "waiting_for_subagent"
    COMPLETED = "completed"
    ERROR = "error"


# 有效状态转换矩阵（不可变）
VALID_STATE_TRANSITIONS: dict[ConversationAgentState, tuple[ConversationAgentState, ...]] = {
    ConversationAgentState.IDLE: (
        ConversationAgentState.PROCESSING,
        ConversationAgentState.ERROR,
    ),
    ConversationAgentState.PROCESSING: (
        ConversationAgentState.WAITING_FOR_SUBAGENT,
        ConversationAgentState.COMPLETED,
        ConversationAgentState.ERROR,
        ConversationAgentState.IDLE,  # 取消或重置
    ),
    ConversationAgentState.WAITING_FOR_SUBAGENT: (
        ConversationAgentState.PROCESSING,  # 收到子Agent结果后恢复
        ConversationAgentState.ERROR,
    ),
    ConversationAgentState.COMPLETED: (
        ConversationAgentState.IDLE,  # 重新开始
    ),
    ConversationAgentState.ERROR: (
        ConversationAgentState.IDLE,  # 重置
    ),
}


@dataclass
class StateChangedEvent(Event):
    """状态变化事件 (Phase 3)

    当 ConversationAgent 状态发生变化时发布此事件。
    协调者Agent订阅此事件以跟踪Agent状态。

    属性：
    - from_state: 原状态
    - to_state: 新状态
    - session_id: 会话ID
    """

    from_state: str = ""
    to_state: str = ""
    session_id: str = ""

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "conversation_agent_state_changed"


@dataclass
class SpawnSubAgentEvent(Event):
    """生成子Agent事件 (Phase 3)

    当 ConversationAgent 需要生成子Agent执行任务时发布此事件。
    Coordinator 订阅此事件以创建和执行子Agent。

    属性：
    - subagent_type: 子Agent类型（search, mcp, python_executor, data_processor）
    - task_payload: 任务负载数据
    - priority: 优先级（数字越小优先级越高）
    - session_id: 会话ID
    - context_snapshot: 上下文快照（可选）
    """

    subagent_type: str = ""
    task_payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    session_id: str = ""
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "spawn_subagent_requested"


class ConversationAgentStateMixin:
    """State mixin for ConversationAgent (skeleton).

    Design goals:
    - Keep `ConversationAgent` public API stable while moving stateful behaviors here.
    - Avoid importing `ConversationAgent` to prevent circular dependencies.
    - Require only minimal host attributes (`event_bus`, `session_context.session_id`, etc.).

    TODO(Phase-2 Step-2+):
    - Implement all methods listed below.
    - Provide a clear initialization hook (e.g. `_init_state_mixin`) and call it from
      the host `ConversationAgent.__init__`.
    """

    # --- Host-provided attributes (expected to exist on the concrete class) ---
    event_bus: EventBus | None
    session_context: Any  # expected: has `.session_id` at runtime

    # --- State / concurrency primitives (initialized by mixin init hook) ---
    _state: ConversationAgentState
    _state_lock: asyncio.Lock
    _critical_event_lock: asyncio.Lock
    _pending_tasks: set[asyncio.Task[Any]]

    # --- Sub-agent wait/resume fields ---
    pending_subagent_id: str | None
    pending_task_id: str | None
    suspended_context: dict[str, Any] | None

    # --- Sub-agent result storage ---
    last_subagent_result: dict[str, Any] | None
    subagent_result_history: list[dict[str, Any]]
    _is_listening_subagent_completions: bool

    # ---------------------------------------------------------------------
    # Initialization hook
    # ---------------------------------------------------------------------

    def _init_state_mixin(self) -> None:
        """Initialize state/locks/task tracking fields.

        NOTE:
        - This hook must be called by the host `ConversationAgent.__init__`.
        - It intentionally does not import `ConversationAgent` to avoid circular deps.
        """
        self._state = ConversationAgentState.IDLE
        self._state_lock = asyncio.Lock()
        self._pending_tasks = set()
        self._critical_event_lock = asyncio.Lock()

        self.pending_subagent_id = None
        self.pending_task_id = None
        self.suspended_context = None

        self.last_subagent_result = None
        self.subagent_result_history = []
        self._is_listening_subagent_completions = False

    # ---------------------------------------------------------------------
    # Task tracking
    # ---------------------------------------------------------------------

    def _create_tracked_task(self, coro: Any) -> asyncio.Task[Any]:
        """创建被追踪的异步任务

        防止任务在完成前被垃圾回收（P0 Race Condition 修复）

        参数：
            coro: 协程对象

        返回：
            被追踪的 Task 对象
        """
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        return task

    # ---------------------------------------------------------------------
    # Event publishing helpers
    # ---------------------------------------------------------------------

    async def _publish_critical_event(self, event: Event) -> None:
        """发布关键事件（P0-2 Fix）

        关键事件需要保证：
        1. 按顺序发布（使用_critical_event_lock）
        2. 必须等待发布完成（await）
        3. 不与_state_lock嵌套以避免死锁

        适用场景：StateChangedEvent、SpawnSubAgentEvent等需要严格顺序的事件

        参数：
            event: 事件对象
        """
        if not self.event_bus:
            return
        async with self._critical_event_lock:
            await self.event_bus.publish(event)

    def _publish_notification_event(self, event: Event) -> None:
        """发布通知事件（P0-2 Fix）

        通知事件特点：
        1. 后台异步发布
        2. 被追踪以防止丢失
        3. 不阻塞主流程

        适用场景：SaveRequest、进度通知等非关键事件

        参数：
            event: 事件对象
        """
        if not self.event_bus:
            return
        self._create_tracked_task(self.event_bus.publish(event))

    # ---------------------------------------------------------------------
    # State transitions
    # ---------------------------------------------------------------------

    def _transition_locked(self, new_state: ConversationAgentState) -> ConversationAgentState:
        """状态转换（锁内版本，不发布事件，P0-2 Optimization）

        此方法必须在 _state_lock 内调用，用于消除原子性空窗。
        调用者负责在释放锁后发布 StateChangedEvent。

        参数：
            new_state: 目标状态

        返回：
            旧状态（用于事件发布）

        异常：
            DomainError: 无效的状态转换
        """
        from src.domain.exceptions import DomainError

        valid_transitions = VALID_STATE_TRANSITIONS.get(self._state, ())
        if new_state not in valid_transitions:
            raise DomainError(f"Invalid state transition: {self._state.value} -> {new_state.value}")

        old_state = self._state
        self._state = new_state
        return old_state

    @property
    def state(self) -> ConversationAgentState:
        """获取当前状态"""
        return self._state

    def transition_to(self, new_state: ConversationAgentState) -> None:
        """状态转换（同步版本）

        注意：同步版本无法await事件发布，仅适用于非关键路径。
        在异步上下文中请使用transition_to_async以保证关键事件顺序。

        参数：
            new_state: 目标状态

        异常：
            DomainError: 无效的状态转换
        """
        from src.domain.exceptions import DomainError

        valid_transitions = VALID_STATE_TRANSITIONS.get(self._state, ())
        if new_state not in valid_transitions:
            raise DomainError(f"Invalid state transition: {self._state.value} -> {new_state.value}")

        old_state = self._state
        self._state = new_state

        # P0-2 Fix: 使用通知事件后台追踪发布（避免阻塞同步调用）
        event = StateChangedEvent(
            from_state=old_state.value,
            to_state=new_state.value,
            session_id=self.session_context.session_id,
            source="conversation_agent",
        )
        self._publish_notification_event(event)

    async def transition_to_async(self, new_state: ConversationAgentState) -> None:
        """状态转换（异步版本，P0-2 Fix）

        保证：
        1. _state修改受_state_lock保护
        2. StateChangedEvent按顺序await发布

        参数：
            new_state: 目标状态

        异常：
            DomainError: 无效的状态转换
        """
        async with self._state_lock:
            from src.domain.exceptions import DomainError

            valid_transitions = VALID_STATE_TRANSITIONS.get(self._state, ())
            if new_state not in valid_transitions:
                raise DomainError(
                    f"Invalid state transition: {self._state.value} -> {new_state.value}"
                )

            old_state = self._state
            self._state = new_state

            event = StateChangedEvent(
                from_state=old_state.value,
                to_state=new_state.value,
                session_id=self.session_context.session_id,
                source="conversation_agent",
            )

        # 释放_state_lock后再发布事件，避免与订阅者产生死锁
        await self._publish_critical_event(event)

    # ---------------------------------------------------------------------
    # Sub-agent wait / resume
    # ---------------------------------------------------------------------

    def wait_for_subagent(self, subagent_id: str, task_id: str, context: dict[str, Any]) -> None:
        """Suspend execution and enter WAITING_FOR_SUBAGENT (sync).

        TODO(Phase-2 Step-4): Implement + deepcopy snapshot semantics.
        """
        raise NotImplementedError

    def resume_from_subagent(self, result: dict[str, Any]) -> dict[str, Any]:
        """Resume execution from a suspended state (sync).

        TODO(Phase-2 Step-4): Implement + deepcopy restore semantics.
        """
        raise NotImplementedError

    async def wait_for_subagent_async(
        self, subagent_id: str, task_id: str, context: dict[str, Any]
    ) -> None:
        """Suspend execution and enter WAITING_FOR_SUBAGENT (async).

        TODO(Phase-2 Step-4): Implement atomic updates under `_state_lock`.
        """
        raise NotImplementedError

    async def resume_from_subagent_async(self, result: dict[str, Any]) -> dict[str, Any]:
        """Resume execution from a suspended state (async).

        TODO(Phase-2 Step-4): Implement atomic restore under `_state_lock`.
        """
        raise NotImplementedError

    def is_waiting_for_subagent(self) -> bool:
        """Check whether agent is waiting for a sub-agent.

        TODO(Phase-2 Step-4): Implement.
        """
        raise NotImplementedError

    def is_processing(self) -> bool:
        """Check whether agent is in PROCESSING state.

        TODO(Phase-2 Step-4): Implement.
        """
        raise NotImplementedError

    def is_idle(self) -> bool:
        """Check whether agent is in IDLE state.

        TODO(Phase-2 Step-4): Implement.
        """
        raise NotImplementedError

    # ---------------------------------------------------------------------
    # Sub-agent completion listener (lifecycle)
    # ---------------------------------------------------------------------

    def start_subagent_completion_listener(self) -> None:
        """Subscribe to sub-agent completion events.

        TODO(Phase-2 Step-5): Implement (ensure idempotent start).
        """
        raise NotImplementedError

    def stop_subagent_completion_listener(self) -> None:
        """Unsubscribe from sub-agent completion events.

        TODO(Phase-2 Step-5): Implement (ensure idempotent stop).
        """
        raise NotImplementedError

    async def _handle_subagent_completed_wrapper(self, event: Any) -> None:
        """Wrapper handler for sub-agent completion events.

        TODO(Phase-2 Step-5): Implement wrapper that delegates to `handle_subagent_completed`.
        """
        raise NotImplementedError

    async def handle_subagent_completed(self, event: Any) -> None:
        """Handle sub-agent completion events.

        TODO(Phase-2 Step-5): Implement lock-protected checks + result storage + resume.
        """
        raise NotImplementedError

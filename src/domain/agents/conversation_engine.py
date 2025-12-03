"""ConversationEngine - 对话 Agent 主循环引擎 (Phase 2)

业务定义：
- ConversationEngine 是 ConversationAgent 的外层驱动引擎
- 负责完整的对话处理生命周期：接收→上下文获取→任务分解→调度→执行→完成
- 支持 pause/resume 实现可中断的长任务处理
- 通过异步 Generator 模式 yield 事件，支持流式处理

生命周期：
1. RECEIVING: 接收用户输入
2. CONTEXT_FETCHING: 从协调者获取上下文（规则、知识、工具）
3. DECOMPOSING: 将复杂任务分解为子任务
4. SCHEDULING: 调度子任务执行顺序
5. EXECUTING: 执行子任务
6. PAUSED: 暂停状态（可恢复）
7. COMPLETED: 处理完成
8. ERROR: 发生错误

使用示例：
    engine = ConversationEngine(coordinator=coordinator, llm=llm)

    async for event in engine.run("帮我分析销售数据"):
        print(f"Event: {event.event_type}, Data: {event.data}")

        if event.event_type == EngineEventType.TASK_DECOMPOSED:
            # 可以在这里暂停
            engine.pause()

    # 恢复执行
    engine.resume()
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class EngineState(str, Enum):
    """引擎状态枚举

    定义 ConversationEngine 的所有可能状态。

    状态：
    - IDLE: 空闲，等待启动
    - RECEIVING: 接收用户输入
    - CONTEXT_FETCHING: 获取协调者上下文
    - DECOMPOSING: 分解任务
    - SCHEDULING: 调度子任务
    - EXECUTING: 执行子任务
    - PAUSED: 暂停（可恢复）
    - COMPLETED: 完成
    - ERROR: 错误
    """

    IDLE = "idle"
    RECEIVING = "receiving"
    CONTEXT_FETCHING = "context_fetching"
    DECOMPOSING = "decomposing"
    SCHEDULING = "scheduling"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class EngineEventType(str, Enum):
    """引擎事件类型枚举

    定义引擎运行期间可以 yield 的事件类型。
    """

    STATE_CHANGED = "state_changed"
    CONTEXT_RECEIVED = "context_received"
    TASK_DECOMPOSED = "task_decomposed"
    TASK_SCHEDULED = "task_scheduled"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    ENGINE_PAUSED = "engine_paused"
    ENGINE_RESUMED = "engine_resumed"
    ENGINE_COMPLETED = "engine_completed"
    ENGINE_ERROR = "engine_error"


@dataclass
class EngineEvent:
    """引擎事件

    引擎运行期间 yield 的事件结构。

    属性：
        event_type: 事件类型
        data: 事件数据
        timestamp: 时间戳
    """

    event_type: EngineEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SubTask:
    """子任务定义

    分解后的子任务结构。

    属性：
        id: 任务ID
        description: 任务描述
        type: 任务类型
        priority: 优先级（数字越小优先级越高）
        status: 任务状态
        result: 执行结果
    """

    id: str
    description: str
    type: str = "generic"
    priority: int = 0
    status: str = "pending"
    result: Any = None
    dependencies: list[str] = field(default_factory=list)


class EngineLLM(Protocol):
    """引擎使用的 LLM 接口"""

    async def decompose_goal(self, goal: str) -> list[dict[str, Any]]:
        """分解目标为子任务"""
        ...


class EngineCoordinator(Protocol):
    """引擎使用的协调者接口"""

    async def get_context_async(
        self,
        user_input: str,
        workflow_id: str | None = None,
    ) -> Any:
        """获取上下文"""
        ...


# 有效状态转换
VALID_ENGINE_TRANSITIONS: dict[EngineState, list[EngineState]] = {
    EngineState.IDLE: [EngineState.RECEIVING, EngineState.ERROR],
    EngineState.RECEIVING: [EngineState.CONTEXT_FETCHING, EngineState.ERROR],
    EngineState.CONTEXT_FETCHING: [
        EngineState.DECOMPOSING,
        EngineState.PAUSED,
        EngineState.ERROR,
    ],
    EngineState.DECOMPOSING: [
        EngineState.SCHEDULING,
        EngineState.PAUSED,
        EngineState.ERROR,
    ],
    EngineState.SCHEDULING: [
        EngineState.EXECUTING,
        EngineState.PAUSED,
        EngineState.ERROR,
    ],
    EngineState.EXECUTING: [
        EngineState.SCHEDULING,  # 继续下一个任务
        EngineState.COMPLETED,
        EngineState.PAUSED,
        EngineState.ERROR,
    ],
    EngineState.PAUSED: [
        EngineState.CONTEXT_FETCHING,
        EngineState.DECOMPOSING,
        EngineState.SCHEDULING,
        EngineState.EXECUTING,
        EngineState.ERROR,
    ],
    EngineState.COMPLETED: [EngineState.IDLE],
    EngineState.ERROR: [EngineState.IDLE],
}


class ConversationEngine:
    """对话 Agent 主循环引擎

    负责驱动 ConversationAgent 的完整生命周期，
    支持 pause/resume 和事件流式处理。
    """

    def __init__(
        self,
        coordinator: EngineCoordinator | None = None,
        llm: EngineLLM | None = None,
        max_tasks: int = 100,
    ):
        """初始化引擎

        参数：
            coordinator: 协调者（用于获取上下文）
            llm: LLM（用于任务分解）
            max_tasks: 最大任务数量限制
        """
        self.coordinator = coordinator
        self.llm = llm
        self.max_tasks = max_tasks

        # 状态管理
        self._state: EngineState = EngineState.IDLE
        self._previous_state: EngineState | None = None

        # 任务管理
        self._tasks: list[SubTask] = []
        self._current_task_index: int = 0
        self._completed_task_count: int = 0

        # 上下文缓存
        self._context: Any = None
        self._user_input: str = ""

        # 暂停/恢复控制
        self._pause_requested: bool = False
        self._resume_event: asyncio.Event = asyncio.Event()
        self._resume_event.set()  # 初始状态不暂停

        # 快照数据
        self._snapshot_data: dict[str, Any] = {}

    @property
    def state(self) -> EngineState:
        """当前引擎状态"""
        return self._state

    @property
    def current_progress(self) -> float:
        """当前进度（0.0 - 1.0）"""
        if not self._tasks:
            return 0.0
        return self._completed_task_count / len(self._tasks)

    @property
    def total_tasks(self) -> int:
        """总任务数"""
        return len(self._tasks)

    @property
    def completed_tasks(self) -> int:
        """已完成任务数"""
        return self._completed_task_count

    def _transition_to(self, new_state: EngineState) -> bool:
        """状态转换

        参数：
            new_state: 目标状态

        返回：
            是否转换成功
        """
        valid_transitions = VALID_ENGINE_TRANSITIONS.get(self._state, [])
        if new_state not in valid_transitions:
            logger.warning(f"Invalid state transition: {self._state.value} -> {new_state.value}")
            return False

        self._previous_state = self._state
        self._state = new_state
        logger.debug(f"Engine state: {self._previous_state.value} -> {new_state.value}")
        return True

    async def run(self, user_input: str) -> AsyncIterator[EngineEvent]:
        """运行引擎主循环

        异步生成器，yield 事件流。

        参数：
            user_input: 用户输入

        Yields:
            EngineEvent: 引擎事件
        """
        self._user_input = user_input

        try:
            # === 阶段 1: 接收输入 ===
            self._transition_to(EngineState.RECEIVING)
            yield EngineEvent(
                event_type=EngineEventType.STATE_CHANGED,
                data={"from": "idle", "to": "receiving", "input": user_input},
            )

            # 检查暂停
            if self._pause_requested:
                yield await self._handle_pause()

            # === 阶段 2: 获取上下文 ===
            self._transition_to(EngineState.CONTEXT_FETCHING)
            yield EngineEvent(
                event_type=EngineEventType.STATE_CHANGED,
                data={"from": "receiving", "to": "context_fetching"},
            )

            context_event = await self._fetch_context(user_input)
            yield context_event

            if context_event.event_type == EngineEventType.ENGINE_ERROR:
                return

            # 检查暂停
            if self._pause_requested:
                yield await self._handle_pause()

            # === 阶段 3: 任务分解 ===
            self._transition_to(EngineState.DECOMPOSING)
            yield EngineEvent(
                event_type=EngineEventType.STATE_CHANGED,
                data={"from": "context_fetching", "to": "decomposing"},
            )

            decompose_event = await self._decompose_tasks(user_input)
            yield decompose_event

            if decompose_event.event_type == EngineEventType.ENGINE_ERROR:
                return

            # 检查暂停
            if self._pause_requested:
                yield await self._handle_pause()

            # === 阶段 4: 调度任务 ===
            self._transition_to(EngineState.SCHEDULING)
            yield EngineEvent(
                event_type=EngineEventType.STATE_CHANGED,
                data={"from": "decomposing", "to": "scheduling"},
            )

            # 按优先级排序任务
            self._tasks.sort(key=lambda t: t.priority)

            for task in self._tasks:
                yield EngineEvent(
                    event_type=EngineEventType.TASK_SCHEDULED,
                    data={
                        "task_id": task.id,
                        "description": task.description,
                        "priority": task.priority,
                    },
                )

            # === 阶段 5: 执行任务 ===
            async for event in self._execute_tasks():
                yield event

                # 检查暂停
                if self._pause_requested:
                    yield await self._handle_pause()

            # === 阶段 6: 完成 ===
            self._transition_to(EngineState.COMPLETED)
            yield EngineEvent(
                event_type=EngineEventType.STATE_CHANGED,
                data={"from": "executing", "to": "completed"},
            )

            yield EngineEvent(
                event_type=EngineEventType.ENGINE_COMPLETED,
                data={
                    "total_tasks": len(self._tasks),
                    "completed_tasks": self._completed_task_count,
                    "user_input": user_input,
                },
            )

        except Exception as e:
            logger.error(f"Engine error: {e}")
            self._transition_to(EngineState.ERROR)
            yield EngineEvent(
                event_type=EngineEventType.ENGINE_ERROR,
                data={"error": str(e), "message": str(e)},
            )

    async def _fetch_context(self, user_input: str) -> EngineEvent:
        """获取协调者上下文

        参数：
            user_input: 用户输入

        返回：
            上下文事件或错误事件
        """
        if not self.coordinator:
            # 没有协调者，返回空上下文
            self._context = None
            return EngineEvent(
                event_type=EngineEventType.CONTEXT_RECEIVED,
                data={"context": None, "source": "none"},
            )

        try:
            self._context = await self.coordinator.get_context_async(user_input)

            context_data = {
                "source": "coordinator",
                "rules_count": len(getattr(self._context, "rules", [])),
                "tools_count": len(getattr(self._context, "tools", [])),
                "knowledge_count": len(getattr(self._context, "knowledge", [])),
            }

            logger.info(
                f"Context fetched: rules={context_data['rules_count']}, "
                f"tools={context_data['tools_count']}"
            )

            return EngineEvent(
                event_type=EngineEventType.CONTEXT_RECEIVED,
                data=context_data,
            )

        except Exception as e:
            logger.error(f"Failed to fetch context: {e}")
            self._transition_to(EngineState.ERROR)
            return EngineEvent(
                event_type=EngineEventType.ENGINE_ERROR,
                data={"error": str(e), "message": f"Context fetch failed: {e}"},
            )

    async def _decompose_tasks(self, user_input: str) -> EngineEvent:
        """分解任务

        参数：
            user_input: 用户输入

        返回：
            分解事件或错误事件
        """
        if not self.llm:
            # 没有 LLM，创建单一任务
            self._tasks = [
                SubTask(
                    id="task_default",
                    description=user_input,
                    type="direct",
                    priority=0,
                )
            ]
            return EngineEvent(
                event_type=EngineEventType.TASK_DECOMPOSED,
                data={
                    "task_count": 1,
                    "tasks": [{"id": "task_default", "description": user_input}],
                },
            )

        try:
            decomposed = await self.llm.decompose_goal(user_input)

            self._tasks = []
            for i, task_data in enumerate(decomposed[: self.max_tasks]):
                task = SubTask(
                    id=task_data.get("id", f"task_{i}"),
                    description=task_data.get("description", ""),
                    type=task_data.get("type", "generic"),
                    priority=task_data.get("priority", i),
                    dependencies=task_data.get("dependencies", []),
                )
                self._tasks.append(task)

            logger.info(f"Decomposed into {len(self._tasks)} tasks")

            return EngineEvent(
                event_type=EngineEventType.TASK_DECOMPOSED,
                data={
                    "task_count": len(self._tasks),
                    "tasks": [
                        {"id": t.id, "description": t.description, "type": t.type}
                        for t in self._tasks
                    ],
                },
            )

        except Exception as e:
            logger.error(f"Failed to decompose tasks: {e}")
            self._transition_to(EngineState.ERROR)
            return EngineEvent(
                event_type=EngineEventType.ENGINE_ERROR,
                data={"error": str(e), "message": f"Task decomposition failed: {e}"},
            )

    async def _execute_tasks(self) -> AsyncIterator[EngineEvent]:
        """执行任务

        Yields:
            任务执行相关事件
        """
        self._transition_to(EngineState.EXECUTING)
        yield EngineEvent(
            event_type=EngineEventType.STATE_CHANGED,
            data={"from": "scheduling", "to": "executing"},
        )

        for task in self._tasks:
            # 检查暂停
            await self._resume_event.wait()

            if self._pause_requested:
                return

            # 任务开始
            task.status = "running"
            yield EngineEvent(
                event_type=EngineEventType.TASK_STARTED,
                data={"task_id": task.id, "description": task.description},
            )

            # 模拟任务执行
            await asyncio.sleep(0.01)  # 最小延迟

            # 任务完成
            task.status = "completed"
            task.result = {"success": True}
            self._completed_task_count += 1

            yield EngineEvent(
                event_type=EngineEventType.TASK_COMPLETED,
                data={
                    "task_id": task.id,
                    "result": task.result,
                    "progress": self.current_progress,
                },
            )

    async def _handle_pause(self) -> EngineEvent:
        """处理暂停请求

        返回：
            暂停事件
        """
        self._previous_state = self._state
        self._transition_to(EngineState.PAUSED)

        event = EngineEvent(
            event_type=EngineEventType.ENGINE_PAUSED,
            data={
                "previous_state": self._previous_state.value if self._previous_state else "unknown",
                "progress": self.current_progress,
                "completed_tasks": self._completed_task_count,
            },
        )

        logger.info(f"Engine paused at state: {self._previous_state}")

        # 等待恢复
        self._resume_event.clear()
        await self._resume_event.wait()

        # 恢复后的事件
        self._pause_requested = False

        return event

    def pause(self) -> bool:
        """暂停引擎

        返回：
            是否成功请求暂停
        """
        if self._state in (EngineState.IDLE, EngineState.COMPLETED, EngineState.ERROR):
            logger.warning(f"Cannot pause engine in state: {self._state.value}")
            return False

        self._pause_requested = True
        self._previous_state = self._state
        self._state = EngineState.PAUSED
        logger.info("Pause requested")
        return True

    def resume(self) -> bool:
        """恢复引擎

        返回：
            是否成功恢复
        """
        if self._state != EngineState.PAUSED:
            logger.warning(f"Cannot resume engine in state: {self._state.value}")
            return False

        # 恢复到之前的状态
        if self._previous_state:
            self._state = self._previous_state

        self._pause_requested = False
        self._resume_event.set()

        logger.info(f"Engine resumed to state: {self._state.value}")
        return True

    def create_snapshot(self) -> dict[str, Any]:
        """创建引擎快照

        返回：
            快照数据字典
        """
        return {
            "state": self._state.value,
            "previous_state": self._previous_state.value if self._previous_state else None,
            "progress": self.current_progress,
            "total_tasks": len(self._tasks),
            "completed_tasks": self._completed_task_count,
            "current_task_index": self._current_task_index,
            "user_input": self._user_input,
            "tasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "type": t.type,
                    "priority": t.priority,
                    "status": t.status,
                }
                for t in self._tasks
            ],
            "timestamp": datetime.now().isoformat(),
        }

    def restore_from_snapshot(self, snapshot: dict[str, Any]) -> bool:
        """从快照恢复引擎状态

        参数：
            snapshot: 快照数据

        返回：
            是否成功恢复
        """
        try:
            self._state = EngineState(snapshot.get("state", "idle"))
            prev_state = snapshot.get("previous_state")
            self._previous_state = EngineState(prev_state) if prev_state else None
            self._completed_task_count = snapshot.get("completed_tasks", 0)
            self._current_task_index = snapshot.get("current_task_index", 0)
            self._user_input = snapshot.get("user_input", "")

            # 恢复任务列表
            self._tasks = []
            for task_data in snapshot.get("tasks", []):
                task = SubTask(
                    id=task_data.get("id", ""),
                    description=task_data.get("description", ""),
                    type=task_data.get("type", "generic"),
                    priority=task_data.get("priority", 0),
                    status=task_data.get("status", "pending"),
                )
                self._tasks.append(task)

            logger.info(f"Engine restored from snapshot, state: {self._state.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore from snapshot: {e}")
            return False

    def reset(self) -> None:
        """重置引擎到初始状态"""
        self._state = EngineState.IDLE
        self._previous_state = None
        self._tasks = []
        self._current_task_index = 0
        self._completed_task_count = 0
        self._context = None
        self._user_input = ""
        self._pause_requested = False
        self._resume_event.set()

        logger.info("Engine reset to initial state")

    # === Phase 3: 子任务调度与隔离 ===

    async def spawn_subtask(
        self,
        subtask: "SubTask",
        executor: Any,
    ) -> Any:
        """在隔离环境中执行子任务

        创建隔离的执行上下文，执行子任务，返回结果。
        子任务的修改不会影响主上下文。

        参数：
            subtask: 子任务定义
            executor: 执行器（实现 SubTaskExecutor 协议）

        返回：
            SubTaskResult 执行结果
        """
        from src.domain.agents.subtask_executor import (
            SubTaskContainer,
        )
        from src.domain.value_objects.execution_context import ExecutionContext

        # 获取或创建执行上下文
        parent_context = self._context
        if parent_context is None:
            parent_context = ExecutionContext.create()

        # 创建隔离容器
        container = SubTaskContainer(
            subtask_id=subtask.id,
            parent_context=parent_context,
        )

        # 执行子任务
        task_data = {
            "id": subtask.id,
            "description": subtask.description,
            "type": subtask.type,
            "priority": subtask.priority,
        }

        result = await container.execute(
            executor=executor,
            task_data=task_data,
        )

        logger.debug(f"Spawned subtask {subtask.id}: success={result.success}")
        return result

    async def execute_subtasks_isolated(
        self,
        subtasks: list["SubTask"],
        executors: list[Any],
        parallel: bool = False,
    ) -> list[Any]:
        """执行多个子任务，每个在隔离环境中

        参数：
            subtasks: 子任务列表
            executors: 执行器列表（与子任务一一对应）
            parallel: 是否并行执行

        返回：
            SubTaskResult 列表
        """
        from src.domain.agents.subtask_executor import SubTaskResult
        from src.domain.value_objects.execution_context import ExecutionContext

        if len(subtasks) != len(executors):
            raise ValueError("subtasks and executors must have the same length")

        results: list[SubTaskResult] = []

        if parallel:
            # 并行执行
            tasks = [
                self.spawn_subtask(subtask, executor)
                for subtask, executor in zip(subtasks, executors, strict=False)
            ]
            results = await asyncio.gather(*tasks)
        else:
            # 顺序执行
            for subtask, executor in zip(subtasks, executors, strict=False):
                result = await self.spawn_subtask(subtask, executor)
                results.append(result)

        # 将结果合并到引擎上下文
        if self._context is None:
            self._context = ExecutionContext.create()

        for result in results:
            if result.success:
                self._context.set_task_result(
                    result.subtask_id,
                    {
                        "success": result.success,
                        "output": result.output,
                        "execution_time": result.execution_time,
                    },
                )

        logger.info(
            f"Executed {len(subtasks)} subtasks: "
            f"{sum(1 for r in results if r.success)} succeeded, "
            f"{sum(1 for r in results if not r.success)} failed"
        )

        return results


# 导出
__all__ = [
    "EngineState",
    "EngineEventType",
    "EngineEvent",
    "SubTask",
    "ConversationEngine",
]

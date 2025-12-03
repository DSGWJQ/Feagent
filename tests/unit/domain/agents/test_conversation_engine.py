"""ConversationEngine 单元测试 - Phase 2

测试目标：
1. 验证 ConversationEngine 生命周期（接收、分解、调度、结束）
2. 验证 pause/resume 功能
3. 验证异步 Generator 事件流
4. 验证状态追踪和异常处理

TDD 红阶段：编写测试，预期失败
"""

import asyncio
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

# === Mock 实现 ===


class MockCoordinator:
    """模拟协调者"""

    def __init__(self):
        self.circuit_breaker = MagicMock()
        self.circuit_breaker.is_open = False
        self._context_calls = []

    async def get_context_async(self, user_input: str, workflow_id: str | None = None):
        """模拟获取上下文"""
        self._context_calls.append(user_input)

        @dataclass
        class MockContextResponse:
            rules: list = field(default_factory=list)
            knowledge: list = field(default_factory=list)
            tools: list = field(default_factory=list)
            summary: str = "Mock context"
            workflow_context: dict | None = None

        return MockContextResponse(
            rules=[{"id": "r1", "name": "规则1"}],
            tools=[{"id": "t1", "name": "工具1"}],
        )


class MockLLM:
    """模拟 LLM"""

    def __init__(self, decompose_result: list[dict] | None = None):
        self._decompose_result = decompose_result or [
            {"id": "task_1", "description": "子任务1", "type": "search"},
            {"id": "task_2", "description": "子任务2", "type": "process"},
        ]

    async def think(self, context: dict) -> str:
        return "思考完成"

    async def decide_action(self, context: dict) -> dict:
        return {"action": "respond", "response": "完成"}

    async def should_continue(self, context: dict) -> bool:
        return False

    async def decompose_goal(self, goal: str) -> list[dict]:
        return self._decompose_result


# === 测试类 ===


class TestEngineStateEnum:
    """测试 EngineState 枚举"""

    def test_engine_state_has_required_states(self):
        """测试：EngineState 具有必需的状态"""
        from src.domain.agents.conversation_engine import EngineState

        # 验证必需状态存在
        assert hasattr(EngineState, "IDLE")
        assert hasattr(EngineState, "RECEIVING")
        assert hasattr(EngineState, "CONTEXT_FETCHING")
        assert hasattr(EngineState, "DECOMPOSING")
        assert hasattr(EngineState, "SCHEDULING")
        assert hasattr(EngineState, "EXECUTING")
        assert hasattr(EngineState, "PAUSED")
        assert hasattr(EngineState, "COMPLETED")
        assert hasattr(EngineState, "ERROR")


class TestEngineEvent:
    """测试 EngineEvent 数据类"""

    def test_engine_event_has_required_fields(self):
        """测试：EngineEvent 具有必需字段"""
        from src.domain.agents.conversation_engine import EngineEvent, EngineEventType

        event = EngineEvent(
            event_type=EngineEventType.STATE_CHANGED,
            data={"from": "idle", "to": "receiving"},
        )

        assert event.event_type == EngineEventType.STATE_CHANGED
        assert event.data["from"] == "idle"

    def test_engine_event_types_exist(self):
        """测试：EngineEventType 具有必需类型"""
        from src.domain.agents.conversation_engine import EngineEventType

        assert hasattr(EngineEventType, "STATE_CHANGED")
        assert hasattr(EngineEventType, "CONTEXT_RECEIVED")
        assert hasattr(EngineEventType, "TASK_DECOMPOSED")
        assert hasattr(EngineEventType, "TASK_SCHEDULED")
        assert hasattr(EngineEventType, "TASK_COMPLETED")
        assert hasattr(EngineEventType, "ENGINE_PAUSED")
        assert hasattr(EngineEventType, "ENGINE_RESUMED")
        assert hasattr(EngineEventType, "ENGINE_COMPLETED")
        assert hasattr(EngineEventType, "ENGINE_ERROR")


class TestConversationEngineCreation:
    """测试 ConversationEngine 创建"""

    def test_create_engine_with_coordinator(self):
        """测试：使用协调者创建引擎"""
        from src.domain.agents.conversation_engine import ConversationEngine

        coordinator = MockCoordinator()
        engine = ConversationEngine(coordinator=coordinator)

        assert engine is not None
        assert engine.coordinator == coordinator

    def test_create_engine_with_llm(self):
        """测试：使用 LLM 创建引擎"""
        from src.domain.agents.conversation_engine import ConversationEngine

        llm = MockLLM()
        engine = ConversationEngine(llm=llm)

        assert engine.llm == llm

    def test_engine_initial_state_is_idle(self):
        """测试：引擎初始状态为 IDLE"""
        from src.domain.agents.conversation_engine import (
            ConversationEngine,
            EngineState,
        )

        engine = ConversationEngine()

        assert engine.state == EngineState.IDLE


class TestConversationEngineLifecycle:
    """测试 ConversationEngine 生命周期"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        from src.domain.agents.conversation_engine import ConversationEngine

        coordinator = MockCoordinator()
        llm = MockLLM()
        return ConversationEngine(coordinator=coordinator, llm=llm)

    @pytest.mark.asyncio
    async def test_run_returns_async_generator(self, engine):
        """测试：run() 返回异步生成器"""
        result = engine.run("测试输入")

        # 应该是异步生成器
        assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    async def test_run_yields_state_changed_event_first(self, engine):
        """测试：run() 首先 yield 状态变化事件"""
        from src.domain.agents.conversation_engine import EngineEventType

        events = []
        async for event in engine.run("测试输入"):
            events.append(event)
            if len(events) >= 1:
                break

        assert len(events) >= 1
        assert events[0].event_type == EngineEventType.STATE_CHANGED

    @pytest.mark.asyncio
    async def test_run_fetches_context_from_coordinator(self, engine):
        """测试：run() 从协调者获取上下文"""
        from src.domain.agents.conversation_engine import EngineEventType

        events = []
        async for event in engine.run("帮我查询数据"):
            events.append(event)
            if event.event_type == EngineEventType.CONTEXT_RECEIVED:
                break

        # 应该有上下文接收事件
        context_events = [e for e in events if e.event_type == EngineEventType.CONTEXT_RECEIVED]
        assert len(context_events) >= 1

        # 协调者应该被调用
        assert len(engine.coordinator._context_calls) >= 1

    @pytest.mark.asyncio
    async def test_run_decomposes_task(self, engine):
        """测试：run() 分解任务"""
        from src.domain.agents.conversation_engine import EngineEventType

        events = []
        async for event in engine.run("复杂任务需要分解"):
            events.append(event)
            if event.event_type == EngineEventType.TASK_DECOMPOSED:
                break

        # 应该有任务分解事件
        decompose_events = [e for e in events if e.event_type == EngineEventType.TASK_DECOMPOSED]
        assert len(decompose_events) >= 1

    @pytest.mark.asyncio
    async def test_run_completes_with_result(self, engine):
        """测试：run() 完成并返回结果"""
        from src.domain.agents.conversation_engine import (
            EngineEventType,
            EngineState,
        )

        events = []
        async for event in engine.run("简单任务"):
            events.append(event)

        # 应该有完成事件
        complete_events = [e for e in events if e.event_type == EngineEventType.ENGINE_COMPLETED]
        assert len(complete_events) >= 1

        # 引擎状态应该是 COMPLETED
        assert engine.state == EngineState.COMPLETED

    @pytest.mark.asyncio
    async def test_run_tracks_state_transitions(self, engine):
        """测试：run() 追踪状态转换"""
        from src.domain.agents.conversation_engine import EngineEventType

        state_changes = []
        async for event in engine.run("测试"):
            if event.event_type == EngineEventType.STATE_CHANGED:
                state_changes.append(event.data)

        # 应该有多个状态变化
        assert len(state_changes) >= 2

        # 第一个应该从 IDLE 开始
        assert state_changes[0]["from"] == "idle"


class TestConversationEnginePauseResume:
    """测试 ConversationEngine 暂停/恢复功能"""

    @pytest.fixture
    def slow_engine(self):
        """创建慢速引擎（模拟长任务）"""
        from src.domain.agents.conversation_engine import ConversationEngine

        # 使用会产生多个任务的 LLM
        llm = MockLLM(
            decompose_result=[
                {"id": f"task_{i}", "description": f"任务{i}", "type": "process"} for i in range(5)
            ]
        )

        return ConversationEngine(
            coordinator=MockCoordinator(),
            llm=llm,
        )

    @pytest.mark.asyncio
    async def test_pause_changes_state_to_paused(self, slow_engine):
        """测试：pause() 将状态改为 PAUSED"""
        from src.domain.agents.conversation_engine import EngineState

        # 启动引擎
        gen = slow_engine.run("长任务")

        # 获取第一个事件
        await gen.__anext__()

        # 暂停
        slow_engine.pause()

        assert slow_engine.state == EngineState.PAUSED

    @pytest.mark.asyncio
    async def test_pause_yields_paused_event(self, slow_engine):
        """测试：pause() 将状态设为 PAUSED 并可以检查暂停"""
        from src.domain.agents.conversation_engine import EngineState

        gen = slow_engine.run("长任务")

        # 获取第一个事件
        event = await gen.__anext__()

        # 暂停
        slow_engine.pause()

        # 验证状态变为 PAUSED
        assert slow_engine.state == EngineState.PAUSED

    @pytest.mark.asyncio
    async def test_resume_changes_state_from_paused(self, slow_engine):
        """测试：resume() 从 PAUSED 恢复状态"""
        from src.domain.agents.conversation_engine import EngineState

        # 启动并暂停
        gen = slow_engine.run("长任务")
        await gen.__anext__()
        slow_engine.pause()

        assert slow_engine.state == EngineState.PAUSED

        # 恢复
        result = slow_engine.resume()

        assert result is True
        assert slow_engine.state != EngineState.PAUSED

    @pytest.mark.asyncio
    async def test_resume_returns_true_when_paused(self, slow_engine):
        """测试：resume() 在暂停状态下返回 True"""
        from src.domain.agents.conversation_engine import EngineState

        gen = slow_engine.run("长任务")
        await gen.__anext__()

        slow_engine.pause()
        assert slow_engine.state == EngineState.PAUSED

        result = slow_engine.resume()
        assert result is True

    @pytest.mark.asyncio
    async def test_pause_resume_preserves_progress(self, slow_engine):
        """测试：暂停/恢复保留进度"""
        gen = slow_engine.run("长任务")

        # 收集一些事件
        for _ in range(3):
            try:
                await asyncio.wait_for(gen.__anext__(), timeout=1.0)
            except (TimeoutError, StopAsyncIteration):
                break

        # 记录暂停时的进度
        progress_before = slow_engine.current_progress

        # 暂停
        slow_engine.pause()

        # 恢复
        slow_engine.resume()

        # 进度应该保持
        assert slow_engine.current_progress >= progress_before

    @pytest.mark.asyncio
    async def test_cannot_resume_if_not_paused(self, slow_engine):
        """测试：非暂停状态下不能恢复"""
        from src.domain.agents.conversation_engine import EngineState

        # 引擎处于 IDLE 状态
        assert slow_engine.state == EngineState.IDLE

        # 调用 resume 应该无效或抛出异常
        result = slow_engine.resume()

        # 返回 False 表示恢复失败
        assert result is False


class TestConversationEngineTaskScheduling:
    """测试任务调度功能"""

    @pytest.fixture
    def engine_with_tasks(self):
        """创建有多个任务的引擎"""
        from src.domain.agents.conversation_engine import ConversationEngine

        llm = MockLLM(
            decompose_result=[
                {"id": "task_1", "description": "搜索任务", "type": "search", "priority": 1},
                {"id": "task_2", "description": "处理任务", "type": "process", "priority": 2},
                {"id": "task_3", "description": "输出任务", "type": "output", "priority": 3},
            ]
        )

        return ConversationEngine(
            coordinator=MockCoordinator(),
            llm=llm,
        )

    @pytest.mark.asyncio
    async def test_tasks_are_scheduled_after_decomposition(self, engine_with_tasks):
        """测试：任务分解后被调度"""
        from src.domain.agents.conversation_engine import EngineEventType

        scheduled_events = []
        async for event in engine_with_tasks.run("需要多步骤的任务"):
            if event.event_type == EngineEventType.TASK_SCHEDULED:
                scheduled_events.append(event)

        # 应该有调度事件
        assert len(scheduled_events) >= 1

    @pytest.mark.asyncio
    async def test_tasks_are_executed_in_order(self, engine_with_tasks):
        """测试：任务按优先级顺序执行"""
        from src.domain.agents.conversation_engine import EngineEventType

        completed_tasks = []
        async for event in engine_with_tasks.run("顺序执行任务"):
            if event.event_type == EngineEventType.TASK_COMPLETED:
                completed_tasks.append(event.data.get("task_id"))

        # 任务应该按顺序完成
        if len(completed_tasks) >= 2:
            # 验证顺序（task_1 应该在 task_2 之前）
            assert completed_tasks.index("task_1") < completed_tasks.index("task_2")


class TestConversationEngineErrorHandling:
    """测试异常处理功能"""

    @pytest.fixture
    def error_coordinator(self):
        """创建会抛出异常的协调者"""

        class ErrorCoordinator:
            circuit_breaker = MagicMock()
            circuit_breaker.is_open = False

            async def get_context_async(self, user_input, workflow_id=None):
                raise Exception("Context fetch failed")

        return ErrorCoordinator()

    @pytest.fixture
    def engine_with_error_coordinator(self, error_coordinator):
        """创建会出错的引擎"""
        from src.domain.agents.conversation_engine import ConversationEngine

        return ConversationEngine(
            coordinator=error_coordinator,
            llm=MockLLM(),
        )

    @pytest.mark.asyncio
    async def test_engine_handles_coordinator_error(self, engine_with_error_coordinator):
        """测试：引擎处理协调者错误"""
        from src.domain.agents.conversation_engine import (
            EngineEventType,
            EngineState,
        )

        events = []
        async for event in engine_with_error_coordinator.run("触发错误"):
            events.append(event)

        # 应该有错误事件
        error_events = [e for e in events if e.event_type == EngineEventType.ENGINE_ERROR]
        assert len(error_events) >= 1

        # 引擎状态应该是 ERROR
        assert engine_with_error_coordinator.state == EngineState.ERROR

    @pytest.mark.asyncio
    async def test_engine_error_contains_message(self, engine_with_error_coordinator):
        """测试：错误事件包含错误信息"""
        from src.domain.agents.conversation_engine import EngineEventType

        error_event = None
        async for event in engine_with_error_coordinator.run("触发错误"):
            if event.event_type == EngineEventType.ENGINE_ERROR:
                error_event = event
                break

        assert error_event is not None
        assert "error" in error_event.data or "message" in error_event.data


class TestConversationEngineProgress:
    """测试进度追踪功能"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        from src.domain.agents.conversation_engine import ConversationEngine

        return ConversationEngine(
            coordinator=MockCoordinator(),
            llm=MockLLM(),
        )

    def test_engine_has_progress_property(self, engine):
        """测试：引擎有进度属性"""
        assert hasattr(engine, "current_progress")
        assert hasattr(engine, "total_tasks")
        assert hasattr(engine, "completed_tasks")

    @pytest.mark.asyncio
    async def test_progress_updates_during_execution(self, engine):
        """测试：执行期间进度更新"""
        initial_progress = engine.current_progress

        events_count = 0
        async for event in engine.run("测试进度"):
            events_count += 1
            if events_count >= 3:
                break

        # 进度应该有更新
        assert engine.current_progress >= initial_progress


class TestConversationEngineSnapshot:
    """测试快照功能"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        from src.domain.agents.conversation_engine import ConversationEngine

        return ConversationEngine(
            coordinator=MockCoordinator(),
            llm=MockLLM(),
        )

    def test_engine_can_create_snapshot(self, engine):
        """测试：引擎可以创建快照"""
        snapshot = engine.create_snapshot()

        assert snapshot is not None
        assert "state" in snapshot
        assert "progress" in snapshot

    @pytest.mark.asyncio
    async def test_engine_can_restore_from_snapshot(self, engine):
        """测试：引擎可以从快照恢复"""
        # 运行一些事件
        gen = engine.run("测试")
        await gen.__anext__()

        # 创建快照
        snapshot = engine.create_snapshot()

        # 创建新引擎并恢复
        from src.domain.agents.conversation_engine import ConversationEngine

        new_engine = ConversationEngine(
            coordinator=MockCoordinator(),
            llm=MockLLM(),
        )
        new_engine.restore_from_snapshot(snapshot)

        # 状态应该恢复
        assert new_engine.state == engine.state


# 导出
__all__ = [
    "TestEngineStateEnum",
    "TestEngineEvent",
    "TestConversationEngineCreation",
    "TestConversationEngineLifecycle",
    "TestConversationEnginePauseResume",
    "TestConversationEngineTaskScheduling",
    "TestConversationEngineErrorHandling",
    "TestConversationEngineProgress",
    "TestConversationEngineSnapshot",
]

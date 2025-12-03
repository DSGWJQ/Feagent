"""ConversationEngine 端到端集成测试 - Phase 2

测试目标：
1. 验证 Engine 完整生命周期（接收→分解→调度→执行→完成）
2. 验证 Engine 与 CoordinatorAgent 集成
3. 验证暂停/恢复真实场景
4. 验证错误恢复和异常处理

运行命令：
    pytest tests/integration/test_conversation_engine_e2e.py -v -s
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.domain.agents.conversation_engine import (
    ConversationEngine,
    EngineEventType,
    EngineState,
)
from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

# === Mock 实现 ===


@dataclass
class MockTool:
    """模拟工具"""

    id: str
    name: str
    description: str
    category: str = "general"
    status: str = "published"
    tags: list[str] = field(default_factory=list)


class MockToolRepository:
    """模拟工具仓库"""

    def __init__(self, tools: list[MockTool] | None = None):
        self._tools = tools or []

    def find_all(self) -> list[MockTool]:
        return self._tools

    def find_published(self) -> list[MockTool]:
        return [t for t in self._tools if t.status == "published"]


class MockKnowledgeRetriever:
    """模拟知识检索器"""

    def __init__(self, results: list[dict[str, Any]] | None = None):
        self._results = results or []

    async def retrieve_by_query(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        return self._results[:top_k]


class MockLLM:
    """模拟 LLM 用于任务分解"""

    def __init__(self, tasks: list[dict] | None = None):
        self._tasks = tasks or [
            {"id": "task_1", "description": "分析数据", "type": "analysis", "priority": 1},
            {"id": "task_2", "description": "生成报告", "type": "report", "priority": 2},
        ]

    async def decompose_goal(self, goal: str) -> list[dict[str, Any]]:
        """分解目标为子任务"""
        return self._tasks


# === 测试类 ===


class TestConversationEngineE2E:
    """ConversationEngine 端到端测试"""

    @pytest.fixture
    def coordinator(self):
        """配置协调者"""
        tools = [
            MockTool(id="t1", name="数据分析工具", description="分析数据"),
            MockTool(id="t2", name="报告生成工具", description="生成报告"),
        ]
        knowledge = [
            {"source_id": "k1", "title": "数据分析指南", "content_preview": "如何分析数据"},
        ]

        coordinator = CoordinatorAgent(
            knowledge_retriever=MockKnowledgeRetriever(knowledge),
        )
        coordinator.tool_repository = MockToolRepository(tools)

        # 添加规则
        coordinator.add_rule(Rule(id="r1", name="安全规则", priority=1))

        return coordinator

    @pytest.fixture
    def llm(self):
        """配置 LLM"""
        return MockLLM()

    @pytest.fixture
    def engine(self, coordinator, llm):
        """配置引擎"""
        return ConversationEngine(coordinator=coordinator, llm=llm)

    @pytest.mark.asyncio
    async def test_complete_lifecycle(self, engine):
        """测试：完整生命周期流程"""
        events = []

        async for event in engine.run("帮我分析销售数据并生成报告"):
            events.append(event)

        # 验证关键事件存在
        event_types = [e.event_type for e in events]

        # 应该有状态变化事件
        assert EngineEventType.STATE_CHANGED in event_types

        # 应该有上下文接收事件
        assert EngineEventType.CONTEXT_RECEIVED in event_types

        # 应该有任务分解事件
        assert EngineEventType.TASK_DECOMPOSED in event_types

        # 应该有任务调度事件
        assert EngineEventType.TASK_SCHEDULED in event_types

        # 应该有任务完成事件
        assert EngineEventType.TASK_COMPLETED in event_types

        # 应该有引擎完成事件
        assert EngineEventType.ENGINE_COMPLETED in event_types

        # 最终状态应该是 COMPLETED
        assert engine.state == EngineState.COMPLETED

    @pytest.mark.asyncio
    async def test_context_integration_with_coordinator(self, engine):
        """测试：与 CoordinatorAgent 的上下文集成"""
        context_event = None

        async for event in engine.run("查询 数据库 分析"):
            if event.event_type == EngineEventType.CONTEXT_RECEIVED:
                context_event = event
                break

        assert context_event is not None
        assert "rules_count" in context_event.data
        assert "tools_count" in context_event.data

        # 应该有规则和工具
        assert context_event.data["rules_count"] >= 1
        assert context_event.data["tools_count"] >= 1

    @pytest.mark.asyncio
    async def test_task_decomposition_and_scheduling(self, engine):
        """测试：任务分解和调度"""
        decompose_event = None
        scheduled_tasks = []

        async for event in engine.run("复杂分析任务"):
            if event.event_type == EngineEventType.TASK_DECOMPOSED:
                decompose_event = event
            elif event.event_type == EngineEventType.TASK_SCHEDULED:
                scheduled_tasks.append(event)

        # 验证任务分解
        assert decompose_event is not None
        assert decompose_event.data["task_count"] == 2

        # 验证任务调度
        assert len(scheduled_tasks) == 2

        # 验证任务顺序（按优先级）
        assert scheduled_tasks[0].data["task_id"] == "task_1"
        assert scheduled_tasks[1].data["task_id"] == "task_2"

    @pytest.mark.asyncio
    async def test_task_execution_progress(self, engine):
        """测试：任务执行进度追踪"""
        completed_tasks = []

        async for event in engine.run("执行任务"):
            if event.event_type == EngineEventType.TASK_COMPLETED:
                completed_tasks.append(event)

        # 验证所有任务完成
        assert len(completed_tasks) == 2

        # 验证进度更新
        assert completed_tasks[0].data["progress"] == 0.5  # 1/2 完成
        assert completed_tasks[1].data["progress"] == 1.0  # 2/2 完成

        # 验证引擎进度属性
        assert engine.current_progress == 1.0
        assert engine.completed_tasks == 2
        assert engine.total_tasks == 2


class TestEnginePauseResumeE2E:
    """暂停/恢复端到端测试"""

    @pytest.fixture
    def slow_llm(self):
        """配置产生多个任务的 LLM"""
        return MockLLM(
            tasks=[
                {"id": f"task_{i}", "description": f"任务{i}", "type": "process", "priority": i}
                for i in range(5)
            ]
        )

    @pytest.fixture
    def engine(self, slow_llm):
        """配置引擎"""
        return ConversationEngine(llm=slow_llm)

    @pytest.mark.asyncio
    async def test_pause_during_execution(self, engine):
        """测试：执行期间暂停"""
        events = []
        gen = engine.run("长任务")

        # 收集前几个事件
        for _ in range(5):
            try:
                event = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
                events.append(event)
            except (TimeoutError, StopAsyncIteration):
                break

        # 记录暂停前的状态
        progress_before = engine.current_progress

        # 暂停引擎
        result = engine.pause()
        assert result is True
        assert engine.state == EngineState.PAUSED

        # 进度应该保持
        assert engine.current_progress == progress_before

    @pytest.mark.asyncio
    async def test_resume_continues_execution(self, engine):
        """测试：恢复后继续执行"""
        gen = engine.run("可恢复任务")

        # 获取一些事件
        for _ in range(3):
            try:
                await asyncio.wait_for(gen.__anext__(), timeout=1.0)
            except (TimeoutError, StopAsyncIteration):
                break

        # 暂停
        engine.pause()
        completed_before = engine.completed_tasks

        # 恢复
        result = engine.resume()
        assert result is True
        assert engine.state != EngineState.PAUSED

        # 可以继续处理
        assert engine.completed_tasks >= completed_before

    @pytest.mark.asyncio
    async def test_snapshot_and_restore(self, engine):
        """测试：快照和恢复"""
        gen = engine.run("快照测试")

        # 运行一些事件
        for _ in range(3):
            try:
                await asyncio.wait_for(gen.__anext__(), timeout=1.0)
            except (TimeoutError, StopAsyncIteration):
                break

        # 创建快照
        snapshot = engine.create_snapshot()

        assert snapshot is not None
        assert "state" in snapshot
        assert "progress" in snapshot
        assert "tasks" in snapshot

        # 创建新引擎并恢复
        new_engine = ConversationEngine()
        result = new_engine.restore_from_snapshot(snapshot)

        assert result is True
        assert new_engine.state == engine.state
        assert len(new_engine._tasks) == len(engine._tasks)


class TestEngineErrorHandlingE2E:
    """错误处理端到端测试"""

    @pytest.fixture
    def faulty_coordinator(self):
        """创建会失败的协调者"""

        class FaultyCoordinator:
            async def get_context_async(self, user_input, workflow_id=None):
                raise Exception("Coordinator error")

        return FaultyCoordinator()

    @pytest.fixture
    def engine_with_faulty_coordinator(self, faulty_coordinator):
        """配置有故障协调者的引擎"""
        return ConversationEngine(coordinator=faulty_coordinator)

    @pytest.mark.asyncio
    async def test_handles_coordinator_error_gracefully(
        self,
        engine_with_faulty_coordinator,
    ):
        """测试：优雅处理协调者错误"""
        events = []

        async for event in engine_with_faulty_coordinator.run("触发错误"):
            events.append(event)

        # 应该有错误事件
        error_events = [e for e in events if e.event_type == EngineEventType.ENGINE_ERROR]
        assert len(error_events) >= 1

        # 错误事件应该包含信息
        assert "error" in error_events[0].data or "message" in error_events[0].data

        # 引擎状态应该是 ERROR
        assert engine_with_faulty_coordinator.state == EngineState.ERROR

    @pytest.mark.asyncio
    async def test_reset_after_error(self, engine_with_faulty_coordinator):
        """测试：错误后重置"""
        # 触发错误
        async for event in engine_with_faulty_coordinator.run("错误"):
            pass

        assert engine_with_faulty_coordinator.state == EngineState.ERROR

        # 重置
        engine_with_faulty_coordinator.reset()

        assert engine_with_faulty_coordinator.state == EngineState.IDLE
        assert engine_with_faulty_coordinator.completed_tasks == 0
        assert engine_with_faulty_coordinator.total_tasks == 0


class TestEngineWithRealCoordinator:
    """使用真实 CoordinatorAgent 的集成测试"""

    @pytest.fixture
    def full_coordinator(self):
        """配置完整的协调者"""
        tools = [
            MockTool(
                id="http_tool",
                name="HTTP请求工具",
                description="发送HTTP请求",
                tags=["http", "api"],
            ),
            MockTool(
                id="db_tool",
                name="数据库工具",
                description="查询数据库",
                tags=["database", "sql"],
            ),
        ]

        knowledge = [
            {
                "source_id": "k1",
                "title": "API最佳实践",
                "content_preview": "HTTP请求应该设置超时",
            },
        ]

        coordinator = CoordinatorAgent(
            knowledge_retriever=MockKnowledgeRetriever(knowledge),
        )
        coordinator.tool_repository = MockToolRepository(tools)

        # 添加多个规则
        coordinator.add_rule(Rule(id="r1", name="安全规则", description="安全检查", priority=1))
        coordinator.add_rule(Rule(id="r2", name="限流规则", description="频率限制", priority=2))

        return coordinator

    @pytest.mark.asyncio
    async def test_engine_uses_coordinator_context(self, full_coordinator):
        """测试：引擎使用协调者上下文"""
        llm = MockLLM()
        engine = ConversationEngine(coordinator=full_coordinator, llm=llm)

        context_event = None
        async for event in engine.run("http api request"):
            if event.event_type == EngineEventType.CONTEXT_RECEIVED:
                context_event = event
                break

        assert context_event is not None

        # 应该获取到规则
        assert context_event.data["rules_count"] == 2

        # 应该获取到工具（基于 http api 关键词匹配）
        assert context_event.data["tools_count"] >= 1

    @pytest.mark.asyncio
    async def test_full_workflow_with_context(self, full_coordinator):
        """测试：带上下文的完整工作流"""
        llm = MockLLM(
            tasks=[
                {"id": "fetch", "description": "获取数据", "type": "http", "priority": 1},
                {"id": "process", "description": "处理数据", "type": "compute", "priority": 2},
                {"id": "store", "description": "存储结果", "type": "database", "priority": 3},
            ]
        )

        engine = ConversationEngine(coordinator=full_coordinator, llm=llm)

        events = []
        async for event in engine.run("获取API数据处理后存入数据库"):
            events.append(event)

        # 验证完整流程
        event_types = [e.event_type for e in events]

        assert EngineEventType.CONTEXT_RECEIVED in event_types
        assert EngineEventType.TASK_DECOMPOSED in event_types
        assert EngineEventType.ENGINE_COMPLETED in event_types

        # 验证3个任务都完成
        completed = [e for e in events if e.event_type == EngineEventType.TASK_COMPLETED]
        assert len(completed) == 3


# 导出
__all__ = [
    "TestConversationEngineE2E",
    "TestEnginePauseResumeE2E",
    "TestEngineErrorHandlingE2E",
    "TestEngineWithRealCoordinator",
]

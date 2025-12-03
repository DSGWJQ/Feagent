"""集成测试：子Agent调度框架端到端验证

测试目标：
1. 完整流程：ConversationAgent -> Coordinator -> SubAgent -> 结果回传
2. 真实场景模拟
3. 状态机正确转换
4. 结果正确写入上下文

完成标准：
- 端到端流程工作正常
- 状态转换符合预期
- 结果正确记录
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.agents.conversation_agent import (
    ConversationAgent,
    ConversationAgentState,
)
from src.domain.agents.coordinator_agent import (
    CoordinatorAgent,
    SubAgentCompletedEvent,
)
from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus
from src.domain.services.sub_agent_scheduler import (
    BaseSubAgent,
    SubAgentType,
)


def create_test_session_context(session_id: str = "test_session") -> SessionContext:
    """创建测试用的 SessionContext"""
    global_ctx = GlobalContext(user_id="test_user")
    return SessionContext(session_id=session_id, global_context=global_ctx)


class MockSearchAgent(BaseSubAgent):
    """模拟搜索子Agent"""

    @property
    def agent_type(self) -> SubAgentType:
        return SubAgentType.SEARCH

    async def _execute_internal(
        self, task: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        query = task.get("query", "")
        return {
            "results": [
                {"title": f"Result 1 for: {query}", "url": "https://example.com/1"},
                {"title": f"Result 2 for: {query}", "url": "https://example.com/2"},
            ],
            "total": 2,
        }

    def get_capabilities(self) -> dict[str, Any]:
        return {"can_search": True, "max_results": 10}


class MockPythonExecutor(BaseSubAgent):
    """模拟Python执行子Agent"""

    @property
    def agent_type(self) -> SubAgentType:
        return SubAgentType.PYTHON_EXECUTOR

    async def _execute_internal(
        self, task: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        code = task.get("code", "")
        return {
            "stdout": f"Executed: {code}",
            "stderr": "",
            "exit_code": 0,
        }

    def get_capabilities(self) -> dict[str, Any]:
        return {"can_execute_python": True, "timeout": 30}


class TestSubAgentE2EFlow:
    """测试子Agent端到端流程"""

    @pytest.fixture
    def event_bus(self):
        """创建真实的 EventBus"""
        return EventBus()

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="需要搜索相关信息")
        llm.decide_action = AsyncMock(
            return_value={"action_type": "spawn_subagent", "subagent_type": "search"}
        )
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    @pytest.fixture
    def session_context(self):
        """创建测试会话上下文"""
        return create_test_session_context("e2e_session")

    @pytest.fixture
    def coordinator(self, event_bus):
        """创建配置好的 Coordinator"""
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.register_subagent_type(SubAgentType.SEARCH, MockSearchAgent)
        coordinator.register_subagent_type(SubAgentType.PYTHON_EXECUTOR, MockPythonExecutor)
        coordinator.start_subagent_listener()
        return coordinator

    @pytest.fixture
    def conversation_agent(self, session_context, mock_llm, event_bus):
        """创建配置好的 ConversationAgent"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        agent.start_subagent_completion_listener()
        return agent

    @pytest.mark.asyncio
    async def test_full_spawn_execute_return_flow(self, conversation_agent, coordinator, event_bus):
        """测试完整的生成-执行-返回流程"""
        # 1. ConversationAgent 转到处理状态
        conversation_agent.transition_to(ConversationAgentState.PROCESSING)
        assert conversation_agent.state == ConversationAgentState.PROCESSING

        # 2. ConversationAgent 请求生成子Agent
        subagent_id = conversation_agent.request_subagent_spawn(
            subagent_type="search",
            task_payload={"query": "Python asyncio tutorial"},
            wait_for_result=True,
        )

        # 3. 验证状态转换为等待
        assert conversation_agent.state == ConversationAgentState.WAITING_FOR_SUBAGENT
        assert conversation_agent.pending_subagent_id is not None

        # 4. 手动触发 Coordinator 执行子Agent（模拟事件处理）
        result = await coordinator.execute_subagent(
            subagent_type="search",
            task_payload={"query": "Python asyncio tutorial"},
            context={},
            session_id="e2e_session",
        )

        # 5. 验证执行成功
        assert result.success is True
        assert "results" in result.output
        assert result.output["total"] == 2

        # 6. 验证 Coordinator 存储了结果
        session_results = coordinator.get_session_subagent_results("e2e_session")
        assert len(session_results) == 1
        assert session_results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_conversation_agent_receives_completion_event(
        self, conversation_agent, coordinator, event_bus
    ):
        """测试 ConversationAgent 接收完成事件"""
        # 1. 设置为等待状态
        conversation_agent.transition_to(ConversationAgentState.PROCESSING)
        subagent_id = conversation_agent.request_subagent_spawn(
            subagent_type="search",
            task_payload={"query": "test"},
            wait_for_result=True,
        )

        assert conversation_agent.state == ConversationAgentState.WAITING_FOR_SUBAGENT

        # 2. 创建完成事件
        completion_event = SubAgentCompletedEvent(
            subagent_id=subagent_id,
            subagent_type="search",
            session_id="e2e_session",
            success=True,
            result={"data": "搜索结果数据"},
            source="coordinator_agent",
        )

        # 3. 直接调用处理方法（模拟事件传递）
        conversation_agent.handle_subagent_completed(completion_event)

        # 4. 验证状态恢复
        assert conversation_agent.state == ConversationAgentState.PROCESSING

        # 5. 验证结果存储
        assert conversation_agent.last_subagent_result is not None
        assert conversation_agent.last_subagent_result["success"] is True

    @pytest.mark.asyncio
    async def test_multiple_subagent_executions(self, coordinator, event_bus):
        """测试多个子Agent执行"""
        session_id = "multi_session"

        # 执行搜索子Agent
        result1 = await coordinator.execute_subagent(
            subagent_type="search",
            task_payload={"query": "first query"},
            context={},
            session_id=session_id,
        )

        # 执行Python执行器子Agent
        result2 = await coordinator.execute_subagent(
            subagent_type="python_executor",
            task_payload={"code": "print('hello')"},
            context={},
            session_id=session_id,
        )

        # 验证两次执行都成功
        assert result1.success is True
        assert result2.success is True

        # 验证会话结果记录了两次执行
        session_results = coordinator.get_session_subagent_results(session_id)
        assert len(session_results) == 2

    @pytest.mark.asyncio
    async def test_subagent_result_history(self, conversation_agent):
        """测试子Agent结果历史记录"""
        conversation_agent.transition_to(ConversationAgentState.PROCESSING)

        # 模拟多次子Agent完成事件
        for i in range(3):
            conversation_agent.wait_for_subagent(
                subagent_id=f"subagent_{i}",
                task_id=f"task_{i}",
                context={},
            )

            event = SubAgentCompletedEvent(
                subagent_id=f"subagent_{i}",
                subagent_type="search",
                success=True,
                result={"data": f"result_{i}"},
            )
            conversation_agent.handle_subagent_completed(event)

        # 验证历史记录
        assert len(conversation_agent.subagent_result_history) == 3
        assert conversation_agent.subagent_result_history[0]["subagent_id"] == "subagent_0"
        assert conversation_agent.subagent_result_history[2]["subagent_id"] == "subagent_2"

    @pytest.mark.asyncio
    async def test_failed_subagent_handling(self, coordinator):
        """测试失败的子Agent处理"""

        class FailingAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.DATA_PROCESSOR

            async def _execute_internal(self, task, context):
                raise ValueError("Processing failed")

            def get_capabilities(self):
                return {}

        coordinator.register_subagent_type(SubAgentType.DATA_PROCESSOR, FailingAgent)

        result = await coordinator.execute_subagent(
            subagent_type="data_processor",
            task_payload={},
            context={},
            session_id="fail_session",
        )

        # 验证失败结果
        assert result.success is False
        assert "Processing failed" in result.error

        # 验证失败也被记录
        session_results = coordinator.get_session_subagent_results("fail_session")
        assert len(session_results) == 1
        assert session_results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_spawn_decision_creation(self, conversation_agent):
        """测试 spawn 决策创建"""
        from src.domain.agents.conversation_agent import DecisionType

        decision = conversation_agent.create_spawn_subagent_decision(
            subagent_type="search",
            task_payload={"query": "test query"},
            context_snapshot={"current_step": 1},
            priority=1,
        )

        assert decision.type == DecisionType.SPAWN_SUBAGENT
        assert decision.payload["subagent_type"] == "search"
        assert decision.payload["task_payload"]["query"] == "test query"
        assert decision.payload["priority"] == 1


class TestStateTransitionFlow:
    """测试状态转换流程"""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考中")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    @pytest.fixture
    def session_context(self):
        return create_test_session_context()

    @pytest.fixture
    def event_bus(self):
        return MagicMock()

    def test_complete_state_lifecycle(self, session_context, mock_llm, event_bus):
        """测试完整的状态生命周期"""
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )

        # 初始状态
        assert agent.state == ConversationAgentState.IDLE

        # IDLE -> PROCESSING
        agent.transition_to(ConversationAgentState.PROCESSING)
        assert agent.state == ConversationAgentState.PROCESSING

        # PROCESSING -> WAITING_FOR_SUBAGENT
        agent.wait_for_subagent("sa_1", "task_1", {})
        assert agent.state == ConversationAgentState.WAITING_FOR_SUBAGENT

        # WAITING_FOR_SUBAGENT -> PROCESSING (收到结果)
        agent.resume_from_subagent({"data": "result"})
        assert agent.state == ConversationAgentState.PROCESSING

        # PROCESSING -> COMPLETED
        agent.transition_to(ConversationAgentState.COMPLETED)
        assert agent.state == ConversationAgentState.COMPLETED

        # COMPLETED -> IDLE (重置)
        agent.transition_to(ConversationAgentState.IDLE)
        assert agent.state == ConversationAgentState.IDLE


# 导出
__all__ = [
    "TestSubAgentE2EFlow",
    "TestStateTransitionFlow",
]

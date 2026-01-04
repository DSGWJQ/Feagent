"""ConversationAgent 与 Emitter 集成测试 - Phase 2

测试目标：
1. ConversationAgent 接受 emitter 依赖
2. ReAct 循环中调用 emitter.emit_*
3. 思考步骤通过 emitter 发送
4. 最终响应通过 emitter 发送
5. 错误情况下 emitter 正确处理
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import GlobalContext, SessionContext

# ==================== 基础集成测试 ====================


class TestConversationAgentEmitterIntegration:
    """测试 ConversationAgent 与 Emitter 集成"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="正在分析用户需求...")
        llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "任务完成"}
        )
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    @pytest.fixture
    def emitter(self):
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        return ConversationFlowEmitter(session_id="session_1")

    def test_conversation_agent_accepts_emitter(self, session_context, mock_llm, emitter):
        """测试：ConversationAgent 应接受 emitter 参数"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
        )

        assert agent.emitter is emitter

    def test_conversation_agent_emitter_is_optional(self, session_context, mock_llm):
        """测试：emitter 参数应是可选的"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
        )

        assert agent.emitter is None

    @pytest.mark.asyncio
    async def test_react_loop_emits_thinking(self, session_context, mock_llm, emitter):
        """测试：ReAct 循环应通过 emitter 发送思考步骤"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            max_iterations=2,
        )

        # 运行 ReAct 循环
        await agent.run_async("帮我创建工作流")

        # 收集 emitter 中的步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 应有思考步骤
        thinking_steps = [s for s in steps if s.kind == StepKind.THINKING]
        assert len(thinking_steps) >= 1
        assert thinking_steps[0].content == "正在分析用户需求..."

    @pytest.mark.asyncio
    async def test_react_loop_emits_final_response(self, session_context, mock_llm, emitter):
        """测试：ReAct 循环应通过 emitter 发送最终响应"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
        )

        await agent.run_async("帮我创建工作流")

        # 收集 emitter 中的步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 应有最终响应步骤
        final_steps = [s for s in steps if s.kind == StepKind.FINAL]
        assert len(final_steps) == 1
        assert final_steps[0].content == "任务完成"

    @pytest.mark.asyncio
    async def test_react_loop_completes_emitter(self, session_context, mock_llm, emitter):
        """测试：ReAct 循环完成后应调用 emitter.complete()"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
        )

        await agent.run_async("帮我创建工作流")

        # 收集 emitter 中的步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 应有结束标记
        end_steps = [s for s in steps if s.kind == StepKind.END]
        assert len(end_steps) == 1

        # emitter 应已完成
        assert emitter.is_completed is True


# ==================== 多迭代测试 ====================


class TestMultiIterationEmission:
    """测试多迭代场景下的 emitter 行为"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def emitter(self):
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        return ConversationFlowEmitter(session_id="session_1")

    @pytest.mark.asyncio
    async def test_multiple_iterations_emit_multiple_thinking(self, session_context, emitter):
        """测试：多次迭代应发送多个思考步骤"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        # 模拟 3 次迭代
        mock_llm = MagicMock()
        thoughts = ["分析需求...", "规划步骤...", "准备执行..."]
        mock_llm.think = AsyncMock(side_effect=thoughts)
        mock_llm.decide_action = AsyncMock(
            side_effect=[
                {"action_type": "continue"},
                {"action_type": "continue"},
                {"action_type": "respond", "response": "完成"},
            ]
        )
        mock_llm.should_continue = AsyncMock(side_effect=[True, True, False])

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            max_iterations=5,
        )

        await agent.run_async("复杂任务")

        # 收集步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 应有 3 个思考步骤
        thinking_steps = [s for s in steps if s.kind == StepKind.THINKING]
        assert len(thinking_steps) == 3
        assert thinking_steps[0].content == "分析需求..."
        assert thinking_steps[1].content == "规划步骤..."
        assert thinking_steps[2].content == "准备执行..."

    @pytest.mark.asyncio
    async def test_iteration_limit_emits_proper_sequence(self, session_context, emitter):
        """测试：达到迭代限制时应正确发送序列"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="思考中...")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        mock_llm.should_continue = AsyncMock(return_value=True)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            max_iterations=3,
        )

        result = await agent.run_async("无限任务")

        # 应因达到限制而终止
        assert result.terminated_by_limit is True

        # 收集步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 应有 3 个思考步骤
        thinking_steps = [s for s in steps if s.kind == StepKind.THINKING]
        assert len(thinking_steps) == 3

        # 序列号应递增
        for i, step in enumerate(steps[:-1]):  # 排除结束标记
            assert step.sequence == i + 1


# ==================== 工具调用测试 ====================


class TestToolCallEmission:
    """测试工具调用的 emitter 行为"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def emitter(self):
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        return ConversationFlowEmitter(session_id="session_1")

    @pytest.mark.asyncio
    async def test_tool_call_decision_emits_tool_call(self, session_context, emitter):
        """测试：tool_call 必须触发真实执行并产生 TOOL_RESULT（严格 ReAct）"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="需要搜索信息...")
        mock_llm.decide_action = AsyncMock(
            side_effect=[
                {
                    "action_type": "tool_call",
                    "tool_name": "search",
                    "tool_id": "tc_001",
                    "arguments": {"query": "Python"},
                },
                {"action_type": "respond", "response": "搜索完成"},
            ]
        )
        mock_llm.should_continue = AsyncMock(side_effect=[True, False])

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            max_iterations=3,
        )

        await agent.run_async("搜索 Python")

        # 收集步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 应有工具调用步骤
        tool_steps = [s for s in steps if s.kind == StepKind.TOOL_CALL]
        assert len(tool_steps) == 1
        assert tool_steps[0].metadata["tool_name"] == "search"

        # 应有工具结果步骤（search 在默认内置工具里不存在 -> 失败 observation 也要落盘）
        result_steps = [s for s in steps if s.kind == StepKind.TOOL_RESULT]
        assert len(result_steps) == 1
        assert result_steps[0].metadata["tool_id"] == "tc_001"
        assert result_steps[0].metadata["success"] is False
        assert "unknown tool" in (result_steps[0].metadata.get("error") or "")

    @pytest.mark.asyncio
    async def test_tool_call_rejected_by_coordinator_emits_error_and_raises(
        self, session_context, emitter
    ):
        from src.application.services.coordinator_policy_chain import CoordinatorRejectedError
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind
        from src.domain.services.decision_events import DecisionRejectedEvent
        from src.domain.services.event_bus import EventBus

        class _FakeValidationResult:
            is_valid = False
            errors = ["blocked by coordinator"]

        class _FakeCoordinator:
            def validate_decision(self, _decision):
                return _FakeValidationResult()

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="Need to call tool...")
        mock_llm.decide_action = AsyncMock(
            side_effect=[
                {
                    "action_type": "tool_call",
                    "tool_name": "search",
                    "tool_id": "tc_rejected",
                    "arguments": {"query": "Python"},
                }
            ]
        )
        mock_llm.should_continue = AsyncMock(return_value=False)

        event_bus = EventBus()
        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            event_bus=event_bus,
            coordinator=_FakeCoordinator(),
            max_iterations=3,
        )

        with pytest.raises(CoordinatorRejectedError):
            await agent.run_async("Search Python")

        steps = []
        while not emitter._queue.empty():
            steps.append(await emitter._queue.get())

        assert any(
            s.kind == StepKind.ERROR and s.metadata.get("error_code") == "COORDINATOR_REJECTED"
            for s in steps
        )
        assert not any(s.kind == StepKind.TOOL_CALL for s in steps)
        assert any(isinstance(e, DecisionRejectedEvent) for e in event_bus.event_log)


# ==================== 错误处理测试 ====================


class TestErrorEmission:
    """测试错误情况下的 emitter 行为"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def emitter(self):
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        return ConversationFlowEmitter(session_id="session_1")

    @pytest.mark.asyncio
    async def test_llm_error_emits_error_step(self, session_context, emitter):
        """测试：LLM 错误应发送 ERROR 步骤"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(side_effect=Exception("LLM 调用失败"))
        mock_llm.decide_action = AsyncMock()
        mock_llm.should_continue = AsyncMock()

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
        )

        # 应该捕获错误并发送错误步骤
        try:
            await agent.run_async("触发错误")
        except Exception:
            pass

        # 收集步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 应有错误步骤
        error_steps = [s for s in steps if s.kind == StepKind.ERROR]
        assert len(error_steps) >= 1


# ==================== 意图分类流程测试 ====================


class TestIntentClassificationWithEmitter:
    """测试意图分类流程中的 emitter 行为"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def emitter(self):
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        return ConversationFlowEmitter(session_id="session_1")

    @pytest.mark.asyncio
    async def test_conversation_intent_emits_directly(self, session_context, emitter):
        """测试：普通对话意图应直接发送响应（不经过 ReAct）"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        mock_llm = MagicMock()
        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "conversation", "confidence": 0.95}
        )
        mock_llm.generate_response = AsyncMock(return_value="你好！我是 AI 助手。")
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            enable_intent_classification=True,
        )

        await agent.process_with_intent("你好")

        # 收集步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 普通对话不应有思考步骤（跳过 ReAct）
        # thinking_steps = [s for s in steps if s.kind == StepKind.THINKING]
        # 应直接有最终响应
        final_steps = [s for s in steps if s.kind == StepKind.FINAL]
        assert len(final_steps) == 1
        assert final_steps[0].content == "你好！我是 AI 助手。"

    @pytest.mark.asyncio
    async def test_workflow_modification_uses_react_with_emitter(self, session_context, emitter):
        """测试：工作流修改意图应使用 ReAct 循环"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        mock_llm = MagicMock()
        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "workflow_modification", "confidence": 0.9}
        )
        mock_llm.think = AsyncMock(return_value="分析工作流需求...")
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "工作流已创建"}
        )
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            enable_intent_classification=True,
        )

        await agent.process_with_intent("创建一个数据处理工作流")

        # 收集步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 工作流修改应有思考步骤（使用 ReAct）
        thinking_steps = [s for s in steps if s.kind == StepKind.THINKING]
        assert len(thinking_steps) >= 1


# ==================== 真实场景测试 ====================


class TestRealWorldScenarios:
    """真实场景测试"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def emitter(self):
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        return ConversationFlowEmitter(session_id="session_1")

    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, session_context, emitter):
        """场景：完整对话流程"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import StepKind

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(
            side_effect=["理解用户需求...", "规划工作流结构...", "生成节点..."]
        )
        mock_llm.decide_action = AsyncMock(
            side_effect=[
                {"action_type": "create_node", "node_type": "llm"},
                {"action_type": "create_node", "node_type": "http"},
                {"action_type": "respond", "response": "工作流已创建，包含 2 个节点"},
            ]
        )
        mock_llm.should_continue = AsyncMock(side_effect=[True, True, False])

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
            max_iterations=5,
        )

        result = await agent.run_async("创建一个包含 LLM 和 HTTP 节点的工作流")

        assert result.completed is True
        assert result.final_response == "工作流已创建，包含 2 个节点"

        # 收集步骤
        steps = []
        while not emitter._queue.empty():
            step = await emitter._queue.get()
            steps.append(step)

        # 验证步骤顺序
        kinds = [s.kind for s in steps]
        assert StepKind.THINKING in kinds
        assert StepKind.FINAL in kinds
        assert StepKind.END in kinds

        # 验证序列号递增
        sequences = [s.sequence for s in steps]
        assert sequences == sorted(sequences)

    @pytest.mark.asyncio
    async def test_emitter_statistics_after_conversation(self, session_context, emitter):
        """场景：对话后检查 emitter 统计"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="思考...")
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "完成"}
        )
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
        )

        await agent.run_async("测试")

        stats = emitter.get_statistics()
        assert stats["total_steps"] >= 2  # 至少有 thinking 和 final
        assert "thinking" in stats["by_kind"]

    @pytest.mark.asyncio
    async def test_async_iteration_during_conversation(self, session_context):
        """场景：在对话过程中异步迭代 emitter"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="思考...")
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "完成"}
        )
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            emitter=emitter,
        )

        collected_steps = []

        async def collect_steps():
            async for step in emitter:
                collected_steps.append(step)
                if step.kind == StepKind.END:
                    break

        async def run_agent():
            await agent.run_async("测试异步迭代")

        # 并行运行
        await asyncio.gather(run_agent(), collect_steps())

        # 验证收集到步骤
        assert len(collected_steps) >= 2
        kinds = [s.kind for s in collected_steps]
        assert StepKind.END in kinds

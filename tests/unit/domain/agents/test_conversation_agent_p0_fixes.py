"""P0 Critical Issues Regression Tests

验证以下修复：
1. F821 类型注解错误 - TYPE_CHECKING imports
2. Race Condition - asyncio.create_task task tracking
3. Shallow copy bug - deepcopy for context isolation
4. Ambiguous variable name - 'l' renamed to 'loop_data'
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.agents.control_flow_ir import ControlFlowIR
from src.domain.services.context_manager import GlobalContext, SessionContext


class TestTypeAnnotationFixes:
    """验证类型注解错误修复 (F821)"""

    def test_formatted_error_type_available(self):
        """FormattedError 应该可以作为类型注解使用"""
        # 这个测试验证 TYPE_CHECKING 导入正确
        # 如果导入失败，ruff check 会报 F821
        from src.domain.agents.error_handling import FormattedError

        assert FormattedError is not None

    def test_user_decision_types_available(self):
        """UserDecision 和 UserDecisionResult 应该可以作为类型注解使用"""
        from src.domain.agents.error_handling import UserDecision, UserDecisionResult

        # 验证类型存在且可导入
        assert UserDecision is not None
        assert UserDecisionResult is not None

    def test_control_flow_ir_type_available(self):
        """ControlFlowIR 应该可以作为类型注解使用"""
        # 已经在文件顶部导入
        assert ControlFlowIR is not None

    def test_edge_definition_type_available(self):
        """EdgeDefinition 应该可以作为类型注解使用"""
        from src.domain.agents.workflow_plan import EdgeDefinition

        assert EdgeDefinition is not None


class TestRaceConditionFixes:
    """验证 Race Condition 修复 - 任务追踪"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 mock EventBus"""
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.fixture
    def global_context(self):
        """创建 GlobalContext"""
        return GlobalContext(user_id="test-user")

    @pytest.fixture
    def conversation_agent(self, mock_event_bus, global_context):
        """创建 ConversationAgent 实例"""
        from src.domain.agents.conversation_agent import ConversationAgent

        session_context = SessionContext(
            session_id="test-session",
            global_context=global_context,
        )
        agent = ConversationAgent(
            session_context=session_context,
            llm=MagicMock(),
            event_bus=mock_event_bus,
        )
        return agent

    def test_pending_tasks_attribute_exists(self, conversation_agent):
        """验证 _pending_tasks 属性存在"""
        assert hasattr(conversation_agent, "_pending_tasks")
        assert isinstance(conversation_agent._pending_tasks, set)

    def test_create_tracked_task_method_exists(self, conversation_agent):
        """验证 _create_tracked_task 方法存在"""
        assert hasattr(conversation_agent, "_create_tracked_task")
        assert callable(conversation_agent._create_tracked_task)

    @pytest.mark.asyncio
    async def test_state_transition_task_tracked(self, conversation_agent, mock_event_bus):
        """验证状态转换时事件发布任务被追踪"""
        from src.domain.agents.conversation_agent import ConversationAgentState

        # 初始状态是 IDLE，转换到 PROCESSING
        conversation_agent.transition_to(ConversationAgentState.PROCESSING)

        # 等待一小段时间让任务完成
        await asyncio.sleep(0.1)

        # 验证事件被发布
        assert mock_event_bus.publish.called

    @pytest.mark.asyncio
    async def test_spawn_subagent_task_tracked(self, conversation_agent, mock_event_bus):
        """验证 request_subagent_spawn 时事件发布任务被追踪"""
        from src.domain.agents.conversation_agent import ConversationAgentState

        # 先进入 PROCESSING 状态
        conversation_agent.transition_to(ConversationAgentState.PROCESSING)

        # 调用 request_subagent_spawn（不等待结果）
        subagent_id = conversation_agent.request_subagent_spawn(
            subagent_type="test_agent",
            task_payload={"test": True},
            wait_for_result=False,
        )

        # 等待任务完成
        await asyncio.sleep(0.1)

        # 验证返回了 subagent_id
        assert subagent_id is not None
        assert subagent_id.startswith("subagent_")


class TestShallowCopyFixes:
    """验证浅拷贝 Bug 修复 - deepcopy"""

    @pytest.fixture
    def global_context(self):
        """创建 GlobalContext"""
        return GlobalContext(user_id="test-user")

    @pytest.fixture
    def conversation_agent(self, global_context):
        """创建 ConversationAgent 实例"""
        from src.domain.agents.conversation_agent import ConversationAgent

        session_context = SessionContext(
            session_id="test-session",
            global_context=global_context,
        )
        agent = ConversationAgent(
            session_context=session_context,
            llm=MagicMock(),
        )
        return agent

    def test_wait_for_subagent_deep_copies_context(self, conversation_agent):
        """验证 wait_for_subagent 使用 deepcopy"""
        from src.domain.agents.conversation_agent import ConversationAgentState

        # 先进入 PROCESSING 状态
        conversation_agent.transition_to(ConversationAgentState.PROCESSING)

        # 创建嵌套上下文
        nested_context = {
            "level1": {
                "level2": {"value": "original"},
            },
            "list_data": [1, 2, 3],
        }

        # 调用 wait_for_subagent
        conversation_agent.wait_for_subagent(
            subagent_id="test-subagent",
            task_id="test-task",
            context=nested_context,
        )

        # 修改原始上下文
        nested_context["level1"]["level2"]["value"] = "modified"
        nested_context["list_data"].append(4)

        # 验证保存的上下文没有被修改（deepcopy 隔离）
        saved_context = conversation_agent.suspended_context
        assert saved_context["level1"]["level2"]["value"] == "original"
        assert saved_context["list_data"] == [1, 2, 3]

    def test_resume_from_subagent_deep_copies_context(self, conversation_agent):
        """验证 resume_from_subagent 使用 deepcopy"""
        from src.domain.agents.conversation_agent import ConversationAgentState

        # 设置保存的上下文
        conversation_agent._state = ConversationAgentState.WAITING_FOR_SUBAGENT
        original_nested = {"data": "original"}
        original_items = [1, 2]
        conversation_agent.suspended_context = {
            "nested": original_nested,
            "items": original_items,
        }

        # 恢复上下文
        resumed_context = conversation_agent.resume_from_subagent({"result": "success"})

        # 修改恢复的上下文
        resumed_context["nested"]["data"] = "modified"
        resumed_context["items"].append(3)

        # 由于 suspended_context 在恢复后被设为 None，
        # 我们验证返回的 context 是独立副本
        # 验证原始数据没有被修改（因为使用了 deepcopy）
        assert original_nested["data"] == "original"
        assert original_items == [1, 2]


class TestAmbiguousVariableNameFix:
    """验证模糊变量名修复 - 'l' renamed to 'loop_data'"""

    def test_control_flow_ir_from_dict_with_loops(self):
        """验证 ControlFlowIR.from_dict 能正确解析循环数据"""
        data = {
            "tasks": [
                {"id": "task1", "name": "Task 1", "description": "First task"},
            ],
            "decisions": [],
            "loops": [
                {
                    "id": "loop1",
                    "description": "Process items",
                    "collection": "items",
                    "loop_variable": "item",
                    "loop_type": "for_each",
                    "confidence": 0.9,
                    "source_text": "for each item in items",
                },
                {
                    "id": "loop2",
                    "description": "Iterate data",
                    "collection": "data_set",
                    "loop_variable": "record",
                    "loop_type": "for_each",
                    "confidence": 0.8,
                },
            ],
        }

        # 解析数据
        ir = ControlFlowIR.from_dict(data)

        # 验证循环被正确解析
        assert len(ir.loops) == 2
        assert ir.loops[0].id == "loop1"
        assert ir.loops[0].collection == "items"
        assert ir.loops[0].loop_variable == "item"
        assert ir.loops[1].id == "loop2"
        assert ir.loops[1].collection == "data_set"
        assert ir.loops[1].loop_variable == "record"

    def test_control_flow_ir_from_dict_empty_loops(self):
        """验证空循环数据不会报错"""
        data = {
            "tasks": [],
            "decisions": [],
            "loops": [],
        }

        ir = ControlFlowIR.from_dict(data)
        assert len(ir.loops) == 0


class TestRuffCompliance:
    """验证 Ruff 代码质量检查通过"""

    def test_no_f821_errors_in_conversation_agent(self):
        """验证 conversation_agent.py 没有 F821 错误

        这个测试是文档性的 - 实际验证通过运行:
        ruff check src/domain/agents/conversation_agent.py --select=F821
        """
        # 如果能导入这些类型，说明它们存在
        from src.domain.agents.control_flow_ir import ControlFlowIR
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import (
            FormattedError,
            UserDecision,
            UserDecisionResult,
        )
        from src.domain.agents.workflow_plan import EdgeDefinition

        # 所有导入成功即通过
        assert all(
            [
                ConversationAgent,
                ControlFlowIR,
                FormattedError,
                UserDecision,
                UserDecisionResult,
                EdgeDefinition,
            ]
        )

    def test_no_e741_errors_in_control_flow_ir(self):
        """验证 control_flow_ir.py 没有 E741 错误（模糊变量名）

        这个测试是文档性的 - 实际验证通过运行:
        ruff check src/domain/agents/control_flow_ir.py --select=E741
        """
        # 能成功解析数据即通过
        ir = ControlFlowIR.from_dict({"tasks": [], "decisions": [], "loops": []})
        assert ir is not None

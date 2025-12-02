"""ConversationAgent 规划能力测试 - Phase 8.3

TDD RED阶段：测试 ConversationAgent 的工作流规划能力
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestConversationAgentPlanning:
    """ConversationAgent 规划能力测试"""

    def test_conversation_agent_creates_workflow_plan(self):
        """ConversationAgent 应能创建完整工作流规划"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_plan import WorkflowPlan
        from src.domain.services.context_manager import GlobalContext, SessionContext

        # 设置
        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        # Mock LLM
        llm = MagicMock()
        llm.plan_workflow = AsyncMock(
            return_value={
                "name": "数据分析流程",
                "nodes": [
                    {"name": "读取数据", "type": "python", "code": "data = read()"},
                    {"name": "处理数据", "type": "python", "code": "result = process(data)"},
                ],
                "edges": [
                    {"source": "读取数据", "target": "处理数据"},
                ],
            }
        )

        agent = ConversationAgent(session_context=session_ctx, llm=llm)

        # 执行
        import asyncio

        plan = asyncio.run(agent.create_workflow_plan("分析这份数据"))

        # 验证
        assert isinstance(plan, WorkflowPlan)
        assert len(plan.nodes) >= 2
        assert len(plan.edges) >= 1

    def test_conversation_agent_decomposes_goal_to_nodes(self):
        """应将目标分解为具体节点定义"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.node_definition import NodeDefinition
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        llm = MagicMock()
        llm.decompose_to_nodes = AsyncMock(
            return_value=[
                {"name": "步骤1", "type": "python", "code": "step1()"},
                {"name": "步骤2", "type": "python", "code": "step2()"},
                {"name": "步骤3", "type": "llm", "prompt": "总结结果"},
            ]
        )

        agent = ConversationAgent(session_context=session_ctx, llm=llm)

        import asyncio

        nodes = asyncio.run(agent.decompose_to_nodes("生成报表"))

        assert len(nodes) == 3
        assert all(isinstance(n, NodeDefinition) for n in nodes)
        assert nodes[0].name == "步骤1"
        assert nodes[2].prompt == "总结结果"

    def test_conversation_agent_publishes_workflow_plan_decision(self):
        """应发布 WorkflowPlanDecision 事件"""
        from src.domain.agents.conversation_agent import ConversationAgent, DecisionType
        from src.domain.services.context_manager import GlobalContext, SessionContext
        from src.domain.services.event_bus import EventBus

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        event_bus = EventBus()

        received_events = []

        async def handler(event):
            received_events.append(event)

        # 订阅决策事件
        from src.domain.agents.conversation_agent import DecisionMadeEvent

        event_bus.subscribe(DecisionMadeEvent, handler)

        llm = MagicMock()
        llm.plan_workflow = AsyncMock(
            return_value={
                "name": "测试流程",
                "nodes": [{"name": "N1", "type": "python", "code": "pass"}],
                "edges": [],
            }
        )

        agent = ConversationAgent(session_context=session_ctx, llm=llm, event_bus=event_bus)

        import asyncio

        asyncio.run(agent.create_workflow_plan_and_publish("测试目标"))

        # 应该发布了事件
        assert len(received_events) >= 1
        event = received_events[0]
        assert event.decision_type == DecisionType.CREATE_WORKFLOW_PLAN.value

    def test_conversation_agent_handles_complex_goal(self):
        """应处理复杂目标（如：分析数据并生成报表）"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        llm = MagicMock()
        # 模拟复杂目标的分解
        llm.plan_workflow = AsyncMock(
            return_value={
                "name": "销售数据分析",
                "nodes": [
                    {
                        "name": "读取Excel",
                        "type": "python",
                        "code": "df = pd.read_excel(file)",
                    },
                    {
                        "name": "数据清洗",
                        "type": "python",
                        "code": "df = clean(df)",
                    },
                    {
                        "name": "计算统计",
                        "type": "python",
                        "code": "stats = calc_stats(df)",
                    },
                    {
                        "name": "生成图表",
                        "type": "python",
                        "code": "chart = plot(stats)",
                    },
                    {
                        "name": "生成报告",
                        "type": "llm",
                        "prompt": "根据统计数据生成分析报告：{stats}",
                    },
                ],
                "edges": [
                    {"source": "读取Excel", "target": "数据清洗"},
                    {"source": "数据清洗", "target": "计算统计"},
                    {"source": "计算统计", "target": "生成图表"},
                    {"source": "计算统计", "target": "生成报告"},
                ],
            }
        )

        agent = ConversationAgent(session_context=session_ctx, llm=llm)

        import asyncio

        plan = asyncio.run(
            agent.create_workflow_plan("分析销售数据Excel，计算统计指标，生成图表和报告")
        )

        # 验证复杂流程
        assert len(plan.nodes) >= 4
        assert len(plan.edges) >= 3
        # 应该有并行分支（图表和报告都依赖统计）
        targets_from_stats = [e.target_node for e in plan.edges if e.source_node == "计算统计"]
        assert len(targets_from_stats) >= 2


class TestConversationAgentDecisionTypes:
    """ConversationAgent 决策类型测试"""

    def test_decision_type_includes_create_workflow_plan(self):
        """DecisionType 应包含 CREATE_WORKFLOW_PLAN"""
        from src.domain.agents.conversation_agent import DecisionType

        assert hasattr(DecisionType, "CREATE_WORKFLOW_PLAN")
        assert DecisionType.CREATE_WORKFLOW_PLAN.value == "create_workflow_plan"

    def test_make_workflow_plan_decision(self):
        """make_decision 应支持创建工作流规划决策"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            Decision,
            DecisionType,
        )
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        llm = MagicMock()
        # 使用 AsyncMock 并设置 return_value 属性以便同步方式访问
        llm.decide_action = AsyncMock(
            return_value={
                "action_type": "create_workflow_plan",
                "plan": {
                    "name": "Test Plan",
                    "nodes": [{"name": "N1", "type": "python", "code": "pass"}],
                    "edges": [],
                },
            }
        )
        # 设置 return_value 属性以便 _run_sync 方式也能访问
        llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "plan": {
                "name": "Test Plan",
                "nodes": [{"name": "N1", "type": "python", "code": "pass"}],
                "edges": [],
            },
        }

        agent = ConversationAgent(session_context=session_ctx, llm=llm)
        decision = agent.make_decision("创建一个数据处理流程")

        assert isinstance(decision, Decision)
        assert decision.type == DecisionType.CREATE_WORKFLOW_PLAN


class TestConversationAgentLLMInterface:
    """ConversationAgent LLM 接口扩展测试"""

    def test_llm_interface_has_plan_workflow_method(self):
        """LLM 接口应有 plan_workflow 方法"""
        from src.domain.agents.conversation_agent import ConversationAgentLLM

        # 检查协议定义
        assert hasattr(ConversationAgentLLM, "plan_workflow")

    def test_llm_interface_has_decompose_to_nodes_method(self):
        """LLM 接口应有 decompose_to_nodes 方法"""
        from src.domain.agents.conversation_agent import ConversationAgentLLM

        assert hasattr(ConversationAgentLLM, "decompose_to_nodes")


class TestConversationAgentPlanValidation:
    """ConversationAgent 规划验证测试"""

    def test_create_workflow_plan_validates_result(self):
        """create_workflow_plan 应验证 LLM 返回的规划"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        llm = MagicMock()
        # 返回一个有无效节点的规划（Python 节点缺少 code）
        llm.plan_workflow = AsyncMock(
            return_value={
                "name": "无效规划",
                "nodes": [
                    {"name": "无效Python节点", "type": "python"},  # 缺少 code
                ],
                "edges": [],
            }
        )

        agent = ConversationAgent(session_context=session_ctx, llm=llm)

        import asyncio

        # 应该抛出验证错误或返回带错误的结果
        with pytest.raises(ValueError, match="[Vv]alidat|验证|code"):
            asyncio.run(agent.create_workflow_plan("测试"))

    def test_create_workflow_plan_validates_circular_dependency(self):
        """create_workflow_plan 应检测循环依赖"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        llm = MagicMock()
        # 返回有循环依赖的规划
        llm.plan_workflow = AsyncMock(
            return_value={
                "name": "循环规划",
                "nodes": [
                    {"name": "A", "type": "python", "code": "pass"},
                    {"name": "B", "type": "python", "code": "pass"},
                ],
                "edges": [
                    {"source": "A", "target": "B"},
                    {"source": "B", "target": "A"},  # 循环
                ],
            }
        )

        agent = ConversationAgent(session_context=session_ctx, llm=llm)

        import asyncio

        with pytest.raises(ValueError, match="[Cc]ircular|[Cc]ycle|循环"):
            asyncio.run(agent.create_workflow_plan("测试"))

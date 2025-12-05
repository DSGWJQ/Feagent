"""测试：对话Agent (ConversationAgent)

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 对话Agent是多Agent协作系统的"大脑"
- 基于ReAct循环进行推理和决策
- 负责理解用户意图、分解目标、生成工作流

真实场景：
1. 用户输入需求 → 对话Agent理解意图
2. 对话Agent分解目标 → 推入目标栈
3. 对话Agent决策创建节点 → 发布决策事件
4. 协调者验证 → 工作流Agent执行
5. 结果反馈 → 对话Agent继续推理

核心能力：
- ReAct循环：Thought → Action → Observation → Thought...
- 目标分解：将复杂目标分解为子目标
- 决策生成：决定创建什么节点、执行什么工作流
- 上下文感知：利用会话上下文进行推理
"""

from unittest.mock import AsyncMock

import pytest


class TestConversationAgentReActLoop:
    """测试对话Agent的ReAct循环

    业务背景：
    - ReAct = Reasoning + Acting
    - 每次循环：思考(Thought) → 行动(Action) → 观察(Observation)
    - 循环直到任务完成或达到最大轮次
    """

    def test_react_loop_produces_thought_action_observation(self):
        """测试：ReAct循环产生思考、行动、观察

        业务场景：
        - 用户说"帮我创建一个数据分析工作流"
        - 对话Agent应该先思考，再决定行动，最后观察结果

        验收标准：
        - 循环产生Thought
        - 循环产生Action
        - 循环产生Observation
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent, StepType
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # Mock LLM
        mock_llm = AsyncMock()
        mock_llm.think.return_value = "我需要创建一个数据分析工作流，首先需要获取数据"
        mock_llm.decide_action.return_value = {
            "action_type": "create_node",
            "node_type": "API",
            "config": {"url": "https://api.example.com/data"},
        }

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        step = agent.execute_step("帮我创建一个数据分析工作流")

        # Assert
        assert step.thought is not None
        assert step.action is not None
        assert step.step_type == StepType.REASONING

    def test_react_loop_max_iterations_limit(self):
        """测试：ReAct循环有最大迭代限制

        业务场景：
        - 防止无限循环消耗资源
        - 达到最大轮次后强制终止

        验收标准：
        - 循环不超过max_iterations
        - 超过后返回终止状态
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        mock_llm = AsyncMock()
        # 模拟LLM总是返回需要继续的动作
        mock_llm.think.return_value = "继续思考..."
        mock_llm.decide_action.return_value = {"action_type": "continue"}
        mock_llm.should_continue.return_value = True

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm, max_iterations=5)

        # Act
        result = agent.run("无限任务")

        # Assert
        assert result.iterations <= 5
        assert result.terminated_by_limit is True

    def test_react_loop_terminates_on_completion(self):
        """测试：任务完成时ReAct循环终止

        业务场景：
        - 对话Agent完成用户请求
        - 生成最终回复并终止循环

        验收标准：
        - 任务完成后循环终止
        - 返回最终结果
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        mock_llm = AsyncMock()
        mock_llm.think.return_value = "任务已完成"
        mock_llm.decide_action.return_value = {
            "action_type": "respond",
            "response": "工作流已创建完成",
        }
        mock_llm.should_continue.return_value = False

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        result = agent.run("简单任务")

        # Assert
        assert result.completed is True
        assert result.final_response is not None


class TestConversationAgentGoalDecomposition:
    """测试对话Agent的目标分解能力

    业务背景：
    - 复杂目标需要分解为可执行的子目标
    - 子目标形成栈结构（LIFO）
    - 完成子目标后继续处理下一个
    """

    def test_decompose_complex_goal_into_subgoals(self):
        """测试：将复杂目标分解为子目标

        业务场景：
        - 用户说"分析销售数据并生成报告"
        - 分解为：1. 获取数据 2. 分析数据 3. 生成报告

        验收标准：
        - 识别出需要分解的复杂目标
        - 生成多个子目标
        - 子目标推入目标栈
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        mock_llm = AsyncMock()
        mock_llm.decompose_goal.return_value = [
            {"description": "获取销售数据", "priority": 1},
            {"description": "分析数据趋势", "priority": 2},
            {"description": "生成可视化报告", "priority": 3},
        ]

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        subgoals = agent.decompose_goal("分析销售数据并生成报告")

        # Assert
        assert len(subgoals) == 3
        assert subgoals[0].description == "获取销售数据"

        # 子目标应该被推入目标栈
        assert len(session_ctx.goal_stack) >= 1

    def test_goal_completion_pops_from_stack(self):
        """测试：完成目标后从栈中弹出

        业务场景：
        - 子目标完成后自动弹出
        - 继续处理下一个子目标

        验收标准：
        - 完成的目标从栈中移除
        - 自动开始处理下一个目标
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, Goal, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 预先设置目标栈
        goal1 = Goal(id="goal_1", description="主目标")
        goal2 = Goal(id="goal_2", description="子目标", parent_id="goal_1")
        session_ctx.push_goal(goal1)
        session_ctx.push_goal(goal2)

        mock_llm = AsyncMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act - 完成子目标
        agent.complete_current_goal()

        # Assert
        assert len(session_ctx.goal_stack) == 1
        assert session_ctx.current_goal().id == "goal_1"


class TestConversationAgentDecisionMaking:
    """测试对话Agent的决策能力

    业务背景：
    - 对话Agent根据上下文做出决策
    - 决策类型：创建节点、执行工作流、请求信息等
    - 决策通过EventBus发布
    """

    def test_decision_to_create_node(self):
        """测试：决策创建节点

        业务场景：
        - 对话Agent决定需要一个LLM节点
        - 发布创建节点的决策事件

        验收标准：
        - 生成正确的决策
        - 决策包含节点类型和配置
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent, DecisionType
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        mock_llm = AsyncMock()
        mock_llm.decide_action.return_value = {
            "action_type": "create_node",
            "node_type": "LLM",
            "node_name": "数据分析节点",  # Added: required field
            "config": {"model": "gpt-4", "user_prompt": "分析数据"},
        }

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        decision = agent.make_decision("需要分析这些数据")

        # Assert
        assert decision.type == DecisionType.CREATE_NODE
        assert decision.payload["node_type"] == "LLM"
        assert decision.payload["node_name"] == "数据分析节点"  # Added: verify node_name
        assert decision.payload["config"]["model"] == "gpt-4"

    def test_decision_to_execute_workflow(self):
        """测试：决策执行工作流

        业务场景：
        - 节点创建完成后
        - 对话Agent决定执行工作流

        验收标准：
        - 生成执行工作流的决策
        - 决策包含工作流ID
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent, DecisionType
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        mock_llm = AsyncMock()
        mock_llm.decide_action.return_value = {
            "action_type": "execute_workflow",
            "workflow_id": "workflow_123",
        }

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        decision = agent.make_decision("开始执行工作流")

        # Assert
        assert decision.type == DecisionType.EXECUTE_WORKFLOW
        assert decision.payload["workflow_id"] == "workflow_123"

    def test_decision_recorded_in_history(self):
        """测试：决策被记录到历史

        业务场景：
        - 所有决策需要记录用于审计
        - 便于回溯和分析

        验收标准：
        - 决策被添加到session的决策历史
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        mock_llm = AsyncMock()
        mock_llm.decide_action.return_value = {
            "action_type": "create_node",
            "node_type": "HTTP",  # Fixed: API -> HTTP (valid enum value)
            "node_name": "API节点",  # Added: required field
            "config": {"url": "https://api.example.com", "method": "GET"},  # Added: required field
        }

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        agent.make_decision("测试决策")

        # Assert
        assert len(session_ctx.decision_history) >= 1


class TestConversationAgentEventPublishing:
    """测试对话Agent的事件发布

    业务背景：
    - 对话Agent通过EventBus与其他Agent通信
    - 决策事件被协调者Agent拦截验证
    """

    @pytest.mark.asyncio
    async def test_publish_decision_event(self):
        """测试：发布决策事件

        业务场景：
        - 对话Agent做出决策后
        - 发布DecisionMadeEvent到EventBus
        - 协调者Agent订阅并验证

        验收标准：
        - 事件被正确发布
        - 事件包含决策信息
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext
        from src.domain.services.event_bus import EventBus

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        event_bus = EventBus()

        received_events = []

        async def capture_event(event):
            received_events.append(event)

        # 订阅决策事件
        from src.domain.agents.conversation_agent import DecisionMadeEvent

        event_bus.subscribe(DecisionMadeEvent, capture_event)

        mock_llm = AsyncMock()
        mock_llm.decide_action.return_value = {"action_type": "create_node", "node_type": "LLM"}

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm, event_bus=event_bus)

        # Act
        await agent.publish_decision({"type": "create_node", "node_type": "LLM"})

        # Assert
        assert len(received_events) == 1
        assert received_events[0].decision_type == "create_node"


class TestConversationAgentContextAwareness:
    """测试对话Agent的上下文感知

    业务背景：
    - 对话Agent需要感知完整的上下文
    - 包括对话历史、当前目标、工作流状态等
    """

    def test_agent_aware_of_conversation_history(self):
        """测试：感知对话历史

        业务场景：
        - 用户多轮对话
        - Agent需要理解之前的上下文

        验收标准：
        - Agent可以访问对话历史
        - 历史影响推理结果
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 添加对话历史
        session_ctx.add_message({"role": "user", "content": "我想分析销售数据"})
        session_ctx.add_message({"role": "assistant", "content": "好的，请上传数据文件"})
        session_ctx.add_message({"role": "user", "content": "数据已上传"})

        mock_llm = AsyncMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        context = agent.get_context_for_reasoning()

        # Assert
        assert "conversation_history" in context
        assert len(context["conversation_history"]) == 3

    def test_agent_aware_of_current_goal(self):
        """测试：感知当前目标

        业务场景：
        - Agent需要知道当前正在处理的目标
        - 基于目标进行推理

        验收标准：
        - Agent可以获取当前目标
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, Goal, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        goal = Goal(id="goal_1", description="分析数据")
        session_ctx.push_goal(goal)

        mock_llm = AsyncMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        context = agent.get_context_for_reasoning()

        # Assert
        assert "current_goal" in context
        assert context["current_goal"].description == "分析数据"


class TestConversationAgentRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_complete_workflow_creation_scenario(self):
        """测试：完整的工作流创建场景

        业务场景：
        1. 用户说"帮我创建一个获取天气并发送通知的工作流"
        2. 对话Agent分解目标
        3. 决策创建API节点获取天气
        4. 决策创建通知节点
        5. 决策连接节点并执行

        这是对话Agent的核心使用场景！

        验收标准：
        - 完成目标分解
        - 生成正确的节点创建决策
        - 最终给出回复
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext
        from src.domain.services.event_bus import EventBus

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        event_bus = EventBus()

        # 模拟LLM的多轮响应
        mock_llm = AsyncMock()

        # 第一轮：分解目标
        mock_llm.decompose_goal.return_value = [
            {"description": "获取天气数据", "priority": 1},
            {"description": "发送通知", "priority": 2},
        ]

        # 决策序列
        decision_sequence = [
            {"action_type": "create_node", "node_type": "API", "config": {"url": "weather_api"}},
            {
                "action_type": "create_node",
                "node_type": "NOTIFICATION",
                "config": {"channel": "email"},
            },
            {"action_type": "respond", "response": "工作流创建完成"},
        ]
        mock_llm.decide_action.side_effect = decision_sequence
        mock_llm.think.return_value = "思考中..."
        mock_llm.should_continue.side_effect = [True, True, False]

        agent = ConversationAgent(
            session_context=session_ctx, llm=mock_llm, event_bus=event_bus, max_iterations=10
        )

        # Act
        result = await agent.run_async("帮我创建一个获取天气并发送通知的工作流")

        # Assert
        assert result.completed is True
        assert result.final_response is not None
        # 应该有决策历史
        assert len(session_ctx.decision_history) >= 2

    def test_handle_ambiguous_user_request(self):
        """测试：处理模糊的用户请求

        业务场景：
        - 用户说"帮我做点什么"
        - Agent需要请求更多信息

        验收标准：
        - 识别请求模糊
        - 生成澄清问题
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent, DecisionType
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        mock_llm = AsyncMock()
        mock_llm.decide_action.return_value = {
            "action_type": "request_clarification",
            "question": "请问您想完成什么具体任务？",
        }

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        # Act
        decision = agent.make_decision("帮我做点什么")

        # Assert
        assert decision.type == DecisionType.REQUEST_CLARIFICATION
        assert "question" in decision.payload

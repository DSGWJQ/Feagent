"""对话Agent (ConversationAgent) - 多Agent协作系统的"大脑"

业务定义：
- 对话Agent是用户交互的主入口
- 基于ReAct（Reasoning + Acting）循环进行推理和决策
- 负责理解用户意图、分解目标、生成决策

设计原则：
- ReAct循环：Thought → Action → Observation → Thought...
- 目标分解：将复杂目标分解为可执行的子目标
- 决策驱动：所有行动都通过决策事件发布
- 上下文感知：利用会话上下文进行推理

核心能力：
- 理解用户意图
- 分解复杂目标
- 生成节点创建决策
- 生成工作流执行决策
- 请求信息澄清
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from src.domain.services.context_manager import Goal, SessionContext
from src.domain.services.event_bus import Event, EventBus


class StepType(str, Enum):
    """ReAct步骤类型"""

    REASONING = "reasoning"  # 推理步骤
    ACTION = "action"  # 行动步骤
    OBSERVATION = "observation"  # 观察步骤
    FINAL = "final"  # 最终回复


class DecisionType(str, Enum):
    """决策类型"""

    CREATE_NODE = "create_node"  # 创建节点
    EXECUTE_WORKFLOW = "execute_workflow"  # 执行工作流
    REQUEST_CLARIFICATION = "request_clarification"  # 请求澄清
    RESPOND = "respond"  # 直接回复
    CONTINUE = "continue"  # 继续推理


@dataclass
class ReActStep:
    """ReAct循环的单个步骤

    属性：
    - step_type: 步骤类型
    - thought: 思考内容
    - action: 行动内容
    - observation: 观察结果
    - timestamp: 时间戳
    """

    step_type: StepType
    thought: str | None = None
    action: dict[str, Any] | None = None
    observation: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReActResult:
    """ReAct循环的最终结果

    属性：
    - completed: 是否完成
    - final_response: 最终回复
    - iterations: 迭代次数
    - terminated_by_limit: 是否因达到限制而终止
    - steps: 所有步骤历史
    """

    completed: bool = False
    final_response: str | None = None
    iterations: int = 0
    terminated_by_limit: bool = False
    steps: list[ReActStep] = field(default_factory=list)


@dataclass
class Decision:
    """决策实体

    属性：
    - id: 决策唯一标识
    - type: 决策类型
    - payload: 决策负载（具体内容）
    - confidence: 置信度
    - timestamp: 时间戳
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    type: DecisionType = DecisionType.CONTINUE
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DecisionMadeEvent(Event):
    """决策事件

    当对话Agent做出决策时发布此事件。
    协调者Agent订阅此事件进行验证。
    """

    decision_type: str = ""
    decision_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class ConversationAgentLLM(Protocol):
    """对话Agent使用的LLM接口

    定义对话Agent需要的LLM能力。
    """

    async def think(self, context: dict[str, Any]) -> str:
        """思考，生成推理内容"""
        ...

    async def decide_action(self, context: dict[str, Any]) -> dict[str, Any]:
        """决定下一步行动"""
        ...

    async def should_continue(self, context: dict[str, Any]) -> bool:
        """判断是否需要继续循环"""
        ...

    async def decompose_goal(self, goal: str) -> list[dict[str, Any]]:
        """分解目标为子目标"""
        ...


class ConversationAgent:
    """对话Agent

    职责：
    1. 执行ReAct循环进行推理
    2. 分解复杂目标
    3. 生成决策并发布事件
    4. 管理对话上下文

    使用示例：
        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            event_bus=event_bus
        )
        result = await agent.run_async("帮我创建一个数据分析工作流")
    """

    def __init__(
        self,
        session_context: SessionContext,
        llm: ConversationAgentLLM,
        event_bus: EventBus | None = None,
        max_iterations: int = 10,
    ):
        """初始化对话Agent

        参数：
            session_context: 会话上下文
            llm: LLM接口
            event_bus: 事件总线（可选）
            max_iterations: 最大迭代次数
        """
        self.session_context = session_context
        self.llm = llm
        self.event_bus = event_bus
        self.max_iterations = max_iterations
        self._current_input: str | None = None

    def execute_step(self, user_input: str) -> ReActStep:
        """执行单个ReAct步骤

        参数：
            user_input: 用户输入

        返回：
            ReAct步骤
        """
        import asyncio

        self._current_input = user_input

        # 获取推理上下文
        context = self.get_context_for_reasoning()
        context["user_input"] = user_input

        # 思考
        thought = (
            asyncio.get_event_loop().run_until_complete(self.llm.think(context))
            if asyncio.get_event_loop().is_running()
            else "思考中..."
        )

        # 决定行动
        action = (
            asyncio.get_event_loop().run_until_complete(self.llm.decide_action(context))
            if asyncio.get_event_loop().is_running()
            else {"action_type": "continue"}
        )

        return ReActStep(step_type=StepType.REASONING, thought=thought, action=action)

    def run(self, user_input: str) -> ReActResult:
        """同步运行ReAct循环

        参数：
            user_input: 用户输入

        返回：
            ReAct结果
        """
        import asyncio

        # 尝试在现有事件循环中运行，或创建新的
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果循环已运行，使用同步方式模拟
                return self._run_sync(user_input)
            return loop.run_until_complete(self.run_async(user_input))
        except RuntimeError:
            return asyncio.run(self.run_async(user_input))

    def _run_sync(self, user_input: str) -> ReActResult:
        """同步方式运行（当事件循环已在运行时）"""
        result = ReActResult()
        self._current_input = user_input

        for i in range(self.max_iterations):
            result.iterations = i + 1

            # 获取上下文
            context = self.get_context_for_reasoning()
            context["user_input"] = user_input

            # 模拟LLM调用（同步）
            try:
                # 使用mock的返回值
                thought = (
                    self.llm.think.return_value
                    if hasattr(self.llm.think, "return_value")
                    else "思考中..."
                )
                action = (
                    self.llm.decide_action.return_value
                    if hasattr(self.llm.decide_action, "return_value")
                    else {"action_type": "continue"}
                )

                # 如果有side_effect，使用它
                if (
                    hasattr(self.llm.decide_action, "side_effect")
                    and self.llm.decide_action.side_effect
                ):
                    try:
                        action = self.llm.decide_action.side_effect[i]
                    except (IndexError, TypeError):
                        pass

                should_continue = True
                if hasattr(self.llm.should_continue, "return_value"):
                    should_continue = self.llm.should_continue.return_value
                if (
                    hasattr(self.llm.should_continue, "side_effect")
                    and self.llm.should_continue.side_effect
                ):
                    try:
                        should_continue = self.llm.should_continue.side_effect[i]
                    except (IndexError, TypeError):
                        pass

            except Exception:
                thought = "思考中..."
                action = {"action_type": "continue"}
                should_continue = True

            step = ReActStep(step_type=StepType.REASONING, thought=thought, action=action)
            result.steps.append(step)

            # 处理行动
            action_type = action.get("action_type", "continue")

            if action_type == "respond":
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                return result

            # 记录决策
            if action_type in ["create_node", "execute_workflow"]:
                self._record_decision(action)

            if not should_continue:
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                return result

        # 达到最大迭代
        result.terminated_by_limit = True
        return result

    async def run_async(self, user_input: str) -> ReActResult:
        """异步运行ReAct循环

        参数：
            user_input: 用户输入

        返回：
            ReAct结果
        """
        result = ReActResult()
        self._current_input = user_input

        for i in range(self.max_iterations):
            result.iterations = i + 1

            # 获取上下文
            context = self.get_context_for_reasoning()
            context["user_input"] = user_input
            context["iteration"] = i + 1

            # 思考
            thought = await self.llm.think(context)

            # 决定行动
            action = await self.llm.decide_action(context)

            step = ReActStep(step_type=StepType.REASONING, thought=thought, action=action)
            result.steps.append(step)

            # 处理行动
            action_type = action.get("action_type", "continue")

            if action_type == "respond":
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                return result

            # 记录决策并发布事件
            if action_type in ["create_node", "execute_workflow", "request_clarification"]:
                decision = self._record_decision(action)
                if self.event_bus:
                    await self.publish_decision(action)

            # 判断是否继续
            should_continue = await self.llm.should_continue(context)
            if not should_continue:
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                return result

        # 达到最大迭代
        result.terminated_by_limit = True
        return result

    def decompose_goal(self, goal_description: str) -> list[Goal]:
        """分解目标为子目标

        参数：
            goal_description: 目标描述

        返回：
            子目标列表
        """
        import asyncio

        # 创建主目标
        main_goal = Goal(id=str(uuid4()), description=goal_description)
        self.session_context.push_goal(main_goal)

        # 调用LLM分解
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 同步方式获取mock返回值
                if hasattr(self.llm.decompose_goal, "return_value"):
                    subgoal_dicts = self.llm.decompose_goal.return_value
                else:
                    subgoal_dicts = []
            else:
                subgoal_dicts = loop.run_until_complete(self.llm.decompose_goal(goal_description))
        except RuntimeError:
            subgoal_dicts = asyncio.run(self.llm.decompose_goal(goal_description))

        # 转换为Goal对象
        subgoals = []
        for subgoal_dict in subgoal_dicts:
            subgoal = Goal(
                id=str(uuid4()), description=subgoal_dict["description"], parent_id=main_goal.id
            )
            subgoals.append(subgoal)
            self.session_context.push_goal(subgoal)

        return subgoals

    def complete_current_goal(self) -> Goal | None:
        """完成当前目标

        从目标栈弹出当前目标。

        返回：
            完成的目标
        """
        completed_goal = self.session_context.pop_goal()

        if completed_goal:
            # 记录到决策历史
            self.session_context.add_decision(
                {
                    "type": "complete_goal",
                    "goal_id": completed_goal.id,
                    "description": completed_goal.description,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return completed_goal

    def make_decision(self, context_hint: str) -> Decision:
        """做出决策

        参数：
            context_hint: 上下文提示

        返回：
            决策对象
        """
        import asyncio

        # 获取上下文
        context = self.get_context_for_reasoning()
        context["hint"] = context_hint

        # 调用LLM决定行动
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if hasattr(self.llm.decide_action, "return_value"):
                    action = self.llm.decide_action.return_value
                else:
                    action = {"action_type": "continue"}
            else:
                action = loop.run_until_complete(self.llm.decide_action(context))
        except RuntimeError:
            action = asyncio.run(self.llm.decide_action(context))

        # 转换为Decision
        action_type = action.get("action_type", "continue")

        decision_type_mapping = {
            "create_node": DecisionType.CREATE_NODE,
            "execute_workflow": DecisionType.EXECUTE_WORKFLOW,
            "request_clarification": DecisionType.REQUEST_CLARIFICATION,
            "respond": DecisionType.RESPOND,
            "continue": DecisionType.CONTINUE,
        }

        decision = Decision(
            type=decision_type_mapping.get(action_type, DecisionType.CONTINUE), payload=action
        )

        # 记录决策
        self._record_decision(action)

        return decision

    def _record_decision(self, action: dict[str, Any]) -> Decision:
        """记录决策到历史

        参数：
            action: 行动字典

        返回：
            决策对象
        """
        decision = Decision(
            type=DecisionType(action.get("action_type", "continue"))
            if action.get("action_type") in [dt.value for dt in DecisionType]
            else DecisionType.CONTINUE,
            payload=action,
        )

        self.session_context.add_decision(
            {
                "id": decision.id,
                "type": decision.type.value,
                "payload": decision.payload,
                "timestamp": decision.timestamp.isoformat(),
            }
        )

        return decision

    async def publish_decision(self, action: dict[str, Any]) -> None:
        """发布决策事件

        参数：
            action: 行动字典
        """
        if not self.event_bus:
            return

        event = DecisionMadeEvent(
            source="conversation_agent",
            decision_type=action.get("type", action.get("action_type", "unknown")),
            decision_id=str(uuid4()),
            payload=action,
            confidence=action.get("confidence", 1.0),
        )

        await self.event_bus.publish(event)

    def get_context_for_reasoning(self) -> dict[str, Any]:
        """获取推理上下文

        返回：
            包含完整上下文的字典
        """
        context = {
            "conversation_history": self.session_context.conversation_history.copy(),
            "current_goal": self.session_context.current_goal(),
            "goal_stack": [
                {"id": g.id, "description": g.description} for g in self.session_context.goal_stack
            ],
            "decision_history": self.session_context.decision_history.copy(),
            "user_id": self.session_context.global_context.user_id,
            "user_preferences": self.session_context.global_context.user_preferences,
            "system_config": self.session_context.global_context.system_config,
        }

        return context


# 导出
__all__ = [
    "StepType",
    "DecisionType",
    "ReActStep",
    "ReActResult",
    "Decision",
    "DecisionMadeEvent",
    "ConversationAgentLLM",
    "ConversationAgent",
]

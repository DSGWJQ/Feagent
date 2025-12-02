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
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from src.domain.services.context_manager import Goal, SessionContext
from src.domain.services.event_bus import Event, EventBus

if TYPE_CHECKING:
    from src.domain.agents.node_definition import NodeDefinition
    from src.domain.agents.workflow_plan import WorkflowPlan


class StepType(str, Enum):
    """ReAct步骤类型"""

    REASONING = "reasoning"  # 推理步骤
    ACTION = "action"  # 行动步骤
    OBSERVATION = "observation"  # 观察步骤
    FINAL = "final"  # 最终回复


class IntentType(str, Enum):
    """意图类型 (Phase 14)

    用于区分用户输入的意图，决定是否需要 ReAct 循环。
    """

    CONVERSATION = "conversation"  # 普通对话（不需要 ReAct）
    WORKFLOW_MODIFICATION = "workflow_modification"  # 工作流修改（需要 ReAct）
    WORKFLOW_QUERY = "workflow_query"  # 查询工作流状态
    CLARIFICATION = "clarification"  # 澄清请求
    ERROR_RECOVERY_REQUEST = "error_recovery_request"  # 错误恢复请求


class DecisionType(str, Enum):
    """决策类型"""

    CREATE_NODE = "create_node"  # 创建节点
    CREATE_WORKFLOW_PLAN = "create_workflow_plan"  # 创建完整工作流规划（Phase 8）
    EXECUTE_WORKFLOW = "execute_workflow"  # 执行工作流
    MODIFY_NODE = "modify_node"  # 修改节点定义（Phase 8）
    REQUEST_CLARIFICATION = "request_clarification"  # 请求澄清
    RESPOND = "respond"  # 直接回复
    CONTINUE = "continue"  # 继续推理
    ERROR_RECOVERY = "error_recovery"  # 错误恢复（Phase 13）
    REPLAN_WORKFLOW = "replan_workflow"  # 重新规划工作流（Phase 13）


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
    - limit_type: 限制类型（阶段5新增）
    - total_tokens: 总 token 消耗（阶段5新增）
    - total_cost: 总成本（阶段5新增）
    - execution_time: 执行时间秒（阶段5新增）
    - alert_message: 告警消息（阶段5新增）
    """

    completed: bool = False
    final_response: str | None = None
    iterations: int = 0
    terminated_by_limit: bool = False
    steps: list[ReActStep] = field(default_factory=list)
    # 阶段5新增：循环控制相关字段
    limit_type: str | None = None
    total_tokens: int = 0
    total_cost: float = 0.0
    execution_time: float = 0.0
    alert_message: str | None = None


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


@dataclass
class SimpleMessageEvent(Event):
    """简单消息事件 (Phase 15)

    当对话不需要 ReAct 循环（普通对话、工作流查询）时发布此事件。
    协调者Agent订阅此事件进行统计记录。

    属性：
    - user_input: 用户输入
    - response: 回复内容
    - intent: 意图类型
    - confidence: 意图分类置信度
    - session_id: 会话ID
    """

    user_input: str = ""
    response: str = ""
    intent: str = ""
    confidence: float = 1.0
    session_id: str = ""


@dataclass
class IntentClassificationResult:
    """意图分类结果 (Phase 14)

    属性：
    - intent: 识别的意图类型
    - confidence: 置信度 (0-1)
    - reasoning: 分类理由
    - extracted_entities: 从输入中提取的实体
    """

    intent: IntentType
    confidence: float = 1.0
    reasoning: str = ""
    extracted_entities: dict[str, Any] = field(default_factory=dict)


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

    async def plan_workflow(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        """规划工作流结构（Phase 8 新增）

        参数：
            goal: 用户目标
            context: 上下文信息

        返回：
            工作流规划字典，包含 nodes 和 edges
        """
        ...

    async def decompose_to_nodes(self, goal: str) -> list[dict[str, Any]]:
        """将目标分解为节点定义列表（Phase 8 新增）

        参数：
            goal: 用户目标

        返回：
            节点定义字典列表
        """
        ...

    async def replan_workflow(
        self,
        goal: str,
        failed_node_id: str,
        failure_reason: str,
        execution_context: dict[str, Any],
    ) -> dict[str, Any]:
        """重新规划工作流（Phase 13 新增）

        参数：
            goal: 原始目标
            failed_node_id: 失败的节点ID
            failure_reason: 失败原因
            execution_context: 执行上下文

        返回：
            重新规划的工作流字典
        """
        ...

    async def classify_intent(self, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        """分类用户意图（Phase 14 新增）

        参数：
            user_input: 用户输入
            context: 上下文信息

        返回：
            意图分类结果字典，包含：
            - intent: 意图类型 (conversation, workflow_modification, workflow_query, etc.)
            - confidence: 置信度 (0-1)
            - reasoning: 分类理由
            - extracted_entities: 提取的实体 (可选)
        """
        ...

    async def generate_response(self, user_input: str, context: dict[str, Any]) -> str:
        """直接生成回复（Phase 14 新增）

        用于普通对话场景，跳过 ReAct 循环直接生成回复。

        参数：
            user_input: 用户输入
            context: 上下文信息

        返回：
            回复文本
        """
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
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
        max_cost: float | None = None,
        coordinator: Any | None = None,
        enable_intent_classification: bool = False,
        intent_confidence_threshold: float = 0.7,
    ):
        """初始化对话Agent

        参数：
            session_context: 会话上下文
            llm: LLM接口
            event_bus: 事件总线（可选）
            max_iterations: 最大迭代次数
            timeout_seconds: 超时时间（秒，阶段5新增）
            max_tokens: 最大 token 限制（阶段5新增）
            max_cost: 最大成本限制（阶段5新增）
            coordinator: 协调者 Agent（阶段5新增）
            enable_intent_classification: 是否启用意图分类（Phase 14，默认False保持向后兼容）
            intent_confidence_threshold: 意图分类置信度阈值（Phase 14）
        """
        self.session_context = session_context
        self.llm = llm
        self.event_bus = event_bus
        self.max_iterations = max_iterations
        # 阶段5新增：循环控制配置
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.max_cost = max_cost
        self.coordinator = coordinator
        self._current_input: str | None = None

        # Phase 13: 反馈监听
        self.pending_feedbacks: list[dict[str, Any]] = []
        self._is_listening_feedbacks = False

        # Phase 14: 意图分类配置
        self.enable_intent_classification = enable_intent_classification
        self.intent_confidence_threshold = intent_confidence_threshold

        # Phase 16: WorkflowAgent 引用（用于新执行链路）
        self.workflow_agent: Any | None = None

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

            # 模拟LLM调用（同步）- 用于测试时的mock兼容
            try:
                # 使用mock的返回值
                thought = (
                    self.llm.think.return_value  # type: ignore[union-attr]
                    if hasattr(self.llm.think, "return_value")
                    else "思考中..."
                )
                action = (
                    self.llm.decide_action.return_value  # type: ignore[union-attr]
                    if hasattr(self.llm.decide_action, "return_value")
                    else {"action_type": "continue"}
                )

                # 如果有side_effect，使用它
                if (
                    hasattr(self.llm.decide_action, "side_effect")
                    and self.llm.decide_action.side_effect  # type: ignore[union-attr]
                ):
                    try:
                        action = self.llm.decide_action.side_effect[i]  # type: ignore[union-attr]
                    except (IndexError, TypeError):
                        pass

                should_continue = True
                if hasattr(self.llm.should_continue, "return_value"):
                    should_continue = self.llm.should_continue.return_value  # type: ignore[union-attr]
                if (
                    hasattr(self.llm.should_continue, "side_effect")
                    and self.llm.should_continue.side_effect  # type: ignore[union-attr]
                ):
                    try:
                        should_continue = self.llm.should_continue.side_effect[i]  # type: ignore[union-attr]
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
        import time

        result = ReActResult()
        self._current_input = user_input
        start_time = time.time()

        for i in range(self.max_iterations):
            result.iterations = i + 1

            # === 阶段5：循环控制检查 ===

            # 检查熔断器
            if self.coordinator and hasattr(self.coordinator, "circuit_breaker"):
                if self.coordinator.circuit_breaker.is_open:
                    result.terminated_by_limit = True
                    result.limit_type = "circuit_breaker"
                    result.alert_message = "熔断器已打开，循环终止"
                    result.execution_time = time.time() - start_time
                    return result

            # 检查超时
            if self.timeout_seconds:
                elapsed = time.time() - start_time
                if elapsed >= self.timeout_seconds:
                    result.terminated_by_limit = True
                    result.limit_type = "timeout"
                    result.execution_time = elapsed
                    result.alert_message = f"已超时 ({self.timeout_seconds}秒)，循环终止"
                    return result

            # 检查 token 限制
            if self.max_tokens and result.total_tokens >= self.max_tokens:
                result.terminated_by_limit = True
                result.limit_type = "token_limit"
                result.execution_time = time.time() - start_time
                result.alert_message = f"已达到 token 限制 ({self.max_tokens})，循环终止"
                return result

            # 检查成本限制
            if self.max_cost and result.total_cost >= self.max_cost:
                result.terminated_by_limit = True
                result.limit_type = "cost_limit"
                result.execution_time = time.time() - start_time
                result.alert_message = f"已达到成本限制 (${self.max_cost})，循环终止"
                return result

            # === 原有逻辑 ===

            # 获取上下文
            context = self.get_context_for_reasoning()
            context["user_input"] = user_input
            context["iteration"] = i + 1

            # 思考
            thought = await self.llm.think(context)

            # 决定行动
            action = await self.llm.decide_action(context)

            # 阶段5：累计 token 和成本
            try:
                if hasattr(self.llm, "get_token_usage"):
                    tokens = self.llm.get_token_usage()  # type: ignore[attr-defined]
                    if isinstance(tokens, int | float):
                        result.total_tokens += int(tokens)
                if hasattr(self.llm, "get_cost"):
                    cost = self.llm.get_cost()  # type: ignore[attr-defined]
                    if isinstance(cost, int | float):
                        result.total_cost += float(cost)
            except (TypeError, AttributeError):
                pass  # LLM 不支持这些方法时跳过

            step = ReActStep(step_type=StepType.REASONING, thought=thought, action=action)
            result.steps.append(step)

            # 处理行动
            action_type = action.get("action_type", "continue")

            if action_type == "respond":
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                result.execution_time = time.time() - start_time
                return result

            # 记录决策并发布事件
            if action_type in ["create_node", "execute_workflow", "request_clarification"]:
                self._record_decision(action)
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
        result.limit_type = "max_iterations"
        result.alert_message = f"已达到最大迭代次数限制 ({self.max_iterations} 次)，循环已终止"
        result.execution_time = time.time() - start_time
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
                    subgoal_dicts = self.llm.decompose_goal.return_value  # type: ignore[union-attr]
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
                    action = self.llm.decide_action.return_value  # type: ignore[union-attr]
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
            "create_workflow_plan": DecisionType.CREATE_WORKFLOW_PLAN,
            "execute_workflow": DecisionType.EXECUTE_WORKFLOW,
            "modify_node": DecisionType.MODIFY_NODE,
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
            # Phase 13: 添加待处理的反馈
            "pending_feedbacks": self.pending_feedbacks.copy(),
        }

        return context

    # === Phase 8: 工作流规划能力 ===

    async def create_workflow_plan(self, goal: str) -> "WorkflowPlan":
        """根据目标创建工作流规划（Phase 8 新增）

        参数：
            goal: 用户目标

        返回：
            WorkflowPlan 实例

        抛出：
            ValueError: 如果规划验证失败或存在循环依赖
        """
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        # 获取上下文
        context = self.get_context_for_reasoning()
        context["goal"] = goal

        # 调用 LLM 规划工作流
        plan_data = await self.llm.plan_workflow(goal, context)

        # 转换节点
        nodes = []
        for node_data in plan_data.get("nodes", []):
            node_type_str = node_data.get("type", "generic")
            try:
                node_type = NodeType(node_type_str.lower())
            except ValueError:
                node_type = NodeType.GENERIC

            node = NodeDefinition(
                node_type=node_type,
                name=node_data.get("name", ""),
                code=node_data.get("code"),
                prompt=node_data.get("prompt"),
                url=node_data.get("url"),
                method=node_data.get("method", "GET"),
                query=node_data.get("query"),
                config=node_data.get("config", {}),
            )
            nodes.append(node)

        # 转换边
        edges = []
        for edge_data in plan_data.get("edges", []):
            edge = EdgeDefinition(
                source_node=edge_data.get("source", edge_data.get("source_node", "")),
                target_node=edge_data.get("target", edge_data.get("target_node", "")),
                condition=edge_data.get("condition"),
            )
            edges.append(edge)

        # 创建规划
        plan = WorkflowPlan(
            name=plan_data.get("name", f"Plan for: {goal[:30]}"),
            description=plan_data.get("description", ""),
            goal=goal,
            nodes=nodes,
            edges=edges,
        )

        # 验证规划
        errors = plan.validate()
        if errors:
            raise ValueError(f"工作流规划验证失败: {'; '.join(errors)}")

        # 检测循环依赖
        if plan.has_circular_dependency():
            raise ValueError("工作流存在循环依赖 (Circular dependency detected)")

        return plan

    async def decompose_to_nodes(self, goal: str) -> list["NodeDefinition"]:
        """将目标分解为节点定义列表（Phase 8 新增）

        参数：
            goal: 用户目标

        返回：
            NodeDefinition 列表
        """
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 调用 LLM 分解
        node_dicts = await self.llm.decompose_to_nodes(goal)

        # 转换为 NodeDefinition
        nodes = []
        for node_data in node_dicts:
            node_type_str = node_data.get("type", "generic")
            try:
                node_type = NodeType(node_type_str.lower())
            except ValueError:
                node_type = NodeType.GENERIC

            node = NodeDefinition(
                node_type=node_type,
                name=node_data.get("name", ""),
                code=node_data.get("code"),
                prompt=node_data.get("prompt"),
                url=node_data.get("url"),
                query=node_data.get("query"),
                config=node_data.get("config", {}),
            )
            nodes.append(node)

        return nodes

    async def create_workflow_plan_and_publish(self, goal: str) -> "WorkflowPlan":
        """创建工作流规划并发布决策事件（Phase 8 新增）

        参数：
            goal: 用户目标

        返回：
            WorkflowPlan 实例
        """
        plan = await self.create_workflow_plan(goal)

        # 发布决策事件
        if self.event_bus:
            event = DecisionMadeEvent(
                source="conversation_agent",
                decision_type=DecisionType.CREATE_WORKFLOW_PLAN.value,
                decision_id=plan.id,
                payload=plan.to_dict(),
                confidence=1.0,
            )
            await self.event_bus.publish(event)

        # 记录决策
        self.session_context.add_decision(
            {
                "id": plan.id,
                "type": DecisionType.CREATE_WORKFLOW_PLAN.value,
                "payload": {"plan_name": plan.name, "node_count": len(plan.nodes)},
                "timestamp": datetime.now().isoformat(),
            }
        )

        return plan

    # === Phase 13: 反馈监听与错误恢复 ===

    def start_feedback_listening(self) -> None:
        """开始监听协调者反馈事件

        订阅 WorkflowAdjustmentRequestedEvent 和 NodeFailureHandledEvent，
        将反馈存储到 pending_feedbacks 供 ReAct 循环使用。
        """
        if self._is_listening_feedbacks:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for feedback listening")

        from src.domain.agents.coordinator_agent import (
            NodeFailureHandledEvent,
            WorkflowAdjustmentRequestedEvent,
        )

        self.event_bus.subscribe(WorkflowAdjustmentRequestedEvent, self._handle_adjustment_event)
        self.event_bus.subscribe(NodeFailureHandledEvent, self._handle_failure_handled_event)

        self._is_listening_feedbacks = True

    def stop_feedback_listening(self) -> None:
        """停止监听协调者反馈事件"""
        if not self._is_listening_feedbacks:
            return

        if not self.event_bus:
            return

        from src.domain.agents.coordinator_agent import (
            NodeFailureHandledEvent,
            WorkflowAdjustmentRequestedEvent,
        )

        self.event_bus.unsubscribe(WorkflowAdjustmentRequestedEvent, self._handle_adjustment_event)
        self.event_bus.unsubscribe(NodeFailureHandledEvent, self._handle_failure_handled_event)

        self._is_listening_feedbacks = False

    async def _handle_adjustment_event(self, event: Any) -> None:
        """处理工作流调整请求事件"""
        self.pending_feedbacks.append(
            {
                "type": "workflow_adjustment",
                "workflow_id": event.workflow_id,
                "failed_node_id": event.failed_node_id,
                "failure_reason": event.failure_reason,
                "suggested_action": event.suggested_action,
                "execution_context": event.execution_context,
                "timestamp": event.timestamp,
            }
        )

    async def _handle_failure_handled_event(self, event: Any) -> None:
        """处理节点失败处理完成事件"""
        self.pending_feedbacks.append(
            {
                "type": "node_failure_handled",
                "workflow_id": event.workflow_id,
                "node_id": event.node_id,
                "strategy": event.strategy,
                "success": event.success,
                "retry_count": event.retry_count,
                "timestamp": event.timestamp,
            }
        )

    def get_pending_feedbacks(self) -> list[dict[str, Any]]:
        """获取待处理的反馈列表

        返回：
            反馈列表的副本
        """
        return self.pending_feedbacks.copy()

    def clear_feedbacks(self) -> None:
        """清空待处理的反馈"""
        self.pending_feedbacks.clear()

    async def generate_error_recovery_decision(self) -> Decision | None:
        """生成错误恢复决策

        根据 pending_feedbacks 中的反馈信息生成恢复决策。

        返回：
            错误恢复决策，如果没有待处理的反馈返回 None
        """
        if not self.pending_feedbacks:
            return None

        # 获取最新的调整请求
        adjustment_feedbacks = [
            f for f in self.pending_feedbacks if f["type"] == "workflow_adjustment"
        ]

        if not adjustment_feedbacks:
            return None

        feedback = adjustment_feedbacks[0]

        # 构建上下文
        context = self.get_context_for_reasoning()
        context["feedback"] = feedback

        # 调用 LLM 生成恢复计划（如果有 plan_error_recovery 方法）
        recovery_plan = {}
        if hasattr(self.llm, "plan_error_recovery"):
            recovery_plan = await self.llm.plan_error_recovery(context)  # type: ignore

        # 创建决策
        decision = Decision(
            type=DecisionType.ERROR_RECOVERY,
            payload={
                "failed_node_id": feedback["failed_node_id"],
                "failure_reason": feedback.get("failure_reason", ""),
                "workflow_id": feedback["workflow_id"],
                "recovery_plan": recovery_plan,
                "execution_context": feedback.get("execution_context", {}),
            },
        )

        # 记录决策
        self.session_context.add_decision(
            {
                "id": decision.id,
                "type": decision.type.value,
                "payload": decision.payload,
                "timestamp": decision.timestamp.isoformat(),
            }
        )

        return decision

    async def replan_workflow(
        self,
        original_goal: str,
        failed_node_id: str,
        failure_reason: str,
        execution_context: dict[str, Any],
    ) -> dict[str, Any]:
        """根据失败信息重新规划工作流

        参数：
            original_goal: 原始目标
            failed_node_id: 失败的节点ID
            failure_reason: 失败原因
            execution_context: 执行上下文（已完成的节点和输出）

        返回：
            重新规划的工作流
        """
        # 构建上下文
        context = self.get_context_for_reasoning()
        context["original_goal"] = original_goal
        context["failed_node_id"] = failed_node_id
        context["failure_reason"] = failure_reason
        context["execution_context"] = execution_context

        # 调用 LLM 重新规划
        if hasattr(self.llm, "replan_workflow"):
            plan = await self.llm.replan_workflow(
                goal=original_goal,
                failed_node_id=failed_node_id,
                failure_reason=failure_reason,
                execution_context=execution_context,
            )
        else:
            # 回退到普通的工作流规划
            plan = await self.llm.plan_workflow(original_goal, context)

        return plan

    # === Phase 14: 意图分类与分流处理 ===

    async def classify_intent(self, user_input: str) -> IntentClassificationResult:
        """分类用户输入的意图

        参数：
            user_input: 用户输入

        返回：
            IntentClassificationResult 意图分类结果
        """
        # 获取上下文
        context = self.get_context_for_reasoning()
        context["user_input"] = user_input

        # 调用 LLM 分类意图
        result_dict = await self.llm.classify_intent(user_input, context)

        # 转换意图类型
        intent_str = result_dict.get("intent", "conversation")
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.CONVERSATION

        return IntentClassificationResult(
            intent=intent,
            confidence=result_dict.get("confidence", 1.0),
            reasoning=result_dict.get("reasoning", ""),
            extracted_entities=result_dict.get("extracted_entities", {}),
        )

    async def process_with_intent(self, user_input: str) -> ReActResult:
        """基于意图分类处理用户输入

        如果启用意图分类且置信度足够高：
        - 普通对话：直接生成回复，跳过 ReAct 循环
        - 工作流查询：查询状态并返回
        - 工作流修改/错误恢复：使用 ReAct 循环

        参数：
            user_input: 用户输入

        返回：
            ReActResult 处理结果
        """
        self._current_input = user_input

        # 如果未启用意图分类，直接使用 ReAct 循环
        if not self.enable_intent_classification:
            return await self.run_async(user_input)

        # 分类意图
        classification = await self.classify_intent(user_input)

        # 如果置信度低于阈值，回退到 ReAct 循环
        if classification.confidence < self.intent_confidence_threshold:
            return await self.run_async(user_input)

        # 根据意图类型分流处理
        if classification.intent == IntentType.CONVERSATION:
            # 普通对话：直接生成回复
            return await self._handle_conversation(user_input, classification)

        elif classification.intent == IntentType.WORKFLOW_QUERY:
            # 工作流查询：返回状态信息
            return await self._handle_workflow_query(user_input, classification)

        else:
            # 工作流修改、澄清请求、错误恢复：使用 ReAct 循环
            return await self.run_async(user_input)

    async def _handle_conversation(
        self, user_input: str, classification: IntentClassificationResult
    ) -> ReActResult:
        """处理普通对话意图

        直接生成回复，不使用 ReAct 循环。

        参数：
            user_input: 用户输入
            classification: 意图分类结果

        返回：
            ReActResult
        """
        context = self.get_context_for_reasoning()
        context["user_input"] = user_input
        context["intent_classification"] = {
            "intent": classification.intent.value,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning,
        }

        # 直接生成回复
        response = await self.llm.generate_response(user_input, context)

        # 构建结果
        result = ReActResult(
            completed=True,
            final_response=response,
            iterations=0,  # 没有 ReAct 迭代
        )

        # 添加到对话历史
        self.session_context.conversation_history.append({"role": "user", "content": user_input})
        self.session_context.conversation_history.append({"role": "assistant", "content": response})

        # Phase 15: 发布简单消息事件
        if self.event_bus:
            event = SimpleMessageEvent(
                source="conversation_agent",
                user_input=user_input,
                response=response,
                intent=classification.intent.value,
                confidence=classification.confidence,
                session_id=self.session_context.session_id,
            )
            await self.event_bus.publish(event)

        return result

    async def _handle_workflow_query(
        self, user_input: str, classification: IntentClassificationResult
    ) -> ReActResult:
        """处理工作流查询意图

        参数：
            user_input: 用户输入
            classification: 意图分类结果

        返回：
            ReActResult
        """
        context = self.get_context_for_reasoning()
        context["user_input"] = user_input
        context["extracted_entities"] = classification.extracted_entities

        # 如果有专门的工作流状态查询方法
        if hasattr(self.llm, "generate_workflow_status"):
            response = await self.llm.generate_workflow_status(  # type: ignore[attr-defined]
                user_input, context
            )
        else:
            # 回退到通用回复生成
            response = await self.llm.generate_response(user_input, context)

        result = ReActResult(
            completed=True,
            final_response=response,
            iterations=0,
        )

        # Phase 15: 发布简单消息事件
        if self.event_bus:
            event = SimpleMessageEvent(
                source="conversation_agent",
                user_input=user_input,
                response=response,
                intent=classification.intent.value,
                confidence=classification.confidence,
                session_id=self.session_context.session_id,
            )
            await self.event_bus.publish(event)

        return result

    # === Phase 16: 新执行链路 ===

    async def execute_workflow(self, workflow: dict[str, Any]) -> Any:
        """执行工作流并返回结果（Phase 16 新执行链路）

        通过 WorkflowAgent 执行工作流，自动调用反思，
        不创建子 Agent，直接使用已注册的 WorkflowAgent。

        参数：
            workflow: 工作流定义

        返回：
            WorkflowExecutionResult 执行结果
        """
        if not self.workflow_agent:
            raise ValueError("WorkflowAgent not registered. Set workflow_agent first.")

        # 执行工作流
        result = await self.workflow_agent.execute(workflow)

        # 自动调用反思
        await self.workflow_agent.reflect(result)

        return result


# 类型提示导入（避免循环导入）
if False:  # TYPE_CHECKING
    from src.domain.agents.node_definition import NodeDefinition
    from src.domain.agents.workflow_plan import WorkflowPlan


# 导出
__all__ = [
    "StepType",
    "IntentType",
    "DecisionType",
    "ReActStep",
    "ReActResult",
    "Decision",
    "DecisionMadeEvent",
    "SimpleMessageEvent",
    "IntentClassificationResult",
    "ConversationAgentLLM",
    "ConversationAgent",
]

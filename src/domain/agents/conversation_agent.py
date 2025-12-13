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

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Final, Protocol
from uuid import uuid4

# P1-6 Phase 3/4/5: Shared models and events (re-export for backward compatibility)
from src.domain.agents.conversation_agent_control_flow import (
    ConversationAgentControlFlowMixin,
)
from src.domain.agents.conversation_agent_events import (
    DecisionMadeEvent,
    IntentClassificationResult,
    SimpleMessageEvent,
)
from src.domain.agents.conversation_agent_models import Decision, DecisionType
from src.domain.agents.conversation_agent_recovery import ConversationAgentRecoveryMixin

# =========================================================================
# P1-6 Phase 2: State module imports (re-export for backward compatibility)
# =========================================================================
from src.domain.agents.conversation_agent_state import (
    VALID_STATE_TRANSITIONS,
    ConversationAgentState,
    ConversationAgentStateMixin,
    SpawnSubAgentEvent,
    StateChangedEvent,
)

# P1-6 Phase 3/4/5: Workflow, Recovery, and Control Flow mixins
from src.domain.agents.conversation_agent_workflow import ConversationAgentWorkflowMixin
from src.domain.services.context_manager import Goal, SessionContext
from src.domain.services.event_bus import EventBus

# =========================================================================
# P1-4: Config兼容性支持（sentinel模式）
# =========================================================================
_LEGACY_UNSET: Final[object] = object()
"""Sentinel值，用于区分'未传递参数'与'传递了None'"""

# =========================================================================
# P1 Fix: 配置常量（避免魔法数字）
# =========================================================================
DEFAULT_MAX_ITERATIONS = 10
"""默认最大ReAct迭代次数"""

DEFAULT_INTENT_CONFIDENCE_THRESHOLD = 0.7
"""默认意图分类置信度阈值"""

RULE_BASED_EXTRACTION_CONFIDENCE = 0.6
"""基于规则提取的置信度（较低，因为不如LLM准确）"""

# =========================================================================
# P1 Fix: 决策类型映射常量（避免重复创建）
# =========================================================================
# 注意：此映射在 DecisionType 枚举定义后使用，在 make_decision 中引用
# 延迟定义为 lambda 以避免循环引用
_DECISION_TYPE_MAP: dict[str, DecisionType] | None = None


def _get_decision_type_map() -> dict[str, DecisionType]:
    """获取决策类型映射（延迟初始化）"""
    global _DECISION_TYPE_MAP
    if _DECISION_TYPE_MAP is None:
        _DECISION_TYPE_MAP = {
            "create_node": DecisionType.CREATE_NODE,
            "create_workflow_plan": DecisionType.CREATE_WORKFLOW_PLAN,
            "execute_workflow": DecisionType.EXECUTE_WORKFLOW,
            "modify_node": DecisionType.MODIFY_NODE,
            "request_clarification": DecisionType.REQUEST_CLARIFICATION,
            "respond": DecisionType.RESPOND,
            "continue": DecisionType.CONTINUE,
            "error_recovery": DecisionType.ERROR_RECOVERY,
            "replan_workflow": DecisionType.REPLAN_WORKFLOW,
            "spawn_subagent": DecisionType.SPAWN_SUBAGENT,
        }
    return _DECISION_TYPE_MAP


if TYPE_CHECKING:
    from src.domain.agents.conversation_agent_config import (
        ConversationAgentConfig,
    )


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


class ConversationAgent(
    ConversationAgentStateMixin,
    ConversationAgentWorkflowMixin,
    ConversationAgentRecoveryMixin,
    ConversationAgentControlFlowMixin,
):
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
        session_context: SessionContext | object = _LEGACY_UNSET,
        llm: ConversationAgentLLM | object = _LEGACY_UNSET,
        event_bus: EventBus | None | object = _LEGACY_UNSET,
        max_iterations: int | object = _LEGACY_UNSET,
        timeout_seconds: float | None | object = _LEGACY_UNSET,
        max_tokens: int | None | object = _LEGACY_UNSET,
        max_cost: float | None | object = _LEGACY_UNSET,
        coordinator: Any | None | object = _LEGACY_UNSET,
        enable_intent_classification: bool | object = _LEGACY_UNSET,
        intent_confidence_threshold: float | object = _LEGACY_UNSET,
        emitter: Any | None | object = _LEGACY_UNSET,
        stream_emitter: Any | None | object = _LEGACY_UNSET,
        *,
        config: ConversationAgentConfig | None = None,
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
            emitter: ConversationFlowEmitter 实例（Phase 2，可选）
            stream_emitter: 流式输出器实例（Phase 8.4，可选）
            config: ConversationAgentConfig 实例（P1-4新增，可选）
        """
        # P1-4: Config兼容性 - 解析配置
        if config is not None or any(
            param is not _LEGACY_UNSET
            for param in [
                session_context,
                llm,
                event_bus,
                max_iterations,
                timeout_seconds,
                max_tokens,
                max_cost,
                coordinator,
                enable_intent_classification,
                intent_confidence_threshold,
                emitter,
                stream_emitter,
            ]
        ):
            final_config = self._resolve_config(
                config,
                session_context,
                llm,
                event_bus,
                max_iterations,
                timeout_seconds,
                max_tokens,
                max_cost,
                coordinator,
                enable_intent_classification,
                intent_confidence_threshold,
                emitter,
                stream_emitter,
            )
            # 从config提取参数
            session_context = final_config.session_context
            llm = final_config.llm.llm  # type: ignore[assignment]
            event_bus = final_config.event_bus
            max_iterations = final_config.react.max_iterations  # type: ignore[assignment]
            timeout_seconds = final_config.react.timeout_seconds
            max_tokens = final_config.resource.max_tokens
            max_cost = final_config.resource.max_cost
            coordinator = final_config.workflow.coordinator
            enable_intent_classification = final_config.intent.enable_intent_classification  # type: ignore[assignment]
            intent_confidence_threshold = final_config.intent.intent_confidence_threshold  # type: ignore[assignment]
            emitter = final_config.streaming.emitter
            stream_emitter = final_config.streaming.stream_emitter
        else:
            # P1-4: 无参构造不合法（Critical修复）
            raise ValueError(
                "ConversationAgent requires initialization parameters. "
                "Provide either 'config' parameter or legacy parameters (session_context and llm are required)."
            )

        self.session_context = session_context  # type: ignore[assignment]
        self.llm = llm  # type: ignore[assignment]
        self.event_bus = event_bus
        self.max_iterations = max_iterations
        # 阶段5新增：循环控制配置
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.max_cost = max_cost
        self.coordinator = coordinator
        self._current_input: str | None = None

        # Phase 14: 意图分类配置
        self.enable_intent_classification = enable_intent_classification
        self.intent_confidence_threshold = intent_confidence_threshold

        # Phase 16: WorkflowAgent 引用（用于新执行链路）
        self.workflow_agent: Any | None = None

        # Phase 2: 流式输出 emitter
        self.emitter = emitter

        # Phase 8.4: 流式进度输出器
        self.stream_emitter = stream_emitter

        # P1-6 Phase 2: State mixin initialization
        self._init_state_mixin()

        # P1-6 Phase 4: Recovery mixin initialization
        self._init_recovery_mixin()

        # Phase 1: 协调者上下文缓存
        self._coordinator_context: Any | None = None

        # Phase 8.4: 进度事件转发
        self.progress_events: list[Any] = []  # 存储进度事件历史
        self._is_listening_progress = False

        # Phase 34: 保存请求通道
        self._save_request_channel_enabled = False

        # P0-2 Phase 2: Staged shared-state updates for batching (performance optimization)
        self._staged_prompt_tokens: int = 0
        self._staged_completion_tokens: int = 0
        self._staged_decision_records: list[dict[str, Any]] = []

        # P1 Fix: 决策元数据自管（避免污染 session_context）
        self._decision_metadata: list[dict[str, Any]] = []

    # =========================================================================
    # P0-2 Phase 2: Staged State Updates (Batching Mechanism)
    # =========================================================================

    def _stage_token_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """暂存token使用增量（P0-2 Phase 2）

        用于批量提交，减少锁获取次数，提升高频路径性能。

        参数：
            prompt_tokens: 提示token增量
            completion_tokens: 完成token增量
        """
        self._staged_prompt_tokens += int(prompt_tokens)
        self._staged_completion_tokens += int(completion_tokens)

    def _stage_decision_record(self, record: dict[str, Any]) -> None:
        """暂存决策记录（P0-2 Phase 2）

        用于批量提交，减少锁获取次数。

        参数：
            record: 决策记录字典
        """
        self._staged_decision_records.append(record)

    async def _flush_staged_state(self) -> None:
        """刷新暂存的状态更新（P0-2 Phase 2）

        在_state_lock保护下批量提交token使用和决策记录。

        性能优化：
        - 每轮迭代只获取一次锁
        - 锁内只做纯内存更新（无await）
        - 减少锁竞争和上下文切换开销

        调用时机：
        - 每轮迭代末尾
        - 所有早退分支（respond/should_continue==False/limit）前

        注意：锁内不允许await（除了获取锁本身）
        """
        # 快速路径：无暂存数据时直接返回
        if (
            self._staged_prompt_tokens == 0
            and self._staged_completion_tokens == 0
            and not self._staged_decision_records
        ):
            return

        async with self._state_lock:
            # 批量提交token使用
            if self._staged_prompt_tokens > 0 or self._staged_completion_tokens > 0:
                self.session_context.update_token_usage(
                    prompt_tokens=self._staged_prompt_tokens,
                    completion_tokens=self._staged_completion_tokens,
                )
                self._staged_prompt_tokens = 0
                self._staged_completion_tokens = 0

            # 批量提交决策记录
            if self._staged_decision_records:
                for record in self._staged_decision_records:
                    self.session_context.add_decision(record)
                self._staged_decision_records.clear()

    # =========================================================================
    # Phase 34: 保存请求通道方法
    # =========================================================================

    def enable_save_request_channel(self) -> None:
        """启用保存请求通道

        启用后，ConversationAgent 将通过 SaveRequest 事件请求持久化操作，
        而不是直接执行文件写入。
        """
        self._save_request_channel_enabled = True

    def disable_save_request_channel(self) -> None:
        """禁用保存请求通道"""
        self._save_request_channel_enabled = False

    def is_save_request_channel_enabled(self) -> bool:
        """检查保存请求通道是否启用

        返回：
            True 如果已启用
        """
        return self._save_request_channel_enabled

    def request_save(
        self,
        target_path: str,
        content: str | bytes,
        reason: str,
        priority: Any | None = None,
        is_binary: bool = False,
    ) -> str | None:
        """发起保存请求

        通过 EventBus 发布 SaveRequest 事件，而非直接写入文件。
        需要先调用 enable_save_request_channel() 启用此功能。

        参数：
            target_path: 目标文件路径
            content: 保存内容
            reason: 保存原因说明
            priority: 优先级（可选）
            is_binary: 是否为二进制内容

        返回：
            请求 ID，如果发送失败返回 None
        """
        if not self._save_request_channel_enabled:
            return None

        if not self.event_bus:
            return None

        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
            SaveRequestType,
        )

        # 设置默认优先级
        if priority is None:
            priority = SaveRequestPriority.NORMAL

        # 创建保存请求
        request = SaveRequest(
            target_path=target_path,
            content=content,
            operation_type=SaveRequestType.FILE_WRITE,
            session_id=self.session_context.session_id,
            reason=reason,
            priority=priority,
            source_agent="ConversationAgent",
            is_binary=is_binary,
        )

        # P1 Fix: 使用 _create_tracked_task 确保事件被发布（避免协程被丢弃）
        self._create_tracked_task(self.event_bus.publish(request))

        return request.request_id

    def is_waiting_for_subagent(self) -> bool:
        """检查是否正在等待子Agent"""
        return self._state == ConversationAgentState.WAITING_FOR_SUBAGENT

    def is_processing(self) -> bool:
        """检查是否正在处理"""
        return self._state == ConversationAgentState.PROCESSING

    def is_idle(self) -> bool:
        """检查是否空闲"""
        return self._state == ConversationAgentState.IDLE

    def create_spawn_subagent_decision(
        self,
        subagent_type: str,
        task_payload: dict[str, Any],
        context_snapshot: dict[str, Any] | None = None,
        priority: int = 0,
        confidence: float = 1.0,
    ) -> Decision:
        """创建 spawn_subagent 决策

        参数：
            subagent_type: 子Agent类型
            task_payload: 任务负载
            context_snapshot: 上下文快照（可选）
            priority: 优先级（默认0）
            confidence: 置信度（默认1.0）

        返回：
            Decision 决策对象
        """
        return Decision(
            type=DecisionType.SPAWN_SUBAGENT,
            payload={
                "subagent_type": subagent_type,
                "task_payload": task_payload,
                "priority": priority,
                "context_snapshot": context_snapshot or {},
            },
            confidence=confidence,
        )

    def request_subagent_spawn(
        self,
        subagent_type: str,
        task_payload: dict[str, Any],
        priority: int = 0,
        wait_for_result: bool = True,
        context_snapshot: dict[str, Any] | None = None,
    ) -> str:
        """请求生成子Agent（同步版本）

        注意：同步版本无法await事件发布，仅适用于非关键路径。
        在异步上下文中请使用request_subagent_spawn_async以保证关键事件顺序。

        参数：
            subagent_type: 子Agent类型
            task_payload: 任务负载
            priority: 优先级（默认0）
            wait_for_result: 是否等待结果（默认True）
            context_snapshot: 上下文快照（可选）

        返回：
            生成的子Agent ID
        """
        from uuid import uuid4

        subagent_id = f"subagent_{uuid4().hex[:12]}"
        task_id = f"task_{uuid4().hex[:8]}"

        # P0-2 Fix: 使用通知事件后台追踪发布
        self._publish_notification_event(
            SpawnSubAgentEvent(
                subagent_type=subagent_type,
                task_payload=task_payload,
                priority=priority,
                session_id=self.session_context.session_id,
                context_snapshot=context_snapshot or {},
                source="conversation_agent",
            )
        )

        # 如果需要等待结果，进入等待状态
        if wait_for_result:
            self.wait_for_subagent(
                subagent_id=subagent_id,
                task_id=task_id,
                context=context_snapshot or {},
            )

        return subagent_id

    async def request_subagent_spawn_async(
        self,
        subagent_type: str,
        task_payload: dict[str, Any],
        priority: int = 0,
        wait_for_result: bool = True,
        context_snapshot: dict[str, Any] | None = None,
    ) -> str:
        """请求生成子Agent（异步版本，P0-2 Fix）

        关键保证：
        1. SpawnSubAgentEvent被await发布（协调者必须看到）
        2. 如果wait_for_result，状态转换发生在事件发布之后

        参数：
            subagent_type: 子Agent类型
            task_payload: 任务负载
            priority: 优先级（默认0）
            wait_for_result: 是否等待结果（默认True）
            context_snapshot: 上下文快照（可选）

        返回：
            生成的子Agent ID
        """
        from uuid import uuid4

        subagent_id = f"subagent_{uuid4().hex[:12]}"
        task_id = f"task_{uuid4().hex[:8]}"

        event = SpawnSubAgentEvent(
            subagent_type=subagent_type,
            task_payload=task_payload,
            priority=priority,
            session_id=self.session_context.session_id,
            context_snapshot=context_snapshot or {},
            source="conversation_agent",
        )
        await self._publish_critical_event(event)

        if wait_for_result:
            await self.wait_for_subagent_async(
                subagent_id=subagent_id,
                task_id=task_id,
                context=context_snapshot or {},
            )

        return subagent_id

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

        for iteration_count in range(self.max_iterations):
            result.iterations = iteration_count + 1

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
                        action = self.llm.decide_action.side_effect[iteration_count]  # type: ignore[union-attr]
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
                        should_continue = self.llm.should_continue.side_effect[iteration_count]  # type: ignore[union-attr]
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
        import logging
        import time

        result = ReActResult()
        self._current_input = user_input
        start_time = time.time()

        # Step 1: 初始化模型信息（如果尚未设置）
        if self.session_context.context_limit == 0:
            self._initialize_model_info()

        # Phase 1: 从协调者获取上下文（规则库、知识库、工具库）
        coordinator_context = None
        if self.coordinator and hasattr(self.coordinator, "get_context_async"):
            try:
                coordinator_context = await self.coordinator.get_context_async(user_input)
                # 记录上下文信息
                self._log_coordinator_context(coordinator_context)
            except Exception as e:
                # 上下文获取失败不应阻止主流程
                logging.warning(f"Failed to get coordinator context: {e}")

        # 保存协调者上下文供后续使用
        self._coordinator_context = coordinator_context

        for iteration_count in range(self.max_iterations):
            result.iterations = iteration_count + 1

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
            context["iteration"] = iteration_count + 1

            # 思考
            try:
                thought = await self.llm.think(context)

                # Phase 2: 发送思考步骤到 emitter
                if self.emitter:
                    await self.emitter.emit_thinking(thought)
            except Exception as e:
                # Phase 2: 发送错误到 emitter
                if self.emitter:
                    await self.emitter.emit_error(str(e), error_code="LLM_THINK_ERROR")
                    await self.emitter.complete()
                raise

            # 决定行动
            action = await self.llm.decide_action(context)

            # 阶段5：累计 token 和成本
            # Step 1: 记录每轮的 token 使用情况
            prompt_tokens = 0
            completion_tokens = 0
            try:
                if hasattr(self.llm, "get_token_usage"):
                    tokens = self.llm.get_token_usage()  # type: ignore[attr-defined]
                    if isinstance(tokens, int | float):
                        result.total_tokens += int(tokens)
                        completion_tokens = int(tokens)
                if hasattr(self.llm, "get_cost"):
                    cost = self.llm.get_cost()  # type: ignore[attr-defined]
                    if isinstance(cost, int | float):
                        result.total_cost += float(cost)
            except (TypeError, AttributeError):
                pass  # LLM 不支持这些方法时跳过

            # Step 1: 更新 SessionContext 的 token 使用情况（P0-2 Phase 2: 使用staged机制）
            if prompt_tokens > 0 or completion_tokens > 0:
                self._stage_token_usage(
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
                )

                # Step 1: 检查是否接近上下文限制并输出预警
                if self.session_context.is_approaching_limit():
                    self._log_context_warning()

            step = ReActStep(step_type=StepType.REASONING, thought=thought, action=action)
            result.steps.append(step)

            # 处理行动
            action_type = action.get("action_type", "continue")

            if action_type == "respond":
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                result.execution_time = time.time() - start_time

                # P0-2 Phase 2: Flush staged state before return
                await self._flush_staged_state()

                # Phase 2: 发送最终响应到 emitter 并完成
                if self.emitter:
                    await self.emitter.emit_final_response(result.final_response)
                    await self.emitter.complete()

                return result

            # Phase 2: 处理工具调用
            if action_type == "tool_call" and self.emitter:
                await self.emitter.emit_tool_call(
                    tool_name=action.get("tool_name", ""),
                    tool_id=action.get("tool_id", ""),
                    arguments=action.get("arguments", {}),
                )

            # 记录决策并发布事件（P0-2 Phase 2: 使用async staged版本）
            if action_type in ["create_node", "execute_workflow", "request_clarification"]:
                await self._record_decision_async(action)
                await self._flush_staged_state()  # 立即flush以确保决策被记录
                if self.event_bus:
                    await self.publish_decision(action)

            # 判断是否继续
            should_continue = await self.llm.should_continue(context)
            if not should_continue:
                result.completed = True
                result.final_response = action.get("response", "任务完成")

                # P0-2 Phase 2: Flush staged state before return
                await self._flush_staged_state()

                # Phase 2: 发送最终响应到 emitter 并完成
                if self.emitter:
                    await self.emitter.emit_final_response(result.final_response)
                    await self.emitter.complete()

                return result

        # 达到最大迭代
        result.terminated_by_limit = True
        result.limit_type = "max_iterations"
        result.alert_message = f"已达到最大迭代次数限制 ({self.max_iterations} 次)，循环已终止"
        result.execution_time = time.time() - start_time

        # P0-2 Phase 2: Flush staged state before return
        await self._flush_staged_state()

        # Phase 2: 完成 emitter
        if self.emitter:
            await self.emitter.complete()

        return result

    def decompose_goal(self, goal_description: str) -> list[Goal]:
        """分解目标为子目标

        参数：
            goal_description: 目标描述

        返回：
            子目标列表
        """

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
        """做出决策（增强版：集成 Pydantic schema 验证）

        参数：
            context_hint: 上下文提示

        返回：
            决策对象

        异常：
            ValidationError: 如果决策 payload 不符合 schema
        """

        from pydantic import ValidationError

        from src.domain.agents.conversation_agent_enhanced import (
            validate_and_enhance_decision,
        )

        # 获取上下文
        context = self.get_context_for_reasoning()
        context["hint"] = context_hint

        # 添加资源约束到上下文
        if hasattr(self.session_context, "resource_constraints"):
            context["resource_constraints"] = self.session_context.resource_constraints

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

        # 获取 action_type
        action_type = action.get("action_type", "continue")

        # ========================================
        # 【增强功能】使用 Pydantic schema 验证
        # ========================================
        try:
            # 获取资源约束（如果存在）
            constraints = (
                self.session_context.resource_constraints
                if hasattr(self.session_context, "resource_constraints")
                else None
            )

            # 综合验证和增强
            validated_payload, metadata = validate_and_enhance_decision(
                action_type, action, constraints
            )

            # 使用验证后的 payload（转回字典）
            validated_dict = validated_payload.model_dump()

            # P1 Fix: 将元数据添加到自管列表（避免污染 session_context）
            if metadata:
                self._decision_metadata.append(
                    {
                        "action_type": action_type,
                        "timestamp": datetime.now().isoformat(),
                        "metadata": metadata,
                    }
                )

        except ValidationError as e:
            # Payload 验证失败
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"决策 payload 验证失败: {e.errors()}")

            # 记录验证失败
            self.session_context.add_decision(
                {
                    "type": "validation_failed",
                    "action_type": action_type,
                    "errors": str(e.errors()),
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # 重新抛出异常
            raise

        # 转换为Decision（使用验证后的 payload）
        # P1 Fix: 使用模块级常量映射，避免每次调用重建字典
        decision = Decision(
            type=_get_decision_type_map().get(action_type, DecisionType.CONTINUE),
            payload=validated_dict,  # 使用验证后的 payload
        )

        # 记录决策
        self._record_decision(validated_dict)

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

    async def _record_decision_async(self, action: dict[str, Any]) -> Decision:
        """记录决策到历史（异步staged版本，P0-2 Phase 2）

        使用staged机制暂存决策记录，批量提交以减少锁获取次数。

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

        # Phase 2: 使用staged机制暂存决策记录
        self._stage_decision_record(
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

    def _log_coordinator_context(self, context: Any) -> None:
        """记录协调者上下文信息（Phase 1）

        将协调者返回的上下文信息记录到日志，方便调试和追踪。

        参数：
            context: ContextResponse 对象
        """
        import logging

        logger = logging.getLogger(__name__)

        if context is None:
            logger.debug("Coordinator context is None")
            return

        # 记录上下文摘要
        summary = getattr(context, "summary", "")
        rules_count = len(getattr(context, "rules", []))
        tools_count = len(getattr(context, "tools", []))
        knowledge_count = len(getattr(context, "knowledge", []))

        logger.info(
            f"Coordinator context retrieved: "
            f"rules={rules_count}, tools={tools_count}, knowledge={knowledge_count}"
        )

        if summary:
            logger.debug(f"Context summary: {summary}")

        # 如果有工作流上下文，也记录
        workflow_context = getattr(context, "workflow_context", None)
        if workflow_context:
            workflow_id = workflow_context.get("workflow_id", "unknown")
            status = workflow_context.get("status", "unknown")
            logger.debug(f"Workflow context: id={workflow_id}, status={status}")

    def _initialize_model_info(self) -> None:
        """初始化模型信息（Step 1: 模型上下文能力确认）

        从 LLM 客户端或配置中获取模型信息，并设置到 SessionContext。
        """
        import logging

        from src.config import settings
        from src.lc.model_metadata import get_model_metadata

        logger = logging.getLogger(__name__)

        # 尝试从配置获取模型信息
        provider = "openai"  # 默认提供商
        model = settings.openai_model

        # 获取模型元数据
        metadata = get_model_metadata(provider, model)

        # 设置到 SessionContext
        self.session_context.set_model_info(
            provider=provider, model=model, context_limit=metadata.context_window
        )

        logger.info(
            f"Model info initialized: provider={provider}, model={model}, "
            f"context_limit={metadata.context_window}"
        )

    def _log_context_warning(self) -> None:
        """记录上下文限制预警（Step 1: 模型上下文能力确认）

        当上下文使用率接近限制时，输出预警日志。
        """
        import logging

        logger = logging.getLogger(__name__)

        summary = self.session_context.get_token_usage_summary()

        logger.warning(
            f"⚠️ Context limit approaching! "
            f"Usage: {summary['total_tokens']}/{summary['context_limit']} tokens "
            f"({summary['usage_ratio']:.1%}), "
            f"Remaining: {summary['remaining_tokens']} tokens"
        )

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

        # Phase 2: 发送最终响应到 emitter 并完成（普通对话跳过思考）
        if self.emitter:
            await self.emitter.emit_final_response(response)
            await self.emitter.complete()

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

        # Phase 2: 发送最终响应到 emitter 并完成
        if self.emitter:
            await self.emitter.emit_final_response(response)
            await self.emitter.complete()

        return result

    # === Phase 8.4: 进度事件转发 ===

    def start_progress_event_listener(self) -> None:
        """启动进度事件监听器

        订阅 ExecutionProgressEvent 以接收工作流执行进度更新。
        """
        if self._is_listening_progress:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for progress event listening")

        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        self.event_bus.subscribe(ExecutionProgressEvent, self._handle_progress_event_async)
        self._is_listening_progress = True

    async def _handle_progress_event_async(self, event: Any) -> None:
        """异步处理进度事件（EventBus 回调）

        参数：
            event: ExecutionProgressEvent 实例
        """
        self.handle_progress_event(event)

        # 如果有流式输出器，转发事件
        if self.stream_emitter:
            await self.forward_progress_event(event)

    def handle_progress_event(self, event: Any) -> None:
        """处理进度事件并记录到历史

        参数：
            event: ExecutionProgressEvent 实例
        """
        self.progress_events.append(event)

    async def forward_progress_event(self, event: Any) -> None:
        """转发进度事件到流式输出器

        参数：
            event: ExecutionProgressEvent 实例
        """
        if not self.stream_emitter:
            return

        # 格式化为用户可读消息
        formatted_message = self.format_progress_message(event)

        # 通过流式输出器发送
        await self.stream_emitter.emit(
            {
                "type": "progress",
                "message": formatted_message,
                "node_id": event.node_id,
                "status": event.status,
                "progress": event.progress,
            }
        )

    def format_progress_message(self, event: Any) -> str:
        """格式化进度事件为用户可读消息

        参数：
            event: ExecutionProgressEvent 实例

        返回：
            格式化的消息字符串
        """
        status = event.status
        progress = event.progress
        message = event.message

        # 根据状态格式化消息
        if status == "started":
            return f"[开始] {message}"
        elif status == "running":
            progress_percent = f"{progress * 100:.0f}%"
            return f"[执行中 {progress_percent}] {message}"
        elif status == "completed":
            return f"[完成 100%] {message}"
        elif status == "failed":
            return f"[失败] {message}"
        else:
            return f"[{status}] {message}"

    def format_progress_for_websocket(self, event: Any) -> dict[str, Any]:
        """格式化进度事件为 WebSocket 消息

        参数：
            event: ExecutionProgressEvent 实例

        返回：
            WebSocket 消息字典
        """
        return {
            "type": "progress",
            "data": {
                "workflow_id": event.workflow_id,
                "node_id": event.node_id,
                "status": event.status,
                "progress": event.progress,
                "message": event.message,
            },
        }

    def format_progress_for_sse(self, event: Any) -> str:
        """格式化进度事件为 SSE 消息

        参数:
            event: ExecutionProgressEvent 实例

        返回：
            SSE 格式的消息字符串
        """
        import json

        data = {
            "workflow_id": event.workflow_id,
            "node_id": event.node_id,
            "status": event.status,
            "progress": event.progress,
            "message": event.message,
        }
        return f"data: {json.dumps(data)}\n\n"

    def get_progress_events_by_workflow(self, workflow_id: str) -> list[Any]:
        """按工作流ID查询进度事件

        参数：
            workflow_id: 工作流ID

        返回：
            该工作流的进度事件列表
        """
        return [
            event
            for event in self.progress_events
            if hasattr(event, "workflow_id") and event.workflow_id == workflow_id
        ]

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

    # =========================================================================
    # P1-4: Config兼容性支持方法
    # =========================================================================

    def _resolve_config(
        self,
        config: ConversationAgentConfig | None,
        session_context: SessionContext | object,
        llm: Any | object,
        event_bus: EventBus | None | object,
        max_iterations: int | object,
        timeout_seconds: float | None | object,
        max_tokens: int | None | object,
        max_cost: float | None | object,
        coordinator: Any | None | object,
        enable_intent_classification: bool | object,
        intent_confidence_threshold: float | object,
        emitter: Any | None | object,
        stream_emitter: Any | None | object,
    ) -> ConversationAgentConfig:
        """解析最终配置（处理config与legacy参数的混用）"""

        # 收集所有传入的legacy参数
        legacy_params = {
            "session_context": session_context,
            "llm": llm,
            "event_bus": event_bus,
            "max_iterations": max_iterations,
            "timeout_seconds": timeout_seconds,
            "max_tokens": max_tokens,
            "max_cost": max_cost,
            "coordinator": coordinator,
            "enable_intent_classification": enable_intent_classification,
            "intent_confidence_threshold": intent_confidence_threshold,
            "emitter": emitter,
            "stream_emitter": stream_emitter,
        }

        # 过滤出真正传递的参数
        provided_legacy = {k: v for k, v in legacy_params.items() if v is not _LEGACY_UNSET}

        # 场景1: 仅传config
        if config is not None and not provided_legacy:
            return config

        # 场景2: 仅传legacy
        if config is None and provided_legacy:
            return self._legacy_to_config(provided_legacy)

        # 场景3: 混用 - 检测冲突
        if config is not None and provided_legacy:
            conflicts = self._detect_conflicts(config, provided_legacy)
            if conflicts:
                raise ValueError(
                    f"Conflicting parameters: {', '.join(conflicts)}. "
                    "Cannot mix config and legacy parameters for the same field."
                )
            return self._merge_config(config, provided_legacy)

        # 场景4: 都没传（不合法）
        raise ValueError(
            "Must provide either 'config' or legacy parameters (session_context and llm are required)"
        )

    def _detect_conflicts(
        self,
        config: ConversationAgentConfig,
        legacy_params: dict[str, Any],
    ) -> list[str]:
        """检测config与legacy参数的冲突"""

        conflicts = []

        # P1-4: 混合冲突检测语义
        # - 对象引用（session_context, llm, coordinator等）: 使用身份比较，相同对象允许
        # - 可选对象（event_bus等）: 两边都非None且不同对象时冲突
        # - 标量值（max_iterations等）: config使用默认值时允许legacy覆盖，否则值不同时冲突

        # 检查session_context（必选参数，config必然有值）
        if "session_context" in legacy_params:
            legacy_val = legacy_params["session_context"]
            if config.session_context is not legacy_val:
                conflicts.append(
                    f"session_context (config={type(config.session_context).__name__}, "
                    f"legacy={type(legacy_val).__name__})"
                )

        # 检查llm（必选参数，config.llm.llm必然有值）
        if "llm" in legacy_params:
            legacy_val = legacy_params["llm"]
            config_val = config.llm.llm
            if config_val is not legacy_val:
                conflicts.append(
                    f"llm (config={type(config_val).__name__}, "
                    f"legacy={type(legacy_val).__name__})"
                )

        # 检查event_bus（仅当两边都非None且不同时冲突）
        if "event_bus" in legacy_params:
            legacy_val = legacy_params["event_bus"]
            config_val = config.event_bus
            if config_val is not None and legacy_val is not None and config_val is not legacy_val:
                conflicts.append(
                    f"event_bus (config={type(config_val).__name__}, "
                    f"legacy={type(legacy_val).__name__})"
                )

        # 检查max_iterations（config使用非默认值且与legacy不同时冲突）
        if "max_iterations" in legacy_params:
            legacy_val = legacy_params["max_iterations"]
            config_val = config.react.max_iterations
            # 仅当config明确设置了非默认值，且与legacy不同时才冲突
            if config_val != DEFAULT_MAX_ITERATIONS and config_val != legacy_val:
                conflicts.append(f"max_iterations (config={config_val}, legacy={legacy_val})")

        # 检查timeout_seconds（仅当两边都非None且不同时冲突）
        if "timeout_seconds" in legacy_params:
            legacy_val = legacy_params["timeout_seconds"]
            config_val = config.react.timeout_seconds
            if config_val is not None and legacy_val is not None and config_val != legacy_val:
                conflicts.append(f"timeout_seconds (config={config_val}, legacy={legacy_val})")

        # 检查max_tokens（仅当两边都非None且不同时冲突）
        if "max_tokens" in legacy_params:
            legacy_val = legacy_params["max_tokens"]
            config_val = config.resource.max_tokens
            if config_val is not None and legacy_val is not None and config_val != legacy_val:
                conflicts.append(f"max_tokens (config={config_val}, legacy={legacy_val})")

        # 检查max_cost（仅当两边都非None且不同时冲突）
        if "max_cost" in legacy_params:
            legacy_val = legacy_params["max_cost"]
            config_val = config.resource.max_cost
            if config_val is not None and legacy_val is not None and config_val != legacy_val:
                conflicts.append(f"max_cost (config={config_val}, legacy={legacy_val})")

        # 检查coordinator（仅当两边都非None且不同时冲突）
        if "coordinator" in legacy_params:
            legacy_val = legacy_params["coordinator"]
            config_val = config.workflow.coordinator
            if config_val is not None and legacy_val is not None and config_val is not legacy_val:
                conflicts.append(
                    f"coordinator (config={type(config_val).__name__}, "
                    f"legacy={type(legacy_val).__name__})"
                )

        # 检查enable_intent_classification（config使用非默认值且与legacy不同时冲突）
        if "enable_intent_classification" in legacy_params:
            legacy_val = legacy_params["enable_intent_classification"]
            config_val = config.intent.enable_intent_classification
            # 仅当config明确设置了非默认值(False)，且与legacy不同时才冲突
            if config_val != False and config_val != legacy_val:  # noqa: E712
                conflicts.append(
                    f"enable_intent_classification (config={config_val}, legacy={legacy_val})"
                )

        # 检查intent_confidence_threshold（config使用非默认值且与legacy不同时冲突）
        if "intent_confidence_threshold" in legacy_params:
            legacy_val = legacy_params["intent_confidence_threshold"]
            config_val = config.intent.intent_confidence_threshold
            # 仅当config明确设置了非默认值，且与legacy不同时才冲突
            if config_val != DEFAULT_INTENT_CONFIDENCE_THRESHOLD and config_val != legacy_val:
                conflicts.append(
                    f"intent_confidence_threshold (config={config_val}, legacy={legacy_val})"
                )

        # 检查emitter（仅当两边都非None且不同时冲突）
        if "emitter" in legacy_params:
            legacy_val = legacy_params["emitter"]
            config_val = config.streaming.emitter
            if config_val is not None and legacy_val is not None and config_val is not legacy_val:
                conflicts.append(
                    f"emitter (config={type(config_val).__name__}, "
                    f"legacy={type(legacy_val).__name__})"
                )

        # 检查stream_emitter（仅当两边都非None且不同时冲突）
        if "stream_emitter" in legacy_params:
            legacy_val = legacy_params["stream_emitter"]
            config_val = config.streaming.stream_emitter
            if config_val is not None and legacy_val is not None and config_val is not legacy_val:
                conflicts.append(
                    f"stream_emitter (config={type(config_val).__name__}, "
                    f"legacy={type(legacy_val).__name__})"
                )

        return conflicts

    def _legacy_to_config(self, legacy_params: dict[str, Any]) -> ConversationAgentConfig:
        """将legacy参数转换为config"""
        from src.domain.agents.conversation_agent_config import (
            ConversationAgentConfig,
            IntentConfig,
            LLMConfig,
            ReActConfig,
            ResourceConfig,
            StreamingConfig,
            WorkflowConfig,
        )

        # 提取必选参数
        session_context = legacy_params.get("session_context")
        llm = legacy_params.get("llm")

        if session_context is None or llm is None:
            raise ValueError("session_context and llm are required")

        # 构建config
        return ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm),
            event_bus=legacy_params.get("event_bus"),
            react=ReActConfig(
                max_iterations=legacy_params.get("max_iterations", DEFAULT_MAX_ITERATIONS),
                timeout_seconds=legacy_params.get("timeout_seconds"),
            ),
            intent=IntentConfig(
                enable_intent_classification=legacy_params.get(
                    "enable_intent_classification", False
                ),
                intent_confidence_threshold=legacy_params.get(
                    "intent_confidence_threshold", DEFAULT_INTENT_CONFIDENCE_THRESHOLD
                ),
            ),
            workflow=WorkflowConfig(
                coordinator=legacy_params.get("coordinator"),
            ),
            streaming=StreamingConfig(
                emitter=legacy_params.get("emitter"),
                stream_emitter=legacy_params.get("stream_emitter"),
            ),
            resource=ResourceConfig(
                max_tokens=legacy_params.get("max_tokens"),
                max_cost=legacy_params.get("max_cost"),
            ),
        )

    def _merge_config(
        self,
        config: ConversationAgentConfig,
        legacy_params: dict[str, Any],
    ) -> ConversationAgentConfig:
        """合并config与legacy参数（legacy填充config未指定的字段）"""
        from src.domain.agents.conversation_agent_config import (
            IntentConfig,
            ReActConfig,
        )

        overrides = {}

        # event_bus
        if "event_bus" in legacy_params and config.event_bus is None:
            overrides["event_bus"] = legacy_params["event_bus"]

        # ReAct配置
        react_overrides = {}
        default_react = ReActConfig()
        if (
            "max_iterations" in legacy_params
            and config.react.max_iterations == default_react.max_iterations
        ):
            react_overrides["max_iterations"] = legacy_params["max_iterations"]
        if "timeout_seconds" in legacy_params and config.react.timeout_seconds is None:
            react_overrides["timeout_seconds"] = legacy_params["timeout_seconds"]
        if react_overrides:
            overrides["react"] = replace(config.react, **react_overrides)

        # Intent配置
        intent_overrides = {}
        default_intent = IntentConfig()
        if (
            "enable_intent_classification" in legacy_params
            and config.intent.enable_intent_classification
            == default_intent.enable_intent_classification
        ):
            intent_overrides["enable_intent_classification"] = legacy_params[
                "enable_intent_classification"
            ]
        if (
            "intent_confidence_threshold" in legacy_params
            and config.intent.intent_confidence_threshold
            == default_intent.intent_confidence_threshold
        ):
            intent_overrides["intent_confidence_threshold"] = legacy_params[
                "intent_confidence_threshold"
            ]
        if intent_overrides:
            overrides["intent"] = replace(config.intent, **intent_overrides)

        # Workflow配置
        if "coordinator" in legacy_params and config.workflow.coordinator is None:
            overrides["workflow"] = replace(
                config.workflow, coordinator=legacy_params["coordinator"]
            )

        # Streaming配置
        streaming_overrides = {}
        if "emitter" in legacy_params and config.streaming.emitter is None:
            streaming_overrides["emitter"] = legacy_params["emitter"]
        if "stream_emitter" in legacy_params and config.streaming.stream_emitter is None:
            streaming_overrides["stream_emitter"] = legacy_params["stream_emitter"]
        if streaming_overrides:
            overrides["streaming"] = replace(config.streaming, **streaming_overrides)

        # Resource配置
        resource_overrides = {}
        if "max_tokens" in legacy_params and config.resource.max_tokens is None:
            resource_overrides["max_tokens"] = legacy_params["max_tokens"]
        if "max_cost" in legacy_params and config.resource.max_cost is None:
            resource_overrides["max_cost"] = legacy_params["max_cost"]
        if resource_overrides:
            overrides["resource"] = replace(config.resource, **resource_overrides)

        return config.with_overrides(**overrides)


# 类型提示导入（避免循环导入）
if False:  # TYPE_CHECKING
    pass


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
    # P1-6 Phase 2: re-export state API
    "ConversationAgentState",
    "VALID_STATE_TRANSITIONS",
    "StateChangedEvent",
    "SpawnSubAgentEvent",
    "ConversationAgentStateMixin",
]

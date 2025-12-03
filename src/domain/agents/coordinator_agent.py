"""协调者Agent (CoordinatorAgent) - 多Agent协作系统的"守门人"

业务定义：
- 协调者Agent负责验证对话Agent的决策
- 通过规则引擎检查决策合法性
- 阻止违规决策，提供纠偏建议
- 监控系统运行状态

设计原则：
- 规则驱动：通过规则引擎进行验证
- 中间件模式：作为EventBus的中间件拦截决策
- 可配置性：规则可动态添加和修改
- 可观测性：跟踪决策统计和异常模式

核心能力：
- 规则引擎：定义和检查规则
- 决策验证：验证决策合法性
- 纠偏机制：拒绝或修正决策
- 流量监控：监控Agent间的事件流量
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event, EventBus


class FailureHandlingStrategy(str, Enum):
    """失败处理策略枚举

    定义节点失败时的处理方式：
    - RETRY: 重试执行
    - SKIP: 跳过节点继续执行
    - ABORT: 终止工作流
    - REPLAN: 请求对话Agent重新规划
    """

    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    REPLAN = "replan"


@dataclass
class Rule:
    """验证规则

    属性：
    - id: 规则唯一标识
    - name: 规则名称
    - description: 规则描述
    - condition: 条件函数，接收决策返回bool
    - priority: 优先级（数字越小优先级越高）
    - error_message: 验证失败时的错误信息
    - correction: 可选的修正函数
    """

    id: str
    name: str
    description: str = ""
    condition: Callable[[dict[str, Any]], bool] = field(default=lambda d: True)
    priority: int = 10
    error_message: str = "验证失败"
    correction: Callable[[dict[str, Any]], dict[str, Any]] | None = None


@dataclass
class ValidationResult:
    """验证结果

    属性：
    - is_valid: 是否验证通过
    - errors: 错误信息列表
    - correction: 可选的修正后决策
    """

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    correction: dict[str, Any] | None = None


@dataclass
class ContextResponse:
    """上下文响应结构（Phase 1）

    协调者返回给对话Agent的上下文信息，包含：
    - rules: 相关规则列表
    - knowledge: 相关知识库条目
    - tools: 可用工具列表
    - summary: 上下文摘要文本
    - workflow_context: 可选的工作流上下文

    属性：
        rules: 规则字典列表，每个包含 id, name, description
        knowledge: 知识条目列表，每个包含 source_id, title, content_preview
        tools: 工具字典列表，每个包含 id, name, description
        summary: 人类可读的上下文摘要
        workflow_context: 当前工作流的状态上下文（可选）
    """

    rules: list[dict[str, Any]] = field(default_factory=list)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    workflow_context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "rules": self.rules,
            "knowledge": self.knowledge,
            "tools": self.tools,
            "summary": self.summary,
        }
        if self.workflow_context is not None:
            result["workflow_context"] = self.workflow_context
        return result


@dataclass
class DecisionValidatedEvent(Event):
    """决策验证通过事件"""

    original_decision_id: str = ""
    decision_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionRejectedEvent(Event):
    """决策拒绝事件"""

    original_decision_id: str = ""
    decision_type: str = ""
    reason: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class CircuitBreakerAlertEvent(Event):
    """熔断器告警事件（阶段5新增）"""

    state: str = ""  # open, half_open, closed
    failure_count: int = 0
    message: str = ""


@dataclass
class WorkflowAdjustmentRequestedEvent(Event):
    """工作流调整请求事件（Phase 12）

    当节点失败需要重新规划时发布此事件，
    对话Agent收到后应重新规划工作流。
    """

    workflow_id: str = ""
    failed_node_id: str = ""
    failure_reason: str = ""
    suggested_action: str = "replan"
    execution_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeFailureHandledEvent(Event):
    """节点失败处理完成事件（Phase 12）

    记录节点失败处理的结果。
    """

    workflow_id: str = ""
    node_id: str = ""
    strategy: str = ""
    success: bool = False
    retry_count: int = 0
    error_message: str = ""


@dataclass
class WorkflowAbortedEvent(Event):
    """工作流终止事件（Phase 12）

    当工作流因严重错误被终止时发布。
    """

    workflow_id: str = ""
    node_id: str = ""
    reason: str = ""


@dataclass
class SubAgentCompletedEvent(Event):
    """子Agent完成事件（Phase 3）

    当子Agent执行完成时发布此事件。
    ConversationAgent 订阅此事件以恢复执行。

    属性：
    - subagent_id: 子Agent实例ID
    - subagent_type: 子Agent类型
    - session_id: 会话ID
    - success: 是否成功
    - result: 执行结果
    - error: 错误信息（失败时）
    - execution_time: 执行时间（秒）
    """

    subagent_id: str = ""
    subagent_type: str = ""
    session_id: str = ""
    success: bool = True
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time: float = 0.0

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "subagent_completed"


@dataclass
class FailureHandlingResult:
    """失败处理结果（Phase 12）

    属性：
    - success: 处理是否成功（重试成功或跳过）
    - skipped: 是否跳过了节点
    - aborted: 是否终止了工作流
    - retry_count: 实际重试次数
    - output: 成功时的输出
    - error_message: 失败时的错误信息
    """

    success: bool = False
    skipped: bool = False
    aborted: bool = False
    retry_count: int = 0
    output: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


class CoordinatorAgent:
    """协调者Agent

    职责：
    1. 管理验证规则
    2. 验证对话Agent的决策
    3. 作为EventBus中间件拦截决策
    4. 发布验证/拒绝事件
    5. 监控决策统计

    使用示例：
        agent = CoordinatorAgent(event_bus=event_bus)
        agent.add_rule(Rule(id="rule_1", name="安全规则", condition=...))
        event_bus.add_middleware(agent.as_middleware())
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        rejection_rate_threshold: float = 0.5,
        circuit_breaker_config: Any | None = None,
        context_bridge: Any | None = None,
        failure_strategy_config: dict[str, Any] | None = None,
        context_compressor: Any | None = None,
        snapshot_manager: Any | None = None,
        knowledge_retriever: Any | None = None,
    ):
        """初始化协调者Agent

        参数：
            event_bus: 事件总线（用于发布验证/拒绝事件）
            rejection_rate_threshold: 拒绝率告警阈值
            circuit_breaker_config: 熔断器配置（阶段5新增）
            context_bridge: 上下文桥接器（阶段5新增）
            failure_strategy_config: 失败处理策略配置（Phase 12）
            context_compressor: 上下文压缩器（阶段2新增）
            snapshot_manager: 快照管理器（阶段2新增）
            knowledge_retriever: 知识检索器（Phase 5 阶段2新增）
        """
        self.event_bus = event_bus
        self.rejection_rate_threshold = rejection_rate_threshold

        self._rules: list[Rule] = []
        self._statistics = {"total": 0, "passed": 0, "rejected": 0}

        # 工作流状态存储
        self.workflow_states: dict[str, dict[str, Any]] = {}
        self._is_monitoring = False
        self._current_workflow_id: str | None = None  # 用于关联节点事件

        # 阶段5新增：熔断器
        self.circuit_breaker = None
        if circuit_breaker_config:
            from src.domain.services.circuit_breaker import CircuitBreaker

            self.circuit_breaker = CircuitBreaker(circuit_breaker_config)

        # 阶段5新增：上下文桥接器
        self.context_bridge = context_bridge

        # Phase 12: 失败处理策略配置
        self.failure_strategy_config: dict[str, Any] = failure_strategy_config or {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": 3,
            "retry_delay": 1.0,
        }

        # Phase 12: 节点级别的失败策略覆盖
        self._node_failure_strategies: dict[str, FailureHandlingStrategy] = {}

        # Phase 12: 注册的 WorkflowAgent 实例
        self._workflow_agents: dict[str, Any] = {}

        # Phase 15: 简单消息日志
        self.message_log: list[dict[str, Any]] = []
        self._is_listening_simple_messages = False

        # Phase 16: 反思上下文存储
        self.reflection_contexts: dict[str, dict[str, Any]] = {}
        self._is_listening_reflections = False

        # 阶段2新增：上下文压缩器
        self.context_compressor = context_compressor
        self.snapshot_manager = snapshot_manager
        self._is_compressing_context = False
        self._compressed_contexts: dict[str, Any] = {}  # workflow_id -> CompressedContext

        # Phase 3: 子Agent管理
        from src.domain.services.sub_agent_scheduler import SubAgentRegistry

        self.subagent_registry = SubAgentRegistry()
        self.active_subagents: dict[str, dict[str, Any]] = {}
        self._is_listening_subagent_events = False

        # Phase 3: 子Agent结果存储（按会话ID分组）
        self.subagent_results: dict[str, list[dict[str, Any]]] = {}

        # Phase 4: 容器执行监控
        self.container_executions: dict[str, list[dict[str, Any]]] = {}  # workflow_id -> executions
        self.container_logs: dict[str, list[dict[str, Any]]] = {}  # container_id -> logs
        self._is_listening_container_events = False

        # Phase 5 阶段2: 知识库集成
        self.knowledge_retriever = knowledge_retriever
        self._knowledge_cache: dict[str, Any] = {}  # workflow_id -> KnowledgeReferences
        self._auto_knowledge_retrieval_enabled = False

        # Phase 1: 工具仓库
        self._tool_repository: Any | None = None

    # ==================== Phase 1: 上下文服务 ====================

    @property
    def tool_repository(self) -> Any | None:
        """获取工具仓库"""
        return self._tool_repository

    @tool_repository.setter
    def tool_repository(self, repo: Any) -> None:
        """设置工具仓库"""
        self._tool_repository = repo

    def get_context(
        self,
        user_input: str,
        workflow_id: str | None = None,
    ) -> ContextResponse:
        """获取上下文信息（同步版本）

        根据用户输入，查询规则库、知识库、工具库，返回相关上下文。

        参数：
            user_input: 用户输入文本
            workflow_id: 可选的工作流ID，用于获取工作流上下文

        返回：
            ContextResponse 包含规则、知识、工具和摘要
        """
        # 1. 获取规则
        rules_data = self._get_relevant_rules(user_input)

        # 2. 获取工具（同步，不查询知识库）
        tools_data = self._get_relevant_tools(user_input)

        # 3. 获取工作流上下文（如果有）
        workflow_context = None
        if workflow_id and workflow_id in self.workflow_states:
            workflow_context = self.workflow_states[workflow_id].copy()

        # 4. 生成摘要
        summary = self._generate_context_summary(
            rules_count=len(rules_data),
            tools_count=len(tools_data),
            knowledge_count=0,
            user_input=user_input,
        )

        return ContextResponse(
            rules=rules_data,
            knowledge=[],  # 同步版本不查询知识库
            tools=tools_data,
            summary=summary,
            workflow_context=workflow_context,
        )

    async def get_context_async(
        self,
        user_input: str,
        workflow_id: str | None = None,
    ) -> ContextResponse:
        """获取上下文信息（异步版本）

        根据用户输入，异步查询规则库、知识库、工具库，返回相关上下文。

        参数：
            user_input: 用户输入文本
            workflow_id: 可选的工作流ID，用于获取工作流上下文

        返回：
            ContextResponse 包含规则、知识、工具和摘要
        """
        # 1. 获取规则
        rules_data = self._get_relevant_rules(user_input)

        # 2. 获取知识（异步）
        knowledge_data = await self._get_relevant_knowledge_async(user_input, workflow_id)

        # 3. 获取工具
        tools_data = self._get_relevant_tools(user_input)

        # 4. 获取工作流上下文（如果有）
        workflow_context = None
        if workflow_id and workflow_id in self.workflow_states:
            workflow_context = self.workflow_states[workflow_id].copy()

        # 5. 生成摘要
        summary = self._generate_context_summary(
            rules_count=len(rules_data),
            tools_count=len(tools_data),
            knowledge_count=len(knowledge_data),
            user_input=user_input,
        )

        return ContextResponse(
            rules=rules_data,
            knowledge=knowledge_data,
            tools=tools_data,
            summary=summary,
            workflow_context=workflow_context,
        )

    def _get_relevant_rules(self, user_input: str) -> list[dict[str, Any]]:
        """获取相关规则

        返回所有规则（规则通常是通用的验证规则）

        参数：
            user_input: 用户输入

        返回：
            规则字典列表
        """
        return [
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "priority": rule.priority,
            }
            for rule in self._rules
        ]

    async def _get_relevant_knowledge_async(
        self,
        user_input: str,
        workflow_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """异步获取相关知识

        参数：
            user_input: 用户输入
            workflow_id: 工作流ID

        返回：
            知识条目列表
        """
        if not self.knowledge_retriever:
            return []

        try:
            results = await self.knowledge_retriever.retrieve_by_query(
                query=user_input,
                workflow_id=workflow_id,
                top_k=5,
            )
            return results
        except Exception:
            return []

    def _get_relevant_tools(self, user_input: str) -> list[dict[str, Any]]:
        """获取相关工具

        根据用户输入的关键词匹配工具

        参数：
            user_input: 用户输入

        返回：
            工具字典列表
        """
        if not self._tool_repository:
            return []

        try:
            # 获取所有已发布的工具
            all_tools = self._tool_repository.find_published()

            # 简单的关键词匹配
            input_lower = user_input.lower()
            keywords = input_lower.split()

            matched_tools = []
            for tool in all_tools:
                # 检查工具名称、描述或标签是否匹配关键词
                tool_text = (
                    getattr(tool, "name", "").lower()
                    + " "
                    + getattr(tool, "description", "").lower()
                    + " "
                    + " ".join(getattr(tool, "tags", []))
                ).lower()

                if any(kw in tool_text for kw in keywords) or not user_input:
                    matched_tools.append(
                        {
                            "id": getattr(tool, "id", ""),
                            "name": getattr(tool, "name", ""),
                            "description": getattr(tool, "description", ""),
                            "category": getattr(tool, "category", ""),
                        }
                    )

            return matched_tools
        except Exception:
            return []

    def _generate_context_summary(
        self,
        rules_count: int,
        tools_count: int,
        knowledge_count: int,
        user_input: str,
    ) -> str:
        """生成上下文摘要

        参数：
            rules_count: 规则数量
            tools_count: 工具数量
            knowledge_count: 知识条目数量
            user_input: 用户输入

        返回：
            摘要文本
        """
        parts = []

        if user_input:
            parts.append(f"用户输入: {user_input[:50]}{'...' if len(user_input) > 50 else ''}")

        parts.append(f"可用规则: {rules_count}")
        parts.append(f"相关工具: {tools_count}")

        if knowledge_count > 0:
            parts.append(f"知识条目: {knowledge_count}")

        return " | ".join(parts)

    def get_available_tools(self) -> list[dict[str, Any]]:
        """获取所有可用工具

        返回：
            工具字典列表
        """
        if not self._tool_repository:
            return []

        try:
            all_tools = self._tool_repository.find_all()
            return [
                {
                    "id": getattr(tool, "id", ""),
                    "name": getattr(tool, "name", ""),
                    "description": getattr(tool, "description", ""),
                    "category": getattr(tool, "category", ""),
                }
                for tool in all_tools
            ]
        except Exception:
            return []

    def find_tools_by_query(self, query: str) -> list[dict[str, Any]]:
        """按查询找到相关工具

        参数：
            query: 查询字符串（可以是关键词或标签）

        返回：
            匹配的工具列表
        """
        if not self._tool_repository:
            return []

        try:
            # 尝试按标签查找
            if hasattr(self._tool_repository, "find_by_tags"):
                tools = self._tool_repository.find_by_tags([query])
                return [
                    {
                        "id": getattr(tool, "id", ""),
                        "name": getattr(tool, "name", ""),
                        "description": getattr(tool, "description", ""),
                    }
                    for tool in tools
                ]
            return []
        except Exception:
            return []

    @property
    def rules(self) -> list[Rule]:
        """获取所有规则（按优先级排序）"""
        return sorted(self._rules, key=lambda r: r.priority)

    def add_rule(self, rule: Rule) -> None:
        """添加规则

        参数：
            rule: 要添加的规则
        """
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则

        参数：
            rule_id: 规则ID

        返回：
            是否成功移除
        """
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def validate_decision(self, decision: dict[str, Any]) -> ValidationResult:
        """验证决策

        按优先级顺序检查所有规则。

        参数：
            decision: 决策字典

        返回：
            验证结果
        """
        self._statistics["total"] += 1

        errors = []
        correction = None

        # 按优先级排序的规则
        sorted_rules = self.rules

        for rule in sorted_rules:
            try:
                if not rule.condition(decision):
                    errors.append(rule.error_message)

                    # 如果有修正函数，尝试修正
                    if rule.correction and correction is None:
                        correction = rule.correction(decision)

            except Exception as e:
                errors.append(f"规则 {rule.name} 执行异常: {str(e)}")

        is_valid = len(errors) == 0

        if is_valid:
            self._statistics["passed"] += 1
        else:
            self._statistics["rejected"] += 1

        return ValidationResult(is_valid=is_valid, errors=errors, correction=correction)

    def get_statistics(self) -> dict[str, Any]:
        """获取决策统计

        返回：
            统计字典
        """
        total = self._statistics["total"]
        rejected = self._statistics["rejected"]

        return {
            "total": total,
            "passed": self._statistics["passed"],
            "rejected": rejected,
            "rejection_rate": rejected / total if total > 0 else 0.0,
        }

    def is_rejection_rate_high(self) -> bool:
        """检查拒绝率是否过高

        返回：
            是否超过阈值
        """
        stats = self.get_statistics()
        return stats["rejection_rate"] > self.rejection_rate_threshold

    def as_middleware(self) -> Callable:
        """返回EventBus中间件函数

        返回：
            中间件函数
        """

        async def middleware(event: Event) -> Event | None:
            # 只处理决策事件
            from src.domain.agents.conversation_agent import DecisionMadeEvent

            if not isinstance(event, DecisionMadeEvent):
                return event

            # 从事件中提取决策信息
            decision = {
                "type": event.decision_type,
                "node_type": event.payload.get("node_type"),
                "config": event.payload.get("config"),
                **event.payload,
            }

            # 验证决策
            result = self.validate_decision(decision)

            if result.is_valid:
                # 发布验证通过事件
                if self.event_bus:
                    validated_event = DecisionValidatedEvent(
                        source="coordinator_agent",
                        original_decision_id=event.id,
                        decision_type=event.decision_type,
                        payload=event.payload,
                    )
                    await self.event_bus.publish(validated_event)

                return event  # 放行

            else:
                # 发布拒绝事件
                if self.event_bus:
                    rejected_event = DecisionRejectedEvent(
                        source="coordinator_agent",
                        original_decision_id=event.id,
                        decision_type=event.decision_type,
                        reason="; ".join(result.errors),
                        errors=result.errors,
                    )
                    await self.event_bus.publish(rejected_event)

                return None  # 阻止传播

        return middleware

    # ==================== 状态监控功能 ====================

    def start_monitoring(self) -> None:
        """启动工作流状态监控

        订阅工作流相关事件，维护状态快照。
        如果启用了上下文压缩，会同时压缩事件数据。
        """
        if self._is_monitoring:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for monitoring")

        # 延迟导入避免循环依赖
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
            WorkflowExecutionStartedEvent,
        )

        # 根据是否启用压缩选择处理器
        if self._is_compressing_context:
            workflow_started_handler = self._handle_workflow_started_with_compression
            node_execution_handler = self._handle_node_execution_with_compression
        else:
            workflow_started_handler = self._handle_workflow_started
            node_execution_handler = self._handle_node_execution

        # 订阅工作流事件
        self.event_bus.subscribe(WorkflowExecutionStartedEvent, workflow_started_handler)
        self.event_bus.subscribe(WorkflowExecutionCompletedEvent, self._handle_workflow_completed)
        self.event_bus.subscribe(NodeExecutionEvent, node_execution_handler)

        self._is_monitoring = True

    def stop_monitoring(self) -> None:
        """停止工作流状态监控

        取消所有事件订阅。
        """
        if not self._is_monitoring:
            return

        if not self.event_bus:
            return

        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
            WorkflowExecutionStartedEvent,
        )

        self.event_bus.unsubscribe(WorkflowExecutionStartedEvent, self._handle_workflow_started)
        self.event_bus.unsubscribe(WorkflowExecutionCompletedEvent, self._handle_workflow_completed)
        self.event_bus.unsubscribe(NodeExecutionEvent, self._handle_node_execution)

        self._is_monitoring = False

    async def _handle_workflow_started(self, event: Any) -> None:
        """处理工作流开始事件"""
        workflow_id = event.workflow_id

        self.workflow_states[workflow_id] = {
            "workflow_id": workflow_id,
            "status": "running",
            "node_count": event.node_count,
            "started_at": datetime.now(),
            "completed_at": None,
            "result": None,
            # 节点跟踪
            "executed_nodes": [],
            "running_nodes": [],
            "failed_nodes": [],
            "node_inputs": {},
            "node_outputs": {},
            "node_errors": {},
        }

        # 记录当前工作流ID（用于关联节点事件）
        self._current_workflow_id = workflow_id

    async def _handle_workflow_completed(self, event: Any) -> None:
        """处理工作流完成事件"""
        workflow_id = event.workflow_id

        if workflow_id in self.workflow_states:
            self.workflow_states[workflow_id]["status"] = event.status
            self.workflow_states[workflow_id]["completed_at"] = datetime.now()
            self.workflow_states[workflow_id]["result"] = event.result

        # 如果启用了压缩，更新上下文
        if self._is_compressing_context:
            self._compress_and_save_context(
                workflow_id=workflow_id,
                source_type="execution",
                raw_data={
                    "workflow_status": event.status,
                    "result": event.result,
                },
            )

    async def _handle_node_execution(self, event: Any) -> None:
        """处理节点执行事件"""
        node_id = event.node_id
        status = event.status

        # 确定工作流ID（从事件或当前追踪的工作流）
        workflow_id = getattr(event, "workflow_id", None) or self._current_workflow_id

        if not workflow_id or workflow_id not in self.workflow_states:
            return

        state = self.workflow_states[workflow_id]

        # 记录输入（如果事件包含）
        if hasattr(event, "inputs") and event.inputs:
            state["node_inputs"][node_id] = event.inputs

        if status == "running":
            # 节点开始运行
            if node_id not in state["running_nodes"]:
                state["running_nodes"].append(node_id)

        elif status == "completed":
            # 节点完成
            if node_id in state["running_nodes"]:
                state["running_nodes"].remove(node_id)
            if node_id not in state["executed_nodes"]:
                state["executed_nodes"].append(node_id)
            if event.result:
                state["node_outputs"][node_id] = event.result

        elif status == "failed":
            # 节点失败
            if node_id in state["running_nodes"]:
                state["running_nodes"].remove(node_id)
            if node_id not in state["failed_nodes"]:
                state["failed_nodes"].append(node_id)
            if event.error:
                state["node_errors"][node_id] = event.error

    def get_workflow_state(self, workflow_id: str) -> dict[str, Any] | None:
        """获取工作流状态快照

        参数：
            workflow_id: 工作流ID

        返回：
            状态快照字典，如果不存在返回None
        """
        state = self.workflow_states.get(workflow_id)
        if state:
            return state.copy()
        return None

    def get_all_workflow_states(self) -> dict[str, dict[str, Any]]:
        """获取所有工作流状态

        返回：
            工作流ID到状态的映射
        """
        return {wf_id: state.copy() for wf_id, state in self.workflow_states.items()}

    def get_system_status(self) -> dict[str, Any]:
        """获取系统状态摘要

        返回：
            系统状态摘要
        """
        total = len(self.workflow_states)
        running = sum(1 for s in self.workflow_states.values() if s["status"] == "running")
        completed = sum(1 for s in self.workflow_states.values() if s["status"] == "completed")
        failed = sum(1 for s in self.workflow_states.values() if s["status"] == "failed")

        # 计算活跃节点数
        active_nodes = sum(len(s["running_nodes"]) for s in self.workflow_states.values())

        return {
            "total_workflows": total,
            "running_workflows": running,
            "completed_workflows": completed,
            "failed_workflows": failed,
            "active_nodes": active_nodes,
            "decision_statistics": self.get_statistics(),
        }

    # ==================== 阶段5：熔断器与上下文桥接 ====================

    async def check_circuit_breaker_state(self) -> None:
        """检查熔断器状态并发布告警事件

        如果熔断器打开，发布告警事件。
        """
        if not self.circuit_breaker:
            return

        if self.circuit_breaker.is_open and self.event_bus:
            metrics = self.circuit_breaker.get_metrics()
            alert = CircuitBreakerAlertEvent(
                source="coordinator_agent",
                state="open",
                failure_count=metrics["failure_count"],
                message="熔断器已打开，系统处于保护状态",
            )
            await self.event_bus.publish(alert)

    async def request_context_bridge(
        self,
        source_workflow_id: str,
        target_workflow_id: str,
        keys: list[str],
    ) -> dict[str, Any]:
        """请求上下文桥接

        代表目标工作流请求源工作流的数据。

        参数：
            source_workflow_id: 源工作流ID
            target_workflow_id: 目标工作流ID
            keys: 请求的数据键列表

        返回：
            桥接的数据

        异常：
            ValueError: 如果没有配置上下文桥接器
        """
        if not self.context_bridge:
            raise ValueError("未配置上下文桥接器")

        from src.domain.services.context_bridge_enhanced import BridgeRequest

        request = BridgeRequest(
            source_workflow_id=source_workflow_id,
            target_workflow_id=target_workflow_id,
            requested_keys=keys,
            requester=f"coordinator_{target_workflow_id}",
        )

        result = await self.context_bridge.transfer_with_request(request)

        if result.success:
            # 合并所有请求的键的数据
            merged_data = {}
            for key in keys:
                if key in result.transferred_data:
                    merged_data.update(result.transferred_data[key])
            return merged_data if merged_data else result.transferred_data

        raise ValueError(f"桥接失败: {result.error}")

    # ==================== Phase 12: 失败处理策略 ====================

    def set_node_failure_strategy(self, node_id: str, strategy: FailureHandlingStrategy) -> None:
        """为特定节点设置失败处理策略

        参数：
            node_id: 节点ID
            strategy: 失败处理策略
        """
        self._node_failure_strategies[node_id] = strategy

    def get_node_failure_strategy(self, node_id: str) -> FailureHandlingStrategy:
        """获取节点的失败处理策略

        如果节点没有特定策略，返回默认策略。

        参数：
            node_id: 节点ID

        返回：
            失败处理策略
        """
        if node_id in self._node_failure_strategies:
            return self._node_failure_strategies[node_id]
        return self.failure_strategy_config["default_strategy"]

    def register_workflow_agent(self, workflow_id: str, agent: Any) -> None:
        """注册 WorkflowAgent 实例

        用于在失败处理时调用重试。

        参数：
            workflow_id: 工作流ID
            agent: WorkflowAgent 实例
        """
        self._workflow_agents[workflow_id] = agent

    async def handle_node_failure(
        self,
        workflow_id: str,
        node_id: str,
        error_code: Any,
        error_message: str,
    ) -> FailureHandlingResult:
        """处理节点失败

        根据配置的策略处理节点执行失败：
        - RETRY: 重试执行节点
        - SKIP: 跳过节点继续执行
        - ABORT: 终止工作流
        - REPLAN: 请求重新规划

        参数：
            workflow_id: 工作流ID
            node_id: 失败的节点ID
            error_code: 错误码
            error_message: 错误信息

        返回：
            失败处理结果
        """

        from src.domain.services.execution_result import ErrorCode

        strategy = self.get_node_failure_strategy(node_id)

        # SKIP 策略
        if strategy == FailureHandlingStrategy.SKIP:
            return await self._handle_skip(workflow_id, node_id, error_message)

        # ABORT 策略
        if strategy == FailureHandlingStrategy.ABORT:
            return await self._handle_abort(workflow_id, node_id, error_message)

        # REPLAN 策略
        if strategy == FailureHandlingStrategy.REPLAN:
            return await self._handle_replan(workflow_id, node_id, error_message)

        # RETRY 策略（默认）
        if strategy == FailureHandlingStrategy.RETRY:
            # 检查错误是否可重试
            if isinstance(error_code, ErrorCode) and not error_code.is_retryable():
                # 不可重试的错误，根据默认行为处理
                return FailureHandlingResult(
                    success=False,
                    error_message=f"Non-retryable error: {error_message}",
                )

            return await self._handle_retry(workflow_id, node_id, error_message)

        # 未知策略，返回失败
        return FailureHandlingResult(
            success=False,
            error_message=f"Unknown strategy: {strategy}",
        )

    async def _handle_retry(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理重试策略"""
        import asyncio

        max_retries = self.failure_strategy_config.get("max_retries", 3)
        retry_delay = self.failure_strategy_config.get("retry_delay", 1.0)

        agent = self._workflow_agents.get(workflow_id)
        if not agent:
            return FailureHandlingResult(
                success=False,
                error_message=f"No WorkflowAgent registered for {workflow_id}",
            )

        retry_count = 0
        while retry_count < max_retries:
            await asyncio.sleep(retry_delay)

            result = await agent.execute_node_with_result(node_id)

            if result.success:
                # 更新执行上下文
                self._update_context_after_success(workflow_id, node_id, result.output)

                # 发布成功事件
                if self.event_bus:
                    event = NodeFailureHandledEvent(
                        source="coordinator_agent",
                        workflow_id=workflow_id,
                        node_id=node_id,
                        strategy="retry",
                        success=True,
                        retry_count=retry_count + 1,
                    )
                    await self.event_bus.publish(event)

                return FailureHandlingResult(
                    success=True,
                    retry_count=retry_count + 1,
                    output=result.output,
                )

            retry_count += 1

        # 重试耗尽
        return FailureHandlingResult(
            success=False,
            retry_count=retry_count,
            error_message=f"Max retries ({max_retries}) exceeded",
        )

    async def _handle_skip(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理跳过策略"""
        # 更新上下文：标记节点为已跳过
        if workflow_id in self.workflow_states:
            state = self.workflow_states[workflow_id]
            if "skipped_nodes" not in state:
                state["skipped_nodes"] = []
            if node_id not in state["skipped_nodes"]:
                state["skipped_nodes"].append(node_id)
            # 从失败节点中移除
            if node_id in state.get("failed_nodes", []):
                state["failed_nodes"].remove(node_id)

        # 发布事件
        if self.event_bus:
            event = NodeFailureHandledEvent(
                source="coordinator_agent",
                workflow_id=workflow_id,
                node_id=node_id,
                strategy="skip",
                success=True,
            )
            await self.event_bus.publish(event)

        return FailureHandlingResult(
            success=True,
            skipped=True,
        )

    async def _handle_abort(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理终止策略"""
        # 更新上下文
        if workflow_id in self.workflow_states:
            self.workflow_states[workflow_id]["status"] = "aborted"

        # 发布终止事件
        if self.event_bus:
            event = WorkflowAbortedEvent(
                source="coordinator_agent",
                workflow_id=workflow_id,
                node_id=node_id,
                reason=error_message,
            )
            await self.event_bus.publish(event)

        return FailureHandlingResult(
            success=False,
            aborted=True,
            error_message=error_message,
        )

    async def _handle_replan(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理重新规划策略"""
        # 获取执行上下文
        execution_context = {}
        if workflow_id in self.workflow_states:
            state = self.workflow_states[workflow_id]
            execution_context = {
                "executed_nodes": state.get("executed_nodes", []),
                "node_outputs": state.get("node_outputs", {}),
                "failed_nodes": state.get("failed_nodes", []),
            }

        # 发布重新规划事件
        if self.event_bus:
            event = WorkflowAdjustmentRequestedEvent(
                source="coordinator_agent",
                workflow_id=workflow_id,
                failed_node_id=node_id,
                failure_reason=error_message,
                suggested_action="replan",
                execution_context=execution_context,
            )
            await self.event_bus.publish(event)

        return FailureHandlingResult(
            success=False,
            error_message=f"Replan requested: {error_message}",
        )

    def _update_context_after_success(
        self, workflow_id: str, node_id: str, output: dict[str, Any]
    ) -> None:
        """重试成功后更新执行上下文"""
        if workflow_id not in self.workflow_states:
            return

        state = self.workflow_states[workflow_id]

        # 添加到已执行节点
        if node_id not in state.get("executed_nodes", []):
            if "executed_nodes" not in state:
                state["executed_nodes"] = []
            state["executed_nodes"].append(node_id)

        # 从失败节点中移除
        if node_id in state.get("failed_nodes", []):
            state["failed_nodes"].remove(node_id)

        # 保存输出
        if "node_outputs" not in state:
            state["node_outputs"] = {}
        state["node_outputs"][node_id] = output

    # === Phase 15: 简单消息监听 ===

    def start_simple_message_listening(self) -> None:
        """开始监听简单消息事件

        订阅 SimpleMessageEvent，将消息记录到 message_log。
        """
        if self._is_listening_simple_messages:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for simple message listening")

        from src.domain.agents.conversation_agent import SimpleMessageEvent

        self.event_bus.subscribe(SimpleMessageEvent, self._handle_simple_message_event)
        self._is_listening_simple_messages = True

    def stop_simple_message_listening(self) -> None:
        """停止监听简单消息事件"""
        if not self._is_listening_simple_messages:
            return

        if not self.event_bus:
            return

        from src.domain.agents.conversation_agent import SimpleMessageEvent

        self.event_bus.unsubscribe(SimpleMessageEvent, self._handle_simple_message_event)
        self._is_listening_simple_messages = False

    async def _handle_simple_message_event(self, event: Any) -> None:
        """处理简单消息事件

        将消息记录到 message_log。

        参数：
            event: SimpleMessageEvent 实例
        """
        self.message_log.append(
            {
                "user_input": event.user_input,
                "response": event.response,
                "intent": event.intent,
                "confidence": event.confidence,
                "session_id": event.session_id,
                "timestamp": event.timestamp,
            }
        )

    def get_message_statistics(self) -> dict[str, Any]:
        """获取消息统计

        返回：
            包含消息统计的字典：
            - total_messages: 总消息数
            - by_intent: 按意图分类的消息数
        """
        by_intent: dict[str, int] = {}

        for msg in self.message_log:
            intent = msg.get("intent", "unknown")
            by_intent[intent] = by_intent.get(intent, 0) + 1

        return {
            "total_messages": len(self.message_log),
            "by_intent": by_intent,
        }

    # === Phase 16: 反思上下文监听 ===

    def start_reflection_listening(self) -> None:
        """开始监听反思事件

        订阅 WorkflowReflectionCompletedEvent，记录反思结果到上下文。
        如果启用了上下文压缩，会同时压缩反思数据。
        """
        if self._is_listening_reflections:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for reflection listening")

        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        # 根据是否启用压缩选择处理器
        if self._is_compressing_context:
            handler = self._handle_reflection_event_with_compression
        else:
            handler = self._handle_reflection_event

        self.event_bus.subscribe(WorkflowReflectionCompletedEvent, handler)
        self._is_listening_reflections = True

    def stop_reflection_listening(self) -> None:
        """停止监听反思事件"""
        if not self._is_listening_reflections:
            return

        if not self.event_bus:
            return

        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        self.event_bus.unsubscribe(WorkflowReflectionCompletedEvent, self._handle_reflection_event)
        self._is_listening_reflections = False

    async def _handle_reflection_event(self, event: Any) -> None:
        """处理反思事件

        将反思结果记录到上下文，包括目标、规则、错误、建议。

        参数：
            event: WorkflowReflectionCompletedEvent 实例
        """
        workflow_id = event.workflow_id

        # 创建反思记录
        reflection_record = {
            "assessment": event.assessment,
            "should_retry": event.should_retry,
            "confidence": event.confidence,
            "timestamp": event.timestamp,
        }

        if workflow_id not in self.reflection_contexts:
            # 首次反思，创建上下文
            self.reflection_contexts[workflow_id] = {
                "workflow_id": workflow_id,
                "assessment": event.assessment,
                "should_retry": event.should_retry,
                "confidence": event.confidence,
                "timestamp": event.timestamp,
                "history": [reflection_record],
            }
        else:
            # 追加历史记录
            context = self.reflection_contexts[workflow_id]
            context["assessment"] = event.assessment
            context["should_retry"] = event.should_retry
            context["confidence"] = event.confidence
            context["timestamp"] = event.timestamp
            context["history"].append(reflection_record)

    def get_reflection_summary(self, workflow_id: str) -> dict[str, Any] | None:
        """获取工作流的反思摘要

        参数：
            workflow_id: 工作流ID

        返回：
            反思摘要字典，如果不存在返回None
        """
        context = self.reflection_contexts.get(workflow_id)
        if not context:
            return None

        return {
            "workflow_id": workflow_id,
            "assessment": context.get("assessment", ""),
            "should_retry": context.get("should_retry", False),
            "confidence": context.get("confidence", 0.0),
            "total_reflections": len(context.get("history", [])),
            "last_updated": context.get("timestamp"),
        }

    # === 阶段2: 上下文压缩 ===

    def start_context_compression(self) -> None:
        """开始上下文压缩

        启用后，Coordinator 会在收到反思事件或节点执行事件时
        自动调用压缩器更新上下文快照。
        """
        if self._is_compressing_context:
            return

        if not self.context_compressor:
            from src.domain.services.context_compressor import ContextCompressor

            self.context_compressor = ContextCompressor()

        if not self.snapshot_manager:
            from src.domain.services.context_compressor import ContextSnapshotManager

            self.snapshot_manager = ContextSnapshotManager()

        self._is_compressing_context = True

    def stop_context_compression(self) -> None:
        """停止上下文压缩"""
        self._is_compressing_context = False

    def _compress_and_save_context(
        self,
        workflow_id: str,
        source_type: str,
        raw_data: dict[str, Any],
    ) -> None:
        """压缩并保存上下文

        参数：
            workflow_id: 工作流ID
            source_type: 来源类型 (execution/reflection/conversation)
            raw_data: 原始数据
        """
        if not self._is_compressing_context:
            return

        if not self.context_compressor or not self.snapshot_manager:
            return

        from src.domain.services.context_compressor import CompressionInput

        input_data = CompressionInput(
            source_type=source_type,
            workflow_id=workflow_id,
            raw_data=raw_data,
        )

        # 获取现有上下文
        existing = self._compressed_contexts.get(workflow_id)

        if existing:
            # 增量更新
            new_context = self.context_compressor.merge(existing, input_data)
        else:
            # 全新压缩
            new_context = self.context_compressor.compress(input_data)

        # 更新缓存
        self._compressed_contexts[workflow_id] = new_context

        # 保存快照
        self.snapshot_manager.save_snapshot(new_context)

    def get_compressed_context(self, workflow_id: str) -> Any:
        """获取压缩后的上下文

        对话 Agent 可以使用此方法获取工作流的压缩上下文。

        参数：
            workflow_id: 工作流ID

        返回：
            CompressedContext 实例，如果不存在返回None
        """
        # 优先从缓存获取
        if workflow_id in self._compressed_contexts:
            return self._compressed_contexts[workflow_id]

        # 从快照管理器获取
        if self.snapshot_manager:
            return self.snapshot_manager.get_latest_snapshot(workflow_id)

        return None

    def get_context_summary_text(self, workflow_id: str) -> str | None:
        """获取上下文的摘要文本

        返回人类可读的摘要文本，适合作为对话 Agent 的上下文。

        参数：
            workflow_id: 工作流ID

        返回：
            摘要文本，如果不存在返回None
        """
        context = self.get_compressed_context(workflow_id)
        if context and hasattr(context, "to_summary_text"):
            return context.to_summary_text()
        return None

    async def _handle_workflow_started_with_compression(self, event: Any) -> None:
        """处理工作流开始事件（带压缩）"""
        await self._handle_workflow_started(event)

        # 压缩初始上下文
        if self._is_compressing_context:
            workflow_id = event.workflow_id
            self._compress_and_save_context(
                workflow_id=workflow_id,
                source_type="execution",
                raw_data={
                    "workflow_status": "running",
                    "node_count": event.node_count,
                },
            )

    async def _handle_node_execution_with_compression(self, event: Any) -> None:
        """处理节点执行事件（带压缩）"""
        await self._handle_node_execution(event)

        # 压缩节点执行结果
        if self._is_compressing_context:
            workflow_id = getattr(event, "workflow_id", None) or self._current_workflow_id
            if workflow_id:
                raw_data = {
                    "executed_nodes": [
                        {
                            "node_id": event.node_id,
                            "status": event.status,
                            "output": getattr(event, "result", None),
                            "error": getattr(event, "error", None),
                        }
                    ],
                    "workflow_status": "running",
                }

                # 如果有工作流状态，补充进度信息
                if workflow_id in self.workflow_states:
                    state = self.workflow_states[workflow_id]
                    executed = len(state.get("executed_nodes", []))
                    total = state.get("node_count", 0)
                    if total > 0:
                        raw_data["progress"] = executed / total

                    # 如果有错误，添加到错误列表
                    if event.status == "failed" and getattr(event, "error", None):
                        raw_data["errors"] = [
                            {
                                "node_id": event.node_id,
                                "error": event.error,
                                "retryable": True,
                            }
                        ]

                self._compress_and_save_context(
                    workflow_id=workflow_id,
                    source_type="execution",
                    raw_data=raw_data,
                )

    async def _handle_reflection_event_with_compression(self, event: Any) -> None:
        """处理反思事件（带压缩）"""
        await self._handle_reflection_event(event)

        # 压缩反思结果
        if self._is_compressing_context:
            workflow_id = event.workflow_id
            self._compress_and_save_context(
                workflow_id=workflow_id,
                source_type="reflection",
                raw_data={
                    "assessment": event.assessment,
                    "should_retry": getattr(event, "should_retry", False),
                    "confidence": event.confidence,
                    "recommendations": getattr(event, "recommendations", []),
                },
            )

    # ==================== Phase 3: 子Agent管理 ====================

    def register_subagent_type(self, agent_type: Any, agent_class: type) -> None:
        """注册子Agent类型

        参数：
            agent_type: SubAgentType 枚举值
            agent_class: 子Agent类
        """
        self.subagent_registry.register(agent_type, agent_class)

    def get_registered_subagent_types(self) -> list[Any]:
        """获取已注册的子Agent类型列表

        返回：
            SubAgentType 列表
        """
        return self.subagent_registry.list_types()

    def start_subagent_listener(self) -> None:
        """启动子Agent事件监听器

        订阅 SpawnSubAgentEvent 以处理子Agent生成请求。
        """
        if self._is_listening_subagent_events:
            return

        if self.event_bus:
            from src.domain.agents.conversation_agent import SpawnSubAgentEvent

            self.event_bus.subscribe(SpawnSubAgentEvent, self._handle_spawn_subagent_event_wrapper)
            self._is_listening_subagent_events = True

    async def _handle_spawn_subagent_event_wrapper(self, event: Any) -> None:
        """SpawnSubAgentEvent 处理器包装器"""
        await self.handle_spawn_subagent_event(event)

    async def handle_spawn_subagent_event(self, event: Any) -> Any:
        """处理子Agent生成事件

        参数：
            event: SpawnSubAgentEvent 事件

        返回：
            SubAgentResult 执行结果
        """
        return await self.execute_subagent(
            subagent_type=event.subagent_type,
            task_payload=event.task_payload,
            context=event.context_snapshot,
            session_id=event.session_id,
        )

    async def execute_subagent(
        self,
        subagent_type: str,
        task_payload: dict[str, Any],
        context: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> Any:
        """执行子Agent任务

        参数：
            subagent_type: 子Agent类型（字符串）
            task_payload: 任务负载
            context: 执行上下文
            session_id: 会话ID

        返回：
            SubAgentResult 执行结果
        """
        from datetime import datetime

        from src.domain.services.sub_agent_scheduler import (
            SubAgentResult,
            SubAgentType,
        )

        # 转换类型字符串为枚举
        try:
            agent_type_enum = SubAgentType(subagent_type)
        except ValueError:
            return SubAgentResult(
                agent_id="",
                agent_type=subagent_type,
                success=False,
                error=f"Unknown subagent type: {subagent_type}",
            )

        # 创建子Agent实例
        agent = self.subagent_registry.create_instance(agent_type_enum)
        if agent is None:
            return SubAgentResult(
                agent_id="",
                agent_type=subagent_type,
                success=False,
                error=f"SubAgent type not registered: {subagent_type}",
            )

        subagent_id = agent.agent_id

        # 记录活跃子Agent
        self.active_subagents[subagent_id] = {
            "type": subagent_type,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "session_id": session_id,
        }

        try:
            # 执行子Agent
            result = await agent.execute(task_payload, context or {})

            # 更新状态
            self.active_subagents[subagent_id]["status"] = (
                "completed" if result.success else "failed"
            )
            self.active_subagents[subagent_id]["completed_at"] = datetime.now().isoformat()

            # 存储结果到会话
            if session_id:
                if session_id not in self.subagent_results:
                    self.subagent_results[session_id] = []
                self.subagent_results[session_id].append(
                    {
                        "subagent_id": subagent_id,
                        "subagent_type": subagent_type,
                        "success": result.success,
                        "result": result.output,
                        "error": result.error,
                        "execution_time": result.execution_time,
                    }
                )

            # 发布完成事件
            if self.event_bus:
                self.event_bus.publish(
                    SubAgentCompletedEvent(
                        subagent_id=subagent_id,
                        subagent_type=subagent_type,
                        session_id=session_id,
                        success=result.success,
                        result=result.output,
                        error=result.error,
                        execution_time=result.execution_time,
                        source="coordinator_agent",
                    )
                )

            # 清理已完成的子Agent
            del self.active_subagents[subagent_id]

            return result

        except Exception as e:
            # 记录失败
            self.active_subagents[subagent_id]["status"] = "failed"
            self.active_subagents[subagent_id]["error"] = str(e)

            # 发布失败事件
            if self.event_bus:
                self.event_bus.publish(
                    SubAgentCompletedEvent(
                        subagent_id=subagent_id,
                        subagent_type=subagent_type,
                        session_id=session_id,
                        success=False,
                        error=str(e),
                        source="coordinator_agent",
                    )
                )

            # 清理
            del self.active_subagents[subagent_id]

            return SubAgentResult(
                agent_id=subagent_id,
                agent_type=subagent_type,
                success=False,
                error=str(e),
            )

    def get_subagent_status(self, subagent_id: str) -> dict[str, Any] | None:
        """获取子Agent状态

        参数：
            subagent_id: 子Agent实例ID

        返回：
            状态字典，如果不存在返回None
        """
        return self.active_subagents.get(subagent_id)

    def get_session_subagent_results(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话的子Agent执行结果列表

        参数：
            session_id: 会话ID

        返回：
            该会话的所有子Agent执行结果列表，如果不存在返回空列表
        """
        return self.subagent_results.get(session_id, [])

    # ==================== Phase 4: 容器执行监控 ====================

    def start_container_execution_listening(self) -> None:
        """启动容器执行事件监听

        订阅容器执行相关事件。
        """
        if self._is_listening_container_events:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for container execution listening")

        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
            ContainerExecutionStartedEvent,
            ContainerLogEvent,
        )

        self.event_bus.subscribe(ContainerExecutionStartedEvent, self._handle_container_started)
        self.event_bus.subscribe(ContainerExecutionCompletedEvent, self._handle_container_completed)
        self.event_bus.subscribe(ContainerLogEvent, self._handle_container_log)

        self._is_listening_container_events = True

    def stop_container_execution_listening(self) -> None:
        """停止容器执行事件监听"""
        if not self._is_listening_container_events:
            return

        if not self.event_bus:
            return

        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
            ContainerExecutionStartedEvent,
            ContainerLogEvent,
        )

        self.event_bus.unsubscribe(ContainerExecutionStartedEvent, self._handle_container_started)
        self.event_bus.unsubscribe(
            ContainerExecutionCompletedEvent, self._handle_container_completed
        )
        self.event_bus.unsubscribe(ContainerLogEvent, self._handle_container_log)

        self._is_listening_container_events = False

    async def _handle_container_started(self, event: Any) -> None:
        """处理容器执行开始事件"""
        workflow_id = event.workflow_id

        if workflow_id not in self.container_executions:
            self.container_executions[workflow_id] = []

        self.container_executions[workflow_id].append(
            {
                "container_id": event.container_id,
                "node_id": event.node_id,
                "image": event.image,
                "status": "running",
                "started_at": event.timestamp,
            }
        )

    async def _handle_container_completed(self, event: Any) -> None:
        """处理容器执行完成事件"""
        workflow_id = event.workflow_id

        if workflow_id not in self.container_executions:
            self.container_executions[workflow_id] = []

        self.container_executions[workflow_id].append(
            {
                "container_id": event.container_id,
                "node_id": event.node_id,
                "success": event.success,
                "exit_code": event.exit_code,
                "stdout": event.stdout,
                "stderr": event.stderr,
                "execution_time": event.execution_time,
                "status": "completed" if event.success else "failed",
                "completed_at": event.timestamp,
            }
        )

    async def _handle_container_log(self, event: Any) -> None:
        """处理容器日志事件"""
        container_id = event.container_id

        if container_id not in self.container_logs:
            self.container_logs[container_id] = []

        self.container_logs[container_id].append(
            {
                "level": event.log_level,
                "message": event.message,
                "timestamp": event.timestamp,
                "node_id": event.node_id,
            }
        )

    def get_workflow_container_executions(self, workflow_id: str) -> list[dict[str, Any]]:
        """获取工作流的容器执行记录

        参数：
            workflow_id: 工作流ID

        返回：
            容器执行记录列表
        """
        return self.container_executions.get(workflow_id, [])

    def get_container_logs(self, container_id: str) -> list[dict[str, Any]]:
        """获取容器日志

        参数：
            container_id: 容器ID

        返回：
            日志列表
        """
        return self.container_logs.get(container_id, [])

    def get_container_execution_statistics(self) -> dict[str, Any]:
        """获取容器执行统计

        返回：
            包含执行统计的字典
        """
        total = 0
        successful = 0
        failed = 0
        total_time = 0.0

        for _workflow_id, executions in self.container_executions.items():
            for execution in executions:
                # 兼容两种格式：有 status 字段或只有 success 字段
                status = execution.get("status")
                has_result = status in ["completed", "failed"] or "success" in execution

                if has_result:
                    total += 1
                    if execution.get("success", False):
                        successful += 1
                    else:
                        failed += 1
                    total_time += execution.get("execution_time", 0.0)

        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "total_execution_time": total_time,
        }

    # ==================== Phase 5 阶段2: 知识库集成 ====================

    async def retrieve_knowledge(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> Any:
        """按查询检索知识

        参数：
            query: 查询文本
            workflow_id: 工作流ID（可选，用于过滤和缓存）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        if not self.knowledge_retriever:
            return refs

        # 检索知识
        results = await self.knowledge_retriever.retrieve_by_query(
            query=query,
            workflow_id=workflow_id,
            top_k=top_k,
        )

        # 转换为 KnowledgeReference
        for result in results:
            ref = KnowledgeReference(
                source_id=result.get("source_id", ""),
                title=result.get("title", ""),
                content_preview=result.get("content_preview", ""),
                relevance_score=result.get("relevance_score", 0.0),
                document_id=result.get("document_id"),
                source_type=result.get("source_type", "knowledge_base"),
            )
            refs.add(ref)

        # 如果指定了 workflow_id，缓存结果
        if workflow_id:
            self._knowledge_cache[workflow_id] = refs

        return refs

    async def retrieve_knowledge_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> Any:
        """按错误类型检索解决方案

        参数：
            error_type: 错误类型
            error_message: 错误消息（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        if not self.knowledge_retriever:
            return refs

        # 检索错误相关知识
        results = await self.knowledge_retriever.retrieve_by_error(
            error_type=error_type,
            error_message=error_message,
            top_k=top_k,
        )

        # 转换为 KnowledgeReference
        for result in results:
            ref = KnowledgeReference(
                source_id=result.get("source_id", ""),
                title=result.get("title", ""),
                content_preview=result.get("content_preview", ""),
                relevance_score=result.get("relevance_score", 0.0),
                source_type=result.get("source_type", "error_solution"),
            )
            refs.add(ref)

        return refs

    async def retrieve_knowledge_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> Any:
        """按目标检索相关知识

        参数：
            goal_text: 目标描述文本
            workflow_id: 工作流ID（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        if not self.knowledge_retriever:
            return refs

        # 检索目标相关知识
        results = await self.knowledge_retriever.retrieve_by_goal(
            goal_text=goal_text,
            workflow_id=workflow_id,
            top_k=top_k,
        )

        # 转换为 KnowledgeReference
        for result in results:
            ref = KnowledgeReference(
                source_id=result.get("source_id", ""),
                title=result.get("title", ""),
                content_preview=result.get("content_preview", ""),
                relevance_score=result.get("relevance_score", 0.0),
                document_id=result.get("document_id"),
                source_type=result.get("source_type", "goal_related"),
            )
            refs.add(ref)

        return refs

    def get_cached_knowledge(self, workflow_id: str) -> Any:
        """获取缓存的知识引用

        参数：
            workflow_id: 工作流ID

        返回：
            KnowledgeReferences 或 None
        """
        return self._knowledge_cache.get(workflow_id)

    def clear_cached_knowledge(self, workflow_id: str) -> None:
        """清除缓存的知识引用

        参数：
            workflow_id: 工作流ID
        """
        if workflow_id in self._knowledge_cache:
            del self._knowledge_cache[workflow_id]

    async def enrich_context_with_knowledge(
        self,
        workflow_id: str,
        goal: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """根据目标和错误丰富上下文

        自动检索与目标和错误相关的知识，并将结果附加到上下文中。

        参数：
            workflow_id: 工作流ID
            goal: 任务目标（可选）
            errors: 错误列表（可选），每个错误包含 error_type 和 message

        返回：
            包含 knowledge_references 的上下文字典
        """
        from src.domain.services.knowledge_reference import KnowledgeReferences

        all_refs = KnowledgeReferences()

        # 基于目标检索知识
        if goal and self.knowledge_retriever:
            goal_refs = await self.retrieve_knowledge_by_goal(
                goal_text=goal,
                workflow_id=workflow_id,
            )
            all_refs = all_refs.merge(goal_refs)

        # 基于错误检索知识
        if errors and self.knowledge_retriever:
            for error in errors:
                error_type = error.get("error_type", "")
                error_message = error.get("message", "")
                if error_type:
                    error_refs = await self.retrieve_knowledge_by_error(
                        error_type=error_type,
                        error_message=error_message,
                    )
                    all_refs = all_refs.merge(error_refs)

        # 去重
        all_refs = all_refs.deduplicate()

        # 缓存结果
        self._knowledge_cache[workflow_id] = all_refs

        # 返回包含知识引用的上下文
        return {
            "workflow_id": workflow_id,
            "knowledge_references": all_refs.to_dict_list(),
        }

    async def inject_knowledge_to_context(
        self,
        workflow_id: str,
        goal: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        """向现有压缩上下文注入知识

        参数：
            workflow_id: 工作流ID
            goal: 任务目标（可选）
            errors: 错误列表（可选）
        """
        # 检索知识
        enriched = await self.enrich_context_with_knowledge(
            workflow_id=workflow_id,
            goal=goal,
            errors=errors,
        )

        # 如果有压缩上下文，注入知识引用
        if workflow_id in self._compressed_contexts:
            ctx = self._compressed_contexts[workflow_id]
            if hasattr(ctx, "knowledge_references"):
                # 合并现有和新的知识引用
                existing_refs = ctx.knowledge_references or []
                new_refs = enriched.get("knowledge_references", [])

                # 去重合并（按 source_id）
                seen_ids = {r.get("source_id") for r in existing_refs}
                for ref in new_refs:
                    if ref.get("source_id") not in seen_ids:
                        existing_refs.append(ref)
                        seen_ids.add(ref.get("source_id"))

                ctx.knowledge_references = existing_refs

    def get_knowledge_enhanced_summary(self, workflow_id: str) -> str | None:
        """获取知识增强的上下文摘要

        返回包含知识引用信息的人类可读摘要。

        参数：
            workflow_id: 工作流ID

        返回：
            摘要文本，如果不存在返回None
        """
        # 获取压缩上下文
        ctx = self.get_compressed_context(workflow_id)
        if not ctx:
            return None

        # 生成基础摘要
        summary_parts = []
        if hasattr(ctx, "to_summary_text"):
            summary_parts.append(ctx.to_summary_text())

        # 添加知识引用详情
        if hasattr(ctx, "knowledge_references") and ctx.knowledge_references:
            refs = ctx.knowledge_references
            ref_summaries = []
            for ref in refs[:3]:  # 最多显示3条
                title = ref.get("title", "未知")
                score = ref.get("relevance_score", 0)
                ref_summaries.append(f"  - {title} (相关度: {score:.0%})")

            if ref_summaries:
                summary_parts.append("知识引用:")
                summary_parts.extend(ref_summaries)

        return "\n".join(summary_parts) if summary_parts else None

    def get_context_for_conversation_agent(
        self,
        workflow_id: str,
    ) -> dict[str, Any] | None:
        """获取用于对话Agent的上下文

        将压缩上下文转换为对话Agent可用的格式。

        参数：
            workflow_id: 工作流ID

        返回：
            对话Agent可用的上下文字典，如果不存在返回None
        """
        ctx = self.get_compressed_context(workflow_id)
        if not ctx:
            return None

        # 构建对话Agent可用的上下文
        agent_context = {
            "workflow_id": workflow_id,
            "goal": getattr(ctx, "task_goal", ""),
            "task_goal": getattr(ctx, "task_goal", ""),
            "execution_status": getattr(ctx, "execution_status", {}),
            "node_summary": getattr(ctx, "node_summary", []),
            "errors": getattr(ctx, "error_log", []),
            "next_actions": getattr(ctx, "next_actions", []),
            "conversation_summary": getattr(ctx, "conversation_summary", ""),
            "reflection_summary": getattr(ctx, "reflection_summary", {}),
        }

        # 添加知识引用
        if hasattr(ctx, "knowledge_references"):
            agent_context["knowledge_references"] = ctx.knowledge_references
            agent_context["references"] = ctx.knowledge_references

        # 添加缓存的知识
        cached = self.get_cached_knowledge(workflow_id)
        if cached and hasattr(cached, "to_dict_list"):
            agent_context["cached_knowledge"] = cached.to_dict_list()

        return agent_context

    async def auto_enrich_context_on_error(
        self,
        workflow_id: str,
        error_type: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """错误发生时自动丰富上下文

        当节点执行失败时，自动检索相关的错误解决方案知识。

        参数：
            workflow_id: 工作流ID
            error_type: 错误类型
            error_message: 错误消息（可选）

        返回：
            丰富后的上下文字典
        """
        # 构建错误列表
        errors = [{"error_type": error_type, "message": error_message or ""}]

        # 获取现有目标
        goal = None
        if workflow_id in self._compressed_contexts:
            ctx = self._compressed_contexts[workflow_id]
            goal = getattr(ctx, "task_goal", None)

        # 丰富上下文
        enriched = await self.enrich_context_with_knowledge(
            workflow_id=workflow_id,
            goal=goal,
            errors=errors,
        )

        # 注入到压缩上下文
        await self.inject_knowledge_to_context(
            workflow_id=workflow_id,
            errors=errors,
        )

        return enriched

    def enable_auto_knowledge_retrieval(self) -> None:
        """启用自动知识检索

        启用后，在节点失败和反思事��时会自动检索相关知识。
        """
        self._auto_knowledge_retrieval_enabled = True

    def disable_auto_knowledge_retrieval(self) -> None:
        """禁用自动知识检索"""
        self._auto_knowledge_retrieval_enabled = False

    async def handle_node_failure_with_knowledge(
        self,
        workflow_id: str,
        node_id: str,
        error_type: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """处理节点失败并检索相关知识

        当节点执行失败时调用此方法，会自动检索与错误相关的知识，
        并将其添加到压缩上下文中。

        参数：
            workflow_id: 工作流ID
            node_id: 失败的节点ID
            error_type: 错误类型
            error_message: 错误消息（可选）

        返回：
            包含知识引用的结果字典
        """
        # 记录错误到错误日志
        if workflow_id in self._compressed_contexts:
            ctx = self._compressed_contexts[workflow_id]
            if hasattr(ctx, "error_log"):
                ctx.error_log.append(
                    {
                        "node_id": node_id,
                        "error_type": error_type,
                        "error_message": error_message or "",
                    }
                )

        # 自动检索错误相关知识
        result = await self.auto_enrich_context_on_error(
            workflow_id=workflow_id,
            error_type=error_type,
            error_message=error_message,
        )

        return result

    async def handle_reflection_with_knowledge(
        self,
        workflow_id: str,
        assessment: str,
        confidence: float = 0.0,
        recommendations: list[str] | None = None,
    ) -> dict[str, Any]:
        """处理反思事件并检索相关知识

        当收到反思事件时调用此方法，会基于工作流目标检索相关知识。

        参数：
            workflow_id: 工作流ID
            assessment: 评估内容
            confidence: 置信度
            recommendations: 建议列表（可选）

        返回：
            包含知识引用的结果字典
        """
        # 更新反思摘要
        if workflow_id in self._compressed_contexts:
            ctx = self._compressed_contexts[workflow_id]
            if hasattr(ctx, "reflection_summary"):
                ctx.reflection_summary = {
                    "assessment": assessment,
                    "confidence": confidence,
                    "recommendations": recommendations or [],
                }
            if hasattr(ctx, "next_actions") and recommendations:
                ctx.next_actions = recommendations

        # 获取目标并检索相关知识
        goal = None
        if workflow_id in self._compressed_contexts:
            ctx = self._compressed_contexts[workflow_id]
            goal = getattr(ctx, "task_goal", None)

        # 基于目标和评估检索知识
        result = await self.enrich_context_with_knowledge(
            workflow_id=workflow_id,
            goal=goal or assessment,  # 如果没有目标，使用评估内容
        )

        # 注入到上下文
        await self.inject_knowledge_to_context(
            workflow_id=workflow_id,
            goal=goal or assessment,
        )

        return result

    # ==================== Phase 5: 执行总结管理 ====================

    def _init_summary_storage(self) -> None:
        """初始化总结存储（懒加载）"""
        if not hasattr(self, "_execution_summaries"):
            self._execution_summaries: dict[str, Any] = {}
        if not hasattr(self, "_channel_bridge"):
            self._channel_bridge: Any | None = None

    def set_channel_bridge(self, bridge: Any) -> None:
        """设置通信桥接器

        参数：
            bridge: AgentChannelBridge 实例
        """
        self._init_summary_storage()
        self._channel_bridge = bridge

    def record_execution_summary(self, summary: Any) -> None:
        """同步记录执行总结

        参数：
            summary: ExecutionSummary 实例
        """
        self._init_summary_storage()
        workflow_id = getattr(summary, "workflow_id", "")
        if workflow_id:
            self._execution_summaries[workflow_id] = summary

    async def record_execution_summary_async(self, summary: Any) -> None:
        """异步记录执行总结并发布事件

        参数：
            summary: ExecutionSummary 实例
        """
        from src.domain.agents.execution_summary import ExecutionSummaryRecordedEvent

        self._init_summary_storage()
        workflow_id = getattr(summary, "workflow_id", "")
        session_id = getattr(summary, "session_id", "")
        success = getattr(summary, "success", True)
        summary_id = getattr(summary, "summary_id", "")

        if workflow_id:
            self._execution_summaries[workflow_id] = summary

        # 发布事件
        if self.event_bus:
            event = ExecutionSummaryRecordedEvent(
                source="coordinator_agent",
                workflow_id=workflow_id,
                session_id=session_id,
                success=success,
                summary_id=summary_id,
            )
            await self.event_bus.publish(event)

    def get_execution_summary(self, workflow_id: str) -> Any | None:
        """获取执行总结

        参数：
            workflow_id: 工作流ID

        返回：
            ExecutionSummary 实例，如果不存在返回 None
        """
        self._init_summary_storage()
        return self._execution_summaries.get(workflow_id)

    def get_summary_statistics(self) -> dict[str, Any]:
        """获取总结统计

        返回：
            包含统计信息的字典
        """
        self._init_summary_storage()

        total = len(self._execution_summaries)
        successful = sum(
            1 for s in self._execution_summaries.values() if getattr(s, "success", False)
        )
        failed = total - successful

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
        }

    async def record_and_push_summary(self, summary: Any) -> None:
        """记录总结并推送到前端

        参数：
            summary: ExecutionSummary 实例
        """
        # 记录总结
        await self.record_execution_summary_async(summary)

        # 推送到前端（如果有桥接器）
        self._init_summary_storage()
        if self._channel_bridge:
            session_id = getattr(summary, "session_id", "")
            if session_id:
                await self._channel_bridge.push_execution_summary(session_id, summary)

    def get_all_summaries(self) -> dict[str, Any]:
        """获取所有总结

        返回：
            工作流ID到总结的映射
        """
        self._init_summary_storage()
        return self._execution_summaries.copy()

    # ==================== Phase 6: 强力压缩器与查询接口 ====================

    def _init_power_compressor_storage(self) -> None:
        """初始化强力压缩器存储（懒加载）"""
        if not hasattr(self, "_power_compressed_contexts"):
            self._power_compressed_contexts: dict[str, dict[str, Any]] = {}
        if not hasattr(self, "_power_compressor"):
            self._power_compressor: Any | None = None

    def _get_power_compressor(self) -> Any:
        """获取强力压缩器实例"""
        self._init_power_compressor_storage()
        if self._power_compressor is None:
            from src.domain.services.power_compressor import PowerCompressor

            self._power_compressor = PowerCompressor()
        return self._power_compressor

    async def compress_and_store(self, summary: Any) -> Any:
        """压缩执行总结并存储

        使用 PowerCompressor 压缩执行总结，生成八段格式的压缩上下文，
        并存储到内部缓存中。

        参数：
            summary: ExecutionSummary 实例

        返回：
            PowerCompressedContext 实例
        """

        compressor = self._get_power_compressor()
        self._init_power_compressor_storage()

        # 使用压缩器压缩总结
        compressed = compressor.compress_summary(summary)

        # 转换为字典并存储
        workflow_id = compressed.workflow_id
        if workflow_id:
            self._power_compressed_contexts[workflow_id] = compressed.to_dict()

        return compressed

    def store_compressed_context(self, workflow_id: str, data: dict[str, Any]) -> None:
        """存储压缩上下文

        直接存储已格式化的压缩上下文数据。

        参数：
            workflow_id: 工作流ID
            data: 压缩上下文数据字典
        """
        self._init_power_compressor_storage()
        self._power_compressed_contexts[workflow_id] = data

    def query_compressed_context(self, workflow_id: str) -> dict[str, Any] | None:
        """查询压缩上下文

        参数：
            workflow_id: 工作流ID

        返回：
            压缩上下文字典，如果不存在返回 None
        """
        self._init_power_compressor_storage()
        return self._power_compressed_contexts.get(workflow_id)

    def query_subtask_errors(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询子任务错误

        参数：
            workflow_id: 工作流ID

        返回：
            子任务错误列表
        """
        self._init_power_compressor_storage()
        ctx = self._power_compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("subtask_errors", [])
        return []

    def query_unresolved_issues(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询未解决问题

        参数：
            workflow_id: 工作流ID

        返回：
            未解决问题列表
        """
        self._init_power_compressor_storage()
        ctx = self._power_compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("unresolved_issues", [])
        return []

    def query_next_plan(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询后续计划

        参数：
            workflow_id: 工作流ID

        返回：
            后续计划列表
        """
        self._init_power_compressor_storage()
        ctx = self._power_compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("next_plan", [])
        return []

    def get_context_for_conversation(self, workflow_id: str) -> dict[str, Any] | None:
        """获取用于对话Agent下一轮输入的上下文

        返回包含所有八段压缩信息的上下文，供对话Agent引用。

        参数：
            workflow_id: 工作流ID

        返回：
            对话Agent可用的上下文字典，如果不存在返回 None
        """
        self._init_power_compressor_storage()
        ctx = self._power_compressed_contexts.get(workflow_id)
        if not ctx:
            return None

        # 返回完整的八段上下文
        return {
            "workflow_id": ctx.get("workflow_id", workflow_id),
            "task_goal": ctx.get("task_goal", ""),
            "execution_status": ctx.get("execution_status", {}),
            "node_summary": ctx.get("node_summary", []),
            "subtask_errors": ctx.get("subtask_errors", []),
            "unresolved_issues": ctx.get("unresolved_issues", []),
            "decision_history": ctx.get("decision_history", []),
            "next_plan": ctx.get("next_plan", []),
            "knowledge_sources": ctx.get("knowledge_sources", []),
        }

    def get_knowledge_for_conversation(self, workflow_id: str) -> list[dict[str, Any]]:
        """获取用于对话Agent引用的知识来源

        参数：
            workflow_id: 工作流ID

        返回：
            知识来源列表
        """
        self._init_power_compressor_storage()
        ctx = self._power_compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("knowledge_sources", [])
        return []

    def get_power_compression_statistics(self) -> dict[str, Any]:
        """获取强力压缩器统计

        返回：
            包含统计信息的字典
        """
        self._init_power_compressor_storage()

        total = len(self._power_compressed_contexts)
        total_errors = sum(
            len(ctx.get("subtask_errors", [])) for ctx in self._power_compressed_contexts.values()
        )
        total_issues = sum(
            len(ctx.get("unresolved_issues", []))
            for ctx in self._power_compressed_contexts.values()
        )
        total_plans = sum(
            len(ctx.get("next_plan", [])) for ctx in self._power_compressed_contexts.values()
        )

        return {
            "total_contexts": total,
            "total_subtask_errors": total_errors,
            "total_unresolved_issues": total_issues,
            "total_next_plan_items": total_plans,
        }


# 导出
__all__ = [
    "FailureHandlingStrategy",
    "Rule",
    "ValidationResult",
    "ContextResponse",
    "DecisionValidatedEvent",
    "DecisionRejectedEvent",
    "CircuitBreakerAlertEvent",
    "WorkflowAdjustmentRequestedEvent",
    "NodeFailureHandledEvent",
    "WorkflowAbortedEvent",
    "SubAgentCompletedEvent",
    "FailureHandlingResult",
    "CoordinatorAgent",
]

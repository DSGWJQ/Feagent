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
    ):
        """初始化协调者Agent

        参数：
            event_bus: 事件总线（用于发布验证/拒绝事件）
            rejection_rate_threshold: 拒绝率告警阈值
            circuit_breaker_config: 熔断器配置（阶段5新增）
            context_bridge: 上下文桥接器（阶段5新增）
            failure_strategy_config: 失败处理策略配置（Phase 12）
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

        # 订阅工作流事件
        self.event_bus.subscribe(WorkflowExecutionStartedEvent, self._handle_workflow_started)
        self.event_bus.subscribe(WorkflowExecutionCompletedEvent, self._handle_workflow_completed)
        self.event_bus.subscribe(NodeExecutionEvent, self._handle_node_execution)

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
        """
        if self._is_listening_reflections:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for reflection listening")

        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        self.event_bus.subscribe(WorkflowReflectionCompletedEvent, self._handle_reflection_event)
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


# 导出
__all__ = [
    "FailureHandlingStrategy",
    "Rule",
    "ValidationResult",
    "DecisionValidatedEvent",
    "DecisionRejectedEvent",
    "CircuitBreakerAlertEvent",
    "WorkflowAdjustmentRequestedEvent",
    "NodeFailureHandledEvent",
    "WorkflowAbortedEvent",
    "FailureHandlingResult",
    "CoordinatorAgent",
]

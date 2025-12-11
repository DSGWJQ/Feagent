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

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.services.event_bus import Event, EventBus
from src.domain.services.safety_guard import ValidationResult
from src.domain.services.workflow_failure_orchestrator import (
    FailureHandlingResult,
    FailureHandlingStrategy,
    NodeFailureHandledEvent,
    WorkflowAbortedEvent,
    WorkflowAdjustmentRequestedEvent,
)

logger = logging.getLogger(__name__)

# =========================================================================
# P1 Fix: 配置常量（避免魔法数字）
# =========================================================================
DEFAULT_REJECTION_RATE_THRESHOLD = 0.5
"""默认决策拒绝率阈值"""

DEFAULT_MAX_RETRIES = 3
"""默认最大重试次数"""

DEFAULT_RETRY_DELAY = 1.0
"""默认重试延迟（秒）"""

MAX_MESSAGE_LOG_SIZE = 1000
"""消息日志最大条目数（防止内存泄漏）"""

MAX_CONTAINER_LOGS_SIZE = 500
"""容器日志最大条目数"""

MAX_SUBAGENT_RESULTS_SIZE = 100
"""子Agent结果历史最大条目数"""


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
    error_message: str | Callable[[dict[str, Any]], str] = "验证失败"
    correction: Callable[[dict[str, Any]], dict[str, Any]] | None = None


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

    # ===================== Phase 34.9: ContextGateway ====================
    class _ContextGateway:
        """Context Gateway for KnowledgeRetrievalOrchestrator

        提供对 _compressed_contexts 的访问接口，解耦编排器与内部状态。
        支持 CompressedContext 数据类和字典两种格式。
        """

        def __init__(self, contexts_dict: dict[str, Any]):
            self._contexts = contexts_dict

        def get_context(self, workflow_id: str) -> Any:
            """获取压缩上下文

            参数：
                workflow_id: 工作流ID

            返回：
                压缩上下文（CompressedContext 或 dict），如果不存在返回 None
            """
            return self._contexts.get(workflow_id)

        def update_knowledge_refs(self, workflow_id: str, refs: list[dict[str, Any]]) -> None:
            """更新知识引用（去重合并）

            参数：
                workflow_id: 工作流ID
                refs: 新的知识引用列表
            """
            if workflow_id not in self._contexts:
                return

            ctx = self._contexts[workflow_id]

            # 处理 CompressedContext 数据类
            if hasattr(ctx, "knowledge_references"):
                existing_refs = getattr(ctx, "knowledge_references", [])
                if not isinstance(existing_refs, list):
                    existing_refs = []

                # 去重合并（按 source_id）
                seen_ids = {r.get("source_id") for r in existing_refs if isinstance(r, dict)}
                for ref in refs:
                    if isinstance(ref, dict) and ref.get("source_id") not in seen_ids:
                        existing_refs.append(ref)
                        seen_ids.add(ref.get("source_id"))

                # 直接修改属性（数据类是可变的）
                ctx.knowledge_references = existing_refs

            # 处理字典格式（兜底）
            elif isinstance(ctx, dict):
                existing_refs = ctx.get("knowledge_references", [])
                if not isinstance(existing_refs, list):
                    existing_refs = []

                seen_ids = {r.get("source_id") for r in existing_refs if isinstance(r, dict)}
                for ref in refs:
                    if isinstance(ref, dict) and ref.get("source_id") not in seen_ids:
                        existing_refs.append(ref)
                        seen_ids.add(ref.get("source_id"))

                ctx["knowledge_references"] = existing_refs

        def update_error_log(self, workflow_id: str, error: dict[str, Any]) -> None:
            """添加错误日志

            参数：
                workflow_id: 工作流ID
                error: 错误信息dict
            """
            if workflow_id not in self._contexts:
                return

            ctx = self._contexts[workflow_id]

            # 处理 CompressedContext 数据类
            if hasattr(ctx, "error_log"):
                error_log = getattr(ctx, "error_log", [])
                if not isinstance(error_log, list):
                    error_log = []
                error_log.append(error)
                ctx.error_log = error_log

            # 处理字典格式（兜底）
            elif isinstance(ctx, dict):
                error_log = ctx.get("error_log", [])
                if not isinstance(error_log, list):
                    error_log = []
                error_log.append(error)
                ctx["error_log"] = error_log

        def update_reflection(self, workflow_id: str, reflection: dict[str, Any]) -> None:
            """更新反思摘要

            参数：
                workflow_id: 工作流ID
                reflection: 反思内容dict
            """
            if workflow_id not in self._contexts:
                return

            ctx = self._contexts[workflow_id]

            # 处理 CompressedContext 数据类
            if hasattr(ctx, "reflection_summary"):
                ctx.reflection_summary = reflection
                # 如果有建议，更新 next_actions
                if "recommendations" in reflection and hasattr(ctx, "next_actions"):
                    ctx.next_actions = reflection["recommendations"]

            # 处理字典格式（兜底）
            elif isinstance(ctx, dict):
                ctx["reflection_summary"] = reflection
                if "recommendations" in reflection:
                    ctx["next_actions"] = reflection["recommendations"]

    # ===================== Phase 34.10: Log Integration Accessors ====================

    class _MessageLogAccessor:
        """Message Log Accessor for UnifiedLogIntegration

        提供对 message_log 的只读访问接口。
        """

        def __init__(self, messages_ref: list[dict[str, Any]]):
            """初始化访问器

            参数：
                messages_ref: message_log 引用（append-only list）
            """
            self._messages = messages_ref

        def get_messages(self) -> list[dict[str, Any]]:
            """获取消息日志列表

            返回：
                消息日志列表（只读访问）
            """
            return self._messages

    class _ContainerLogAccessor:
        """Container Log Accessor for UnifiedLogIntegration

        提供对 container_logs 的只读访问接口。
        """

        def __init__(self, container_monitor: Any):
            """初始化访问器

            参数：
                container_monitor: ContainerExecutionMonitor 实例
            """
            self._monitor = container_monitor

        def get_container_logs(self) -> dict[str, list[dict[str, Any]]]:
            """获取容器日志字典

            返回：
                容器日志字典 {container_id: [logs]}
            """
            return self._monitor.container_logs

    # =====================================================================

    def __init__(
        self,
        event_bus: EventBus | None = None,
        rejection_rate_threshold: float = DEFAULT_REJECTION_RATE_THRESHOLD,
        circuit_breaker_config: Any | None = None,
        context_bridge: Any | None = None,
        failure_strategy_config: dict[str, Any] | None = None,
        context_compressor: Any | None = None,
        snapshot_manager: Any | None = None,
        knowledge_retriever: Any | None = None,
    ):
        """初始化协调者Agent（Phase 34.11: 使用 CoordinatorBootstrap）

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
        from src.domain.services.coordinator_bootstrap import (
            CoordinatorBootstrap,
            CoordinatorConfig,
        )

        # 1. 创建配置对象
        config = CoordinatorConfig(
            event_bus=event_bus,
            rejection_rate_threshold=rejection_rate_threshold,
            circuit_breaker_config=circuit_breaker_config,
            context_bridge=context_bridge,
            failure_strategy_config=failure_strategy_config,
            context_compressor=context_compressor,
            snapshot_manager=snapshot_manager,
            knowledge_retriever=knowledge_retriever,
        )

        # 2. 执行依赖装配
        bootstrap = CoordinatorBootstrap(config=config)
        wiring = bootstrap.assemble()

        # 3. 解包装配结果：配置属性
        self.event_bus = event_bus
        self.rejection_rate_threshold = rejection_rate_threshold

        # 4. 解包装配结果：基础状态（使用bootstrap创建的容器，确保状态共享）
        self._rules: list[Rule] = wiring.base_state["_rules"]
        self._statistics = wiring.base_state["_statistics"]

        # 5. 解包装配结果：工作流状态（共享bootstrap容器）
        self.workflow_states: dict[str, dict[str, Any]] = wiring.base_state["workflow_states"]
        self._is_monitoring = wiring.base_state["_is_monitoring"]
        self._current_workflow_id: str | None = wiring.base_state["_current_workflow_id"]

        # 6. 解包装配结果：共享组件（log_collector）
        self.log_collector = wiring.log_collector

        # 7. 解包装配结果：所有别名
        for alias_name, alias_value in wiring.aliases.items():
            setattr(self, alias_name, alias_value)

        # 8. 解包装配结果：所有编排器
        self._failure_orchestrator = wiring.orchestrators["failure_orchestrator"]
        self._container_monitor = wiring.orchestrators["container_monitor"]
        self._log_integration = wiring.orchestrators["log_integration"]
        self.knowledge_manager = wiring.orchestrators["knowledge_manager"]
        self._knowledge_retrieval_orchestrator = wiring.orchestrators[
            "knowledge_retrieval_orchestrator"
        ]
        self._summary_manager = wiring.orchestrators["summary_manager"]
        self._power_compressor_facade = wiring.orchestrators["power_compressor_facade"]
        self._subagent_orchestrator = wiring.orchestrators["subagent_orchestrator"]
        self._supervision_coordinator = wiring.orchestrators["supervision_coordinator"]
        self._prompt_facade = wiring.orchestrators["prompt_facade"]
        self._experiment_orchestrator = wiring.orchestrators["experiment_orchestrator"]
        self._save_request_orchestrator = wiring.orchestrators["save_request_orchestrator"]
        self.injection_manager = wiring.orchestrators["context_injection_manager"]
        self.supervision_module = wiring.orchestrators["supervision_module"]
        self.intervention_coordinator = wiring.orchestrators["intervention_coordinator"]
        self.workflow_modifier = wiring.orchestrators["workflow_modifier"]
        self.task_terminator = wiring.orchestrators["task_terminator"]
        self._safety_guard = wiring.orchestrators["safety_guard"]

        # 可选组件
        if "alert_rule_manager" in wiring.orchestrators:
            self.alert_rule_manager = wiring.orchestrators["alert_rule_manager"]
        if "circuit_breaker" in wiring.orchestrators:
            self.circuit_breaker = wiring.orchestrators["circuit_breaker"]

        # 9. 重建内部状态容器（共享bootstrap容器以保持状态一致）
        self._node_failure_strategies: dict[str, FailureHandlingStrategy] = wiring.base_state[
            "_node_failure_strategies"
        ]
        self._workflow_agents: dict[str, Any] = wiring.base_state["_workflow_agents"]
        self.message_log: list[dict[str, Any]] = wiring.base_state["message_log"]
        self.reflection_contexts: dict[str, dict[str, Any]] = wiring.base_state[
            "reflection_contexts"
        ]
        self._compressed_contexts: dict[str, Any] = wiring.base_state["_compressed_contexts"]
        self._knowledge_cache: dict[str, Any] = wiring.base_state["_knowledge_cache"]

        # 10. 重建 accessor 和 gateway（依赖共享状态容器）
        self._message_log_accessor = self._MessageLogAccessor(self.message_log)
        self._container_log_accessor = self._ContainerLogAccessor(self._container_monitor)
        self._context_gateway = self._ContextGateway(self._compressed_contexts)

        # 11. 暴露 SupervisionCoordinator 子模块（向后兼容）
        self.conversation_supervision = self._supervision_coordinator.conversation_supervision
        self.efficiency_monitor = self._supervision_coordinator.efficiency_monitor
        self.strategy_repository = self._supervision_coordinator.strategy_repository

        # 12. 暴露内部 logger（向后兼容）
        self._injection_logger = wiring.orchestrators["injection_logger"]
        self._supervision_logger = wiring.orchestrators["supervision_logger"]
        self._intervention_logger = wiring.orchestrators["intervention_logger"]

        # 14. 保留原始配置引用（向后兼容）
        self.failure_strategy_config = failure_strategy_config or self._failure_orchestrator.config
        self.knowledge_retriever = knowledge_retriever

    # =========================================================================
    # P1-6 Fix: 有界列表辅助方法（防止内存泄漏）
    # =========================================================================

    def _add_to_bounded_list(
        self,
        target_list: list[Any],
        item: Any,
        max_size: int,
    ) -> None:
        """添加项目到有界列表，超出限制时移除最旧的项

        参数：
            target_list: 目标列表
            item: 要添加的项目
            max_size: 最大大小限制
        """
        target_list.append(item)
        while len(target_list) > max_size:
            target_list.pop(0)  # 移除最旧的

    # ==================== Phase 5 (七种节点类型): 安全规则配置与验证（委托给 SafetyGuard）====================

    def configure_file_security(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        max_content_bytes: int | None = None,
        allowed_operations: set[str] | None = None,
    ) -> None:
        """配置文件操作安全规则（代理到 SafetyGuard）

        参数:
            whitelist: 允许访问的路径白名单
            blacklist: 禁止访问的路径黑名单
            max_content_bytes: 内容最大字节数限制
            allowed_operations: 允许的操作类型集合
        """
        self._safety_guard.configure_file_security(
            whitelist=whitelist,
            blacklist=blacklist,
            max_content_bytes=max_content_bytes,
            allowed_operations=allowed_operations,
        )

    def configure_api_domains(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        allowed_schemes: set[str] | None = None,
    ) -> None:
        """配置API域名白名单规则（代理到 SafetyGuard）

        参数:
            whitelist: 允许访问的域名白名单
            blacklist: 禁止访问的域名黑名单
            allowed_schemes: 允许的URL scheme集合
        """
        self._safety_guard.configure_api_domains(
            whitelist=whitelist,
            blacklist=blacklist,
            allowed_schemes=allowed_schemes,
        )

    async def validate_file_operation(
        self,
        node_id: str,
        operation: str | None,
        path: str | None,
        config: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """验证文件操作安全性（代理到 SafetyGuard）

        参数:
            node_id: 节点ID
            operation: 文件操作类型（read/write/append/delete/list）
            path: 文件路径
            config: 节点配置，包含content等字段

        返回:
            ValidationResult: 验证结果
        """
        return await self._safety_guard.validate_file_operation(
            node_id=node_id,
            operation=operation,
            path=path,
            config=config,
        )

    async def validate_api_request(
        self,
        node_id: str,
        url: str | None,
        method: str | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> ValidationResult:
        """验证API请求安全性（代理到 SafetyGuard）

        参数:
            node_id: 节点ID
            url: 请求URL
            method: HTTP方法
            headers: 请求头
            body: 请求体

        返回:
            ValidationResult: 验证结果
        """
        return await self._safety_guard.validate_api_request(
            node_id=node_id,
            url=url,
            method=method,
            headers=headers,
            body=body,
        )

    async def validate_human_interaction(
        self,
        node_id: str,
        prompt: str,
        expected_inputs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """验证人机交互内容安全性（代理到 SafetyGuard）

        参数:
            node_id: 节点ID
            prompt: 交互提示词
            expected_inputs: 期望的输入选项
            metadata: 元数据

        返回:
            ValidationResult: 验证结果
        """
        return await self._safety_guard.validate_human_interaction(
            node_id=node_id,
            prompt=prompt,
            expected_inputs=expected_inputs,
            metadata=metadata,
        )

    # ==================== Phase 34: 保存请求处理（委托 SaveRequestOrchestrator） ====================

    def enable_save_request_handler(self) -> None:
        """启用保存请求处理器（代理到 SaveRequestOrchestrator）

        启用后，Coordinator 将订阅 SaveRequest 事件并管理请求队列。
        """
        if not self._save_request_orchestrator:
            raise ValueError("SaveRequestOrchestrator not initialized (event_bus required)")

        self._save_request_orchestrator.enable_save_request_handler()

        # 同步状态标志
        self._save_request_handler_enabled = (
            self._save_request_orchestrator._save_request_handler_enabled
        )
        self._is_listening_save_requests = (
            self._save_request_orchestrator._is_listening_save_requests
        )

    def disable_save_request_handler(self) -> None:
        """禁用保存请求处理器（代理到 SaveRequestOrchestrator）"""
        if not self._save_request_orchestrator:
            return

        self._save_request_orchestrator.disable_save_request_handler()

        # 同步状态标志
        self._save_request_handler_enabled = (
            self._save_request_orchestrator._save_request_handler_enabled
        )
        self._is_listening_save_requests = (
            self._save_request_orchestrator._is_listening_save_requests
        )

    def _handle_save_request(self, event: Any) -> None:
        """处理 SaveRequest 事件（已由 SaveRequestOrchestrator 接管）

        注意：此方法不应被直接调用，event_bus 会直接调用 orchestrator 的异步处理器。
        保留此方法仅为向后兼容。

        参数：
            event: SaveRequest 事件
        """
        # 实际处理已由 orchestrator._handle_save_request (async) 完成
        # 此方法仅用于保持接口兼容，实际不会被调用
        pass

    def has_pending_save_requests(self) -> bool:
        """检查是否有待处理的保存请求（代理到 SaveRequestOrchestrator）

        返回：
            True 如果有待处理请求
        """
        if not self._save_request_orchestrator:
            return False
        return self._save_request_orchestrator.has_pending_save_requests()

    def get_pending_save_request_count(self) -> int:
        """获取待处理保存请求数量（代理到 SaveRequestOrchestrator）

        返回：
            待处理请求数量
        """
        if not self._save_request_orchestrator:
            return 0
        return self._save_request_orchestrator.get_pending_save_request_count()

    def get_save_request_queue(self) -> list[Any]:
        """获取保存请求队列（按优先级排序）（代理到 SaveRequestOrchestrator）

        返回：
            排序后的 SaveRequest 列表
        """
        if not self._save_request_orchestrator:
            return []
        return self._save_request_orchestrator.get_save_request_queue()

    def get_save_request_status(self, request_id: str) -> Any:
        """获取保存请求状态（代理到 SaveRequestOrchestrator）

        参数：
            request_id: 请求 ID

        返回：
            SaveRequestStatus 或 None
        """
        if not self._save_request_orchestrator:
            from src.domain.services.save_request_channel import SaveRequestStatus

            return SaveRequestStatus.PENDING
        return self._save_request_orchestrator.get_save_request_status(request_id)

    def get_save_requests_by_session(self, session_id: str) -> list[Any]:
        """获取特定会话的保存请求（代理到 SaveRequestOrchestrator）

        参数：
            session_id: 会话 ID

        返回：
            该会话的 SaveRequest 列表
        """
        if not self._save_request_orchestrator:
            return []
        return self._save_request_orchestrator.get_save_requests_by_session(session_id)

    def dequeue_save_request(self) -> Any | None:
        """从队列中取出最高优先级的保存请求（代理到 SaveRequestOrchestrator）

        返回：
            SaveRequest 或 None
        """
        if not self._save_request_orchestrator:
            return None
        return self._save_request_orchestrator.dequeue_save_request()

    # ==================== Phase 34.2: 审核与执行 ====================

    def configure_save_auditor(
        self,
        path_whitelist: list[str] | None = None,
        path_blacklist: list[str] | None = None,
        max_content_size: int = 10 * 1024 * 1024,
        enable_rate_limit: bool = True,
        enable_sensitive_check: bool = True,
    ) -> None:
        """配置保存请求审核器（代理到 SaveRequestOrchestrator）

        参数：
            path_whitelist: 路径白名单（如果提供，只允许这些路径）
            path_blacklist: 路径黑名单
            max_content_size: 最大内容大小（字节）
            enable_rate_limit: 是否启用频率限制
            enable_sensitive_check: 是否启用敏感内容检查
        """
        if not self._save_request_orchestrator:
            raise ValueError("SaveRequestOrchestrator not initialized (event_bus required)")

        self._save_request_orchestrator.configure_save_auditor(
            path_whitelist=path_whitelist,
            path_blacklist=path_blacklist,
            max_content_size=max_content_size,
            enable_rate_limit=enable_rate_limit,
            enable_sensitive_check=enable_sensitive_check,
        )

        # 同步内部组件引用（向后兼容）
        self._save_auditor = self._save_request_orchestrator._save_auditor
        self._save_executor = self._save_request_orchestrator._save_executor
        self._save_audit_logger = self._save_request_orchestrator._save_audit_logger

    def process_next_save_request(self) -> Any | None:
        """处理下一个保存请求（代理到 SaveRequestOrchestrator）

        流程：
        1. 从队列取出请求
        2. 执行审核
        3. 如果通过，执行写操作
        4. 记录审计日志
        5. 发布完成事件

        返回：
            ProcessResult 或 None（队列为空时）
        """
        if not self._save_request_orchestrator:
            return None

        import asyncio

        # 同步包装异步方法
        result = asyncio.run(self._save_request_orchestrator.process_next_save_request())

        # 同步内部组件引用（向后兼容）
        self._save_auditor = self._save_request_orchestrator._save_auditor
        self._save_executor = self._save_request_orchestrator._save_executor
        self._save_audit_logger = self._save_request_orchestrator._save_audit_logger

        return result

    def get_save_audit_logs(self) -> list[dict]:
        """获取保存审计日志（代理到 SaveRequestOrchestrator）

        返回：
            审计日志列表
        """
        if not self._save_request_orchestrator:
            return []
        return self._save_request_orchestrator.get_save_audit_logs()

    def get_save_audit_logs_by_session(self, session_id: str) -> list[dict]:
        """获取特定会话的保存审计日志（代理到 SaveRequestOrchestrator）

        参数：
            session_id: 会话 ID

        返回：
            该会话的审计日志列表
        """
        if not self._save_request_orchestrator:
            return []
        return self._save_request_orchestrator.get_save_audit_logs_by_session(session_id)

    # ==================== Phase 34.3 → 34.12: 上下文注入（委托到 ContextInjectionManager Facade）====================

    def inject_context(
        self,
        session_id: str,
        injection_type: Any,
        content: str,
        reason: str,
        priority: int = 30,
    ) -> Any:
        """向会话注入上下文（委托到 ContextInjectionManager）

        参数：
            session_id: 会话 ID
            injection_type: 注入类型（InjectionType 枚举）
            content: 注入内容
            reason: 注入原因
            priority: 优先级

        返回：
            创建的 ContextInjection
        """
        return self.injection_manager.inject_context(
            session_id=session_id,
            injection_type=injection_type,
            content=content,
            reason=reason,
            priority=priority,
        )

    def inject_warning(
        self,
        session_id: str,
        warning_message: str,
        rule_id: str | None = None,
    ) -> Any:
        """注入警告信息

        当规则违反或检测到风险时调用。

        参数：
            session_id: 会话 ID
            warning_message: 警告消息
            rule_id: 触发警告的规则 ID

        返回：
            创建的 ContextInjection
        """
        reason = f"规则 {rule_id} 触发" if rule_id else "安全检测"
        return self.injection_manager.inject_warning(
            session_id=session_id,
            content=warning_message,
            source="coordinator",
            reason=reason,
        )

    def inject_intervention(
        self,
        session_id: str,
        intervention_message: str,
        reason: str = "需要干预",
    ) -> Any:
        """注入干预指令

        当需要暂停或干预执行时调用。

        参数：
            session_id: 会话 ID
            intervention_message: 干预消息
            reason: 干预原因

        返回：
            创建的 ContextInjection
        """
        return self.injection_manager.inject_intervention(
            session_id=session_id,
            content=intervention_message,
            source="coordinator",
            reason=reason,
        )

    def inject_memory(
        self,
        session_id: str,
        memory_content: str,
        relevance_score: float = 0.0,
    ) -> Any:
        """注入长期记忆

        参数：
            session_id: 会话 ID
            memory_content: 记忆内容
            relevance_score: 相关性分数

        返回：
            创建的 ContextInjection
        """
        return self.injection_manager.inject_memory(
            session_id=session_id,
            content=memory_content,
            source="memory_system",
            relevance_score=relevance_score,
        )

    def inject_observation(
        self,
        session_id: str,
        observation: str,
        source: str = "monitor",
    ) -> Any:
        """注入观察信息

        参数：
            session_id: 会话 ID
            observation: 观察内容
            source: 来源

        返回：
            创建的 ContextInjection
        """
        return self.injection_manager.inject_observation(
            session_id=session_id,
            content=observation,
            source=source,
        )

    def get_injection_logs(self) -> list[dict[str, Any]]:
        """获取所有注入日志（委托到 ContextInjectionManager）"""
        return self.injection_manager.get_injection_logs()

    def get_injection_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """获取指定会话的注入日志（委托到 ContextInjectionManager）"""
        return self.injection_manager.get_injection_logs_by_session(session_id)

    # ==================== Phase 34.4: 监督模块 ====================

    def supervise_context(self, context: dict[str, Any]) -> list[Any]:
        """监督上下文

        分析上下文数据，判断是否需要干预。

        参数：
            context: 上下文数据

        返回：
            触发的 SupervisionInfo 列表
        """
        return self.supervision_module.analyze_context(context)

    def supervise_save_request(self, request: dict[str, Any]) -> list[Any]:
        """监督保存请求

        分析保存请求，判断是否需要干预。

        参数：
            request: 保存请求数据

        返回：
            触发的 SupervisionInfo 列表
        """
        return self.supervision_module.analyze_save_request(request)

    def supervise_decision_chain(
        self,
        decisions: list[dict[str, Any]],
        session_id: str,
    ) -> list[Any]:
        """监督决策链路

        分析决策链路，判断是否需要干预。

        参数：
            decisions: 决策列表
            session_id: 会话 ID

        返回：
            触发的 SupervisionInfo 列表
        """
        return self.supervision_module.analyze_decision_chain(decisions, session_id)

    def execute_intervention(self, supervision_info: Any) -> dict[str, Any]:
        """执行干预

        根据监督信息执行相应的干预动作。

        参数：
            supervision_info: 监督信息

        返回：
            干预结果
        """
        from src.domain.services.supervision_module import SupervisionAction

        action = supervision_info.action
        session_id = supervision_info.session_id
        result = {"success": True, "action": action.value}

        if action == SupervisionAction.WARNING:
            # 注入警告
            self.inject_warning(
                session_id=session_id,
                warning_message=supervision_info.content,
                rule_id=supervision_info.trigger_rule,
            )
            result["intervention_type"] = "warning_injected"

        elif action == SupervisionAction.REPLACE:
            # 替换内容 - 通过注入 SUPPLEMENT 类型信息
            replacement = supervision_info.metadata.get("replacement_content", "[REDACTED]")
            injection = self._create_supplement_injection(session_id, replacement, supervision_info)
            self.injection_manager.add_injection(injection)
            result["intervention_type"] = "content_replaced"
            result["replacement"] = replacement

        elif action == SupervisionAction.TERMINATE:
            # 注入干预指令
            self.inject_intervention(
                session_id=session_id,
                intervention_message=f"任务已终止: {supervision_info.content}",
                reason=supervision_info.trigger_condition,
            )
            result["intervention_type"] = "task_terminated"

        # 记录干预日志
        self._supervision_logger.log_intervention(
            supervision_info,
            result=result.get("intervention_type", "unknown"),
        )

        return result

    def _create_supplement_injection(
        self,
        session_id: str,
        replacement: str,
        supervision_info: Any,
    ) -> Any:
        """创建补充注入（内部方法）"""
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        return ContextInjection(
            session_id=session_id,
            injection_type=InjectionType.SUPPLEMENT,
            injection_point=InjectionPoint.PRE_THINKING,
            content=f"内容已被替换为: {replacement}",
            source="supervisor",
            reason=supervision_info.trigger_condition,
        )

    def get_supervision_logs(self) -> list[dict[str, Any]]:
        """获取所有监督日志"""
        return self._supervision_logger.get_logs()

    def get_supervision_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """获取指定会话的监督日志"""
        return self._supervision_logger.get_logs_by_session(session_id)

    # ==================== Phase 34.5: 干预系统 ====================

    def replace_workflow_node(
        self,
        workflow_definition: dict[str, Any],
        node_id: str,
        replacement_config: dict[str, Any],
        reason: str,
        session_id: str,
    ) -> Any:
        """替换工作流节点

        参数：
            workflow_definition: 工作流定义
            node_id: 原节点 ID
            replacement_config: 替换节点配置
            reason: 替换原因
            session_id: 会话 ID

        返回：
            ModificationResult
        """
        from src.domain.services.intervention_system import NodeReplacementRequest

        request = NodeReplacementRequest(
            workflow_id=workflow_definition.get("id", "unknown"),
            original_node_id=node_id,
            replacement_node_config=replacement_config,
            reason=reason,
            session_id=session_id,
        )

        return self.workflow_modifier.replace_node(workflow_definition, request)

    def remove_workflow_node(
        self,
        workflow_definition: dict[str, Any],
        node_id: str,
        reason: str,
        session_id: str,
    ) -> Any:
        """移除工作流节点

        参数：
            workflow_definition: 工作流定义
            node_id: 节点 ID
            reason: 移除原因
            session_id: 会话 ID

        返回：
            ModificationResult
        """
        from src.domain.services.intervention_system import NodeReplacementRequest

        request = NodeReplacementRequest(
            workflow_id=workflow_definition.get("id", "unknown"),
            original_node_id=node_id,
            replacement_node_config=None,  # None 表示移除
            reason=reason,
            session_id=session_id,
        )

        return self.workflow_modifier.remove_node(workflow_definition, request)

    def terminate_task(
        self,
        session_id: str,
        reason: str,
        error_code: str,
        notify_agents: list[str] | None = None,
        notify_user: bool = True,
    ) -> Any:
        """终止任务

        参数：
            session_id: 会话 ID
            reason: 终止原因
            error_code: 错误代码
            notify_agents: 需要通知的 Agent 列表
            notify_user: 是否通知用户

        返回：
            TerminationResult
        """
        from src.domain.services.intervention_system import TaskTerminationRequest

        request = TaskTerminationRequest(
            session_id=session_id,
            reason=reason,
            error_code=error_code,
            notify_agents=notify_agents or ["conversation", "workflow"],
            notify_user=notify_user,
        )

        return self.task_terminator.terminate(request)

    def handle_intervention(
        self,
        level: Any,
        context: dict[str, Any],
    ) -> Any:
        """处理干预

        参数：
            level: 干预级别 (InterventionLevel)
            context: 上下文数据

        返回：
            InterventionResult
        """
        return self.intervention_coordinator.handle_intervention(level, context)

    def get_intervention_logs(self) -> list[dict[str, Any]]:
        """获取所有干预日志"""
        return self._intervention_logger.get_logs()

    def get_intervention_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """获取指定会话的干预日志"""
        return self._intervention_logger.get_logs_by_session(session_id)

    # ==================== Phase 34.6: 结果回执系统 ====================

    def send_save_result_receipt(
        self,
        session_id: str,
        request_id: str,
        success: bool,
        message: str,
        error_code: str | None = None,
        error_message: str | None = None,
        violation_severity: str | None = None,
        audit_trail: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """发送保存结果回执（代理到 SaveRequestOrchestrator）

        当 SaveRequest 执行完成后，调用此方法发送回执给 ConversationAgent。

        参数：
            session_id: 会话 ID
            request_id: 原始请求 ID
            success: 是否成功
            message: 状态消息
            error_code: 错误代码（如有）
            error_message: 错误信息（如有）
            violation_severity: 违规严重级别（如有）
            audit_trail: 审计追踪信息

        返回：
            处理结果字典
        """
        if not self._save_request_orchestrator:
            return {"ok": False, "error": "orchestrator_not_initialized"}

        import asyncio

        # 同步包装异步方法
        return asyncio.run(
            self._save_request_orchestrator.send_save_result_receipt(
                session_id=session_id,
                request_id=request_id,
                success=success,
                message=message,
                error_code=error_code,
                error_message=error_message,
                violation_severity=violation_severity,
                audit_trail=audit_trail,
            )
        )

    def process_save_request_with_receipt(self) -> dict[str, Any] | None:
        """处理保存请求并发送回执（代理到 SaveRequestOrchestrator）

        完整流程：
        1. 从队列取出请求
        2. 执行审核
        3. 如果通过，执行写操作
        4. 发送结果回执
        5. 更新 ConversationAgent 记忆

        返回：
            处理结果或 None（队列为空时）
        """
        if not self._save_request_orchestrator:
            return None

        import asyncio

        # 同步包装异步方法
        return asyncio.run(self._save_request_orchestrator.process_save_request_with_receipt())

    def get_save_receipt_context(self, session_id: str) -> dict[str, Any]:
        """获取保存回执上下文（代理到 SaveRequestOrchestrator）

        为 ConversationAgent 生成保存结果相关的上下文。

        参数：
            session_id: 会话 ID

        返回：
            上下文字典
        """
        if not self._save_request_orchestrator:
            return {}
        return self._save_request_orchestrator.get_save_receipt_context(session_id)

    def get_save_receipt_chain_log(self, request_id: str) -> dict[str, Any] | None:
        """获取保存请求的完整链路日志（代理到 SaveRequestOrchestrator）

        参数：
            request_id: 请求 ID

        返回：
            链路日志或 None
        """
        if not self._save_request_orchestrator:
            return None
        return self._save_request_orchestrator.get_save_receipt_chain_log(request_id)

    def get_save_receipt_logs(self) -> list[dict[str, Any]]:
        """获取所有回执日志（代理到 SaveRequestOrchestrator）"""
        if not self._save_request_orchestrator:
            return []
        return self._save_request_orchestrator.get_save_receipt_logs()

    def get_session_save_statistics(self, session_id: str) -> dict[str, Any]:
        """获取会话的保存统计（代理到 SaveRequestOrchestrator）

        参数：
            session_id: 会话 ID

        返回：
            统计信息字典
        """
        if not self._save_request_orchestrator:
            return {"total_requests": 0, "successful": 0, "failed": 0}
        return self._save_request_orchestrator.get_session_save_statistics(session_id)

    # ==================== Phase 1: 上下文服务 ====================

    @property
    def tool_repository(self) -> Any | None:
        """获取工具仓库"""
        return self._tool_repository

    @tool_repository.setter
    def tool_repository(self, repo: Any) -> None:
        """设置工具仓库"""
        self._tool_repository = repo

    # ==================== GAP-004: 代码自动修复 ====================

    @property
    def auto_repair_enabled(self) -> bool:
        """是否启用自动修复"""
        return self._auto_repair_enabled

    @property
    def max_repair_attempts(self) -> int:
        """最大修复尝试次数"""
        return self._max_repair_attempts

    def enable_auto_repair(self, max_attempts: int = 3) -> None:
        """启用代码自动修复

        参数：
            max_attempts: 最大修复尝试次数
        """
        self._auto_repair_enabled = True
        self._max_repair_attempts = max_attempts

        # 懒加载代码修复服务
        if self._code_repair_service is None:
            from src.domain.services.code_repair import CodeRepair

            self._code_repair_service = CodeRepair(max_repair_attempts=max_attempts)

    def disable_auto_repair(self) -> None:
        """禁用代码自动修复"""
        self._auto_repair_enabled = False

    async def handle_code_execution_failure(
        self,
        node_id: str,
        code: str,
        error: BaseException,
        execution_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """处理代码执行失败

        尝试分析错误并进行修复（如果启用了自动修复）。

        参数：
            node_id: 节点ID
            code: 执行失败的代码
            error: 错误实例
            execution_context: 执行上下文

        返回：
            处理结果字典
        """
        result: dict[str, Any] = {
            "node_id": node_id,
            "original_error": str(error),
            "repair_attempted": False,
            "action": "none",
        }

        if not self._auto_repair_enabled:
            result["action"] = "manual_review_required"
            return result

        # 懒加载代码修复服务
        if self._code_repair_service is None:
            from src.domain.services.code_repair import CodeRepair

            self._code_repair_service = CodeRepair(max_repair_attempts=self._max_repair_attempts)

        result["repair_attempted"] = True

        # 分析错误
        analysis = self._code_repair_service.analyze_error(code, error)
        result["error_analysis"] = analysis

        # 尝试修复
        repair_result = await self._code_repair_service.repair_code_with_result(
            code,
            error,
            context=execution_context,
        )

        if repair_result.success:
            result["action"] = "repaired"
            result["repaired_code"] = repair_result.repaired_code
            result["repair_attempts"] = repair_result.attempts
        else:
            result["action"] = "repair_failed"
            result["repair_error"] = repair_result.error_message
            result["requires_manual_intervention"] = repair_result.requires_manual_intervention

        return result

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
                    # 处理可调用的 error_message (Phase 8.4)
                    if callable(rule.error_message):
                        error_msg = rule.error_message(decision)
                    else:
                        error_msg = rule.error_message

                    # 如果错误消息包含分号分隔的多个错误，拆分为独立错误 (Phase 8.4)
                    if ";" in error_msg:
                        error_items = [e.strip() for e in error_msg.split(";") if e.strip()]
                        errors.extend(error_items)
                    else:
                        errors.append(error_msg)

                    # 如果有修正函数，尝试修正
                    if rule.correction and correction is None:
                        correction = rule.correction(decision)

            except Exception as e:
                errors.append(f"规则 {rule.name} 执行异常: {str(e)}")

        is_valid = len(errors) == 0

        if is_valid:
            self._statistics["passed"] += 1
            # 记录验证通过日志
            self.log_collector.info(
                "CoordinatorAgent",
                "决策验证通过",
                {"action_type": decision.get("action_type", "unknown")},
            )
        else:
            self._statistics["rejected"] += 1
            # 记录验证失败日志
            self.log_collector.warning(
                "CoordinatorAgent",
                f"决策验证失败: {len(errors)} 个错误",
                {"action_type": decision.get("action_type", "unknown"), "errors": errors},
            )

        return ValidationResult(is_valid=is_valid, errors=errors, correction=correction)

    # ==================== 提示词版本管理接口（代理到 PromptVersionFacade）====================

    def init_prompt_version_manager(
        self,
        config: dict[str, str] | None = None,
    ) -> None:
        """初始化提示词版本管理器（代理到 Facade）"""
        self._prompt_facade.initialize(config)

    @property
    def prompt_version_manager(self) -> Any:
        """获取提示词版本管理器（代理到 Facade）"""
        return self._prompt_facade.prompt_version_manager

    def register_prompt_version(
        self,
        module_name: str,
        version: str,
        template: str,
        variables: list[str],
        changelog: str,
        author: str = "system",
    ) -> Any:
        """注册新的提示词版本（代理到 Facade）"""
        return self._prompt_facade.register_prompt_version(
            module_name=module_name,
            version=version,
            template=template,
            variables=variables,
            changelog=changelog,
            author=author,
        )

    def load_prompt_template(
        self,
        module_name: str,
        version: str | None = None,
    ) -> str:
        """加载提示词模板（代理到 Facade）"""
        return self._prompt_facade.load_prompt_template(module_name, version)

    def switch_prompt_version(
        self,
        module_name: str,
        version: str,
    ) -> None:
        """切换提示词版本（代理到 Facade）"""
        self._prompt_facade.switch_prompt_version(module_name, version)

    def rollback_prompt_version(
        self,
        module_name: str,
        target_version: str | None = None,
        reason: str = "",
    ) -> Any:
        """回滚提示词版本（代理到 Facade）"""
        return self._prompt_facade.rollback_prompt_version(
            module_name=module_name,
            target_version=target_version,
            reason=reason,
        )

    def get_prompt_audit_logs(
        self,
        module_name: str,
    ) -> list[Any]:
        """获取提示词版本审计日志（代理到 Facade）"""
        return self._prompt_facade.get_prompt_audit_logs(module_name)

    def get_prompt_version_history(
        self,
        module_name: str,
    ) -> list[Any]:
        """获取提示词版本历史（代理到 Facade）"""
        return self._prompt_facade.get_prompt_version_history(module_name)

    def submit_prompt_change(
        self,
        module_name: str,
        new_version: str,
        template: str,
        variables: list[str],
        reason: str,
        author: str,
    ) -> Any:
        """提交提示词变更申请（代理到 Facade）"""
        return self._prompt_facade.submit_prompt_change(
            module_name=module_name,
            new_version=new_version,
            template=template,
            variables=variables,
            reason=reason,
            author=author,
        )

    def approve_prompt_change(
        self,
        record_id: str,
        comment: str = "",
    ) -> Any:
        """审批通过提示词变更（代理到 Facade）"""
        return self._prompt_facade.approve_prompt_change(
            record_id=record_id,
            comment=comment,
        )

    def reject_prompt_change(
        self,
        record_id: str,
        reason: str,
    ) -> Any:
        """拒绝提示词变更（代理到 Facade）"""
        return self._prompt_facade.reject_prompt_change(
            record_id=record_id,
            reason=reason,
        )

    def get_prompt_loading_logs(self) -> list[Any]:
        """获取提示词加载日志（代理到 Facade）"""
        return self._prompt_facade.get_prompt_loading_logs()

    # ==================== Phase 8.4: Payload 和 DAG 验证方法 ====================

    def add_payload_validation_rule(
        self,
        decision_type: str,
        required_fields: list[str],
    ) -> None:
        """添加 payload 必填字段验证规则

        参数：
            decision_type: 决策类型
            required_fields: 必填字段列表
        """

        def condition(decision: dict[str, Any]) -> bool:
            # 只验证匹配的决策类型
            if decision.get("action_type") != decision_type:
                return True

            # 检查所有必填字段
            missing_fields = []
            for field_name in required_fields:
                if field_name not in decision or decision[field_name] is None:
                    missing_fields.append(field_name)
                # 检查空列表/空字典（Phase 8.4 增强）
                elif isinstance(decision[field_name], list | dict) and not decision[field_name]:
                    missing_fields.append(field_name)

            # 如果有缺失字段，记录到决策中以便错误消息使用
            if missing_fields:
                decision["_missing_fields"] = missing_fields
                return False

            return True

        rule = Rule(
            id=f"payload_required_{decision_type}",
            name=f"Payload 必填字段验证 ({decision_type})",
            condition=condition,
            priority=1,
            error_message=lambda d: "; ".join(
                [f"缺少必填字段: {field}" for field in d.get("_missing_fields", [])]
            )
            if len(d.get("_missing_fields", [])) > 1
            else f"缺少必填字段: {', '.join(d.get('_missing_fields', []))}",
        )

        self.add_rule(rule)

    def add_payload_type_validation_rule(
        self,
        decision_type: str,
        field_types: dict[str, type | tuple[type, ...]],
        nested_field_types: dict[str, type | tuple[type, ...]] | None = None,
    ) -> None:
        """添加 payload 字段类型验证规则

        参数：
            decision_type: 决策类型
            field_types: 字段类型映射 {字段名: 类型}
            nested_field_types: 嵌套字段类型映射 {字段路径: 类型}，如 {"config.timeout": int}
        """

        def condition(decision: dict[str, Any]) -> bool:
            if decision.get("action_type") != decision_type:
                return True

            type_errors = []

            # 检查顶层字段类型
            for field_name, expected_type in field_types.items():
                if field_name in decision:
                    value = decision[field_name]
                    if not isinstance(value, expected_type):
                        type_name = (
                            expected_type.__name__
                            if isinstance(expected_type, type)
                            else " or ".join(t.__name__ for t in expected_type)
                        )
                        type_errors.append(
                            f"字段 {field_name} 类型错误，期望 {type_name}，实际 {type(value).__name__}"
                        )

            # 检查嵌套字段类型
            if nested_field_types:
                for field_path, expected_type in nested_field_types.items():
                    parts = field_path.split(".")
                    current = decision
                    try:
                        for part in parts:
                            current = current[part]

                        if not isinstance(current, expected_type):
                            type_name = (
                                expected_type.__name__
                                if isinstance(expected_type, type)
                                else " or ".join(t.__name__ for t in expected_type)
                            )
                            type_errors.append(f"字段 {field_path} 类型错误，期望 {type_name}")
                    except (KeyError, TypeError):
                        # 字段不存在，跳过（由必填字段验证处理）
                        pass

            if type_errors:
                decision["_type_errors"] = type_errors
                return False

            return True

        rule = Rule(
            id=f"payload_type_{decision_type}",
            name=f"Payload 字段类型验证 ({decision_type})",
            condition=condition,
            priority=2,
            error_message=lambda d: "; ".join(d.get("_type_errors", [])),
        )

        self.add_rule(rule)

    def add_payload_range_validation_rule(
        self,
        decision_type: str,
        field_ranges: dict[str, dict[str, int | float]],
    ) -> None:
        """添加 payload 字段值范围验证规则

        参数：
            decision_type: 决策类型
            field_ranges: 字段范围映射 {字段路径: {"min": 最小值, "max": 最大值}}
        """

        def condition(decision: dict[str, Any]) -> bool:
            if decision.get("action_type") != decision_type:
                return True

            range_errors = []

            for field_path, range_spec in field_ranges.items():
                parts = field_path.split(".")
                current = decision
                try:
                    for part in parts:
                        current = current[part]

                    # 检查范围（仅对数值类型进行比较）
                    if not isinstance(current, int | float):
                        continue

                    min_val = range_spec.get("min")
                    max_val = range_spec.get("max")

                    if min_val is not None and current < min_val:
                        range_errors.append(f"字段 {field_path} 值 {current} 小于最小值 {min_val}")

                    if max_val is not None and current > max_val:
                        range_errors.append(f"字段 {field_path} 值 {current} 大于最大值 {max_val}")

                except (KeyError, TypeError):
                    # 字段不存在或类型错误，跳过
                    pass

            if range_errors:
                decision["_range_errors"] = range_errors
                return False

            return True

        rule = Rule(
            id=f"payload_range_{decision_type}",
            name=f"Payload 字段范围验证 ({decision_type})",
            condition=condition,
            priority=3,
            error_message=lambda d: "; ".join(d.get("_range_errors", [])),
        )

        self.add_rule(rule)

    def add_payload_enum_validation_rule(
        self,
        decision_type: str,
        field_enums: dict[str, list[str]],
    ) -> None:
        """添加 payload 字段枚举值验证规则

        参数：
            decision_type: 决策类型
            field_enums: 字段枚举映射 {字段名: 允许的值列表}
        """

        def condition(decision: dict[str, Any]) -> bool:
            if decision.get("action_type") != decision_type:
                return True

            enum_errors = []

            for field_name, allowed_values in field_enums.items():
                if field_name in decision:
                    value = decision[field_name]
                    if value not in allowed_values:
                        enum_errors.append(
                            f"字段 {field_name} 值 {value} 不在允许的列表中: {', '.join(allowed_values)}"
                        )

            if enum_errors:
                decision["_enum_errors"] = enum_errors
                return False

            return True

        rule = Rule(
            id=f"payload_enum_{decision_type}",
            name=f"Payload 枚举值验证 ({decision_type})",
            condition=condition,
            priority=4,
            error_message=lambda d: "; ".join(d.get("_enum_errors", [])),
        )

        self.add_rule(rule)

    def add_dag_validation_rule(self) -> None:
        """添加 DAG（有向无环图）验证规则

        验证工作流的节点和边结构：
        - 节点 ID 唯一性
        - 边引用的节点存在性
        - 无循环依赖
        """

        def condition(decision: dict[str, Any]) -> bool:
            # 只验证工作流规划决策
            if decision.get("action_type") != "create_workflow_plan":
                return True

            nodes = decision.get("nodes", [])
            edges = decision.get("edges", [])

            dag_errors = []

            # 1. 检查节点 ID 唯一性
            node_ids = [node.get("node_id") for node in nodes if "node_id" in node]
            if len(node_ids) != len(set(node_ids)):
                duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
                dag_errors.append(f"节点 ID 重复: {', '.join(set(duplicates))}")

            node_id_set = set(node_ids)

            # 2. 检查边引用的节点存在性
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")

                if source and source not in node_id_set:
                    dag_errors.append(f"边的源节点 {source} 不存在")

                if target and target not in node_id_set:
                    dag_errors.append(f"边的目标节点 {target} 不存在")

            # 3. 检测循环依赖（使用 Kahn's 算法拓扑排序）
            # 即使有节点引用错误，也进行循环检测以报告所有问题
            if nodes and edges:
                has_cycle, unvisited = self._detect_cycle_kahn(nodes, edges)
                if has_cycle:
                    dag_errors.append(f"工作流存在循环依赖，涉及节点: {', '.join(unvisited)}")

            if dag_errors:
                decision["_dag_errors"] = dag_errors
                return False

            return True

        rule = Rule(
            id="dag_validation",
            name="DAG 结构验证",
            condition=condition,
            priority=5,
            error_message=lambda d: "; ".join(d.get("_dag_errors", [])),
        )

        self.add_rule(rule)

    def _detect_cycle_kahn(self, nodes: list[dict], edges: list[dict]) -> tuple[bool, list[str]]:
        """使用 Kahn's 算法检测循环依赖

        参数：
            nodes: 节点列表
            edges: 边列表

        返回：
            (是否有循环, 涉及循环的节点列表)
        """
        # 构建邻接表和入度表
        graph: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}

        for node in nodes:
            node_id = node.get("node_id")
            if node_id:
                graph[node_id] = []
                in_degree[node_id] = 0

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target and source in graph and target in graph:
                graph[source].append(target)
                in_degree[target] += 1

        # Kahn's 算法
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        visited = []

        while queue:
            node_id = queue.pop(0)
            visited.append(node_id)

            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否所有节点都被访问
        has_cycle = len(visited) != len(nodes)
        if has_cycle:
            unvisited = [
                node.get("node_id", "") for node in nodes if node.get("node_id") not in visited
            ]
            return True, unvisited

        return False, []

    # ==================== 统计和监控 ====================

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
        # 同时更新本地状态和编排器（向后兼容）
        self._node_failure_strategies[node_id] = strategy
        self._failure_orchestrator.set_node_strategy(node_id, strategy)

    def get_node_failure_strategy(self, node_id: str) -> FailureHandlingStrategy:
        """获取节点的失败处理策略

        如果节点没有特定策略，返回默认策略。

        参数：
            node_id: 节点ID

        返回：
            失败处理策略
        """
        return self._failure_orchestrator.get_node_strategy(node_id)

    def register_workflow_agent(self, workflow_id: str, agent: Any) -> None:
        """注册 WorkflowAgent 实例

        用于在失败处理时调用重试。

        参数：
            workflow_id: 工作流ID
            agent: WorkflowAgent 实例
        """
        # 同时注册到本地和编排器（向后兼容）
        self._workflow_agents[workflow_id] = agent
        self._failure_orchestrator.register_workflow_agent(workflow_id, agent)

    def _sync_config_to_orchestrator(self) -> None:
        """同步 failure_strategy_config 到编排器

        当测试或运行时修改配置时，需要同步到编排器。
        """
        # 更新编排器的配置
        self._failure_orchestrator.config = {
            "default_strategy": self.failure_strategy_config.get(
                "default_strategy", FailureHandlingStrategy.RETRY
            ),
            "max_retries": self.failure_strategy_config.get("max_retries", 3),
            "retry_delay": self.failure_strategy_config.get("retry_delay", 1.0),
        }

    async def handle_node_failure(
        self,
        workflow_id: str,
        node_id: str,
        error_code: Any,
        error_message: str,
    ) -> FailureHandlingResult:
        """处理节点失败（委托给 WorkflowFailureOrchestrator）

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
        # 同步配置到编排器（支持运行时修改）
        self._sync_config_to_orchestrator()

        return await self._failure_orchestrator.handle_node_failure(
            workflow_id=workflow_id,
            node_id=node_id,
            error_code=error_code,
            error_message=error_message,
        )

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

        将消息记录到 message_log（带大小限制防止内存泄漏）。

        参数：
            event: SimpleMessageEvent 实例
        """
        # P1-6 Fix: 使用有界列表防止内存泄漏
        self._add_to_bounded_list(
            self.message_log,
            {
                "user_input": event.user_input,
                "response": event.response,
                "intent": event.intent,
                "confidence": event.confidence,
                "session_id": event.session_id,
                "timestamp": event.timestamp,
            },
            MAX_MESSAGE_LOG_SIZE,
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

    # ==================== Phase 3: 子Agent管理（代理到 SubAgentOrchestrator）====================

    # 向后兼容属性（只读代理到 orchestrator 内部状态）
    @property
    def subagent_registry(self) -> Any:
        """子Agent注册表（向后兼容，只读）"""
        return self._subagent_orchestrator._registry

    @property
    def active_subagents(self) -> dict[str, dict[str, Any]]:
        """活跃子Agent状态（向后兼容，只读）"""
        return self._subagent_orchestrator._active_subagents

    @property
    def subagent_results(self) -> dict[str, list[dict[str, Any]]]:
        """子Agent执行结果（向后兼容，只读）"""
        return self._subagent_orchestrator._results

    def register_subagent_type(self, agent_type: Any, agent_class: type) -> None:
        """注册子Agent类型（代理到 SubAgentOrchestrator）"""
        self._subagent_orchestrator.register_type(agent_type, agent_class)

    def get_registered_subagent_types(self) -> list[Any]:
        """获取已注册的子Agent类型列表（代理到 SubAgentOrchestrator）"""
        return self._subagent_orchestrator.list_types()

    def start_subagent_listener(self) -> None:
        """启动子Agent事件监听器（代理到 SubAgentOrchestrator）"""
        self._subagent_orchestrator.start_listening()

    async def handle_spawn_subagent_event(self, event: Any) -> Any:
        """处理子Agent生成事件（代理到 SubAgentOrchestrator）"""
        return await self._subagent_orchestrator.handle_spawn_event(event)

    async def execute_subagent(
        self,
        subagent_type: str,
        task_payload: dict[str, Any],
        context: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> Any:
        """执行子Agent任务（代理到 SubAgentOrchestrator）"""
        return await self._subagent_orchestrator.execute(
            subagent_type=subagent_type,
            task_payload=task_payload,
            context=context,
            session_id=session_id,
        )

    def get_subagent_status(self, subagent_id: str) -> dict[str, Any] | None:
        """获取子Agent状态（代理到 SubAgentOrchestrator）"""
        return self._subagent_orchestrator.get_status(subagent_id)

    def get_session_subagent_results(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话的子Agent执行结果列表（代理到 SubAgentOrchestrator）"""
        return self._subagent_orchestrator.get_session_results(session_id)

    # ==================== Phase 4: 容器执行监控（代理到 ContainerExecutionMonitor）====================

    # 向后兼容属性（只读代理到 monitor 内部状态）
    @property
    def container_executions(self) -> dict[str, list[dict[str, Any]]]:
        """容器执行记录（向后兼容，只读）"""
        return self._container_monitor.container_executions

    @property
    def container_logs(self) -> dict[str, list[dict[str, Any]]]:
        """容器日志（向后兼容，只读）"""
        return self._container_monitor.container_logs

    @property
    def _is_listening_container_events(self) -> bool:
        """监听状态（向后兼容，只读）"""
        return self._container_monitor._is_listening_container_events

    def start_container_execution_listening(self) -> None:
        """启动容器执行事件监听（代理到 ContainerExecutionMonitor）

        订阅容器执行相关事件。
        """
        self._container_monitor.start_container_execution_listening()

    def stop_container_execution_listening(self) -> None:
        """停止容器执行事件监听（代理到 ContainerExecutionMonitor）"""
        self._container_monitor.stop_container_execution_listening()

    async def _handle_container_started(self, event: Any) -> None:
        """处理容器执行开始事件（代理到 ContainerExecutionMonitor）"""
        await self._container_monitor._handle_container_started(event)

    async def _handle_container_completed(self, event: Any) -> None:
        """处理容器执行完成事件（代理到 ContainerExecutionMonitor）"""
        await self._container_monitor._handle_container_completed(event)

    async def _handle_container_log(self, event: Any) -> None:
        """处理容器日志事件（代理到 ContainerExecutionMonitor）"""
        await self._container_monitor._handle_container_log(event)

    def get_workflow_container_executions(self, workflow_id: str) -> list[dict[str, Any]]:
        """获取工作流的容器执行记录（代理到 ContainerExecutionMonitor）

        参数：
            workflow_id: 工作流ID

        返回：
            容器执行记录列表
        """
        return self._container_monitor.get_workflow_container_executions(workflow_id)

    def get_container_logs(self, container_id: str) -> list[dict[str, Any]]:
        """获取容器日志（代理到 ContainerExecutionMonitor）

        参数：
            container_id: 容器ID

        返回：
            日志列表
        """
        return self._container_monitor.get_container_logs(container_id)

    def get_container_execution_statistics(self) -> dict[str, Any]:
        """获取容器执行统计（代理到 ContainerExecutionMonitor）

        返回：
            包含执行统计的字典
        """
        return self._container_monitor.get_container_execution_statistics()

    def reset_container_executions(self) -> None:
        """重置所有容器执行记录（代理到 ContainerExecutionMonitor）

        用于测试或清理场景。
        """
        self._container_monitor.reset_executions()

    def reset_container_logs(self) -> None:
        """重置所有容器日志（代理到 ContainerExecutionMonitor）

        用于测试或清理场景。
        """
        self._container_monitor.reset_logs()

    def reset_all_container_data(self) -> None:
        """重置所有容器数据（代理到 ContainerExecutionMonitor）

        包括执行记录和日志。用于测试或清理场景。
        """
        self._container_monitor.reset_all()

    # ==================== Phase 34.9: 知识库集成（委托到 KnowledgeRetrievalOrchestrator）====================

    async def retrieve_knowledge(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> Any:
        """按查询检索知识（委托）

        参数：
            query: 查询文本
            workflow_id: 工作流ID（可选，用于过滤和缓存）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        return await self._knowledge_retrieval_orchestrator.retrieve_knowledge(
            query=query,
            workflow_id=workflow_id,
            top_k=top_k,
        )

    async def retrieve_knowledge_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> Any:
        """按错误类型检索解决方案（委托）

        参数：
            error_type: 错误类型
            error_message: 错误消息（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        return await self._knowledge_retrieval_orchestrator.retrieve_knowledge_by_error(
            error_type=error_type,
            error_message=error_message,
            top_k=top_k,
        )

    async def retrieve_knowledge_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> Any:
        """按目标检索相关知识（委托）

        参数：
            goal_text: 目标描述文本
            workflow_id: 工作流ID（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        return await self._knowledge_retrieval_orchestrator.retrieve_knowledge_by_goal(
            goal_text=goal_text,
            workflow_id=workflow_id,
            top_k=top_k,
        )

    def get_cached_knowledge(self, workflow_id: str) -> Any:
        """获取缓存的知识引用（委托）

        参数：
            workflow_id: 工作流ID

        返回：
            KnowledgeReferences 或 None
        """
        return self._knowledge_retrieval_orchestrator.get_cached_knowledge(workflow_id)

    def clear_cached_knowledge(self, workflow_id: str) -> None:
        """清除缓存的知识引用（委托）

        参数：
            workflow_id: 工作流ID
        """
        self._knowledge_retrieval_orchestrator.clear_cached_knowledge(workflow_id)

    async def enrich_context_with_knowledge(
        self,
        workflow_id: str,
        goal: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """根据目标和错误丰富上下文（委托）

        自动检索与目标和错误相关的知识，并将结果附加到上下文中。

        参数：
            workflow_id: 工作流ID
            goal: 任务目标（可选）
            errors: 错误列表（可选），每个错误包含 error_type 和 message

        返回：
            包含 knowledge_references 的上下文字典
        """
        return await self._knowledge_retrieval_orchestrator.enrich_context_with_knowledge(
            workflow_id=workflow_id,
            goal=goal,
            errors=errors,
        )

    async def inject_knowledge_to_context(
        self,
        workflow_id: str,
        goal: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        """向现有压缩上下文注入知识（委托）

        参数：
            workflow_id: 工作流ID
            goal: 任务目标（可选）
            errors: 错误列表（可选）
        """
        await self._knowledge_retrieval_orchestrator.inject_knowledge_to_context(
            workflow_id=workflow_id,
            goal=goal,
            errors=errors,
        )

    def get_knowledge_enhanced_summary(self, workflow_id: str) -> str | None:
        """获取知识增强的上下文摘要（委托）

        返回包含知识引用信息的人类可读摘要。

        参数：
            workflow_id: 工作流ID

        返回：
            摘要文本，如果不存在返回None
        """
        return self._knowledge_retrieval_orchestrator.get_knowledge_enhanced_summary(workflow_id)

    def get_context_for_conversation_agent(
        self,
        workflow_id: str,
    ) -> dict[str, Any] | None:
        """获取用于对话Agent的上下文（委托）

        将压缩上下文转换为对话Agent可用的格式。

        参数：
            workflow_id: 工作流ID

        返回：
            对话Agent可用的上下文字典，如果不存在返回None
        """
        return self._knowledge_retrieval_orchestrator.get_context_for_conversation_agent(
            workflow_id
        )

    async def auto_enrich_context_on_error(
        self,
        workflow_id: str,
        error_type: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """错误发生时自动丰富上下文（委托）

        当节点执行失败时，自动检索相关的错误解决方案知识。

        参数：
            workflow_id: 工作流ID
            error_type: 错误类型
            error_message: 错误消息（可选）

        返回：
            丰富后的上下文字典
        """
        return await self._knowledge_retrieval_orchestrator.auto_enrich_context_on_error(
            workflow_id=workflow_id,
            error_type=error_type,
            error_message=error_message,
        )

    def enable_auto_knowledge_retrieval(self) -> None:
        """启用自动知识检索（委托）

        启用后，在节点失败和反思事件时会自动检索相关知识。
        """
        self._knowledge_retrieval_orchestrator.enable_auto_knowledge_retrieval()
        # 同步 CoordinatorAgent 的标志（向后兼容）
        self._auto_knowledge_retrieval_enabled = True

    def disable_auto_knowledge_retrieval(self) -> None:
        """禁用自动知识检索（委托）"""
        self._knowledge_retrieval_orchestrator.disable_auto_knowledge_retrieval()
        # 同步 CoordinatorAgent 的标志（向后兼容）
        self._auto_knowledge_retrieval_enabled = False

    async def handle_node_failure_with_knowledge(
        self,
        workflow_id: str,
        node_id: str,
        error_type: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """处理节点失败并检索相关知识（委托）

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
        return await self._knowledge_retrieval_orchestrator.handle_node_failure_with_knowledge(
            workflow_id=workflow_id,
            node_id=node_id,
            error_type=error_type,
            error_message=error_message,
        )

    async def handle_reflection_with_knowledge(
        self,
        workflow_id: str,
        assessment: str,
        confidence: float = 0.0,
        recommendations: list[str] | None = None,
    ) -> dict[str, Any]:
        """处理反思事件并检索相关知识（委托）

        当收到反思事件时调用此方法，会基于工作流目标检索相关知识。

        参数：
            workflow_id: 工作流ID
            assessment: 评估内容
            confidence: 置信度
            recommendations: 建议列表（可选）

        返回：
            包含知识引用的结果字典
        """
        return await self._knowledge_retrieval_orchestrator.handle_reflection_with_knowledge(
            workflow_id=workflow_id,
            assessment=assessment,
            confidence=confidence,
            recommendations=recommendations,
        )

    # ==================== Phase 5: 执行总结管理 ====================

    # ==================== Phase 34.7: 执行总结管理（委托到 ExecutionSummaryManager）====================

    def set_channel_bridge(self, bridge: Any) -> None:
        """设置通信桥接器

        参数：
            bridge: AgentChannelBridge 实例
        """
        self._summary_manager.set_channel_bridge(bridge)

    def record_execution_summary(self, summary: Any) -> None:
        """同步记录执行总结

        参数：
            summary: ExecutionSummary 实例
        """
        self._summary_manager.record_execution_summary(summary)

    async def record_execution_summary_async(self, summary: Any) -> None:
        """异步记录执行总结并发布事件

        参数：
            summary: ExecutionSummary 实例
        """
        await self._summary_manager.record_execution_summary_async(summary)

    def get_execution_summary(self, workflow_id: str) -> Any | None:
        """获取执行总结

        参数：
            workflow_id: 工作流ID

        返回：
            ExecutionSummary 实例，如果不存在返回 None
        """
        return self._summary_manager.get_execution_summary(workflow_id)

    def get_summary_statistics(self) -> dict[str, Any]:
        """获取总结统计

        返回：
            包含统计信息的字典
        """
        return self._summary_manager.get_summary_statistics()

    async def record_and_push_summary(self, summary: Any) -> None:
        """记录总结并推送到前端

        参数：
            summary: ExecutionSummary 实例
        """
        await self._summary_manager.record_and_push_summary(summary)

    def get_all_summaries(self) -> dict[str, Any]:
        """获取所有总结

        返回：
            工作流ID到总结的映射
        """
        return self._summary_manager.get_all_summaries()

    # ==================== Phase 34.10: 统一日志集成（委托到 UnifiedLogIntegration）====================

    def get_merged_logs(self) -> list[dict[str, Any]]:
        """获取合并后的多源日志

        合并以下日志源：
        1. UnifiedLogCollector 的日志
        2. message_log（消息日志）
        3. container_logs（容器日志）

        返回：
            统一格式的日志列表，按时间从旧到新排序
            每条日志包含：
            - level: 日志级别
            - source: 日志来源
            - message: 日志消息
            - timestamp: 时间戳（ISO格式）
            - context: 上下文信息字典
        """
        return self._log_integration.get_merged_logs()

    # ==================== Phase 34.8: PowerCompressor 包装（委托到 PowerCompressorFacade）====================

    async def compress_and_store(self, summary: Any) -> Any:
        """压缩执行总结并存储

        使用 PowerCompressor 压缩执行总结，生成八段格式的压缩上下文，
        并存储到内部缓存中。

        参数：
            summary: ExecutionSummary 实例

        返回：
            PowerCompressedContext 实例
        """
        return await self._power_compressor_facade.compress_and_store(summary)

    def store_compressed_context(self, workflow_id: str, data: dict[str, Any]) -> None:
        """存储压缩上下文

        直接存储已格式化的压缩上下文数据。

        参数：
            workflow_id: 工作流ID
            data: 压缩上下文数据字典
        """
        self._power_compressor_facade.store_compressed_context(workflow_id, data)

    def query_compressed_context(self, workflow_id: str) -> dict[str, Any] | None:
        """查询压缩上下文

        参数：
            workflow_id: 工作流ID

        返回：
            压缩上下文字典，如果不存在返回 None
        """
        return self._power_compressor_facade.query_compressed_context(workflow_id)

    def query_subtask_errors(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询子任务错误

        参数：
            workflow_id: 工作流ID

        返回：
            子任务错误列表
        """
        return self._power_compressor_facade.query_subtask_errors(workflow_id)

    def query_unresolved_issues(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询未解决问题

        参数：
            workflow_id: 工作流ID

        返回：
            未解决问题列表
        """
        return self._power_compressor_facade.query_unresolved_issues(workflow_id)

    def query_next_plan(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询后续计划

        参数：
            workflow_id: 工作流ID

        返回：
            后续计划列表
        """
        return self._power_compressor_facade.query_next_plan(workflow_id)

    def get_context_for_conversation(self, workflow_id: str) -> dict[str, Any] | None:
        """获取用于对话Agent下一轮输入的上下文

        返回包含所有八段压缩信息的上下文，供对话Agent引用。

        参数：
            workflow_id: 工作流ID

        返回：
            对话Agent可用的上下文字典，如果不存在返回 None
        """
        return self._power_compressor_facade.get_context_for_conversation(workflow_id)

    def get_knowledge_for_conversation(self, workflow_id: str) -> list[dict[str, Any]]:
        """获取用于对话Agent引用的知识来源

        参数：
            workflow_id: 工作流ID

        返回：
            知识来源列表
        """
        return self._power_compressor_facade.get_knowledge_for_conversation(workflow_id)

    def get_power_compression_statistics(self) -> dict[str, Any]:
        """获取强力压缩器统计

        返回：
            包含统计信息的字典
        """
        return self._power_compressor_facade.get_statistics()

    # ==================== 扩展模块：知识库 CRUD ====================

    def create_knowledge(
        self,
        title: str,
        content: str,
        category: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """创建知识条目

        参数：
            title: 标题
            content: 内容
            category: 类别
            tags: 标签列表（可选）
            metadata: 元数据（可选）

        返回：
            新创建条目的 ID
        """
        entry_id = self.knowledge_manager.create(
            title=title,
            content=content,
            category=category,
            tags=tags,
            metadata=metadata,
        )

        self.log_collector.info(
            "CoordinatorAgent",
            f"创建知识条目: {title}",
            {"entry_id": entry_id, "category": category},
        )

        return entry_id

    def get_knowledge(self, entry_id: str) -> dict[str, Any] | None:
        """获取知识条目

        参数：
            entry_id: 条目 ID

        返回：
            条目字典，如果不存在返回 None
        """
        return self.knowledge_manager.get(entry_id)

    def update_knowledge(
        self,
        entry_id: str,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """更新知识条目

        参数：
            entry_id: 条目 ID
            title: 新标题（可选）
            content: 新内容（可选）
            category: 新类别（可选）
            tags: 新标签（可选）
            metadata: 新元数据（可选）

        返回：
            是否更新成功
        """
        success = self.knowledge_manager.update(
            entry_id,
            title=title,
            content=content,
            category=category,
            tags=tags,
            metadata=metadata,
        )

        if success:
            self.log_collector.info(
                "CoordinatorAgent",
                f"更新知识条目: {entry_id}",
                {"entry_id": entry_id},
            )

        return success

    def delete_knowledge(self, entry_id: str) -> bool:
        """删除知识条目

        参数：
            entry_id: 条目 ID

        返回：
            是否删除成功
        """
        success = self.knowledge_manager.delete(entry_id)

        if success:
            self.log_collector.info(
                "CoordinatorAgent",
                f"删除知识条目: {entry_id}",
                {"entry_id": entry_id},
            )

        return success

    def search_knowledge(self, keyword: str) -> list[dict[str, Any]]:
        """按关键词搜索知识条目

        参数：
            keyword: 搜索关键词

        返回：
            匹配的条目列表
        """
        return self.knowledge_manager.search(keyword)

    # ==================== 扩展模块：动态告警规则 ====================

    def add_alert_rule(
        self,
        name: str,
        rule_type: str,
        severity: str = "warning",
        **kwargs: Any,
    ) -> str:
        """添加告警规则

        参数：
            name: 规则名称
            rule_type: 规则类型 (threshold/pattern/rate)
            severity: 严重性 (info/warning/critical)
            **kwargs: 规则配置（取决于规则类型）

        返回：
            规则 ID
        """
        rule_id = self.alert_rule_manager.create_rule(
            name=name,
            rule_type=rule_type,
            severity=severity,
            **kwargs,
        )

        self.log_collector.info(
            "CoordinatorAgent",
            f"添加告警规则: {name}",
            {"rule_id": rule_id, "rule_type": rule_type, "severity": severity},
        )

        return rule_id

    def remove_alert_rule(self, rule_id: str) -> bool:
        """删除告警规则

        参数：
            rule_id: 规则 ID

        返回：
            是否删除成功
        """
        return self.alert_rule_manager.delete_rule(rule_id)

    def get_system_status_with_alerts(self) -> dict[str, Any]:
        """获取带告警评估的系统状态

        自动评估所有告警规则，返回系统状态和触发的告警。

        返回：
            系统状态字典，包含 alerts 字段
        """
        # 获取基本状态
        status = self.get_system_status()

        # 计算指标
        total = self._statistics.get("total", 0)
        rejected = self._statistics.get("rejected", 0)
        rejection_rate = rejected / total if total > 0 else 0.0

        # 评估告警规则
        metrics = {
            "rejection_rate": rejection_rate,
            "total_decisions": total,
            "rejected_decisions": rejected,
            "passed_decisions": self._statistics.get("passed", 0),
        }

        alerts = self.alert_rule_manager.evaluate(metrics)

        status["alerts"] = alerts
        status["alert_rules_count"] = len(self.alert_rule_manager.rules)

        return status

    # ==================== 监督模块代理方法 ====================

    def supervise_input(self, text: str) -> dict[str, Any]:
        """监督用户输入

        对输入文本进行全面检查，包括偏见、有害内容、稳定性检测。

        参数：
            text: 用户输入文本

        返回：
            包含检查结果的字典：
            - passed: bool - 是否通过检查
            - issues: list - 检测到的问题列表
            - action: str - 建议的动作 (allow/warn/block/terminate)
        """
        from src.domain.services.supervision_modules import ComprehensiveCheckResult

        result: ComprehensiveCheckResult = self.conversation_supervision.check_all(text)

        # 记录日志
        if result.passed:
            self.log_collector.debug(
                "CoordinatorAgent",
                "输入检查通过",
                {"text_length": len(text)},
            )
        else:
            self.log_collector.warning(
                "CoordinatorAgent",
                f"输入检查发现 {len(result.issues)} 个问题",
                {
                    "text_length": len(text),
                    "issues": [issue.category for issue in result.issues],
                    "action": result.action,
                },
            )
            # 记录干预事件
            for issue in result.issues:
                self._supervision_coordinator.record_intervention(
                    intervention_type=issue.category,
                    reason=issue.message,
                    source="conversation_supervision",
                    target_id="user_input",
                    severity=issue.severity,
                )

        return {
            "passed": result.passed,
            "issues": [
                {
                    "detected": issue.detected,
                    "category": issue.category,
                    "severity": issue.severity,
                    "message": issue.message,
                }
                for issue in result.issues
            ],
            "action": result.action,
        }

    def record_workflow_resource(
        self,
        workflow_id: str,
        node_id: str,
        memory_mb: float,
        cpu_percent: float,
        duration_seconds: float,
    ) -> None:
        """记录工作流节点的资源使用

        参数：
            workflow_id: 工作流 ID
            node_id: 节点 ID
            memory_mb: 内存使用 (MB)
            cpu_percent: CPU 使用百分比
            duration_seconds: 执行时长 (秒)
        """
        self.efficiency_monitor.record_resource_usage(
            workflow_id=workflow_id,
            node_id=node_id,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            duration_seconds=duration_seconds,
        )

        self.log_collector.debug(
            "CoordinatorAgent",
            f"记录资源使用: {workflow_id}/{node_id}",
            {
                "memory_mb": memory_mb,
                "cpu_percent": cpu_percent,
                "duration_seconds": duration_seconds,
            },
        )

    def check_workflow_efficiency(self, workflow_id: str) -> list[dict[str, Any]]:
        """检查工作流效率

        评估工作流的资源使用是否超过阈值。

        参数：
            workflow_id: 工作流 ID

        返回：
            告警列表，每个告警包含 type, message, severity
        """
        alerts = self.efficiency_monitor.check_thresholds(workflow_id)

        if alerts:
            self.log_collector.warning(
                "CoordinatorAgent",
                f"工作流效率告警: {workflow_id}",
                {"alert_count": len(alerts), "alerts": alerts},
            )

        return alerts

    def add_supervision_strategy(
        self,
        name: str,
        trigger_conditions: list[str],
        action: str,
        priority: int = 10,
        **kwargs: Any,
    ) -> str:
        """添加监督策略

        注册一个新的监督策略到策略库。

        参数：
            name: 策略名称
            trigger_conditions: 触发条件列表 (如 ["bias", "harmful"])
            action: 动作类型 (warn/block/terminate)
            priority: 优先级 (数字越小优先级越高)
            **kwargs: 额外配置

        返回：
            策略 ID
        """
        strategy_id = self.strategy_repository.register(
            name=name,
            trigger_conditions=trigger_conditions,
            action=action,
            priority=priority,
            **kwargs,
        )

        self.log_collector.info(
            "CoordinatorAgent",
            f"添加监督策略: {name}",
            {
                "strategy_id": strategy_id,
                "trigger_conditions": trigger_conditions,
                "action": action,
            },
        )

        return strategy_id

    def get_intervention_events(self) -> list[dict[str, Any]]:
        """获取干预事件历史

        返回：
            干预事件列表
        """
        events = self._supervision_coordinator.get_intervention_events()
        return [
            {
                "intervention_type": e.intervention_type,
                "reason": e.reason,
                "source": e.source,
                "target_id": e.target_id,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in events
        ]

    # ==================== Section 27: A/B 测试与实验管理（代理到 ExperimentOrchestrator）====================

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        module_name: str,
        control_version: str,
        treatment_version: str,
        traffic_allocation: dict[str, int] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """创建 A/B 测试实验（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.create_experiment(
            experiment_id=experiment_id,
            name=name,
            module_name=module_name,
            control_version=control_version,
            treatment_version=treatment_version,
            traffic_allocation=traffic_allocation,
            description=description,
        )

    def create_multi_variant_experiment(
        self,
        experiment_id: str,
        name: str,
        module_name: str,
        variants: dict[str, dict[str, Any]],
        description: str = "",
    ) -> dict[str, Any]:
        """创建多变体实验（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.create_multi_variant_experiment(
            experiment_id=experiment_id,
            name=name,
            module_name=module_name,
            variants=variants,
            description=description,
        )

    def start_experiment(self, experiment_id: str) -> bool:
        """启动实验（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.start_experiment(experiment_id)

    def pause_experiment(self, experiment_id: str) -> bool:
        """暂停实验（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.pause_experiment(experiment_id)

    def complete_experiment(self, experiment_id: str) -> bool:
        """完成实验（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.complete_experiment(experiment_id)

    def get_experiment_variant(self, experiment_id: str, user_id: str) -> str | None:
        """获取用户的实验变体（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.get_experiment_variant(experiment_id, user_id)

    def get_prompt_version_for_experiment(
        self,
        module_name: str,
        user_id: str,
    ) -> str | None:
        """获取用户在模块实验中应使用的提示词版本（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.get_prompt_version_for_experiment(module_name, user_id)

    def record_experiment_metrics(
        self,
        module_name: str,
        user_id: str,
        success: bool,
        duration_ms: int = 0,
        satisfaction: int = 0,
    ) -> None:
        """记录实验指标（代理到 ExperimentOrchestrator）"""
        self._experiment_orchestrator.record_experiment_metrics(
            module_name=module_name,
            user_id=user_id,
            success=success,
            duration_ms=duration_ms,
            satisfaction=satisfaction,
        )

    def get_experiment_report(self, experiment_id: str) -> dict[str, Any]:
        """获取实验报告（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.get_experiment_report(experiment_id)

    def get_experiment_metrics_summary(self, experiment_id: str) -> dict[str, Any]:
        """获取实验指标汇总（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.get_experiment_metrics_summary(experiment_id)

    def create_rollout_plan(
        self,
        experiment_id: str,
        module_name: str,
        new_version: str,
        stages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """创建灰度发布计划（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.create_rollout_plan(
            experiment_id=experiment_id,
            module_name=module_name,
            new_version=new_version,
            stages=stages,
        )

    def advance_rollout_stage(self, experiment_id: str) -> dict[str, Any]:
        """推进灰度发布阶段（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.advance_rollout_stage(experiment_id)

    def rollback_rollout(self, experiment_id: str) -> dict[str, Any]:
        """回滚灰度发布（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.rollback_rollout(experiment_id)

    def should_rollback_rollout(self, experiment_id: str) -> bool:
        """检查是否应该回滚（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.should_rollback_rollout(experiment_id)

    def get_experiment_audit_logs(self, experiment_id: str) -> list[dict[str, Any]]:
        """获取实验审计日志（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.get_experiment_audit_logs(experiment_id)

    def list_experiments(self, status: str | None = None) -> list[dict[str, Any]]:
        """列出所有实验（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.list_experiments(status=status)

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        """获取实验详情（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.get_experiment(experiment_id)

    def check_experiment_metrics_threshold(
        self,
        experiment_id: str,
        variant: str,
        thresholds: dict[str, float],
    ) -> dict[str, Any]:
        """检查实验指标是否达到阈值（代理到 ExperimentOrchestrator）"""
        return self._experiment_orchestrator.check_experiment_metrics_threshold(
            experiment_id=experiment_id,
            variant=variant,
            thresholds=thresholds,
        )


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

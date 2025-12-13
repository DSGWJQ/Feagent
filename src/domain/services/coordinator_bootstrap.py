"""CoordinatorBootstrap - 依赖装配模块

本模块提供 Builder + Facade 组合的依赖装配实现，用于将 CoordinatorAgent 的
复杂初始化逻辑提取为可测试、可复用的独立服务。

设计模式：
- Builder Pattern：按阶段构建依赖（base_state → infra → failure → knowledge → ...）
- Facade Pattern：通过 CoordinatorWiring 封装装配结果
- Gateway Pattern：通过内部 accessor 解耦日志集成依赖

职责：
- 依赖创建：创建所有 orchestrator、service、logger 实例
- 依赖注入：正确传递共享实例（log_collector、event_bus）
- 别名管理：维护向后兼容的属性别名
- 顺序控制：按照依赖关系正确初始化组件

使用示例：
    config = CoordinatorConfig(event_bus=event_bus)
    bootstrap = CoordinatorBootstrap(config=config)
    wiring = bootstrap.assemble()

    # 使用装配结果
    log_collector = wiring.log_collector
    orchestrators = wiring.orchestrators
    aliases = wiring.aliases

从 CoordinatorAgent 提取（Phase 34.11）：
- 原 __init__ 方法：368-630 行（263 行）
- 初始化顺序：14 个关键步骤
- 向后兼容：所有属性别名保留
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.domain.services.container_execution_monitor import ContainerExecutionMonitor
from src.domain.services.execution_summary_manager import ExecutionSummaryManager
from src.domain.services.experiment_orchestrator import ExperimentOrchestrator
from src.domain.services.knowledge_manager import KnowledgeManager
from src.domain.services.knowledge_retrieval_orchestrator import (
    KnowledgeRetrievalOrchestrator,
)
from src.domain.services.power_compressor_facade import PowerCompressorFacade
from src.domain.services.prompt_version_facade import PromptVersionFacade
from src.domain.services.subagent_orchestrator import SubAgentOrchestrator
from src.domain.services.supervision_modules import SupervisionCoordinator
from src.domain.services.unified_log_collector import UnifiedLogCollector
from src.domain.services.unified_log_integration import UnifiedLogIntegration
from src.domain.services.workflow_failure_orchestrator import (
    FailureHandlingStrategy,
    WorkflowFailureOrchestrator,
)

# =====================================================================
# 常量与默认配置（保持与 CoordinatorAgent 一致）
# =====================================================================

DEFAULT_REJECTION_RATE_THRESHOLD = 0.5
"""默认决策拒绝率阈值"""

MAX_CONTAINER_LOGS_SIZE = 500
"""容器日志最大条目数"""

DEFAULT_FAILURE_STRATEGY_CONFIG = {
    "default_strategy": FailureHandlingStrategy.RETRY,
    "max_retries": 3,
    "retry_delay": 1.0,
}
"""默认失败处理策略配置"""

logger = logging.getLogger(__name__)


# =====================================================================
# 内部访问器（Gateway Pattern）
# =====================================================================


class _MessageLogAccessor:
    """Message Log 访问器

    提供对 message_log 列表的只读访问接口，用于 UnifiedLogIntegration。
    """

    def __init__(self, messages_ref: list[dict[str, Any]]) -> None:
        """初始化访问器

        参数：
            messages_ref: message_log 列表引用（append-only）
        """
        self._messages = messages_ref

    def get_messages(self) -> list[dict[str, Any]]:
        """获取消息日志列表

        返回：
            消息日志列表（只读访问）
        """
        return self._messages


class _ContainerLogAccessor:
    """Container Log 访问器

    提供对 container_logs 字典的只读访问接口，用于 UnifiedLogIntegration。
    """

    def __init__(self, container_monitor: Any) -> None:
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


class _ContextGateway:
    """Context Gateway for KnowledgeRetrievalOrchestrator

    提供对 _compressed_contexts 的访问接口，解耦编排器与内部状态。
    """

    def __init__(self, contexts_dict: dict[str, Any]) -> None:
        """初始化 Gateway

        参数：
            contexts_dict: 压缩上下文字典引用 {workflow_id: CompressedContext}
        """
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


# =====================================================================
# 配置与装配结果数据类
# =====================================================================


@dataclass
class CoordinatorConfig:
    """Coordinator 配置

    包含所有可配置的参数，用于 Bootstrap 初始化。

    属性：
        event_bus: 事件总线实例（可选）
        rejection_rate_threshold: 决策拒绝率阈值
        circuit_breaker_config: 熔断器配置（可选）
        context_bridge: 上下文桥接器（可选）
        failure_strategy_config: 失败处理策略配置（可选）
        context_compressor: 上下文压缩器（可选）
        snapshot_manager: 快照管理器（可选）
        knowledge_retriever: 知识检索器（可选）
        rule_engine_facade: 规则引擎 Facade 实例（可选注入，P1-1 Step 3）
        alert_rule_manager_enabled: 是否启用告警规则管理器（P1-1 Step 3）

    注意：
        P1-1 Step 3 Critical Fix #4: 新增字段放末尾，保持位置参数向后兼容
    """

    event_bus: Any | None = None
    rejection_rate_threshold: float = DEFAULT_REJECTION_RATE_THRESHOLD
    circuit_breaker_config: Any | None = None
    context_bridge: Any | None = None
    failure_strategy_config: dict[str, Any] | None = None
    context_compressor: Any | None = None
    snapshot_manager: Any | None = None
    knowledge_retriever: Any | None = None
    # P1-1 Step 3 新增字段（放末尾保持兼容）
    rule_engine_facade: Any | None = None
    alert_rule_manager_enabled: bool = True


@dataclass
class CoordinatorWiring:
    """Coordinator 装配结果

    包含所有装配完成的组件、编排器和别名。

    属性：
        log_collector: UnifiedLogCollector 实例（共享单例）
        orchestrators: 编排器字典 {name: orchestrator_instance}
        aliases: 向后兼容别名字典 {alias_name: object_reference}
        base_state: 基础状态字典（workflow_states、message_log等运行时容器）
        config: 原始配置（可选，用于追踪）
    """

    log_collector: Any
    orchestrators: dict[str, Any]
    aliases: dict[str, Any]
    base_state: dict[str, Any]
    config: CoordinatorConfig | None = None


# =====================================================================
# Bootstrap Builder
# =====================================================================


class CoordinatorBootstrap:
    """Coordinator 依赖装配器（Builder Pattern）

    按阶段构建 Coordinator 的所有依赖，确保：
    - 初始化顺序正确（按依赖关系排序）
    - 共享实例唯一（log_collector、event_bus）
    - 别名完整保留（向后兼容）

    构建阶段（14 步）：
    1. build_base_state: 基础状态（rules、statistics、workflow_states、flags）
    2. build_infra: 基础设施（log_collector、container_monitor、log_integration）
    3. build_failure_layer: 失败处理层（WorkflowFailureOrchestrator）
    4. build_knowledge_layer: 知识层（KnowledgeManager、KnowledgeRetrievalOrchestrator）
    5. build_agent_coordination: Agent 协调层（SubAgentOrchestrator、SupervisionCoordinator）
    6. build_prompt_experiment: 提示词与实验层（PromptVersionFacade、ExperimentOrchestrator）
    7. build_save_flow: 保存请求流程（SaveRequestOrchestrator，仅当 event_bus 不为 None）
    8. build_guardians: 守护层（SafetyGuard、ContextInjectionManager、SupervisionModule、Intervention）

    使用示例：
        config = CoordinatorConfig(event_bus=event_bus)
        bootstrap = CoordinatorBootstrap(config=config)
        wiring = bootstrap.assemble()
    """

    def __init__(self, config: CoordinatorConfig | dict[str, Any] | Any) -> None:
        """初始化 Bootstrap（P1-1 步骤2：支持新Config）

        参数：
            config: Coordinator 配置，支持三种类型：
                - CoordinatorAgentConfig（新）
                - CoordinatorConfig（旧）
                - dict[str, Any]（旧）
        """
        self.config = self._normalize_config(config)

    def _validate_agent_config(self, agent_config: Any) -> None:
        """对 CoordinatorAgentConfig 执行校验（P1-1 Step 2 Critical Fix #3）

        参数：
            agent_config: CoordinatorAgentConfig 实例

        异常：
            ValueError: 配置验证失败
        """
        if not hasattr(agent_config, "validate"):
            return

        # 根据 event_bus 是否存在决定严格程度
        strict = getattr(agent_config, "event_bus", None) is not None
        try:
            agent_config.validate(strict=strict)
        except TypeError:
            # 兼容旧版 validate() 无 strict 参数的情况
            agent_config.validate()
        except ValueError as exc:
            raise ValueError(
                "Invalid CoordinatorAgentConfig passed to CoordinatorBootstrap. "
                "Fix the config or pass a legacy CoordinatorConfig/dict instead."
            ) from exc

    def _normalize_config(self, config: Any) -> CoordinatorConfig:
        """归一化配置为 CoordinatorConfig

        支持三种输入类型：
        1. CoordinatorAgentConfig（新）→ 映射到旧 CoordinatorConfig
        2. CoordinatorConfig（旧）→ 直接使用
        3. dict（旧）→ 构造 CoordinatorConfig

        参数：
            config: 输入配置

        返回：
            归一化的 CoordinatorConfig

        注意：
            - P1-1 Step 2 Critical Fix #1: 使用 isinstance() 显式检查类型，避免 duck typing 误判
            - P1-1 Step 2 Critical Fix #3: 调用 validate() 进行配置校验（支持宽松模式）
            - failure schema 转换为 Bootstrap 期望的旧 dict schema
        """
        # Case 1: CoordinatorAgentConfig（新）- 使用显式类型检查避免 duck typing 误判
        # P1-1 Step 2 Critical Fix #1: 使用 isinstance() 替代 hasattr()
        try:
            from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig
        except Exception:
            CoordinatorAgentConfig = None  # type: ignore[assignment]

        if CoordinatorAgentConfig is not None and isinstance(config, CoordinatorAgentConfig):
            # P1-1 Step 2 Critical Fix #3: 调用 validate() 进行配置校验
            self._validate_agent_config(config)
            return self._map_agent_config_to_coordinator_config(config)

        # Case 2: CoordinatorConfig（旧）
        if isinstance(config, CoordinatorConfig):
            return config

        # Case 3: dict（旧）
        if isinstance(config, dict):
            return CoordinatorConfig(**config)

        # P1-1 Step 2 Critical Fix #1: 提供更清晰的错误消息
        raise TypeError(
            "Unsupported config type for CoordinatorBootstrap. "
            f"Got: {type(config)!r}. "
            "Expected one of: CoordinatorAgentConfig, CoordinatorConfig, dict[str, Any]."
        )

    def _map_agent_config_to_coordinator_config(self, agent_config: Any) -> CoordinatorConfig:
        """将 CoordinatorAgentConfig 映射到 CoordinatorConfig

        映射规则：
        - rules → rejection_rate_threshold, circuit_breaker_config, rule_engine_facade
        - context → context_bridge, context_compressor, snapshot_manager
        - failure → failure_strategy_config (转换为旧 schema)
        - knowledge → knowledge_retriever
        - runtime → 暂不映射（保留未来扩展）

        参数：
            agent_config: CoordinatorAgentConfig 实例

        返回：
            映射后的 CoordinatorConfig

        异常：
            ValueError: 冲突检测失败（P1-1 Step 3：rule_engine_facade 与构建参数冲突）
        """
        # 提取 rules 组（P1-1 Step 3）
        rejection_rate_threshold = agent_config.rules.rejection_rate_threshold
        circuit_breaker_config = agent_config.rules.circuit_breaker_config
        rule_engine_facade = agent_config.rules.rule_engine_facade
        alert_rule_manager_enabled = agent_config.rules.alert_rule_manager_enabled

        # P1-1 Step 3: 冲突检测 - 注入 facade 时禁止再提供构建参数
        if rule_engine_facade is not None:
            # 导入默认配置用于对比（P1-1 Critical Fix: 导入失败直接抛出，避免静默失效）
            from src.domain.agents.coordinator_agent_config import RuleEngineConfig

            defaults = RuleEngineConfig()
            # 检查是否有非默认的构建参数
            if rejection_rate_threshold != defaults.rejection_rate_threshold:
                raise ValueError(
                    f"rule_engine_facade conflicts with rejection_rate_threshold: "
                    f"cannot inject facade and provide custom rejection_rate_threshold={rejection_rate_threshold}. "
                    f"Use facade with default threshold or provide threshold without facade."
                )
            if circuit_breaker_config is not None:
                raise ValueError(
                    "rule_engine_facade conflicts with circuit_breaker_config: "
                    "cannot inject facade and provide custom circuit_breaker_config. "
                    "Configure CircuitBreaker in the facade or provide circuit_breaker_config without facade."
                )

        # 提取 context 组
        context_bridge = agent_config.context.context_bridge
        context_compressor = agent_config.context.context_compressor
        snapshot_manager = agent_config.context.snapshot_manager

        # 提取 knowledge 组
        # 注意：knowledge_retrieval_orchestrator 实际语义是 retriever
        knowledge_retriever = agent_config.knowledge.knowledge_retrieval_orchestrator

        # 如果 enable_knowledge_retrieval=False，强制 knowledge_retriever=None
        if not agent_config.knowledge.enable_knowledge_retrieval:
            knowledge_retriever = None

        # 提取 failure 组并转换为旧 schema
        failure_strategy_config = self._map_failure_config_to_dict(agent_config.failure)

        # 提取 event_bus（顶层字段）
        event_bus = agent_config.event_bus

        return CoordinatorConfig(
            event_bus=event_bus,
            rejection_rate_threshold=rejection_rate_threshold,
            circuit_breaker_config=circuit_breaker_config,
            rule_engine_facade=rule_engine_facade,
            alert_rule_manager_enabled=alert_rule_manager_enabled,
            context_bridge=context_bridge,
            failure_strategy_config=failure_strategy_config,
            context_compressor=context_compressor,
            snapshot_manager=snapshot_manager,
            knowledge_retriever=knowledge_retriever,
        )

    def _map_failure_config_to_dict(self, failure: Any) -> dict[str, Any] | None:
        """将 FailureHandlingConfig 转换为 WorkflowFailureOrchestrator 期望的 dict schema

        WorkflowFailureOrchestrator 实际消费的 schema：
        - default_strategy: FailureHandlingStrategy 枚举
        - max_retries: int
        - retry_delay: float

        参数：
            failure: FailureHandlingConfig 实例

        返回：
            旧 schema 的 dict，如果使用默认值则返回 None

        注意：
            P1-1 Step 2 Critical Fix #2 & #4:
            - 使用 DEFAULT_FAILURE_STRATEGY_CONFIG 对比而非硬编码数值
            - 只映射 orchestrator 实际消费的字段，避免"假配置"问题
            - FailureHandlingConfig 中的 enable_auto_recovery / failure_notification_enabled
              目前不被 WorkflowFailureOrchestrator 消费，因此不包含在映射中
        """
        # P1-1 Step 2 Critical Fix #4: 只映射实际被消费的字段
        bootstrap_dict = {
            "default_strategy": FailureHandlingStrategy.RETRY,
            "max_retries": failure.max_retry_attempts,
            "retry_delay": failure.retry_delay_seconds,
        }

        # P1-1 Step 2 Critical Fix #2: 使用默认配置对比，避免硬编码漂移
        if bootstrap_dict == DEFAULT_FAILURE_STRATEGY_CONFIG:
            return None

        return bootstrap_dict

    def assemble(self) -> CoordinatorWiring:
        """装配所有依赖

        按照依赖顺序构建所有组件，返回装配结果。

        返回：
            CoordinatorWiring 装配结果
        """
        # 阶段 1: 基础状态
        base = self.build_base_state()

        # 阶段 2: 基础设施
        infra = self.build_infra(base)

        # 阶段 3: 失败处理层
        failure_layer = self.build_failure_layer(base, infra)

        # 阶段 4: 知识层
        knowledge_layer = self.build_knowledge_layer(base, infra)

        # 阶段 5: Agent 协调层
        agent_layer = self.build_agent_coordination(base, infra)

        # 阶段 6: 提示词与实验层
        prompt_layer = self.build_prompt_experiment(infra)

        # 阶段 7: 保存请求流程
        save_layer = self.build_save_flow(base, infra, knowledge_layer)

        # 阶段 8: 守护层
        guardian_layer = self.build_guardians(infra, agent_layer)

        # 阶段 9: RuleEngineFacade（P1-1 Step 3）
        rule_engine_layer = self.build_rule_engine_facade(base, infra, agent_layer, guardian_layer)

        # 汇总别名
        aliases = self._collect_aliases(
            base, infra, failure_layer, knowledge_layer, agent_layer, prompt_layer, save_layer
        )

        # 汇总编排器
        orchestrators = self._collect_orchestrators(
            infra,
            failure_layer,
            knowledge_layer,
            agent_layer,
            prompt_layer,
            save_layer,
            guardian_layer,
            rule_engine_layer,
        )

        return CoordinatorWiring(
            log_collector=infra["log_collector"],
            orchestrators=orchestrators,
            aliases=aliases,
            base_state=base,
            config=self.config,
        )

    # =====================================================================
    # 构建阶段方法
    # =====================================================================

    def build_base_state(self) -> dict[str, Any]:
        """构建基础状态

        创建所有基础状态容器：规则列表、统计字典、工作流状态、标志位等。

        返回：
            基础状态字典
        """
        import copy

        return {
            # 规则与统计
            "_rules": [],
            "_statistics": {"total": 0, "passed": 0, "rejected": 0},
            # 工作流状态
            "workflow_states": {},
            "_is_monitoring": False,
            "_current_workflow_id": None,
            # 失败处理状态
            "_node_failure_strategies": {},
            "_workflow_agents": {},
            "failure_strategy_config": (
                self.config.failure_strategy_config
                or copy.deepcopy(DEFAULT_FAILURE_STRATEGY_CONFIG)
            ),
            # 消息日志
            "message_log": [],
            "_is_listening_simple_messages": False,
            # 反思上下文
            "reflection_contexts": {},
            "_is_listening_reflections": False,
            # 上下文压缩
            "context_compressor": self.config.context_compressor,
            "snapshot_manager": self.config.snapshot_manager,
            "_compressed_contexts": {},
            "_is_compressing_context": False,
            # 知识库
            "_knowledge_cache": {},
            "_auto_knowledge_retrieval_enabled": False,
            # 工具仓库
            "_tool_repository": None,
            # 代码修复
            "_auto_repair_enabled": False,
            "_max_repair_attempts": 3,
            "_code_repair_service": None,
            # 保存请求（初始化为 None，在 build_save_flow 中设置）
            "_save_request_handler_enabled": False,
            "_is_listening_save_requests": False,
            "_save_auditor": None,
            "_save_executor": None,
            "_save_audit_logger": None,
            "_save_request_queue": None,
            "save_receipt_system": None,
            "_save_receipt_logger": None,
            # 子Agent（初始化为 None，在 build_agent_coordination 中设置）
            "_subagent_orchestrator": None,
        }

    def build_infra(self, base: dict[str, Any]) -> dict[str, Any]:
        """构建基础设施层

        创建：
        - CircuitBreaker（如果配置提供）
        - UnifiedLogCollector（共享单例）
        - ContainerExecutionMonitor
        - UnifiedLogIntegration（带 accessor）

        参数：
            base: 基础状态字典

        返回：
            基础设施组件字典
        """
        # 1. CircuitBreaker（可选）
        circuit_breaker = None
        if self.config.circuit_breaker_config:
            from src.domain.services.circuit_breaker import CircuitBreaker

            circuit_breaker = CircuitBreaker(self.config.circuit_breaker_config)

        # 2. UnifiedLogCollector（共享单例）
        log_collector = UnifiedLogCollector()

        # 3. ContainerExecutionMonitor
        container_monitor = ContainerExecutionMonitor(
            event_bus=self.config.event_bus,
            max_log_size=MAX_CONTAINER_LOGS_SIZE,
        )

        # 4. Message/Container Log Accessor
        message_log_accessor = _MessageLogAccessor(base["message_log"])
        container_log_accessor = _ContainerLogAccessor(container_monitor)

        # 5. UnifiedLogIntegration
        log_integration = UnifiedLogIntegration(
            log_collector=log_collector,
            message_log_accessor=message_log_accessor,
            container_log_accessor=container_log_accessor,
        )

        return {
            "circuit_breaker": circuit_breaker,
            "log_collector": log_collector,
            "container_monitor": container_monitor,
            "message_log_accessor": message_log_accessor,
            "container_log_accessor": container_log_accessor,
            "log_integration": log_integration,
        }

    def build_failure_layer(self, base: dict[str, Any], infra: dict[str, Any]) -> dict[str, Any]:
        """构建失败处理层

        创建 WorkflowFailureOrchestrator，注入状态访问器和工作流 Agent 解析器。

        参数：
            base: 基础状态字典
            infra: 基础设施组件字典

        返回：
            失败处理层组件字典
        """
        failure_orchestrator = WorkflowFailureOrchestrator(
            event_bus=self.config.event_bus,
            state_accessor=lambda wf_id: base["workflow_states"].get(wf_id),
            state_mutator=lambda wf_id: base["workflow_states"].setdefault(wf_id, {}),
            workflow_agent_resolver=lambda wf_id: base["_workflow_agents"].get(wf_id),
            config=base["failure_strategy_config"],
        )

        return {
            "failure_orchestrator": failure_orchestrator,
        }

    def build_knowledge_layer(self, base: dict[str, Any], infra: dict[str, Any]) -> dict[str, Any]:
        """构建知识层

        创建：
        - KnowledgeManager
        - _ContextGateway（访问 _compressed_contexts）
        - KnowledgeRetrievalOrchestrator
        - ExecutionSummaryManager
        - PowerCompressorFacade

        参数：
            base: 基础状态字典
            infra: 基础设施组件字典

        返回：
            知识层组件字典
        """
        # 1. KnowledgeManager
        knowledge_manager = KnowledgeManager()

        # 2. ContextGateway
        context_gateway = _ContextGateway(base["_compressed_contexts"])

        # 3. KnowledgeRetrievalOrchestrator
        knowledge_retrieval_orchestrator = KnowledgeRetrievalOrchestrator(
            knowledge_retriever=self.config.knowledge_retriever,
            context_gateway=context_gateway,
        )

        # 4. ExecutionSummaryManager
        summary_manager = ExecutionSummaryManager(event_bus=self.config.event_bus)

        # 5. PowerCompressorFacade
        power_compressor_facade = PowerCompressorFacade()

        return {
            "knowledge_manager": knowledge_manager,
            "context_gateway": context_gateway,
            "knowledge_retrieval_orchestrator": knowledge_retrieval_orchestrator,
            "summary_manager": summary_manager,
            "power_compressor_facade": power_compressor_facade,
        }

    def build_agent_coordination(
        self, base: dict[str, Any], infra: dict[str, Any]
    ) -> dict[str, Any]:
        """构建 Agent 协调层

        创建：
        - SubAgentOrchestrator（共享 log_collector）
        - SupervisionCoordinator
        - DynamicAlertRuleManager（可选，如果模块存在）

        参数：
            base: 基础状态字典
            infra: 基础设施组件字典

        返回：
            Agent 协调层组件字典
        """
        # 1. SubAgentOrchestrator（共享 log_collector）
        subagent_orchestrator = SubAgentOrchestrator(
            event_bus=self.config.event_bus,
            log_collector=infra["log_collector"],
        )
        # 显式暴露 log_collector 属性（满足兼容性测试）
        subagent_orchestrator.log_collector = infra["log_collector"]  # type: ignore[attr-defined]

        # 2. SupervisionCoordinator
        supervision_coordinator = SupervisionCoordinator()

        # 3. DynamicAlertRuleManager（可选，如果模块存在且配置启用，P1-1 Step 3）
        alert_rule_manager = None
        if getattr(self.config, "alert_rule_manager_enabled", True):
            try:
                from src.domain.services.dynamic_alert_rule_manager import DynamicAlertRuleManager

                alert_rule_manager = DynamicAlertRuleManager()
            except (ImportError, AttributeError):
                # 模块不存在或未实现，跳过
                pass

        return {
            "subagent_orchestrator": subagent_orchestrator,
            "supervision_coordinator": supervision_coordinator,
            "alert_rule_manager": alert_rule_manager,
        }

    def build_prompt_experiment(self, infra: dict[str, Any]) -> dict[str, Any]:
        """构建提示词与实验层

        创建：
        - PromptVersionFacade（共享 log_collector）
        - ExperimentOrchestrator（共享 log_collector）

        参数：
            infra: 基础设施组件字典

        返回：
            提示词与实验层组件字典
        """
        # 1. PromptVersionFacade（共享 log_collector）
        prompt_facade = PromptVersionFacade(log_collector=infra["log_collector"])
        # 显式暴露 log_collector 属性（满足兼容性测试）
        prompt_facade.log_collector = infra["log_collector"]  # type: ignore[attr-defined]

        # 2. ExperimentOrchestrator（共享 log_collector）
        experiment_orchestrator = ExperimentOrchestrator(log_collector=infra["log_collector"])
        # 显式暴露 log_collector 属性（满足兼容性测试）
        experiment_orchestrator.log_collector = infra["log_collector"]  # type: ignore[attr-defined]

        return {
            "prompt_facade": prompt_facade,
            "experiment_orchestrator": experiment_orchestrator,
        }

    def build_save_flow(
        self,
        base: dict[str, Any],
        infra: dict[str, Any],
        knowledge_layer: dict[str, Any],
    ) -> dict[str, Any]:
        """构建保存请求流程

        创建 SaveRequestOrchestrator（仅当 event_bus 不为 None），
        并更新 base 中的相关别名。

        参数：
            base: 基础状态字典
            infra: 基础设施组件字典
            knowledge_layer: 知识层组件字典

        返回：
            保存请求流程组件字典
        """
        save_request_queue = None
        save_receipt_system = None
        save_receipt_logger = None

        if self.config.event_bus is not None:
            from src.domain.services.save_request_orchestrator import SaveRequestOrchestrator

            save_request_orchestrator = SaveRequestOrchestrator(
                event_bus=self.config.event_bus,
                knowledge_manager=knowledge_layer["knowledge_manager"],
                log_collector=infra["log_collector"],
            )

            # 提取内部引用（向后兼容）
            save_request_queue = save_request_orchestrator._save_request_queue
            save_receipt_system = save_request_orchestrator.save_receipt_system
            save_receipt_logger = save_receipt_system.receipt_logger
        else:
            # P1-2: 无EventBus时使用Null Object，消除调用方的18处None检查
            from src.domain.services.null_save_request_orchestrator import (
                NullSaveRequestOrchestrator,
            )

            save_request_orchestrator = NullSaveRequestOrchestrator()

        # 更新 base 中的别名（向后兼容）
        base["_save_request_queue"] = save_request_queue
        base["save_receipt_system"] = save_receipt_system
        base["_save_receipt_logger"] = save_receipt_logger

        return {
            "save_request_orchestrator": save_request_orchestrator,
            "_save_request_queue": save_request_queue,
            "save_receipt_system": save_receipt_system,
            "_save_receipt_logger": save_receipt_logger,
        }

    def build_guardians(self, infra: dict[str, Any], agent_layer: dict[str, Any]) -> dict[str, Any]:
        """构建守护层

        创建：
        - ContextInjectionManager Facade（Phase 34.12：包装旧的注入管理器）
        - SupervisionFacade（Phase 34.13：包装 SupervisionModule、Logger、Coordinator）
        - InterventionCoordinator（WorkflowModifier、TaskTerminator、InterventionLogger）
        - SafetyGuard

        参数：
            infra: 基础设施层组件字典（需要 log_collector）
            agent_layer: Agent 协调层组件字典（需要 supervision_coordinator）

        返回：
            守护层组件字典
        """
        # 1. ContextInjectionManager Facade (Phase 34.12)
        # 1.1 创建底层注入组件（旧版，仍然需要）
        from src.domain.services.context_injection import (
            ContextInjectionManager as OldInjectionManager,
        )
        from src.domain.services.context_injection import (
            InjectionLogger,
        )

        injection_logger = InjectionLogger()
        old_injection_manager = OldInjectionManager(logger=injection_logger)

        # 1.2 创建 Facade 包装旧组件（新版，提供统一接口）
        from src.domain.services.context_injection_manager import (
            ContextInjectionManager,
        )

        context_injection_manager = ContextInjectionManager(
            injection_manager=old_injection_manager,
            injection_logger=injection_logger,
        )

        # 2. SupervisionModule 和 SupervisionLogger
        from src.domain.services.supervision_module import (
            SupervisionLogger as SupLogger,
        )
        from src.domain.services.supervision_module import (
            SupervisionModule,
        )

        supervision_logger = SupLogger()
        supervision_module = SupervisionModule(logger=supervision_logger, use_builtin_rules=True)

        # 2.1 SupervisionFacade (Phase 34.13)
        from src.domain.services.supervision_facade import SupervisionFacade

        supervision_facade = SupervisionFacade(
            supervision_module=supervision_module,
            supervision_logger=supervision_logger,
            supervision_coordinator=agent_layer["supervision_coordinator"],
            context_injection_manager=context_injection_manager,
            log_collector=infra["log_collector"],
        )

        # 3. InterventionCoordinator
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLogger,
            TaskTerminator,
            WorkflowModifier,
        )

        intervention_logger = InterventionLogger()
        workflow_modifier = WorkflowModifier(logger=intervention_logger)
        task_terminator = TaskTerminator(logger=intervention_logger)
        intervention_coordinator = InterventionCoordinator(
            workflow_modifier=workflow_modifier,
            task_terminator=task_terminator,
            logger=intervention_logger,
        )

        # 4. SafetyGuard
        from src.domain.services.safety_guard import SafetyGuard

        safety_guard = SafetyGuard()

        return {
            "injection_logger": injection_logger,
            "context_injection_manager": context_injection_manager,
            "supervision_logger": supervision_logger,
            "supervision_module": supervision_module,
            "supervision_facade": supervision_facade,  # Phase 34.13
            "intervention_logger": intervention_logger,
            "workflow_modifier": workflow_modifier,
            "task_terminator": task_terminator,
            "intervention_coordinator": intervention_coordinator,
            "safety_guard": safety_guard,
        }

    def build_rule_engine_facade(
        self,
        base: dict[str, Any],
        infra: dict[str, Any],
        agent_layer: dict[str, Any],
        guardian_layer: dict[str, Any],
    ) -> dict[str, Any]:
        """构建 RuleEngineFacade（P1-1 Step 3）

        创建规则引擎 Facade，整合决策规则、安全校验、审计等功能。

        策略：
        - 如果 config.rule_engine_facade 已注入，直接使用
        - 否则，自动构建 Facade 实例并共享 base 状态容器

        参数：
            base: 基础状态字典（需要 _rules, _statistics）
            infra: 基础设施组件字典（需要 circuit_breaker, log_collector）
            agent_layer: Agent 协调层组件字典（需要 alert_rule_manager）
            guardian_layer: 守护层组件字典（需要 safety_guard）

        返回：
            规则引擎层组件字典
        """
        # 优先使用注入的 facade
        if self.config.rule_engine_facade is not None:
            logger.info("Using injected RuleEngineFacade")
            return {"rule_engine_facade": self.config.rule_engine_facade}

        # 自动构建 Facade
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(
            safety_guard=guardian_layer["safety_guard"],
            circuit_breaker=infra.get("circuit_breaker"),
            alert_rule_manager=agent_layer.get("alert_rule_manager"),
            rejection_rate_threshold=self.config.rejection_rate_threshold,
            log_collector=infra.get("log_collector"),
            rules_ref=base["_rules"],
            statistics_ref=base["_statistics"],
        )

        logger.info(
            "Built RuleEngineFacade with rejection_rate_threshold=%.2f, "
            "circuit_breaker=%s, alert_rule_manager=%s",
            self.config.rejection_rate_threshold,
            "configured" if infra.get("circuit_breaker") else "none",
            "configured" if agent_layer.get("alert_rule_manager") else "none",
        )

        return {"rule_engine_facade": facade}

    # =====================================================================
    # 汇总辅助方法
    # =====================================================================

    def _collect_aliases(
        self,
        base: dict[str, Any],
        infra: dict[str, Any],
        failure: dict[str, Any],
        knowledge: dict[str, Any],
        agent: dict[str, Any],
        prompt: dict[str, Any],
        save: dict[str, Any],
    ) -> dict[str, Any]:
        """汇总所有向后兼容别名

        从各层组件中提取所有需要暴露的别名，确保向后兼容性。

        参数：
            base: 基础状态字典
            infra: 基础设施组件字典
            failure: 失败处理层组件字典
            knowledge: 知识层组件字典
            agent: Agent 协调层组件字典
            prompt: 提示词与实验层组件字典
            save: 保存请求流程组件字典

        返回：
            别名字典 {alias_name: object_reference}
        """
        supervision_coordinator = agent["supervision_coordinator"]

        return {
            # 配置别名
            "context_bridge": self.config.context_bridge,
            "context_compressor": base["context_compressor"],
            "snapshot_manager": base["snapshot_manager"],
            "circuit_breaker": infra["circuit_breaker"],
            # 标志位
            "_is_monitoring": base["_is_monitoring"],
            "_is_listening_simple_messages": base["_is_listening_simple_messages"],
            "_is_listening_reflections": base["_is_listening_reflections"],
            "_is_compressing_context": base["_is_compressing_context"],
            "_auto_repair_enabled": base["_auto_repair_enabled"],
            "_auto_knowledge_retrieval_enabled": base["_auto_knowledge_retrieval_enabled"],
            "_save_request_handler_enabled": base["_save_request_handler_enabled"],
            "_is_listening_save_requests": base["_is_listening_save_requests"],
            # Placeholder
            "_tool_repository": base["_tool_repository"],
            "_code_repair_service": base["_code_repair_service"],
            # SupervisionCoordinator 暴露的别名
            "conversation_supervision": supervision_coordinator.conversation_supervision,
            "efficiency_monitor": supervision_coordinator.efficiency_monitor,
            "strategy_repository": supervision_coordinator.strategy_repository,
            # SaveRequest 相关别名
            "_save_request_queue": save["_save_request_queue"],
            "save_receipt_system": save["save_receipt_system"],
            "_save_receipt_logger": save["_save_receipt_logger"],
        }

    def _collect_orchestrators(
        self,
        infra: dict[str, Any],
        failure: dict[str, Any],
        knowledge: dict[str, Any],
        agent: dict[str, Any],
        prompt: dict[str, Any],
        save: dict[str, Any],
        guardian: dict[str, Any],
        rule_engine: dict[str, Any],
    ) -> dict[str, Any]:
        """汇总所有编排器

        从各层组件中收集所有编排器，统一管理。

        参数：
            infra: 基础设施组件字典
            failure: 失败处理层组件字典
            knowledge: 知识层组件字典
            agent: Agent 协调层组件字典
            prompt: 提示词与实验层组件字典
            save: 保存请求流程组件字典
            guardian: 守护层组件字典
            rule_engine: 规则引擎层组件字典（P1-1 Step 3）

        返回：
            编排器字典 {name: orchestrator_instance}
        """
        orchestrators = {
            # 基础设施层
            "container_monitor": infra["container_monitor"],
            "log_integration": infra["log_integration"],
            # 失败处理层
            "failure_orchestrator": failure["failure_orchestrator"],
            # 知识层
            "knowledge_manager": knowledge["knowledge_manager"],
            "knowledge_retrieval_orchestrator": knowledge["knowledge_retrieval_orchestrator"],
            "summary_manager": knowledge["summary_manager"],
            "power_compressor_facade": knowledge["power_compressor_facade"],
            # Agent 协调层
            "subagent_orchestrator": agent["subagent_orchestrator"],
            "supervision_coordinator": agent["supervision_coordinator"],
            # 提示词与实验层
            "prompt_facade": prompt["prompt_facade"],
            "experiment_orchestrator": prompt["experiment_orchestrator"],
            # 保存请求流程
            "save_request_orchestrator": save["save_request_orchestrator"],
            # 守护层
            "context_injection_manager": guardian["context_injection_manager"],
            "injection_logger": guardian["injection_logger"],
            "supervision_module": guardian["supervision_module"],
            "supervision_logger": guardian["supervision_logger"],
            "supervision_facade": guardian["supervision_facade"],  # Phase 34.13
            "intervention_coordinator": guardian["intervention_coordinator"],
            "intervention_logger": guardian["intervention_logger"],
            "workflow_modifier": guardian["workflow_modifier"],
            "task_terminator": guardian["task_terminator"],
            "safety_guard": guardian["safety_guard"],
            # 规则引擎层（P1-1 Step 3）
            "rule_engine_facade": rule_engine["rule_engine_facade"],
        }

        # 添加可选组件
        if agent.get("alert_rule_manager") is not None:
            orchestrators["alert_rule_manager"] = agent["alert_rule_manager"]

        if infra.get("circuit_breaker") is not None:
            orchestrators["circuit_breaker"] = infra["circuit_breaker"]

        return orchestrators


__all__ = [
    "CoordinatorConfig",
    "CoordinatorWiring",
    "CoordinatorBootstrap",
    "DEFAULT_REJECTION_RATE_THRESHOLD",
    "MAX_CONTAINER_LOGS_SIZE",
    "DEFAULT_FAILURE_STRATEGY_CONFIG",
]

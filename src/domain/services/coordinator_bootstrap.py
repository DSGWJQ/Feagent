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
    """

    event_bus: Any | None = None
    rejection_rate_threshold: float = DEFAULT_REJECTION_RATE_THRESHOLD
    circuit_breaker_config: Any | None = None
    context_bridge: Any | None = None
    failure_strategy_config: dict[str, Any] | None = None
    context_compressor: Any | None = None
    snapshot_manager: Any | None = None
    knowledge_retriever: Any | None = None


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

    def __init__(self, config: CoordinatorConfig | dict[str, Any]) -> None:
        """初始化 Bootstrap

        参数：
            config: Coordinator 配置（CoordinatorConfig 实例或字典）
        """
        self.config = (
            config if isinstance(config, CoordinatorConfig) else CoordinatorConfig(**config)
        )

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

        # 3. DynamicAlertRuleManager（可选，如果模块存在）
        alert_rule_manager = None
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
        save_request_orchestrator = None
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

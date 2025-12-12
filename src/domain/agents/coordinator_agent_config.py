"""CoordinatorAgent 配置系统（Coordinator Agent Config）

统一管理 CoordinatorAgent 的所有配置参数，减少构造函数参数数量。

组件：
- RuleEngineConfig: 规则引擎配置
- ContextConfig: 上下文管理配置
- FailureHandlingConfig: 失败处理配置
- KnowledgeConfig: 知识系统配置
- RuntimeConfig: 运行时配置
- CoordinatorAgentConfig: 主配置类

功能：
- 配置分组管理
- 配置验证
- 部分配置覆盖
- 不可变配置对象

设计原则：
- 分组清晰：按功能分组配置
- 不可变性：frozen dataclass 保证配置稳定
- 验证优先：启动时验证配置
- 灵活覆盖：支持部分配置替换

实现日期：2025-12-12（P1-1）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# 规则引擎配置
# =============================================================================


@dataclass(frozen=True)
class RuleEngineConfig:
    """规则引擎配置

    属性：
        rejection_rate_threshold: 拒绝率阈值
        circuit_breaker_config: 熔断器配置
        enable_decision_rules_middleware: 是否启用决策规则中间件
        alert_rule_manager_enabled: 是否启用告警规则管理
        rule_engine_facade: 规则引擎 Facade 实例（可选注入）
    """

    rejection_rate_threshold: float = 0.5
    circuit_breaker_config: dict[str, Any] | None = None
    enable_decision_rules_middleware: bool = True
    alert_rule_manager_enabled: bool = True
    rule_engine_facade: Any | None = None

    def __post_init__(self) -> None:
        """验证配置"""
        if not 0.0 <= self.rejection_rate_threshold <= 1.0:
            raise ValueError("rejection_rate_threshold must be between 0.0 and 1.0")


# =============================================================================
# 上下文管理配置
# =============================================================================


@dataclass(frozen=True)
class ContextConfig:
    """上下文管理配置

    属性：
        context_bridge: 上下文桥接器实例
        context_compressor: 上下文压缩器实例
        snapshot_manager: 快照管理器实例
        context_service: 上下文服务实例
        context_injection_manager: 上下文注入管理器实例
        reflection_context_manager: 反思上下文管理器实例
        max_context_length: 最大上下文长度
        enable_context_compression: 是否启用上下文压缩
    """

    context_bridge: Any | None = None
    context_compressor: Any | None = None
    snapshot_manager: Any | None = None
    context_service: Any | None = None
    context_injection_manager: Any | None = None
    reflection_context_manager: Any | None = None
    max_context_length: int = 4000
    enable_context_compression: bool = True

    def __post_init__(self) -> None:
        """验证配置"""
        if self.max_context_length <= 0:
            raise ValueError("max_context_length must be positive")


# =============================================================================
# 失败处理配置
# =============================================================================


@dataclass(frozen=True)
class FailureHandlingConfig:
    """失败处理配置

    属性：
        workflow_failure_orchestrator: 工作流失败编排器实例
        max_retry_attempts: 最大重试次数
        retry_delay_seconds: 重试延迟（秒）
        enable_auto_recovery: 是否启用自动恢复
        failure_notification_enabled: 是否启用失败通知
    """

    workflow_failure_orchestrator: Any | None = None
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    enable_auto_recovery: bool = True
    failure_notification_enabled: bool = True

    def __post_init__(self) -> None:
        """验证配置"""
        if self.max_retry_attempts < 0:
            raise ValueError("max_retry_attempts must be non-negative")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")


# =============================================================================
# 知识系统配置
# =============================================================================


@dataclass(frozen=True)
class KnowledgeConfig:
    """知识系统配置

    属性：
        knowledge_retrieval_orchestrator: 知识检索编排器实例
        enable_knowledge_retrieval: 是否启用知识检索
        retrieval_timeout_seconds: 检索超时时间（秒）
        max_retrieval_results: 最大检索结果数
    """

    knowledge_retrieval_orchestrator: Any | None = None
    enable_knowledge_retrieval: bool = True
    retrieval_timeout_seconds: float = 5.0
    max_retrieval_results: int = 10

    def __post_init__(self) -> None:
        """验证配置"""
        if self.retrieval_timeout_seconds <= 0:
            raise ValueError("retrieval_timeout_seconds must be positive")
        if self.max_retrieval_results <= 0:
            raise ValueError("max_retrieval_results must be positive")


# =============================================================================
# 运行时配置
# =============================================================================


@dataclass(frozen=True)
class RuntimeConfig:
    """运行时配置

    属性：
        experiment_orchestrator: 实验编排器实例
        execution_summary_manager: 执行摘要管理器实例
        supervision_facade: 监督门面实例
        workflow_state_monitor: 工作流状态监控器实例
        log_collector: 日志收集器实例
        enable_performance_monitoring: 是否启用性能监控
        enable_debug_logging: 是否启用调试日志
    """

    experiment_orchestrator: Any | None = None
    execution_summary_manager: Any | None = None
    supervision_facade: Any | None = None
    workflow_state_monitor: Any | None = None
    log_collector: Any | None = None
    enable_performance_monitoring: bool = True
    enable_debug_logging: bool = False


# =============================================================================
# 主配置类
# =============================================================================


@dataclass(frozen=True)
class CoordinatorAgentConfig:
    """CoordinatorAgent 主配置

    统一管理所有配置参数，分为5个功能组。

    使用示例：
        # 使用默认配置
        config = CoordinatorAgentConfig()

        # 自定义配置
        config = CoordinatorAgentConfig(
            event_bus=event_bus,
            rules=RuleEngineConfig(rejection_rate_threshold=0.3),
            context=ContextConfig(max_context_length=8000),
        )

        # 部分覆盖配置
        new_config = config.with_overrides(
            rules=RuleEngineConfig(rejection_rate_threshold=0.4)
        )

    属性：
        event_bus: 事件总线实例（必选）
        rules: 规则引擎配置
        context: 上下文管理配置
        failure: 失败处理配置
        knowledge: 知识系统配置
        runtime: 运行时配置
    """

    event_bus: Any | None = None
    rules: RuleEngineConfig = field(default_factory=RuleEngineConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    failure: FailureHandlingConfig = field(default_factory=FailureHandlingConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    def validate(self, *, strict: bool = True) -> None:
        """验证配置完整性

        检查：
        1. 必选依赖是否存在
        2. 配置组内部一致性
        3. 配置组间依赖关系

        参数：
            strict: 是否严格校验（默认 True）
                - True: event_bus=None 会抛出 ValueError
                - False: event_bus=None 只记录 warning（用于测试/装配场景）

        异常：
            ValueError: 配置验证失败（仅在 strict=True 时）

        说明：
            P1-1 Step 2 Critical Fix #3: 增加 strict 参数支持宽松校验
        """
        # 必选依赖检查
        if self.event_bus is None:
            if strict:
                raise ValueError("event_bus is required")
            logger.warning("CoordinatorAgentConfig.validate(strict=False): event_bus is None")

        # 配置组内部验证（__post_init__ 已执行）
        # 这里检查跨组依赖关系

        # 如果启用上下文压缩，必须提供压缩器
        if self.context.enable_context_compression and self.context.context_compressor is None:
            logger.warning("context_compression enabled but context_compressor not provided")

        # 如果启用自动恢复，建议提供失败编排器
        if self.failure.enable_auto_recovery and self.failure.workflow_failure_orchestrator is None:
            logger.warning("auto_recovery enabled but workflow_failure_orchestrator not provided")

        # 如果启用知识检索，必须提供检索编排器
        if (
            self.knowledge.enable_knowledge_retrieval
            and self.knowledge.knowledge_retrieval_orchestrator is None
        ):
            logger.warning(
                "knowledge_retrieval enabled but knowledge_retrieval_orchestrator not provided"
            )

        logger.info("CoordinatorAgentConfig validation passed")

    def with_overrides(self, **kwargs: Any) -> CoordinatorAgentConfig:
        """创建配置副本并覆盖部分参数

        支持直接覆盖顶层字段或配置组：

        使用示例：
            # 覆盖顶层字段
            new_config = config.with_overrides(event_bus=new_bus)

            # 覆盖配置组
            new_config = config.with_overrides(
                rules=RuleEngineConfig(rejection_rate_threshold=0.4)
            )

            # 混合覆盖
            new_config = config.with_overrides(
                event_bus=new_bus,
                context=ContextConfig(max_context_length=8000)
            )

        参数：
            **kwargs: 要覆盖的字段

        返回：
            新的配置实例

        异常：
            TypeError: 字段名不存在
        """
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于日志和调试）

        返回：
            配置字典（不包含实例对象）
        """
        return {
            "event_bus_configured": self.event_bus is not None,
            "rules": {
                "rejection_rate_threshold": self.rules.rejection_rate_threshold,
                "circuit_breaker_configured": self.rules.circuit_breaker_config is not None,
                "enable_decision_rules_middleware": self.rules.enable_decision_rules_middleware,
                "alert_rule_manager_enabled": self.rules.alert_rule_manager_enabled,
                "rule_engine_facade_configured": self.rules.rule_engine_facade is not None,
            },
            "context": {
                "max_context_length": self.context.max_context_length,
                "enable_context_compression": self.context.enable_context_compression,
                "context_bridge_configured": self.context.context_bridge is not None,
                "context_compressor_configured": self.context.context_compressor is not None,
                "context_service_configured": self.context.context_service is not None,
            },
            "failure": {
                "max_retry_attempts": self.failure.max_retry_attempts,
                "retry_delay_seconds": self.failure.retry_delay_seconds,
                "enable_auto_recovery": self.failure.enable_auto_recovery,
                "failure_notification_enabled": self.failure.failure_notification_enabled,
                "workflow_failure_orchestrator_configured": self.failure.workflow_failure_orchestrator
                is not None,
            },
            "knowledge": {
                "enable_knowledge_retrieval": self.knowledge.enable_knowledge_retrieval,
                "retrieval_timeout_seconds": self.knowledge.retrieval_timeout_seconds,
                "max_retrieval_results": self.knowledge.max_retrieval_results,
                "knowledge_retrieval_orchestrator_configured": self.knowledge.knowledge_retrieval_orchestrator
                is not None,
            },
            "runtime": {
                "enable_performance_monitoring": self.runtime.enable_performance_monitoring,
                "enable_debug_logging": self.runtime.enable_debug_logging,
                "experiment_orchestrator_configured": self.runtime.experiment_orchestrator
                is not None,
                "supervision_facade_configured": self.runtime.supervision_facade is not None,
                "log_collector_configured": self.runtime.log_collector is not None,
            },
        }


# =============================================================================
# 配置构建辅助
# =============================================================================


class CoordinatorAgentConfigBuilder:
    """CoordinatorAgent 配置构建器

    提供流式 API 构建配置对象。

    使用示例：
        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(event_bus)
            .with_rejection_rate_threshold(0.3)
            .with_max_context_length(8000)
            .build()
        )
    """

    def __init__(self) -> None:
        """初始化构建器"""
        self._event_bus: Any | None = None
        self._rules: RuleEngineConfig = RuleEngineConfig()
        self._context: ContextConfig = ContextConfig()
        self._failure: FailureHandlingConfig = FailureHandlingConfig()
        self._knowledge: KnowledgeConfig = KnowledgeConfig()
        self._runtime: RuntimeConfig = RuntimeConfig()

    def with_event_bus(self, event_bus: Any) -> CoordinatorAgentConfigBuilder:
        """设置事件总线"""
        self._event_bus = event_bus
        return self

    def with_rejection_rate_threshold(self, threshold: float) -> CoordinatorAgentConfigBuilder:
        """设置拒绝率阈值"""
        self._rules = replace(self._rules, rejection_rate_threshold=threshold)
        return self

    def with_max_context_length(self, length: int) -> CoordinatorAgentConfigBuilder:
        """设置最大上下文长度"""
        self._context = replace(self._context, max_context_length=length)
        return self

    def with_max_retry_attempts(self, attempts: int) -> CoordinatorAgentConfigBuilder:
        """设置最大重试次数"""
        self._failure = replace(self._failure, max_retry_attempts=attempts)
        return self

    def with_rules_config(self, config: RuleEngineConfig) -> CoordinatorAgentConfigBuilder:
        """设置规则引擎配置"""
        self._rules = config
        return self

    def with_context_config(self, config: ContextConfig) -> CoordinatorAgentConfigBuilder:
        """设置上下文配置"""
        self._context = config
        return self

    def with_failure_config(self, config: FailureHandlingConfig) -> CoordinatorAgentConfigBuilder:
        """设置失败处理配置"""
        self._failure = config
        return self

    def with_knowledge_config(self, config: KnowledgeConfig) -> CoordinatorAgentConfigBuilder:
        """设置知识系统配置"""
        self._knowledge = config
        return self

    def with_runtime_config(self, config: RuntimeConfig) -> CoordinatorAgentConfigBuilder:
        """设置运行时配置"""
        self._runtime = config
        return self

    def build(self) -> CoordinatorAgentConfig:
        """构建配置对象

        返回：
            CoordinatorAgentConfig 实例

        异常：
            ValueError: 配置验证失败
        """
        config = CoordinatorAgentConfig(
            event_bus=self._event_bus,
            rules=self._rules,
            context=self._context,
            failure=self._failure,
            knowledge=self._knowledge,
            runtime=self._runtime,
        )

        config.validate()
        return config


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "RuleEngineConfig",
    "ContextConfig",
    "FailureHandlingConfig",
    "KnowledgeConfig",
    "RuntimeConfig",
    "CoordinatorAgentConfig",
    "CoordinatorAgentConfigBuilder",
]

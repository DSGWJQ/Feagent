"""ConversationAgent 配置系统（Conversation Agent Config）

统一管理 ConversationAgent 的所有配置参数，减少构造函数参数数量。

组件：
- LLMConfig: LLM配置（模型、温度、token限制）
- ReActConfig: ReAct循环配置（迭代次数、超时）
- IntentConfig: 意图分类配置（置信度阈值）
- WorkflowConfig: 工作流协调配置（子Agent、反馈监听）
- StreamingConfig: 流式输出配置（SSE）
- ResourceConfig: 资源限制配置（token、成本、超时）
- ConversationAgentConfig: 主配置类

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

实现日期：2025-12-13（P1-4 步骤1）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# LLM 配置
# =============================================================================


@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置组

    属性：
        llm: ConversationAgentLLM 实例（必选）
        model: 模型名称（可选，用于日志）
        temperature: 温度参数
        max_tokens: 单次调用最大 token
    """

    llm: Any  # ConversationAgentLLM 实例
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4000

    def __post_init__(self) -> None:
        """验证配置"""
        if self.llm is None:
            raise ValueError("llm instance is required")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")


# =============================================================================
# ReAct 循环配置
# =============================================================================


@dataclass(frozen=True)
class ReActConfig:
    """ReAct 循环配置

    属性：
        max_iterations: 最大迭代次数
        timeout_seconds: 单次运行超时时间（秒）
        enable_reasoning_trace: 是否记录推理轨迹
        enable_parallel_actions: 是否启用并行 Action 执行
    """

    max_iterations: int = 10
    timeout_seconds: float | None = None
    enable_reasoning_trace: bool = True
    enable_parallel_actions: bool = False

    def __post_init__(self) -> None:
        """验证配置"""
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


# =============================================================================
# 意图分类配置
# =============================================================================


@dataclass(frozen=True)
class IntentConfig:
    """意图分类配置（Phase 14）

    属性：
        enable_intent_classification: 是否启用意图分类
        intent_confidence_threshold: 置信度阈值
        fallback_to_react: 低置信度时是否回退到 ReAct
        use_rule_based_extraction: 是否使用基于规则的控制流提取
    """

    enable_intent_classification: bool = False
    intent_confidence_threshold: float = 0.7
    fallback_to_react: bool = True
    use_rule_based_extraction: bool = True

    def __post_init__(self) -> None:
        """验证配置"""
        if not 0.0 <= self.intent_confidence_threshold <= 1.0:
            raise ValueError("intent_confidence_threshold must be between 0.0 and 1.0")


# =============================================================================
# 工作流协调配置
# =============================================================================


@dataclass(frozen=True)
class WorkflowConfig:
    """工作流协调配置

    属性：
        coordinator: CoordinatorAgent 实例（可选）
        enable_subagent_spawn: 是否启用子 Agent 生成
        enable_feedback_listening: 是否启用工作流反馈监听
        enable_progress_events: 是否启用进度事件
        subagent_timeout_seconds: 子 Agent 超时时间
    """

    coordinator: Any | None = None
    enable_subagent_spawn: bool = True
    enable_feedback_listening: bool = True
    enable_progress_events: bool = True
    subagent_timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        """验证配置"""
        if self.subagent_timeout_seconds <= 0:
            raise ValueError("subagent_timeout_seconds must be positive")


# =============================================================================
# 流式输出配置
# =============================================================================


@dataclass(frozen=True)
class StreamingConfig:
    """流式输出配置

    属性：
        emitter: ConversationFlowEmitter 实例（可选）
        stream_emitter: 流式输出器实例（可选）
        enable_sse: 是否启用 SSE 输出
        enable_save_request_channel: 是否启用保存请求通道
    """

    emitter: Any | None = None
    stream_emitter: Any | None = None
    enable_sse: bool = True  # Step 1.5: 默认启用 SSE
    enable_save_request_channel: bool = False

    def validate(self, event_bus: Any | None, *, strict: bool = False) -> None:
        """验证流式输出配置

        参数：
            event_bus: EventBus 实例（来自 ConversationAgentConfig）
            strict: 是否严格模式（True=启用时必须有event_bus，False=仅警告）

        异常：
            ValueError: 如果 strict=True 且 enable_save_request_channel=True 但 event_bus 为 None
        """
        if self.enable_save_request_channel and event_bus is None:
            msg = (
                "enable_save_request_channel=True requires event_bus to be configured. "
                "SaveRequest feature will not work without EventBus."
            )
            if strict:
                raise ValueError(msg)
            else:
                import warnings

                warnings.warn(msg, UserWarning, stacklevel=3)


# =============================================================================
# 资源限制配置
# =============================================================================


@dataclass(frozen=True)
class ResourceConfig:
    """资源限制配置

    属性：
        max_tokens: 累计最大 token 限制
        max_cost: 最大成本限制（美元）
        enable_token_tracking: 是否启用 token 跟踪
        enable_cost_tracking: 是否启用成本跟踪
    """

    max_tokens: int | None = None
    max_cost: float | None = None
    enable_token_tracking: bool = True
    enable_cost_tracking: bool = False

    def __post_init__(self) -> None:
        """验证配置"""
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.max_cost is not None and self.max_cost <= 0:
            raise ValueError("max_cost must be positive")


# =============================================================================
# 主配置类
# =============================================================================


@dataclass(frozen=True)
class ConversationAgentConfig:
    """ConversationAgent 主配置

    统一管理所有配置参数，分为6个功能组。

    使用示例：
        # 使用默认配置（除必选参数）
        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance),
            event_bus=event_bus,
        )

        # 自定义配置
        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance, temperature=0.5),
            react=ReActConfig(max_iterations=15),
            intent=IntentConfig(enable_intent_classification=True),
            workflow=WorkflowConfig(coordinator=coordinator),
            event_bus=event_bus,
        )

        # 部分覆盖配置
        new_config = config.with_overrides(
            react=ReActConfig(max_iterations=20)
        )

    属性：
        session_context: 会话上下文（必选）
        llm: LLM 配置组（必选）
        event_bus: 事件总线实例（可选）
        model_metadata_port: 模型元数据端口（可选，P1-1）
        react: ReAct 循环配置
        intent: 意图分类配置
        workflow: 工作流协调配置
        streaming: 流式输出配置
        resource: 资源限制配置
    """

    session_context: Any | None = None  # SessionContext 实例（可选，延迟注入）
    llm: LLMConfig | None = None  # LLM 配置（可选，延迟注入）
    event_bus: Any | None = None  # EventBus 实例（可选）
    model_metadata_port: Any | None = None  # ModelMetadataPort 实例（可选，P1-1）
    react: ReActConfig = field(default_factory=ReActConfig)
    intent: IntentConfig = field(default_factory=IntentConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    resource: ResourceConfig = field(default_factory=ResourceConfig)

    def validate(self, *, strict: bool = True) -> None:
        """验证配置完整性

        检查：
        1. 必选依赖是否存在
        2. 配置组内部一致性
        3. 配置组间依赖关系

        参数：
            strict: 是否严格校验（默认 True）
                - True: event_bus=None 会抛出 ValueError（生产环境）
                - False: event_bus=None 只记录 warning（测试/装配场景）

        异常：
            ValueError: 配置验证失败（仅在 strict=True 时）
        """
        # 延迟注入检查（session_context 和 llm 可以延迟提供）
        if self.session_context is None:
            if strict:
                logger.warning(
                    "ConversationAgentConfig: session_context is None (will use default)"
                )

        if self.llm is None:
            if strict:
                logger.warning("ConversationAgentConfig: llm config is None (will use default)")

        # event_bus 可选（但生产环境推荐提供）
        if self.event_bus is None:
            if strict:
                raise ValueError("event_bus is required in production mode")
            logger.warning("ConversationAgentConfig.validate(strict=False): event_bus is None")

        # 配置组内部验证（__post_init__ 已执行）
        # 这里检查跨组依赖关系

        # 如果启用意图分类，推荐提供 coordinator
        if self.intent.enable_intent_classification and self.workflow.coordinator is None:
            logger.warning("Intent classification enabled but coordinator not provided")

        # 如果启用子 Agent 生成，必须提供 coordinator
        if self.workflow.enable_subagent_spawn and self.workflow.coordinator is None:
            logger.warning("Subagent spawn enabled but coordinator not provided")

        # 如果启用进度事件，必须提供 event_bus
        if self.workflow.enable_progress_events and self.event_bus is None:
            logger.warning("Progress events enabled but event_bus not provided")

        # 流式输出配置验证（P2迭代3：SaveRequest系统改进）
        if self.streaming:
            self.streaming.validate(event_bus=self.event_bus, strict=False)  # 默认非严格

        logger.info("ConversationAgentConfig validation passed")

    def with_overrides(self, **kwargs: Any) -> ConversationAgentConfig:
        """创建配置副本并覆盖部分参数

        支持直接覆盖顶层字段或配置组：

        使用示例：
            # 覆盖顶层字段
            new_config = config.with_overrides(event_bus=new_bus)

            # 覆盖配置组
            new_config = config.with_overrides(
                react=ReActConfig(max_iterations=20)
            )

            # 混合覆盖
            new_config = config.with_overrides(
                event_bus=new_bus,
                intent=IntentConfig(enable_intent_classification=True)
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
            "session_context_configured": self.session_context is not None,
            "event_bus_configured": self.event_bus is not None,
            "model_metadata_port_configured": self.model_metadata_port is not None,
            "llm": {
                "llm_configured": self.llm is not None and self.llm.llm is not None,
                "model": self.llm.model if self.llm else None,
                "temperature": self.llm.temperature if self.llm else None,
                "max_tokens": self.llm.max_tokens if self.llm else None,
            },
            "react": {
                "max_iterations": self.react.max_iterations,
                "timeout_seconds": self.react.timeout_seconds,
                "enable_reasoning_trace": self.react.enable_reasoning_trace,
                "enable_parallel_actions": self.react.enable_parallel_actions,
            },
            "intent": {
                "enable_intent_classification": self.intent.enable_intent_classification,
                "intent_confidence_threshold": self.intent.intent_confidence_threshold,
                "fallback_to_react": self.intent.fallback_to_react,
                "use_rule_based_extraction": self.intent.use_rule_based_extraction,
            },
            "workflow": {
                "coordinator_configured": self.workflow.coordinator is not None,
                "enable_subagent_spawn": self.workflow.enable_subagent_spawn,
                "enable_feedback_listening": self.workflow.enable_feedback_listening,
                "enable_progress_events": self.workflow.enable_progress_events,
                "subagent_timeout_seconds": self.workflow.subagent_timeout_seconds,
            },
            "streaming": {
                "emitter_configured": self.streaming.emitter is not None,
                "stream_emitter_configured": self.streaming.stream_emitter is not None,
                "enable_sse": self.streaming.enable_sse,
                "enable_save_request_channel": self.streaming.enable_save_request_channel,
            },
            "resource": {
                "max_tokens": self.resource.max_tokens,
                "max_cost": self.resource.max_cost,
                "enable_token_tracking": self.resource.enable_token_tracking,
                "enable_cost_tracking": self.resource.enable_cost_tracking,
            },
        }


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "LLMConfig",
    "ReActConfig",
    "IntentConfig",
    "WorkflowConfig",
    "StreamingConfig",
    "ResourceConfig",
    "ConversationAgentConfig",
]

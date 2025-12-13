"""Unified supervision protocols (P1-8 Phase 1)

目标：
- 用 typing.Protocol 定义统一的结构化子类型接口
- 不强制物理合并现有实现；通过 adapter 让现有模块无侵入接入
- 为未来监督系统统一打下基础

设计原则：
- 只依赖标准库类型
- 使用 Protocol 实现结构化子类型
- 提供适配器包装现有实现

使用示例：
    from src.domain.services.supervision.protocols import (
        SupervisionAnalyzer,
        AnalysisRequest,
        SupervisionModuleAnalyzerAdapter,
    )

    # 包装现有模块
    module = SupervisionModule()
    analyzer: SupervisionAnalyzer = SupervisionModuleAnalyzerAdapter(module)

    # 使用统一接口
    result = analyzer.analyze(AnalysisRequest(kind="context", payload=context))

Created: 2025-12-13 (P1-8 Phase 1)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict, TypeVar, runtime_checkable

# =============================================================================
# Type Variables
# =============================================================================

JSONMapping = Mapping[str, Any]

_InputT = TypeVar("_InputT", contravariant=True)
_OutputT = TypeVar("_OutputT", covariant=True)
_ActionT = TypeVar("_ActionT", contravariant=True)
_ExecResultT = TypeVar("_ExecResultT", covariant=True)
_StrategyT = TypeVar("_StrategyT", covariant=True)


# =============================================================================
# Unified Result Models
# =============================================================================


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """统一分析结果

    属性：
    - findings: 分析发现列表
    - severity: 严重程度 (low/medium/high/critical)
    - recommendations: 建议列表
    - metadata: 额外元数据
    - raw: 原始返回值（向后兼容）
    """

    findings: Sequence[Any] = ()
    severity: str = "low"
    recommendations: Sequence[str] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """统一执行结果

    属性：
    - success: 是否成功
    - action_taken: 执行的动作
    - message: 结果消息
    - outcome: 执行结果数据
    - audit_trail: 审计记录
    - raw: 原始返回值（向后兼容）
    """

    success: bool = True
    action_taken: str = ""
    message: str = ""
    outcome: dict[str, Any] = field(default_factory=dict)
    audit_trail: Sequence[Any] = ()
    raw: Any | None = None


class StrategyRecord(TypedDict, total=False):
    """策略记录（与 strategy_repo.py 兼容）"""

    id: str
    name: str
    trigger_conditions: list[str]
    action: str
    priority: int
    action_params: dict[str, Any]
    enabled: bool
    created_at: str


# =============================================================================
# Core Protocols
# =============================================================================


@runtime_checkable
class SupervisionAnalyzer(Protocol[_InputT, _OutputT]):
    """统一监督分析器协议

    用于分析上下文、请求、决策链等，返回分析结果。

    实现者：
    - SupervisionModule (via adapter)
    - PromptScanner (via adapter)
    - SupervisionCoordinator (via adapter)
    """

    def analyze(self, input: _InputT, /) -> _OutputT:
        """分析输入并返回结果"""
        ...


@runtime_checkable
class InterventionExecutor(Protocol[_ActionT, _ExecResultT]):
    """统一干预执行器协议

    用于执行干预动作（上下文注入、任务终止、重新规划等）。

    实现者：
    - InterventionManager (via adapter)
    """

    def execute(self, action: _ActionT, /) -> _ExecResultT:
        """执行干预动作"""
        ...


@runtime_checkable
class StrategyProvider(Protocol[_InputT, _StrategyT]):
    """统一策略提供者协议

    根据上下文返回最匹配的策略。

    实现者：
    - StrategyRepository (via adapter)
    """

    def get_strategy(self, context: _InputT, /) -> _StrategyT | None:
        """获取匹配的策略，无匹配返回 None"""
        ...


# =============================================================================
# Unified Request Models
# =============================================================================


AnalysisKind = Literal["context", "save_request", "decision_chain", "text"]


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    """统一分析请求

    用于适配器输入，指定分析类型和载荷。

    kind 取值：
    - "context": 分析上下文 (payload 为 dict)
    - "save_request": 分析保存请求 (payload 为 dict)
    - "decision_chain": 分析决策链 (payload 包含 decisions, session_id)
    - "text": 分析文本 (payload 包含 text/message)
    """

    kind: AnalysisKind
    payload: dict[str, Any] = field(default_factory=dict)


InterventionKind = Literal[
    "context_injection",
    "task_termination",
    "workflow_termination",
    "replan_requested",
]


@dataclass(frozen=True, slots=True)
class InterventionRequest:
    """统一干预请求

    用于适配器输入，指定干预类型和参数。

    kind 取值：
    - "context_injection": 注入上下文
    - "task_termination": 终止任务
    - "workflow_termination": 终止工作流
    - "replan_requested": 请求重新规划
    """

    kind: InterventionKind
    target_agent: str = ""
    context_type: str = ""
    message: str = ""
    severity: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)
    task_id: str = ""
    workflow_id: str = ""
    reason: str = ""
    graceful: bool = True
    context: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Adapters for Existing Implementations
# =============================================================================


class SupervisionModuleAnalyzerAdapter(SupervisionAnalyzer[AnalysisRequest, AnalysisResult]):
    """适配 supervision_module.SupervisionModule

    将 SupervisionModule 包装为统一的 SupervisionAnalyzer 接口。

    期望被适配对象提供：
    - analyze_context(context: dict) -> list[SupervisionInfo]
    - analyze_save_request(request: dict) -> list[SupervisionInfo]
    - analyze_decision_chain(decisions, session_id) -> list[SupervisionInfo]
    """

    def __init__(self, module: Any) -> None:
        """初始化适配器

        参数：
            module: SupervisionModule 实例
        """
        self._module = module

    def analyze(self, input: AnalysisRequest, /) -> AnalysisResult:
        """执行分析

        参数：
            input: 统一分析请求

        返回：
            统一分析结果
        """
        kind = input.kind
        payload = input.payload

        if kind == "context":
            raw = self._module.analyze_context(payload)
        elif kind == "save_request":
            raw = self._module.analyze_save_request(payload)
        elif kind == "decision_chain":
            decisions = payload.get("decisions", [])
            session_id = payload.get("session_id", "unknown")
            raw = self._module.analyze_decision_chain(decisions, session_id)
        else:
            raise ValueError(f"Unsupported analysis kind for SupervisionModule: {kind}")

        return AnalysisResult(
            findings=raw if isinstance(raw, Sequence) else (raw,),
            metadata={"kind": kind},
            raw=raw,
        )


class PromptScannerAnalyzerAdapter(SupervisionAnalyzer[AnalysisRequest, AnalysisResult]):
    """适配 supervision_strategy.PromptScanner

    将 PromptScanner 包装为统一的 SupervisionAnalyzer 接口。

    期望被适配对象提供：
    - scan(text: str) -> ScanResult
    """

    def __init__(self, scanner: Any) -> None:
        """初始化适配器

        参数：
            scanner: PromptScanner 实例
        """
        self._scanner = scanner

    def analyze(self, input: AnalysisRequest, /) -> AnalysisResult:
        """执行文本扫描

        参数：
            input: 统一分析请求 (kind 必须为 "text")

        返回：
            统一分析结果
        """
        if input.kind != "text":
            raise ValueError(f"Unsupported analysis kind for PromptScanner: {input.kind}")

        text = (
            input.payload.get("text")
            or input.payload.get("message")
            or input.payload.get("input")
            or ""
        )
        raw = self._scanner.scan(text)

        # 从 ScanResult 提取严重程度
        severity = "low"
        action = getattr(raw, "recommended_action", "")
        if action in {"block", "terminate"}:
            severity = "high"

        return AnalysisResult(
            findings=[raw],
            severity=severity,
            metadata={"kind": "text"},
            raw=raw,
        )


class InterventionManagerExecutorAdapter(
    InterventionExecutor[InterventionRequest, ExecutionResult]
):
    """适配 supervision_strategy.InterventionManager

    将 InterventionManager 包装为统一的 InterventionExecutor 接口。

    期望被适配对象提供：
    - inject_context(target_agent, context_type, message, severity, metadata)
    - terminate_task(task_id, reason, graceful, workflow_id)
    - terminate_workflow(workflow_id, reason, graceful) (可选)
    - trigger_replan(workflow_id, reason, context, constraints)
    """

    def __init__(self, manager: Any) -> None:
        """初始化适配器

        参数：
            manager: InterventionManager 实例
        """
        self._manager = manager

    def execute(self, action: InterventionRequest, /) -> ExecutionResult:
        """执行干预动作

        参数：
            action: 统一干预请求

        返回：
            统一执行结果
        """
        kind = action.kind

        if kind == "context_injection":
            raw = self._manager.inject_context(
                target_agent=action.target_agent,
                context_type=action.context_type,
                message=action.message,
                severity=action.severity,
                metadata=action.metadata or None,
            )
            return ExecutionResult(
                success=True,
                action_taken="context_injection",
                message=action.message,
                raw=raw,
            )

        if kind == "task_termination":
            raw = self._manager.terminate_task(
                task_id=action.task_id,
                reason=action.reason or action.message,
                graceful=action.graceful,
                workflow_id=action.workflow_id,
            )
            return ExecutionResult(
                success=getattr(raw, "success", True),
                action_taken="task_termination",
                message=getattr(raw, "message", "") or action.reason,
                raw=raw,
            )

        if kind == "workflow_termination":
            if not hasattr(self._manager, "terminate_workflow"):
                raise ValueError("terminate_workflow not supported by this manager")
            raw = self._manager.terminate_workflow(
                workflow_id=action.workflow_id,
                reason=action.reason or action.message,
                graceful=action.graceful,
            )
            return ExecutionResult(
                success=getattr(raw, "success", True),
                action_taken="workflow_termination",
                message=getattr(raw, "message", "") or action.reason,
                raw=raw,
            )

        if kind == "replan_requested":
            raw = self._manager.trigger_replan(
                workflow_id=action.workflow_id,
                reason=action.reason or action.message,
                context=action.context or None,
                constraints=action.constraints or None,
            )
            return ExecutionResult(
                success=True,
                action_taken="replan_requested",
                message=action.reason or action.message,
                raw=raw,
            )

        raise ValueError(f"Unsupported intervention kind: {kind}")


class StrategyRepositoryProviderAdapter(StrategyProvider[JSONMapping, StrategyRecord]):
    """适配 supervision/strategy_repo.StrategyRepository

    将 StrategyRepository 包装为统一的 StrategyProvider 接口。

    期望被适配对象提供：
    - find_by_condition(condition: str) -> list[StrategyRecord]
    """

    def __init__(
        self,
        repository: Any,
        *,
        condition_keys: Sequence[str] = ("condition", "trigger_condition", "category"),
    ) -> None:
        """初始化适配器

        参数：
            repository: StrategyRepository 实例
            condition_keys: 从 context 提取条件的键名优先级
        """
        self._repository = repository
        self._condition_keys = tuple(condition_keys)

    def get_strategy(self, context: JSONMapping, /) -> StrategyRecord | None:
        """获取匹配的策略

        参数：
            context: 包含条件信息的上下文

        返回：
            最高优先级的匹配策略，或 None
        """
        condition = ""
        for key in self._condition_keys:
            value = context.get(key)
            if isinstance(value, str) and value:
                condition = value
                break

        if not condition:
            return None

        matches = self._repository.find_by_condition(condition)
        if not matches:
            return None

        # StrategyRepository 已按 priority 排序；取第一个作为最匹配
        return matches[0]  # type: ignore[return-value]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Unified models
    "AnalysisResult",
    "ExecutionResult",
    "StrategyRecord",
    # Protocols
    "SupervisionAnalyzer",
    "InterventionExecutor",
    "StrategyProvider",
    # Unified requests
    "AnalysisRequest",
    "AnalysisKind",
    "InterventionRequest",
    "InterventionKind",
    # Adapters
    "SupervisionModuleAnalyzerAdapter",
    "PromptScannerAnalyzerAdapter",
    "InterventionManagerExecutorAdapter",
    "StrategyRepositoryProviderAdapter",
]

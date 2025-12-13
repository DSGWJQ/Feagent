"""监督系统包

Phase 34.14: supervision 包统一导出
Phase P1-8: 统一协议接口

将 supervision_modules.py 拆分为模块化包结构：
- models.py: 数据模型（DetectionResult, ComprehensiveCheckResult, TerminationResult）
- events.py: 事件定义（InterventionEvent, ContextInjectionEvent, TaskTerminationEvent）
- conversation.py: 对话监督（ConversationSupervisionModule）
- efficiency.py: 效率监控（WorkflowEfficiencyMonitor）
- strategy_repo.py: 策略库（StrategyRepository）
- coordinator.py: 协调器（SupervisionCoordinator）
- protocols.py: 统一协议接口（P1-8 Phase 1）
"""

from __future__ import annotations

from .conversation import ConversationSupervisionModule
from .coordinator import SupervisionCoordinator
from .efficiency import WorkflowEfficiencyMonitor
from .events import ContextInjectionEvent, InterventionEvent, TaskTerminationEvent
from .models import ComprehensiveCheckResult, DetectionResult, TerminationResult
from .protocols import (
    AnalysisRequest,
    AnalysisResult,
    ExecutionResult,
    InterventionExecutor,
    InterventionManagerExecutorAdapter,
    InterventionRequest,
    PromptScannerAnalyzerAdapter,
    StrategyProvider,
    StrategyRecord,
    StrategyRepositoryProviderAdapter,
    SupervisionAnalyzer,
    SupervisionModuleAnalyzerAdapter,
)
from .strategy_repo import StrategyRepository

__all__ = [
    # 数据模型
    "DetectionResult",
    "ComprehensiveCheckResult",
    "TerminationResult",
    # 事件
    "InterventionEvent",
    "ContextInjectionEvent",
    "TaskTerminationEvent",
    # 业务模块
    "ConversationSupervisionModule",
    "WorkflowEfficiencyMonitor",
    "StrategyRepository",
    "SupervisionCoordinator",
    # P1-8 统一协议
    "AnalysisResult",
    "ExecutionResult",
    "StrategyRecord",
    "SupervisionAnalyzer",
    "InterventionExecutor",
    "StrategyProvider",
    "AnalysisRequest",
    "InterventionRequest",
    "SupervisionModuleAnalyzerAdapter",
    "PromptScannerAnalyzerAdapter",
    "InterventionManagerExecutorAdapter",
    "StrategyRepositoryProviderAdapter",
]

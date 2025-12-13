"""监督模块（向后兼容）

⚠️ DEPRECATED: 本模块已在 Phase 34.14 拆分为子包 `supervision/`

新导入路径：
    from src.domain.services.supervision import SupervisionCoordinator
    from src.domain.services.supervision import ConversationSupervisionModule
    from src.domain.services.supervision import WorkflowEfficiencyMonitor
    from src.domain.services.supervision import StrategyRepository
    from src.domain.services.supervision import DetectionResult
    from src.domain.services.supervision import InterventionEvent
    ...

本文件保留向后兼容性，所有导入均转发至新包。

旧导入方式仍然有效：
    from src.domain.services.supervision import SupervisionCoordinator  # 仍可用

建议迁移：
    - 更新导入语句使用新包路径
    - 代码逻辑保持不变
    - 所有 API 接口完全兼容

模块结构：
    supervision/
    ├── __init__.py          # 包导出
    ├── models.py            # 数据模型（DetectionResult, ComprehensiveCheckResult, TerminationResult）
    ├── events.py            # 事件定义（InterventionEvent, ContextInjectionEvent, TaskTerminationEvent）
    ├── conversation.py      # 对话监督（ConversationSupervisionModule）
    ├── efficiency.py        # 效率监控（WorkflowEfficiencyMonitor）
    ├── strategy_repo.py     # 策略库（StrategyRepository）
    └── coordinator.py       # 协调器（SupervisionCoordinator）
"""

from __future__ import annotations

# ==================== DEPRECATION WARNING ====================
import warnings

warnings.warn(
    "supervision_modules.py is deprecated (Phase 34.14). "
    "Use 'from src.domain.services.supervision import XXX' instead. "
    "This module will be removed in version 2.0 (2026-06-01). "
    "See docs/architecture/SUPERVISION_MIGRATION_GUIDE.md for migration instructions.",
    DeprecationWarning,
    stacklevel=2,
)

# ==================== 向后兼容导入 ====================
# 从新包导入所有组件并重新导出
from src.domain.services.supervision import (  # noqa: E402
    ComprehensiveCheckResult,
    ContextInjectionEvent,
    ConversationSupervisionModule,
    DetectionResult,
    InterventionEvent,
    StrategyRepository,
    SupervisionCoordinator,
    TaskTerminationEvent,
    TerminationResult,
    WorkflowEfficiencyMonitor,
)

# ==================== 导出列表（保持不变）====================
__all__ = [
    "DetectionResult",
    "ComprehensiveCheckResult",
    "TerminationResult",
    "InterventionEvent",
    "ContextInjectionEvent",
    "TaskTerminationEvent",
    "ConversationSupervisionModule",
    "WorkflowEfficiencyMonitor",
    "StrategyRepository",
    "SupervisionCoordinator",
]

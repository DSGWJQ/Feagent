"""监督模块数据模型

Phase 34.14: 从 supervision_modules.py 提取共享数据模型

提供监督系统使用的数据类：
- DetectionResult: 检测结果
- ComprehensiveCheckResult: 综合检查结果
- TerminationResult: 终止结果
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ==================== 数据类定义 ====================


@dataclass
class DetectionResult:
    """检测结果"""

    detected: bool = False
    category: str = ""
    severity: str = "low"  # low, medium, high
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComprehensiveCheckResult:
    """综合检查结果"""

    passed: bool = True
    issues: list[DetectionResult] = field(default_factory=list)
    action: str = "allow"  # allow, warn, block, terminate

    def add_issue(self, issue: DetectionResult) -> None:
        """添加问题"""
        self.issues.append(issue)
        self.passed = False


@dataclass
class TerminationResult:
    """终止结果"""

    success: bool = True
    task_id: str = ""
    termination_type: str = "graceful"  # graceful, immediate
    message: str = ""
    severity: str = "medium"  # low, medium, high, critical


__all__ = [
    "DetectionResult",
    "ComprehensiveCheckResult",
    "TerminationResult",
]

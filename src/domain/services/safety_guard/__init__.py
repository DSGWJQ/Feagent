"""SafetyGuard - 安全校验服务包

Phase 35.2: 从单文件重构为包结构，添加规则构建器。

模块：
- core: SafetyGuard核心（文件操作、API调用、人机交互校验）
- rules: Rule数据类（从CoordinatorAgent迁移）
- payload_rule_builder: PayloadRuleBuilder（Payload验证规则构建器）
- dag_rule_builder: DagRuleBuilder（DAG验证规则构建器）
"""

from src.domain.services.safety_guard.core import SafetyGuard, ValidationResult
from src.domain.services.safety_guard.dag_rule_builder import CycleDetector, DagRuleBuilder
from src.domain.services.safety_guard.payload_rule_builder import PayloadRuleBuilder
from src.domain.services.safety_guard.rules import Rule

__all__ = [
    "SafetyGuard",
    "ValidationResult",
    "Rule",
    "PayloadRuleBuilder",
    "DagRuleBuilder",
    "CycleDetector",
]

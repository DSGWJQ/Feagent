"""干预策略系统

提供干预级别判定、严重程度计算、干预动作决策等功能。

组件：
- InterventionLevel: 干预级别枚举
- InterventionAction: 干预动作枚举
- Intervention: 干预结果
- SeverityCalculator: 严重程度计算器
- InterventionStrategy: 干预策略

设计原则：
- 分级干预：根据问题严重程度采取不同动作
- 可配置：阈值可调整
- 透明：干预理由清晰
"""

from dataclasses import dataclass
from enum import Enum


class SeverityLevel(Enum):
    """严重程度级别

    Phase 35.0 修复：重命名 InterventionLevel → SeverityLevel 避免与执行层枚举冲突

    从低到高排序：
    - NONE: 无需干预
    - LOW: 轻微问题
    - MEDIUM: 中度问题
    - HIGH: 严重问题
    - CRITICAL: 危急问题
    """

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class InterventionAction(Enum):
    """干预动作

    - pass: 放行，不干预
    - warn: 警告并继续
    - suggest: 建议修正
    - reject: 拒绝决策
    - terminate: 终止任务
    """

    PASS = "pass"
    WARN = "warn"
    SUGGEST = "suggest"
    REJECT = "reject"
    TERMINATE = "terminate"


@dataclass
class Intervention:
    """干预结果

    属性：
    - level: 严重程度级别
    - action: 干预动作
    - reason: 干预理由
    - suggestion: 修正建议（可选）
    """

    level: SeverityLevel
    action: InterventionAction
    reason: str
    suggestion: str | None = None


class SeverityCalculator:
    """严重程度计算器

    综合多个维度计算问题严重程度。

    计算公式：
    severity = max(
        violation_score,
        alignment_penalty,
        resource_penalty
    )

    使用示例：
        calculator = SeverityCalculator()
        severity = calculator.calculate(
            rule_violations=["违规1"],
            alignment_score=0.7,
            resource_usage_ratio=0.5
        )
    """

    def __init__(
        self,
        violation_weight: float = 0.3,
        alignment_weight: float = 0.4,
        resource_weight: float = 0.3,
    ):
        """初始化

        参数：
            violation_weight: 违规权重
            alignment_weight: 对齐权重
            resource_weight: 资源权重
        """
        self.violation_weight = violation_weight
        self.alignment_weight = alignment_weight
        self.resource_weight = resource_weight

    def calculate(
        self, rule_violations: list[str], alignment_score: float, resource_usage_ratio: float
    ) -> float:
        """计算严重程度

        参数：
            rule_violations: 规则违规列表
            alignment_score: 对齐分数 (0-1, 越高越好)
            resource_usage_ratio: 资源使用比例 (0-1, 越低越好)

        返回：
            严重程度 (0-1, 越高越严重)
        """
        # 如果没有任何问题，返回0
        if not rule_violations and alignment_score >= 0.7 and resource_usage_ratio <= 0.5:
            return 0.0

        scores = []

        # 1. 违规分数 - 每个违规增加0.2，最高1.0
        if rule_violations:
            violation_score = min(1.0, len(rule_violations) * 0.2)
            scores.append(violation_score)

        # 2. 对齐惩罚 - 对齐分数越低，惩罚越高
        # alignment_score: 1.0 -> penalty: 0.0
        # alignment_score: 0.5 -> penalty: 0.5
        # alignment_score: 0.0 -> penalty: 1.0
        alignment_penalty = 1.0 - alignment_score
        if alignment_penalty > 0.3:  # 只有显著偏离才计入
            scores.append(alignment_penalty)

        # 3. 资源惩罚 - 资源使用越高，惩罚越高
        if resource_usage_ratio > 0.5:  # 只有超过50%才计入
            resource_penalty = resource_usage_ratio
            scores.append(resource_penalty)

        # 返回最大分数作为综合严重程度
        return max(scores) if scores else 0.0


class InterventionStrategy:
    """干预策略

    根据严重程度决定干预动作。

    阈值配置：
    - severity < 0.2: PASS
    - 0.2 <= severity < 0.4: WARN
    - 0.4 <= severity < 0.6: SUGGEST
    - 0.6 <= severity < 0.8: REJECT
    - severity >= 0.8: TERMINATE

    使用示例：
        strategy = InterventionStrategy()
        intervention = strategy.decide(
            rule_violations=["违规1"],
            alignment_score=0.5,
            resource_usage_ratio=0.7
        )
    """

    def __init__(
        self,
        pass_threshold: float = 0.2,
        warn_threshold: float = 0.4,
        suggest_threshold: float = 0.6,
        reject_threshold: float = 0.8,
    ):
        """初始化

        参数：
            pass_threshold: 放行阈值
            warn_threshold: 警告阈值
            suggest_threshold: 建议阈值
            reject_threshold: 拒绝阈值
        """
        self.pass_threshold = pass_threshold
        self.warn_threshold = warn_threshold
        self.suggest_threshold = suggest_threshold
        self.reject_threshold = reject_threshold

        self.severity_calculator = SeverityCalculator()

    def decide(
        self,
        rule_violations: list[str],
        alignment_score: float,
        resource_usage_ratio: float,
        suggestion: str | None = None,
    ) -> Intervention:
        """决定干预措施

        参数：
            rule_violations: 规则违规列表
            alignment_score: 对齐分数
            resource_usage_ratio: 资源使用比例
            suggestion: 修正建议（可选）

        返回：
            干预结果
        """
        # 计算严重程度
        severity = self.severity_calculator.calculate(
            rule_violations=rule_violations,
            alignment_score=alignment_score,
            resource_usage_ratio=resource_usage_ratio,
        )

        # 根据严重程度决定干预
        if severity < self.pass_threshold:
            return Intervention(
                level=SeverityLevel.NONE, action=InterventionAction.PASS, reason="一切正常"
            )

        elif severity < self.warn_threshold:
            return Intervention(
                level=SeverityLevel.LOW,
                action=InterventionAction.WARN,
                reason=self._build_reason(rule_violations, alignment_score, resource_usage_ratio),
                suggestion=suggestion,
            )

        elif severity < self.suggest_threshold:
            return Intervention(
                level=SeverityLevel.MEDIUM,
                action=InterventionAction.SUGGEST,
                reason=self._build_reason(rule_violations, alignment_score, resource_usage_ratio),
                suggestion=suggestion or "建议修正决策",
            )

        elif severity < self.reject_threshold:
            return Intervention(
                level=SeverityLevel.HIGH,
                action=InterventionAction.REJECT,
                reason=self._build_reason(rule_violations, alignment_score, resource_usage_ratio),
                suggestion=suggestion,
            )

        else:
            return Intervention(
                level=SeverityLevel.CRITICAL,
                action=InterventionAction.TERMINATE,
                reason=self._build_reason(rule_violations, alignment_score, resource_usage_ratio),
                suggestion=None,
            )

    def _build_reason(
        self, rule_violations: list[str], alignment_score: float, resource_usage_ratio: float
    ) -> str:
        """构建干预理由

        参数：
            rule_violations: 规则违规列表
            alignment_score: 对齐分数
            resource_usage_ratio: 资源使用比例

        返回：
            干预理由字符串
        """
        reasons = []

        if rule_violations:
            reasons.append(f"规则违规: {len(rule_violations)}项")

        if alignment_score < 0.5:
            reasons.append(f"目标对齐度低: {alignment_score:.1%}")

        if resource_usage_ratio > 0.7:
            reasons.append(f"资源使用过高: {resource_usage_ratio:.1%}")

        return "; ".join(reasons) if reasons else "检测到问题"


# 导出
__all__ = [
    "SeverityLevel",  # Phase 35.0: 重命名 InterventionLevel → SeverityLevel
    "InterventionAction",
    "Intervention",
    "SeverityCalculator",
    "InterventionStrategy",
]

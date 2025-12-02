"""决策验证器 (Decision Validator) - Phase 7.2

业务定义：
- 验证对话Agent的决策
- 集成规则库进行多维度检查
- 支持自动修正建议
- 提供详细的验证结果

验证流程：
1. 接收决策请求
2. 按优先级检查规则
3. 收集违规信息
4. 尝试自动修正
5. 生成验证结果

设计原则：
- 责任链模式：按优先级依次检查规则
- 策略模式：不同类型的规则使用不同检查策略
- 开放封闭：易于扩展新的检查逻辑
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.enhanced_rule_repository import (
    EnhancedRuleRepository,
    RuleCategory,
)
from src.domain.services.rule_engine import RuleAction, RuleViolation

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """验证状态"""

    APPROVED = "approved"  # 批准执行
    MODIFIED = "modified"  # 修正后批准
    REJECTED = "rejected"  # 拒绝
    ESCALATED = "escalated"  # 升级处理


@dataclass
class DecisionRequest:
    """决策请求

    属性：
    - decision_id: 决策唯一标识
    - decision_type: 决策类型 (create_node, execute_workflow, etc.)
    - payload: 决策内容
    - context: 当前上下文
    - requester: 请求者标识
    - timestamp: 请求时间
    """

    decision_id: str
    decision_type: str
    payload: dict[str, Any]
    context: dict[str, Any]
    requester: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationResult:
    """验证结果

    属性：
    - status: 验证状态
    - original_request: 原始请求
    - modified_payload: 修正后的决策内容（仅MODIFIED时有值）
    - violations: 违规列表
    - suggestions: 建议列表
    - timestamp: 验证时间
    """

    status: ValidationStatus
    original_request: DecisionRequest
    violations: list[RuleViolation] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    modified_payload: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class DecisionValidator:
    """决策验证器

    职责：
    1. 验证决策是否符合规则
    2. 收集违规信息
    3. 提供修正建议
    4. 检查目标对齐

    使用示例：
        repo = EnhancedRuleRepository()
        validator = DecisionValidator(rule_repository=repo)
        result = validator.validate(request)
    """

    def __init__(
        self,
        rule_repository: EnhancedRuleRepository,
        goal_checker: Any | None = None,
    ):
        """初始化决策验证器

        参数：
            rule_repository: 规则库
            goal_checker: 目标对齐检测器（可选）
        """
        self.rule_repository = rule_repository
        self.goal_checker = goal_checker
        self._goal: str | None = None

    def set_goal(self, goal: str) -> None:
        """设置当前目标

        参数：
            goal: 目标描述
        """
        self._goal = goal

    def validate(self, request: DecisionRequest) -> ValidationResult:
        """验证决策

        流程：
        1. 构建验证上下文
        2. 按类别检查规则
        3. 检查目标对齐
        4. 收集违规和建议
        5. 确定验证状态

        参数：
            request: 决策请求

        返回：
            验证结果
        """
        violations: list[RuleViolation] = []
        suggestions: list[str] = []

        # 构建验证上下文
        eval_context = self._build_eval_context(request)

        # 1. 检查行为边界规则
        behavior_violations = self._check_rules_by_category(eval_context, RuleCategory.BEHAVIOR)
        violations.extend(behavior_violations)

        # 2. 检查工具约束规则
        tool_violations = self._check_rules_by_category(eval_context, RuleCategory.TOOL)
        violations.extend(tool_violations)

        # 3. 检查数据访问规则
        data_violations = self._check_rules_by_category(eval_context, RuleCategory.DATA)
        violations.extend(data_violations)

        # 4. 检查执行策略规则
        exec_violations = self._check_rules_by_category(eval_context, RuleCategory.EXECUTION)
        violations.extend(exec_violations)

        # 5. 检查目标对齐
        if self._goal and self.goal_checker:
            goal_violations = self._check_goal_alignment(request)
            violations.extend(goal_violations)

        # 6. 收集建议
        suggestions = self._collect_suggestions(violations)

        # 7. 确定状态
        status = self._determine_status(violations)

        return ValidationResult(
            status=status,
            original_request=request,
            violations=violations,
            suggestions=suggestions,
            modified_payload=self._try_auto_correct(request, violations)
            if status == ValidationStatus.MODIFIED
            else None,
        )

    def _build_eval_context(self, request: DecisionRequest) -> dict[str, Any]:
        """构建评估上下文

        参数：
            request: 决策请求

        返回：
            评估上下文
        """
        context = {
            "decision_id": request.decision_id,
            "decision_type": request.decision_type,
            "payload": request.payload,
            "requester": request.requester,
            **request.context,
            **request.payload,
        }
        return context

    def _check_rules_by_category(
        self, context: dict[str, Any], category: RuleCategory
    ) -> list[RuleViolation]:
        """按类别检查规则

        参数：
            context: 评估上下文
            category: 规则类别

        返回：
            违规列表
        """
        return self.rule_repository.evaluate_by_category(context, category)

    def _check_goal_alignment(self, request: DecisionRequest) -> list[RuleViolation]:
        """检查目标对齐

        参数：
            request: 决策请求

        返回：
            违规列表
        """
        if not self._goal or not self.goal_checker:
            return []

        # 获取行动描述
        action_desc = request.payload.get("action_description", "")
        if not action_desc:
            action_desc = str(request.payload)

        # 检查对齐
        score = self.goal_checker.check_alignment(self._goal, action_desc)

        if score < self.goal_checker.threshold:
            reason = self.goal_checker.get_deviation_reason(self._goal, action_desc)
            return [
                RuleViolation(
                    rule_id="goal_alignment_check",
                    rule_name="目标对齐检测",
                    action=RuleAction.SUGGEST_CORRECTION,
                    context={"goal": self._goal, "action": action_desc, "score": score},
                    message=reason or f"行动与目标对齐度不足 (分数: {score:.2f})",
                )
            ]

        return []

    def _collect_suggestions(self, violations: list[RuleViolation]) -> list[str]:
        """收集建议

        参数：
            violations: 违规列表

        返回：
            建议列表
        """
        suggestions = []

        for violation in violations:
            # 从规则元数据获取建议
            rule = self.rule_repository.get_rule(violation.rule_id)
            if rule and rule.metadata.get("suggestion"):
                suggestions.append(rule.metadata["suggestion"])

            # 从违规消息生成建议
            if violation.message and "建议" not in str(suggestions):
                suggestions.append(violation.message)

        return list(set(suggestions))  # 去重

    def _determine_status(self, violations: list[RuleViolation]) -> ValidationStatus:
        """确定验证状态

        参数：
            violations: 违规列表

        返回：
            验证状态
        """
        if not violations:
            return ValidationStatus.APPROVED

        # 检查是否有强制终止或拒绝的违规
        has_reject = any(
            v.action in [RuleAction.REJECT_DECISION, RuleAction.FORCE_TERMINATE] for v in violations
        )

        if has_reject:
            return ValidationStatus.REJECTED

        # 检查是否只有建议修正的违规
        all_suggestions = all(
            v.action in [RuleAction.SUGGEST_CORRECTION, RuleAction.LOG_WARNING] for v in violations
        )

        if all_suggestions:
            return ValidationStatus.MODIFIED

        return ValidationStatus.REJECTED

    def _try_auto_correct(
        self, request: DecisionRequest, violations: list[RuleViolation]
    ) -> dict[str, Any] | None:
        """尝试自动修正

        参数：
            request: 原始请求
            violations: 违规列表

        返回：
            修正后的payload，无法修正返回None
        """
        if not violations:
            return None

        # 目前只返回原始payload的副本，具体修正逻辑可以扩展
        modified = request.payload.copy()

        # 可以根据违规类型进行具体修正
        for violation in violations:
            rule = self.rule_repository.get_rule(violation.rule_id)
            if rule and rule.metadata.get("correction_type"):
                correction_type = rule.metadata["correction_type"]

                if correction_type == "field_restriction":
                    # 字段限制修正示例
                    if "config" in modified and "sql" in modified.get("config", {}):
                        # 标记需要修正
                        modified["_needs_field_restriction"] = True

        return modified


# 导出
__all__ = [
    "ValidationStatus",
    "DecisionRequest",
    "ValidationResult",
    "DecisionValidator",
]

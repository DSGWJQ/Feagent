"""增强规则库 (Enhanced Rule Repository) - Phase 7.1

业务定义：
- ��类存储和管理规则
- 支持按类别、来源、优先级查询
- 支持字符串和函数两种条件类型
- 提供规则评估功能

规则分类：
- BEHAVIOR: 行为边界规则（迭代次数、Token预算）
- TOOL: 工具使用约束（允许的工具、参数范围）
- DATA: 数据访问权限（敏感字段过滤）
- EXECUTION: 执行策略规则（超时、并发）
- GOAL: 目标对齐检测（偏离检测）

设计原则：
- 单一职责：只负责规则存储和评估
- 开放封闭：易于扩展新的规则类别
- 依赖倒置：通过协议定义规则条件
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.rule_engine import RuleAction, RuleViolation

logger = logging.getLogger(__name__)


class RuleCategory(str, Enum):
    """规则类别"""

    BEHAVIOR = "behavior"  # 行为边界
    TOOL = "tool"  # 工具约束
    DATA = "data"  # 数据访问
    EXECUTION = "execution"  # 执行策略
    GOAL = "goal"  # 目标对齐


class RuleSource(str, Enum):
    """规则来源"""

    USER = "user"  # 用户定义
    SYSTEM = "system"  # 系统预设
    TOOL = "tool"  # 工具配置
    GENERATED = "generated"  # 动态生成


class DuplicateRuleError(Exception):
    """重复规则异常"""

    pass


@dataclass
class EnhancedRule:
    """增强规则定义

    属性：
    - id: 规则唯一标识
    - name: 规则名称
    - category: 规则类别
    - description: 规则描述
    - condition: 条件（字符串表达式或函数）
    - action: 触发动作
    - priority: 优先级（越小越高）
    - source: 规则来源
    - enabled: 是否启用
    - metadata: 元数据��用于修正建议等）
    - created_at: 创建时间
    - updated_at: 更新时间
    """

    id: str
    name: str
    category: RuleCategory
    description: str
    condition: str | Callable[[dict[str, Any]], bool]
    action: RuleAction
    priority: int
    source: RuleSource
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class EnhancedRuleRepository:
    """增强规则库

    职责：
    1. 存储和管理规则
    2. 按类别、来源、优先级查询规则
    3. 评估规则并返回违规列表
    4. 支持规则的CRUD操作

    使用示例：
        repo = EnhancedRuleRepository()
        repo.add_rule(EnhancedRule(...))
        violations = repo.evaluate({"iteration_count": 15})
    """

    def __init__(self):
        """初始化增强规则库"""
        self._rules: dict[str, EnhancedRule] = {}

        # 用于安全评估字符串条件的内置函数
        self._safe_builtins = {
            "True": True,
            "False": False,
            "None": None,
            "abs": abs,
            "min": min,
            "max": max,
            "len": len,
            "sum": sum,
            "all": all,
            "any": any,
            "bool": bool,
            "int": int,
            "float": float,
            "str": str,
            "list": list,
            "dict": dict,
            "set": set,
        }

    def add_rule(self, rule: EnhancedRule) -> None:
        """添加规则

        参数：
            rule: 要添加的规则

        异常：
            DuplicateRuleError: 规则ID已存在
        """
        if rule.id in self._rules:
            raise DuplicateRuleError(f"规则ID '{rule.id}' 已存在")

        self._rules[rule.id] = rule
        logger.debug(f"添加规则: {rule.id} (类别: {rule.category.value})")

    def get_rule(self, rule_id: str) -> EnhancedRule | None:
        """根据ID获取规则

        参数：
            rule_id: 规则ID

        返回：
            规则对象，不存在则返回None
        """
        return self._rules.get(rule_id)

    def get_all_rules(self) -> list[EnhancedRule]:
        """获取所有规则（按优先级排序）

        返回：
            规则列表
        """
        return sorted(self._rules.values(), key=lambda r: r.priority)

    def get_rules_by_category(self, category: RuleCategory) -> list[EnhancedRule]:
        """按类别获取规则（按优先级排序）

        参数：
            category: 规则类别

        返回：
            规则列表
        """
        rules = [r for r in self._rules.values() if r.category == category]
        return sorted(rules, key=lambda r: r.priority)

    def get_rules_by_source(self, source: RuleSource) -> list[EnhancedRule]:
        """按来源获取规则（按优先级排序）

        参数：
            source: 规则来源

        返回：
            规则列表
        """
        rules = [r for r in self._rules.values() if r.source == source]
        return sorted(rules, key=lambda r: r.priority)

    def get_enabled_rules(self) -> list[EnhancedRule]:
        """获取所有启用的规则（按优先级排序）

        返回：
            规则列表
        """
        rules = [r for r in self._rules.values() if r.enabled]
        return sorted(rules, key=lambda r: r.priority)

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则

        参数：
            rule_id: 规则ID

        返回：
            是否成功移除
        """
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.debug(f"移除规则: {rule_id}")
            return True
        return False

    def update_rule(
        self,
        rule_id: str,
        name: str | None = None,
        description: str | None = None,
        condition: str | Callable[[dict[str, Any]], bool] | None = None,
        action: RuleAction | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """更新规则

        参数：
            rule_id: 规则ID
            其他参数: 要更新的字段

        返回：
            是否成功更新
        """
        rule = self._rules.get(rule_id)
        if not rule:
            return False

        if name is not None:
            rule.name = name
        if description is not None:
            rule.description = description
        if condition is not None:
            rule.condition = condition
        if action is not None:
            rule.action = action
        if priority is not None:
            rule.priority = priority
        if enabled is not None:
            rule.enabled = enabled
        if metadata is not None:
            rule.metadata = metadata

        rule.updated_at = datetime.now()
        logger.debug(f"更新规则: {rule_id}")
        return True

    def clear(self) -> None:
        """清空所有规则"""
        self._rules.clear()
        logger.debug("清空所有规则")

    def load_default_rules(self) -> None:
        """加载默认系统规则"""
        default_rules = [
            EnhancedRule(
                id="sys_max_iterations",
                name="最大迭代次数限制",
                category=RuleCategory.BEHAVIOR,
                description="防止ReAct循环过多迭代",
                condition="iteration_count > 10",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.SYSTEM,
                metadata={"max_value": 10, "suggestion": "请简化任务或分解为子任务"},
            ),
            EnhancedRule(
                id="sys_token_budget",
                name="Token预算限制",
                category=RuleCategory.BEHAVIOR,
                description="防止单次任务消耗过多token",
                condition="token_used > 10000",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.SYSTEM,
                metadata={"max_value": 10000, "suggestion": "请优化prompt或减少上下文"},
            ),
            EnhancedRule(
                id="sys_goal_deviation",
                name="目标偏离检测",
                category=RuleCategory.GOAL,
                description="检测对话Agent是否偏离目标",
                condition="alignment_score < 0.5",
                action=RuleAction.SUGGEST_CORRECTION,
                priority=2,
                source=RuleSource.SYSTEM,
                metadata={"threshold": 0.5, "suggestion": "请确保操作与原始目标相关"},
            ),
            EnhancedRule(
                id="sys_timeout",
                name="执行超时限制",
                category=RuleCategory.EXECUTION,
                description="单节点执行超时限制",
                condition="execution_time > 60",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.SYSTEM,
                metadata={"max_seconds": 60, "suggestion": "请优化执行逻辑或增加超时时间"},
            ),
        ]

        for rule in default_rules:
            if rule.id not in self._rules:
                self._rules[rule.id] = rule

        logger.info(f"加载了 {len(default_rules)} 条默认系统规则")

    def evaluate(self, context: dict[str, Any]) -> list[RuleViolation]:
        """评估所有启用的规则

        遍历所有启用的规则，检查条件是否满足。

        参数：
            context: 评估上下文

        返回：
            违规列表
        """
        violations: list[RuleViolation] = []

        for rule in self.get_enabled_rules():
            try:
                if self._check_condition(rule.condition, context):
                    violation = RuleViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        action=rule.action,
                        context=context,
                        message=f"规则 '{rule.name}' 被触发",
                    )
                    violations.append(violation)
                    logger.debug(f"规则违规: {rule.id}")
            except Exception as e:
                logger.warning(f"规则 {rule.id} 条件评估失败: {e}")

        return violations

    def evaluate_by_category(
        self, context: dict[str, Any], category: RuleCategory
    ) -> list[RuleViolation]:
        """按类别评估规则

        只检查指定类别的规则。

        参数：
            context: 评估上下文
            category: 规则类别

        返回：
            违规列表
        """
        violations: list[RuleViolation] = []

        rules = [r for r in self.get_enabled_rules() if r.category == category]

        for rule in rules:
            try:
                if self._check_condition(rule.condition, context):
                    violation = RuleViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        action=rule.action,
                        context=context,
                        message=f"规则 '{rule.name}' 被触发",
                    )
                    violations.append(violation)
                    logger.debug(f"规则违规: {rule.id}")
            except Exception as e:
                logger.warning(f"规则 {rule.id} 条件评估失败: {e}")

        return violations

    def _check_condition(
        self, condition: str | Callable[[dict[str, Any]], bool], context: dict[str, Any]
    ) -> bool:
        """检查条件是否满足

        参数：
            condition: 条件（字符串或函数）
            context: 上下文

        返回：
            条件是否满足
        """
        if callable(condition):
            return condition(context)

        # 字符串条件，使用安全eval
        try:
            result = eval(condition, {"__builtins__": self._safe_builtins}, context)
            return bool(result)
        except Exception:
            return False


# 导出
__all__ = [
    "RuleCategory",
    "RuleSource",
    "DuplicateRuleError",
    "EnhancedRule",
    "EnhancedRuleRepository",
]

"""规则引擎 (Rule Engine)

协调者Agent的核心组件，负责：
- 规则注册与管理
- 规则评估与匹配
- 规则优先级排序
- 规则动作执行

设计原则：
- 静态规则：从配置文件加载，适用于固定的业务规则
- 动态规则：运行时生成，适用于上下文相关的规则
- 安全评估：使用受限的表达式评估，防止代码注入

使用示例：
    engine = RuleEngine()
    engine.add_rule(Rule(
        id="max_iterations",
        name="最大迭代次数限制",
        description="防止ReAct循环过多迭代",
        type=RuleType.STATIC,
        priority=1,
        condition="iteration_count > 10",
        action=RuleAction.FORCE_TERMINATE,
    ))

    violations = engine.evaluate({"iteration_count": 15})
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class RuleType(Enum):
    """规则类型"""

    STATIC = "static"  # 静态规则（配置文件）
    DYNAMIC = "dynamic"  # 动态规则（运行时生成）


class RuleAction(Enum):
    """规则动作"""

    LOG_WARNING = "log_warning"  # 记录警告日志
    SUGGEST_CORRECTION = "suggest"  # 建议修正
    REJECT_DECISION = "reject"  # 拒绝决策
    FORCE_TERMINATE = "terminate"  # 强制终止


@dataclass
class Rule:
    """规则定义

    属性：
    - id: 规则唯一标识
    - name: 规则名称
    - description: 规则描述
    - type: 规则类型（静态/动态）
    - priority: 优先级（越小优先级越高）
    - condition: 条件表达式
    - action: 触发时的动作
    - enabled: 是否启用
    """

    id: str
    name: str
    description: str
    type: RuleType
    priority: int
    condition: str
    action: RuleAction
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RuleViolation:
    """规则违规

    当规则条件满足时生成违规记录。

    属性：
    - rule_id: 触发的规则ID
    - rule_name: 规则名称
    - action: 应执行的动作
    - context: 评估时的上下文
    - timestamp: 违规时间
    - message: 违规消息
    """

    rule_id: str
    rule_name: str
    action: RuleAction
    context: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message: str | None = None


class RuleEngine:
    """规则引擎

    协调者Agent的核心组件，负责评估规则并返回违规列表。

    职责：
    1. 管理规则（添加、删除、更新）
    2. 评估规则条件
    3. 生成违规记录
    4. 按优先级排序规则
    """

    def __init__(self):
        """初始化规则引擎"""
        self._rules: list[Rule] = []

    @property
    def rules(self) -> list[Rule]:
        """获取所有规则（按优先级排序）"""
        return self._rules

    def add_rule(self, rule: Rule) -> None:
        """添加规则

        规则添加后会自动按优先级排序。

        参数：
            rule: 要添加的规则
        """
        self._rules.append(rule)
        self._sort_rules()
        logger.debug(f"添加规则: {rule.id} (优先级: {rule.priority})")

    def remove_rule(self, rule_id: str) -> bool:
        """删除规则

        参数：
            rule_id: 规则ID

        返回：
            是否成功删除
        """
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                del self._rules[i]
                logger.debug(f"删除规则: {rule_id}")
                return True
        return False

    def get_rule(self, rule_id: str) -> Rule | None:
        """根据ID获取规则

        参数：
            rule_id: 规则ID

        返回：
            规则对象，不存在则返回None
        """
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def update_rule(
        self,
        rule_id: str,
        condition: str | None = None,
        action: RuleAction | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """更新规则

        参数：
            rule_id: 规则ID
            condition: 新的条件表达式
            action: 新的动作
            priority: 新的优先级
            enabled: 是否启用

        返回：
            是否成功更新
        """
        rule = self.get_rule(rule_id)
        if not rule:
            return False

        if condition is not None:
            rule.condition = condition
        if action is not None:
            rule.action = action
        if priority is not None:
            rule.priority = priority
            self._sort_rules()
        if enabled is not None:
            rule.enabled = enabled

        rule.updated_at = datetime.now()
        logger.debug(f"更新规则: {rule_id}")
        return True

    def evaluate(self, context: dict[str, Any]) -> list[RuleViolation]:
        """评估所有规则

        遍历所有启用的规则，检查条件是否满足。

        参数：
            context: 评估上下文（包含变量）

        返回：
            违规列表
        """
        violations: list[RuleViolation] = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            try:
                if self._check_condition(rule.condition, context):
                    violation = RuleViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        action=rule.action,
                        context=context,
                        message=f"规则 '{rule.name}' 被触发: {rule.condition}",
                    )
                    violations.append(violation)
                    logger.debug(f"规则违规: {rule.id} - {rule.condition}")
            except Exception as e:
                # 条件评估失败时记录日志但不中断
                logger.warning(f"规则 {rule.id} 条件评估失败: {e}")

        return violations

    def _check_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """检查条件是否满足

        使用受限的eval进行安全评估。

        参数：
            condition: 条件表达式
            context: 上下文变量

        返回：
            条件是否满足
        """
        try:
            # 使用受限的内置函数，防止代码注入
            safe_builtins = {
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
                "not": lambda x: not x,
                "and": lambda x, y: x and y,
                "or": lambda x, y: x or y,
            }

            result = eval(condition, {"__builtins__": safe_builtins}, context)
            return bool(result)
        except Exception:
            return False

    def _sort_rules(self) -> None:
        """按优先级排序规则（小的在前）"""
        self._rules.sort(key=lambda r: r.priority)

    def load_rules(self, config_path: str) -> None:
        """从YAML文件加载规则

        参数：
            config_path: 配置文件路径
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"规则配置文件不存在: {config_path}")

        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.load_rules_from_dict(config)
        logger.info(f"从 {config_path} 加载了 {len(self._rules)} 条规则")

    def load_rules_from_dict(self, config: dict[str, Any]) -> None:
        """从字典加载规则

        参数：
            config: 规则配置字典
        """
        rules_data = config.get("rules", [])

        for rule_data in rules_data:
            rule = self._parse_rule(rule_data)
            if rule:
                self.add_rule(rule)

    def _parse_rule(self, data: dict[str, Any]) -> Rule | None:
        """解析规则数据

        参数：
            data: 规则数据字典

        返回：
            Rule对象
        """
        try:
            # 解析规则类型
            rule_type_str = data.get("type", "static")
            rule_type = RuleType.STATIC if rule_type_str == "static" else RuleType.DYNAMIC

            # 解析规则动作
            action_str = data.get("action", "log_warning")
            action_map = {
                "log_warning": RuleAction.LOG_WARNING,
                "suggest": RuleAction.SUGGEST_CORRECTION,
                "reject": RuleAction.REJECT_DECISION,
                "terminate": RuleAction.FORCE_TERMINATE,
            }
            action = action_map.get(action_str, RuleAction.LOG_WARNING)

            return Rule(
                id=data["id"],
                name=data["name"],
                description=data.get("description", ""),
                type=rule_type,
                priority=data.get("priority", 10),
                condition=data["condition"],
                action=action,
                enabled=data.get("enabled", True),
            )
        except KeyError as e:
            logger.error(f"规则解析失败，缺少必要字段: {e}")
            return None

    def clear(self) -> None:
        """清空所有规则"""
        self._rules.clear()
        logger.debug("清空所有规则")


class RuleEngineFactory:
    """规则引擎工厂

    提供创建预配置规则引擎的便捷方法。
    """

    @staticmethod
    def create_default() -> RuleEngine:
        """创建默认规则引擎

        包含协调者Agent常用的预设规则。

        返回：
            配置好的规则引擎
        """
        engine = RuleEngine()

        # 预设规则
        default_rules = [
            Rule(
                id="max_iterations",
                name="最大迭代次数限制",
                description="防止ReAct循环过多迭代",
                type=RuleType.STATIC,
                priority=1,
                condition="iteration_count > 10",
                action=RuleAction.FORCE_TERMINATE,
            ),
            Rule(
                id="token_budget",
                name="Token预算限制",
                description="防止单次任务消耗过多token",
                type=RuleType.STATIC,
                priority=1,
                condition="token_used > 10000",
                action=RuleAction.FORCE_TERMINATE,
            ),
            Rule(
                id="goal_deviation",
                name="目标偏离检测",
                description="检测对话Agent是否偏离目标",
                type=RuleType.STATIC,
                priority=2,
                condition="alignment_score < 0.5",
                action=RuleAction.SUGGEST_CORRECTION,
            ),
            Rule(
                id="low_confidence",
                name="低置信度警告",
                description="决策置信度过低时警告",
                type=RuleType.STATIC,
                priority=3,
                condition="decision_confidence < 0.5",
                action=RuleAction.LOG_WARNING,
            ),
        ]

        for rule in default_rules:
            engine.add_rule(rule)

        return engine

    @staticmethod
    def create_with_rules(rules_config: list[dict[str, Any]]) -> RuleEngine:
        """使用自定义规则创建引擎

        参数：
            rules_config: 规则配置列表

        返回：
            配置好的规则引擎
        """
        engine = RuleEngine()
        engine.load_rules_from_dict({"rules": rules_config})
        return engine

    @staticmethod
    def create_from_file(config_path: str) -> RuleEngine:
        """从配置文件创建引擎

        参数：
            config_path: 配置文件路径

        返回：
            配置好的规则引擎
        """
        engine = RuleEngine()
        engine.load_rules(config_path)
        return engine

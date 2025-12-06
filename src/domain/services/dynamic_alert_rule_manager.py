"""动态告警规则管理器

提供动态告警规则的配置和评估：
- 阈值规则（threshold）: 当指标超过阈值时触发
- 模式规则（pattern）: 当匹配特定模式时触发（如连续失败）
- 速率规则（rate）: 当变化速率超过阈值时触发

用法：
    manager = DynamicAlertRuleManager()

    # 创建规则
    rule_id = manager.create_rule(
        name="高拒绝率告警",
        rule_type="threshold",
        metric="rejection_rate",
        threshold=0.5,
        comparison=">=",
        severity="warning",
    )

    # 评估规则
    alerts = manager.evaluate({"rejection_rate": 0.6})

    # 管理规则
    manager.disable_rule(rule_id)
    manager.delete_rule(rule_id)

    # 查看告警历史
    history = manager.get_alert_history()
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AlertRule:
    """告警规则"""

    id: str
    name: str
    rule_type: str  # threshold, pattern, rate
    severity: str  # info, warning, critical
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "id": self.id,
            "name": self.name,
            "rule_type": self.rule_type,
            "severity": self.severity,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        result.update(self.config)
        return result


@dataclass
class Alert:
    """告警实例"""

    rule_id: str
    rule_name: str
    severity: str
    message: str
    metric_value: Any
    triggered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "message": self.message,
            "metric_value": self.metric_value,
            "triggered_at": self.triggered_at.isoformat(),
        }


class DynamicAlertRuleManager:
    """动态告警规则管理器

    支持动态创建、更新、删除告警规则，并评估指标触发告警。
    """

    # 比较运算符映射
    COMPARISONS: dict[str, Callable[[Any, Any], bool]] = {
        ">": lambda x, y: x > y,
        ">=": lambda x, y: x >= y,
        "<": lambda x, y: x < y,
        "<=": lambda x, y: x <= y,
        "==": lambda x, y: x == y,
        "!=": lambda x, y: x != y,
    }

    def __init__(self) -> None:
        """初始化告警规则管理器"""
        self.rules: dict[str, AlertRule] = {}
        self.alert_history: list[Alert] = []

    def create_rule(
        self,
        name: str,
        rule_type: str,
        severity: str = "warning",
        **kwargs: Any,
    ) -> str:
        """创建告警规则

        参数：
            name: 规则名称
            rule_type: 规则类型 (threshold/pattern/rate)
            severity: 严重性 (info/warning/critical)
            **kwargs: 规则配置（取决于规则类型）

        返回：
            规则 ID
        """
        rule_id = f"alert_rule_{uuid.uuid4().hex[:12]}"

        rule = AlertRule(
            id=rule_id,
            name=name,
            rule_type=rule_type,
            severity=severity,
            config=kwargs,
        )

        self.rules[rule_id] = rule
        return rule_id

    def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        """获取规则

        参数：
            rule_id: 规则 ID

        返回：
            规则字典，如果不存在返回 None
        """
        rule = self.rules.get(rule_id)
        if rule is None:
            return None
        return rule.to_dict()

    def list_rules(self) -> list[dict[str, Any]]:
        """列出所有规则

        返回：
            所有规则的列表
        """
        return [rule.to_dict() for rule in self.rules.values()]

    def update_rule(self, rule_id: str, **kwargs: Any) -> bool:
        """更新规则

        参数：
            rule_id: 规则 ID
            **kwargs: 要更新的字段

        返回：
            是否更新成功
        """
        rule = self.rules.get(rule_id)
        if rule is None:
            return False

        # 更新可更新的字段
        if "name" in kwargs:
            rule.name = kwargs.pop("name")
        if "severity" in kwargs:
            rule.severity = kwargs.pop("severity")
        if "enabled" in kwargs:
            rule.enabled = kwargs.pop("enabled")

        # 其余的更新到配置中
        rule.config.update(kwargs)
        rule.updated_at = datetime.now()

        return True

    def delete_rule(self, rule_id: str) -> bool:
        """删除规则

        参数：
            rule_id: 规则 ID

        返回：
            是否删除成功
        """
        if rule_id not in self.rules:
            return False

        del self.rules[rule_id]
        return True

    def enable_rule(self, rule_id: str) -> bool:
        """启用规则

        参数：
            rule_id: 规则 ID

        返回：
            是否成功
        """
        rule = self.rules.get(rule_id)
        if rule is None:
            return False

        rule.enabled = True
        rule.updated_at = datetime.now()
        return True

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则

        参数：
            rule_id: 规则 ID

        返回：
            是否成功
        """
        rule = self.rules.get(rule_id)
        if rule is None:
            return False

        rule.enabled = False
        rule.updated_at = datetime.now()
        return True

    def evaluate(self, metrics: dict[str, Any]) -> list[dict[str, Any]]:
        """评估所有规则

        参数：
            metrics: 指标字典 {指标名: 值}

        返回：
            触发的告警列表
        """
        alerts = []

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            alert = self._evaluate_rule(rule, metrics)
            if alert is not None:
                alerts.append(alert.to_dict())
                self.alert_history.append(alert)

        return alerts

    def _evaluate_rule(self, rule: AlertRule, metrics: dict[str, Any]) -> Alert | None:
        """评估单个规则

        参数：
            rule: 告警规则
            metrics: 指标字典

        返回：
            如果触发返回 Alert，否则返回 None
        """
        if rule.rule_type == "threshold":
            return self._evaluate_threshold_rule(rule, metrics)
        elif rule.rule_type == "pattern":
            return self._evaluate_pattern_rule(rule, metrics)
        elif rule.rule_type == "rate":
            return self._evaluate_rate_rule(rule, metrics)

        return None

    def _evaluate_threshold_rule(self, rule: AlertRule, metrics: dict[str, Any]) -> Alert | None:
        """评估阈值规则"""
        metric_name = rule.config.get("metric")
        threshold = rule.config.get("threshold")
        comparison = rule.config.get("comparison", ">=")

        if metric_name not in metrics:
            return None

        metric_value = metrics[metric_name]
        compare_fn = self.COMPARISONS.get(comparison, lambda x, y: x >= y)

        if compare_fn(metric_value, threshold):
            return Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"{metric_name} ({metric_value}) {comparison} {threshold}",
                metric_value=metric_value,
            )

        return None

    def _evaluate_pattern_rule(self, rule: AlertRule, metrics: dict[str, Any]) -> Alert | None:
        """评估模式规则"""
        pattern = rule.config.get("pattern")
        count = rule.config.get("count", 1)

        if pattern == "consecutive_failures":
            if metrics.get("consecutive_failures", 0) >= count:
                return Alert(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=f"连续失败次数达到 {count}",
                    metric_value=metrics.get("consecutive_failures"),
                )

        return None

    def _evaluate_rate_rule(self, rule: AlertRule, metrics: dict[str, Any]) -> Alert | None:
        """评估速率规则"""
        metric_name = rule.config.get("metric")
        rate_threshold = rule.config.get("rate_threshold")

        rate_metric_name = f"{metric_name}_rate"
        if rate_metric_name in metrics:
            rate_value = metrics[rate_metric_name]
            if rate_value >= rate_threshold:
                return Alert(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=f"{metric_name} 速率 ({rate_value}/min) >= {rate_threshold}/min",
                    metric_value=rate_value,
                )

        return None

    def get_alert_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """获取告警历史

        参数：
            limit: 返回数量限制（可选）

        返回：
            告警历史列表
        """
        if limit is not None:
            return [alert.to_dict() for alert in self.alert_history[-limit:]]
        return [alert.to_dict() for alert in self.alert_history]

    def get_alerts_by_severity(self, severity: str) -> list[dict[str, Any]]:
        """按严重性获取告警历史

        参数：
            severity: 严重性级别

        返回：
            匹配的告警列表
        """
        return [alert.to_dict() for alert in self.alert_history if alert.severity == severity]

    def clear_alert_history(self) -> None:
        """清空告警历史"""
        self.alert_history.clear()

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息

        返回：
            统计信息字典
        """
        severity_counts: dict[str, int] = {}
        for alert in self.alert_history:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

        return {
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules.values() if r.enabled),
            "total_alerts": len(self.alert_history),
            "alerts_by_severity": severity_counts,
        }

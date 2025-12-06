"""监督模块

提供对话和工作流的监督能力：

1. ConversationSupervisionModule - 对话提示监控
   - 偏见检测（性别、种族等）
   - 有害内容检测（暴力、非法活动、自伤）
   - 稳定性检测（提示注入、越狱、上下文溢出）

2. WorkflowEfficiencyMonitor - 工作流效率监控
   - 资源监控（内存、CPU）
   - 延迟监控
   - 阈值告警

3. StrategyRepository - 策略库
   - 策略注册和管理
   - 策略匹配和执行

4. 事件定义
   - InterventionEvent: 干预事件
   - ContextInjectionEvent: 上下文注入事件
   - TaskTerminationEvent: 任务终止事件

用法：
    # 对话监督
    supervision = ConversationSupervisionModule()
    result = supervision.check_all("用户输入")
    if not result.passed:
        for issue in result.issues:
            print(f"检测到问题: {issue}")

    # 效率监控
    monitor = WorkflowEfficiencyMonitor()
    monitor.record_resource_usage(workflow_id, node_id, memory_mb, cpu_percent, duration)
    alerts = monitor.check_thresholds(workflow_id)

    # 策略管理
    repo = StrategyRepository()
    repo.register(name="策略", trigger_conditions=["bias"], action="warn")
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.services.event_bus import Event

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


# ==================== 事件定义 ====================


@dataclass
class InterventionEvent(Event):
    """干预事件

    当监督模块检测到问题并采取干预措施时发布。

    属性：
        intervention_type: 干预类型 (warn/block/terminate)
        reason: 干预原因
        source: 干预来源模块
        target_id: 目标ID（消息/任务/工作流）
        severity: 严重性 (low/medium/high/critical)
        details: 详细信息
    """

    intervention_type: str = ""
    reason: str = ""
    source: str = ""
    target_id: str = ""
    severity: str = "medium"
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return "intervention"


@dataclass
class ContextInjectionEvent(Event):
    """上下文注入事件

    当需要向目标 Agent 注入额外上下文时发布。

    属性：
        target_agent: 目标Agent
        context_data: 注入的上下文数据
        injection_type: 注入类型 (pre_response/post_detection)
    """

    target_agent: str = ""
    context_data: dict[str, Any] = field(default_factory=dict)
    injection_type: str = "pre_response"

    @property
    def event_type(self) -> str:
        return "context_injection"


@dataclass
class TaskTerminationEvent(Event):
    """任务终止事件

    当任务被监督模块强制终止时发布。

    属性：
        task_id: 任务ID
        workflow_id: 工作流ID
        reason: 终止原因
        initiated_by: 发起终止的模块
        termination_type: 终止类型 (graceful/immediate)
    """

    task_id: str = ""
    workflow_id: str = ""
    reason: str = ""
    initiated_by: str = ""
    termination_type: str = "graceful"

    @property
    def event_type(self) -> str:
        return "task_termination"


# ==================== 对话监督模块 ====================


class ConversationSupervisionModule:
    """对话提示监控模块

    检测对话中的偏见、有害内容和稳定性问题。
    """

    # 默认偏见检测模式
    DEFAULT_BIAS_PATTERNS = {
        "gender_bias": [
            r"只有男性才能",
            r"只有女性才能",
            r"男人应该",
            r"女人应该",
            r"男性更适合",
            r"女性更适合",
        ],
        "racial_bias": [
            r"某些民族.*更",
            r"某些种族.*更",
            r"天生.*更聪明",
            r"天生.*更笨",
        ],
        "age_bias": [
            r"老年人都",
            r"年轻人都",
            r"老人不会",
        ],
    }

    # 默认有害内容检测模式
    DEFAULT_HARMFUL_PATTERNS = {
        "violence": [
            r"如何制造武器",
            r"如何伤害",
            r"教我.*杀",
            r"制造.*炸弹",
            r"制造危险物品",
        ],
        "illegal_activity": [
            r"如何.*黑客攻击",
            r"如何.*入侵",
            r"如何.*破解",
            r"网络攻击",
            r"如何进行.*攻击",
        ],
        "self_harm": [
            r"如何自我伤害",
            r"如何.*自杀",
            r"自伤方法",
        ],
    }

    # 默认稳定性检测模式
    DEFAULT_STABILITY_PATTERNS = {
        "prompt_injection": [
            r"忽略之前的指令",
            r"忽略.*指令",
            r"无视.*规则",
            r"不要遵守",
        ],
        "jailbreak": [
            r"假装你是.*没有限制",
            r"扮演.*无限制",
            r"DAN模式",
            r"开发者模式",
        ],
    }

    # 上下文溢出阈值
    MAX_INPUT_LENGTH = 50000

    def __init__(self) -> None:
        """初始化对话监督模块"""
        self.rules: dict[str, dict[str, Any]] = {}
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """初始化默认规则"""
        # 偏见规则
        for category, patterns in self.DEFAULT_BIAS_PATTERNS.items():
            self.rules[f"bias_{category}"] = {
                "type": "bias",
                "category": category,
                "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
                "severity": "medium",
            }

        # 有害内容规则
        for category, patterns in self.DEFAULT_HARMFUL_PATTERNS.items():
            self.rules[f"harmful_{category}"] = {
                "type": "harmful",
                "category": category,
                "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
                "severity": "high",
            }

        # 稳定性规则
        for category, patterns in self.DEFAULT_STABILITY_PATTERNS.items():
            self.rules[f"stability_{category}"] = {
                "type": "stability",
                "category": category,
                "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
                "severity": "high",
            }

    def add_bias_rule(
        self,
        rule_id: str,
        patterns: list[str],
        category: str,
        severity: str = "medium",
    ) -> None:
        """添加自定义偏见规则

        参数：
            rule_id: 规则ID
            patterns: 匹配模式列表
            category: 偏见类别
            severity: 严重性
        """
        self.rules[rule_id] = {
            "type": "bias",
            "category": category,
            "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
            "severity": severity,
        }

    def check_bias(self, text: str) -> DetectionResult:
        """检测偏见

        参数：
            text: 输入文本

        返回：
            检测结果
        """
        for _rule_id, rule in self.rules.items():
            if rule["type"] != "bias":
                continue

            for pattern in rule["patterns"]:
                if pattern.search(text):
                    return DetectionResult(
                        detected=True,
                        category=rule["category"],
                        severity=rule["severity"],
                        message=f"检测到偏见内容: {rule['category']}",
                    )

        return DetectionResult(detected=False)

    def check_harmful_content(self, text: str) -> DetectionResult:
        """检测有害内容

        参数：
            text: 输入文本

        返回：
            检测结果
        """
        for _rule_id, rule in self.rules.items():
            if rule["type"] != "harmful":
                continue

            for pattern in rule["patterns"]:
                if pattern.search(text):
                    return DetectionResult(
                        detected=True,
                        category=rule["category"],
                        severity=rule["severity"],
                        message=f"检测到有害内容: {rule['category']}",
                    )

        return DetectionResult(detected=False)

    def check_stability(self, text: str) -> DetectionResult:
        """检测稳定性问题

        参数：
            text: 输入文本

        返回：
            检测结果
        """
        # 检查上下文溢出
        if len(text) > self.MAX_INPUT_LENGTH:
            return DetectionResult(
                detected=True,
                category="context_overflow",
                severity="high",
                message=f"输入长度 ({len(text)}) 超过限制 ({self.MAX_INPUT_LENGTH})",
            )

        # 检查其他稳定性问题
        for _rule_id, rule in self.rules.items():
            if rule["type"] != "stability":
                continue

            for pattern in rule["patterns"]:
                if pattern.search(text):
                    return DetectionResult(
                        detected=True,
                        category=rule["category"],
                        severity=rule["severity"],
                        message=f"检测到稳定性问题: {rule['category']}",
                    )

        return DetectionResult(detected=False)

    def check_all(self, text: str) -> ComprehensiveCheckResult:
        """综合检查

        参数：
            text: 输入文本

        返回：
            综合检查结果
        """
        result = ComprehensiveCheckResult()

        # 检查偏见
        bias_result = self.check_bias(text)
        if bias_result.detected:
            result.add_issue(bias_result)

        # 检查有害内容
        harmful_result = self.check_harmful_content(text)
        if harmful_result.detected:
            result.add_issue(harmful_result)
            result.action = "block"  # 有害内容直接阻止

        # 检查稳定性
        stability_result = self.check_stability(text)
        if stability_result.detected:
            result.add_issue(stability_result)
            if stability_result.category in ["prompt_injection", "jailbreak"]:
                result.action = "block"

        return result

    def create_injection_context(
        self,
        issue_type: str,
        severity: str,
        message: str,
        action: str = "warn",
    ) -> dict[str, Any]:
        """创建注入上下文

        参数：
            issue_type: 问题类型
            severity: 严重性
            message: 消息
            action: 动作

        返回：
            上下文字典
        """
        return {
            "warning": message,
            "issue_type": issue_type,
            "severity": severity,
            "action": action,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }


# ==================== 工作流效率监控 ====================


class WorkflowEfficiencyMonitor:
    """工作流效率监控

    监控工作流的资源使用和延迟。
    """

    DEFAULT_THRESHOLDS = {
        "max_duration_seconds": 300.0,  # 5 分钟
        "max_node_duration_seconds": 60.0,  # 1 分钟
        "max_memory_mb": 2048,  # 2 GB
        "max_cpu_percent": 90.0,
    }

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        """初始化效率监控器

        参数：
            thresholds: 自定义阈值
        """
        self.thresholds = {**self.DEFAULT_THRESHOLDS}
        if thresholds:
            self.thresholds.update(thresholds)

        self.workflow_usage: dict[str, dict[str, Any]] = {}
        self.latency_records: dict[str, dict[str, float]] = {}

    def record_resource_usage(
        self,
        workflow_id: str,
        node_id: str,
        memory_mb: float,
        cpu_percent: float,
        duration_seconds: float,
    ) -> None:
        """记录资源使用

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            memory_mb: 内存使用 (MB)
            cpu_percent: CPU 使用率 (%)
            duration_seconds: 执行时长 (秒)
        """
        if workflow_id not in self.workflow_usage:
            self.workflow_usage[workflow_id] = {
                "nodes": {},
                "total_duration": 0.0,
                "max_memory": 0.0,
                "max_cpu": 0.0,
            }

        usage = self.workflow_usage[workflow_id]

        usage["nodes"][node_id] = {
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
            "duration_seconds": duration_seconds,
            "recorded_at": datetime.now().isoformat(),
        }

        usage["total_duration"] += duration_seconds
        usage["max_memory"] = max(usage["max_memory"], memory_mb)
        usage["max_cpu"] = max(usage["max_cpu"], cpu_percent)

    def record_latency(
        self,
        workflow_id: str,
        node_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """记录节点延迟

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            start_time: 开始时间
            end_time: 结束时间
        """
        if workflow_id not in self.latency_records:
            self.latency_records[workflow_id] = {}

        latency = (end_time - start_time).total_seconds()
        self.latency_records[workflow_id][node_id] = latency

    def get_workflow_usage(self, workflow_id: str) -> dict[str, Any] | None:
        """获取工作流资源使用情况

        参数：
            workflow_id: 工作流ID

        返回：
            资源使用情况
        """
        return self.workflow_usage.get(workflow_id)

    def get_node_latency(self, workflow_id: str, node_id: str) -> float | None:
        """获取节点延迟

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID

        返回：
            延迟（秒）
        """
        if workflow_id not in self.latency_records:
            return None
        return self.latency_records[workflow_id].get(node_id)

    def get_workflow_total_duration(self, workflow_id: str) -> float:
        """获取工作流总时长

        参数：
            workflow_id: 工作流ID

        返回：
            总时长（秒）
        """
        usage = self.workflow_usage.get(workflow_id)
        if not usage:
            return 0.0
        return usage["total_duration"]

    def check_thresholds(self, workflow_id: str) -> list[dict[str, Any]]:
        """检查阈值并生成告警

        参数：
            workflow_id: 工作流ID

        返回：
            告警列表
        """
        alerts = []
        usage = self.workflow_usage.get(workflow_id)

        if not usage:
            return alerts

        # 检查总时长
        if usage["total_duration"] > self.thresholds["max_duration_seconds"]:
            alerts.append(
                {
                    "type": "slow_execution",
                    "severity": "warning",
                    "message": f"工作流总时长 ({usage['total_duration']:.1f}s) 超过阈值 ({self.thresholds['max_duration_seconds']}s)",
                    "value": usage["total_duration"],
                    "threshold": self.thresholds["max_duration_seconds"],
                }
            )

        # 检查内存
        if usage["max_memory"] > self.thresholds["max_memory_mb"]:
            alerts.append(
                {
                    "type": "memory_overuse",
                    "severity": "warning",
                    "message": f"内存使用 ({usage['max_memory']:.0f}MB) 超过阈值 ({self.thresholds['max_memory_mb']}MB)",
                    "value": usage["max_memory"],
                    "threshold": self.thresholds["max_memory_mb"],
                }
            )

        # 检查 CPU
        if usage["max_cpu"] > self.thresholds["max_cpu_percent"]:
            alerts.append(
                {
                    "type": "cpu_overuse",
                    "severity": "warning",
                    "message": f"CPU 使用率 ({usage['max_cpu']:.1f}%) 超过阈值 ({self.thresholds['max_cpu_percent']}%)",
                    "value": usage["max_cpu"],
                    "threshold": self.thresholds["max_cpu_percent"],
                }
            )

        # 检查单个节点时长
        for node_id, node_usage in usage["nodes"].items():
            if node_usage["duration_seconds"] > self.thresholds["max_node_duration_seconds"]:
                alerts.append(
                    {
                        "type": "slow_execution",
                        "severity": "warning",
                        "message": f"节点 {node_id} 执行时长 ({node_usage['duration_seconds']:.1f}s) 超过阈值",
                        "node_id": node_id,
                        "value": node_usage["duration_seconds"],
                        "threshold": self.thresholds["max_node_duration_seconds"],
                    }
                )

        return alerts


# ==================== 策略库 ====================


class StrategyRepository:
    """策略库

    管理监督策略的注册、查询和执行。
    """

    def __init__(self) -> None:
        """初始化策略库"""
        self.strategies: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        trigger_conditions: list[str],
        action: str,
        priority: int = 10,
        action_params: dict[str, Any] | None = None,
    ) -> str:
        """注册策略

        参数：
            name: 策略名称
            trigger_conditions: 触发条件列表
            action: 动作 (warn/block/terminate/log)
            priority: 优先级（数字越小优先级越高）
            action_params: 动作参数

        返回：
            策略ID
        """
        strategy_id = f"strategy_{uuid.uuid4().hex[:12]}"

        self.strategies[strategy_id] = {
            "id": strategy_id,
            "name": name,
            "trigger_conditions": trigger_conditions,
            "action": action,
            "priority": priority,
            "action_params": action_params or {},
            "enabled": True,
            "created_at": datetime.now().isoformat(),
        }

        return strategy_id

    def get(self, strategy_id: str) -> dict[str, Any] | None:
        """获取策略

        参数：
            strategy_id: 策略ID

        返回：
            策略字典
        """
        return self.strategies.get(strategy_id)

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有策略

        返回：
            策略列表
        """
        return list(self.strategies.values())

    def find_by_condition(self, condition: str) -> list[dict[str, Any]]:
        """按条件查找策略

        参数：
            condition: 触发条件

        返回：
            匹配的策略列表（按优先级排序）
        """
        matches = []

        for strategy in self.strategies.values():
            if not strategy["enabled"]:
                continue
            if condition in strategy["trigger_conditions"]:
                matches.append(strategy)

        # 按优先级排序
        matches.sort(key=lambda s: s["priority"])

        return matches

    def delete(self, strategy_id: str) -> bool:
        """删除策略

        参数：
            strategy_id: 策略ID

        返回：
            是否成功
        """
        if strategy_id not in self.strategies:
            return False
        del self.strategies[strategy_id]
        return True


# ==================== 监督协调器 ====================


class SupervisionCoordinator:
    """监督协调器

    协调对话监督和效率监控，管理终止流程。
    """

    def __init__(self) -> None:
        """初始化监督协调器"""
        self.conversation_supervision = ConversationSupervisionModule()
        self.efficiency_monitor = WorkflowEfficiencyMonitor()
        self.strategy_repository = StrategyRepository()

        self.intervention_events: list[InterventionEvent] = []
        self.termination_events: list[TaskTerminationEvent] = []

    def initiate_termination(
        self,
        task_id: str,
        reason: str,
        severity: str,
        graceful: bool = True,
        workflow_id: str = "",
    ) -> TerminationResult:
        """发起任务终止

        参数：
            task_id: 任务ID
            reason: 终止原因
            severity: 严重性
            graceful: 是否优雅终止
            workflow_id: 工作流ID

        返回：
            终止结果
        """
        termination_type = "graceful" if graceful else "immediate"

        # 创建终止事件
        event = TaskTerminationEvent(
            task_id=task_id,
            workflow_id=workflow_id,
            reason=reason,
            initiated_by="supervision_coordinator",
            termination_type=termination_type,
        )

        self.termination_events.append(event)

        return TerminationResult(
            success=True,
            task_id=task_id,
            termination_type=termination_type,
            message=f"任务 {task_id} 已{termination_type}终止: {reason}",
        )

    def get_termination_events(self) -> list[TaskTerminationEvent]:
        """获取终止事件列表

        返回：
            终止事件列表
        """
        return self.termination_events

    def record_intervention(
        self,
        intervention_type: str,
        reason: str,
        source: str,
        target_id: str,
        severity: str = "medium",
    ) -> InterventionEvent:
        """记录干预事件

        参数：
            intervention_type: 干预类型
            reason: 原因
            source: 来源
            target_id: 目标ID
            severity: 严重性

        返回：
            干预事件
        """
        event = InterventionEvent(
            intervention_type=intervention_type,
            reason=reason,
            source=source,
            target_id=target_id,
            severity=severity,
        )

        self.intervention_events.append(event)
        return event

    def get_intervention_events(self) -> list[InterventionEvent]:
        """获取干预事件列表

        返回：
            干预事件列表
        """
        return self.intervention_events


# 导出
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

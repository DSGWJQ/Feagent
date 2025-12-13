"""监督策略实现

提供增强的监督能力：

1. PromptScanner - 提示扫描器
   - 基于策略的扫描（正则、关键词、组合）
   - 提示净化（Sanitization）

2. EnhancedResourceMonitor - 增强资源监控
   - API 延迟监控
   - 实时监控
   - 组合阈值检测

3. InterventionManager - 干预管理器
   - 上下文注入
   - 任务终止
   - REPLAN 触发

4. InterventionExecutor - 干预执行器
   - 执行策略动作
   - 日志记录

5. SupervisionIntegration - 监督集成
   - 对话监督
   - 工作流监督
   - 端到端流程
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.services.event_bus import Event
from src.domain.services.supervision import (
    ContextInjectionEvent,
    TaskTerminationEvent,
    TerminationResult,
    WorkflowEfficiencyMonitor,
)

# ==================== 数据类定义 ====================


@dataclass
class PolicyViolation:
    """策略违规"""

    policy_id: str
    policy_name: str
    severity: str = "medium"  # low, medium, high, critical
    action: str = "warn"  # warn, block, terminate
    message: str = ""
    matched_content: str = ""
    category: str = ""  # 策略类别，用于匹配
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """扫描结果"""

    passed: bool = True
    violations: list[PolicyViolation] = field(default_factory=list)
    recommended_action: str = "allow"  # allow, warn, block, terminate
    scan_time_ms: float = 0.0

    def add_violation(self, violation: PolicyViolation) -> None:
        """添加违规"""
        self.violations.append(violation)
        self.passed = False
        # 更新推荐动作（取最严格的）
        action_priority = {"allow": 0, "warn": 1, "block": 2, "terminate": 3}
        if action_priority.get(violation.action, 0) > action_priority.get(
            self.recommended_action, 0
        ):
            self.recommended_action = violation.action


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool = True
    action_taken: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplanEvent(Event):
    """REPLAN 请求事件"""

    workflow_id: str = ""
    reason: str = ""
    target_agent: str = "conversation_agent"
    payload: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return "replan_requested"


@dataclass
class WorkflowTerminationResult:
    """工作流终止结果"""

    success: bool = True
    workflow_id: str = ""
    termination_type: str = "graceful"
    message: str = ""


# ==================== 提示扫描器 ====================


class PromptScanner:
    """提示扫描器

    基于策略的提示扫描，支持多种策略类型。
    """

    # 默认策略
    DEFAULT_POLICIES = {
        "injection_detect": {
            "name": "提示注入检测",
            "category": "prompt_injection",  # 用于策略匹配
            "type": "regex",
            "patterns": [
                r"忽略.*指令",
                r"忽略.*规则",
                r"无视.*规则",
                r"不要遵守",
                r"ignore.*instructions",
                r"disregard.*rules",
            ],
            "action": "block",
            "severity": "high",
            "enabled": True,
        },
        "jailbreak_detect": {
            "name": "越狱检测",
            "category": "jailbreak",
            "type": "regex",
            "patterns": [
                r"假装你是.*没有限制",
                r"扮演.*无限制",
                r"DAN模式",
                r"开发者模式",
                r"pretend.*no.*restrictions",
            ],
            "action": "block",
            "severity": "high",
            "enabled": True,
        },
        "harmful_content": {
            "name": "有害内容检测",
            "category": "harmful",
            "type": "keyword",
            "keywords": [
                "制造炸弹",
                "制造武器",
                "制造危险物品",
                "如何杀人",
                "如何伤害",
            ],
            "action": "terminate",
            "severity": "critical",
            "enabled": True,
        },
    }

    def __init__(self) -> None:
        """初始化扫描器"""
        self.policies: dict[str, dict[str, Any]] = {}
        self._init_default_policies()

    def _init_default_policies(self) -> None:
        """初始化默认策略"""
        for policy_id, policy in self.DEFAULT_POLICIES.items():
            self.policies[policy_id] = {
                **policy,
                "id": policy_id,
                "created_at": datetime.now().isoformat(),
            }
            # 编译正则表达式
            if policy["type"] == "regex":
                self.policies[policy_id]["compiled_patterns"] = [
                    re.compile(p, re.IGNORECASE) for p in policy["patterns"]
                ]

    def add_policy(
        self,
        name: str,
        policy_type: str,
        action: str = "warn",
        severity: str = "medium",
        pattern: str | None = None,
        patterns: list[str] | None = None,
        keywords: list[str] | None = None,
        conditions: list[dict[str, Any]] | None = None,
        logic: str = "or",
        **kwargs: Any,
    ) -> str:
        """添加策略

        参数：
            name: 策略名称
            policy_type: 策略类型 (regex/keyword/composite)
            action: 动作 (warn/block/terminate)
            severity: 严重性
            pattern: 单个正则模式
            patterns: 正则模式列表
            keywords: 关键词列表
            conditions: 组合条件
            logic: 组合逻辑 (or/and)

        返回：
            策略ID
        """
        policy_id = f"policy_{uuid.uuid4().hex[:12]}"

        policy = {
            "id": policy_id,
            "name": name,
            "type": policy_type,
            "action": action,
            "severity": severity,
            "enabled": True,
            "created_at": datetime.now().isoformat(),
        }

        if policy_type == "regex":
            all_patterns = patterns or []
            if pattern:
                all_patterns.append(pattern)
            policy["patterns"] = all_patterns
            policy["compiled_patterns"] = [re.compile(p, re.IGNORECASE) for p in all_patterns]

        elif policy_type == "keyword":
            policy["keywords"] = keywords or []

        elif policy_type == "composite":
            policy["conditions"] = conditions or []
            policy["logic"] = logic

        self.policies[policy_id] = policy
        return policy_id

    def enable_policy(self, policy_id: str) -> bool:
        """启用策略"""
        if policy_id not in self.policies:
            return False
        self.policies[policy_id]["enabled"] = True
        return True

    def disable_policy(self, policy_id: str) -> bool:
        """禁用策略"""
        if policy_id not in self.policies:
            return False
        self.policies[policy_id]["enabled"] = False
        return True

    def scan(self, text: str) -> ScanResult:
        """扫描文本

        参数：
            text: 输入文本

        返回：
            扫描结果
        """
        start_time = datetime.now()
        result = ScanResult()

        for _policy_id, policy in self.policies.items():
            if not policy.get("enabled", True):
                continue

            violation = self._check_policy(text, policy)
            if violation:
                result.add_violation(violation)

        result.scan_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        return result

    def _check_policy(self, text: str, policy: dict[str, Any]) -> PolicyViolation | None:
        """检查单个策略

        参数：
            text: 输入文本
            policy: 策略配置

        返回：
            违规对象或 None
        """
        policy_type = policy.get("type", "")

        if policy_type == "regex":
            return self._check_regex_policy(text, policy)
        elif policy_type == "keyword":
            return self._check_keyword_policy(text, policy)
        elif policy_type == "composite":
            return self._check_composite_policy(text, policy)

        return None

    def _check_regex_policy(self, text: str, policy: dict[str, Any]) -> PolicyViolation | None:
        """检查正则策略"""
        compiled = policy.get("compiled_patterns", [])

        for pattern in compiled:
            match = pattern.search(text)
            if match:
                return PolicyViolation(
                    policy_id=policy["id"],
                    policy_name=policy["name"],
                    severity=policy.get("severity", "medium"),
                    action=policy.get("action", "warn"),
                    message=f"匹配策略: {policy['name']}",
                    matched_content=match.group(),
                    category=policy.get("category", policy["id"]),
                )

        return None

    def _check_keyword_policy(self, text: str, policy: dict[str, Any]) -> PolicyViolation | None:
        """检查关键词策略"""
        keywords = policy.get("keywords", [])
        text_lower = text.lower()

        for keyword in keywords:
            if keyword.lower() in text_lower:
                return PolicyViolation(
                    policy_id=policy["id"],
                    policy_name=policy["name"],
                    severity=policy.get("severity", "medium"),
                    action=policy.get("action", "warn"),
                    message=f"匹配关键词: {keyword}",
                    matched_content=keyword,
                    category=policy.get("category", policy["id"]),
                )

        return None

    def _check_composite_policy(self, text: str, policy: dict[str, Any]) -> PolicyViolation | None:
        """检查组合策略"""
        conditions = policy.get("conditions", [])
        logic = policy.get("logic", "or")

        matches = []
        for cond in conditions:
            cond_type = cond.get("type", "")
            matched = False

            if cond_type == "keyword":
                keywords = cond.get("keywords", [])
                text_lower = text.lower()
                for kw in keywords:
                    if kw.lower() in text_lower:
                        matched = True
                        break

            elif cond_type == "regex":
                pattern = cond.get("pattern", "")
                if pattern and re.search(pattern, text, re.IGNORECASE):
                    matched = True

            matches.append(matched)

        # 根据逻辑判断
        if logic == "or" and any(matches):
            return PolicyViolation(
                policy_id=policy["id"],
                policy_name=policy["name"],
                severity=policy.get("severity", "medium"),
                action=policy.get("action", "warn"),
                message=f"匹配组合策略: {policy['name']}",
                category=policy.get("category", policy["id"]),
            )
        elif logic == "and" and all(matches) and matches:
            return PolicyViolation(
                policy_id=policy["id"],
                policy_name=policy["name"],
                severity=policy.get("severity", "medium"),
                action=policy.get("action", "warn"),
                message=f"匹配组合策略: {policy['name']}",
                category=policy.get("category", policy["id"]),
            )

        return None

    def sanitize(self, text: str) -> str:
        """净化文本

        移除或替换违规内容。

        参数：
            text: 输入文本

        返回：
            净化后的文本
        """
        sanitized = text

        for _policy_id, policy in self.policies.items():
            if not policy.get("enabled", True):
                continue

            if policy.get("type") == "regex":
                for pattern in policy.get("compiled_patterns", []):
                    sanitized = pattern.sub("[已过滤]", sanitized)

            elif policy.get("type") == "keyword":
                for keyword in policy.get("keywords", []):
                    sanitized = re.sub(
                        re.escape(keyword), "[已过滤]", sanitized, flags=re.IGNORECASE
                    )

        return sanitized

    def sanitize_with_log(self, text: str) -> dict[str, Any]:
        """带日志的净化

        参数：
            text: 输入文本

        返回：
            包含净化结果和变更记录的字典
        """
        original = text
        changes = []

        for policy_id, policy in self.policies.items():
            if not policy.get("enabled", True):
                continue

            if policy.get("type") == "regex":
                for pattern in policy.get("compiled_patterns", []):
                    matches = pattern.findall(text)
                    if matches:
                        for match in matches:
                            changes.append(
                                {
                                    "policy_id": policy_id,
                                    "policy_name": policy["name"],
                                    "matched": match,
                                    "action": "replaced",
                                }
                            )
                        text = pattern.sub("[已过滤]", text)

            elif policy.get("type") == "keyword":
                for keyword in policy.get("keywords", []):
                    if keyword.lower() in text.lower():
                        changes.append(
                            {
                                "policy_id": policy_id,
                                "policy_name": policy["name"],
                                "matched": keyword,
                                "action": "replaced",
                            }
                        )
                        text = re.sub(re.escape(keyword), "[已过滤]", text, flags=re.IGNORECASE)

        return {
            "original": original,
            "sanitized": text,
            "changes": changes,
            "modified": original != text,
        }


# ==================== 增强资源监控器 ====================


class EnhancedResourceMonitor(WorkflowEfficiencyMonitor):
    """增强资源监控器

    扩展基础监控器，添加 API 延迟监控和实时监控能力。
    """

    ENHANCED_THRESHOLDS = {
        "max_api_latency_ms": 3000,  # 3 秒
        "max_avg_api_latency_ms": 1000,  # 1 秒平均
        "critical_memory_mb": 8192,  # 8 GB
        "critical_cpu_percent": 95.0,
    }

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        """初始化增强监控器"""
        super().__init__(thresholds)
        self.thresholds.update(self.ENHANCED_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

        self.api_latency_records: dict[str, dict[str, list[float]]] = {}
        self.monitoring_sessions: dict[str, dict[str, Any]] = {}

    def set_threshold(self, key: str, value: float) -> None:
        """设置阈值"""
        self.thresholds[key] = value

    def record_api_latency(
        self,
        workflow_id: str,
        node_id: str,
        api_name: str,
        latency_ms: float,
    ) -> None:
        """记录 API 延迟

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            api_name: API 名称
            latency_ms: 延迟（毫秒）
        """
        if workflow_id not in self.api_latency_records:
            self.api_latency_records[workflow_id] = {}

        key = f"{node_id}:{api_name}"
        if key not in self.api_latency_records[workflow_id]:
            self.api_latency_records[workflow_id][key] = []

        self.api_latency_records[workflow_id][key].append(latency_ms)

    def get_api_latency(self, workflow_id: str, node_id: str, api_name: str) -> float | None:
        """获取最新 API 延迟"""
        if workflow_id not in self.api_latency_records:
            return None

        key = f"{node_id}:{api_name}"
        records = self.api_latency_records[workflow_id].get(key, [])
        return records[-1] if records else None

    def get_api_latency_stats(self, workflow_id: str, api_name: str) -> dict[str, Any]:
        """获取 API 延迟统计

        参数：
            workflow_id: 工作流ID
            api_name: API 名称

        返回：
            统计信息
        """
        if workflow_id not in self.api_latency_records:
            return {"count": 0, "avg": 0, "max": 0, "min": 0}

        all_latencies = []
        for key, latencies in self.api_latency_records[workflow_id].items():
            if api_name in key:
                all_latencies.extend(latencies)

        if not all_latencies:
            return {"count": 0, "avg": 0, "max": 0, "min": 0}

        return {
            "count": len(all_latencies),
            "avg": sum(all_latencies) / len(all_latencies),
            "max": max(all_latencies),
            "min": min(all_latencies),
        }

    def start_monitoring(self, workflow_id: str) -> str:
        """启动实时监控

        参数：
            workflow_id: 工作流ID

        返回：
            监控会话ID
        """
        session_id = f"mon_{uuid.uuid4().hex[:8]}"
        self.monitoring_sessions[workflow_id] = {
            "session_id": session_id,
            "started_at": datetime.now().isoformat(),
            "active": True,
        }
        return session_id

    def stop_monitoring(self, workflow_id: str) -> bool:
        """停止实时监控"""
        if workflow_id not in self.monitoring_sessions:
            return False
        self.monitoring_sessions[workflow_id]["active"] = False
        self.monitoring_sessions[workflow_id]["stopped_at"] = datetime.now().isoformat()
        return True

    def is_monitoring(self, workflow_id: str) -> bool:
        """检查是否正在监控"""
        session = self.monitoring_sessions.get(workflow_id)
        return session is not None and session.get("active", False)

    def get_current_metrics(self, workflow_id: str) -> dict[str, Any]:
        """获取当前指标"""
        usage = self.workflow_usage.get(workflow_id, {})
        return {
            "memory_mb": usage.get("max_memory", 0),
            "cpu_percent": usage.get("max_cpu", 0),
            "duration_seconds": usage.get("total_duration", 0),
            "node_count": len(usage.get("nodes", {})),
        }

    def check_thresholds(self, workflow_id: str) -> list[dict[str, Any]]:
        """检查阈值（扩展版本）"""
        alerts = super().check_thresholds(workflow_id)

        # 检查 API 延迟
        if workflow_id in self.api_latency_records:
            for key, latencies in self.api_latency_records[workflow_id].items():
                for latency in latencies:
                    if latency > self.thresholds.get("max_api_latency_ms", 3000):
                        alerts.append(
                            {
                                "type": "api_latency_exceeded",
                                "severity": "warning",
                                "message": f"API 延迟 ({latency:.0f}ms) 超过阈值",
                                "api_key": key,
                                "value": latency,
                                "threshold": self.thresholds["max_api_latency_ms"],
                            }
                        )

        return alerts


# ==================== 干预管理器 ====================


class InterventionManager:
    """干预管理器

    管理上下文注入、任务终止和 REPLAN 触发。
    """

    def __init__(self) -> None:
        """初始化干预管理器"""
        self.injection_events: list[ContextInjectionEvent] = []
        self.termination_events: list[TaskTerminationEvent] = []
        self.replan_events: list[ReplanEvent] = []
        self.intervention_log: list[dict[str, Any]] = []

    def inject_context(
        self,
        target_agent: str,
        context_type: str,
        message: str,
        severity: str = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> ContextInjectionEvent:
        """注入上下文

        参数：
            target_agent: 目标 Agent
            context_type: 上下文类型 (warning/blocking)
            message: 消息
            severity: 严重性
            metadata: 元数据

        返回：
            上下文注入事件
        """
        context_data = {
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            context_data.update(metadata)

        event = ContextInjectionEvent(
            target_agent=target_agent,
            context_data=context_data,
            injection_type=context_type,
        )

        self.injection_events.append(event)

        # 记录日志
        self._log_intervention(
            intervention_type="context_injection",
            target=target_agent,
            message=message,
            metadata=metadata or {},
        )

        return event

    def terminate_task(
        self,
        task_id: str,
        reason: str,
        graceful: bool = True,
        workflow_id: str = "",
    ) -> TerminationResult:
        """终止任务

        参数：
            task_id: 任务ID
            reason: 原因
            graceful: 是否优雅终止
            workflow_id: 工作流ID

        返回：
            终止结果
        """
        termination_type = "graceful" if graceful else "immediate"

        event = TaskTerminationEvent(
            task_id=task_id,
            workflow_id=workflow_id,
            reason=reason,
            initiated_by="intervention_manager",
            termination_type=termination_type,
        )

        self.termination_events.append(event)

        # 记录日志
        self._log_intervention(
            intervention_type="task_termination",
            target=task_id,
            message=reason,
            metadata={"workflow_id": workflow_id, "type": termination_type},
        )

        return TerminationResult(
            success=True,
            task_id=task_id,
            termination_type=termination_type,
            message=f"任务 {task_id} 已终止: {reason}",
        )

    def terminate_workflow(
        self,
        workflow_id: str,
        reason: str,
        graceful: bool = True,
    ) -> WorkflowTerminationResult:
        """终止工作流

        参数：
            workflow_id: 工作流ID
            reason: 原因
            graceful: 是否优雅终止

        返回：
            终止结果
        """
        termination_type = "graceful" if graceful else "immediate"

        event = TaskTerminationEvent(
            task_id="",
            workflow_id=workflow_id,
            reason=reason,
            initiated_by="intervention_manager",
            termination_type=termination_type,
        )

        self.termination_events.append(event)

        # 记录日志
        self._log_intervention(
            intervention_type="workflow_termination",
            target=workflow_id,
            message=reason,
            metadata={"type": termination_type},
        )

        return WorkflowTerminationResult(
            success=True,
            workflow_id=workflow_id,
            termination_type=termination_type,
            message=f"工作流 {workflow_id} 已终止: {reason}",
        )

    def trigger_replan(
        self,
        workflow_id: str,
        reason: str,
        context: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> ReplanEvent:
        """触发 REPLAN

        参数：
            workflow_id: 工作流ID
            reason: 原因
            context: 上下文
            constraints: 约束

        返回：
            REPLAN 事件
        """
        payload = context or {}
        payload["reason"] = reason
        # 将 constraints 也放入 payload 以便访问
        if constraints:
            payload["constraints"] = constraints

        event = ReplanEvent(
            workflow_id=workflow_id,
            reason=reason,
            target_agent="conversation_agent",
            payload=payload,
            constraints=constraints or {},
        )

        self.replan_events.append(event)

        # 记录日志
        self._log_intervention(
            intervention_type="replan_requested",
            target=workflow_id,
            message=reason,
            metadata={"constraints": constraints or {}},
        )

        return event

    def get_termination_events(self) -> list[TaskTerminationEvent]:
        """获取终止事件列表"""
        return self.termination_events

    def get_replan_events(self) -> list[ReplanEvent]:
        """获取 REPLAN 事件列表"""
        return self.replan_events

    def get_intervention_log(self) -> list[dict[str, Any]]:
        """获取干预日志"""
        return self.intervention_log

    def export_log_json(self) -> str:
        """导出日志为 JSON"""
        return json.dumps(self.intervention_log, ensure_ascii=False, indent=2)

    def _log_intervention(
        self,
        intervention_type: str,
        target: str,
        message: str,
        metadata: dict[str, Any],
    ) -> None:
        """记录干预日志"""
        self.intervention_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": intervention_type,
                "target": target,
                "message": message,
                "metadata": metadata,
            }
        )


# ==================== 干预执行器 ====================


class InterventionExecutor:
    """干预执行器

    执行策略动作。
    """

    def __init__(self) -> None:
        """初始化执行器"""
        self.intervention_manager = InterventionManager()
        self.execution_log: list[ExecutionResult] = []

    def execute(self, violation: PolicyViolation) -> ExecutionResult:
        """执行干预

        参数：
            violation: 策略违规

        返回：
            执行结果
        """
        action = violation.action

        if action == "warn":
            self.intervention_manager.inject_context(
                target_agent="conversation_agent",
                context_type="warning",
                message=violation.message,
                severity=violation.severity,
            )
            result = ExecutionResult(
                success=True,
                action_taken="warn",
                message="已发送警告",
            )

        elif action == "block":
            self.intervention_manager.inject_context(
                target_agent="conversation_agent",
                context_type="blocking",
                message=violation.message,
                severity=violation.severity,
            )
            result = ExecutionResult(
                success=True,
                action_taken="block",
                message="已阻止请求",
            )

        elif action == "terminate":
            task_id = violation.context.get("task_id", "unknown")
            self.intervention_manager.terminate_task(
                task_id=task_id,
                reason=violation.message,
                graceful=False,
            )
            result = ExecutionResult(
                success=True,
                action_taken="terminate",
                message="已终止任务",
            )

        else:
            result = ExecutionResult(
                success=True,
                action_taken="log",
                message="已记录",
            )

        self.execution_log.append(result)
        return result


# ==================== 监督集成 ====================


class SupervisionIntegration:
    """监督集成

    提供完整的监督集成，连接扫描器、监控器和干预管理器。
    """

    def __init__(self) -> None:
        """初始化监督集成"""
        self.scanner = PromptScanner()
        self.resource_monitor = EnhancedResourceMonitor()
        self.intervention_manager = InterventionManager()
        self.executor = InterventionExecutor()

        self.strategy_repository: dict[str, dict[str, Any]] = {}
        self.consecutive_failures: dict[str, int] = {}

    def add_strategy(
        self,
        name: str,
        conditions: list[str],
        action: str,
        priority: int = 10,
    ) -> str:
        """添加策略"""
        strategy_id = f"strategy_{uuid.uuid4().hex[:12]}"
        self.strategy_repository[strategy_id] = {
            "id": strategy_id,
            "name": name,
            "conditions": conditions,
            "action": action,
            "priority": priority,
        }
        return strategy_id

    def supervise_conversation_input(
        self,
        message: str,
        session_id: str,
    ) -> dict[str, Any]:
        """监督对话输入

        参数：
            message: 消息
            session_id: 会话ID

        返回：
            监督结果
        """
        # 扫描消息
        scan_result = self.scanner.scan(message)

        if scan_result.passed:
            return {
                "allowed": True,
                "action": "allow",
                "scan_result": scan_result,
            }

        # 处理违规
        action = scan_result.recommended_action
        warning = None

        # 检查是否有自定义策略覆盖
        for violation in scan_result.violations:
            # 检查自定义策略
            for _strategy_id, strategy in self.strategy_repository.items():
                conditions = strategy.get("conditions", [])
                # 使用 category 匹配策略条件
                violation_category = violation.category or violation.policy_id
                if any(
                    cond == violation_category or cond in violation_category for cond in conditions
                ):
                    # 使用策略定义的动作（如果优先级更高）
                    strategy_action = strategy.get("action", "warn")
                    action_priority = {"allow": 0, "warn": 1, "block": 2, "terminate": 3}
                    if action_priority.get(strategy_action, 0) > action_priority.get(action, 0):
                        action = strategy_action

        for violation in scan_result.violations:
            # 更新违规的动作
            violation.action = action

            # 执行干预
            self.executor.execute(violation)

            # 记录干预
            self.intervention_manager.inject_context(
                target_agent="conversation_agent",
                context_type="warning" if action == "warn" else "blocking",
                message=violation.message,
                severity=violation.severity,
                metadata={"policy_id": violation.policy_id, "session_id": session_id},
            )

            if action == "warn":
                warning = violation.message

        return {
            "allowed": action == "warn",
            "action": action,
            "violations": [
                {
                    "policy_id": v.policy_id,
                    "policy_name": v.policy_name,
                    "message": v.message,
                }
                for v in scan_result.violations
            ],
            "warning": warning,
        }

    def supervise_workflow_execution(
        self,
        workflow_id: str,
        node_id: str,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """监督工作流执行

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            metrics: 指标

        返回：
            监督结果
        """
        # 记录资源使用
        self.resource_monitor.record_resource_usage(
            workflow_id=workflow_id,
            node_id=node_id,
            memory_mb=metrics.get("memory_mb", 0),
            cpu_percent=metrics.get("cpu_percent", 0),
            duration_seconds=metrics.get("duration_seconds", 0),
        )

        # 记录 API 延迟
        if "api_latency_ms" in metrics:
            self.resource_monitor.record_api_latency(
                workflow_id=workflow_id,
                node_id=node_id,
                api_name="default",
                latency_ms=metrics["api_latency_ms"],
            )

        # 检查阈值
        alerts = self.resource_monitor.check_thresholds(workflow_id)

        if not alerts:
            # 重置连续失败计数
            self.consecutive_failures[workflow_id] = 0
            return {
                "allowed": True,
                "action": "allow",
                "alerts": [],
            }

        # 更新连续失败计数
        self.consecutive_failures[workflow_id] = self.consecutive_failures.get(workflow_id, 0) + 1

        # 确定动作
        action = "warn"
        critical_memory = self.resource_monitor.thresholds.get("critical_memory_mb", 8192)

        if metrics.get("memory_mb", 0) > critical_memory:
            action = "terminate"
        elif self.consecutive_failures[workflow_id] >= 3:
            # 连续 3 次失败触发 REPLAN
            self.intervention_manager.trigger_replan(
                workflow_id=workflow_id,
                reason="连续资源超限",
            )

        # 记录干预事件
        for alert in alerts:
            self.intervention_manager.inject_context(
                target_agent="workflow_agent",
                context_type="warning",
                message=alert["message"],
                severity=alert.get("severity", "warning"),
                metadata={"workflow_id": workflow_id, "node_id": node_id},
            )

        return {
            "allowed": action != "terminate",
            "action": action,
            "alerts": alerts,
        }

    def get_intervention_log(self) -> list[dict[str, Any]]:
        """获取干预日志"""
        return self.intervention_manager.get_intervention_log()

    def get_intervention_events(self) -> list[ContextInjectionEvent]:
        """获取干预事件"""
        return self.intervention_manager.injection_events

    def get_replan_events(self) -> list[ReplanEvent]:
        """获取 REPLAN 事件"""
        return self.intervention_manager.get_replan_events()

    def generate_intervention_report(self) -> dict[str, Any]:
        """生成干预报告"""
        logs = self.intervention_manager.get_intervention_log()

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for log in logs:
            log_type = log.get("type", "unknown")
            by_type[log_type] = by_type.get(log_type, 0) + 1

            severity = log.get("metadata", {}).get("severity", "unknown")
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total_interventions": len(logs),
            "by_type": by_type,
            "by_severity": by_severity,
            "logs": logs,
        }


# 导出
__all__ = [
    "PolicyViolation",
    "ScanResult",
    "ExecutionResult",
    "ReplanEvent",
    "WorkflowTerminationResult",
    "PromptScanner",
    "EnhancedResourceMonitor",
    "InterventionManager",
    "InterventionExecutor",
    "SupervisionIntegration",
]

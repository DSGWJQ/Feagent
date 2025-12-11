"""监督模块 (Supervision Module)

业务定义：
- Coordinator 维护的监督模块
- 持续分析对话 agent 的上下文、SaveRequest、决策链路
- 判断是否需要干预（警告、节点替换、终止任务）
- 监督信息结构化（类型、内容、触发规则、持续时间）

设计原则：
- 规则可配置：支持添加自定义规则
- 内置规则：提供常用的安全和性能检测规则
- 完整日志：记录每次触发和干预

实现日期：2025-12-08
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

from src.domain.services.event_bus import Event

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================


class SupervisionAction(str, Enum):
    """监督动作类型

    定义监督模块可以执行的动作类型。
    优先级：TERMINATE > REPLACE > WARNING
    """

    WARNING = "warning"        # 警告 - 注入警告信息
    REPLACE = "replace"        # 替换 - 替换内容/节点
    TERMINATE = "terminate"    # 终止 - 终止任务

    @staticmethod
    def get_priority(action: "SupervisionAction") -> int:
        """获取动作优先级

        参数：
            action: 监督动作

        返回：
            优先级数值（越大优先级越高）
        """
        priorities = {
            SupervisionAction.WARNING: 10,
            SupervisionAction.REPLACE: 50,
            SupervisionAction.TERMINATE: 100,
        }
        return priorities.get(action, 0)


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class SupervisionInfo:
    """监督信息结构

    属性：
        supervision_id: 监督唯一标识
        session_id: 会话 ID
        action: 动作类型
        content: 监督内容/消息
        trigger_rule: 触发规则 ID
        trigger_condition: 触发条件描述
        duration: 持续时间（秒）
        metadata: 附加元数据
        timestamp: 创建时间
        resolved: 是否已解决
    """

    session_id: str
    action: SupervisionAction
    content: str
    trigger_rule: str
    trigger_condition: str
    supervision_id: str = field(default_factory=lambda: f"sup-{uuid4().hex[:12]}")
    duration: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "supervision_id": self.supervision_id,
            "session_id": self.session_id,
            "action": self.action.value,
            "content": self.content,
            "trigger_rule": self.trigger_rule,
            "trigger_condition": self.trigger_condition,
            "duration": self.duration,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
        }

    def mark_resolved(self) -> None:
        """标记为已解决"""
        self.resolved = True


@dataclass
class SupervisionRule:
    """监督规则

    属性：
        rule_id: 规则唯一标识
        name: 规则名称
        description: 规则描述
        action: 触发时的动作
        priority: 规则优先级
        enabled: 是否启用
        condition: 条件函数
        replacement_content: 替换内容（用于 REPLACE 动作）
    """

    rule_id: str
    name: str
    description: str
    action: SupervisionAction
    priority: int = 50
    enabled: bool = True
    condition: Callable[[dict[str, Any]], bool] | None = None
    replacement_content: str | None = None

    def check(self, context: dict[str, Any]) -> SupervisionInfo | None:
        """检查规则是否触发

        参数：
            context: 上下文数据

        返回：
            触发时返回 SupervisionInfo，否则返回 None
        """
        if not self.enabled:
            return None

        if self.condition is None:
            return None

        try:
            if self.condition(context):
                return SupervisionInfo(
                    session_id=context.get("session_id", "unknown"),
                    action=self.action,
                    content=f"规则 [{self.name}] 触发",
                    trigger_rule=self.rule_id,
                    trigger_condition=self.description,
                    metadata={
                        "rule_priority": self.priority,
                        "replacement_content": self.replacement_content,
                    },
                )
        except Exception as e:
            logger.warning(f"Rule {self.rule_id} check failed: {e}")

        return None


# =============================================================================
# 事件定义
# =============================================================================


@dataclass
class SupervisionTriggeredEvent(Event):
    """监督触发事件

    当监督规则被触发时发布。
    """

    supervision_info: SupervisionInfo = field(default_factory=lambda: SupervisionInfo(
        session_id="",
        action=SupervisionAction.WARNING,
        content="",
        trigger_rule="",
        trigger_condition="",
    ))

    @property
    def event_type(self) -> str:
        return "supervision_triggered"


@dataclass
class InterventionExecutedEvent(Event):
    """干预执行事件

    当干预被实际执行时发布。
    """

    supervision_id: str = ""
    session_id: str = ""
    action: SupervisionAction = SupervisionAction.WARNING
    result: str = ""

    @property
    def event_type(self) -> str:
        return "intervention_executed"


# =============================================================================
# 监督日志记录器
# =============================================================================


class SupervisionLogger:
    """监督日志记录器

    记录所有监督触发和干预操作。
    """

    def __init__(self):
        """初始化"""
        self._logs: list[dict[str, Any]] = []

    def log_trigger(self, info: SupervisionInfo) -> None:
        """记录触发

        参数：
            info: 监督信息
        """
        log_entry = {
            "type": "trigger",
            "supervision_id": info.supervision_id,
            "session_id": info.session_id,
            "action": info.action.value,
            "content": info.content,
            "trigger_rule": info.trigger_rule,
            "trigger_condition": info.trigger_condition,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        # 同时输出到标准日志
        logger.info(
            f"[SUPERVISION TRIGGER] rule={info.trigger_rule} "
            f"action={info.action.value} "
            f"session={info.session_id} "
            f"condition={info.trigger_condition}"
        )

    def log_intervention(self, info: SupervisionInfo, result: str) -> None:
        """记录干预

        参数：
            info: 监督信息
            result: 干预结果
        """
        log_entry = {
            "type": "intervention",
            "supervision_id": info.supervision_id,
            "session_id": info.session_id,
            "action": info.action.value,
            "content": info.content,
            "trigger_rule": info.trigger_rule,
            "trigger_condition": info.trigger_condition,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[SUPERVISION INTERVENTION] rule={info.trigger_rule} "
            f"action={info.action.value} "
            f"result={result} "
            f"session={info.session_id}"
        )

    def get_logs(self) -> list[dict[str, Any]]:
        """获取所有日志"""
        return self._logs.copy()

    def get_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """按会话获取日志"""
        return [log for log in self._logs if log.get("session_id") == session_id]

    def clear(self) -> None:
        """清空日志"""
        self._logs.clear()


# =============================================================================
# 内置规则
# =============================================================================


def _create_builtin_rules() -> list[SupervisionRule]:
    """创建内置规则

    返回：
        内置规则列表
    """
    rules = []

    # 1. 高上下文使用率警告规则
    rules.append(SupervisionRule(
        rule_id="builtin-high-usage-warning",
        name="高上下文使用率警告",
        description="上下文使用率超过80%时警告",
        action=SupervisionAction.WARNING,
        priority=30,
        condition=lambda ctx: ctx.get("usage_ratio", 0) > 0.8,
    ))

    # 2. 临界上下文使用率终止规则
    rules.append(SupervisionRule(
        rule_id="builtin-critical-usage-terminate",
        name="临界上下文使用率终止",
        description="上下文使用率超过95%时终止",
        action=SupervisionAction.TERMINATE,
        priority=90,
        condition=lambda ctx: ctx.get("usage_ratio", 0) > 0.95,
    ))

    # 3. 敏感路径检测规则
    def _check_dangerous_path(ctx: dict[str, Any]) -> bool:
        path = ctx.get("target_path", "")
        dangerous_prefixes = ["/etc/", "/boot/", "/root/", "/sys/", "/proc/"]
        return any(path.startswith(prefix) for prefix in dangerous_prefixes)

    rules.append(SupervisionRule(
        rule_id="builtin-dangerous-path",
        name="危险路径检测",
        description="检测对系统关键路径的写入",
        action=SupervisionAction.TERMINATE,
        priority=100,
        condition=_check_dangerous_path,
    ))

    # 4. 敏感内容检测规则
    def _check_sensitive_content(ctx: dict[str, Any]) -> bool:
        content = ctx.get("content", "")
        patterns = [
            r'password\s*=\s*[\'"][^\'"]+[\'"]',
            r'api_key\s*=\s*[\'"][^\'"]+[\'"]',
            r'secret\s*=\s*[\'"][^\'"]+[\'"]',
            r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----',
        ]
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    rules.append(SupervisionRule(
        rule_id="builtin-sensitive-content",
        name="敏感内容检测",
        description="检测密码、API密钥等敏感信息",
        action=SupervisionAction.WARNING,
        priority=70,
        condition=_check_sensitive_content,
    ))

    # 5. 危险命令检测规则
    def _check_dangerous_command(ctx: dict[str, Any]) -> bool:
        content = ctx.get("content", "")
        dangerous_commands = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            ":(){:|:&};:",  # fork bomb
            "dd if=/dev/zero",
        ]
        return any(cmd in content for cmd in dangerous_commands)

    rules.append(SupervisionRule(
        rule_id="builtin-dangerous-command",
        name="危险命令检测",
        description="检测可能造成系统损坏的命令",
        action=SupervisionAction.TERMINATE,
        priority=100,
        condition=_check_dangerous_command,
    ))

    # 6. 循环检测规则
    def _check_loop_pattern(ctx: dict[str, Any]) -> bool:
        decisions = ctx.get("decisions", [])
        if len(decisions) < 5:
            return False
        # 检查最近5个决策是否相同
        recent_actions = [d.get("action") for d in decisions[-5:]]
        return len(set(recent_actions)) == 1 and recent_actions[0] is not None

    rules.append(SupervisionRule(
        rule_id="builtin-loop-detection",
        name="循环检测",
        description="检测重复的决策模式",
        action=SupervisionAction.WARNING,
        priority=50,
        condition=_check_loop_pattern,
    ))

    # 7. 超长对话历史警告
    def _check_long_history(ctx: dict[str, Any]) -> bool:
        history = ctx.get("conversation_history", [])
        return len(history) > 50

    rules.append(SupervisionRule(
        rule_id="builtin-long-history",
        name="超长对话历史",
        description="对话历史超过50轮时警告",
        action=SupervisionAction.WARNING,
        priority=20,
        condition=_check_long_history,
    ))

    return rules


# =============================================================================
# 监督模块
# =============================================================================


class SupervisionModule:
    """监督模块

    持续分析对话 agent 的上下文、SaveRequest、决策链路，
    判断是否需要干预（警告、节点替换、终止任务）。
    """

    def __init__(
        self,
        rules: list[SupervisionRule] | None = None,
        logger: SupervisionLogger | None = None,
        use_builtin_rules: bool = False,
    ):
        """初始化

        参数：
            rules: 自定义规则列表
            logger: 日志记录器
            use_builtin_rules: 是否使用内置规则
        """
        self._rules: list[SupervisionRule] = []
        self._logger = logger or SupervisionLogger()

        # 添加内置规则
        if use_builtin_rules:
            self._rules.extend(_create_builtin_rules())

        # 添加自定义规则
        if rules:
            self._rules.extend(rules)

    @property
    def rules(self) -> list[SupervisionRule]:
        """获取规则列表"""
        return self._rules.copy()

    @property
    def supervision_logger(self) -> SupervisionLogger:
        """获取日志记录器"""
        return self._logger

    def add_rule(self, rule: SupervisionRule) -> None:
        """添加规则

        参数：
            rule: 监督规则
        """
        self._rules.append(rule)
        logger.debug(f"Added supervision rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则

        参数：
            rule_id: 规则 ID

        返回：
            是否成功移除
        """
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                del self._rules[i]
                logger.debug(f"Removed supervision rule: {rule_id}")
                return True
        return False

    def analyze_context(self, context: dict[str, Any]) -> list[SupervisionInfo]:
        """分析上下文

        参数：
            context: 上下文数据

        返回：
            触发的监督信息列表
        """
        results = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            info = rule.check(context)
            if info:
                results.append(info)
                self._logger.log_trigger(info)

        # 按动作优先级排序
        results.sort(
            key=lambda x: SupervisionAction.get_priority(x.action),
            reverse=True
        )

        return results

    def analyze_save_request(self, request: dict[str, Any]) -> list[SupervisionInfo]:
        """分析保存请求

        参数：
            request: 保存请求数据

        返回：
            触发的监督信息列表
        """
        # 将请求转换为上下文格式
        context = {
            "session_id": request.get("session_id", "unknown"),
            "target_path": request.get("target_path", ""),
            "content": request.get("content", ""),
            "request_id": request.get("request_id", ""),
        }

        return self.analyze_context(context)

    def analyze_decision_chain(
        self,
        decisions: list[dict[str, Any]],
        session_id: str,
    ) -> list[SupervisionInfo]:
        """分析决策链路

        参数：
            decisions: 决策列表
            session_id: 会话 ID

        返回：
            触发的监督信息列表
        """
        context = {
            "session_id": session_id,
            "decisions": decisions,
        }

        return self.analyze_context(context)

    def should_intervene(self, infos: list[SupervisionInfo]) -> bool:
        """判断是否需要干预

        参数：
            infos: 监督信息列表

        返回：
            是否需要干预
        """
        return len(infos) > 0

    def get_highest_priority_action(
        self,
        infos: list[SupervisionInfo],
    ) -> SupervisionAction | None:
        """获取最高优先级动作

        参数：
            infos: 监督信息列表

        返回：
            最高优先级的动作
        """
        if not infos:
            return None

        return max(infos, key=lambda x: SupervisionAction.get_priority(x.action)).action


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "SupervisionAction",
    "SupervisionInfo",
    "SupervisionRule",
    "SupervisionTriggeredEvent",
    "InterventionExecutedEvent",
    "SupervisionLogger",
    "SupervisionModule",
]

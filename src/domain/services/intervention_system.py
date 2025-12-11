"""干预系统模块 (Intervention System)

业务定义：
- 为 Coordinator 提供修改工作流定义的接口（替换/移除节点）
- 提供终止任务的指令通道（通知 ConversationAgent、WorkflowAgent、用户）
- 支持干预级别升级机制

设计原则：
- 干预级别递进：NONE → NOTIFY → WARN → REPLACE → TERMINATE
- 完整日志：记录每次干预操作
- 通知机制：支持多目标通知

实现日期：2025-12-08
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from src.domain.services.event_bus import Event

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================


class InterventionLevel(str, Enum):
    """干预级别枚举

    定义干预的严重程度级别。
    级别递进：NONE → NOTIFY → WARN → REPLACE → TERMINATE
    """

    NONE = "none"  # 无干预
    NOTIFY = "notify"  # 通知（仅记录）
    WARN = "warn"  # 警告（注入警告）
    REPLACE = "replace"  # 替换（替换节点）
    TERMINATE = "terminate"  # 终止（强制终止）

    @staticmethod
    def get_severity(level: "InterventionLevel") -> int:
        """获取级别严重程度

        参数：
            level: 干预级别

        返回：
            严重程度数值（越大越严重）
        """
        severities = {
            InterventionLevel.NONE: 0,
            InterventionLevel.NOTIFY: 10,
            InterventionLevel.WARN: 30,
            InterventionLevel.REPLACE: 60,
            InterventionLevel.TERMINATE: 100,
        }
        return severities.get(level, 0)

    @staticmethod
    def can_escalate(current: "InterventionLevel", target: "InterventionLevel") -> bool:
        """判断是否可以升级到目标级别

        参数：
            current: 当前级别
            target: 目标级别

        返回：
            是否可以升级
        """
        return InterventionLevel.get_severity(target) > InterventionLevel.get_severity(current)

    @staticmethod
    def next_level(current: "InterventionLevel") -> "InterventionLevel":
        """获取下一个级别

        参数：
            current: 当前级别

        返回：
            下一个级别
        """
        order = [
            InterventionLevel.NONE,
            InterventionLevel.NOTIFY,
            InterventionLevel.WARN,
            InterventionLevel.REPLACE,
            InterventionLevel.TERMINATE,
        ]
        try:
            idx = order.index(current)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        return current


# =============================================================================
# 请求数据结构
# =============================================================================


@dataclass
class NodeReplacementRequest:
    """节点替换请求

    属性：
        request_id: 请求唯一标识
        workflow_id: 工作流 ID
        original_node_id: 原节点 ID
        replacement_node_config: 替换节点配置（None 表示移除）
        reason: 替换原因
        session_id: 会话 ID
        timestamp: 请求时间
    """

    workflow_id: str
    original_node_id: str
    replacement_node_config: dict[str, Any] | None
    reason: str
    session_id: str
    request_id: str = field(default_factory=lambda: f"nrr-{uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)

    def is_removal(self) -> bool:
        """是否为移除操作"""
        return self.replacement_node_config is None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "original_node_id": self.original_node_id,
            "replacement_node_config": self.replacement_node_config,
            "reason": self.reason,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "is_removal": self.is_removal(),
        }


@dataclass
class TaskTerminationRequest:
    """任务终止请求

    属性：
        request_id: 请求唯一标识
        session_id: 会话 ID
        reason: 终止原因
        error_code: 错误代码
        notify_agents: 需要通知的 Agent 列表
        notify_user: 是否通知用户
        timestamp: 请求时间
    """

    session_id: str
    reason: str
    error_code: str
    request_id: str = field(default_factory=lambda: f"ttr-{uuid4().hex[:12]}")
    notify_agents: list[str] = field(default_factory=lambda: ["conversation", "workflow"])
    notify_user: bool = True
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "reason": self.reason,
            "error_code": self.error_code,
            "notify_agents": self.notify_agents,
            "notify_user": self.notify_user,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# 结果数据结构
# =============================================================================


@dataclass
class ModificationResult:
    """工作流修改结果"""

    success: bool
    modified_workflow: dict[str, Any] | None = None
    error: str | None = None
    original_node_id: str = ""
    replacement_node_id: str | None = None


@dataclass
class ValidationResult:
    """工作流验证结果"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class TerminationResult:
    """任务终止结果"""

    success: bool
    session_id: str
    notified_agents: list[str] = field(default_factory=list)
    user_notified: bool = False
    user_message: str | None = None
    error_event: Any = None


@dataclass
class InterventionResult:
    """干预结果"""

    success: bool
    action_taken: str
    details: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 事件定义
# =============================================================================


@dataclass
class NodeReplacedEvent(Event):
    """节点替换事件"""

    workflow_id: str = ""
    original_node_id: str = ""
    replacement_node_id: str = ""
    reason: str = ""
    session_id: str = ""

    @property
    def event_type(self) -> str:
        return "node_replaced"


@dataclass
class TaskTerminatedEvent(Event):
    """任务终止事件"""

    session_id: str = ""
    reason: str = ""
    error_code: str = ""

    @property
    def event_type(self) -> str:
        return "task_terminated"


@dataclass
class UserErrorNotificationEvent(Event):
    """用户错误通知事件"""

    session_id: str = ""
    error_code: str = ""
    error_message: str = ""
    user_friendly_message: str = ""

    @property
    def event_type(self) -> str:
        return "user_error_notification"


# =============================================================================
# 干预日志记录器
# =============================================================================


class InterventionLogger:
    """干预日志记录器

    记录所有干预操作。
    """

    def __init__(self):
        """初始化"""
        self._logs: list[dict[str, Any]] = []

    def log_node_replacement(
        self,
        workflow_id: str,
        original_node_id: str,
        replacement_node_id: str | None,
        reason: str,
        session_id: str,
    ) -> None:
        """记录节点替换"""
        log_entry = {
            "type": "node_replacement",
            "workflow_id": workflow_id,
            "original_node_id": original_node_id,
            "replacement_node_id": replacement_node_id,
            "reason": reason,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[INTERVENTION] type=node_replacement "
            f"workflow={workflow_id} "
            f"node={original_node_id} -> {replacement_node_id} "
            f"reason={reason}"
        )

    def log_task_termination(
        self,
        session_id: str,
        reason: str,
        error_code: str,
    ) -> None:
        """记录任务终止"""
        log_entry = {
            "type": "task_termination",
            "session_id": session_id,
            "reason": reason,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[INTERVENTION] type=task_termination "
            f"session={session_id} "
            f"error_code={error_code} "
            f"reason={reason}"
        )

    def log_intervention(
        self,
        level: InterventionLevel,
        session_id: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """记录通用干预"""
        log_entry = {
            "type": "intervention",
            "level": level.value,
            "session_id": session_id,
            "action": action,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[INTERVENTION] level={level.value} " f"session={session_id} " f"action={action}"
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
# 工作流修改器
# =============================================================================


class WorkflowModifier:
    """工作流修改器

    提供修改工作流定义的接口。
    """

    def __init__(self, logger: InterventionLogger | None = None):
        """初始化

        参数：
            logger: 干预日志记录器
        """
        self._logger = logger or InterventionLogger()

    def replace_node(
        self,
        workflow_definition: dict[str, Any],
        request: NodeReplacementRequest,
    ) -> ModificationResult:
        """替换节点

        参数：
            workflow_definition: 工作流定义
            request: 替换请求

        返回：
            修改结果
        """
        nodes = workflow_definition.get("nodes", [])

        # 查找原节点
        original_index = None
        for i, node in enumerate(nodes):
            if node.get("id") == request.original_node_id:
                original_index = i
                break

        if original_index is None:
            return ModificationResult(
                success=False,
                error=f"Node not found: {request.original_node_id}",
            )

        # 创建修改后的工作流
        modified_workflow = workflow_definition.copy()
        modified_nodes = nodes.copy()

        # 创建替换节点
        replacement_node = request.replacement_node_config.copy()
        if "id" not in replacement_node:
            replacement_node["id"] = request.original_node_id  # 保持原 ID
        replacement_node_id = replacement_node["id"]

        # 替换节点
        modified_nodes[original_index] = replacement_node
        modified_workflow["nodes"] = modified_nodes

        # 如果节点 ID 变化，更新边
        if replacement_node_id != request.original_node_id:
            edges = modified_workflow.get("edges", [])
            modified_edges = []
            for edge in edges:
                new_edge = edge.copy()
                if new_edge.get("from") == request.original_node_id:
                    new_edge["from"] = replacement_node_id
                if new_edge.get("to") == request.original_node_id:
                    new_edge["to"] = replacement_node_id
                modified_edges.append(new_edge)
            modified_workflow["edges"] = modified_edges

        # 记录日志
        self._logger.log_node_replacement(
            workflow_id=request.workflow_id,
            original_node_id=request.original_node_id,
            replacement_node_id=replacement_node_id,
            reason=request.reason,
            session_id=request.session_id,
        )

        return ModificationResult(
            success=True,
            modified_workflow=modified_workflow,
            original_node_id=request.original_node_id,
            replacement_node_id=replacement_node_id,
        )

    def remove_node(
        self,
        workflow_definition: dict[str, Any],
        request: NodeReplacementRequest,
    ) -> ModificationResult:
        """移除节点

        参数：
            workflow_definition: 工作流定义
            request: 移除请求

        返回：
            修改结果
        """
        nodes = workflow_definition.get("nodes", [])

        # 查找原节点
        original_index = None
        for i, node in enumerate(nodes):
            if node.get("id") == request.original_node_id:
                original_index = i
                break

        if original_index is None:
            return ModificationResult(
                success=False,
                error=f"Node not found: {request.original_node_id}",
            )

        # 创建修改后的工作流
        modified_workflow = workflow_definition.copy()
        modified_nodes = [n for n in nodes if n.get("id") != request.original_node_id]
        modified_workflow["nodes"] = modified_nodes

        # 移除相关边
        edges = modified_workflow.get("edges", [])
        modified_edges = [
            e
            for e in edges
            if e.get("from") != request.original_node_id and e.get("to") != request.original_node_id
        ]
        modified_workflow["edges"] = modified_edges

        # 记录日志
        self._logger.log_node_replacement(
            workflow_id=request.workflow_id,
            original_node_id=request.original_node_id,
            replacement_node_id=None,
            reason=request.reason,
            session_id=request.session_id,
        )

        return ModificationResult(
            success=True,
            modified_workflow=modified_workflow,
            original_node_id=request.original_node_id,
            replacement_node_id=None,
        )

    def validate_workflow(self, workflow_definition: dict[str, Any]) -> ValidationResult:
        """验证工作流

        参数：
            workflow_definition: 工作流定义

        返回：
            验证结果
        """
        errors = []

        # 检查节点
        nodes = workflow_definition.get("nodes", [])
        if not nodes:
            errors.append("Workflow has no nodes")

        # 检查节点 ID 唯一性
        node_ids = [n.get("id") for n in nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Duplicate node IDs found")

        # 检查边的有效性
        edges = workflow_definition.get("edges", [])
        for edge in edges:
            from_id = edge.get("from")
            to_id = edge.get("to")
            if from_id not in node_ids:
                errors.append(f"Edge references non-existent node: {from_id}")
            if to_id not in node_ids:
                errors.append(f"Edge references non-existent node: {to_id}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )


# =============================================================================
# 任务终止器
# =============================================================================


class TaskTerminator:
    """任务终止器

    提供终止任务的指令通道。
    """

    def __init__(self, logger: InterventionLogger | None = None):
        """初始化

        参数：
            logger: 干预日志记录器
        """
        self._logger = logger or InterventionLogger()

    def terminate(self, request: TaskTerminationRequest) -> TerminationResult:
        """终止任务

        参数：
            request: 终止请求

        返回：
            终止结果
        """
        notified_agents = []
        user_message = None

        # 通知 Agent
        for agent_type in request.notify_agents:
            self._notify_agent(agent_type, request.session_id, request.reason)
            notified_agents.append(agent_type)

        # 通知用户
        user_notified = False
        if request.notify_user:
            user_message = self._create_user_message(request)
            user_notified = True

        # 创建错误事件
        error_event = TaskTerminatedEvent(
            session_id=request.session_id,
            reason=request.reason,
            error_code=request.error_code,
        )

        # 记录日志
        self._logger.log_task_termination(
            session_id=request.session_id,
            reason=request.reason,
            error_code=request.error_code,
        )

        return TerminationResult(
            success=True,
            session_id=request.session_id,
            notified_agents=notified_agents,
            user_notified=user_notified,
            user_message=user_message,
            error_event=error_event,
        )

    def _notify_agent(self, agent_type: str, session_id: str, reason: str) -> None:
        """通知 Agent

        参数：
            agent_type: Agent 类型
            session_id: 会话 ID
            reason: 终止原因
        """
        logger.info(
            f"[TERMINATION] Notifying {agent_type} agent: " f"session={session_id} reason={reason}"
        )

    def _create_user_message(self, request: TaskTerminationRequest) -> str:
        """创建用户消息

        参数：
            request: 终止请求

        返回：
            用户友好的错误消息
        """
        return (
            f"任务已终止 [错误代码: {request.error_code}]\n"
            f"原因: {request.reason}\n"
            f"如需帮助，请联系管理员。"
        )


# =============================================================================
# 干预协调器
# =============================================================================


class InterventionCoordinator:
    """干预协调器

    协调干预操作，支持级别升级。
    """

    def __init__(
        self,
        workflow_modifier: WorkflowModifier | None = None,
        task_terminator: TaskTerminator | None = None,
        logger: InterventionLogger | None = None,
    ):
        """初始化

        参数：
            workflow_modifier: 工作流修改器
            task_terminator: 任务终止器
            logger: 干预日志记录器
        """
        self._logger = logger or InterventionLogger()
        self._workflow_modifier = workflow_modifier or WorkflowModifier(self._logger)
        self._task_terminator = task_terminator or TaskTerminator(self._logger)

    @property
    def intervention_logger(self) -> InterventionLogger:
        """获取日志记录器"""
        return self._logger

    def handle_intervention(
        self,
        level: InterventionLevel,
        context: dict[str, Any],
    ) -> InterventionResult:
        """处理干预

        参数：
            level: 干预级别
            context: 上下文数据

        返回：
            干预结果
        """
        session_id = context.get("session_id", "unknown")

        if level == InterventionLevel.NONE:
            return InterventionResult(success=True, action_taken="none")

        elif level == InterventionLevel.NOTIFY:
            self._logger.log_intervention(level, session_id, "logged", context)
            return InterventionResult(success=True, action_taken="logged")

        elif level == InterventionLevel.WARN:
            self._logger.log_intervention(level, session_id, "warning_injected", context)
            return InterventionResult(success=True, action_taken="warning_injected")

        elif level == InterventionLevel.REPLACE:
            self._logger.log_intervention(level, session_id, "node_replaced", context)
            return InterventionResult(success=True, action_taken="node_replaced")

        elif level == InterventionLevel.TERMINATE:
            self._logger.log_intervention(level, session_id, "task_terminated", context)
            return InterventionResult(success=True, action_taken="task_terminated")

        return InterventionResult(success=False, action_taken="unknown")

    def escalate_intervention(
        self,
        current_level: InterventionLevel,
        reason: str,
    ) -> InterventionLevel:
        """升级干预级别

        参数：
            current_level: 当前级别
            reason: 升级原因

        返回：
            新的干预级别
        """
        new_level = InterventionLevel.next_level(current_level)

        logger.info(f"[ESCALATION] {current_level.value} -> {new_level.value}: {reason}")

        return new_level


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "InterventionLevel",
    "NodeReplacementRequest",
    "TaskTerminationRequest",
    "ModificationResult",
    "ValidationResult",
    "TerminationResult",
    "InterventionResult",
    "NodeReplacedEvent",
    "TaskTerminatedEvent",
    "UserErrorNotificationEvent",
    "InterventionLogger",
    "WorkflowModifier",
    "TaskTerminator",
    "InterventionCoordinator",
]

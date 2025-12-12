"""干预系统数据模型

Phase 34.15: 从 intervention_system.py 提取数据模型

提供干预系统使用的枚举和数据类：
- InterventionLevel: 干预级别枚举
- NodeReplacementRequest: 节点替换请求
- TaskTerminationRequest: 任务终止请求
- ModificationResult: 工作流修改结果
- ValidationResult: 工作流验证结果
- TerminationResult: 任务终止结果
- InterventionResult: 干预结果
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

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
    def get_severity(level: InterventionLevel) -> int:
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
    def can_escalate(current: InterventionLevel, target: InterventionLevel) -> bool:
        """判断是否可以升级到目标级别

        参数：
            current: 当前级别
            target: 目标级别

        返回：
            是否可以升级
        """
        return InterventionLevel.get_severity(target) > InterventionLevel.get_severity(current)

    @staticmethod
    def next_level(current: InterventionLevel) -> InterventionLevel:
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


__all__ = [
    "InterventionLevel",
    "NodeReplacementRequest",
    "TaskTerminationRequest",
    "ModificationResult",
    "ValidationResult",
    "TerminationResult",
    "InterventionResult",
]

"""上下文注入机制模块 (Context Injection)

业务定义：
- 为 Coordinator 提供向 ConversationAgent 注入上下文的能力
- 支持在 ReAct 循环的不同阶段注入信息
- 支持指令/观察/记忆/警告/补充/干预等多种注入类型

设计原则：
- 注入点明确：PRE_LOOP / PRE_THINKING / POST_THINKING / INTERVENTION
- 优先级控制：高优先级注入先处理
- 完整日志：记录所有注入及其原因

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


class InjectionType(str, Enum):
    """注入类型枚举

    定义可以注入的信息类型。
    """

    INSTRUCTION = "instruction"  # 指令更新
    OBSERVATION = "observation"  # 观察信息
    MEMORY = "memory"  # 长期记忆
    WARNING = "warning"  # 警告信息
    SUPPLEMENT = "supplement"  # 补充信息
    INTERVENTION = "intervention"  # 干预指令


class InjectionPoint(str, Enum):
    """注入点枚举

    定义在 ReAct 循环中可以注入的位置。
    """

    PRE_LOOP = "pre_loop"  # 循环开始前
    PRE_THINKING = "pre_thinking"  # 思考阶段前
    POST_THINKING = "post_thinking"  # 思考阶段后
    INTERVENTION = "intervention"  # 干预注入点


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class ContextInjection:
    """上下文注入数据

    属性：
        injection_id: 注入唯一标识
        session_id: 会话 ID
        injection_type: 注入类型
        injection_point: 注入点
        content: 注入内容
        source: 来源（coordinator/supervisor/memory_system）
        reason: 注入原因
        priority: 优先级（数值越大优先级越高）
        metadata: 附加元数据
        timestamp: 创建时间
        applied: 是否已应用
    """

    session_id: str
    injection_type: InjectionType
    injection_point: InjectionPoint
    content: str
    source: str
    reason: str
    injection_id: str = field(default_factory=lambda: f"inj-{uuid4().hex[:12]}")
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "injection_id": self.injection_id,
            "session_id": self.session_id,
            "injection_type": self.injection_type.value,
            "injection_point": self.injection_point.value,
            "content": self.content,
            "source": self.source,
            "reason": self.reason,
            "priority": self.priority,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "applied": self.applied,
        }

    def to_prompt_format(self) -> str:
        """转换为提示词格式

        返回可直接插入上下文的格式化字符串。
        """
        type_labels = {
            InjectionType.INSTRUCTION: "[指令]",
            InjectionType.OBSERVATION: "[观察]",
            InjectionType.MEMORY: "[记忆]",
            InjectionType.WARNING: "[警告]",
            InjectionType.SUPPLEMENT: "[补充]",
            InjectionType.INTERVENTION: "[干预]",
        }

        label = type_labels.get(self.injection_type, "[信息]")
        return f"{label} {self.content}"


# =============================================================================
# 事件定义
# =============================================================================


@dataclass
class ContextInjectionEvent(Event):
    """上下文注入事件

    当注入被添加时发布。
    """

    injection: ContextInjection = field(
        default_factory=lambda: ContextInjection(
            session_id="",
            injection_type=InjectionType.INSTRUCTION,
            injection_point=InjectionPoint.PRE_LOOP,
            content="",
            source="",
            reason="",
        )
    )

    @property
    def event_type(self) -> str:
        return "context_injection"


@dataclass
class InjectionAppliedEvent(Event):
    """注入已应用事件

    当注入被实际应用到上下文时发布。
    """

    injection_id: str = ""
    session_id: str = ""
    applied_at_iteration: int = 0

    @property
    def event_type(self) -> str:
        return "injection_applied"


# =============================================================================
# 注入日志记录器
# =============================================================================


class InjectionLogger:
    """注入日志记录器

    记录所有注入操作及其结果。
    """

    def __init__(self):
        """初始化"""
        self._logs: list[dict[str, Any]] = []

    def log_injection(self, injection: ContextInjection) -> None:
        """记录注入

        参数：
            injection: 注入数据
        """
        log_entry = {
            "type": "injection",
            "injection_id": injection.injection_id,
            "session_id": injection.session_id,
            "injection_type": injection.injection_type.value,
            "injection_point": injection.injection_point.value,
            "content": injection.content,
            "source": injection.source,
            "reason": injection.reason,
            "priority": injection.priority,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        # 同时输出到标准日志
        logger.info(
            f"[INJECTION] type={injection.injection_type.value} "
            f"point={injection.injection_point.value} "
            f"session={injection.session_id} "
            f"source={injection.source} "
            f"reason={injection.reason}"
        )

    def log_applied(
        self,
        injection_id: str,
        session_id: str,
        iteration: int = 0,
    ) -> None:
        """记录注入已应用

        参数：
            injection_id: 注入 ID
            session_id: 会话 ID
            iteration: 应用时的迭代次数
        """
        log_entry = {
            "type": "applied",
            "injection_id": injection_id,
            "session_id": session_id,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[INJECTION APPLIED] id={injection_id} "
            f"session={session_id} "
            f"iteration={iteration}"
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
# 上下文注入管理器
# =============================================================================


class ContextInjectionManager:
    """上下文注入管理器

    管理待处理的上下文注入，支持按会话和注入点分类。
    """

    def __init__(self, logger: InjectionLogger | None = None):
        """初始化

        参数：
            logger: 注入日志记录器
        """
        self._injections: dict[str, list[ContextInjection]] = {}
        self._logger = logger

    def add_injection(self, injection: ContextInjection) -> None:
        """添加注入

        参数：
            injection: 注入数据
        """
        session_id = injection.session_id

        if session_id not in self._injections:
            self._injections[session_id] = []

        self._injections[session_id].append(injection)

        # 记录日志
        if self._logger:
            self._logger.log_injection(injection)

        logger.debug(
            f"Added injection {injection.injection_id} "
            f"to session {session_id} "
            f"at point {injection.injection_point.value}"
        )

    def get_pending_injections(
        self,
        session_id: str,
        injection_point: InjectionPoint,
    ) -> list[ContextInjection]:
        """获取待处理注入

        参数：
            session_id: 会话 ID
            injection_point: 注入点

        返回：
            按优先级排序的注入列表（高优先级在前）
        """
        if session_id not in self._injections:
            return []

        pending = [
            inj
            for inj in self._injections[session_id]
            if inj.injection_point == injection_point and not inj.applied
        ]

        # 按优先级降序排序
        pending.sort(key=lambda x: x.priority, reverse=True)

        return pending

    def mark_as_applied(
        self,
        injection_id: str,
        iteration: int = 0,
    ) -> bool:
        """标记注入已应用

        参数：
            injection_id: 注入 ID
            iteration: 应用时的迭代次数

        返回：
            是否成功标记
        """
        for session_id, injections in self._injections.items():
            for injection in injections:
                if injection.injection_id == injection_id:
                    injection.applied = True

                    # 记录日志
                    if self._logger:
                        self._logger.log_applied(
                            injection_id=injection_id,
                            session_id=session_id,
                            iteration=iteration,
                        )

                    logger.debug(f"Marked injection {injection_id} as applied")
                    return True

        return False

    def clear_session(self, session_id: str) -> None:
        """清除会话的所有注入

        参数：
            session_id: 会话 ID
        """
        if session_id in self._injections:
            del self._injections[session_id]
            logger.debug(f"Cleared all injections for session {session_id}")

    def clear_all(self) -> None:
        """清除所有注入"""
        self._injections.clear()
        logger.debug("Cleared all injections")

    # =========================================================================
    # 便捷注入方法
    # =========================================================================

    def inject_memory(
        self,
        session_id: str,
        content: str,
        source: str = "memory_system",
        relevance_score: float = 0.0,
        priority: int = 10,
    ) -> ContextInjection:
        """注入长期记忆

        参数：
            session_id: 会话 ID
            content: 记忆内容
            source: 来源
            relevance_score: 相关性分数
            priority: 优先级

        返回：
            创建的注入
        """
        injection = ContextInjection(
            session_id=session_id,
            injection_type=InjectionType.MEMORY,
            injection_point=InjectionPoint.PRE_LOOP,
            content=content,
            source=source,
            reason="长期记忆召回",
            priority=priority,
            metadata={"relevance_score": relevance_score},
        )

        self.add_injection(injection)
        return injection

    def inject_warning(
        self,
        session_id: str,
        content: str,
        source: str = "supervisor",
        reason: str = "安全检测",
        priority: int = 50,
    ) -> ContextInjection:
        """注入警告

        参数：
            session_id: 会话 ID
            content: 警告内容
            source: 来源
            reason: 原因
            priority: 优先级

        返回：
            创建的注入
        """
        injection = ContextInjection(
            session_id=session_id,
            injection_type=InjectionType.WARNING,
            injection_point=InjectionPoint.PRE_THINKING,
            content=content,
            source=source,
            reason=reason,
            priority=priority,
        )

        self.add_injection(injection)
        return injection

    def inject_intervention(
        self,
        session_id: str,
        content: str,
        source: str = "coordinator",
        reason: str = "需要干预",
        priority: int = 100,
    ) -> ContextInjection:
        """注入干预

        参数：
            session_id: 会话 ID
            content: 干预内容
            source: 来源
            reason: 原因
            priority: 优先级（干预默认最高）

        返回：
            创建的注入
        """
        injection = ContextInjection(
            session_id=session_id,
            injection_type=InjectionType.INTERVENTION,
            injection_point=InjectionPoint.INTERVENTION,
            content=content,
            source=source,
            reason=reason,
            priority=priority,
        )

        self.add_injection(injection)
        return injection

    def inject_instruction(
        self,
        session_id: str,
        content: str,
        source: str = "coordinator",
        reason: str = "指令更新",
        priority: int = 30,
    ) -> ContextInjection:
        """注入指令

        参数：
            session_id: 会话 ID
            content: 指令内容
            source: 来源
            reason: 原因
            priority: 优先级

        返回：
            创建的注入
        """
        injection = ContextInjection(
            session_id=session_id,
            injection_type=InjectionType.INSTRUCTION,
            injection_point=InjectionPoint.PRE_LOOP,
            content=content,
            source=source,
            reason=reason,
            priority=priority,
        )

        self.add_injection(injection)
        return injection

    def inject_observation(
        self,
        session_id: str,
        content: str,
        source: str = "monitor",
        reason: str = "状态观察",
        priority: int = 20,
    ) -> ContextInjection:
        """注入观察

        参数：
            session_id: 会话 ID
            content: 观察内容
            source: 来源
            reason: 原因
            priority: 优先级

        返回：
            创建的注入
        """
        injection = ContextInjection(
            session_id=session_id,
            injection_type=InjectionType.OBSERVATION,
            injection_point=InjectionPoint.PRE_LOOP,
            content=content,
            source=source,
            reason=reason,
            priority=priority,
        )

        self.add_injection(injection)
        return injection


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "InjectionType",
    "InjectionPoint",
    "ContextInjection",
    "ContextInjectionEvent",
    "InjectionAppliedEvent",
    "InjectionLogger",
    "ContextInjectionManager",
]

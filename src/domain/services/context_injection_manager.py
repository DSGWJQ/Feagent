"""上下文注入管理器

Phase 34.12: 从 CoordinatorAgent 提取上下文注入逻辑到独立 Facade

职责：
- 集中管理所有注入类型（WARNING/INTERVENTION/MEMORY/OBSERVATION/SUPPLEMENT）
- 提供类型→注入点映射逻辑
- 代理到核心注入器和日志记录器
- 维持向后兼容的API接口

设计模式：
- Facade/Manager: 集中注入 API + 日志查询
- Delegation: CoordinatorAgent 通过薄代理调用

依赖：
- ContextInjectionManager (src/domain/services/context_injection.py)
- InjectionLogger (由 bootstrap 注入)

版本：
- 提取时间: 2025-12-11
- 来源: CoordinatorAgent Phase 34.3 (lines 828-978)
"""

from typing import Any


class ContextInjectionManager:
    """上下文注入管理器

    集中管理上下文注入相关操作，包括：
    - 通用注入（含类型→注入点映射）
    - 四类专用注入：warning/intervention/memory/observation
    - 注入日志查询（全部/按会话）

    属性：
        _injection_manager: 核心注入器实例
        _injection_logger: 注入日志记录器实例
    """

    def __init__(
        self,
        injection_manager: Any,
        injection_logger: Any,
    ):
        """初始化注入管理器

        参数：
            injection_manager: ContextInjectionManager 实例
            injection_logger: InjectionLogger 实例
        """
        self._injection_manager = injection_manager
        self._injection_logger = injection_logger
        # 向后兼容：部分单测/旧代码直接读取 _injections（实现细节）。
        self._injections = getattr(injection_manager, "_injections", {})

    def get_pending_injections(self, session_id: str, injection_point: Any) -> list[Any]:
        """获取待处理注入（代理到核心注入器，向后兼容）。"""
        return self._injection_manager.get_pending_injections(session_id, injection_point)

    def inject_context(
        self,
        session_id: str,
        injection_type: Any,
        content: str,
        reason: str,
        priority: int = 30,
    ) -> Any:
        """向会话注入上下文（通用方法）

        根据注入类型自动映射到对应的注入点：
        - WARNING → PRE_THINKING
        - INTERVENTION → INTERVENTION
        - 其他类型 → PRE_LOOP（默认）

        参数：
            session_id: 会话 ID
            injection_type: 注入类型（InjectionType 枚举或字符串）
            content: 注入内容
            reason: 注入原因
            priority: 优先级（默认30）

        返回：
            创建的 ContextInjection 实例
        """
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        # Codex Fix: 规范化类型输入（支持字符串值）
        if isinstance(injection_type, str):
            try:
                injection_type = InjectionType(injection_type)
            except ValueError:
                injection_type = InjectionType.SUPPLEMENT  # 默认兜底

        # 根据类型确定注入点
        injection_point = InjectionPoint.PRE_LOOP  # 默认
        if injection_type == InjectionType.WARNING:
            injection_point = InjectionPoint.PRE_THINKING
        elif injection_type == InjectionType.INTERVENTION:
            injection_point = InjectionPoint.INTERVENTION

        # 创建注入对象
        injection = ContextInjection(
            session_id=session_id,
            injection_type=injection_type,
            injection_point=injection_point,
            content=content,
            source="coordinator",
            reason=reason,
            priority=priority,
        )

        # 添加到注入管理器
        self._injection_manager.add_injection(injection)
        return injection

    def add_injection(self, injection: Any) -> None:
        """添加注入（低级方法，向后兼容）

        直接添加已创建的 ContextInjection 实例。
        用于需要自定义注入点或其他高级场景。

        参数：
            injection: ContextInjection 实例
        """
        self._injection_manager.add_injection(injection)

    def inject_warning(
        self,
        session_id: str,
        warning_message: str | None = None,
        rule_id: str | None = None,
        content: str | None = None,
        source: str = "coordinator",
        reason: str | None = None,
    ) -> Any:
        """注入警告信息

        当规则违反或检测到风险时调用。

        参数：
            session_id: 会话 ID
            warning_message: 警告消息（可选，向后兼容）
            rule_id: 触发警告的规则 ID（可选）
            content: 警告内容（兼容旧接口：传 content=...）
            source: 来源（可选）
            reason: 原因（可选，默认由 rule_id 推导）

        返回：
            创建的 ContextInjection 实例
        """
        if warning_message is None:
            warning_message = content
        if not warning_message:
            warning_message = ""

        if reason is None:
            reason = f"规则 {rule_id} 触发" if rule_id else "安全检测"
        return self._injection_manager.inject_warning(
            session_id=session_id,
            content=warning_message,
            source=source,
            reason=reason,
        )

    def inject_intervention(
        self,
        session_id: str,
        intervention_message: str | None = None,
        reason: str = "需要干预",
        content: str | None = None,
        source: str = "coordinator",
    ) -> Any:
        """注入干预指令

        当需要暂停或干预执行时调用。

        参数：
            session_id: 会话 ID
            intervention_message: 干预消息（可选，向后兼容）
            reason: 干预原因
            content: 干预内容（兼容旧接口：传 content=...）
            source: 来源（可选）

        返回：
            创建的 ContextInjection 实例
        """
        if intervention_message is None:
            intervention_message = content
        if not intervention_message:
            intervention_message = ""

        return self._injection_manager.inject_intervention(
            session_id=session_id,
            content=intervention_message,
            source=source,
            reason=reason,
        )

    def inject_memory(
        self,
        session_id: str,
        memory_content: str | None = None,
        relevance_score: float = 0.0,
        content: str | None = None,
        source: str = "memory_system",
    ) -> Any:
        """注入长期记忆

        参数：
            session_id: 会话 ID
            memory_content: 记忆内容（可选，向后兼容）
            relevance_score: 相关性分数
            content: 记忆内容（兼容旧接口：传 content=...）
            source: 来源（可选）

        返回：
            创建的 ContextInjection 实例
        """
        if memory_content is None:
            memory_content = content
        if not memory_content:
            memory_content = ""

        return self._injection_manager.inject_memory(
            session_id=session_id,
            content=memory_content,
            source=source,
            relevance_score=relevance_score,
        )

    def inject_observation(
        self,
        session_id: str,
        observation: str | None = None,
        source: str = "monitor",
        content: str | None = None,
    ) -> Any:
        """注入观察信息

        参数：
            session_id: 会话 ID
            observation: 观察内容（可选，向后兼容）
            source: 来源（默认"monitor"）
            content: 观察内容（兼容旧接口：传 content=...）

        返回：
            创建的 ContextInjection 实例
        """
        if observation is None:
            observation = content
        if not observation:
            observation = ""

        return self._injection_manager.inject_observation(
            session_id=session_id,
            content=observation,
            source=source,
        )

    def get_injection_logs(self) -> list[dict[str, Any]]:
        """获取所有注入日志

        返回：
            注入日志列表
        """
        return self._injection_logger.get_logs()

    def get_injection_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """获取指定会话的注入日志

        参数：
            session_id: 会话 ID

        返回：
            该会话的注入日志列表
        """
        return self._injection_logger.get_logs_by_session(session_id)

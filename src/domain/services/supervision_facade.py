"""监督模块 Facade

Phase 34.13: 从 CoordinatorAgent 提取监督逻辑到独立 Facade

职责：
- 集中管理所有监督功能（上下文监督、保存请求监督、决策链监督）
- 执行干预动作（WARNING/REPLACE/TERMINATE）
- 输入检查与策略管理
- 监督日志记录与查询
- 暴露 SupervisionCoordinator 子模块别名

设计模式：
- Facade Pattern：包装 SupervisionModule、SupervisionLogger、SupervisionCoordinator
- Delegation Pattern：CoordinatorAgent 委托给 Facade

依赖：
- SupervisionModule (分析器)
- SupervisionLogger (日志记录器)
- SupervisionCoordinator (协调器，提供 conversation_supervision/strategy_repository/efficiency_monitor)
- ContextInjectionManager (用于执行干预)
- UnifiedLogCollector (审计日志)

版本：
- 提取时间: 2025-12-11
- 来源: CoordinatorAgent Phase 34.3 (lines 966-3979)
"""

from typing import Any


class SupervisionFacade:
    """监督模块 Facade

    集中管理监督相关操作，包括：
    - 三类监督分析：上下文/保存请求/决策链
    - 干预执行：WARNING/REPLACE/TERMINATE
    - 输入检查与策略管理
    - 监督日志查询

    属性：
        _supervision_module: 核心监督分析器
        _supervision_logger: 监督日志记录器
        _supervision_coordinator: 监督协调器
        _context_injection_manager: 上下文注入管理器
        _log_collector: 审计日志收集器
        conversation_supervision: 对话监督子模块（别名）
        strategy_repository: 策略仓库（别名）
        efficiency_monitor: 效率监控器（别名）
    """

    def __init__(
        self,
        supervision_module: Any,
        supervision_logger: Any,
        supervision_coordinator: Any,
        context_injection_manager: Any,
        log_collector: Any,
    ):
        """初始化监督 Facade

        参数：
            supervision_module: SupervisionModule 实例
            supervision_logger: SupervisionLogger 实例
            supervision_coordinator: SupervisionCoordinator 实例
            context_injection_manager: ContextInjectionManager 实例
            log_collector: UnifiedLogCollector 实例
        """
        self._supervision_module = supervision_module
        self._supervision_logger = supervision_logger
        self._supervision_coordinator = supervision_coordinator
        self._context_injection_manager = context_injection_manager
        self._log_collector = log_collector

        # 暴露 SupervisionCoordinator 的子模块别名（向后兼容）
        self.conversation_supervision = supervision_coordinator.conversation_supervision
        self.strategy_repository = supervision_coordinator.strategy_repository
        self.efficiency_monitor = supervision_coordinator.efficiency_monitor

    # ==================== 三类监督分析 ====================

    def supervise_context(self, context: dict[str, Any]) -> list[Any]:
        """监督上下文

        将上下文交给 SupervisionModule 进行分析。

        参数：
            context: 上下文字典

        返回：
            触发的 SupervisionInfo 列表
        """
        return self._supervision_module.analyze_context(context)

    def supervise_save_request(self, save_request: dict[str, Any]) -> list[Any]:
        """监督保存请求

        将保存请求交给 SupervisionModule 进行分析。

        参数：
            save_request: 保存请求字典

        返回：
            触发的 SupervisionInfo 列表
        """
        return self._supervision_module.analyze_save_request(save_request)

    def supervise_decision_chain(
        self, decisions: list[dict[str, Any]], session_id: str
    ) -> list[Any]:
        """监督决策链

        将决策链交给 SupervisionModule 进行质量分析。

        参数：
            decisions: 决策链列表
            session_id: 会话 ID

        返回：
            触发的 SupervisionInfo 列表
        """
        return self._supervision_module.analyze_decision_chain(decisions, session_id)

    # ==================== 干预执行 ====================

    def execute_intervention(
        self, supervision_info: Any
    ) -> dict[str, Any]:  # supervision_info 是 SupervisionInfo
        """执行干预动作

        根据 SupervisionInfo 的 action 类型执行相应的干预：
        - WARNING: 注入警告消息
        - REPLACE: 替换内容（创建 SUPPLEMENT 注入）
        - TERMINATE: 终止任务（注入干预消息）

        参数：
            supervision_info: SupervisionInfo 实例

        返回：
            干预结果字典，包含 success、action、intervention_type 等信息
        """
        from src.domain.services.supervision_module import SupervisionAction

        action = supervision_info.action
        session_id = supervision_info.session_id
        content = supervision_info.content
        trigger_condition = supervision_info.trigger_condition

        # 构建返回结果
        result = {"success": True, "action": action.value}

        # 根据 action 类型执行不同的干预
        if action == SupervisionAction.WARNING:
            # 注入警告
            self._context_injection_manager.inject_warning(
                session_id=session_id,
                warning_message=content,
                rule_id=None,
            )
            status = "warning_injected"
            result["intervention_type"] = status

        elif action == SupervisionAction.REPLACE:
            # 替换内容：创建 SUPPLEMENT 注入
            injection = self._create_supplement_injection(session_id, content, trigger_condition)
            self._context_injection_manager.add_injection(injection)
            status = "content_replaced"
            result["intervention_type"] = status
            result["replacement"] = content

        elif action == SupervisionAction.TERMINATE:
            # 终止任务：注入干预消息
            self._context_injection_manager.inject_intervention(
                session_id=session_id,
                intervention_message=content,
                reason=trigger_condition,
            )
            status = "task_terminated"
            result["intervention_type"] = status

        else:
            # 未知类型，默认记录警告
            status = "unknown_action"
            result["intervention_type"] = status

        # 记录监督日志
        self._supervision_logger.log_intervention(supervision_info, status)

        # 记录审计日志
        self._log_collector.log(
            level="warning",
            message=f"Supervision intervention executed: {action.value}",
            metadata={
                "session_id": session_id,
                "action_type": action.value,
                "reason": trigger_condition,
                "status": status,
            },
        )

        return result

    def _create_supplement_injection(self, session_id: str, content: str, reason: str) -> Any:
        """创建补充型注入（SUPPLEMENT, PRE_THINKING）

        参数：
            session_id: 会话 ID
            content: 补充内容
            reason: 注入原因

        返回：
            ContextInjection 实例
        """
        from src.domain.services.context_injection import (
            ContextInjection,
            InjectionPoint,
            InjectionType,
        )

        return ContextInjection(
            session_id=session_id,
            injection_type=InjectionType.SUPPLEMENT,
            injection_point=InjectionPoint.PRE_THINKING,
            content=content,
            source="coordinator",
            reason=reason,
            priority=40,  # 监督模块优先级
        )

    # ==================== 日志查询 ====================

    def get_supervision_logs(self) -> list[dict[str, Any]]:
        """获取所有监督日志

        返回：
            监督日志列表
        """
        return self._supervision_logger.get_logs()

    def get_supervision_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """获取指定会话的监督日志

        参数：
            session_id: 会话 ID

        返回：
            该会话的监督日志列表
        """
        return self._supervision_logger.get_logs_by_session(session_id)

    # ==================== 输入检查与策略管理 ====================

    def supervise_input(self, text: str, session_id: str | None = None) -> dict[str, Any]:
        """监督用户输入

        使用 conversation_supervision.check_all 检查用户输入，
        如果发现 issues，记录干预事件。

        参数：
            text: 用户输入文本
            session_id: 会话 ID（可选，仅用于记录干预事件）

        返回：
            检查结果 {"passed": bool, "issues": list, "action": str}
        """
        from src.domain.services.supervision import ComprehensiveCheckResult

        result: ComprehensiveCheckResult = self.conversation_supervision.check_all(text)

        # 记录日志
        if result.passed:
            self._log_collector.log(
                level="debug",
                message="输入检查通过",
                metadata={"text_length": len(text)},
            )
        else:
            self._log_collector.log(
                level="warning",
                message=f"输入检查发现 {len(result.issues)} 个问题",
                metadata={
                    "text_length": len(text),
                    "issues": [issue.category for issue in result.issues],
                    "action": result.action,
                },
            )
            # 如果提供了 session_id，记录干预事件
            if session_id:
                for issue in result.issues:
                    self._supervision_coordinator.record_intervention(
                        intervention_type=issue.category,
                        reason=issue.message,
                        source="conversation_supervision",
                        target_id="user_input",
                        severity=issue.severity,
                    )

        return {
            "passed": result.passed,
            "issues": [
                {
                    "detected": issue.detected,
                    "category": issue.category,
                    "severity": issue.severity,
                    "message": issue.message,
                }
                for issue in result.issues
            ],
            "action": result.action,
        }

    def add_supervision_strategy(
        self,
        name: str,
        trigger_conditions: list[str],
        action: str,
        priority: int = 10,
        **kwargs: Any,
    ) -> str:
        """添加监督策略

        通过 strategy_repository 注册新的监督策略。

        参数：
            name: 策略名称
            trigger_conditions: 触发条件列表 (如 ["bias", "harmful"])
            action: 动作类型 (warn/block/terminate)
            priority: 优先级 (数字越小优先级越高)
            **kwargs: 额外配置

        返回：
            策略 ID
        """
        strategy_id = self.strategy_repository.register(
            name=name,
            trigger_conditions=trigger_conditions,
            action=action,
            priority=priority,
            **kwargs,
        )

        # 记录 info 日志
        self._log_collector.log(
            level="info",
            message=f"添加监督策略: {name}",
            metadata={
                "strategy_id": strategy_id,
                "trigger_conditions": trigger_conditions,
                "action": action,
            },
        )

        return strategy_id

    def get_intervention_events(self) -> list[dict[str, Any]]:
        """获取干预事件历史

        拉取并格式化干预事件。

        返回：
            干预事件列表
        """
        events = self._supervision_coordinator.get_intervention_events()

        # 格式化事件
        formatted_events = [
            {
                "intervention_type": e.intervention_type,
                "reason": e.reason,
                "source": e.source,
                "target_id": e.target_id,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in events
        ]

        return formatted_events

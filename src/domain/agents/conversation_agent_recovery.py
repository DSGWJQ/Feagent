"""ConversationAgent recovery module.

This module extracts error recovery and user-decision handling concerns out of
`src/domain/agents/conversation_agent.py` (P1-6 Phase 4).

Scope:
- Feedback listening from Coordinator (WorkflowAdjustmentRequestedEvent / NodeFailureHandledEvent)
- Pending feedback queue management (sync + async)
- Error recovery decision generation based on feedbacks
- User-facing error formatting and user decision handling
- Emitting error / recovery completion events

Design principles:
- Keep `ConversationAgent` public API and behavior 100% backward compatible
- Use a Mixin to avoid circular imports and keep `conversation_agent.py` as the stable entry point
- Depend only on minimal host attributes/methods (documented below)
- Follow Phase 2 lock conventions: protect shared mutable state with `_state_lock`
- Pure move (no logic changes): this file is a verbatim relocation of existing implementations

Host contract (expected on the concrete ConversationAgent):
- llm: ConversationAgentLLM-compatible object (optional plan_error_recovery method)
- event_bus: EventBus | None
- session_context: SessionContext
- _state_lock: asyncio.Lock (from ConversationAgentStateMixin)
- get_context_for_reasoning(): returns dict[str, Any]
- _stage_decision_record(record: dict): stage decision for batch commit
- _flush_staged_state(): flush staged decisions to session_context
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.agents.conversation_agent_models import Decision, DecisionType

if TYPE_CHECKING:
    import asyncio

    from src.domain.agents.conversation_agent_protocols import EventBusProtocol, RecoveryHost
    from src.domain.agents.error_handling import (
        FormattedError,
        UserDecision,
        UserDecisionResult,
    )
    from src.domain.services.context_manager import SessionContext


class ConversationAgentRecoveryMixin:
    """Recovery and error handling mixin for ConversationAgent (P1-6 Phase 4).

    This mixin encapsulates error recovery, feedback listening, and user
    error decision handling that was previously inline in ConversationAgent.

    Host expectations (attributes):
    - llm: May provide optional plan_error_recovery method
    - event_bus: Optional EventBus for subscribing to coordinator events
    - session_context: SessionContext for decision recording
    - _state_lock: asyncio.Lock for protecting pending_feedbacks

    Host expectations (methods):
    - get_context_for_reasoning(): Returns context dict for LLM calls
    - _stage_decision_record(record): Stage decision for batch commit
    - _flush_staged_state(): Flush staged decisions (async)

    Type contract: Host must satisfy RecoveryHost protocol (P2 improvement).
    """

    # --- Host-provided attributes (runtime expectations) ---
    # Type hint: RecoveryHost protocol (P2 improvement)
    llm: Any
    event_bus: EventBusProtocol | None
    session_context: SessionContext
    _state_lock: asyncio.Lock

    # --- Recovery-related fields (initialized by mixin init hook) ---
    pending_feedbacks: list[dict[str, Any]]
    _is_listening_feedbacks: bool

    def get_context_for_reasoning(self) -> dict[str, Any]:  # pragma: no cover
        """Get reasoning context from host.

        Must be provided by concrete ConversationAgent.
        """
        raise NotImplementedError("Host must implement get_context_for_reasoning()")

    def _stage_decision_record(self, record: dict[str, Any]) -> None:  # pragma: no cover
        """Stage decision record for batch commit.

        Must be provided by concrete ConversationAgent.
        """
        raise NotImplementedError("Host must implement _stage_decision_record()")

    async def _flush_staged_state(self) -> None:  # pragma: no cover
        """Flush staged state updates.

        Must be provided by concrete ConversationAgent.
        """
        raise NotImplementedError("Host must implement _flush_staged_state()")

    # =========================================================================
    # Initialization hook
    # =========================================================================

    def _init_recovery_mixin(self: RecoveryHost) -> None:
        """Initialize feedback listening and recovery fields.

        This must be called by the host ConversationAgent.__init__.
        """
        # Phase 13: 反馈监听字段
        self.pending_feedbacks = []
        self._is_listening_feedbacks = False

    # =========================================================================
    # Phase 13: 反馈监听与错误恢复
    # =========================================================================

    def start_feedback_listening(self: RecoveryHost) -> None:
        """开始监听协调者反馈事件

        订阅 WorkflowAdjustmentRequestedEvent 和 NodeFailureHandledEvent，
        将反馈存储到 pending_feedbacks 供 ReAct 循环使用。

        副作用：
        - 订阅两个事件类型到event_bus
        - 设置_is_listening_feedbacks为True

        异常：
            ValueError: 如果event_bus未配置
        """
        if self._is_listening_feedbacks:
            return  # Idempotent guard

        if not self.event_bus:
            raise ValueError("EventBus is required for feedback listening")

        from src.domain.services.workflow_failure_orchestrator import (
            NodeFailureHandledEvent,
            WorkflowAdjustmentRequestedEvent,
        )

        self.event_bus.subscribe(WorkflowAdjustmentRequestedEvent, self._handle_adjustment_event)
        self.event_bus.subscribe(NodeFailureHandledEvent, self._handle_failure_handled_event)

        self._is_listening_feedbacks = True

    def stop_feedback_listening(self: RecoveryHost) -> None:
        """停止监听协调者反馈事件

        副作用：
        - 从event_bus取消订阅两个事件类型
        - 设置_is_listening_feedbacks为False
        """
        if not self._is_listening_feedbacks:
            return  # Idempotent guard

        if not self.event_bus:
            return

        from src.domain.services.workflow_failure_orchestrator import (
            NodeFailureHandledEvent,
            WorkflowAdjustmentRequestedEvent,
        )

        self.event_bus.unsubscribe(WorkflowAdjustmentRequestedEvent, self._handle_adjustment_event)
        self.event_bus.unsubscribe(NodeFailureHandledEvent, self._handle_failure_handled_event)

        self._is_listening_feedbacks = False

    async def _handle_adjustment_event(self, event: Any) -> None:
        """处理工作流调整请求事件（P0-2 Phase 2: 锁保护版本）

        当Coordinator发出WorkflowAdjustmentRequestedEvent时调用。

        锁保护：
        - 使用_state_lock保护pending_feedbacks的并发追加

        参数：
            event: WorkflowAdjustmentRequestedEvent实例
        """
        async with self._state_lock:
            self.pending_feedbacks.append(
                {
                    "type": "workflow_adjustment",
                    "workflow_id": event.workflow_id,
                    "failed_node_id": event.failed_node_id,
                    "failure_reason": event.failure_reason,
                    "suggested_action": event.suggested_action,
                    "execution_context": event.execution_context,
                    "timestamp": event.timestamp,
                }
            )

    async def _handle_failure_handled_event(self, event: Any) -> None:
        """处理节点失败处理完成事件（P0-2 Phase 2: 锁保护版本）

        当Coordinator发出NodeFailureHandledEvent时调用。

        锁保护：
        - 使用_state_lock保护pending_feedbacks的并发追加

        参数：
            event: NodeFailureHandledEvent实例
        """
        async with self._state_lock:
            self.pending_feedbacks.append(
                {
                    "type": "node_failure_handled",
                    "workflow_id": event.workflow_id,
                    "node_id": event.node_id,
                    "strategy": event.strategy,
                    "success": event.success,
                    "retry_count": event.retry_count,
                    "timestamp": event.timestamp,
                }
            )

    def get_pending_feedbacks(self) -> list[dict[str, Any]]:
        """获取待处理的反馈列表

        返回反馈列表的副本，避免外部修改内部状态。

        注意：同步版本不使用锁，适用于非关键路径。
        在异步上下文中请使用get_pending_feedbacks_async。

        返回：
            反馈列表的副本
        """
        return self.pending_feedbacks.copy()

    def clear_feedbacks(self) -> None:
        """清空待处理的反馈

        注意：同步版本不使用锁，适用于非关键路径。
        在异步上下文中请使用clear_feedbacks_async。
        """
        self.pending_feedbacks.clear()

    async def get_pending_feedbacks_async(self) -> list[dict[str, Any]]:
        """获取待处理的反馈列表（异步锁保护版本，P0-2 Phase 2）

        在_state_lock保护下返回快照，避免并发修改。

        返回：
            反馈列表的副本
        """
        async with self._state_lock:
            return self.pending_feedbacks.copy()

    async def clear_feedbacks_async(self) -> None:
        """清空待处理的反馈（异步锁保护版本，P0-2 Phase 2）

        在_state_lock保护下清空，避免并发冲突。
        """
        async with self._state_lock:
            self.pending_feedbacks.clear()

    async def generate_error_recovery_decision(self) -> Decision | None:
        """生成错误恢复决策（P0-2 Phase 2: 锁保护版本）

        根据 pending_feedbacks 中的反馈信息生成恢复决策。

        锁保护：
        - 在_state_lock下读取pending_feedbacks快照
        - 使用staged机制记录决策（批量提交）

        返回：
            错误恢复决策，如果没有待处理的反馈返回 None
        """
        # 在锁内读取pending_feedbacks快照
        async with self._state_lock:
            feedbacks_snapshot = self.pending_feedbacks.copy()

        if not feedbacks_snapshot:
            return None

        # 获取最新的调整请求
        adjustment_feedbacks = [f for f in feedbacks_snapshot if f["type"] == "workflow_adjustment"]

        if not adjustment_feedbacks:
            return None

        feedback = adjustment_feedbacks[0]

        # 构建上下文
        context = self.get_context_for_reasoning()
        context["feedback"] = feedback

        # 调用 LLM 生成恢复计划（如果有 plan_error_recovery 方法）
        recovery_plan = {}
        if hasattr(self.llm, "plan_error_recovery"):
            recovery_plan = await self.llm.plan_error_recovery(context)  # type: ignore

        # 创建决策
        decision = Decision(
            type=DecisionType.ERROR_RECOVERY,
            payload={
                "failed_node_id": feedback["failed_node_id"],
                "failure_reason": feedback.get("failure_reason", ""),
                "workflow_id": feedback["workflow_id"],
                "recovery_plan": recovery_plan,
                "execution_context": feedback.get("execution_context", {}),
            },
        )

        # Phase 2: 使用staged机制记录决策（批量提交）
        self._stage_decision_record(
            {
                "id": decision.id,
                "type": decision.type.value,
                "payload": decision.payload,
                "timestamp": decision.timestamp.isoformat(),
            }
        )
        await self._flush_staged_state()

        return decision

    # =========================================================================
    # 第五步: 异常处理与重规划 (User-facing error handling)
    # =========================================================================

    def format_error_for_user(
        self, node_id: str, error: Exception, node_name: str = ""
    ) -> FormattedError:
        """将错误格式化为用户友好消息

        使用错误分类器、消息生成器和选项生成器将技术错误
        转换为用户可理解的格式。

        参数：
            node_id: 节点ID
            error: 异常实例
            node_name: 节点名称（可选，用于更友好的消息）

        返回：
            格式化的错误信息，包含消息、用户选项和分类
        """
        from src.domain.agents.error_handling import (
            ExceptionClassifier,
            FormattedError,
            UserActionOptionsGenerator,
            UserFriendlyMessageGenerator,
        )

        classifier = ExceptionClassifier()
        message_generator = UserFriendlyMessageGenerator()
        options_generator = UserActionOptionsGenerator()

        # 分类错误
        category = classifier.classify(error)

        # 生成用户友好消息
        details = f"{node_name}: {error}" if node_name else str(error)
        message = message_generator.generate(category, details)

        # 获取用户操作选项
        options = options_generator.get_options(category)

        return FormattedError(message=message, options=options, category=category)

    async def handle_user_error_decision(self, decision: UserDecision) -> UserDecisionResult:
        """处理用户的错误恢复决策

        根据用户选择的action返回相应的处理结果。

        参数：
            decision: 用户决策对象（包含action和optional_data）

        返回：
            决策处理结果（指示是否继续、是否跳过节点等）
        """
        from src.domain.agents.error_handling import UserDecisionResult

        if decision.action == "retry":
            return UserDecisionResult(
                action_taken="retry", should_continue=True, node_skipped=False
            )
        elif decision.action == "skip":
            return UserDecisionResult(action_taken="skip", should_continue=True, node_skipped=True)
        elif decision.action == "abort":
            return UserDecisionResult(
                action_taken="abort",
                should_continue=False,
                workflow_aborted=True,
            )
        elif decision.action == "provide_data":
            return UserDecisionResult(action_taken="provide_data", should_continue=True)
        else:
            return UserDecisionResult(action_taken=decision.action, should_continue=True)

    async def emit_error_event(self, node_id: str, error: Exception, recovery_action: str) -> None:
        """发布错误事件到事件总线

        将节点执行错误发布为NodeErrorEvent，供监控和日志系统订阅。

        参数：
            node_id: 节点ID
            error: 异常实例
            recovery_action: 恢复动作描述（如"retry", "skip"等）
        """
        if not self.event_bus:
            return

        from src.domain.agents.error_handling import NodeErrorEvent

        event = NodeErrorEvent(
            node_id=node_id,
            error_type=type(error).__name__,
            error_message=str(error),
            recovery_action=recovery_action,
        )

        await self.event_bus.publish(event)

    async def emit_recovery_complete_event(
        self, node_id: str, success: bool, method: str, attempts: int = 1
    ) -> None:
        """发布恢复完成事件

        将错误恢复的结果发布为RecoveryCompleteEvent，供监控系统订阅。

        参数：
            node_id: 节点ID
            success: 恢复是否成功
            method: 恢复方法（如"retry", "fallback", "user_intervention"）
            attempts: 尝试次数（默认1）
        """
        if not self.event_bus:
            return

        from src.domain.agents.error_handling import RecoveryCompleteEvent

        event = RecoveryCompleteEvent(
            node_id=node_id,
            success=success,
            recovery_method=method,
            attempts=attempts,
        )

        await self.event_bus.publish(event)

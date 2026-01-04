"""决策执行桥接器 (DecisionExecutionBridge) - Phase 8.4

业务定义：
- 桥接 ConversationAgent 的决策和 WorkflowAgent 的执行
- 订阅 DecisionMadeEvent，验证后转发给 WorkflowAgent
- 发布执行结果事件

设计原则：
- 事件驱动：通过事件总线连接各组件
- 可选验证：支持配置决策验证器
- 错误隔离：单个决策失败不影响后续处理

使用示例：
    bridge = DecisionExecutionBridge(
        event_bus=event_bus,
        decision_validator=validator,
        workflow_agent_factory=lambda: WorkflowAgent(...),
    )
    await bridge.start()
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
from src.domain.services.event_bus import Event, EventBus

logger = logging.getLogger(__name__)


# 可执行的决策类型
ACTIONABLE_DECISION_TYPES = {
    DecisionType.CREATE_NODE.value,
    DecisionType.CREATE_WORKFLOW_PLAN.value,
    DecisionType.EXECUTE_WORKFLOW.value,
    DecisionType.MODIFY_NODE.value,
}


@dataclass
class ExecutionResultEvent(Event):
    """执行结果事件

    当决策执行完成后发布此事件。

    属性：
        decision_id: 原始决策ID
        decision_type: 决策类型
        status: 执行状态 (completed, failed)
        result: 执行结果
        error: 错误信息（如果失败）
    """

    decision_id: str = ""
    decision_type: str = ""
    status: str = ""  # completed, failed
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ValidationRejectedEvent(Event):
    """验证拒绝事件

    当决策验证失败时发布此事件。

    属性：
        decision_id: 原始决策ID
        decision_type: 决策类型
        violations: 违规列表
    """

    decision_id: str = ""
    decision_type: str = ""
    violations: list[str] = field(default_factory=list)


class DecisionExecutionBridge:
    """决策执行桥接器

    职责：
    1. 订阅 DecisionMadeEvent
    2. 验证决策（如果配置了验证器）
    3. 转发给 WorkflowAgent 执行
    4. 发布执行结果事件

    使用示例：
        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            decision_validator=validator,
            workflow_agent_factory=lambda: WorkflowAgent(...),
        )
        await bridge.start()
        # ... 应用运行 ...
        await bridge.stop()
    """

    def __init__(
        self,
        event_bus: EventBus,
        decision_validator: Any | None = None,
        workflow_agent_factory: Callable[[], Any] | None = None,
        workflow_decision_handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
        | None = None,
        actionable_decision_types: set[str] | None = None,
    ):
        """初始化桥接器

        参数：
            event_bus: 事件总线
            decision_validator: 决策验证器（可选）
            workflow_agent_factory: WorkflowAgent 工厂函数（可选）
        """
        self.event_bus = event_bus
        self.decision_validator = decision_validator
        self.workflow_agent_factory = workflow_agent_factory
        self.workflow_decision_handler = workflow_decision_handler
        self._actionable_decision_types = actionable_decision_types or set(
            ACTIONABLE_DECISION_TYPES
        )
        self._handler = None
        self._running = False

    async def start(self) -> None:
        """启动桥接器，订阅决策事件"""
        if self._running:
            return

        self._handler = self._handle_decision
        self.event_bus.subscribe(DecisionMadeEvent, self._handler)
        self._running = True
        logger.info(
            "DecisionExecutionBridge started",
            extra={
                "actionable_decision_types": sorted(self._actionable_decision_types),
                "has_validator": self.decision_validator is not None,
                "has_agent_factory": self.workflow_agent_factory is not None,
                "has_decision_handler": self.workflow_decision_handler is not None,
            },
        )

    async def stop(self) -> None:
        """停止桥接器，取消订阅"""
        if not self._running:
            return

        if self._handler:
            self.event_bus.unsubscribe(DecisionMadeEvent, self._handler)
            self._handler = None
        self._running = False
        logger.info("DecisionExecutionBridge stopped")

    async def _handle_decision(self, event: Event) -> None:
        """处理决策事件

        参数：
            event: 决策事件
        """
        if not isinstance(event, DecisionMadeEvent):
            return

        decision_type = event.decision_type
        decision_id = event.decision_id
        # payload is available via event.payload when needed

        logger.debug(f"Received decision: {decision_type} ({decision_id})")

        # 检查是否是可执行的决策类型
        if decision_type not in self._actionable_decision_types:
            logger.debug(f"Ignoring non-actionable decision type: {decision_type}")
            return

        # 验证决策（如果配置了验证器）
        if self.decision_validator:
            validation_result = await self._validate_decision(event)
            if validation_result and validation_result.status.value == "rejected":
                await self._publish_rejection(event, validation_result.violations)
                return

        # 执行决策
        await self._execute_decision(event)

    async def _validate_decision(self, event: DecisionMadeEvent) -> Any:
        """验证决策

        参数：
            event: 决策事件

        返回：
            验证结果
        """
        if not self.decision_validator:
            return None

        try:
            # 构造验证请求
            from src.domain.services.decision_validator import DecisionRequest

            request = DecisionRequest(
                decision_id=event.decision_id,
                decision_type=event.decision_type,
                payload=event.payload,
                context={},
                requester="conversation_agent",
            )

            result = self.decision_validator.validate(request)
            return result
        except ImportError:
            # DecisionValidator 不可用，跳过验证
            logger.warning("DecisionValidator not available, skipping validation")
            return None
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return None

    async def _publish_rejection(self, event: DecisionMadeEvent, violations: list[str]) -> None:
        """发布验证拒绝事件

        参数：
            event: 原始决策事件
            violations: 违规列表
        """
        rejection_event = ValidationRejectedEvent(
            source="decision_execution_bridge",
            decision_id=event.decision_id,
            decision_type=event.decision_type,
            violations=violations,
        )
        await self.event_bus.publish(rejection_event)
        logger.warning(f"Decision rejected: {event.decision_id}, violations: {violations}")

    async def _execute_decision(self, event: DecisionMadeEvent) -> None:
        """执行决策

        参数：
            event: 决策事件
        """
        if self.workflow_decision_handler is None and not self.workflow_agent_factory:
            logger.warning(
                "DecisionExecutionBridge not configured (missing handler/factory), dropping decision",
                extra={"decision_type": event.decision_type, "decision_id": event.decision_id},
            )
            return

        try:
            decision_type = event.decision_type
            payload = event.payload

            decision_data = {"decision_type": decision_type, **payload}

            if self.workflow_decision_handler is not None:
                result = await self.workflow_decision_handler(decision_data)
            else:
                workflow_agent_factory = self.workflow_agent_factory
                if workflow_agent_factory is None:
                    logger.warning(
                        "DecisionExecutionBridge not configured (missing factory), dropping decision",
                        extra={
                            "decision_type": event.decision_type,
                            "decision_id": event.decision_id,
                        },
                    )
                    return
                workflow_agent = workflow_agent_factory()
                # 根据决策类型执行不同操作
                if decision_type == DecisionType.CREATE_WORKFLOW_PLAN.value:
                    # 执行工作流规划
                    result = await self._execute_workflow_plan(workflow_agent, payload)
                else:
                    # 其他决策类型使用 handle_decision
                    result = await workflow_agent.handle_decision(decision_data)

            # 发布执行结果
            await self._publish_result(event, "completed", result)

        except Exception as e:
            logger.error(f"Execution error for decision {event.decision_id}: {e}")
            await self._publish_result(event, "failed", {}, str(e))

    async def _execute_workflow_plan(
        self, workflow_agent: Any, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """执行工作流规划

        参数：
            workflow_agent: WorkflowAgent 实例
            payload: 规划数据

        返回：
            执行结果
        """
        # 尝试使用 execute_plan_from_dict 方法（payload 是 dict 格式）
        if hasattr(workflow_agent, "execute_plan_from_dict"):
            return await workflow_agent.execute_plan_from_dict(payload)

        # 回退到 handle_decision
        return await workflow_agent.handle_decision(
            {
                "decision_type": DecisionType.CREATE_WORKFLOW_PLAN.value,
                **payload,
            }
        )

    async def _publish_result(
        self,
        event: DecisionMadeEvent,
        status: str,
        result: dict[str, Any],
        error: str | None = None,
    ) -> None:
        """发布执行结果事件

        参数：
            event: 原始决策事件
            status: 执行状态
            result: 执行结果
            error: 错误信息
        """
        result_event = ExecutionResultEvent(
            source="decision_execution_bridge",
            decision_id=event.decision_id,
            decision_type=event.decision_type,
            status=status,
            result=result,
            error=error,
        )
        await self.event_bus.publish(result_event)
        logger.info(f"Execution result: {event.decision_id} -> {status}")


# 导出
__all__ = [
    "DecisionExecutionBridge",
    "ExecutionResultEvent",
    "ValidationRejectedEvent",
    "ACTIONABLE_DECISION_TYPES",
]

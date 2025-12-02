"""Agent编排器 (AgentOrchestrator) - 统一管理多Agent协作

业务定义：
- AgentOrchestrator 负责初始化和连接三个核心Agent
- 统一管理 EventBus 的订阅和中间件注册
- 提供完整的 Agent 协作链路

设计原则：
- 单一职责：只负责 Agent 的注册和连接
- 依赖注入：Agent 实例由外部传入
- 可观测性：提供状态查询和日志

核心流程：
1. ConversationAgent 发布 DecisionMadeEvent
2. CoordinatorAgent 作为中间件验证决策
3. 验证通过发布 DecisionValidatedEvent
4. WorkflowAgent 订阅并处理决策
5. WorkflowAgent 发布 NodeExecutionEvent 和 WorkflowExecutionCompletedEvent

使用示例：
    orchestrator = AgentOrchestrator(
        event_bus=event_bus,
        conversation_agent=conversation_agent,
        coordinator_agent=coordinator_agent,
        workflow_agent=workflow_agent
    )
    orchestrator.start()

    # 现在 Agent 之间可以通过事件通信
    await conversation_agent.run_async("创建一个 HTTP 节点")
"""

import logging
from dataclasses import dataclass
from typing import Any

from src.domain.agents.coordinator_agent import (
    CoordinatorAgent,
    DecisionValidatedEvent,
)
from src.domain.agents.workflow_agent import (
    NodeExecutionEvent,
    WorkflowAgent,
    WorkflowExecutionCompletedEvent,
    WorkflowExecutionStartedEvent,
)
from src.domain.services.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorStatistics:
    """编排器统计"""

    decisions_processed: int = 0
    decisions_validated: int = 0
    decisions_rejected: int = 0
    workflows_started: int = 0
    workflows_completed: int = 0
    nodes_executed: int = 0


class AgentOrchestrator:
    """Agent编排器

    职责：
    1. 连接三个Agent到EventBus
    2. 注册CoordinatorAgent作为中间件
    3. 设置WorkflowAgent订阅
    4. 提供状态监控

    使用示例：
        # 创建组件
        event_bus = EventBus()
        conversation_agent = ConversationAgent(...)
        coordinator_agent = CoordinatorAgent(...)
        workflow_agent = WorkflowAgent(...)

        # 创建编排器
        orchestrator = AgentOrchestrator(
            event_bus=event_bus,
            conversation_agent=conversation_agent,
            coordinator_agent=coordinator_agent,
            workflow_agent=workflow_agent
        )

        # 启动
        orchestrator.start()

        # 触发流程
        await conversation_agent.run_async("创建节点")

        # 查看事件日志
        print(orchestrator.get_event_log())
    """

    def __init__(
        self,
        event_bus: EventBus,
        conversation_agent: Any,  # ConversationAgent
        coordinator_agent: CoordinatorAgent,
        workflow_agent: WorkflowAgent,
    ):
        """初始化编排器

        参数：
            event_bus: 事件总线
            conversation_agent: 对话Agent
            coordinator_agent: 协调者Agent
            workflow_agent: 工作流Agent
        """
        self.event_bus = event_bus
        self.conversation_agent = conversation_agent
        self.coordinator_agent = coordinator_agent
        self.workflow_agent = workflow_agent

        self._is_running = False
        self._statistics = OrchestratorStatistics()

    def start(self) -> None:
        """启动编排器

        注册所有Agent到EventBus。
        """
        if self._is_running:
            logger.warning("Orchestrator already running")
            return

        logger.info("Starting AgentOrchestrator...")

        # 1. 注册 CoordinatorAgent 作为中间件（验证决策）
        self.event_bus.add_middleware(self.coordinator_agent.as_middleware())
        logger.info("CoordinatorAgent registered as middleware")

        # 2. 订阅 DecisionValidatedEvent -> WorkflowAgent 处理
        self.event_bus.subscribe(DecisionValidatedEvent, self._handle_decision_validated)
        logger.info("WorkflowAgent subscribed to DecisionValidatedEvent")

        # 3. 订阅执行事件（用于统计和监控）
        self.event_bus.subscribe(WorkflowExecutionStartedEvent, self._handle_workflow_started)
        self.event_bus.subscribe(WorkflowExecutionCompletedEvent, self._handle_workflow_completed)
        self.event_bus.subscribe(NodeExecutionEvent, self._handle_node_execution)

        # 4. 确保 ConversationAgent 有 event_bus 引用
        if hasattr(self.conversation_agent, "event_bus"):
            self.conversation_agent.event_bus = self.event_bus
            logger.info("ConversationAgent connected to EventBus")

        self._is_running = True
        logger.info("AgentOrchestrator started successfully")

    def stop(self) -> None:
        """停止编排器

        取消所有订阅。
        """
        if not self._is_running:
            return

        logger.info("Stopping AgentOrchestrator...")

        # 取消订阅
        self.event_bus.unsubscribe(DecisionValidatedEvent, self._handle_decision_validated)
        self.event_bus.unsubscribe(WorkflowExecutionStartedEvent, self._handle_workflow_started)
        self.event_bus.unsubscribe(WorkflowExecutionCompletedEvent, self._handle_workflow_completed)
        self.event_bus.unsubscribe(NodeExecutionEvent, self._handle_node_execution)

        self._is_running = False
        logger.info("AgentOrchestrator stopped")

    async def _handle_decision_validated(self, event: DecisionValidatedEvent) -> None:
        """处理验证通过的决策

        将决策转发给 WorkflowAgent。
        """
        logger.info(
            f"Decision validated: type={event.decision_type}, id={event.original_decision_id}"
        )

        self._statistics.decisions_validated += 1

        # 构建决策数据
        decision_data = {
            "decision_type": event.decision_type,
            **event.payload,
        }

        # 转发给 WorkflowAgent
        try:
            result = await self.workflow_agent.handle_decision(decision_data)
            logger.info(f"WorkflowAgent handled decision: {result}")
        except Exception as e:
            logger.error(f"WorkflowAgent failed to handle decision: {e}")

    async def _handle_workflow_started(self, event: WorkflowExecutionStartedEvent) -> None:
        """处理工作流开始事件"""
        logger.info(f"Workflow started: workflow_id={event.workflow_id}, nodes={event.node_count}")
        self._statistics.workflows_started += 1

    async def _handle_workflow_completed(self, event: WorkflowExecutionCompletedEvent) -> None:
        """处理工作流完成事件"""
        logger.info(f"Workflow completed: workflow_id={event.workflow_id}, status={event.status}")
        self._statistics.workflows_completed += 1

        # 将结果同步给 ConversationAgent（反向同步）
        if hasattr(self.conversation_agent, "receive_execution_result"):
            result_data = {
                "workflow_id": event.workflow_id,
                "status": event.status,
                "result": event.result,
            }
            await self.conversation_agent.receive_execution_result(result_data)

    async def _handle_node_execution(self, event: NodeExecutionEvent) -> None:
        """处理节点执行事件"""
        logger.debug(f"Node execution: node_id={event.node_id}, status={event.status}")
        if event.status in ("completed", "failed"):
            self._statistics.nodes_executed += 1

        # 将状态同步给 ConversationAgent
        if hasattr(self.conversation_agent, "receive_node_status"):
            status_data = {
                "node_id": event.node_id,
                "node_type": event.node_type,
                "status": event.status,
                "result": event.result,
            }
            await self.conversation_agent.receive_node_status(status_data)

    def get_statistics(self) -> dict[str, int]:
        """获取统计信息"""
        return {
            "decisions_validated": self._statistics.decisions_validated,
            "decisions_rejected": self._statistics.decisions_rejected,
            "workflows_started": self._statistics.workflows_started,
            "workflows_completed": self._statistics.workflows_completed,
            "nodes_executed": self._statistics.nodes_executed,
        }

    def get_event_log(self) -> list[Any]:
        """获取事件日志"""
        return self.event_bus.event_log

    def get_status(self) -> dict[str, Any]:
        """获取编排器状态"""
        return {
            "is_running": self._is_running,
            "statistics": self.get_statistics(),
            "event_count": len(self.event_bus.event_log),
            "coordinator_stats": self.coordinator_agent.get_statistics(),
        }


# 导出
__all__ = [
    "AgentOrchestrator",
    "OrchestratorStatistics",
]

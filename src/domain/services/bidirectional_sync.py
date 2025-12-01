"""双向同步协议

实现对话Agent和工作流Agent之间的双向通信。

组件：
- BidirectionalSyncProtocol: 双向同步协议

功能：
- 前向同步：将验证通过的决策转发给工作流Agent
- 反向同步：将执行结果同步回对话Agent
- 状态同步：节点状态变化通知

设计原则：
- 事件驱动：通过EventBus订阅和发布事件
- 解耦：Agent之间不直接调用
- 可观测：提供统计和状态查询

"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class SyncStatistics:
    """同步统计"""

    decisions_forwarded: int = 0
    results_synced: int = 0
    node_status_synced: int = 0


class BidirectionalSyncProtocol:
    """双向同步协议

    桥接ConversationAgent和WorkflowAgent，实现双向通信。

    使用示例：
        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=conversation_agent,
            workflow_agent=workflow_agent
        )
        protocol.start()

        # 现在决策会自动转发，结果会自动同步
    """

    def __init__(
        self, event_bus: Any, conversation_agent: Any, workflow_agent: Any, buffer_size: int = 10
    ):
        """初始化

        参数：
            event_bus: 事件总线
            conversation_agent: 对话Agent
            workflow_agent: 工作流Agent
            buffer_size: 事件缓冲区大小
        """
        self.event_bus = event_bus
        self.conversation_agent = conversation_agent
        self.workflow_agent = workflow_agent
        self.buffer_size = buffer_size

        self._is_running = False
        self._statistics = SyncStatistics()
        self._node_event_buffer: list[Any] = []

        # 存储订阅句柄，用于取消订阅
        self._subscriptions: list[Callable] = []

    def start(self) -> None:
        """启动同步协议

        订阅相关事件并开始处理。
        """
        if self._is_running:
            return

        self._is_running = True

        # 延迟导入避免循环依赖
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
        )

        # 订阅决策验证事件（前向同步）
        self.event_bus.subscribe(DecisionValidatedEvent, self._handle_decision_validated)

        # 订阅工作流完成事件（反向同步）
        self.event_bus.subscribe(WorkflowExecutionCompletedEvent, self._handle_workflow_completed)

        # 订阅节点执行事件（状态同步）
        self.event_bus.subscribe(NodeExecutionEvent, self._handle_node_execution)

    def stop(self) -> None:
        """停止同步协议

        取消订阅并停止处理。
        """
        if not self._is_running:
            return

        self._is_running = False

        # 延迟导入
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
        )

        # 取消订阅
        self.event_bus.unsubscribe(DecisionValidatedEvent, self._handle_decision_validated)
        self.event_bus.unsubscribe(WorkflowExecutionCompletedEvent, self._handle_workflow_completed)
        self.event_bus.unsubscribe(NodeExecutionEvent, self._handle_node_execution)

    async def _handle_decision_validated(self, event: Any) -> None:
        """处理验证通过的决策（前向同步）

        将决策转发给工作流Agent执行。

        参数：
            event: DecisionValidatedEvent
        """
        if not self._is_running:
            return

        # 构建决策数据
        decision_data = {"decision_type": event.decision_type, **event.payload}

        # 转发给工作流Agent
        await self.workflow_agent.handle_decision(decision_data)

        # 更新统计
        self._statistics.decisions_forwarded += 1

    async def _handle_workflow_completed(self, event: Any) -> None:
        """处理工作流完成事件（反向同步）

        将执行结果同步给对话Agent。

        参数：
            event: WorkflowExecutionCompletedEvent
        """
        if not self._is_running:
            return

        # 构建结果数据
        result_data = {
            "workflow_id": event.workflow_id,
            "status": event.status,
            "result": event.result,
        }

        # 同步给对话Agent
        await self.conversation_agent.receive_execution_result(result_data)

        # 更新统计
        self._statistics.results_synced += 1

    async def _handle_node_execution(self, event: Any) -> None:
        """处理节点执行事件（状态同步）

        将节点状态同步给对话Agent。

        参数：
            event: NodeExecutionEvent
        """
        if not self._is_running:
            return

        # 构建状态数据
        status_data = {
            "node_id": event.node_id,
            "node_type": event.node_type,
            "status": event.status,
            "result": event.result,
        }

        # 同步给对话Agent
        await self.conversation_agent.receive_node_status(status_data)

        # 更新统计
        self._statistics.node_status_synced += 1

    def get_statistics(self) -> dict[str, int]:
        """获取同步统计

        返回：
            统计数据字典
        """
        return {
            "decisions_forwarded": self._statistics.decisions_forwarded,
            "results_synced": self._statistics.results_synced,
            "node_status_synced": self._statistics.node_status_synced,
        }

    def get_status(self) -> dict[str, Any]:
        """获取同步状态

        返回：
            状态字典
        """
        return {
            "is_running": self._is_running,
            "buffer_size": self.buffer_size,
            "statistics": self.get_statistics(),
        }

    def reset_statistics(self) -> None:
        """重置统计"""
        self._statistics = SyncStatistics()


# 导出
__all__ = [
    "BidirectionalSyncProtocol",
]

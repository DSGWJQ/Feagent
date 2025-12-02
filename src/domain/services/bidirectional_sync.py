"""双向同步协议

实现对话Agent和工作流Agent之间的双向通信。

组件：
- BidirectionalSyncProtocol: 双向同步协议（决策→工作流，结果→对话）
- BidirectionalSyncService: 双向同步服务（画布→对话，阶段3新增）
- CanvasChangeEvent: 画布变更事件
- CanvasState: 画布状态

功能：
- 前向同步：将验证通过的决策转发给工作流Agent
- 反向同步：将执行结果同步回对话Agent
- 状态同步：节点状态变化通知
- 画布同步：将画布变更同步到对话Agent上下文（阶段3新增）

设计原则：
- 事件驱动：通过EventBus订阅和发布事件
- 解耦：Agent之间不直接调用
- 可观测：提供统计和状态查询
- 单一数据源：画布为Master（阶段3）

"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event

# ==================== 阶段 3：画布→对话同步 ====================


class CanvasChangeType(str, Enum):
    """画布变更类型"""

    NODE_ADDED = "node_added"
    NODE_UPDATED = "node_updated"
    NODE_DELETED = "node_deleted"
    NODE_MOVED = "node_moved"
    EDGE_ADDED = "edge_added"
    EDGE_DELETED = "edge_deleted"


@dataclass
class CanvasChangeEvent(Event):
    """画布变更事件

    当用户在前端画布上进行操作时，通过 WebSocket 发送此事件到后端。
    BidirectionalSyncService 订阅此事件并更新画布状态和对话Agent上下文。

    属性：
        workflow_id: 工作流ID
        change_type: 变更类型
        change_data: 变更数据（节点/边的详细信息）
        client_id: 客户端ID（用于排除回显）
        version: 版本号（用于冲突检测）
        timestamp: 时间戳
    """

    workflow_id: str = ""
    change_type: str = ""
    change_data: dict[str, Any] = field(default_factory=dict)
    client_id: str = ""
    version: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SyncResult:
    """同步结果

    属性：
        success: 是否成功
        conflict: 是否有冲突
        current_version: 当前版本号
        message: 消息
    """

    success: bool = True
    conflict: bool = False
    current_version: int = 0
    message: str = ""


class CanvasState:
    """画布状态

    存储工作流的画布状态，包括节点和边。
    作为单一数据源（Master）。

    使用示例：
        state = CanvasState(workflow_id="wf_123")
        state.add_node(node_id="node_1", node_type="HTTP", config={...})
        state.add_edge(edge_id="edge_1", source_id="node_1", target_id="node_2")
    """

    def __init__(self, workflow_id: str):
        """初始化画布状态

        参数：
            workflow_id: 工作流ID
        """
        self.workflow_id = workflow_id
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, dict[str, Any]] = {}
        self.version: int = 0

    def add_node(
        self,
        node_id: str,
        node_type: str,
        position: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """添加节点

        参数：
            node_id: 节点ID
            node_type: 节点类型
            position: 位置
            config: 配置
        """
        self.nodes[node_id] = {
            "node_id": node_id,
            "node_type": node_type,
            "position": position or {"x": 0, "y": 0},
            "config": config or {},
        }
        self.version += 1

    def update_node(self, node_id: str, changes: dict[str, Any]) -> None:
        """更新节点

        参数：
            node_id: 节点ID
            changes: 变更内容
        """
        if node_id in self.nodes:
            # 深度合并变更
            for key, value in changes.items():
                if isinstance(value, dict) and key in self.nodes[node_id]:
                    self.nodes[node_id][key].update(value)
                else:
                    self.nodes[node_id][key] = value
            self.version += 1

    def delete_node(self, node_id: str) -> None:
        """删除节点

        参数：
            node_id: 节点ID
        """
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.version += 1

    def move_node(self, node_id: str, position: dict[str, Any]) -> None:
        """移动节点

        参数：
            node_id: 节点ID
            position: 新位置
        """
        if node_id in self.nodes:
            self.nodes[node_id]["position"] = position
            self.version += 1

    def add_edge(self, edge_id: str, source_id: str, target_id: str) -> None:
        """添加边

        参数：
            edge_id: 边ID
            source_id: 源节点ID
            target_id: 目标节点ID
        """
        self.edges[edge_id] = {
            "edge_id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
        }
        self.version += 1

    def delete_edge(self, edge_id: str) -> None:
        """删除边

        参数：
            edge_id: 边ID
        """
        if edge_id in self.edges:
            del self.edges[edge_id]
            self.version += 1

    def to_dict(self) -> dict[str, Any]:
        """转换为字典

        返回：
            状态字典
        """
        return {
            "workflow_id": self.workflow_id,
            "nodes": self.nodes.copy(),
            "edges": self.edges.copy(),
            "version": self.version,
        }


class BidirectionalSyncService:
    """双向同步服务（阶段3新增）

    处理画布→对话的反向同步。

    职责：
    1. 订阅 CanvasChangeEvent
    2. 维护画布状态（CanvasState）
    3. 更新 ConversationAgent 的 SessionContext.canvas_state
    4. 处理冲突检测

    使用示例：
        service = BidirectionalSyncService(event_bus=event_bus)
        service.register_conversation_agent("wf_123", conversation_agent)

        # 当画布变更事件发布时，自动更新对话Agent上下文
    """

    def __init__(self, event_bus: Any):
        """初始化

        参数：
            event_bus: 事件总线
        """
        self.event_bus = event_bus
        self._canvas_states: dict[str, CanvasState] = {}
        self._conversation_agents: dict[str, Any] = {}
        self._canvas_synchronizer: Any | None = None

        # 订阅画布变更事件
        self.event_bus.subscribe(CanvasChangeEvent, self._handle_canvas_change)

    def register_conversation_agent(self, workflow_id: str, agent: Any) -> None:
        """注册 ConversationAgent

        参数：
            workflow_id: 工作流ID
            agent: ConversationAgent 实例
        """
        self._conversation_agents[workflow_id] = agent

    def set_canvas_synchronizer(self, synchronizer: Any) -> None:
        """设置 CanvasSynchronizer

        参数：
            synchronizer: CanvasSynchronizer 实例
        """
        self._canvas_synchronizer = synchronizer

    def get_canvas_state(self, workflow_id: str) -> CanvasState:
        """获取画布状态

        参数：
            workflow_id: 工作流ID

        返回：
            画布状态
        """
        if workflow_id not in self._canvas_states:
            self._canvas_states[workflow_id] = CanvasState(workflow_id)
        return self._canvas_states[workflow_id]

    async def _handle_canvas_change(self, event: CanvasChangeEvent) -> None:
        """处理画布变更事件

        参数：
            event: CanvasChangeEvent
        """
        result = await self.handle_change(event)
        if not result.success:
            # 冲突或错误处理
            pass

    async def handle_change(self, event: CanvasChangeEvent) -> SyncResult:
        """处理画布变更

        参数：
            event: CanvasChangeEvent

        返回：
            SyncResult
        """
        state = self.get_canvas_state(event.workflow_id)

        # 冲突检测（基于版本号）
        # 对于 node_added 和 edge_added，不检查版本冲突
        if event.change_type not in ["node_added", "edge_added"]:
            if event.version < state.version:
                return SyncResult(
                    success=False,
                    conflict=True,
                    current_version=state.version,
                    message="版本冲突，请基于最新状态重试",
                )

        # 应用变更
        self._apply_change(state, event)

        # 更新 ConversationAgent 上下文
        await self._update_conversation_context(event.workflow_id, state)

        return SyncResult(
            success=True,
            conflict=False,
            current_version=state.version,
        )

    def _apply_change(self, state: CanvasState, event: CanvasChangeEvent) -> None:
        """应用变更到画布状态

        参数：
            state: 画布状态
            event: 变更事件
        """
        change_type = event.change_type
        data = event.change_data

        if change_type == "node_added":
            state.add_node(
                node_id=data.get("node_id", ""),
                node_type=data.get("node_type", ""),
                position=data.get("position"),
                config=data.get("config"),
            )
        elif change_type == "node_updated":
            state.update_node(
                node_id=data.get("node_id", ""),
                changes=data.get("changes", {}),
            )
        elif change_type == "node_deleted":
            state.delete_node(node_id=data.get("node_id", ""))
        elif change_type == "node_moved":
            state.move_node(
                node_id=data.get("node_id", ""),
                position=data.get("position", {}),
            )
        elif change_type == "edge_added":
            state.add_edge(
                edge_id=data.get("edge_id", ""),
                source_id=data.get("source_id", ""),
                target_id=data.get("target_id", ""),
            )
        elif change_type == "edge_deleted":
            state.delete_edge(edge_id=data.get("edge_id", ""))

    async def _update_conversation_context(self, workflow_id: str, state: CanvasState) -> None:
        """更新 ConversationAgent 上下文

        参数：
            workflow_id: 工作流ID
            state: 画布状态
        """
        agent = self._conversation_agents.get(workflow_id)
        if agent and hasattr(agent, "session_context"):
            # 更新 session_context.canvas_state
            agent.session_context.canvas_state = state.to_dict()


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
    # 阶段 1-2：决策→工作流，结果→对话
    "BidirectionalSyncProtocol",
    "SyncStatistics",
    # 阶段 3：画布→对话
    "CanvasChangeType",
    "CanvasChangeEvent",
    "CanvasState",
    "SyncResult",
    "BidirectionalSyncService",
]

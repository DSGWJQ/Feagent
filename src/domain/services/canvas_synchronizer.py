"""画布同步系统

提供工作流画布的实时同步功能。

组件：
- CanvasSynchronizer: 画布同步器

功能：
- 连接管理：管理WebSocket连接
- 状态同步：节点/边的增删改同步
- 执行状态：工作流执行状态同步
- 快照支持：画布状态快照

设计原则：
- 实时性：变化立即推送
- 解耦：与具体WebSocket实现解耦
- 容错：断开连接自动清理

"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SyncStatistics:
    """同步统计"""

    messages_sent: int = 0
    connections_count: int = 0
    errors_count: int = 0


@dataclass
class CanvasState:
    """画布状态"""

    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    execution_status: dict[str, str] = field(default_factory=dict)


class CanvasSynchronizer:
    """画布同步器

    管理WebSocket连接，同步画布状态变化到前端。

    使用示例：
        synchronizer = CanvasSynchronizer()

        # 注册连接
        await synchronizer.register_connection("workflow_1", websocket)

        # 同步节点创建
        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_123",
            node_type="LLM",
            position={"x": 100, "y": 200},
            config={}
        )
    """

    def __init__(self):
        """初始化"""
        # 连接映射：workflow_id -> [websocket, ...]
        self._connections: dict[str, list[Any]] = {}

        # 画布状态：workflow_id -> CanvasState
        self._canvas_states: dict[str, CanvasState] = {}

        # 统计
        self._statistics = SyncStatistics()

    @property
    def connections(self) -> dict[str, list[Any]]:
        """获取所有连接"""
        return self._connections

    async def register_connection(
        self, workflow_id: str, websocket: Any, send_initial_state: bool = False
    ) -> None:
        """注册WebSocket连接

        参数：
            workflow_id: 工作流ID
            websocket: WebSocket连接对象
            send_initial_state: 是否发送初始状态
        """
        if workflow_id not in self._connections:
            self._connections[workflow_id] = []

        self._connections[workflow_id].append(websocket)
        self._statistics.connections_count = sum(len(conns) for conns in self._connections.values())

        logger.debug(
            f"注册连接: workflow_id={workflow_id}, 当前连接数={len(self._connections[workflow_id])}"
        )

        # 发送初始状态
        if send_initial_state:
            snapshot = self.get_canvas_snapshot(workflow_id)
            try:
                await websocket.send_json({"type": "canvas_snapshot", "data": snapshot})
                self._statistics.messages_sent += 1
            except Exception as e:
                logger.error(f"发送初始状态失败: {e}")

    async def unregister_connection(self, workflow_id: str, websocket: Any) -> None:
        """注销WebSocket连接

        参数：
            workflow_id: 工作流ID
            websocket: WebSocket连接对象
        """
        if workflow_id in self._connections:
            if websocket in self._connections[workflow_id]:
                self._connections[workflow_id].remove(websocket)

                # 清理空列表
                if not self._connections[workflow_id]:
                    del self._connections[workflow_id]

                self._statistics.connections_count = sum(
                    len(conns) for conns in self._connections.values()
                )

                logger.debug(f"注销连接: workflow_id={workflow_id}")

    async def _broadcast(self, workflow_id: str, message: dict[str, Any]) -> None:
        """广播消息给指定工作流的所有连接

        参数：
            workflow_id: 工作流ID
            message: 要发送的消息
        """
        connections = self._connections.get(workflow_id, [])
        disconnected = []

        for ws in connections:
            try:
                await ws.send_json(message)
                self._statistics.messages_sent += 1
            except Exception as e:
                logger.warning(f"发送消息失败，连接可能已断开: {e}")
                self._statistics.errors_count += 1
                disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            await self.unregister_connection(workflow_id, ws)

    # ========== 节点同步 ==========

    async def sync_node_created(
        self,
        workflow_id: str,
        node_id: str,
        node_type: str,
        position: dict[str, float],
        config: dict[str, Any],
    ) -> None:
        """同步节点创建

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            node_type: 节点类型
            position: 节点位置 {x, y}
            config: 节点配置
        """
        await self._broadcast(
            workflow_id,
            {
                "type": "node_created",
                "data": {
                    "node_id": node_id,
                    "node_type": node_type,
                    "position": position,
                    "config": config,
                },
            },
        )

    async def sync_node_updated(
        self, workflow_id: str, node_id: str, changes: dict[str, Any]
    ) -> None:
        """同步节点更新

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            changes: 变化的字段
        """
        await self._broadcast(
            workflow_id, {"type": "node_updated", "data": {"node_id": node_id, "changes": changes}}
        )

    async def sync_node_deleted(self, workflow_id: str, node_id: str) -> None:
        """同步节点删除

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
        """
        await self._broadcast(workflow_id, {"type": "node_deleted", "data": {"node_id": node_id}})

    async def sync_node_moved(
        self, workflow_id: str, node_id: str, new_position: dict[str, float]
    ) -> None:
        """同步节点移动

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            new_position: 新位置 {x, y}
        """
        await self._broadcast(
            workflow_id,
            {"type": "node_moved", "data": {"node_id": node_id, "position": new_position}},
        )

    # ========== 边同步 ==========

    async def sync_edge_created(
        self, workflow_id: str, edge_id: str, source_id: str, target_id: str
    ) -> None:
        """同步边创建

        参数：
            workflow_id: 工作流ID
            edge_id: 边ID
            source_id: 源节点ID
            target_id: 目标节点ID
        """
        await self._broadcast(
            workflow_id,
            {
                "type": "edge_created",
                "data": {"edge_id": edge_id, "source_id": source_id, "target_id": target_id},
            },
        )

    async def sync_edge_deleted(self, workflow_id: str, edge_id: str) -> None:
        """同步边删除

        参数：
            workflow_id: 工作流ID
            edge_id: 边ID
        """
        await self._broadcast(workflow_id, {"type": "edge_deleted", "data": {"edge_id": edge_id}})

    # ========== 执行状态同步 ==========

    async def sync_execution_status(self, workflow_id: str, node_id: str, status: str) -> None:
        """同步节点执行状态

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            status: 状态 (running, completed, failed)
        """
        await self._broadcast(
            workflow_id,
            {"type": "execution_status", "data": {"node_id": node_id, "status": status}},
        )

    async def sync_workflow_started(self, workflow_id: str) -> None:
        """同步工作流开始执行

        参数：
            workflow_id: 工作流ID
        """
        await self._broadcast(
            workflow_id, {"type": "workflow_started", "data": {"workflow_id": workflow_id}}
        )

    async def sync_workflow_completed(
        self, workflow_id: str, status: str, result_summary: str | None = None
    ) -> None:
        """同步工作流执行完成

        参数：
            workflow_id: 工作流ID
            status: 完成状态 (completed, failed)
            result_summary: 结果摘要
        """
        await self._broadcast(
            workflow_id,
            {
                "type": "workflow_completed",
                "data": {
                    "workflow_id": workflow_id,
                    "status": status,
                    "result_summary": result_summary,
                },
            },
        )

    # ========== 画布状态管理 ==========

    def set_canvas_state(
        self, workflow_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> None:
        """设置画布状态

        参数：
            workflow_id: 工作流ID
            nodes: 节点列表
            edges: 边列表
        """
        self._canvas_states[workflow_id] = CanvasState(nodes=nodes, edges=edges)

    def get_canvas_snapshot(self, workflow_id: str) -> dict[str, Any]:
        """获取画布快照

        参数：
            workflow_id: 工作流ID

        返回：
            画布状态快照
        """
        state = self._canvas_states.get(workflow_id, CanvasState())
        return {
            "nodes": state.nodes,
            "edges": state.edges,
            "execution_status": state.execution_status,
        }

    # ========== EventBus集成 ==========

    def register_with_event_bus(self, event_bus: Any, workflow_id: str) -> None:
        """注册到EventBus

        参数：
            event_bus: EventBus实例
            workflow_id: 要监听的工作流ID
        """
        from src.domain.agents.workflow_agent import NodeExecutionEvent

        async def handle_node_execution(event: NodeExecutionEvent):
            await self.sync_execution_status(
                workflow_id=workflow_id, node_id=event.node_id, status=event.status
            )

        event_bus.subscribe(NodeExecutionEvent, handle_node_execution)

    # ========== 统计 ==========

    def get_statistics(self) -> dict[str, int]:
        """获取同步统计

        返回：
            统计数据字典
        """
        return {
            "total_connections": self._statistics.connections_count,
            "messages_sent": self._statistics.messages_sent,
            "errors": self._statistics.errors_count,
        }


# 导出
__all__ = [
    "CanvasSynchronizer",
]

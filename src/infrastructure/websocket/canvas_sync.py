"""WebSocket画布同步服务

提供实时画布同步功能，用于：
- 管理WebSocket连接
- 向客户端广播画布更新
- 与事件总线集成
- 支持多用户协作编辑

使用示例：
    # 创建服务
    service = CanvasSyncService(event_bus=event_bus)

    # 连接客户端
    await service.connection_manager.connect(websocket, workflow_id="wf_123")

    # 同步节点创建
    await service.sync_node_created(
        workflow_id="wf_123",
        node_id="node_1",
        node_type="llm",
        position={"x": 100, "y": 200}
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ReliableMessage:
    """可靠消息

    用于支持消息确认和重试机制。
    """

    type: str
    workflow_id: str
    data: dict[str, Any]
    message_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "type": self.type,
            "workflow_id": self.workflow_id,
            "message_id": self.message_id,
            "timestamp": self.created_at.isoformat(),
        }
        result.update(self.data)
        return result

    def is_expired(self) -> bool:
        """检查是否已达到最大重试次数"""
        return self.retry_count >= self.max_retries


class MessageAckHandler:
    """消息确认处理器

    管理待确认消息，支持重试和超时处理。
    """

    def __init__(self, ack_timeout: float = 5.0, max_retries: int = 3):
        """初始化

        参数：
            ack_timeout: ACK 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        self.pending_messages: dict[str, ReliableMessage] = {}

    def register_message(self, message: ReliableMessage) -> None:
        """注册待确认消息"""
        self.pending_messages[message.message_id] = message

    def acknowledge(self, message_id: str) -> bool:
        """确认消息

        返回：
            是否成功确认（消息存在）
        """
        if message_id in self.pending_messages:
            del self.pending_messages[message_id]
            return True
        return False

    def get_pending_messages(self, workflow_id: str) -> list["ReliableMessage"]:
        """获取指定工作流的待确认消息"""
        return [msg for msg in self.pending_messages.values() if msg.workflow_id == workflow_id]

    async def check_and_retry(
        self,
        retry_callback: Any,
        failure_callback: Any = None,
    ) -> None:
        """检查超时消息并重试

        参数：
            retry_callback: 重试回调 async def callback(message)
            failure_callback: 失败回调 def callback(message)
        """
        now = datetime.now()
        expired_ids = []

        for msg_id, msg in list(self.pending_messages.items()):
            elapsed = (now - msg.created_at).total_seconds()

            if elapsed > self.ack_timeout * (msg.retry_count + 1):
                if msg.is_expired():
                    # 达到最大重试次数
                    expired_ids.append(msg_id)
                    if failure_callback:
                        failure_callback(msg)
                else:
                    # 重试
                    msg.retry_count += 1
                    await retry_callback(msg)

        # 移除过期消息
        for msg_id in expired_ids:
            del self.pending_messages[msg_id]


@dataclass
class CanvasDiff:
    """画布状态差异

    用于表示两个画布状态之间的增量变化，减少网络传输。
    """

    added_nodes: list[dict[str, Any]]
    removed_nodes: list[str]  # 节点 ID 列表
    modified_nodes: list[dict[str, Any]]  # {"id": str, "changes": dict}
    added_edges: list[dict[str, Any]]
    removed_edges: list[str]  # 边 ID 列表

    def is_empty(self) -> bool:
        """检查是否没有变更"""
        return (
            len(self.added_nodes) == 0
            and len(self.removed_nodes) == 0
            and len(self.modified_nodes) == 0
            and len(self.added_edges) == 0
            and len(self.removed_edges) == 0
        )

    def to_messages(self, workflow_id: str) -> list[dict[str, Any]]:
        """将差异转换为 WebSocket 消息列表

        参数：
            workflow_id: 工作流 ID

        返回：
            消息列表
        """
        messages = []
        timestamp = datetime.now().isoformat()

        # 节点创建消息
        for node in self.added_nodes:
            messages.append(
                {
                    "type": "node_created",
                    "workflow_id": workflow_id,
                    "node_id": node["id"],
                    "node_type": node.get("type", "default"),
                    "position": node.get("position", {"x": 0, "y": 0}),
                    "config": node.get("data", {}),
                    "timestamp": timestamp,
                }
            )

        # 节点删除消息
        for node_id in self.removed_nodes:
            messages.append(
                {
                    "type": "node_deleted",
                    "workflow_id": workflow_id,
                    "node_id": node_id,
                    "timestamp": timestamp,
                }
            )

        # 节点更新消息
        for node_change in self.modified_nodes:
            messages.append(
                {
                    "type": "node_updated",
                    "workflow_id": workflow_id,
                    "node_id": node_change["id"],
                    "changes": node_change["changes"],
                    "timestamp": timestamp,
                }
            )

        # 边创建消息
        for edge in self.added_edges:
            messages.append(
                {
                    "type": "edge_created",
                    "workflow_id": workflow_id,
                    "edge_id": edge["id"],
                    "source_id": edge["source"],
                    "target_id": edge["target"],
                    "timestamp": timestamp,
                }
            )

        # 边删除消息
        for edge_id in self.removed_edges:
            messages.append(
                {
                    "type": "edge_deleted",
                    "workflow_id": workflow_id,
                    "edge_id": edge_id,
                    "timestamp": timestamp,
                }
            )

        return messages


@dataclass
class WebSocketClient:
    """WebSocket客户端信息"""

    websocket: Any
    workflow_id: str
    client_id: str = field(default_factory=lambda: str(uuid4()))
    connected_at: datetime = field(default_factory=datetime.now)


class ConnectionManager:
    """WebSocket连接管理器

    管理所有WebSocket连接，支持：
    - 按工作流分组
    - 广播消息
    - 连接统计
    """

    def __init__(self):
        """初始化连接管理器"""
        self._connections: list[WebSocketClient] = []
        self._workflow_clients: dict[str, set[str]] = {}
        self._sync_service: Any | None = None

    def set_sync_service(self, service: Any) -> None:
        """设置画布同步服务引用

        参数：
            service: CanvasSyncService实例
        """
        self._sync_service = service

    @property
    def active_connections(self) -> list[WebSocketClient]:
        """获取所有活跃连接"""
        return self._connections

    async def connect(
        self,
        websocket: Any,
        workflow_id: str,
        client_id: str | None = None,
        send_initial_state: bool = False,
    ) -> WebSocketClient:
        """连接客户端

        参数：
            websocket: WebSocket连接对象
            workflow_id: 工作流ID
            client_id: 客户端ID（可选）
            send_initial_state: 是否发送初始状态

        返回：
            客户端信息
        """
        await websocket.accept()

        client = WebSocketClient(
            websocket=websocket,
            workflow_id=workflow_id,
            client_id=client_id or str(uuid4()),
        )

        self._connections.append(client)

        if workflow_id not in self._workflow_clients:
            self._workflow_clients[workflow_id] = set()
        self._workflow_clients[workflow_id].add(client.client_id)

        logger.info(f"客户端连接: {client.client_id} -> 工作流 {workflow_id}")

        # 发送初始状态
        if send_initial_state and self._sync_service is not None:
            await self._sync_service.send_initial_state(websocket, workflow_id, client.client_id)

        return client

    def disconnect(self, websocket: Any) -> None:
        """断开客户端

        参数：
            websocket: WebSocket连接对象
        """
        for i, client in enumerate(self._connections):
            if client.websocket == websocket:
                # 从工作流客户端列表中移除
                if client.workflow_id in self._workflow_clients:
                    self._workflow_clients[client.workflow_id].discard(client.client_id)
                    if not self._workflow_clients[client.workflow_id]:
                        del self._workflow_clients[client.workflow_id]

                del self._connections[i]
                logger.info(f"客户端断开: {client.client_id}")
                return

    def get_connections(self, workflow_id: str) -> list[WebSocketClient]:
        """获取指定工作流的所有连接

        参数：
            workflow_id: 工作流ID

        返回：
            客户端列表
        """
        return [c for c in self._connections if c.workflow_id == workflow_id]

    def get_client_ids(self, workflow_id: str) -> list[str]:
        """获取指定工作流的所有客户端ID

        参数：
            workflow_id: 工作流ID

        返回：
            客户端ID列表
        """
        return list(self._workflow_clients.get(workflow_id, set()))

    async def broadcast(
        self,
        workflow_id: str,
        message: dict[str, Any],
        exclude_client: str | None = None,
    ) -> None:
        """向工作流广播消息

        参数：
            workflow_id: 工作流ID
            message: 消息内容
            exclude_client: 排除的客户端ID
        """
        connections = self.get_connections(workflow_id)
        disconnected = []

        for client in connections:
            if exclude_client and client.client_id == exclude_client:
                continue

            try:
                await client.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"发送消息失败: {client.client_id} - {e}")
                disconnected.append(client.websocket)

        # 移除断开的连接
        for ws in disconnected:
            self.disconnect(ws)

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        """向指定客户端发送消息

        参数：
            client_id: 客户端ID
            message: 消息内容

        返回：
            是否发送成功
        """
        for client in self._connections:
            if client.client_id == client_id:
                try:
                    await client.websocket.send_json(message)
                    return True
                except Exception as e:
                    logger.warning(f"发送消息失败: {client_id} - {e}")
                    self.disconnect(client.websocket)
                    return False
        return False

    def get_statistics(self) -> dict[str, Any]:
        """获取连接统计信息

        返回：
            统计信息字典
        """
        workflows = {}
        for client in self._connections:
            if client.workflow_id not in workflows:
                workflows[client.workflow_id] = 0
            workflows[client.workflow_id] += 1

        return {
            "total_connections": len(self._connections),
            "workflows": workflows,
        }


class CanvasSyncService:
    """画布同步服务

    提供高层API用于同步画布状态，支持：
    - 节点CRUD同步
    - 边CRUD同步
    - 执行状态同步
    - 事件总线集成
    """

    def __init__(self, event_bus: Any | None = None):
        """初始化画布同步服务

        参数：
            event_bus: 事件总线（可选）
        """
        self.connection_manager = ConnectionManager()
        self.connection_manager.set_sync_service(self)
        self.event_bus = event_bus
        self._workflow_states: dict[str, dict[str, Any]] = {}

        # 消息可靠性支持
        self.ack_handler = MessageAckHandler()
        self.received_message_ids: set[str] = set()
        self._max_received_ids = 1000  # 最大保留的已接收消息 ID 数量

        if event_bus:
            self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """设置事件处理器"""
        from src.domain.services.canvas_synchronizer import (
            NodeCreatedEvent,
            NodeExecutionCompletedEvent,
        )

        if self.event_bus is None:
            return

        self.event_bus.subscribe(NodeCreatedEvent, self._on_node_created)
        self.event_bus.subscribe(NodeExecutionCompletedEvent, self._on_node_execution_completed)

    async def _on_node_created(self, event: Any) -> None:
        """处理节点创建事件"""
        await self.sync_node_created(
            workflow_id=event.workflow_id,
            node_id=event.node_id,
            node_type=event.node_type,
        )

    async def _on_node_execution_completed(self, event: Any) -> None:
        """处理节点执行完成事件"""
        await self.sync_execution_status(
            workflow_id=event.workflow_id,
            node_id=event.node_id,
            status="completed",
            outputs=event.outputs,
        )

    def set_workflow_state(
        self,
        workflow_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        """设置工作流状态

        参数：
            workflow_id: 工作流ID
            nodes: 节点列表
            edges: 边列表
        """
        self._workflow_states[workflow_id] = {
            "nodes": nodes,
            "edges": edges,
        }

    def get_canvas_snapshot(self, workflow_id: str) -> dict[str, Any]:
        """获取画布快照

        参数：
            workflow_id: 工作流ID

        返回：
            画布状态快照
        """
        return self._workflow_states.get(workflow_id, {"nodes": [], "edges": []})

    def _calculate_diff(
        self,
        old_state: dict[str, Any],
        new_state: dict[str, Any],
    ) -> CanvasDiff:
        """计算两个状态之间的差异

        参数：
            old_state: 旧状态 {"nodes": [...], "edges": [...]}
            new_state: 新状态 {"nodes": [...], "edges": [...]}

        返回：
            CanvasDiff 对象
        """
        old_nodes = {n["id"]: n for n in old_state.get("nodes", [])}
        new_nodes = {n["id"]: n for n in new_state.get("nodes", [])}

        old_edges = {e["id"]: e for e in old_state.get("edges", [])}
        new_edges = {e["id"]: e for e in new_state.get("edges", [])}

        # 计算节点变化
        added_nodes = []
        removed_nodes = []
        modified_nodes = []

        # 新增节点
        for node_id, node in new_nodes.items():
            if node_id not in old_nodes:
                added_nodes.append(node)

        # 删除节点
        for node_id in old_nodes:
            if node_id not in new_nodes:
                removed_nodes.append(node_id)

        # 修改节点
        for node_id, new_node in new_nodes.items():
            if node_id in old_nodes:
                old_node = old_nodes[node_id]
                changes = self._compare_nodes(old_node, new_node)
                if changes:
                    modified_nodes.append({"id": node_id, "changes": changes})

        # 计算边变化
        added_edges = []
        removed_edges = []

        # 新增边
        for edge_id, edge in new_edges.items():
            if edge_id not in old_edges:
                added_edges.append(edge)

        # 删除边
        for edge_id in old_edges:
            if edge_id not in new_edges:
                removed_edges.append(edge_id)

        return CanvasDiff(
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            modified_nodes=modified_nodes,
            added_edges=added_edges,
            removed_edges=removed_edges,
        )

    def _compare_nodes(
        self,
        old_node: dict[str, Any],
        new_node: dict[str, Any],
    ) -> dict[str, Any]:
        """比较两个节点，返回变更

        参数：
            old_node: 旧节点
            new_node: 新节点

        返回：
            变更字典，如果没有变更则返回空字典
        """
        changes = {}

        # 比较位置
        old_pos = old_node.get("position", {})
        new_pos = new_node.get("position", {})
        if old_pos != new_pos:
            changes["position"] = new_pos

        # 比较数据
        old_data = old_node.get("data", {})
        new_data = new_node.get("data", {})
        if old_data != new_data:
            changes["data"] = new_data

        # 比较类型（不应该变化，但作为安全检查）
        if old_node.get("type") != new_node.get("type"):
            changes["type"] = new_node.get("type")

        return changes

    def check_and_record_message(self, message_id: str) -> bool:
        """检查并记录消息 ID（用于去重）

        参数：
            message_id: 消息 ID

        返回：
            True 如果是新消息，False 如果是重复消息
        """
        if message_id in self.received_message_ids:
            return False

        self.received_message_ids.add(message_id)

        # 清理旧的消息 ID
        if len(self.received_message_ids) > self._max_received_ids:
            # 简单策略：移除前 100 个
            to_remove = list(self.received_message_ids)[:100]
            for mid in to_remove:
                self.received_message_ids.discard(mid)

        return True

    async def handle_client_message(
        self,
        workflow_id: str,
        data: dict[str, Any],
    ) -> bool:
        """处理客户端消息

        参数：
            workflow_id: 工作流 ID
            data: 消息数据

        返回：
            是否成功处理
        """
        msg_type = data.get("type")

        if msg_type == "ack":
            # 处理 ACK
            message_id = data.get("message_id")
            if message_id:
                return self.ack_handler.acknowledge(message_id)
            return False

        return True

    async def process_incoming_message(
        self,
        workflow_id: str,
        data: dict[str, Any],
        websocket: Any,
    ) -> None:
        """处理传入消息并发送 ACK

        参数：
            workflow_id: 工作流 ID
            data: 消息数据
            websocket: WebSocket 连接
        """
        message_id = data.get("message_id")

        if message_id:
            # 发送 ACK
            ack_message = {
                "type": "ack",
                "message_id": message_id,
            }
            try:
                await websocket.send_json(ack_message)
            except Exception as e:
                logger.warning(f"发送 ACK 失败: {e}")

    async def sync_node_created(
        self,
        workflow_id: str,
        node_id: str,
        node_type: str,
        position: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """同步节点创建

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            node_type: 节点类型
            position: 节点位置
            config: 节点配置
        """
        message_id = str(uuid4())
        message = {
            "type": "node_created",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "node_type": node_type,
            "position": position or {"x": 0, "y": 0},
            "config": config or {},
            "timestamp": datetime.now().isoformat(),
            "message_id": message_id,
        }

        await self.connection_manager.broadcast(workflow_id, message)

    async def sync_node_updated(
        self,
        workflow_id: str,
        node_id: str,
        changes: dict[str, Any],
    ) -> None:
        """同步节点更新

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            changes: 变更内容
        """
        message = {
            "type": "node_updated",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "changes": changes,
            "timestamp": datetime.now().isoformat(),
        }

        await self.connection_manager.broadcast(workflow_id, message)

    async def sync_node_deleted(
        self,
        workflow_id: str,
        node_id: str,
    ) -> None:
        """同步节点删除

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
        """
        message = {
            "type": "node_deleted",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "timestamp": datetime.now().isoformat(),
        }

        await self.connection_manager.broadcast(workflow_id, message)

    async def sync_edge_created(
        self,
        workflow_id: str,
        edge_id: str,
        source_id: str,
        target_id: str,
    ) -> None:
        """同步边创建

        参数：
            workflow_id: 工作流ID
            edge_id: 边ID
            source_id: 源节点ID
            target_id: 目标节点ID
        """
        message = {
            "type": "edge_created",
            "workflow_id": workflow_id,
            "edge_id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "timestamp": datetime.now().isoformat(),
        }

        await self.connection_manager.broadcast(workflow_id, message)

    async def sync_edge_deleted(
        self,
        workflow_id: str,
        edge_id: str,
    ) -> None:
        """同步边删除

        参数：
            workflow_id: 工作流ID
            edge_id: 边ID
        """
        message = {
            "type": "edge_deleted",
            "workflow_id": workflow_id,
            "edge_id": edge_id,
            "timestamp": datetime.now().isoformat(),
        }

        await self.connection_manager.broadcast(workflow_id, message)

    async def sync_execution_status(
        self,
        workflow_id: str,
        node_id: str,
        status: str,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """同步执行状态

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            status: 状态
            outputs: 输出结果
            error: 错误信息
        """
        message = {
            "type": "execution_status",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "status": status,
            "outputs": outputs or {},
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }

        await self.connection_manager.broadcast(workflow_id, message)

    async def sync_workflow_completed(
        self,
        workflow_id: str,
        status: str,
        outputs: dict[str, Any] | None = None,
    ) -> None:
        """同步工作流完成

        参数：
            workflow_id: 工作流ID
            status: 状态
            outputs: 输出结果
        """
        message = {
            "type": "workflow_completed",
            "workflow_id": workflow_id,
            "status": status,
            "outputs": outputs or {},
            "timestamp": datetime.now().isoformat(),
        }

        await self.connection_manager.broadcast(workflow_id, message)

    async def send_initial_state(
        self,
        websocket: Any,
        workflow_id: str,
        client_id: str | None = None,
    ) -> None:
        """发送初始状态

        参数：
            websocket: WebSocket连接
            workflow_id: 工作流ID
            client_id: 客户端ID（可选）
        """
        snapshot = self.get_canvas_snapshot(workflow_id)

        message = {
            "type": "initial_state",
            "workflow_id": workflow_id,
            "nodes": snapshot["nodes"],
            "edges": snapshot["edges"],
            "timestamp": datetime.now().isoformat(),
        }

        # 如果有 client_id，添加到消息中
        if client_id:
            message["client_id"] = client_id

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"发送初始状态失败: {e}")


class CanvasSyncServiceWithInitialState(CanvasSyncService):
    """支持初始状态发送的画布同步服务

    扩展 CanvasSyncService，在连接时自动发送初始状态。
    """

    async def connect_with_initial_state(
        self,
        websocket: Any,
        workflow_id: str,
        client_id: str | None = None,
    ) -> WebSocketClient:
        """连接客户端并发送初始状态

        参数：
            websocket: WebSocket连接对象
            workflow_id: 工作流ID
            client_id: 客户端ID（可选）

        返回：
            客户端信息
        """
        client = await self.connection_manager.connect(websocket, workflow_id, client_id)
        await self.send_initial_state(websocket, workflow_id)
        return client

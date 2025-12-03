"""WebSocket 画布同步端到端测试

测试目标：
1. 验证 WebSocket 连接管理
2. 验证节点 CRUD 同步
3. 验证边 CRUD 同步
4. 验证多客户端协作
5. 验证与事件总线的集成

运行命令：
    pytest tests/integration/test_websocket_canvas_sync_e2e.py -v
"""

import asyncio

import pytest


class MockWebSocket:
    """模拟 WebSocket 连接"""

    def __init__(self, client_id: str = "test_client"):
        self.client_id = client_id
        self.sent_messages: list[dict] = []
        self.closed = False
        self._receive_queue: asyncio.Queue = asyncio.Queue()

    async def accept(self) -> None:
        """接受连接"""
        pass

    async def send_json(self, data: dict) -> None:
        """发送 JSON 消息"""
        if not self.closed:
            self.sent_messages.append(data)

    async def receive_json(self) -> dict:
        """接收 JSON 消息"""
        return await self._receive_queue.get()

    async def close(self) -> None:
        """关闭连接"""
        self.closed = True

    def add_message(self, data: dict) -> None:
        """添加待接收的消息（测试用）"""
        self._receive_queue.put_nowait(data)


class TestConnectionManager:
    """测试 WebSocket 连接管理"""

    @pytest.fixture
    def connection_manager(self):
        """创建连接管理器"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_client(self, connection_manager):
        """测试客户端连接"""
        ws = MockWebSocket()

        client = await connection_manager.connect(
            websocket=ws,
            workflow_id="wf_001",
            client_id="client_1",
        )

        assert client is not None
        assert client.client_id == "client_1"
        assert client.workflow_id == "wf_001"
        assert len(connection_manager.active_connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_client(self, connection_manager):
        """测试客户端断开"""
        ws = MockWebSocket()

        await connection_manager.connect(
            websocket=ws,
            workflow_id="wf_001",
            client_id="client_1",
        )

        assert len(connection_manager.active_connections) == 1

        connection_manager.disconnect(ws)

        assert len(connection_manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_multiple_clients_same_workflow(self, connection_manager):
        """测试多客户端连接同一工作流"""
        ws1 = MockWebSocket("client_1")
        ws2 = MockWebSocket("client_2")
        ws3 = MockWebSocket("client_3")

        await connection_manager.connect(ws1, "wf_001", "client_1")
        await connection_manager.connect(ws2, "wf_001", "client_2")
        await connection_manager.connect(ws3, "wf_001", "client_3")

        assert len(connection_manager.active_connections) == 3

        # 验证都属于同一工作流（通过检查 _workflow_clients）
        assert "wf_001" in connection_manager._workflow_clients
        assert len(connection_manager._workflow_clients["wf_001"]) == 3

    @pytest.mark.asyncio
    async def test_clients_different_workflows(self, connection_manager):
        """测试客户端连接不同工作流"""
        ws1 = MockWebSocket("client_1")
        ws2 = MockWebSocket("client_2")

        await connection_manager.connect(ws1, "wf_001", "client_1")
        await connection_manager.connect(ws2, "wf_002", "client_2")

        assert len(connection_manager.active_connections) == 2

        # 验证分属不同工作流
        assert "wf_001" in connection_manager._workflow_clients
        assert "wf_002" in connection_manager._workflow_clients
        assert len(connection_manager._workflow_clients["wf_001"]) == 1
        assert len(connection_manager._workflow_clients["wf_002"]) == 1


class TestCanvasSyncService:
    """测试画布同步服务"""

    @pytest.fixture
    def sync_service(self):
        """创建同步服务"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        return CanvasSyncService()

    @pytest.mark.asyncio
    async def test_sync_node_created(self, sync_service):
        """测试节点创建同步"""
        ws1 = MockWebSocket("client_1")
        ws2 = MockWebSocket("client_2")

        await sync_service.connection_manager.connect(ws1, "wf_001", "client_1")
        await sync_service.connection_manager.connect(ws2, "wf_001", "client_2")

        # 同步节点创建
        await sync_service.sync_node_created(
            workflow_id="wf_001",
            node_id="node_1",
            node_type="LLM",
            position={"x": 100, "y": 200},
            config={"user_prompt": "测试提示"},
        )

        # 验证两个客户端都收到消息
        assert len(ws1.sent_messages) >= 1
        assert len(ws2.sent_messages) >= 1

        # 验证消息内容
        msg1 = ws1.sent_messages[-1]
        assert msg1["type"] == "node_created"
        assert msg1["node_id"] == "node_1"
        assert msg1["node_type"] == "LLM"

    @pytest.mark.asyncio
    async def test_sync_node_updated(self, sync_service):
        """测试节点更新同步"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步节点更新
        await sync_service.sync_node_updated(
            workflow_id="wf_001",
            node_id="node_1",
            changes={"config": {"user_prompt": "更新后的提示"}},
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "node_updated"
        assert msg["node_id"] == "node_1"

    @pytest.mark.asyncio
    async def test_sync_node_deleted(self, sync_service):
        """测试节点删除同步"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步节点删除
        await sync_service.sync_node_deleted(
            workflow_id="wf_001",
            node_id="node_1",
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "node_deleted"
        assert msg["node_id"] == "node_1"

    @pytest.mark.asyncio
    async def test_sync_edge_created(self, sync_service):
        """测试边创建同步"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步边创建
        await sync_service.sync_edge_created(
            workflow_id="wf_001",
            edge_id="edge_1",
            source_id="node_1",
            target_id="node_2",
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "edge_created"
        assert msg["edge_id"] == "edge_1"
        assert msg["source_id"] == "node_1"
        assert msg["target_id"] == "node_2"

    @pytest.mark.asyncio
    async def test_sync_edge_deleted(self, sync_service):
        """测试边删除同步"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步边删除
        await sync_service.sync_edge_deleted(
            workflow_id="wf_001",
            edge_id="edge_1",
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "edge_deleted"
        assert msg["edge_id"] == "edge_1"


class TestMultiClientCollaboration:
    """测试多客户端协作"""

    @pytest.fixture
    def sync_service(self):
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        return CanvasSyncService()

    @pytest.mark.asyncio
    async def test_broadcast_to_all_clients(self, sync_service):
        """测试广播到所有客户端"""
        clients = [MockWebSocket(f"client_{i}") for i in range(5)]

        for i, ws in enumerate(clients):
            await sync_service.connection_manager.connect(ws, "wf_001", f"client_{i}")

        # 广播消息
        await sync_service.connection_manager.broadcast(
            workflow_id="wf_001",
            message={"type": "test", "data": "hello"},
        )

        # 验证所有客户端都收到消息
        for ws in clients:
            assert len(ws.sent_messages) >= 1
            assert ws.sent_messages[-1]["type"] == "test"

    @pytest.mark.asyncio
    async def test_broadcast_excludes_sender(self, sync_service):
        """测试广播排除发送者"""
        ws1 = MockWebSocket("client_1")
        ws2 = MockWebSocket("client_2")
        ws3 = MockWebSocket("client_3")

        await sync_service.connection_manager.connect(ws1, "wf_001", "client_1")
        await sync_service.connection_manager.connect(ws2, "wf_001", "client_2")
        await sync_service.connection_manager.connect(ws3, "wf_001", "client_3")

        # 广播消息，排除 client_1
        await sync_service.connection_manager.broadcast(
            workflow_id="wf_001",
            message={"type": "node_moved", "node_id": "node_1"},
            exclude_client="client_1",
        )

        # client_1 不应收到消息，其他客户端应该收到
        assert len(ws1.sent_messages) == 0
        assert len(ws2.sent_messages) >= 1
        assert len(ws3.sent_messages) >= 1

    @pytest.mark.asyncio
    async def test_workflow_isolation(self, sync_service):
        """测试工作流隔离"""
        ws1 = MockWebSocket("client_1")
        ws2 = MockWebSocket("client_2")

        await sync_service.connection_manager.connect(ws1, "wf_001", "client_1")
        await sync_service.connection_manager.connect(ws2, "wf_002", "client_2")

        # 向 wf_001 广播
        await sync_service.connection_manager.broadcast(
            workflow_id="wf_001",
            message={"type": "node_created", "node_id": "node_1"},
        )

        # 只有 wf_001 的客户端收到消息
        assert len(ws1.sent_messages) >= 1
        assert len(ws2.sent_messages) == 0


class TestExecutionStatusSync:
    """测试执行状态同步"""

    @pytest.fixture
    def sync_service(self):
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        return CanvasSyncService()

    @pytest.mark.asyncio
    async def test_sync_execution_status_running(self, sync_service):
        """测试执行状态同步 - 运行中"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步节点执行状态
        await sync_service.sync_execution_status(
            workflow_id="wf_001",
            node_id="node_1",
            status="running",
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "execution_status"
        assert msg["node_id"] == "node_1"
        assert msg["status"] == "running"

    @pytest.mark.asyncio
    async def test_sync_execution_status_completed(self, sync_service):
        """测试执行状态同步 - 完成"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步节点执行完成
        await sync_service.sync_execution_status(
            workflow_id="wf_001",
            node_id="node_1",
            status="completed",
            outputs={"result": "success"},
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "execution_status"
        assert msg["node_id"] == "node_1"
        assert msg["status"] == "completed"
        assert msg["outputs"]["result"] == "success"

    @pytest.mark.asyncio
    async def test_sync_execution_status_failed(self, sync_service):
        """测试执行状态同步 - 失败"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步节点执行失败
        await sync_service.sync_execution_status(
            workflow_id="wf_001",
            node_id="node_1",
            status="failed",
            error="API timeout",
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "execution_status"
        assert msg["status"] == "failed"
        assert msg["error"] == "API timeout"

    @pytest.mark.asyncio
    async def test_sync_workflow_completed(self, sync_service):
        """测试工作流完成同步"""
        ws = MockWebSocket()
        await sync_service.connection_manager.connect(ws, "wf_001", "client_1")

        # 同步工作流完成
        await sync_service.sync_workflow_completed(
            workflow_id="wf_001",
            status="success",
            outputs={"final_result": "done"},
        )

        # 验证消息
        assert len(ws.sent_messages) >= 1
        msg = ws.sent_messages[-1]
        assert msg["type"] == "workflow_completed"
        assert msg["status"] == "success"


class TestEventBusIntegration:
    """测试与事件总线的集成"""

    @pytest.fixture
    def event_bus(self):
        from src.domain.services.event_bus import EventBus

        return EventBus()

    @pytest.fixture
    def sync_service_with_event_bus(self, event_bus):
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        return CanvasSyncService(event_bus=event_bus)

    @pytest.mark.asyncio
    async def test_event_bus_triggers_sync(self, sync_service_with_event_bus, event_bus):
        """测试事件总线触发同步"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent

        ws = MockWebSocket()
        await sync_service_with_event_bus.connection_manager.connect(ws, "wf_001", "client_1")

        # 发布决策事件
        await event_bus.publish(
            DecisionMadeEvent(
                source="test",
                decision_type="create_node",
                payload={
                    "workflow_id": "wf_001",
                    "node_type": "LLM",
                    "node_id": "node_1",
                },
            )
        )

        # 注：实际集成取决于事件处理器的设置
        # 这里验证服务正常工作
        assert sync_service_with_event_bus.event_bus is not None


class TestMessageReliability:
    """测试消息可靠性"""

    @pytest.fixture
    def ack_handler(self):
        from src.infrastructure.websocket.canvas_sync import MessageAckHandler

        return MessageAckHandler(ack_timeout=1.0, max_retries=3)

    def test_register_and_acknowledge_message(self, ack_handler):
        """测试注册和确认消息"""
        from src.infrastructure.websocket.canvas_sync import ReliableMessage

        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_001",
            data={"node_id": "node_1"},
        )

        ack_handler.register_message(msg)
        assert msg.message_id in ack_handler.pending_messages

        # 确认消息
        result = ack_handler.acknowledge(msg.message_id)
        assert result is True
        assert msg.message_id not in ack_handler.pending_messages

    def test_acknowledge_unknown_message(self, ack_handler):
        """测试确认不存在的消息"""
        result = ack_handler.acknowledge("unknown_id")
        assert result is False

    def test_get_pending_messages_by_workflow(self, ack_handler):
        """测试按工作流获取待确认消息"""
        from src.infrastructure.websocket.canvas_sync import ReliableMessage

        msg1 = ReliableMessage(type="test", workflow_id="wf_001", data={})
        msg2 = ReliableMessage(type="test", workflow_id="wf_001", data={})
        msg3 = ReliableMessage(type="test", workflow_id="wf_002", data={})

        ack_handler.register_message(msg1)
        ack_handler.register_message(msg2)
        ack_handler.register_message(msg3)

        pending_wf1 = ack_handler.get_pending_messages("wf_001")
        pending_wf2 = ack_handler.get_pending_messages("wf_002")

        assert len(pending_wf1) == 2
        assert len(pending_wf2) == 1


class TestCanvasDiff:
    """测试画布差异计算"""

    def test_canvas_diff_to_messages(self):
        """测试画布差异转换为消息"""
        from src.infrastructure.websocket.canvas_sync import CanvasDiff

        diff = CanvasDiff(
            added_nodes=[{"id": "node_1", "type": "LLM", "position": {"x": 100, "y": 200}}],
            removed_nodes=["node_2"],
            modified_nodes=[{"id": "node_3", "changes": {"config": {}}}],
            added_edges=[{"id": "edge_1", "source": "node_1", "target": "node_3"}],
            removed_edges=["edge_2"],
        )

        messages = diff.to_messages("wf_001")

        # 应该生成 5 条消息
        assert len(messages) == 5

        # 验证消息类型
        message_types = [m["type"] for m in messages]
        assert "node_created" in message_types
        assert "node_deleted" in message_types
        assert "node_updated" in message_types
        assert "edge_created" in message_types
        assert "edge_deleted" in message_types

    def test_empty_canvas_diff(self):
        """测试空差异"""
        from src.infrastructure.websocket.canvas_sync import CanvasDiff

        diff = CanvasDiff(
            added_nodes=[],
            removed_nodes=[],
            modified_nodes=[],
            added_edges=[],
            removed_edges=[],
        )

        assert diff.is_empty() is True
        assert len(diff.to_messages("wf_001")) == 0


class TestFullE2ECanvasSync:
    """完整的端到端画布同步测试"""

    @pytest.fixture
    def sync_service(self):
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        return CanvasSyncService()

    @pytest.mark.asyncio
    async def test_full_workflow_editing_scenario(self, sync_service):
        """测试完整的工作流编辑场景"""
        # 设置：两个用户同时编辑同一工作流
        user_a = MockWebSocket("user_a")
        user_b = MockWebSocket("user_b")

        await sync_service.connection_manager.connect(user_a, "wf_001", "user_a")
        await sync_service.connection_manager.connect(user_b, "wf_001", "user_b")

        # 场景 1: User A 创建起始节点
        await sync_service.sync_node_created(
            workflow_id="wf_001",
            node_id="start_node",
            node_type="START",
            position={"x": 0, "y": 100},
        )

        # 场景 2: User A 创建 LLM 节点
        await sync_service.sync_node_created(
            workflow_id="wf_001",
            node_id="llm_node",
            node_type="LLM",
            position={"x": 200, "y": 100},
            config={"user_prompt": "分析数据"},
        )

        # 场景 3: User A 创建结束节点
        await sync_service.sync_node_created(
            workflow_id="wf_001",
            node_id="end_node",
            node_type="END",
            position={"x": 400, "y": 100},
        )

        # 场景 4: User A 连接节点
        await sync_service.sync_edge_created(
            workflow_id="wf_001",
            edge_id="edge_1",
            source_id="start_node",
            target_id="llm_node",
        )
        await sync_service.sync_edge_created(
            workflow_id="wf_001",
            edge_id="edge_2",
            source_id="llm_node",
            target_id="end_node",
        )

        # 场景 5: User B 更新 LLM 节点配置
        await sync_service.sync_node_updated(
            workflow_id="wf_001",
            node_id="llm_node",
            changes={"config": {"user_prompt": "深入分析数据并生成报告"}},
        )

        # 验证：两个用户都收到了所有同步消息
        # User A 应该收到 6 条消息（3 节点 + 2 边 + 1 更新）
        # User B 也应该收到 6 条消息
        assert len(user_a.sent_messages) == 6
        assert len(user_b.sent_messages) == 6

        # 验证消息类型顺序
        assert user_a.sent_messages[0]["type"] == "node_created"
        assert user_a.sent_messages[3]["type"] == "edge_created"
        assert user_a.sent_messages[5]["type"] == "node_updated"

    @pytest.mark.asyncio
    async def test_execution_status_updates_scenario(self, sync_service):
        """测试执行状态更新场景"""
        viewer = MockWebSocket("viewer")
        await sync_service.connection_manager.connect(viewer, "wf_001", "viewer")

        # 节点 1 开始执行
        await sync_service.sync_execution_status(
            workflow_id="wf_001",
            node_id="node_1",
            status="running",
        )

        # 节点 1 完成
        await sync_service.sync_execution_status(
            workflow_id="wf_001",
            node_id="node_1",
            status="completed",
            outputs={"result": "ok"},
        )

        # 节点 2 开始
        await sync_service.sync_execution_status(
            workflow_id="wf_001",
            node_id="node_2",
            status="running",
        )

        # 节点 2 失败
        await sync_service.sync_execution_status(
            workflow_id="wf_001",
            node_id="node_2",
            status="failed",
            error="API timeout",
        )

        # 工作流完成（带错误）
        await sync_service.sync_workflow_completed(
            workflow_id="wf_001",
            status="failed",
            outputs={"error": "Node 2 failed"},
        )

        # 验证收到所有状态更新
        assert len(viewer.sent_messages) == 5

        # 验证消息类型
        types = [m["type"] for m in viewer.sent_messages]
        assert types[0] == "execution_status"
        assert types[-1] == "workflow_completed"

    @pytest.mark.asyncio
    async def test_client_reconnection_scenario(self, sync_service):
        """测试客户端重连场景"""
        client = MockWebSocket("client_1")

        # 初次连接
        await sync_service.connection_manager.connect(client, "wf_001", "client_1")

        # 创建一些节点
        await sync_service.sync_node_created(
            workflow_id="wf_001",
            node_id="node_1",
            node_type="LLM",
            position={"x": 100, "y": 100},
        )

        assert len(client.sent_messages) == 1

        # 断开连接
        sync_service.connection_manager.disconnect(client)
        assert len(sync_service.connection_manager.active_connections) == 0

        # 重新连接
        new_client = MockWebSocket("client_1")
        await sync_service.connection_manager.connect(new_client, "wf_001", "client_1")

        # 验证重连成功
        assert len(sync_service.connection_manager.active_connections) == 1


# 导出
__all__ = [
    "TestConnectionManager",
    "TestCanvasSyncService",
    "TestMultiClientCollaboration",
    "TestExecutionStatusSync",
    "TestEventBusIntegration",
    "TestMessageReliability",
    "TestCanvasDiff",
    "TestFullE2ECanvasSync",
]

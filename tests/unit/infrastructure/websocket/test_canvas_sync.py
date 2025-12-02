"""WebSocket画布同步单元测试

TDD Phase: RED -> GREEN -> REFACTOR

测试WebSocket画布同步的核心功能：
1. WebSocket连接管理
2. 画布状态同步
3. 消息广播
4. 事件处理
5. 真实场景测试
"""

from unittest.mock import AsyncMock

import pytest


class TestWebSocketConnection:
    """WebSocket连接测试"""

    @pytest.mark.asyncio
    async def test_create_connection_manager(self):
        """测试：创建连接管理器"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        assert manager is not None
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_connect_client(self):
        """测试：连接客户端"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, workflow_id="wf_123")

        assert len(manager.active_connections) == 1
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_client(self):
        """测试：断开客户端"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, workflow_id="wf_123")
        manager.disconnect(mock_websocket)

        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_multiple_clients_same_workflow(self):
        """测试：多个客户端连接同一工作流"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect(ws1, workflow_id="wf_123")
        await manager.connect(ws2, workflow_id="wf_123")

        assert len(manager.active_connections) == 2
        assert len(manager.get_connections("wf_123")) == 2

    @pytest.mark.asyncio
    async def test_clients_different_workflows(self):
        """测试：不同工作流的客户端隔离"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect(ws1, workflow_id="wf_1")
        await manager.connect(ws2, workflow_id="wf_2")

        assert len(manager.get_connections("wf_1")) == 1
        assert len(manager.get_connections("wf_2")) == 1


class TestMessageBroadcast:
    """消息广播测试"""

    @pytest.mark.asyncio
    async def test_broadcast_to_workflow(self):
        """测试：向工作流广播消息"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, workflow_id="wf_123")
        await manager.connect(ws2, workflow_id="wf_123")

        message = {"type": "node_created", "node_id": "node_1"}
        await manager.broadcast(workflow_id="wf_123", message=message)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_only_to_target_workflow(self):
        """测试：只广播给目标工作流"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, workflow_id="wf_1")
        await manager.connect(ws2, workflow_id="wf_2")

        message = {"type": "update"}
        await manager.broadcast(workflow_id="wf_1", message=message)

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnected_client(self):
        """测试：广播处理已断开的客户端"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        await manager.connect(ws1, workflow_id="wf_123")

        message = {"type": "update"}
        # 不应抛出异常
        await manager.broadcast(workflow_id="wf_123", message=message)

        # 断开的客户端应该被移除
        assert len(manager.get_connections("wf_123")) == 0


class TestCanvasSyncService:
    """画布同步服务测试"""

    @pytest.mark.asyncio
    async def test_create_canvas_sync_service(self):
        """测试：创建画布同步服务"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        assert service is not None

    @pytest.mark.asyncio
    async def test_sync_node_created(self):
        """测试：同步节点创建事件"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123")

        await service.sync_node_created(
            workflow_id="wf_123",
            node_id="node_1",
            node_type="llm",
            position={"x": 100, "y": 200},
            config={"model": "gpt-4"},
        )

        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "node_created"
        assert call_args["node_id"] == "node_1"

    @pytest.mark.asyncio
    async def test_sync_node_updated(self):
        """测试：同步节点更新事件"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123")

        await service.sync_node_updated(
            workflow_id="wf_123",
            node_id="node_1",
            changes={"status": "running"},
        )

        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "node_updated"
        assert call_args["changes"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_sync_node_deleted(self):
        """测试：同步节点删除事件"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123")

        await service.sync_node_deleted(
            workflow_id="wf_123",
            node_id="node_1",
        )

        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "node_deleted"
        assert call_args["node_id"] == "node_1"

    @pytest.mark.asyncio
    async def test_sync_edge_created(self):
        """测试：同步边创建事件"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123")

        await service.sync_edge_created(
            workflow_id="wf_123",
            edge_id="edge_1",
            source_id="node_1",
            target_id="node_2",
        )

        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "edge_created"
        assert call_args["source_id"] == "node_1"

    @pytest.mark.asyncio
    async def test_sync_execution_status(self):
        """测试：同步执行状态"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123")

        await service.sync_execution_status(
            workflow_id="wf_123",
            node_id="node_1",
            status="completed",
            outputs={"result": "success"},
        )

        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "execution_status"
        assert call_args["status"] == "completed"


class TestEventBusIntegration:
    """事件总线集成测试"""

    @pytest.mark.asyncio
    async def test_integrate_with_event_bus(self):
        """测试：与事件总线集成"""
        from src.domain.services.event_bus import EventBus
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        event_bus = EventBus()
        service = CanvasSyncService(event_bus=event_bus)

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123")

        # 发布事件
        from src.domain.services.canvas_synchronizer import NodeCreatedEvent

        event = NodeCreatedEvent(
            source="test",
            workflow_id="wf_123",
            node_id="node_1",
            node_type="llm",
        )
        await event_bus.publish(event)

        # 验证消息被发送
        ws.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_event_handler_for_node_execution(self):
        """测试：节点执行事件处理"""
        from src.domain.services.event_bus import EventBus
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        event_bus = EventBus()
        service = CanvasSyncService(event_bus=event_bus)

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123")

        # 发布节点执行完成事件
        from src.domain.services.canvas_synchronizer import NodeExecutionCompletedEvent

        event = NodeExecutionCompletedEvent(
            source="test",
            workflow_id="wf_123",
            node_id="node_1",
            outputs={"data": "result"},
        )
        await event_bus.publish(event)

        ws.send_json.assert_called()


class TestCanvasSnapshot:
    """画布快照测试"""

    @pytest.mark.asyncio
    async def test_get_canvas_snapshot(self):
        """测试：获取画布快照"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        # 模拟工作流状态
        service.set_workflow_state(
            workflow_id="wf_123",
            nodes=[
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}},
                {"id": "node_2", "type": "llm", "position": {"x": 200, "y": 0}},
            ],
            edges=[{"id": "edge_1", "source": "node_1", "target": "node_2"}],
        )

        snapshot = service.get_canvas_snapshot("wf_123")

        assert len(snapshot["nodes"]) == 2
        assert len(snapshot["edges"]) == 1

    @pytest.mark.asyncio
    async def test_send_initial_state_on_connect(self):
        """测试：连接时发送初始状态"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        # 设置工作流状态
        service.set_workflow_state(
            workflow_id="wf_123",
            nodes=[{"id": "node_1", "type": "start"}],
            edges=[],
        )

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await service.connection_manager.connect(ws, workflow_id="wf_123", send_initial_state=True)

        # 应该发送初始状态
        ws.send_json.assert_called()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "initial_state"


class TestRealWorldScenarios:
    """真实场景测试"""

    @pytest.mark.asyncio
    async def test_workflow_execution_sync(self):
        """测试：工作流执行同步"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        # 模拟多个前端客户端
        clients = []
        for _ in range(3):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            await service.connection_manager.connect(ws, workflow_id="wf_123")
            clients.append(ws)

        # 模拟工作流执行过程
        # 1. 开始执行
        await service.sync_execution_status(
            workflow_id="wf_123",
            node_id="start",
            status="running",
        )

        # 2. 第一个节点完成
        await service.sync_execution_status(
            workflow_id="wf_123",
            node_id="node_1",
            status="completed",
            outputs={"data": "processed"},
        )

        # 3. 工作流完成
        await service.sync_workflow_completed(
            workflow_id="wf_123",
            status="success",
            outputs={"final_result": "done"},
        )

        # 验证所有客户端都收到了消息
        for client in clients:
            assert client.send_json.call_count >= 3

    @pytest.mark.asyncio
    async def test_collaborative_editing(self):
        """测试：协作编辑场景"""
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        service = CanvasSyncService()

        # 两个用户同时编辑
        user1_ws = AsyncMock()
        user1_ws.accept = AsyncMock()
        user1_ws.send_json = AsyncMock()

        user2_ws = AsyncMock()
        user2_ws.accept = AsyncMock()
        user2_ws.send_json = AsyncMock()

        await service.connection_manager.connect(user1_ws, workflow_id="wf_123")
        await service.connection_manager.connect(user2_ws, workflow_id="wf_123")

        # 用户1创建节点
        await service.sync_node_created(
            workflow_id="wf_123",
            node_id="node_new",
            node_type="http",
            position={"x": 300, "y": 100},
        )

        # 两个用户都应该收到更新
        user1_ws.send_json.assert_called()
        user2_ws.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_agent_canvas_sync(self):
        """测试：Agent与画布同步"""
        from src.domain.services.event_bus import EventBus
        from src.infrastructure.websocket.canvas_sync import CanvasSyncService

        event_bus = EventBus()
        service = CanvasSyncService(event_bus=event_bus)

        # 模拟前端画布
        canvas_ws = AsyncMock()
        canvas_ws.accept = AsyncMock()
        canvas_ws.send_json = AsyncMock()

        await service.connection_manager.connect(canvas_ws, workflow_id="wf_123")

        # 模拟对话Agent创建节点决策
        from src.domain.services.canvas_synchronizer import NodeCreatedEvent

        # Agent决定创建一个LLM节点
        create_event = NodeCreatedEvent(
            source="conversation_agent",
            workflow_id="wf_123",
            node_id="agent_node_1",
            node_type="llm",
        )
        await event_bus.publish(create_event)

        # 画布应该收到更新
        canvas_ws.send_json.assert_called()
        message = canvas_ws.send_json.call_args[0][0]
        assert message["node_id"] == "agent_node_1"


class TestConnectionStatistics:
    """连接统计测试"""

    @pytest.mark.asyncio
    async def test_get_connection_count(self):
        """测试：获取连接数"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        for i in range(5):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            await manager.connect(ws, workflow_id=f"wf_{i % 2}")

        stats = manager.get_statistics()

        assert stats["total_connections"] == 5
        assert stats["workflows"]["wf_0"] == 3
        assert stats["workflows"]["wf_1"] == 2

    @pytest.mark.asyncio
    async def test_get_workflow_client_list(self):
        """测试：获取工作流客户端列表"""
        from src.infrastructure.websocket.canvas_sync import ConnectionManager

        manager = ConnectionManager()

        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect(ws1, workflow_id="wf_123", client_id="client_1")
        await manager.connect(ws2, workflow_id="wf_123", client_id="client_2")

        clients = manager.get_client_ids("wf_123")

        assert "client_1" in clients
        assert "client_2" in clients

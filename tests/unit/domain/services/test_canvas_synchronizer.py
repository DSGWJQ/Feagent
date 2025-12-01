"""测试：画布同步系统

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 工作流画布需要实时同步到前端
- 节点/边的增删改需要即时反映
- 支持WebSocket实时推送

真实场景：
1. 对话Agent创建节点 → 画布同步 → 前端更新
2. 用户拖拽节点 → 位置同步 → 其他客户端更新
3. 工作流执行 → 节点状态变化 → 前端高亮

核心能力：
- 状态同步：节点/边的增删改
- 实时推送：WebSocket连接管理
- 增量更新：只推送变化部分

"""

from unittest.mock import AsyncMock

import pytest


class TestCanvasSynchronizerSetup:
    """测试画布同步器的基础设置

    业务背景：
    - 画布同步器需要管理WebSocket连接
    - 需要订阅工作流状态变化事件
    """

    @pytest.mark.asyncio
    async def test_create_canvas_synchronizer(self):
        """测试：创建画布同步器

        验收标准：
        - 同步器正确初始化
        - 可以管理连接
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        assert synchronizer is not None
        assert synchronizer.connections == {}

    @pytest.mark.asyncio
    async def test_register_connection(self):
        """测试：注册WebSocket连接

        验收标准：
        - 连接按workflow_id分组
        - 可以注册多个连接
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()

        await synchronizer.register_connection("workflow_1", mock_ws_1)
        await synchronizer.register_connection("workflow_1", mock_ws_2)

        assert len(synchronizer.connections.get("workflow_1", [])) == 2

    @pytest.mark.asyncio
    async def test_unregister_connection(self):
        """测试：注销WebSocket连接

        验收标准：
        - 连接被正确移除
        - 其他连接不受影响
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()

        await synchronizer.register_connection("workflow_1", mock_ws_1)
        await synchronizer.register_connection("workflow_1", mock_ws_2)
        await synchronizer.unregister_connection("workflow_1", mock_ws_1)

        assert len(synchronizer.connections.get("workflow_1", [])) == 1
        assert mock_ws_2 in synchronizer.connections["workflow_1"]


class TestNodeSynchronization:
    """测试节点同步

    业务背景：
    - 节点的增删改需要同步到前端
    - 包含节点位置、配置等信息
    """

    @pytest.mark.asyncio
    async def test_sync_node_created(self):
        """测试：同步节点创建

        业务场景：
        - 对话Agent创建了新节点
        - 画布同步器推送到前端

        验收标准：
        - WebSocket收到node_created消息
        - 包含节点完整信息
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 同步节点创建
        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_123",
            node_type="LLM",
            position={"x": 100, "y": 200},
            config={"user_prompt": "分析数据"},
        )

        # 验证消息发送
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "node_created"
        assert call_args["data"]["node_id"] == "node_123"
        assert call_args["data"]["node_type"] == "LLM"
        assert call_args["data"]["position"]["x"] == 100

    @pytest.mark.asyncio
    async def test_sync_node_updated(self):
        """测试：同步节点更新

        业务场景：
        - 用户修改了节点配置
        - 变化需要同步到其他客户端

        验收标准：
        - WebSocket收到node_updated消息
        - 只包含变化的字段
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 同步节点更新
        await synchronizer.sync_node_updated(
            workflow_id="workflow_1",
            node_id="node_123",
            changes={"config": {"user_prompt": "新的提示词"}},
        )

        # 验证
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "node_updated"
        assert call_args["data"]["node_id"] == "node_123"
        assert "config" in call_args["data"]["changes"]

    @pytest.mark.asyncio
    async def test_sync_node_deleted(self):
        """测试：同步节点删除

        验收标准：
        - WebSocket收到node_deleted消息
        - 包含被删除的节点ID
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 同步节点删除
        await synchronizer.sync_node_deleted(workflow_id="workflow_1", node_id="node_123")

        # 验证
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "node_deleted"
        assert call_args["data"]["node_id"] == "node_123"

    @pytest.mark.asyncio
    async def test_sync_node_position_changed(self):
        """测试：同步节点位置变化

        业务场景：
        - 用户拖拽节点
        - 位置变化实时同步

        验收标准：
        - WebSocket收到node_moved消息
        - 包含新位置
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 同步位置变化
        await synchronizer.sync_node_moved(
            workflow_id="workflow_1", node_id="node_123", new_position={"x": 300, "y": 400}
        )

        # 验证
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "node_moved"
        assert call_args["data"]["position"]["x"] == 300


class TestEdgeSynchronization:
    """测试边同步

    业务背景：
    - 节点之间的连接需要同步
    - 包括创建和删除
    """

    @pytest.mark.asyncio
    async def test_sync_edge_created(self):
        """测试：同步边创建

        验收标准：
        - WebSocket收到edge_created消息
        - 包含源节点和目标节点
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 同步边创建
        await synchronizer.sync_edge_created(
            workflow_id="workflow_1", edge_id="edge_123", source_id="node_1", target_id="node_2"
        )

        # 验证
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "edge_created"
        assert call_args["data"]["source_id"] == "node_1"
        assert call_args["data"]["target_id"] == "node_2"

    @pytest.mark.asyncio
    async def test_sync_edge_deleted(self):
        """测试：同步边删除

        验收标准：
        - WebSocket收到edge_deleted消息
        - 包含被删除的边ID
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 同步边删除
        await synchronizer.sync_edge_deleted(workflow_id="workflow_1", edge_id="edge_123")

        # 验证
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "edge_deleted"
        assert call_args["data"]["edge_id"] == "edge_123"


class TestExecutionStatusSync:
    """测试执行状态同步

    业务背景：
    - 工作流执行时，节点状态需要实时更新
    - 前端据此高亮当前执行的节点
    """

    @pytest.mark.asyncio
    async def test_sync_node_execution_status(self):
        """测试：同步节点执行状态

        业务场景：
        - 工作流执行中
        - 节点状态变为running/completed/failed

        验收标准：
        - WebSocket收到execution_status消息
        - 包含节点ID和状态
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 同步执行状态
        await synchronizer.sync_execution_status(
            workflow_id="workflow_1", node_id="node_123", status="running"
        )

        # 验证
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "execution_status"
        assert call_args["data"]["node_id"] == "node_123"
        assert call_args["data"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_sync_workflow_execution_started(self):
        """测试：同步工作流开始执行

        验收标准：
        - WebSocket收到workflow_started消息
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        await synchronizer.sync_workflow_started(workflow_id="workflow_1")

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "workflow_started"

    @pytest.mark.asyncio
    async def test_sync_workflow_execution_completed(self):
        """测试：同步工作流执行完成

        验收标准：
        - WebSocket收到workflow_completed消息
        - 包含执行结果摘要
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        await synchronizer.sync_workflow_completed(
            workflow_id="workflow_1", status="completed", result_summary="执行成功，分析了100条数据"
        )

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "workflow_completed"
        assert call_args["data"]["status"] == "completed"


class TestBroadcast:
    """测试广播功能

    业务背景：
    - 同一工作流可能有多个客户端
    - 变化需要广播给所有客户端
    """

    @pytest.mark.asyncio
    async def test_broadcast_to_all_connections(self):
        """测试：广播给所有连接

        验收标准：
        - 所有连接都收到消息
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()
        mock_ws_3 = AsyncMock()

        await synchronizer.register_connection("workflow_1", mock_ws_1)
        await synchronizer.register_connection("workflow_1", mock_ws_2)
        await synchronizer.register_connection("workflow_1", mock_ws_3)

        # 同步节点创建（应该广播给所有3个连接）
        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_123",
            node_type="LLM",
            position={"x": 0, "y": 0},
            config={},
        )

        # 验证所有连接都收到消息
        assert mock_ws_1.send_json.call_count == 1
        assert mock_ws_2.send_json.call_count == 1
        assert mock_ws_3.send_json.call_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_only_to_same_workflow(self):
        """测试：只广播给相同工作流的连接

        验收标准：
        - 不同工作流的连接不收到消息
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws_1 = AsyncMock()  # workflow_1
        mock_ws_2 = AsyncMock()  # workflow_2

        await synchronizer.register_connection("workflow_1", mock_ws_1)
        await synchronizer.register_connection("workflow_2", mock_ws_2)

        # 向workflow_1发送消息
        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_123",
            node_type="LLM",
            position={"x": 0, "y": 0},
            config={},
        )

        # 只有workflow_1的连接收到消息
        assert mock_ws_1.send_json.call_count == 1
        assert mock_ws_2.send_json.call_count == 0

    @pytest.mark.asyncio
    async def test_handle_disconnected_client(self):
        """测试：处理断开的客户端

        业务场景：
        - 客户端断开连接
        - 发送消息时应该跳过并清理

        验收标准：
        - 断开的连接被跳过
        - 其他连接正常收到消息
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws_1 = AsyncMock()
        mock_ws_1.send_json.side_effect = Exception("Connection closed")
        mock_ws_2 = AsyncMock()

        await synchronizer.register_connection("workflow_1", mock_ws_1)
        await synchronizer.register_connection("workflow_1", mock_ws_2)

        # 发送消息（ws_1会失败）
        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_123",
            node_type="LLM",
            position={"x": 0, "y": 0},
            config={},
        )

        # ws_2应该正常收到消息
        assert mock_ws_2.send_json.call_count == 1


class TestEventBusIntegration:
    """测试与EventBus的集成

    业务背景：
    - 画布同步器需要订阅工作流事件
    - 自动同步状态变化到前端
    """

    @pytest.mark.asyncio
    async def test_integrate_with_event_bus(self):
        """测试：与EventBus集成

        验收标准：
        - 可以注册到EventBus
        - 自动处理工作流事件
        """
        from src.domain.agents.workflow_agent import NodeExecutionEvent
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        synchronizer = CanvasSynchronizer()

        # 注册连接
        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 注册事件处理
        synchronizer.register_with_event_bus(event_bus, "workflow_1")

        # 发布节点执行事件
        await event_bus.publish(
            NodeExecutionEvent(node_id="node_123", node_type="LLM", status="running", result=None)
        )

        # 验证WebSocket收到消息
        assert mock_ws.send_json.call_count == 1


class TestCanvasSnapshot:
    """测试画布快照

    业务背景：
    - 新客户端连接时需要获取完整状态
    - 支持状态恢复
    """

    @pytest.mark.asyncio
    async def test_get_canvas_snapshot(self):
        """测试：获取画布快照

        验收标准：
        - 返回完整的节点和边列表
        - 包含当前执行状态
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        # 设置一些状态
        synchronizer.set_canvas_state(
            workflow_id="workflow_1",
            nodes=[
                {"id": "node_1", "type": "START", "position": {"x": 0, "y": 0}},
                {"id": "node_2", "type": "LLM", "position": {"x": 200, "y": 0}},
            ],
            edges=[{"id": "edge_1", "source": "node_1", "target": "node_2"}],
        )

        # 获取快照
        snapshot = synchronizer.get_canvas_snapshot("workflow_1")

        assert len(snapshot["nodes"]) == 2
        assert len(snapshot["edges"]) == 1
        assert snapshot["nodes"][0]["id"] == "node_1"

    @pytest.mark.asyncio
    async def test_send_initial_state_on_connect(self):
        """测试：连接时发送初始状态

        业务场景：
        - 新客户端连接
        - 自动接收当前画布状态

        验收标准：
        - 连接时收到canvas_snapshot消息
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        # 设置画布状态
        synchronizer.set_canvas_state(
            workflow_id="workflow_1", nodes=[{"id": "node_1", "type": "START"}], edges=[]
        )

        # 注册连接（应该自动发送快照）
        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws, send_initial_state=True)

        # 验证收到快照
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "canvas_snapshot"


class TestSynchronizerStatistics:
    """测试同步器统计"""

    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """测试：获取同步统计

        验收标准：
        - 返回连接数
        - 返回消息发送数
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        mock_ws = AsyncMock()
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 发送一些消息
        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_1",
            node_type="START",
            position={"x": 0, "y": 0},
            config={},
        )

        stats = synchronizer.get_statistics()

        assert stats["total_connections"] == 1
        assert stats["messages_sent"] >= 1


class TestRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_complete_canvas_sync_flow(self):
        """测试：完整的画布同步流程

        业务场景：
        1. 客户端连接
        2. 对话Agent创建节点
        3. 节点被同步到画布
        4. 工作流执行
        5. 执行状态同步

        这是画布同步的核心场景！

        验收标准：
        - 所有状态变化被同步
        - 客户端收到正确的消息序列
        """
        from src.domain.services.canvas_synchronizer import CanvasSynchronizer

        synchronizer = CanvasSynchronizer()

        # 记录收到的消息
        received_messages = []

        mock_ws = AsyncMock()

        async def capture_message(msg):
            received_messages.append(msg)

        mock_ws.send_json.side_effect = capture_message

        # 1. 客户端连接
        await synchronizer.register_connection("workflow_1", mock_ws)

        # 2. 创建节点
        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_1",
            node_type="START",
            position={"x": 0, "y": 0},
            config={},
        )

        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_2",
            node_type="LLM",
            position={"x": 200, "y": 0},
            config={"user_prompt": "分析"},
        )

        await synchronizer.sync_node_created(
            workflow_id="workflow_1",
            node_id="node_3",
            node_type="END",
            position={"x": 400, "y": 0},
            config={},
        )

        # 3. 创建边
        await synchronizer.sync_edge_created(
            workflow_id="workflow_1", edge_id="edge_1", source_id="node_1", target_id="node_2"
        )

        await synchronizer.sync_edge_created(
            workflow_id="workflow_1", edge_id="edge_2", source_id="node_2", target_id="node_3"
        )

        # 4. 执行工作流
        await synchronizer.sync_workflow_started(workflow_id="workflow_1")

        await synchronizer.sync_execution_status(
            workflow_id="workflow_1", node_id="node_1", status="completed"
        )

        await synchronizer.sync_execution_status(
            workflow_id="workflow_1", node_id="node_2", status="running"
        )

        await synchronizer.sync_execution_status(
            workflow_id="workflow_1", node_id="node_2", status="completed"
        )

        await synchronizer.sync_execution_status(
            workflow_id="workflow_1", node_id="node_3", status="completed"
        )

        await synchronizer.sync_workflow_completed(
            workflow_id="workflow_1", status="completed", result_summary="执行成功"
        )

        # 验证消息序列
        message_types = [msg["type"] for msg in received_messages]

        assert "node_created" in message_types
        assert "edge_created" in message_types
        assert "workflow_started" in message_types
        assert "execution_status" in message_types
        assert "workflow_completed" in message_types

        # 验证消息数量
        assert message_types.count("node_created") == 3
        assert message_types.count("edge_created") == 2
        assert message_types.count("execution_status") == 4

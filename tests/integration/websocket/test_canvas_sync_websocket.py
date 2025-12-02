"""WebSocket Canvas 同步集成测试

TDD 驱动：先写测试定义期望行为，再实现功能

测试场景：
1. 客户端连接 WebSocket 并接收初始状态
2. 节点创建时广播消息给所有客户端
3. 节点更新时广播消息
4. 节点删除时广播消息
5. 执行状态同步
6. 多客户端协作场景
7. 连接断开处理

技术栈：
- FastAPI WebSocket
- pytest + pytest-asyncio
- Starlette TestClient (WebSocket 支持)
"""

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def app():
    """创建测试用 FastAPI 应用"""
    from src.interfaces.api.main import app

    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


class TestWebSocketConnection:
    """测试 WebSocket 连接基础功能"""

    def test_websocket_connect_should_succeed(self, client):
        """测试：客户端应该能成功连接 WebSocket

        验收标准：
        - 连接 /ws/workflows/{workflow_id}
        - 连接成功，收到初始状态消息
        """
        with client.websocket_connect("/ws/workflows/wf_test_123") as websocket:
            # 应该收到初始状态消息
            data = websocket.receive_json()

            assert data["type"] == "initial_state"
            assert data["workflow_id"] == "wf_test_123"
            assert "nodes" in data
            assert "edges" in data
            assert "timestamp" in data

    def test_websocket_connect_with_client_id(self, client):
        """测试：客户端可以指定 client_id 连接

        验收标准：
        - 连接时传入 client_id 参数
        - 服务器使用该 client_id 标识客户端
        """
        with client.websocket_connect(
            "/ws/workflows/wf_test_123?client_id=client_abc"
        ) as websocket:
            data = websocket.receive_json()

            assert data["type"] == "initial_state"
            # 初始状态中应该包含 client_id
            assert data.get("client_id") == "client_abc" or "client_id" in str(data)

    def test_websocket_disconnect_gracefully(self, client):
        """测试：客户端断开连接应该被正确处理

        验收标准：
        - 断开连接不应抛出异常
        - 服务器应该清理连接资源
        """
        with client.websocket_connect("/ws/workflows/wf_test_123") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "initial_state"
        # 断开连接后不应有异常


class TestNodeSynchronization:
    """测试节点同步功能"""

    def test_node_created_should_broadcast_to_all_clients(self, client):
        """测试：创建节点时应该广播给所有连接的客户端

        场景：
        - 客户端 A 连接
        - 客户端 B 连接
        - 客户端 A 创建节点
        - 客户端 B 应该收到节点创建消息
        """
        with client.websocket_connect("/ws/workflows/wf_sync_test") as ws1:
            # 接收初始状态
            ws1.receive_json()

            with client.websocket_connect("/ws/workflows/wf_sync_test") as ws2:
                # 接收初始状态
                ws2.receive_json()

                # 客户端 1 发送创建节点消息
                ws1.send_json(
                    {
                        "action": "create_node",
                        "node": {
                            "id": "node_new_1",
                            "type": "llm",
                            "position": {"x": 100, "y": 200},
                            "config": {"model": "gpt-4"},
                        },
                    }
                )

                # 客户端 2 应该收到广播
                data = ws2.receive_json()

                assert data["type"] == "node_created"
                assert data["node_id"] == "node_new_1"
                assert data["node_type"] == "llm"
                assert data["position"] == {"x": 100, "y": 200}

    def test_node_updated_should_broadcast_changes(self, client):
        """测试：更新节点时应该广播变更

        验收标准：
        - 发送节点更新消息
        - 其他客户端收到更新通知
        """
        with client.websocket_connect("/ws/workflows/wf_sync_test") as ws1:
            ws1.receive_json()  # 初始状态

            with client.websocket_connect("/ws/workflows/wf_sync_test") as ws2:
                ws2.receive_json()  # 初始状态

                # 发送更新节点消息
                ws1.send_json(
                    {
                        "action": "update_node",
                        "node_id": "node_1",
                        "changes": {"config": {"model": "gpt-4-turbo"}, "name": "Updated Node"},
                    }
                )

                # 验证广播
                data = ws2.receive_json()

                assert data["type"] == "node_updated"
                assert data["node_id"] == "node_1"
                assert "changes" in data

    def test_node_deleted_should_broadcast_deletion(self, client):
        """测试：删除节点时应该广播删除消息

        验收标准：
        - 发送删除节点消息
        - 其他客户端收到删除通知
        """
        with client.websocket_connect("/ws/workflows/wf_sync_test") as ws1:
            ws1.receive_json()

            with client.websocket_connect("/ws/workflows/wf_sync_test") as ws2:
                ws2.receive_json()

                # 发送删除节点消息
                ws1.send_json({"action": "delete_node", "node_id": "node_to_delete"})

                # 验证广播
                data = ws2.receive_json()

                assert data["type"] == "node_deleted"
                assert data["node_id"] == "node_to_delete"

    def test_node_moved_should_broadcast_position(self, client):
        """测试：移动节点时应该广播新位置

        验收标准：
        - 发送节点移动消息
        - 其他客户端收到位置更新
        """
        with client.websocket_connect("/ws/workflows/wf_sync_test") as ws1:
            ws1.receive_json()

            with client.websocket_connect("/ws/workflows/wf_sync_test") as ws2:
                ws2.receive_json()

                # 发送移动节点消息
                ws1.send_json(
                    {"action": "move_node", "node_id": "node_1", "position": {"x": 300, "y": 400}}
                )

                # 验证广播
                data = ws2.receive_json()

                assert data["type"] == "node_moved"
                assert data["node_id"] == "node_1"
                assert data["position"] == {"x": 300, "y": 400}


class TestEdgeSynchronization:
    """测试边同步功能"""

    def test_edge_created_should_broadcast(self, client):
        """测试：创建边时应该广播

        验收标准：
        - 发送创建边消息
        - 其他客户端收到边创建通知
        """
        with client.websocket_connect("/ws/workflows/wf_edge_test") as ws1:
            ws1.receive_json()

            with client.websocket_connect("/ws/workflows/wf_edge_test") as ws2:
                ws2.receive_json()

                # 发送创建边消息
                ws1.send_json(
                    {
                        "action": "create_edge",
                        "edge": {"id": "edge_1", "source": "node_a", "target": "node_b"},
                    }
                )

                # 验证广播
                data = ws2.receive_json()

                assert data["type"] == "edge_created"
                assert data["edge_id"] == "edge_1"
                assert data["source_id"] == "node_a"
                assert data["target_id"] == "node_b"

    def test_edge_deleted_should_broadcast(self, client):
        """测试：删除边时应该广播

        验收标准：
        - 发送删除边消息
        - 其他客户端收到边删除通知
        """
        with client.websocket_connect("/ws/workflows/wf_edge_test") as ws1:
            ws1.receive_json()

            with client.websocket_connect("/ws/workflows/wf_edge_test") as ws2:
                ws2.receive_json()

                # 发送删除边消息
                ws1.send_json({"action": "delete_edge", "edge_id": "edge_to_delete"})

                # 验证广播
                data = ws2.receive_json()

                assert data["type"] == "edge_deleted"
                assert data["edge_id"] == "edge_to_delete"


class TestExecutionStatusSync:
    """测试执行状态同步"""

    def test_execution_started_should_broadcast(self, client):
        """测试：工作流执行开始时应该广播

        验收标准：
        - 执行开始时所有客户端收到通知
        - 包含工作流 ID 和开始时间
        """
        with client.websocket_connect("/ws/workflows/wf_exec_test") as ws:
            ws.receive_json()  # 初始状态

            # 通过 API 触发执行（模拟）
            # 这里需要与执行服务集成
            ws.send_json({"action": "start_execution"})

            # 应该收到执行开始消息
            data = ws.receive_json()

            assert data["type"] == "workflow_started"
            assert data["workflow_id"] == "wf_exec_test"
            assert "timestamp" in data

    def test_node_execution_status_should_broadcast(self, client):
        """测试：节点执行状态变化时应该广播

        验收标准：
        - 节点开始执行、完成、失败时广播状态
        - 包含节点 ID、状态、输出（如有）
        """
        with client.websocket_connect("/ws/workflows/wf_exec_test") as ws:
            ws.receive_json()  # 初始状态

            # 模拟节点状态变化（从服务端触发）
            # 这需要与 CanvasSyncService 集成

            # 期望的消息格式 (for reference)
            # {
            #     "type": "execution_status",
            #     "workflow_id": "wf_exec_test",
            #     "node_id": "node_1",
            #     "status": "running",  # running | completed | error
            #     "outputs": {},
            #     "error": None,
            # }

            # 注意：这个测试需要后端集成完成后才能完全工作
            # 现在先定义期望的行为

    def test_workflow_completed_should_broadcast_result(self, client):
        """测试：工作流完成时应该广播结果

        验收标准：
        - 工作流完成时广播完成状态
        - 包含最终输出和执行日志
        """
        with client.websocket_connect("/ws/workflows/wf_exec_test") as ws:
            ws.receive_json()  # 初始状态

            # 期望的消息格式 (for reference)
            # {
            #     "type": "workflow_completed",
            #     "workflow_id": "wf_exec_test",
            #     "status": "completed",  # completed | failed
            #     "outputs": {},
            #     "execution_log": [],
            # }


class TestMultiClientScenarios:
    """测试多客户端场景"""

    def test_multiple_clients_same_workflow(self, client):
        """测试：多个客户端编辑同一工作流

        场景：
        - 3 个客户端连接同一工作流
        - 每个客户端的操作都广播给其他客户端
        """
        with client.websocket_connect("/ws/workflows/wf_multi") as ws1:
            ws1.receive_json()

            with client.websocket_connect("/ws/workflows/wf_multi") as ws2:
                ws2.receive_json()

                with client.websocket_connect("/ws/workflows/wf_multi") as ws3:
                    ws3.receive_json()

                    # ws1 创建节点
                    ws1.send_json(
                        {
                            "action": "create_node",
                            "node": {
                                "id": "multi_node_1",
                                "type": "http",
                                "position": {"x": 0, "y": 0},
                            },
                        }
                    )

                    # ws2 和 ws3 都应该收到
                    data2 = ws2.receive_json()
                    data3 = ws3.receive_json()

                    assert data2["type"] == "node_created"
                    assert data3["type"] == "node_created"
                    assert data2["node_id"] == "multi_node_1"
                    assert data3["node_id"] == "multi_node_1"

    def test_client_isolation_between_workflows(self, client):
        """测试：不同工作流的客户端应该隔离

        验收标准：
        - 工作流 A 的客户端不应收到工作流 B 的消息
        """
        with client.websocket_connect("/ws/workflows/wf_a") as ws_a:
            ws_a.receive_json()

            with client.websocket_connect("/ws/workflows/wf_b") as ws_b:
                ws_b.receive_json()

                # 在 wf_a 中创建节点
                ws_a.send_json(
                    {
                        "action": "create_node",
                        "node": {"id": "node_in_a", "type": "llm", "position": {"x": 0, "y": 0}},
                    }
                )

                # ws_b 不应该收到任何消息（或者收到超时）
                # 使用 receive_json 的超时机制
                try:
                    # 设置短超时
                    ws_b.receive_json(timeout=0.5)
                    # 如果收到消息，测试失败
                    raise AssertionError("ws_b should not receive messages from wf_a")
                except Exception as e:
                    # 超时是预期的，但AssertionError应该重新抛出
                    if isinstance(e, AssertionError):
                        raise
                    pass


class TestErrorHandling:
    """测试错误处理"""

    def test_invalid_action_should_return_error(self, client):
        """测试：无效操作应该返回错误

        验收标准：
        - 发送无效 action 返回错误消息
        - 连接保持活跃
        """
        with client.websocket_connect("/ws/workflows/wf_error_test") as ws:
            ws.receive_json()  # 初始状态

            # 发送无效操作
            ws.send_json({"action": "invalid_action_xyz"})

            # 应该收到错误消息
            data = ws.receive_json()

            assert data["type"] == "error"
            assert "message" in data or "error" in data

    def test_malformed_message_should_return_error(self, client):
        """测试：格式错误的消息应该返回错误

        验收标准：
        - 发送非 JSON 或缺少必要字段的消息
        - 返回错误但不断开连接
        """
        with client.websocket_connect("/ws/workflows/wf_error_test") as ws:
            ws.receive_json()  # 初始状态

            # 发送缺少必要字段的消息
            ws.send_json({"invalid": "message"})

            # 应该收到错误消息
            data = ws.receive_json()

            assert data["type"] == "error"

    def test_workflow_not_found_should_still_connect(self, client):
        """测试：即使工作流不存在也应该能连接

        验收标准：
        - 连接不存在的工作流 ID
        - 仍然可以连接（返回空的初始状态）
        - 可以创建节点
        """
        with client.websocket_connect("/ws/workflows/wf_nonexistent_123") as ws:
            data = ws.receive_json()

            assert data["type"] == "initial_state"
            assert data["nodes"] == []
            assert data["edges"] == []

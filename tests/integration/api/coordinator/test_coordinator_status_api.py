"""协调者状态 API 集成测试

TDD 驱动：验证协调者状态查询和 SSE 推送功能

测试场景：
1. GET /api/coordinator/status - 获取系统状态
2. GET /api/coordinator/workflows/{workflow_id} - 获取工作流状态
3. GET /api/coordinator/workflows/{workflow_id}/stream - SSE 实时状态推送
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestCoordinatorStatusAPI:
    """协调者状态 API 测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        from src.interfaces.api.routes.coordinator_status import router

        app = FastAPI()
        app.include_router(router, prefix="/api/coordinator")
        return app

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return TestClient(app)

    # ==================== 系统状态测试 ====================

    def test_get_system_status_returns_summary(self, client):
        """测试：获取系统状态返回摘要"""
        response = client.get("/api/coordinator/status")

        assert response.status_code == 200
        data = response.json()

        # 验证返回字段
        assert "total_workflows" in data
        assert "running_workflows" in data
        assert "completed_workflows" in data
        assert "failed_workflows" in data
        assert "active_nodes" in data

    def test_system_status_includes_decision_statistics(self, client):
        """测试：系统状态包含决策统计"""
        response = client.get("/api/coordinator/status")

        assert response.status_code == 200
        data = response.json()

        assert "decision_statistics" in data
        stats = data["decision_statistics"]
        assert "total" in stats
        assert "passed" in stats
        assert "rejected" in stats

    # ==================== 工作流状态测试 ====================

    def test_get_workflow_state_returns_snapshot(self, client):
        """测试：获取工作流状态返回快照"""
        # 先模拟启动一个工作流
        with patch("src.interfaces.api.routes.coordinator_status.get_coordinator") as mock_get:
            mock_coordinator = MagicMock()
            mock_coordinator.get_workflow_state.return_value = {
                "workflow_id": "wf_123",
                "status": "running",
                "node_count": 3,
                "executed_nodes": ["node_1"],
                "running_nodes": ["node_2"],
                "failed_nodes": [],
                "node_inputs": {},
                "node_outputs": {"node_1": {"result": "data"}},
                "node_errors": {},
                "started_at": "2025-01-01T00:00:00",
            }
            mock_get.return_value = mock_coordinator

            response = client.get("/api/coordinator/workflows/wf_123")

            assert response.status_code == 200
            data = response.json()
            assert data["workflow_id"] == "wf_123"
            assert data["status"] == "running"
            assert "node_1" in data["executed_nodes"]
            assert data["node_outputs"]["node_1"] == {"result": "data"}

    def test_get_unknown_workflow_returns_404(self, client):
        """测试：查询未知工作流返回404"""
        with patch("src.interfaces.api.routes.coordinator_status.get_coordinator") as mock_get:
            mock_coordinator = MagicMock()
            mock_coordinator.get_workflow_state.return_value = None
            mock_get.return_value = mock_coordinator

            response = client.get("/api/coordinator/workflows/unknown")

            assert response.status_code == 404

    def test_get_all_workflows_returns_list(self, client):
        """测试：获取所有工作流状态"""
        with patch("src.interfaces.api.routes.coordinator_status.get_coordinator") as mock_get:
            mock_coordinator = MagicMock()
            mock_coordinator.get_all_workflow_states.return_value = {
                "wf_1": {"workflow_id": "wf_1", "status": "running"},
                "wf_2": {"workflow_id": "wf_2", "status": "completed"},
            }
            mock_get.return_value = mock_coordinator

            response = client.get("/api/coordinator/workflows")

            assert response.status_code == 200
            data = response.json()
            assert len(data["workflows"]) == 2

    # ==================== SSE 流测试 ====================

    def test_stream_workflow_status_returns_sse(self, client):
        """测试：流式获取工作流状态返回 SSE"""
        with patch("src.interfaces.api.routes.coordinator_status.get_coordinator") as mock_get:
            mock_coordinator = MagicMock()
            # 使用 completed 状态使流能够正常终止
            mock_coordinator.get_workflow_state.return_value = {
                "workflow_id": "wf_123",
                "status": "completed",
                "node_count": 1,
                "executed_nodes": ["node_1"],
                "running_nodes": [],
                "failed_nodes": [],
                "node_inputs": {},
                "node_outputs": {"node_1": {"result": "done"}},
                "node_errors": {},
                "started_at": "2025-01-01T00:00:00",
                "result": {"status": "success"},
            }
            mock_get.return_value = mock_coordinator

            # 使用 stream=True 获取 SSE 响应
            with client.stream("GET", "/api/coordinator/workflows/wf_123/stream") as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")

                # 读取事件直到 [DONE]
                events = []
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        event_data = line[6:]  # 去掉 "data: " 前缀
                        if event_data == "[DONE]":
                            break
                        events.append(json.loads(event_data))

                # 验证事件格式
                assert len(events) >= 1
                # 应该有 status_update 和 workflow_completed 事件
                event_types = [e.get("type") for e in events]
                assert "status_update" in event_types
                assert "workflow_completed" in event_types

    def test_stream_includes_node_status_updates(self, client):
        """测试：流包含节点状态更新"""
        # 这个测试验证当工作流执行时，SSE 流会推送节点状态更新
        with patch("src.interfaces.api.routes.coordinator_status.get_coordinator") as mock_get:
            mock_coordinator = MagicMock()

            # 模拟状态变化序列：running -> running -> completed
            states = [
                {
                    "workflow_id": "wf_123",
                    "status": "running",
                    "running_nodes": ["node_1"],
                    "executed_nodes": [],
                    "failed_nodes": [],
                    "node_outputs": {},
                },
                {
                    "workflow_id": "wf_123",
                    "status": "running",
                    "running_nodes": [],
                    "executed_nodes": ["node_1"],
                    "failed_nodes": [],
                    "node_outputs": {"node_1": {"result": "data"}},
                },
                {
                    "workflow_id": "wf_123",
                    "status": "completed",
                    "running_nodes": [],
                    "executed_nodes": ["node_1"],
                    "failed_nodes": [],
                    "node_outputs": {"node_1": {"result": "data"}},
                    "result": {"status": "success"},
                },
            ]
            mock_coordinator.get_workflow_state.side_effect = states
            mock_get.return_value = mock_coordinator

            with client.stream(
                "GET", "/api/coordinator/workflows/wf_123/stream?poll_interval=0.1"
            ) as response:
                assert response.status_code == 200

                # 收集所有事件
                events = []
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        event_data = line[6:]
                        if event_data == "[DONE]":
                            break
                        events.append(json.loads(event_data))

                # 验证有状态更新和节点事件
                event_types = [e.get("type") for e in events]
                assert "status_update" in event_types
                # 应该检测到节点开始运行和完成
                assert "node_started" in event_types or "node_completed" in event_types


class TestCoordinatorStatusDTO:
    """协调者状态 DTO 测试"""

    def test_workflow_state_response_serialization(self):
        """测试：工作流状态响应序列化"""
        from datetime import datetime

        from src.interfaces.api.dto.coordinator_dto import WorkflowStateResponse

        state = WorkflowStateResponse(
            workflow_id="wf_123",
            status="running",
            node_count=3,
            executed_nodes=["node_1"],
            running_nodes=["node_2"],
            failed_nodes=[],
            node_inputs={"node_2": {"prompt": "test"}},
            node_outputs={"node_1": {"result": "data"}},
            node_errors={},
            started_at=datetime.now(),
            completed_at=None,
            result=None,
        )

        # 验证可以转换为 dict
        data = state.model_dump()
        assert data["workflow_id"] == "wf_123"
        assert data["status"] == "running"

    def test_system_status_response_serialization(self):
        """测试：系统状态响应序列化"""
        from src.interfaces.api.dto.coordinator_dto import SystemStatusResponse

        status = SystemStatusResponse(
            total_workflows=10,
            running_workflows=3,
            completed_workflows=5,
            failed_workflows=2,
            active_nodes=5,
            decision_statistics={
                "total": 100,
                "passed": 90,
                "rejected": 10,
                "rejection_rate": 0.1,
            },
        )

        data = status.model_dump()
        assert data["total_workflows"] == 10
        assert data["active_nodes"] == 5


class TestCoordinatorSSEEvents:
    """协调者 SSE 事件测试"""

    def test_sse_event_format(self):
        """测试：SSE 事件格式正确"""
        from src.interfaces.api.routes.coordinator_status import format_sse_event

        event_data = {"type": "status_update", "workflow_id": "wf_123"}
        sse_message = format_sse_event(event_data)

        assert sse_message.startswith("data: ")
        assert sse_message.endswith("\n\n")
        assert "wf_123" in sse_message

    def test_sse_done_event_format(self):
        """测试：SSE DONE 事件格式正确"""
        from src.interfaces.api.routes.coordinator_status import format_sse_done

        done_message = format_sse_done()
        assert done_message == "data: [DONE]\n\n"

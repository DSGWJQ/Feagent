"""测试：上下文压缩 API 端点

测试目标：
1. GET /coordinator/workflows/{workflow_id}/context - 获取压缩上下文
2. GET /coordinator/workflows/{workflow_id}/context/stream - SSE 实时推送
3. 验证响应格式和数据一致性

完成标准：
- API 端点返回正确的压缩上下文
- SSE 能实时推送上下文变化
- 错误处理正确
"""

import pytest
from fastapi.testclient import TestClient

# ==================== 测试1：获取压缩上下文 API ====================


class TestGetCompressedContextAPI:
    """测试获取压缩上下文 API"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    @pytest.fixture
    def setup_coordinator_with_context(self, client):
        """设置 Coordinator 并创建测试上下文"""
        import src.interfaces.api.routes.coordinator_status as coord_module
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextCompressor,
            ContextSnapshotManager,
        )

        # 重置全局协调者
        coord_module._coordinator = None
        coordinator = coord_module.get_coordinator()
        coordinator.context_compressor = ContextCompressor()
        coordinator.snapshot_manager = ContextSnapshotManager()
        coordinator._is_compressing_context = True

        # 创建测试上下文
        test_context = CompressedContext(
            workflow_id="test_wf_001",
            task_goal="分析销售数据",
            execution_status={"status": "running", "progress": 0.5},
            node_summary=[
                {"node_id": "n1", "status": "completed"},
                {"node_id": "n2", "status": "running"},
            ],
            decision_history=[],
            reflection_summary={"assessment": "进展顺利", "confidence": 0.85},
            conversation_summary="用户请求分析数据",
            error_log=[],
            next_actions=["执行下一节点"],
        )

        coordinator._compressed_contexts["test_wf_001"] = test_context
        coordinator.snapshot_manager.save_snapshot(test_context)

        return coordinator

    def test_get_compressed_context_success(self, client, setup_coordinator_with_context):
        """成功获取压缩上下文"""
        response = client.get("/api/coordinator/workflows/test_wf_001/context")

        assert response.status_code == 200
        data = response.json()

        assert data["workflow_id"] == "test_wf_001"
        assert data["task_goal"] == "分析销售数据"
        assert data["execution_status"]["status"] == "running"
        assert len(data["node_summary"]) == 2

    def test_get_compressed_context_not_found(self, client):
        """获取不存在的上下文应返回 404"""
        response = client.get("/api/coordinator/workflows/nonexistent_wf/context")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_compressed_context_includes_summary_text(
        self, client, setup_coordinator_with_context
    ):
        """响应应包含摘要文本"""
        response = client.get("/api/coordinator/workflows/test_wf_001/context")

        assert response.status_code == 200
        data = response.json()

        assert "summary_text" in data
        assert len(data["summary_text"]) > 0


# ==================== 测试2：上下文历史 API ====================


class TestContextHistoryAPI:
    """测试上下文历史 API"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    @pytest.fixture
    def setup_coordinator_with_history(self, client):
        """设置 Coordinator 并创建多个历史版本"""
        import src.interfaces.api.routes.coordinator_status as coord_module
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextCompressor,
            ContextSnapshotManager,
        )

        # 重置全局协调者
        coord_module._coordinator = None
        coordinator = coord_module.get_coordinator()
        coordinator.context_compressor = ContextCompressor()
        coordinator.snapshot_manager = ContextSnapshotManager()
        coordinator._is_compressing_context = True

        # 创建多个版本
        for i in range(3):
            context = CompressedContext(
                workflow_id="history_wf",
                task_goal=f"目标版本 {i + 1}",
                version=i + 1,
            )
            coordinator.snapshot_manager.save_snapshot(context)

        return coordinator

    def test_get_context_history(self, client, setup_coordinator_with_history):
        """获取上下文历史"""
        response = client.get("/api/coordinator/workflows/history_wf/context/history")

        assert response.status_code == 200
        data = response.json()

        assert "snapshots" in data
        assert len(data["snapshots"]) == 3


# ==================== 测试3：SSE 流式推送 ====================


class TestContextSSEStream:
    """测试上下文 SSE 流式推送"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    @pytest.fixture
    def setup_coordinator_for_stream(self, client):
        """设置 Coordinator 用于流测试"""
        import src.interfaces.api.routes.coordinator_status as coord_module
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextCompressor,
            ContextSnapshotManager,
        )

        # 重置全局协调者
        coord_module._coordinator = None
        coordinator = coord_module.get_coordinator()
        coordinator.context_compressor = ContextCompressor()
        coordinator.snapshot_manager = ContextSnapshotManager()
        coordinator._is_compressing_context = True

        # 创建初始上下文
        context = CompressedContext(
            workflow_id="stream_wf",
            task_goal="流测试",
            execution_status={"status": "running", "progress": 0.0},
        )
        coordinator._compressed_contexts["stream_wf"] = context
        coordinator.snapshot_manager.save_snapshot(context)

        return coordinator

    def test_sse_stream_returns_event_source_response(self, client, setup_coordinator_for_stream):
        """SSE 流应返回正确的内容类型"""
        with client.stream(
            "GET", "/api/coordinator/workflows/stream_wf/context/stream"
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

    def test_sse_stream_sends_initial_context(self, client, setup_coordinator_for_stream):
        """SSE 流应发送初始上下文"""

        events = []
        with client.stream(
            "GET",
            "/api/coordinator/workflows/stream_wf/context/stream",
            params={"timeout": 1},
        ) as response:
            for line in response.iter_lines():
                if line:
                    events.append(line)
                if len(events) >= 2:  # 至少收到一个事件
                    break

        # 应该收到至少一个事件
        assert len(events) >= 1


# ==================== 测试4：错误处理 ====================


class TestContextAPIErrorHandling:
    """测试错误处理"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    def test_invalid_workflow_id_format(self, client):
        """无效的工作流 ID 格式"""
        # 使用特殊字符
        response = client.get("/api/coordinator/workflows/invalid<>wf/context")

        # 应该返回 404 或 400
        assert response.status_code in [400, 404]

    def test_compression_disabled_returns_appropriate_response(self, client):
        """压缩未启用时的响应"""
        import src.interfaces.api.routes.coordinator_status as coord_module

        # 重置全局协调者
        coord_module._coordinator = None
        coordinator = coord_module.get_coordinator()
        coordinator._is_compressing_context = False
        coordinator._compressed_contexts = {}

        response = client.get("/api/coordinator/workflows/any_wf/context")

        # 应该返回 404（未找到）或 503（服务不可用）
        assert response.status_code in [404, 503]


# ==================== 测试5：响应格式验证 ====================


class TestContextResponseFormat:
    """测试响应格式"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    @pytest.fixture
    def setup_complete_context(self, client):
        """设置完整的测试上下文"""
        import src.interfaces.api.routes.coordinator_status as coord_module
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextCompressor,
            ContextSnapshotManager,
        )

        # 重置全局协调者
        coord_module._coordinator = None
        coordinator = coord_module.get_coordinator()
        coordinator.context_compressor = ContextCompressor()
        coordinator.snapshot_manager = ContextSnapshotManager()
        coordinator._is_compressing_context = True

        context = CompressedContext(
            workflow_id="format_wf",
            task_goal="完整测试",
            execution_status={"status": "completed", "progress": 1.0},
            node_summary=[
                {"node_id": "n1", "status": "completed", "output_summary": "结果1"},
            ],
            decision_history=[{"decision_type": "model", "choice": "gpt-4"}],
            reflection_summary={
                "assessment": "执行成功",
                "confidence": 0.95,
                "recommendations": ["优化缓存"],
            },
            conversation_summary="用户请求完成",
            error_log=[],
            next_actions=["归档结果"],
            version=5,
            evidence_refs=["ref_001", "ref_002"],
        )

        coordinator._compressed_contexts["format_wf"] = context
        coordinator.snapshot_manager.save_snapshot(context)

        return coordinator

    def test_response_contains_all_eight_segments(self, client, setup_complete_context):
        """响应应包含所有八个段"""
        response = client.get("/api/coordinator/workflows/format_wf/context")

        assert response.status_code == 200
        data = response.json()

        # 验证八段都存在
        assert "task_goal" in data
        assert "execution_status" in data
        assert "node_summary" in data
        assert "decision_history" in data
        assert "reflection_summary" in data
        assert "conversation_summary" in data
        assert "error_log" in data
        assert "next_actions" in data

    def test_response_contains_metadata(self, client, setup_complete_context):
        """响应应包含元数据"""
        response = client.get("/api/coordinator/workflows/format_wf/context")

        assert response.status_code == 200
        data = response.json()

        assert "workflow_id" in data
        assert "version" in data
        assert "created_at" in data

    def test_response_datetime_format(self, client, setup_complete_context):
        """日期时间格式应为 ISO 格式"""
        response = client.get("/api/coordinator/workflows/format_wf/context")

        assert response.status_code == 200
        data = response.json()

        # created_at 应为 ISO 格式
        from datetime import datetime

        try:
            datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Invalid datetime format: {data['created_at']}")

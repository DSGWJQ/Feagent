"""Phase 3: Conversation Stream API 集成测试

测试 /api/conversation/stream 端点的完整流式功能。

完成标准:
1. 通过测试看到 "Thought/Tool/Result" 逐条流式输出
2. 测试断开连接清理机制
3. 测试会话状态查询
"""

import json

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.main import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestConversationStreamAPI:
    """测试 Conversation Stream API"""

    def test_stream_endpoint_exists(self, client: TestClient):
        """测试: /conversation/stream 端点存在"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "你好"},
        )

        # 端点应该存在并返回 200
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_returns_sse_format(self, client: TestClient):
        """测试: 端点返回 SSE 格式"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试消息"},
        )

        assert response.status_code == 200

        # 验证响应头
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("Connection") == "keep-alive"

        # 验证 SSE 格式
        content = response.text
        assert "data:" in content

    def test_stream_includes_thinking_event(self, client: TestClient):
        """测试: 流包含 thinking 事件"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "分析这个请求"},
        )

        assert response.status_code == 200

        # 解析事件
        events = self._parse_sse_events(response.text)

        # 应该有 thinking 事件
        thinking_events = [e for e in events if e.get("type") == "thinking"]
        assert len(thinking_events) >= 1, "应该至少有一个 thinking 事件"

    def test_stream_includes_final_event(self, client: TestClient):
        """测试: 流包含 final 事件"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "完成请求"},
        )

        assert response.status_code == 200

        events = self._parse_sse_events(response.text)

        # 应该有 final 事件
        final_events = [e for e in events if e.get("type") == "final"]
        assert len(final_events) == 1, "应该有一个 final 事件"

    def test_stream_ends_with_done_marker(self, client: TestClient):
        """测试: 流以 [DONE] 结束"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )

        assert response.status_code == 200
        assert "[DONE]" in response.text

    def test_stream_with_workflow_id(self, client: TestClient):
        """测试: 带 workflow_id 的流式请求包含工具调用"""
        response = client.post(
            "/api/conversation/stream",
            json={
                "message": "分析工作流",
                "workflow_id": "test_workflow_123",
            },
        )

        assert response.status_code == 200

        events = self._parse_sse_events(response.text)

        # 应该有 tool_call 和 tool_result 事件
        event_types = [e.get("type") for e in events]
        assert "tool_call" in event_types, "应该有 tool_call 事件"
        assert "tool_result" in event_types, "应该有 tool_result 事件"

    def test_stream_events_have_sequence(self, client: TestClient):
        """测试: 事件有序列号"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )

        events = self._parse_sse_events(response.text)

        # 验证序列号递增
        sequences = [e.get("sequence") for e in events if "sequence" in e]
        assert sequences == sorted(sequences), "序列号应该递增"

    def test_stream_events_have_timestamp(self, client: TestClient):
        """测试: 事件有时间戳"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )

        events = self._parse_sse_events(response.text)

        # 验证时间戳存在
        for event in events:
            assert "timestamp" in event, f"事件应该有时间戳: {event}"

    def test_stream_returns_session_id_header(self, client: TestClient):
        """测试: 响应头包含 session_id"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )

        assert response.status_code == 200
        assert "X-Session-ID" in response.headers

    def _parse_sse_events(self, content: str) -> list[dict]:
        """解析 SSE 事件"""
        events = []
        for line in content.strip().split("\n"):
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str != "[DONE]":
                    try:
                        events.append(json.loads(data_str))
                    except json.JSONDecodeError:
                        pass
        return events


class TestConversationStreamComplete:
    """测试完整的对话流程"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_complete_react_flow(self, client: TestClient):
        """测试: 完整的 ReAct 流程"""
        response = client.post(
            "/api/conversation/stream",
            json={
                "message": "帮我分析这个工作流",
                "workflow_id": "wf_001",
            },
        )

        assert response.status_code == 200

        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and line[6:] != "[DONE]":
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        # 验证 ReAct 流程
        event_types = [e.get("type") for e in events]

        # 应该有思考 -> 工具调用 -> 工具结果 -> 最终响应
        assert event_types.count("thinking") >= 1
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "final" in event_types

        # 验证最终响应包含工作流信息
        final_event = next(e for e in events if e.get("type") == "final")
        assert "wf_001" in final_event.get("content", "") or "工作流" in final_event.get(
            "content", ""
        )

    def test_event_order_preserved(self, client: TestClient):
        """测试: 事件顺序保持正确"""
        response = client.post(
            "/api/conversation/stream",
            json={
                "message": "测试顺序",
                "workflow_id": "wf_order",
            },
        )

        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and line[6:] != "[DONE]":
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        # 验证事件顺序
        event_types = [e.get("type") for e in events]

        # thinking 应该在 tool_call 之前
        if "thinking" in event_types and "tool_call" in event_types:
            first_thinking = event_types.index("thinking")
            first_tool_call = event_types.index("tool_call")
            assert first_thinking < first_tool_call, "thinking 应该在 tool_call 之前"

        # tool_call 应该在 tool_result 之前
        if "tool_call" in event_types and "tool_result" in event_types:
            tool_call_idx = event_types.index("tool_call")
            tool_result_idx = event_types.index("tool_result")
            assert tool_call_idx < tool_result_idx, "tool_call 应该在 tool_result 之前"

        # final 应该在最后
        if "final" in event_types:
            final_idx = event_types.index("final")
            assert final_idx == len(event_types) - 1, "final 应该是最后一个事件"


class TestConversationStreamSession:
    """测试会话管理"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint(self, client: TestClient):
        """测试: 健康检查端点"""
        response = client.get("/api/conversation/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "active_sessions" in data

    def test_session_cancel(self, client: TestClient):
        """测试: 取消会话"""
        # 首先创建一个会话
        stream_response = client.post(
            "/api/conversation/stream",
            json={"message": "测试"},
        )
        session_id = stream_response.headers.get("X-Session-ID")

        if session_id:
            # 取消会话
            cancel_response = client.delete(f"/api/conversation/stream/{session_id}")
            assert cancel_response.status_code == 200
            assert cancel_response.json()["status"] == "cancelled"


class TestSSEEventContent:
    """测试 SSE 事件内容"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_thinking_event_content(self, client: TestClient):
        """测试: thinking 事件包含思考内容"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "分析请求"},
        )

        events = self._parse_events(response.text)
        thinking = next((e for e in events if e.get("type") == "thinking"), None)

        assert thinking is not None
        assert "content" in thinking
        assert len(thinking["content"]) > 0

    def test_tool_call_event_metadata(self, client: TestClient):
        """测试: tool_call 事件包含工具元数据"""
        response = client.post(
            "/api/conversation/stream",
            json={
                "message": "查询工作流",
                "workflow_id": "wf_meta",
            },
        )

        events = self._parse_events(response.text)
        tool_call = next((e for e in events if e.get("type") == "tool_call"), None)

        assert tool_call is not None
        assert "metadata" in tool_call
        metadata = tool_call["metadata"]
        assert "tool_name" in metadata
        assert "tool_id" in metadata

    def test_tool_result_event_success(self, client: TestClient):
        """测试: tool_result 事件包含成功状态"""
        response = client.post(
            "/api/conversation/stream",
            json={
                "message": "执行工作流",
                "workflow_id": "wf_result",
            },
        )

        events = self._parse_events(response.text)
        tool_result = next((e for e in events if e.get("type") == "tool_result"), None)

        assert tool_result is not None
        assert "metadata" in tool_result
        assert tool_result["metadata"].get("success") is True

    def test_final_event_is_marked_final(self, client: TestClient):
        """测试: final 事件标记为 is_final"""
        response = client.post(
            "/api/conversation/stream",
            json={"message": "完成"},
        )

        events = self._parse_events(response.text)
        final = next((e for e in events if e.get("type") == "final"), None)

        assert final is not None
        assert final.get("is_final") is True

    def _parse_events(self, content: str) -> list[dict]:
        events = []
        for line in content.strip().split("\n"):
            if line.startswith("data: ") and line[6:] != "[DONE]":
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return events


# 导出
__all__ = [
    "TestConversationStreamAPI",
    "TestConversationStreamComplete",
    "TestConversationStreamSession",
    "TestSSEEventContent",
]

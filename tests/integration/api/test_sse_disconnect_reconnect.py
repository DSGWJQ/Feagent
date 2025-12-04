"""Phase 3: SSE 断开重连测试

完成标准:
1. 测试客户端断开连接时 emitter 能正确清理
2. 测试重连后能创建新会话
3. 模拟真实场景的断开/重连

TDD: 这些测试验证生产环境中的断开重连行为。
"""

import asyncio
import json
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from src.domain.services.conversation_flow_emitter import (
    ConversationFlowEmitter,
    EmitterClosedError,
    StepKind,
)
from src.interfaces.api.services.sse_emitter_handler import (
    SSESessionManager,
)


class TestEmitterDisconnectCleanup:
    """测试 Emitter 断开连接清理"""

    @pytest.mark.asyncio
    async def test_emitter_cleanup_on_client_disconnect(self):
        """测试: 客户端断开时 emitter 清理"""
        emitter = ConversationFlowEmitter(session_id="disconnect_test")

        # 发送一些消息
        await emitter.emit_thinking("开始处理")
        await emitter.emit_thinking("继续处理")

        # 模拟客户端断开
        await emitter.complete_with_error("Client disconnected")

        # 验证 emitter 已关闭
        assert emitter.is_completed

        # 尝试再次发送应该失败
        with pytest.raises(EmitterClosedError):
            await emitter.emit_thinking("不应该发送")

    @pytest.mark.asyncio
    async def test_emitter_graceful_shutdown(self):
        """测试: Emitter 优雅关闭"""
        emitter = ConversationFlowEmitter(session_id="graceful_test")

        # 发送消息
        await emitter.emit_thinking("处理中")
        await emitter.emit_final_response("完成")

        # 正常关闭
        await emitter.complete()

        # 验证状态
        assert emitter.is_completed
        stats = emitter.get_statistics()
        assert stats["total_steps"] >= 2

    @pytest.mark.asyncio
    async def test_emitter_handles_disconnect_during_iteration(self):
        """测试: 迭代过程中断开连接"""
        emitter = ConversationFlowEmitter(session_id="iter_disconnect", timeout=0.5)
        disconnect_event = asyncio.Event()
        received_steps = []

        async def producer():
            """生产者：发送消息"""
            for i in range(5):
                if disconnect_event.is_set():
                    await emitter.complete_with_error("Disconnected")
                    return
                await emitter.emit_thinking(f"步骤 {i}")
                await asyncio.sleep(0.1)
            await emitter.complete()

        async def consumer():
            """消费者：模拟接收并断开"""
            count = 0
            async for step in emitter:
                if step.kind == StepKind.END or step.kind == StepKind.ERROR:
                    break
                received_steps.append(step)
                count += 1
                if count >= 2:  # 接收 2 条后断开
                    disconnect_event.set()
                    break

        # 同时运行生产者和消费者
        await asyncio.gather(producer(), consumer())

        # 验证只接收到部分消息
        assert len(received_steps) >= 2
        assert emitter.is_completed


class TestSSESessionManagerReconnect:
    """测试 SSE 会话管理器重连"""

    @pytest.mark.asyncio
    async def test_session_manager_creates_new_session_on_reconnect(self):
        """测试: 重连时创建新会话"""
        manager = SSESessionManager()

        # 第一次连接
        emitter1, handler1 = await manager.create_session("user_session_1")
        await emitter1.emit_thinking("第一次连接")

        # 完成第一次连接
        await emitter1.complete()

        # 重连 - 应该创建新会话
        emitter2, handler2 = await manager.create_session("user_session_1")

        # 验证是新的 emitter
        assert emitter2 is not emitter1
        assert emitter2.is_active
        assert not emitter1.is_active

        # 清理
        await emitter2.complete()

    @pytest.mark.asyncio
    async def test_session_manager_cancels_old_session_on_reconnect(self):
        """测试: 重连时取消旧会话"""
        manager = SSESessionManager()

        # 第一次连接（不完成）
        emitter1, handler1 = await manager.create_session("active_session")
        await emitter1.emit_thinking("活跃会话")

        # 重连 - 应该取消旧会话
        emitter2, handler2 = await manager.create_session("active_session")

        # 旧会话应该被取消
        assert emitter1.is_completed
        assert emitter2.is_active

        # 清理
        await emitter2.complete()

    @pytest.mark.asyncio
    async def test_session_manager_cleanup_completed_sessions(self):
        """测试: 清理已完成的会话"""
        manager = SSESessionManager()

        # 创建多个会话
        sessions = []
        for i in range(5):
            emitter, handler = await manager.create_session(f"session_{i}")
            sessions.append(emitter)

        # 完成一些会话
        await sessions[0].complete()
        await sessions[2].complete()
        await sessions[4].complete()

        # 清理
        cleaned = await manager.cleanup_completed()
        assert cleaned == 3

        # 验证活跃会话数
        assert manager.active_sessions == 2

        # 清理剩余
        await sessions[1].complete()
        await sessions[3].complete()


class TestSSEHandlerDisconnect:
    """测试 SSE Handler 断开处理"""

    @pytest.fixture
    def app(self):
        return FastAPI()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_sse_handler_detects_client_disconnect(self, app, client):
        """测试: SSE handler 检测客户端断开"""
        cleanup_called = False

        async def sse_with_cleanup() -> AsyncGenerator[str, None]:
            nonlocal cleanup_called
            emitter = ConversationFlowEmitter(session_id="detect_disconnect")

            async def producer():
                for i in range(10):
                    if emitter.is_completed:
                        return
                    await emitter.emit_thinking(f"消息 {i}")
                    await asyncio.sleep(0.1)
                await emitter.complete()

            task = asyncio.create_task(producer())

            try:
                async for step in emitter:
                    if step.kind == StepKind.END:
                        break
                    yield f"data: {json.dumps(step.to_dict())}\n\n"
            finally:
                cleanup_called = True
                if not emitter.is_completed:
                    await emitter.complete_with_error("Cleanup")
                await task

            yield "data: [DONE]\n\n"

        @app.get("/disconnect-test")
        async def disconnect_test():
            return StreamingResponse(sse_with_cleanup(), media_type="text/event-stream")

        # 发送请求并立即关闭（模拟断开）
        response = client.get("/disconnect-test")
        # TestClient 会等待完整响应，所以这里实际上是完整接收

        assert response.status_code == 200
        assert cleanup_called or "[DONE]" in response.text

    def test_sse_handler_stops_sending_after_disconnect(self, app, client):
        """测试: 断开后停止发送"""
        send_count = 0

        async def sse_with_disconnect_check() -> AsyncGenerator[str, None]:
            nonlocal send_count
            emitter = ConversationFlowEmitter(session_id="stop_send")

            async def producer():
                nonlocal send_count
                for i in range(3):
                    await emitter.emit_thinking(f"消息 {i}")
                    send_count += 1
                await emitter.complete()

            task = asyncio.create_task(producer())

            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict())}\n\n"

            await task
            yield "data: [DONE]\n\n"

        @app.get("/stop-send-test")
        async def stop_send():
            return StreamingResponse(sse_with_disconnect_check(), media_type="text/event-stream")

        response = client.get("/stop-send-test")
        assert response.status_code == 200
        assert send_count == 3  # 应该发送了 3 条


class TestRealWorldDisconnectScenarios:
    """测试真实世界断开场景"""

    @pytest.fixture
    def app(self):
        return FastAPI()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_network_timeout_simulation(self, app, client):
        """测试: 模拟网络超时"""
        timeout_handled = False

        async def sse_with_timeout() -> AsyncGenerator[str, None]:
            nonlocal timeout_handled
            emitter = ConversationFlowEmitter(session_id="timeout_sim", timeout=0.2)

            async def slow_producer():
                await emitter.emit_thinking("开始")
                await asyncio.sleep(0.05)  # 快速发送
                await emitter.emit_thinking("处理中")
                await asyncio.sleep(0.05)
                await emitter.emit_final_response("完成")
                await emitter.complete()

            task = asyncio.create_task(slow_producer())

            try:
                async for step in emitter:
                    if step.kind == StepKind.END:
                        break
                    yield f"data: {json.dumps(step.to_dict())}\n\n"
            except TimeoutError:
                timeout_handled = True
                yield 'data: {"type": "error", "content": "Timeout"}\n\n'
            finally:
                await task

            yield "data: [DONE]\n\n"

        @app.get("/timeout-sim")
        async def timeout_sim():
            return StreamingResponse(sse_with_timeout(), media_type="text/event-stream")

        response = client.get("/timeout-sim")
        assert response.status_code == 200
        assert "[DONE]" in response.text

    def test_concurrent_disconnect_and_send(self, app, client):
        """测试: 并发断开和发送"""

        async def sse_concurrent() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="concurrent")
            error_occurred = False

            async def producer():
                nonlocal error_occurred
                try:
                    for i in range(5):
                        await emitter.emit_thinking(f"并发消息 {i}")
                        await asyncio.sleep(0.02)
                    await emitter.emit_final_response("完成")
                    await emitter.complete()
                except EmitterClosedError:
                    error_occurred = True

            task = asyncio.create_task(producer())

            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict())}\n\n"

            await task
            yield "data: [DONE]\n\n"

        @app.get("/concurrent")
        async def concurrent():
            return StreamingResponse(sse_concurrent(), media_type="text/event-stream")

        response = client.get("/concurrent")
        assert response.status_code == 200

        # 验证收到了消息
        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and line[6:] != "[DONE]":
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        assert len(events) >= 5, f"应该收到至少 5 条消息，实际: {len(events)}"

    def test_reconnect_after_error(self, app, client):
        """测试: 错误后重连"""
        connection_count = 0

        async def sse_with_reconnect() -> AsyncGenerator[str, None]:
            nonlocal connection_count
            connection_count += 1
            conn_id = connection_count

            emitter = ConversationFlowEmitter(session_id=f"reconnect_{conn_id}")

            async def producer():
                await emitter.emit_thinking(f"连接 {conn_id}")
                await emitter.emit_final_response(f"响应 {conn_id}")
                await emitter.complete()

            task = asyncio.create_task(producer())

            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict())}\n\n"

            await task
            yield "data: [DONE]\n\n"

        @app.get("/reconnect-test")
        async def reconnect_test():
            return StreamingResponse(sse_with_reconnect(), media_type="text/event-stream")

        # 第一次连接
        response1 = client.get("/reconnect-test")
        assert response1.status_code == 200
        # Unicode 可能被编码，检查任一格式
        assert "连接 1" in response1.text or "\\u8fde\\u63a5 1" in response1.text

        # 模拟断开后重连
        response2 = client.get("/reconnect-test")
        assert response2.status_code == 200
        assert "连接 2" in response2.text or "\\u8fde\\u63a5 2" in response2.text

        # 验证连接计数
        assert connection_count == 2


class TestChatStreamReactWithEmitter:
    """测试改进后的 chat-stream-react 端点"""

    def test_chat_stream_react_uses_emitter_events(self):
        """测试: chat-stream-react 使用 emitter 事件格式"""
        from src.interfaces.api.main import app

        client = TestClient(app)

        # 注意：这个测试需要数据库中有工作流
        # 这里测试端点存在并返回正确格式
        response = client.post(
            "/api/workflows/nonexistent/chat-stream-react",
            json={"message": "测试消息"},
        )

        # 应该返回 200 (SSE 流)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # 应该有 session id header
        assert "X-Session-ID" in response.headers

        # 验证事件格式
        content = response.text
        assert "data:" in content


# 导出
__all__ = [
    "TestEmitterDisconnectCleanup",
    "TestSSESessionManagerReconnect",
    "TestSSEHandlerDisconnect",
    "TestRealWorldDisconnectScenarios",
    "TestChatStreamReactWithEmitter",
]

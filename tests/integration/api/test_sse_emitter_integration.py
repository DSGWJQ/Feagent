"""Phase 3: SSE + Emitter 集成测试

测试 SSE handler 从 ConversationFlowEmitter 接收消息并流式输出。

完成标准:
1. SSE handler 从 emitter 的 queue 中 await 消息并发送给前端
2. 断开连接时 emitter 能清理
3. 通过测试模拟前端断开、重连
4. 看到 "Thought/Tool/Result" 逐条流式输出
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


class TestSSEEmitterIntegration:
    """测试 SSE 与 Emitter 的集成"""

    @pytest.fixture
    def app(self):
        """创建测试 FastAPI 应用"""
        app = FastAPI()
        return app

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return TestClient(app)

    # ============== 基础 SSE 流测试 ==============

    def test_sse_streams_emitter_steps(self, app, client):
        """测试: SSE 能够流式传输 emitter 的步骤"""

        async def sse_from_emitter() -> AsyncGenerator[str, None]:
            """从 emitter 生成 SSE 事件"""
            emitter = ConversationFlowEmitter(session_id="test_session")

            # 模拟 ConversationAgent 发送步骤
            async def agent_work():
                await asyncio.sleep(0.01)
                await emitter.emit_thinking("正在分析您的请求...")
                await asyncio.sleep(0.01)
                await emitter.emit_tool_call(
                    tool_name="search",
                    tool_id="tool_1",
                    arguments={"query": "test"},
                )
                await asyncio.sleep(0.01)
                await emitter.emit_tool_result(
                    tool_id="tool_1",
                    result={"data": "result"},
                    success=True,
                )
                await asyncio.sleep(0.01)
                await emitter.emit_final_response("这是最终响应")
                await emitter.complete()

            # 启动 agent 工作
            task = asyncio.create_task(agent_work())

            # 从 emitter 流式输出
            try:
                async for step in emitter:
                    if step.kind == StepKind.END:
                        yield "data: [DONE]\n\n"
                        break
                    event_data = json.dumps(step.to_dict(), ensure_ascii=False)
                    yield f"data: {event_data}\n\n"
            finally:
                await task

        @app.get("/test-stream")
        async def test_stream():
            return StreamingResponse(
                sse_from_emitter(),
                media_type="text/event-stream",
            )

        response = client.get("/test-stream")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # 解析事件
        lines = response.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str != "[DONE]":
                    events.append(json.loads(data_str))

        # 验证事件顺序
        assert len(events) >= 4, f"应该有至少 4 个事件，实际: {len(events)}"

        kinds = [e["kind"] for e in events]
        assert "thinking" in kinds, "应该包含 thinking 事件"
        assert "tool_call" in kinds, "应该包含 tool_call 事件"
        assert "tool_result" in kinds, "应该包含 tool_result 事件"
        assert "final" in kinds, "应该包含 final 事件"

    def test_sse_includes_thought_content(self, app, client):
        """测试: SSE 事件包含 Thought 内容"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="test")

            async def agent():
                await emitter.emit_thinking("我需要先理解用户的需求")
                await emitter.emit_reasoning("根据上下文，用户想要...")
                await emitter.emit_final_response("完成")
                await emitter.complete()

            task = asyncio.create_task(agent())
            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                # 使用 ensure_ascii=False 保持中文原样
                yield f"data: {json.dumps(step.to_dict(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/thought-stream")
        async def thought_stream():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/thought-stream")
        content = response.text

        # 验证思考内容 (检查 Unicode 或原始中文)
        assert "thinking" in content
        # 内容可能是 Unicode 编码或原始中文
        assert "理解" in content or "\\u7406\\u89e3" in content

    def test_sse_includes_tool_details(self, app, client):
        """测试: SSE 事件包含 Tool 调用详情"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="test")

            async def agent():
                await emitter.emit_tool_call(
                    tool_name="calculator",
                    tool_id="calc_001",
                    arguments={"expression": "2+2"},
                )
                await emitter.emit_tool_result(
                    tool_id="calc_001",
                    result=4,
                    success=True,
                )
                await emitter.complete()

            task = asyncio.create_task(agent())
            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict())}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/tool-stream")
        async def tool_stream():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/tool-stream")

        # 解析事件
        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and line[6:] != "[DONE]":
                events.append(json.loads(line[6:]))

        # 验证工具调用事件
        tool_call = next((e for e in events if e["kind"] == "tool_call"), None)
        assert tool_call is not None
        assert tool_call["metadata"]["tool_name"] == "calculator"
        assert tool_call["metadata"]["tool_id"] == "calc_001"

        # 验证工具结果事件
        tool_result = next((e for e in events if e["kind"] == "tool_result"), None)
        assert tool_result is not None
        assert tool_result["metadata"]["result"] == 4
        assert tool_result["metadata"]["success"] is True

    def test_sse_includes_result_content(self, app, client):
        """测试: SSE 事件包含 Result 内容"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="test")

            async def agent():
                await emitter.emit_final_response("任务已完成，结果如下：成功处理了您的请求。")
                await emitter.complete()

            task = asyncio.create_task(agent())
            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/result-stream")
        async def result_stream():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/result-stream")
        content = response.text

        assert "任务已完成" in content
        assert "final" in content


class TestSSEDisconnectHandling:
    """测试 SSE 断开连接处理"""

    @pytest.fixture
    def app(self):
        return FastAPI()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_emitter_cleanup_on_disconnect(self):
        """测试: 断开连接时 emitter 能够清理"""
        emitter = ConversationFlowEmitter(session_id="test", timeout=0.1)
        cleanup_called = False

        async def cleanup():
            nonlocal cleanup_called
            cleanup_called = True
            if not emitter.is_completed:
                await emitter.complete_with_error("Client disconnected")

        # 模拟断开连接
        await cleanup()

        assert cleanup_called
        assert emitter.is_completed

    @pytest.mark.asyncio
    async def test_emitter_stops_emitting_after_disconnect(self):
        """测试: 断开连接后 emitter 停止发送"""
        emitter = ConversationFlowEmitter(session_id="test")

        # 正常发送
        await emitter.emit_thinking("测试")
        assert emitter._queue.qsize() == 1

        # 模拟断开并关闭
        await emitter.complete_with_error("Disconnected")

        # 尝试再次发送应该失败
        with pytest.raises(EmitterClosedError):
            await emitter.emit_thinking("不应该发送")

    @pytest.mark.asyncio
    async def test_emitter_with_cancellation_token(self):
        """测试: 使用取消令牌控制 emitter"""
        emitter = ConversationFlowEmitter(session_id="test", timeout=0.5)
        cancelled = asyncio.Event()

        async def producer():
            for i in range(10):
                if cancelled.is_set():
                    await emitter.complete_with_error("Cancelled by token")
                    return
                await emitter.emit_delta(f"chunk_{i}")
                await asyncio.sleep(0.05)
            await emitter.complete()

        async def consumer_with_cancel():
            received = []
            task = asyncio.create_task(producer())

            # 接收一些消息后取消
            count = 0
            async for step in emitter:
                if step.kind == StepKind.END or step.kind == StepKind.ERROR:
                    break
                received.append(step)
                count += 1
                if count >= 3:
                    cancelled.set()
                    break

            await task
            return received

        received = await consumer_with_cancel()
        assert len(received) >= 3
        assert emitter.is_completed


class TestSSEReconnection:
    """测试 SSE 重连场景"""

    @pytest.fixture
    def app(self):
        return FastAPI()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_new_emitter_on_reconnect(self):
        """测试: 重连时创建新的 emitter"""
        # 第一个连接
        emitter1 = ConversationFlowEmitter(session_id="session_1")
        await emitter1.emit_thinking("第一次连接")
        await emitter1.complete()

        # 模拟断开后重连
        emitter2 = ConversationFlowEmitter(session_id="session_1")
        assert emitter2.is_active
        assert emitter2._sequence_counter == 0  # 新的 emitter，序列号重置

        await emitter2.emit_thinking("重连后的消息")
        assert emitter2._queue.qsize() == 1

        await emitter2.complete()

    @pytest.mark.asyncio
    async def test_session_id_tracking_for_reconnect(self):
        """测试: 通过 session_id 跟踪重连"""
        sessions = {}

        def get_or_create_emitter(session_id: str) -> ConversationFlowEmitter:
            if session_id not in sessions or sessions[session_id].is_completed:
                sessions[session_id] = ConversationFlowEmitter(session_id=session_id)
            return sessions[session_id]

        # 首次连接
        emitter1 = get_or_create_emitter("user_123")
        await emitter1.emit_thinking("首次连接")

        # 同一会话，返回相同 emitter
        emitter2 = get_or_create_emitter("user_123")
        assert emitter1 is emitter2

        # 关闭后重连，应该创建新的
        await emitter1.complete()
        emitter3 = get_or_create_emitter("user_123")
        assert emitter3 is not emitter1
        assert emitter3.is_active


class TestSSEStreamFormatting:
    """测试 SSE 流格式"""

    @pytest.fixture
    def app(self):
        return FastAPI()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_sse_correct_format(self, app, client):
        """测试: SSE 格式正确 (data: JSON\\n\\n)"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="test")

            async def agent():
                await emitter.emit_thinking("测试")
                await emitter.complete()

            task = asyncio.create_task(agent())
            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict())}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/format-test")
        async def format_test():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/format-test")

        # 验证格式
        lines = response.text.split("\n\n")
        for line in lines:
            if line.strip():
                assert line.startswith("data: "), f"每行应该以 'data: ' 开头: {line}"

    def test_sse_done_marker(self, app, client):
        """测试: SSE 流以 [DONE] 结束"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="test")

            async def agent():
                await emitter.emit_final_response("完成")
                await emitter.complete()

            task = asyncio.create_task(agent())
            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict())}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/done-test")
        async def done_test():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/done-test")

        assert "data: [DONE]" in response.text

    def test_sse_headers(self, app, client):
        """测试: SSE 响应头正确"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            yield "data: {}\n\n"

        @app.get("/headers-test")
        async def headers_test():
            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        response = client.get("/headers-test")

        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("Connection") == "keep-alive"
        assert response.headers.get("X-Accel-Buffering") == "no"


class TestSSEErrorHandling:
    """测试 SSE 错误处理"""

    @pytest.fixture
    def app(self):
        return FastAPI()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_sse_error_event(self, app, client):
        """测试: SSE 错误事件格式"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="test")

            async def agent():
                await emitter.emit_thinking("开始处理")
                await emitter.emit_error("处理失败", error_code="PROCESSING_ERROR")
                await emitter.complete()

            task = asyncio.create_task(agent())
            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/error-test")
        async def error_test():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/error-test")

        # 验证错误事件存在
        assert "error" in response.text
        assert "处理失败" in response.text
        assert "PROCESSING_ERROR" in response.text

    def test_sse_graceful_shutdown_on_error(self, app, client):
        """测试: 错误后优雅关闭"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="test")

            async def agent():
                await emitter.emit_thinking("处理中")
                # 模拟错误
                await emitter.complete_with_error("发生了意外错误")

            task = asyncio.create_task(agent())
            async for step in emitter:
                if step.kind == StepKind.END or step.kind == StepKind.ERROR:
                    yield f"data: {json.dumps(step.to_dict(), ensure_ascii=False)}\n\n"
                    if step.kind == StepKind.ERROR:
                        break
                else:
                    yield f"data: {json.dumps(step.to_dict(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/shutdown-test")
        async def shutdown_test():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/shutdown-test")

        # 应该包含错误信息和结束标记
        assert "发生了意外错误" in response.text
        assert "[DONE]" in response.text


class TestSSEWithRealConversationAgent:
    """测试 SSE 与真实 ConversationAgent 集成"""

    @pytest.fixture
    def app(self):
        return FastAPI()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_sse_with_mock_conversation_agent(self, app, client):
        """测试: SSE 与模拟的 ConversationAgent 集成"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="conv_test")

            # 模拟 ConversationAgent 的 ReAct 循环
            async def mock_react_loop():
                # Iteration 1: Think
                await emitter.emit_thinking("用户询问天气，我需要调用天气工具")

                # Iteration 1: Tool Call
                await emitter.emit_tool_call(
                    tool_name="get_weather",
                    tool_id="weather_001",
                    arguments={"city": "北京"},
                )

                # Iteration 1: Tool Result
                await emitter.emit_tool_result(
                    tool_id="weather_001",
                    result={"temperature": 25, "condition": "晴天"},
                    success=True,
                )

                # Iteration 2: Think & Respond
                await emitter.emit_thinking("获取到天气信息，可以回复用户了")
                await emitter.emit_final_response("北京今天天气晴朗，气温25度。")

                await emitter.complete()

            task = asyncio.create_task(mock_react_loop())

            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                event = {
                    "type": step.kind.value,
                    "content": step.content,
                    "metadata": step.metadata,
                    "sequence": step.sequence,
                    "timestamp": step.timestamp.isoformat(),
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"
            await task

        @app.get("/conversation-stream")
        async def conversation_stream():
            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        response = client.get("/conversation-stream")

        assert response.status_code == 200

        # 解析事件
        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and line[6:] != "[DONE]":
                events.append(json.loads(line[6:]))

        # 验证 ReAct 循环的完整事件序列
        types = [e["type"] for e in events]
        assert types.count("thinking") == 2, "应该有 2 个思考步骤"
        assert "tool_call" in types, "应该有工具调用"
        assert "tool_result" in types, "应该有工具结果"
        assert "final" in types, "应该有最终响应"

        # 验证序列号递增
        sequences = [e["sequence"] for e in events]
        assert sequences == sorted(sequences), "序列号应该递增"

    def test_sse_multi_iteration_react(self, app, client):
        """测试: SSE 多轮 ReAct 迭代"""

        async def sse_generator() -> AsyncGenerator[str, None]:
            emitter = ConversationFlowEmitter(session_id="multi_iter")

            async def multi_iteration_agent():
                # 迭代 1
                await emitter.emit_thinking("第一轮思考：分析问题")
                await emitter.emit_tool_call("analyze", "t1", {"input": "data"})
                await emitter.emit_tool_result("t1", {"analysis": "需要更多信息"})

                # 迭代 2
                await emitter.emit_thinking("第二轮思考：获取更多信息")
                await emitter.emit_tool_call("search", "t2", {"query": "more info"})
                await emitter.emit_tool_result("t2", {"results": ["info1", "info2"]})

                # 迭代 3
                await emitter.emit_thinking("第三轮思考：综合结果")
                await emitter.emit_final_response("综合分析结果...")

                await emitter.complete()

            task = asyncio.create_task(multi_iteration_agent())
            async for step in emitter:
                if step.kind == StepKind.END:
                    break
                yield f"data: {json.dumps(step.to_dict(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            await task

        @app.get("/multi-iter-stream")
        async def multi_iter():
            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        response = client.get("/multi-iter-stream")

        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and line[6:] != "[DONE]":
                events.append(json.loads(line[6:]))

        # 验证事件数量
        thinking_count = sum(1 for e in events if e["kind"] == "thinking")
        tool_call_count = sum(1 for e in events if e["kind"] == "tool_call")
        tool_result_count = sum(1 for e in events if e["kind"] == "tool_result")

        assert thinking_count == 3, f"应该有 3 个思考步骤，实际: {thinking_count}"
        assert tool_call_count == 2, f"应该有 2 个工具调用，实际: {tool_call_count}"
        assert tool_result_count == 2, f"应该有 2 个工具结果，实际: {tool_result_count}"


# 导出
__all__ = [
    "TestSSEEmitterIntegration",
    "TestSSEDisconnectHandling",
    "TestSSEReconnection",
    "TestSSEStreamFormatting",
    "TestSSEErrorHandling",
    "TestSSEWithRealConversationAgent",
]

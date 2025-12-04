"""ConversationFlowEmitter TDD 测试 - Phase 2

测试目标：
1. emit_step() - 发送步骤消息
2. emit_tool_call() - 发送工具调用消息
3. emit_final_response() - 发送最终响应
4. complete() - 完成流式传输
5. 使用 asyncio.Queue 缓存消息
6. complete 后拒绝新消息
7. 错误处理
"""

import asyncio

import pytest

# ==================== 基础功能测试 ====================


class TestConversationFlowEmitterBasics:
    """测试 ConversationFlowEmitter 基础功能"""

    def test_emitter_class_exists(self):
        """测试：ConversationFlowEmitter 类应存在"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        assert ConversationFlowEmitter is not None

    def test_emitter_can_be_instantiated(self):
        """测试：可以创建 emitter 实例"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")
        assert emitter is not None
        assert emitter.session_id == "session_1"

    def test_emitter_has_queue(self):
        """测试：emitter 应有内部消息队列"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")
        assert hasattr(emitter, "_queue")
        assert isinstance(emitter._queue, asyncio.Queue)

    def test_emitter_initial_state_is_active(self):
        """测试：emitter 初始状态应为 active"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")
        assert emitter.is_active is True
        assert emitter.is_completed is False


# ==================== ConversationStep 数据类测试 ====================


class TestConversationStep:
    """测试 ConversationStep 数据类"""

    def test_conversation_step_exists(self):
        """测试：ConversationStep 数据类应存在"""
        from src.domain.services.conversation_flow_emitter import ConversationStep

        assert ConversationStep is not None

    def test_conversation_step_has_required_fields(self):
        """测试：ConversationStep 应有必要字段"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationStep,
            StepKind,
        )

        step = ConversationStep(
            kind=StepKind.THINKING,
            content="正在思考...",
        )

        assert step.kind == StepKind.THINKING
        assert step.content == "正在思考..."
        assert step.step_id is not None
        assert step.timestamp is not None

    def test_step_kind_enum_values(self):
        """测试：StepKind 枚举应包含所有必要值"""
        from src.domain.services.conversation_flow_emitter import StepKind

        assert StepKind.THINKING is not None
        assert StepKind.REASONING is not None
        assert StepKind.ACTION is not None
        assert StepKind.OBSERVATION is not None
        assert StepKind.TOOL_CALL is not None
        assert StepKind.TOOL_RESULT is not None
        assert StepKind.DELTA is not None
        assert StepKind.FINAL is not None
        assert StepKind.ERROR is not None

    def test_conversation_step_to_dict(self):
        """测试：ConversationStep 应能序列化为字典"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationStep,
            StepKind,
        )

        step = ConversationStep(
            kind=StepKind.THINKING,
            content="测试内容",
            metadata={"key": "value"},
        )

        data = step.to_dict()

        assert data["kind"] == "thinking"
        assert data["content"] == "测试内容"
        assert data["metadata"] == {"key": "value"}
        assert "step_id" in data
        assert "timestamp" in data


# ==================== emit_step 测试 ====================


class TestEmitStep:
    """测试 emit_step 方法"""

    @pytest.mark.asyncio
    async def test_emit_step_adds_to_queue(self):
        """测试：emit_step 应将消息加入队列"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            ConversationStep,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        step = ConversationStep(
            kind=StepKind.THINKING,
            content="正在分析...",
        )

        await emitter.emit_step(step)

        # 验证队列不为空
        assert not emitter._queue.empty()

        # 取出并验证
        queued_step = await emitter._queue.get()
        assert queued_step.content == "正在分析..."

    @pytest.mark.asyncio
    async def test_emit_step_maintains_order(self):
        """测试：emit_step 应保持消息顺序"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            ConversationStep,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        # 发送多个步骤
        for i in range(5):
            step = ConversationStep(
                kind=StepKind.THINKING,
                content=f"步骤 {i}",
            )
            await emitter.emit_step(step)

        # 验证顺序
        for i in range(5):
            step = await emitter._queue.get()
            assert step.content == f"步骤 {i}"

    @pytest.mark.asyncio
    async def test_emit_step_increments_sequence(self):
        """测试：emit_step 应递增序列号"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            ConversationStep,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        for i in range(3):
            step = ConversationStep(kind=StepKind.THINKING, content=f"步骤 {i}")
            await emitter.emit_step(step)

        # 验证序列号递增
        step1 = await emitter._queue.get()
        step2 = await emitter._queue.get()
        step3 = await emitter._queue.get()

        assert step1.sequence == 1
        assert step2.sequence == 2
        assert step3.sequence == 3


# ==================== emit_thinking / emit_delta 便捷方法测试 ====================


class TestEmitConvenienceMethods:
    """测试便捷方法"""

    @pytest.mark.asyncio
    async def test_emit_thinking(self):
        """测试：emit_thinking 应发送思考步骤"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_thinking("用户想要创建工作流...")

        step = await emitter._queue.get()
        assert step.kind == StepKind.THINKING
        assert step.content == "用户想要创建工作流..."

    @pytest.mark.asyncio
    async def test_emit_delta(self):
        """测试：emit_delta 应发送增量内容"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_delta("好的，")
        await emitter.emit_delta("我来帮您")
        await emitter.emit_delta("创建工作流。")

        step1 = await emitter._queue.get()
        step2 = await emitter._queue.get()
        step3 = await emitter._queue.get()

        assert step1.kind == StepKind.DELTA
        assert step1.content == "好的，"
        assert step1.is_delta is True

        assert step2.content == "我来帮您"
        assert step3.content == "创建工作流。"

    @pytest.mark.asyncio
    async def test_emit_reasoning(self):
        """测试：emit_reasoning 应发送推理步骤"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_reasoning("分析用户需求...")

        step = await emitter._queue.get()
        assert step.kind == StepKind.REASONING
        assert step.content == "分析用户需求..."


# ==================== emit_tool_call 测试 ====================


class TestEmitToolCall:
    """测试 emit_tool_call 方法"""

    @pytest.mark.asyncio
    async def test_emit_tool_call_start(self):
        """测试：emit_tool_call 应发送工具调用开始"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_tool_call(
            tool_name="search",
            tool_id="tc_001",
            arguments={"query": "Python 教程"},
        )

        step = await emitter._queue.get()
        assert step.kind == StepKind.TOOL_CALL
        assert step.metadata["tool_name"] == "search"
        assert step.metadata["tool_id"] == "tc_001"
        assert step.metadata["arguments"] == {"query": "Python 教程"}

    @pytest.mark.asyncio
    async def test_emit_tool_result(self):
        """测试：emit_tool_result 应发送工具执行结果"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_tool_result(
            tool_id="tc_001",
            result={"data": "搜索结果..."},
            success=True,
        )

        step = await emitter._queue.get()
        assert step.kind == StepKind.TOOL_RESULT
        assert step.metadata["tool_id"] == "tc_001"
        assert step.metadata["success"] is True
        assert "data" in step.metadata["result"]

    @pytest.mark.asyncio
    async def test_emit_tool_result_failure(self):
        """测试：emit_tool_result 应能处理失败结果"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_tool_result(
            tool_id="tc_001",
            result=None,
            success=False,
            error="连接超时",
        )

        step = await emitter._queue.get()
        assert step.kind == StepKind.TOOL_RESULT
        assert step.metadata["success"] is False
        assert step.metadata["error"] == "连接超时"


# ==================== emit_final_response 测试 ====================


class TestEmitFinalResponse:
    """测试 emit_final_response 方法"""

    @pytest.mark.asyncio
    async def test_emit_final_response(self):
        """测试：emit_final_response 应发送最终响应"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_final_response("工作流已创建完成。")

        step = await emitter._queue.get()
        assert step.kind == StepKind.FINAL
        assert step.content == "工作流已创建完成。"
        assert step.is_final is True

    @pytest.mark.asyncio
    async def test_emit_final_response_with_metadata(self):
        """测试：emit_final_response 应支持元数据"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_final_response(
            content="任务完成",
            metadata={
                "token_count": 150,
                "latency_ms": 1200,
            },
        )

        step = await emitter._queue.get()
        assert step.metadata["token_count"] == 150
        assert step.metadata["latency_ms"] == 1200


# ==================== complete 测试 ====================


class TestComplete:
    """测试 complete 方法"""

    @pytest.mark.asyncio
    async def test_complete_marks_emitter_as_completed(self):
        """测试：complete 应标记 emitter 为已完成"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")
        assert emitter.is_completed is False

        await emitter.complete()

        assert emitter.is_completed is True
        assert emitter.is_active is False

    @pytest.mark.asyncio
    async def test_complete_adds_end_marker(self):
        """测试：complete 应添加结束标记到队列"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.complete()

        # 队列应有结束标记
        step = await emitter._queue.get()
        assert step.kind == StepKind.END
        assert step.is_final is True

    @pytest.mark.asyncio
    async def test_emit_after_complete_raises_error(self):
        """测试：complete 后调用 emit 应抛出异常"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            EmitterClosedError,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")
        await emitter.complete()

        with pytest.raises(EmitterClosedError):
            await emitter.emit_thinking("尝试发送")

    @pytest.mark.asyncio
    async def test_emit_delta_after_complete_raises_error(self):
        """测试：complete 后调用 emit_delta 应抛出异常"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            EmitterClosedError,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")
        await emitter.complete()

        with pytest.raises(EmitterClosedError):
            await emitter.emit_delta("尝试发送")

    @pytest.mark.asyncio
    async def test_complete_is_idempotent(self):
        """测试：多次调用 complete 应该是幂等的"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.complete()
        await emitter.complete()  # 第二次调用不应抛异常
        await emitter.complete()  # 第三次也不应抛异常

        assert emitter.is_completed is True


# ==================== 错误处理测试 ====================


class TestErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_emit_error(self):
        """测试：emit_error 应发送错误步骤"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_error(
            error_message="LLM 调用超时",
            error_code="LLM_TIMEOUT",
            recoverable=True,
        )

        step = await emitter._queue.get()
        assert step.kind == StepKind.ERROR
        assert step.content == "LLM 调用超时"
        assert step.metadata["error_code"] == "LLM_TIMEOUT"
        assert step.metadata["recoverable"] is True

    @pytest.mark.asyncio
    async def test_complete_with_error(self):
        """测试：complete_with_error 应发送错误并关闭"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.complete_with_error("发生致命错误")

        # 应有错误步骤
        step = await emitter._queue.get()
        assert step.kind == StepKind.ERROR
        assert step.content == "发生致命错误"

        # emitter 应已关闭
        assert emitter.is_completed is True


# ==================== 迭代器测试 ====================


class TestAsyncIterator:
    """测试异步迭代器功能"""

    @pytest.mark.asyncio
    async def test_emitter_is_async_iterable(self):
        """测试：emitter 应支持异步迭代"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        # 应该实现 __aiter__
        assert hasattr(emitter, "__aiter__")

    @pytest.mark.asyncio
    async def test_iterate_over_steps(self):
        """测试：应能通过 async for 遍历步骤"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
            StepKind,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        # 在后台任务中发送消息
        async def send_messages():
            await asyncio.sleep(0.01)
            await emitter.emit_thinking("思考中...")
            await asyncio.sleep(0.01)
            await emitter.emit_delta("回复内容")
            await asyncio.sleep(0.01)
            await emitter.complete()

        asyncio.create_task(send_messages())

        # 遍历收集所有步骤
        steps = []
        async for step in emitter:
            steps.append(step)
            if step.kind == StepKind.END:
                break

        assert len(steps) == 3  # thinking, delta, end
        assert steps[0].kind == StepKind.THINKING
        assert steps[1].kind == StepKind.DELTA
        assert steps[2].kind == StepKind.END

    @pytest.mark.asyncio
    async def test_iterate_with_timeout(self):
        """测试：迭代应支持超时"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1", timeout=0.1)

        # 不发送任何消息，应该超时
        with pytest.raises(asyncio.TimeoutError):
            async for _ in emitter:
                pass


# ==================== 统计功能测试 ====================


class TestStatistics:
    """测试统计功能"""

    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """测试：应能获取发送统计"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_thinking("思考1")
        await emitter.emit_thinking("思考2")
        await emitter.emit_delta("增量1")
        await emitter.emit_delta("增量2")
        await emitter.emit_delta("增量3")

        stats = emitter.get_statistics()

        assert stats["total_steps"] == 5
        assert stats["by_kind"]["thinking"] == 2
        assert stats["by_kind"]["delta"] == 3

    @pytest.mark.asyncio
    async def test_get_accumulated_content(self):
        """测试：应能获取累积的内容"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationFlowEmitter,
        )

        emitter = ConversationFlowEmitter(session_id="session_1")

        await emitter.emit_delta("好的，")
        await emitter.emit_delta("我来")
        await emitter.emit_delta("帮您。")

        accumulated = emitter.get_accumulated_content()
        assert accumulated == "好的，我来帮您。"


# ==================== 与 StreamMessage 的转换测试 ====================


class TestStreamMessageConversion:
    """测试与 StreamMessage 的转换"""

    @pytest.mark.asyncio
    async def test_step_to_stream_message(self):
        """测试：ConversationStep 应能转换为 StreamMessage"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationStep,
            StepKind,
        )

        step = ConversationStep(
            kind=StepKind.THINKING,
            content="正在思考...",
            metadata={"agent_id": "conv_agent"},
        )

        # 调用转换方法
        stream_msg = step.to_stream_message()

        # 验证转换结果
        from src.domain.services.stream_message import StreamMessageType

        assert stream_msg.type == StreamMessageType.THINKING_START
        assert stream_msg.content == "正在思考..."
        assert stream_msg.metadata.agent_id == "conv_agent"

    @pytest.mark.asyncio
    async def test_delta_step_to_stream_message(self):
        """测试：Delta 步骤应正确转换为 StreamMessage"""
        from src.domain.services.conversation_flow_emitter import (
            ConversationStep,
            StepKind,
        )

        step = ConversationStep(
            kind=StepKind.DELTA,
            content="增量内容",
            is_delta=True,
            delta_index=5,
        )

        stream_msg = step.to_stream_message()

        from src.domain.services.stream_message import StreamMessageType

        assert stream_msg.type == StreamMessageType.CONTENT_DELTA
        assert stream_msg.is_delta is True
        assert stream_msg.delta_index == 5

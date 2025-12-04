"""Phase 4: 流式消息格式化层测试

TDD: 测试 StreamMessageFormatter 将内部数据转换为前端可用格式。
"""

import json
from datetime import datetime

import pytest

from src.domain.services.conversation_flow_emitter import ConversationStep, StepKind
from src.domain.services.stream_message_formatter import (
    FrontendMessage,
    FrontendMessageType,
    FrontendSSEEncoder,
    StreamMessageFormatter,
    create_final_message,
    create_thought_message,
    create_tool_call_message,
    create_tool_result_message,
    format_step_for_frontend,
)


class TestFrontendMessage:
    """测试 FrontendMessage 数据类"""

    def test_frontend_message_creation(self):
        """测试: 创建前端消息"""
        msg = FrontendMessage(
            type=FrontendMessageType.THOUGHT,
            content="正在思考",
            sequence=1,
        )

        assert msg.type == FrontendMessageType.THOUGHT
        assert msg.content == "正在思考"
        assert msg.sequence == 1
        assert msg.timestamp  # 应该自动填充

    def test_frontend_message_to_dict(self):
        """测试: 转换为字典格式"""
        msg = FrontendMessage(
            type=FrontendMessageType.TOOL_CALL,
            content="调用搜索",
            metadata={"tool": "search", "tool_id": "t1"},
            sequence=2,
        )

        result = msg.to_dict()

        assert result["type"] == "tool_call"
        assert result["content"] == "调用搜索"
        assert result["metadata"]["tool"] == "search"
        assert result["sequence"] == 2

    def test_frontend_message_to_sse(self):
        """测试: 转换为 SSE 格式"""
        msg = FrontendMessage(
            type=FrontendMessageType.THOUGHT,
            content="思考中",
            sequence=1,
        )

        sse = msg.to_sse()

        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        # 解析 JSON
        json_str = sse[6:-2]
        data = json.loads(json_str)
        assert data["type"] == "thought"
        assert data["content"] == "思考中"


class TestStreamMessageFormatter:
    """测试 StreamMessageFormatter 格式化器"""

    @pytest.fixture
    def formatter(self):
        return StreamMessageFormatter()

    def test_format_thinking_step(self, formatter):
        """测试: 格式化思考步骤"""
        step = ConversationStep(
            kind=StepKind.THINKING,
            content="正在分析用户请求",
            sequence=1,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.THOUGHT
        assert msg.content == "正在分析用户请求"
        assert msg.sequence == 1

    def test_format_reasoning_step(self, formatter):
        """测试: 格式化推理步骤"""
        step = ConversationStep(
            kind=StepKind.REASONING,
            content="根据上下文判断",
            sequence=2,
        )

        msg = formatter.format(step)

        # Reasoning 也应该显示为 thought
        assert msg.type == FrontendMessageType.THOUGHT

    def test_format_tool_call_step(self, formatter):
        """测试: 格式化工具调用步骤"""
        step = ConversationStep(
            kind=StepKind.TOOL_CALL,
            content="",
            metadata={
                "tool_name": "search",
                "tool_id": "search_001",
                "arguments": {"query": "Python 教程"},
            },
            sequence=3,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.TOOL_CALL
        assert msg.metadata["tool"] == "search"
        assert msg.metadata["tool_id"] == "search_001"
        assert msg.metadata["arguments"]["query"] == "Python 教程"

    def test_format_tool_result_success(self, formatter):
        """测试: 格式化工具结果（成功）"""
        step = ConversationStep(
            kind=StepKind.TOOL_RESULT,
            content="搜索结果",
            metadata={
                "tool_id": "search_001",
                "result": {"items": ["item1", "item2"]},
                "success": True,
            },
            sequence=4,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.TOOL_RESULT
        assert msg.metadata["tool_id"] == "search_001"
        assert msg.metadata["result"]["items"] == ["item1", "item2"]
        assert msg.metadata["success"] is True

    def test_format_tool_result_failure(self, formatter):
        """测试: 格式化工具结果（失败）"""
        step = ConversationStep(
            kind=StepKind.TOOL_RESULT,
            content="搜索失败",
            metadata={
                "tool_id": "search_001",
                "result": None,
                "success": False,
                "error": "网络超时",
            },
            sequence=5,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.TOOL_RESULT
        assert msg.metadata["success"] is False
        assert msg.metadata["error"] == "网络超时"

    def test_format_final_step(self, formatter):
        """测试: 格式化最终响应"""
        step = ConversationStep(
            kind=StepKind.FINAL,
            content="这是最终答案",
            is_final=True,
            sequence=10,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.FINAL
        assert msg.content == "这是最终答案"
        assert msg.metadata.get("is_final") is True

    def test_format_error_step(self, formatter):
        """测试: 格式化错误步骤"""
        step = ConversationStep(
            kind=StepKind.ERROR,
            content="处理失败",
            metadata={
                "error_code": "LLM_TIMEOUT",
                "recoverable": True,
            },
            sequence=99,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.ERROR
        assert msg.content == "处理失败"
        assert msg.metadata["error_code"] == "LLM_TIMEOUT"
        assert msg.metadata["recoverable"] is True

    def test_format_delta_step(self, formatter):
        """测试: 格式化增量步骤"""
        step = ConversationStep(
            kind=StepKind.DELTA,
            content="增量内容",
            is_delta=True,
            delta_index=5,
            sequence=6,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.DELTA
        assert msg.is_streaming is True
        assert msg.metadata["delta_index"] == 5

    def test_format_end_step(self, formatter):
        """测试: 格式化结束步骤"""
        step = ConversationStep(
            kind=StepKind.END,
            content="",
            sequence=100,
        )

        msg = formatter.format(step)

        assert msg.type == FrontendMessageType.STREAM_END

    def test_format_preserves_timestamp(self, formatter):
        """测试: 格式化保留时间戳"""
        timestamp = datetime(2025, 12, 4, 10, 30, 0)
        step = ConversationStep(
            kind=StepKind.THINKING,
            content="测试",
            timestamp=timestamp,
            sequence=1,
        )

        msg = formatter.format(step)

        assert "2025-12-04" in msg.timestamp
        assert "10:30:00" in msg.timestamp

    def test_format_preserves_step_id(self, formatter):
        """测试: 格式化保留步骤 ID"""
        step = ConversationStep(
            kind=StepKind.THINKING,
            content="测试",
            step_id="step_abc123",
            sequence=1,
        )

        msg = formatter.format(step)

        assert msg.message_id == "step_abc123"


class TestFrontendSSEEncoder:
    """测试 SSE 编码器"""

    @pytest.fixture
    def encoder(self):
        return FrontendSSEEncoder()

    def test_encode_step(self, encoder):
        """测试: 编码步骤为 SSE"""
        step = ConversationStep(
            kind=StepKind.THINKING,
            content="思考中",
            sequence=1,
        )

        sse = encoder.encode_step(step)

        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        # 验证 JSON 可解析
        json_str = sse[6:-2]
        data = json.loads(json_str)
        assert data["type"] == "thought"

    def test_encode_done(self, encoder):
        """测试: 编码结束标记"""
        done = encoder.encode_done()

        assert done == "data: [DONE]\n\n"

    def test_encode_message(self, encoder):
        """测试: 编码前端消息"""
        msg = FrontendMessage(
            type=FrontendMessageType.FINAL,
            content="完成",
            sequence=10,
        )

        sse = encoder.encode_message(msg)

        assert "final" in sse
        assert "完成" in sse


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_format_step_for_frontend(self):
        """测试: format_step_for_frontend 函数"""
        step = ConversationStep(
            kind=StepKind.THINKING,
            content="测试内容",
            sequence=1,
        )

        result = format_step_for_frontend(step)

        assert isinstance(result, dict)
        assert result["type"] == "thought"
        assert result["content"] == "测试内容"

    def test_create_thought_message(self):
        """测试: create_thought_message 函数"""
        result = create_thought_message("正在分析...", sequence=1)

        assert result["type"] == "thought"
        assert result["content"] == "正在分析..."
        assert result["sequence"] == 1

    def test_create_tool_call_message(self):
        """测试: create_tool_call_message 函数"""
        result = create_tool_call_message(
            tool_name="search",
            tool_id="s1",
            arguments={"query": "test"},
            sequence=2,
        )

        assert result["type"] == "tool_call"
        assert result["metadata"]["tool"] == "search"
        assert result["metadata"]["tool_id"] == "s1"
        assert result["metadata"]["arguments"]["query"] == "test"

    def test_create_tool_result_message_success(self):
        """测试: create_tool_result_message 函数（成功）"""
        result = create_tool_result_message(
            tool_id="s1",
            result={"data": "value"},
            success=True,
            sequence=3,
        )

        assert result["type"] == "tool_result"
        assert result["metadata"]["success"] is True
        assert result["metadata"]["result"]["data"] == "value"

    def test_create_tool_result_message_failure(self):
        """测试: create_tool_result_message 函数（失败）"""
        result = create_tool_result_message(
            tool_id="s1",
            result=None,
            success=False,
            error="超时",
            sequence=3,
        )

        assert result["type"] == "tool_result"
        assert result["metadata"]["success"] is False
        assert result["metadata"]["error"] == "超时"

    def test_create_final_message(self):
        """测试: create_final_message 函数"""
        result = create_final_message("最终答案", sequence=10)

        assert result["type"] == "final"
        assert result["content"] == "最终答案"
        assert result["metadata"]["is_final"] is True


class TestFrontendMessageTypes:
    """测试前端消息类型映射"""

    @pytest.fixture
    def formatter(self):
        return StreamMessageFormatter()

    def test_all_step_kinds_have_mapping(self, formatter):
        """测试: 所有 StepKind 都有对应的前端类型"""
        for kind in StepKind:
            step = ConversationStep(kind=kind, content="test", sequence=1)
            msg = formatter.format(step)
            assert msg.type is not None

    def test_message_type_values(self):
        """测试: 消息类型值符合前端预期"""
        assert FrontendMessageType.THOUGHT.value == "thought"
        assert FrontendMessageType.TOOL_CALL.value == "tool_call"
        assert FrontendMessageType.TOOL_RESULT.value == "tool_result"
        assert FrontendMessageType.FINAL.value == "final"
        assert FrontendMessageType.ERROR.value == "error"


class TestCompleteWorkflow:
    """测试完整工作流格式化"""

    @pytest.fixture
    def formatter(self):
        return StreamMessageFormatter()

    def test_format_complete_react_loop(self, formatter):
        """测试: 格式化完整 ReAct 循环"""
        steps = [
            ConversationStep(
                kind=StepKind.THINKING,
                content="用户想查询天气",
                sequence=1,
            ),
            ConversationStep(
                kind=StepKind.TOOL_CALL,
                content="",
                metadata={
                    "tool_name": "weather",
                    "tool_id": "w1",
                    "arguments": {"city": "北京"},
                },
                sequence=2,
            ),
            ConversationStep(
                kind=StepKind.TOOL_RESULT,
                content="",
                metadata={
                    "tool_id": "w1",
                    "result": {"temp": 25, "condition": "晴"},
                    "success": True,
                },
                sequence=3,
            ),
            ConversationStep(
                kind=StepKind.FINAL,
                content="北京今天天气晴朗，气温25度。",
                is_final=True,
                sequence=4,
            ),
        ]

        # 格式化所有步骤
        messages = [formatter.format(step) for step in steps]

        # 验证消息类型序列
        types = [m.type for m in messages]
        assert types == [
            FrontendMessageType.THOUGHT,
            FrontendMessageType.TOOL_CALL,
            FrontendMessageType.TOOL_RESULT,
            FrontendMessageType.FINAL,
        ]

        # 验证序列号递增
        sequences = [m.sequence for m in messages]
        assert sequences == [1, 2, 3, 4]

        # 验证最终消息内容
        assert "北京" in messages[3].content
        assert messages[3].metadata.get("is_final") is True


# 导出
__all__ = [
    "TestFrontendMessage",
    "TestStreamMessageFormatter",
    "TestFrontendSSEEncoder",
    "TestConvenienceFunctions",
    "TestFrontendMessageTypes",
    "TestCompleteWorkflow",
]

"""测试 ShortTermBuffer 数据结构

测试目标：
1. ShortTermBuffer 应该能够存储对话轮次信息
2. 应该包含 turn_id、role、content、tool_refs、token_usage 字段
3. 应该能够计算单个轮次的 token 数
4. 应该支持序列化和反序列化
"""

from datetime import datetime

from src.domain.services.short_term_buffer import ShortTermBuffer, TurnRole


class TestShortTermBuffer:
    """测试 ShortTermBuffer 数据结构"""

    def test_create_short_term_buffer_with_valid_inputs_should_succeed(self):
        """测试：使用有效输入创建 ShortTermBuffer 应该成功"""
        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Hello, how are you?",
            tool_refs=[],
            token_usage={"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        )

        assert buffer.turn_id == "turn_001"
        assert buffer.role == TurnRole.USER
        assert buffer.content == "Hello, how are you?"
        assert buffer.tool_refs == []
        assert buffer.token_usage["total_tokens"] == 10

    def test_short_term_buffer_should_have_timestamp(self):
        """测试：ShortTermBuffer 应该有时间戳"""
        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Hello",
            tool_refs=[],
            token_usage={"total_tokens": 5},
        )

        assert hasattr(buffer, "timestamp")
        assert isinstance(buffer.timestamp, datetime)

    def test_short_term_buffer_with_tool_refs_should_store_them(self):
        """测试：ShortTermBuffer 应该能够存储工具引用"""
        buffer = ShortTermBuffer(
            turn_id="turn_002",
            role=TurnRole.ASSISTANT,
            content="Let me search for that information.",
            tool_refs=["tool_call_001", "tool_call_002"],
            token_usage={"total_tokens": 20},
        )

        assert len(buffer.tool_refs) == 2
        assert "tool_call_001" in buffer.tool_refs
        assert "tool_call_002" in buffer.tool_refs

    def test_get_total_tokens_should_return_correct_count(self):
        """测试：获取总 token 数应该返回正确值"""
        buffer = ShortTermBuffer(
            turn_id="turn_003",
            role=TurnRole.ASSISTANT,
            content="Here is the answer.",
            tool_refs=[],
            token_usage={"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
        )

        total = buffer.get_total_tokens()

        assert total == 80

    def test_get_total_tokens_with_missing_field_should_return_zero(self):
        """测试：token_usage 缺少 total_tokens 字段时应该返回 0"""
        buffer = ShortTermBuffer(
            turn_id="turn_004",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={},
        )

        total = buffer.get_total_tokens()

        assert total == 0

    def test_to_dict_should_return_serializable_dict(self):
        """测试：to_dict 应该返回可序列化的字典"""
        buffer = ShortTermBuffer(
            turn_id="turn_005",
            role=TurnRole.ASSISTANT,
            content="Response",
            tool_refs=["tool_001"],
            token_usage={"total_tokens": 15},
        )

        data = buffer.to_dict()

        assert data["turn_id"] == "turn_005"
        assert data["role"] == "assistant"
        assert data["content"] == "Response"
        assert data["tool_refs"] == ["tool_001"]
        assert data["token_usage"]["total_tokens"] == 15
        assert "timestamp" in data

    def test_from_dict_should_reconstruct_buffer(self):
        """测试：from_dict 应该能够重建 ShortTermBuffer"""
        data = {
            "turn_id": "turn_006",
            "role": "user",
            "content": "Question",
            "tool_refs": [],
            "token_usage": {"total_tokens": 10},
            "timestamp": "2025-01-01T12:00:00",
        }

        buffer = ShortTermBuffer.from_dict(data)

        assert buffer.turn_id == "turn_006"
        assert buffer.role == TurnRole.USER
        assert buffer.content == "Question"
        assert buffer.tool_refs == []
        assert buffer.token_usage["total_tokens"] == 10


class TestTurnRole:
    """测试 TurnRole 枚举"""

    def test_turn_role_should_have_user_assistant_system(self):
        """测试：TurnRole 应该包含 USER、ASSISTANT、SYSTEM"""
        assert TurnRole.USER == "user"
        assert TurnRole.ASSISTANT == "assistant"
        assert TurnRole.SYSTEM == "system"

    def test_turn_role_should_be_string_enum(self):
        """测试：TurnRole 应该是字符串枚举"""
        assert isinstance(TurnRole.USER.value, str)
        assert isinstance(TurnRole.ASSISTANT.value, str)
        assert isinstance(TurnRole.SYSTEM.value, str)


class TestShortTermBufferList:
    """测试 ShortTermBuffer 列表操作"""

    def test_calculate_total_tokens_from_buffer_list(self):
        """测试：计算缓冲区列表的总 token 数"""
        buffers = [
            ShortTermBuffer(
                turn_id="turn_001",
                role=TurnRole.USER,
                content="Hello",
                tool_refs=[],
                token_usage={"total_tokens": 10},
            ),
            ShortTermBuffer(
                turn_id="turn_002",
                role=TurnRole.ASSISTANT,
                content="Hi there!",
                tool_refs=[],
                token_usage={"total_tokens": 15},
            ),
            ShortTermBuffer(
                turn_id="turn_003",
                role=TurnRole.USER,
                content="How are you?",
                tool_refs=[],
                token_usage={"total_tokens": 12},
            ),
        ]

        total = sum(b.get_total_tokens() for b in buffers)

        assert total == 37

    def test_filter_buffers_by_role(self):
        """测试：按角色过滤缓冲区"""
        buffers = [
            ShortTermBuffer(
                turn_id="turn_001",
                role=TurnRole.USER,
                content="Q1",
                tool_refs=[],
                token_usage={"total_tokens": 5},
            ),
            ShortTermBuffer(
                turn_id="turn_002",
                role=TurnRole.ASSISTANT,
                content="A1",
                tool_refs=[],
                token_usage={"total_tokens": 10},
            ),
            ShortTermBuffer(
                turn_id="turn_003",
                role=TurnRole.USER,
                content="Q2",
                tool_refs=[],
                token_usage={"total_tokens": 5},
            ),
        ]

        user_buffers = [b for b in buffers if b.role == TurnRole.USER]

        assert len(user_buffers) == 2
        assert all(b.role == TurnRole.USER for b in user_buffers)

    def test_get_latest_n_buffers(self):
        """测试：获取最新的 N 个缓冲区"""
        buffers = [
            ShortTermBuffer(
                turn_id=f"turn_{i:03d}",
                role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                content=f"Content {i}",
                tool_refs=[],
                token_usage={"total_tokens": 10},
            )
            for i in range(10)
        ]

        latest_3 = buffers[-3:]

        assert len(latest_3) == 3
        assert latest_3[0].turn_id == "turn_007"
        assert latest_3[1].turn_id == "turn_008"
        assert latest_3[2].turn_id == "turn_009"

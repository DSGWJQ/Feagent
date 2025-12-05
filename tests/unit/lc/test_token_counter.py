"""测试 Token 计数工具

测试目标：
1. 消息列表的 token 计数
2. 单个文本的 token 计数
3. 不同模型的 token 计数差异
4. 上下文使用率计算
"""

from src.lc.token_counter import (
    TokenCounter,
    count_message_tokens,
    count_text_tokens,
    estimate_tokens,
)


class TestTokenCounter:
    """测试 TokenCounter 类"""

    def test_create_token_counter_with_openai_model_should_succeed(self):
        """测试：使用 OpenAI 模型创建 TokenCounter 应该成功"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        assert counter.provider == "openai"
        assert counter.model == "gpt-4"
        assert counter.context_limit > 0

    def test_count_messages_should_return_token_count(self):
        """测试：计数消息列表应该返回 token 数"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you!"},
        ]

        token_count = counter.count_messages(messages)

        assert token_count > 0
        assert isinstance(token_count, int)

    def test_count_text_should_return_token_count(self):
        """测试：计数文本应该返回 token 数"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        text = "This is a test message for token counting."
        token_count = counter.count_text(text)

        assert token_count > 0
        assert isinstance(token_count, int)

    def test_calculate_usage_ratio_should_return_correct_ratio(self):
        """测试：计算使用率应该返回正确的比率"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        # GPT-4 的上下文限制是 8192
        used_tokens = 4096
        ratio = counter.calculate_usage_ratio(used_tokens)

        assert ratio == 0.5  # 4096 / 8192 = 0.5
        assert 0 <= ratio <= 1

    def test_calculate_usage_ratio_exceeding_limit_should_return_greater_than_one(self):
        """测试：使用率超过限制应该返回大于 1 的值"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        # 超过上下文限制
        used_tokens = 10000
        ratio = counter.calculate_usage_ratio(used_tokens)

        assert ratio > 1.0

    def test_is_approaching_limit_should_return_true_when_near_limit(self):
        """测试：接近限制时应该返回 True"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        # 使用 85% 的上下文（默认阈值是 0.8）
        used_tokens = int(8192 * 0.85)
        is_approaching = counter.is_approaching_limit(used_tokens)

        assert is_approaching is True

    def test_is_approaching_limit_should_return_false_when_far_from_limit(self):
        """测试：远离限制时应该返回 False"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        # 使用 50% 的上下文
        used_tokens = int(8192 * 0.5)
        is_approaching = counter.is_approaching_limit(used_tokens)

        assert is_approaching is False

    def test_is_approaching_limit_with_custom_threshold_should_work(self):
        """测试：自定义阈值应该生效"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        # 使用 70% 的上下文，阈值设为 0.6
        used_tokens = int(8192 * 0.7)
        is_approaching = counter.is_approaching_limit(used_tokens, threshold=0.6)

        assert is_approaching is True

    def test_get_remaining_tokens_should_return_correct_count(self):
        """测试：获取剩余 token 数应该返回正确值"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        used_tokens = 4096
        remaining = counter.get_remaining_tokens(used_tokens)

        assert remaining == 4096  # 8192 - 4096

    def test_get_remaining_tokens_when_exceeded_should_return_zero(self):
        """测试：超过限制时剩余 token 数应该返回 0"""
        counter = TokenCounter(provider="openai", model="gpt-4")

        used_tokens = 10000
        remaining = counter.get_remaining_tokens(used_tokens)

        assert remaining == 0


class TestCountMessageTokens:
    """测试 count_message_tokens 函数"""

    def test_count_message_tokens_with_openai_model_should_return_count(self):
        """测试：使用 OpenAI 模型计数消息应该返回 token 数"""
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        token_count = count_message_tokens(messages, provider="openai", model="gpt-4")

        assert token_count > 0
        assert isinstance(token_count, int)

    def test_count_message_tokens_with_empty_list_should_return_zero(self):
        """测试：空消息列表应该返回 0"""
        messages = []

        token_count = count_message_tokens(messages, provider="openai", model="gpt-4")

        assert token_count == 0

    def test_count_message_tokens_with_long_messages_should_return_higher_count(self):
        """测试：长消息应该返回更高的 token 数"""
        short_messages = [{"role": "user", "content": "Hi"}]
        long_messages = [
            {
                "role": "user",
                "content": "This is a much longer message that contains more words and should result in a higher token count.",
            }
        ]

        short_count = count_message_tokens(short_messages, provider="openai", model="gpt-4")
        long_count = count_message_tokens(long_messages, provider="openai", model="gpt-4")

        assert long_count > short_count


class TestCountTextTokens:
    """测试 count_text_tokens 函数"""

    def test_count_text_tokens_should_return_count(self):
        """测试：计数文本应该返回 token 数"""
        text = "This is a test message."
        token_count = count_text_tokens(text, provider="openai", model="gpt-4")

        assert token_count > 0
        assert isinstance(token_count, int)

    def test_count_text_tokens_with_empty_string_should_return_zero(self):
        """测试：空字符串应该返回 0"""
        text = ""
        token_count = count_text_tokens(text, provider="openai", model="gpt-4")

        assert token_count == 0

    def test_count_text_tokens_with_chinese_should_work(self):
        """测试：中文文本应该正确计数"""
        text = "这是一个测试消息。"
        token_count = count_text_tokens(text, provider="openai", model="gpt-4")

        assert token_count > 0


class TestEstimateTokens:
    """测试 estimate_tokens 函数"""

    def test_estimate_tokens_should_return_approximate_count(self):
        """测试：估算 token 数应该返回近似值"""
        text = "This is a test message for token estimation."
        estimated = estimate_tokens(text)

        assert estimated > 0
        assert isinstance(estimated, int)

    def test_estimate_tokens_should_be_close_to_actual_count(self):
        """测试：估算值应该接近实际值"""
        text = "This is a test message for token estimation."

        estimated = estimate_tokens(text)
        actual = count_text_tokens(text, provider="openai", model="gpt-4")

        # 估算值应该在实际值的 50% 到 150% 之间
        assert actual * 0.5 <= estimated <= actual * 1.5

    def test_estimate_tokens_with_empty_string_should_return_zero(self):
        """测试：空字符串估算应该返回 0"""
        text = ""
        estimated = estimate_tokens(text)

        assert estimated == 0

    def test_estimate_tokens_with_chinese_should_work(self):
        """测试：中文文本估算应该工作"""
        text = "这是一个测试消息，用于 token 估算。"
        estimated = estimate_tokens(text)

        assert estimated > 0


class TestTokenCounterWithDifferentModels:
    """测试不同模型的 TokenCounter"""

    def test_gpt4_turbo_should_have_larger_context_limit(self):
        """测试：GPT-4 Turbo 应该有更大的上下文限制"""
        gpt4_counter = TokenCounter(provider="openai", model="gpt-4")
        gpt4_turbo_counter = TokenCounter(provider="openai", model="gpt-4-turbo")

        assert gpt4_turbo_counter.context_limit > gpt4_counter.context_limit

    def test_deepseek_counter_should_work(self):
        """测试：DeepSeek 计数器应该工作"""
        counter = TokenCounter(provider="deepseek", model="deepseek-chat")

        text = "This is a test message."
        token_count = counter.count_text(text)

        assert token_count > 0

    def test_unknown_model_should_use_default_limit(self):
        """测试：未知模型应该使用默认限制"""
        counter = TokenCounter(provider="unknown", model="unknown-model")

        assert counter.context_limit == 4096  # 默认值

"""
Unit tests for TFIDFCompressor

测试目标：验证基于 TF-IDF 的消息压缩算法
TDD Phase: RED
"""

import pytest

from src.domain.entities.chat_message import ChatMessage


class TestTFIDFCompressor:
    """TFIDFCompressor 单元测试"""

    @pytest.fixture
    def compressor(self):
        """创建压缩器实例"""
        from src.infrastructure.memory.tfidf_compressor import TFIDFCompressor

        return TFIDFCompressor()

    def test_tfidf_compressor_exists(self):
        """测试：TFIDFCompressor 类应该存在"""
        from src.infrastructure.memory.tfidf_compressor import TFIDFCompressor

        assert TFIDFCompressor is not None

    def test_compress_returns_all_when_under_token_limit(self, compressor):
        """测试：消息总 token 数小于限制时，返回所有消息"""
        messages = [
            ChatMessage.create("wf_123", "Hello", is_user=True),
            ChatMessage.create("wf_123", "World", is_user=False),
        ]

        result = compressor.compress(messages, max_tokens=1000, min_messages=2)

        assert len(result) == 2
        assert result == messages

    def test_compress_enforces_min_messages(self, compressor):
        """测试：即使超过 token 限制，也要保留 min_messages 条消息"""
        # 创建大量消息
        messages = [
            ChatMessage.create("wf_123", "Message " + "x" * 100, is_user=True) for _ in range(20)
        ]

        # 即使 max_tokens 很小，也应该保留 min_messages=5 条
        result = compressor.compress(messages, max_tokens=10, min_messages=5)

        assert len(result) >= 5

    def test_compress_keeps_recent_messages_first(self, compressor):
        """测试：优先保留最近的消息"""
        messages = [
            ChatMessage.create("wf_123", f"Old message {i}", is_user=True) for i in range(10)
        ]
        # 最后一条是最新的
        messages.append(ChatMessage.create("wf_123", "Recent message", is_user=True))

        result = compressor.compress(messages, max_tokens=50, min_messages=2)

        # 最后一条消息应该被保留
        assert any("Recent message" in msg.content for msg in result)

    def test_compress_returns_messages_in_chronological_order(self, compressor):
        """测试：压缩后的消息应该按时间顺序返回"""
        messages = [ChatMessage.create("wf_123", f"Message {i}", is_user=True) for i in range(10)]

        result = compressor.compress(messages, max_tokens=100, min_messages=2)

        # 验证顺序（通过时间戳）
        for i in range(len(result) - 1):
            assert result[i].timestamp <= result[i + 1].timestamp

    def test_compress_with_empty_list(self, compressor):
        """测试：空列表应该返回空列表"""
        result = compressor.compress([], max_tokens=1000, min_messages=2)
        assert result == []

    def test_compress_with_single_message(self, compressor):
        """测试：单条消息应该直接返回"""
        messages = [ChatMessage.create("wf_123", "Single message", is_user=True)]

        result = compressor.compress(messages, max_tokens=1000, min_messages=1)

        assert len(result) == 1
        assert result[0].content == "Single message"

    def test_estimate_tokens_for_chinese(self, compressor):
        """测试：中文 token 估算（约 1.3 字符/token）"""
        text = "你好世界" * 100  # 400 个中文字符

        tokens = compressor._estimate_tokens(text)

        # 约 400 / 1.3 ≈ 308 tokens
        assert 250 < tokens < 350

    def test_estimate_tokens_for_english(self, compressor):
        """测试：英文 token 估算（约 4 字符/token）"""
        text = "Hello world " * 100  # 约 1200 个英文字符

        tokens = compressor._estimate_tokens(text)

        # 约 1200 / 4 = 300 tokens
        assert 250 < tokens < 350

    def test_estimate_tokens_for_mixed_content(self, compressor):
        """测试：中英混合 token 估算"""
        text = "Hello 你好 World 世界"

        tokens = compressor._estimate_tokens(text)

        # 2 个中文字符 (约 1.5 tokens) + ~15 英文字符 (约 4 tokens) ≈ 5-6 tokens
        assert tokens > 0

    def test_compress_prefers_high_tfidf_messages(self, compressor):
        """测试：应该优先保留 TF-IDF 分数高的消息（信息量大）"""
        messages = [
            # 低信息量消息（重复词汇）
            ChatMessage.create("wf_123", "好的 好的 好的", is_user=True),
            ChatMessage.create("wf_123", "谢谢 谢谢", is_user=False),
            # 高信息量消息（独特词汇）
            ChatMessage.create("wf_123", "请创建一个HTTP节点连接到LLM节点", is_user=True),
            ChatMessage.create("wf_123", "已成功创建工作流", is_user=False),
        ]

        # 设置严格的 token 限制，强制压缩
        result = compressor.compress(messages, max_tokens=30, min_messages=2)

        # 高信息量的消息更可能被保留
        high_info_preserved = any(
            "HTTP" in msg.content or "LLM" in msg.content or "工作流" in msg.content
            for msg in result
        )
        assert high_info_preserved

    def test_tokenize_handles_chinese(self, compressor):
        """测试：分词器应该正确处理中文"""
        text = "你好世界"

        words = compressor._tokenize(text)

        # 中文应该按字符分词
        assert "你" in words
        assert "好" in words
        assert "世" in words
        assert "界" in words

    def test_tokenize_handles_english(self, compressor):
        """测试：分词器应该正确处理英文"""
        text = "Hello world"

        words = compressor._tokenize(text)

        # 英文应该按空格分词
        assert "Hello" in words
        assert "world" in words

    def test_calculate_tfidf_scores_returns_list(self, compressor):
        """测试：TF-IDF 计算应该返回分数列表"""
        messages = [
            ChatMessage.create("wf_123", "Message 1", is_user=True),
            ChatMessage.create("wf_123", "Message 2", is_user=False),
        ]

        scores = compressor._calculate_tfidf_scores(messages)

        assert isinstance(scores, list)
        assert len(scores) == 2
        assert all(isinstance(score, float) for score in scores)

    def test_calculate_tfidf_scores_assigns_higher_to_unique_words(self, compressor):
        """测试：包含更多不同词汇的消息应该获得更高的 TF-IDF 分数"""
        messages = [
            # 低多样性：重复同一个词
            ChatMessage.create("wf_123", "common common common common", is_user=True),
            # 高多样性：多个不同的词
            ChatMessage.create("wf_123", "unique word diversity vocabulary", is_user=False),
            # 中等：共享一些词
            ChatMessage.create("wf_123", "common word", is_user=True),
        ]

        scores = compressor._calculate_tfidf_scores(messages)

        # 第二条消息（高多样性）应该得分更高
        # 因为它包含更多独特词汇，每个词的 IDF 权重都更高
        assert scores[1] > scores[0]

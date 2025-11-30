"""
TF-IDF Message Compressor

基于 TF-IDF 的智能消息压缩算法。
根据消息的信息量（TF-IDF 分数）和时间新鲜度进行压缩。

Author: Claude Code
Date: 2025-11-30
"""

import math
from collections import Counter

from src.domain.entities.chat_message import ChatMessage


class TFIDFCompressor:
    """
    基于 TF-IDF 的消息重要性评估与压缩

    压缩策略：
    1. 计算每条消息的 TF-IDF 分数（信息量指标）
    2. 优先保留最近的消息（时间维度）
    3. 在超过 token 限制时，移除低分旧消息
    4. 强制保留最少 N 条消息

    Example:
        >>> compressor = TFIDFCompressor()
        >>> messages = [msg1, msg2, msg3, ...]  # 100 条消息
        >>> compressed = compressor.compress(messages, max_tokens=4000, min_messages=5)
        >>> len(compressed)  # 可能是 20-30 条
        20
    """

    def compress(
        self, messages: list[ChatMessage], max_tokens: int = 4000, min_messages: int = 2
    ) -> list[ChatMessage]:
        """
        压缩消息列表到指定 token 限制

        算法步骤：
        1. 如果消息数 ≤ min_messages，直接返回
        2. 计算每条消息的 token 数
        3. 如果总 token 数 ≤ max_tokens，直接返回
        4. 计算 TF-IDF 分数
        5. 按时间倒序，强制保留最近 min_messages 条
        6. 其余按 TF-IDF 分数降序选择，直到达到 token 限制
        7. 按时间顺序返回

        Args:
            messages: 要压缩的消息列表
            max_tokens: 最大 token 数（默认 4000）
            min_messages: 最少保留消息数（默认 2）

        Returns:
            压缩后的消息列表（按时间升序）
        """
        if len(messages) <= min_messages:
            return messages

        # 1. 计算每条消息的 token 数
        message_tokens = [self._estimate_tokens(msg.content) for msg in messages]
        total_tokens = sum(message_tokens)

        if total_tokens <= max_tokens:
            return messages

        # 2. 计算 TF-IDF 分数
        scores = self._calculate_tfidf_scores(messages)

        # 3. 按时间倒序排序（索引，最新的在前）
        sorted_indices = list(range(len(messages)))
        sorted_indices.sort(key=lambda i: messages[i].timestamp, reverse=True)

        # 4. 贪心选择：优先保留最近 + 高分消息
        selected = []
        current_tokens = 0

        # 强制保留最近 min_messages 条
        for i in range(min(min_messages, len(messages))):
            idx = sorted_indices[i]
            selected.append(idx)
            current_tokens += message_tokens[idx]

        # 按分数选择剩余消息
        remaining = [(idx, scores[idx]) for idx in sorted_indices[min_messages:]]
        remaining.sort(key=lambda x: x[1], reverse=True)  # 按分数降序

        for idx, _score in remaining:
            if current_tokens + message_tokens[idx] <= max_tokens:
                selected.append(idx)
                current_tokens += message_tokens[idx]
            else:
                break

        # 5. 按时间顺序返回
        selected.sort()
        return [messages[i] for i in selected]

    def _estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量（启发式）

        规则：
        - 中文字符：~1.3 字符/token
        - 其他字符：~4 字符/token

        Args:
            text: 要估算的文本

        Returns:
            估算的 token 数
        """
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.3 + other_chars / 4)

    def _calculate_tfidf_scores(self, messages: list[ChatMessage]) -> list[float]:
        """
        计算每条消息的 TF-IDF 分数

        TF-IDF = TF(词频) × IDF(逆文档频率)
        - TF: 词在文档中出现的频率
        - IDF: log(总文档数 / 包含该词的文档数)

        Args:
            messages: 消息列表

        Returns:
            每条消息的 TF-IDF 分数列表
        """
        # 构建词频表
        all_words = []
        message_words = []

        for msg in messages:
            words = self._tokenize(msg.content)
            message_words.append(words)
            all_words.extend(words)

        # 计算 IDF
        word_doc_count = Counter()
        for words in message_words:
            word_doc_count.update(set(words))

        num_docs = len(messages)
        idf = {word: math.log(num_docs / count) for word, count in word_doc_count.items()}

        # 计算每条消息的 TF-IDF 得分
        scores = []
        for words in message_words:
            word_count = Counter(words)
            total_words = len(words)

            if total_words == 0:
                scores.append(0.0)
                continue

            tfidf_sum = sum(
                (count / total_words) * idf.get(word, 0.0) for word, count in word_count.items()
            )
            scores.append(tfidf_sum)

        return scores

    def _tokenize(self, text: str) -> list[str]:
        """
        简单分词（空格分隔 + 中文按字符）

        处理：
        - 中文：按字符拆分
        - 英文：按空格拆分
        - 过滤空白

        Args:
            text: 要分词的文本

        Returns:
            词列表
        """
        words = []

        # 中文按字符
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                words.append(char)

        # 英文按空格
        words.extend(text.split())

        # 过滤空白
        return [w for w in words if w.strip()]

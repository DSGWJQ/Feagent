"""Token 计数工具

职责：
1. 计算消息列表的 token 数
2. 计算单个文本的 token 数
3. 计算上下文使用率
4. 判断是否接近上下文限制

设计原则：
- 使用 tiktoken 进行精确计数（OpenAI 模型）
- 对于非 OpenAI 模型，使用估算方法
- 提供快捷函数简化使用
- 集成模型元数据获取上下文限制

依赖：
- tiktoken: OpenAI 官方 token 计数库
- model_metadata: 获取模型上下文限制
"""

from typing import Any

from src.infrastructure.lc_adapters.model_metadata import get_model_metadata


class TokenCounter:
    """Token 计数器

    属性：
    - provider: 提供商名称
    - model: 模型名称
    - context_limit: 上下文窗口大小
    """

    def __init__(self, provider: str, model: str):
        """初始化 Token 计数器

        参数：
            provider: 提供商名称
            model: 模型名称
        """
        self.provider = provider
        self.model = model

        # 获取模型元数据
        metadata = get_model_metadata(provider, model)
        self.context_limit = metadata.context_window

        # 初始化 tiktoken 编码器（仅 OpenAI 模型）
        self._encoding = None
        if provider.lower() == "openai":
            try:
                import tiktoken

                # 尝试获取模型的编码器
                try:
                    self._encoding = tiktoken.encoding_for_model(model)
                except KeyError:
                    # 如果模型不支持，使用默认编码器
                    self._encoding = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                # tiktoken 未安装，使用估算方法
                pass

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """计算消息列表的 token 数

        参数：
            messages: 消息列表，每个消息包含 role 和 content

        返回：
            token 数
        """
        if not messages:
            return 0

        if self._encoding:
            # 使用 tiktoken 精确计数
            return self._count_messages_with_tiktoken(messages)
        else:
            # 使用估算方法
            return self._estimate_message_tokens(messages)

    def _count_messages_with_tiktoken(self, messages: list[dict[str, Any]]) -> int:
        """使用 tiktoken 精确计数消息 token 数

        参考：https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb

        参数：
            messages: 消息列表

        返回：
            token 数
        """
        num_tokens = 0

        # 每条消息的固定开销
        tokens_per_message = 3  # <|start|>role<|end|>content
        tokens_per_name = 1  # 如果有 name 字段

        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(self._encoding.encode(value))  # type: ignore
                if key == "name":
                    num_tokens += tokens_per_name

        # 每次对话的固定开销
        num_tokens += 3  # <|start|>assistant<|message|>

        return num_tokens

    def _estimate_message_tokens(self, messages: list[dict[str, Any]]) -> int:
        """估算消息 token 数（非 OpenAI 模型）

        使用简单的启发式方法：
        - 英文：约 4 个字符 = 1 token
        - 中文：约 1.5 个字符 = 1 token
        - 每条消息额外 3 token 开销

        参数：
            messages: 消息列表

        返回：
            估算的 token 数
        """
        total_tokens = 0

        for message in messages:
            # 消息固定开销
            total_tokens += 3

            # 计算内容 token
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += estimate_tokens(content)

        # 对话固定开销
        total_tokens += 3

        return total_tokens

    def count_text(self, text: str) -> int:
        """计算文本的 token 数

        参数：
            text: 文本内容

        返回：
            token 数
        """
        if not text:
            return 0

        if self._encoding:
            # 使用 tiktoken 精确计数
            return len(self._encoding.encode(text))
        else:
            # 使用估算方法
            return estimate_tokens(text)

    def calculate_usage_ratio(self, used_tokens: int) -> float:
        """计算上下文使用率

        参数：
            used_tokens: 已使用的 token 数

        返回：
            使用率（0-1 之间，超过 1 表示超限）
        """
        if self.context_limit == 0:
            return 0.0

        return used_tokens / self.context_limit

    def is_approaching_limit(self, used_tokens: int, threshold: float = 0.8) -> bool:
        """判断是否接近上下文限制

        参数：
            used_tokens: 已使用的 token 数
            threshold: 阈值（默认 0.8，即 80%）

        返回：
            是否接近限制
        """
        ratio = self.calculate_usage_ratio(used_tokens)
        return ratio >= threshold

    def get_remaining_tokens(self, used_tokens: int) -> int:
        """获取剩余可用 token 数

        参数：
            used_tokens: 已使用的 token 数

        返回：
            剩余 token 数（最小为 0）
        """
        remaining = self.context_limit - used_tokens
        return max(0, remaining)


def count_message_tokens(
    messages: list[dict[str, Any]],
    provider: str = "openai",
    model: str = "gpt-4",
) -> int:
    """计算消息列表的 token 数（快捷函数）

    参数：
        messages: 消息列表
        provider: 提供商名称（默认 openai）
        model: 模型名称（默认 gpt-4）

    返回：
        token 数
    """
    counter = TokenCounter(provider=provider, model=model)
    return counter.count_messages(messages)


def count_text_tokens(
    text: str,
    provider: str = "openai",
    model: str = "gpt-4",
) -> int:
    """计算文本的 token 数（快捷函数）

    参数：
        text: 文本内容
        provider: 提供商名称（默认 openai）
        model: 模型名称（默认 gpt-4）

    返回：
        token 数
    """
    counter = TokenCounter(provider=provider, model=model)
    return counter.count_text(text)


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数（通用方法）

    使用简单的启发式方法：
    - 英文：约 4 个字符 = 1 token
    - 中文：约 1.5 个字符 = 1 token
    - 混合文本：根据字符类型加权平均

    参数：
        text: 文本内容

    返回：
        估算的 token 数
    """
    if not text:
        return 0

    # 统计中文字符和英文字符
    chinese_chars = 0
    english_chars = 0

    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            # 中文字符
            chinese_chars += 1
        else:
            # 其他字符（英文、数字、标点等）
            english_chars += 1

    # 计算 token 数
    # 中文：约 1.5 个字符 = 1 token
    # 英文：约 4 个字符 = 1 token
    chinese_tokens = chinese_chars / 1.5
    english_tokens = english_chars / 4.0

    return int(chinese_tokens + english_tokens)

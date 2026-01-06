"""LLM抽象接口(Domain Port) - 隔离Domain与具体LLM实现.

职责:
- 定义LLM生成文本的标准接口
- 支持同步和流式生成
- 隔离OpenAI/Anthropic/Mock等具体实现

设计原则:
- 使用Protocol实现结构化子类型(鸭子类型)
- 不依赖任何具体LLM库
- 符合依赖倒置原则(DIP)
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol


class LLMPort(Protocol):
    """LLM抽象接口(Domain Port).

    所有LLM Adapter必须实现此Protocol的所有方法。
    """

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """生成文本响应.

        参数:
            prompt: 提示词
            temperature: 温度参数(0.0-1.0), 控制生成的随机性
            max_tokens: 最大token数
            **kwargs: 其他LLM特定参数

        返回:
            生成的文本内容

        异常:
            ValueError: 参数验证失败
            RuntimeError: LLM调用失败
        """
        ...

    def generate_streaming(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式生成文本响应.

        参数:
            prompt: 提示词
            temperature: 温度参数(0.0-1.0)
            max_tokens: 最大token数
            **kwargs: 其他LLM特定参数

        生成:
            文本片段(delta), 逐步返回生成内容

        异常:
            ValueError: 参数验证失败
            RuntimeError: LLM调用失败
        """
        ...

"""LLM OpenAI Adapter - 真实OpenAI API调用实现.

职责:
- 调用OpenAI Chat Completions API
- 支持同步和流式生成
- 提供生产级错误处理

适用场景:
- 生产环境
- Full-real测试模式(nightly)
- 真实LLM波动探测
"""

from collections.abc import AsyncIterator
from typing import Any


class LLMOpenAIAdapter:
    """LLM OpenAI实现 - 真实API调用.

    模式C (Full-real)的核心组件。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        """初始化OpenAI Adapter.

        参数:
            api_key: OpenAI API密钥
            model: 模型名称(默认gpt-4o-mini)
            base_url: API基础URL(支持自定义端点)

        注意:
            使用AsyncOpenAI而非OpenAI,确保异步一致性
        """
        # 延迟导入,避免未使用OpenAI时加载SDK
        from openai import AsyncOpenAI

        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Please set OPENAI_API_KEY in your .env file."
            )

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """调用OpenAI API生成文本.

        参数:
            prompt: 提示词
            temperature: 温度参数(0.0-1.0)
            max_tokens: 最大token数
            **kwargs: 其他OpenAI参数(如top_p, frequency_penalty等)

        返回:
            LLM生成的文本内容

        异常:
            openai.APIError: API调用失败
            openai.RateLimitError: 超过速率限制
            openai.AuthenticationError: 认证失败
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # 提取生成内容
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError(f"OpenAI returned empty content. Response: {response}")

        return content

    async def generate_streaming(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式调用OpenAI API生成文本.

        参数:
            prompt: 提示词
            temperature: 温度参数(0.0-1.0)
            max_tokens: 最大token数
            **kwargs: 其他OpenAI参数

        生成:
            文本片段(delta), 逐步返回生成内容

        异常:
            openai.APIError: API调用失败
            openai.RateLimitError: 超过速率限制
        """
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        # 流式返回delta
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

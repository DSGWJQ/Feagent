"""LLM Stub Adapter - 返回固定响应的确定性实现.

职责:
- 提供完全确定性的LLM响应(用于CI测试)
- 支持基于prompt hash的响应映射
- 无外部依赖,零成本

适用场景:
- PR回归测试
- 冒烟测试
- 快速失败检测
"""

import hashlib
from collections.abc import AsyncIterator
from typing import Any


class LLMStubAdapter:
    """LLM Stub实现 - 返回固定的确定性响应.

    模式A (Deterministic)的核心组件。
    """

    def __init__(self, fixed_responses: dict[str, str] | None = None) -> None:
        """初始化Stub Adapter.

        参数:
            fixed_responses: prompt_hash -> response的映射(可选)
                            如果提供,将根据prompt的MD5 hash查找响应
                            如果未找到匹配,使用default_response
        """
        self.fixed_responses = fixed_responses or {}
        self.default_response = '{"result": "stubbed_workflow_output", "status": "success"}'

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """生成确定性响应.

        参数:
            prompt: 提示词(用于计算hash)
            temperature: 忽略(stub不需要随机性)
            max_tokens: 忽略(stub返回固定内容)
            **kwargs: 忽略

        返回:
            固定的stub响应或根据prompt hash匹配的响应
        """
        # 使用MD5 hash作为查找键,避免存储完整prompt
        prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        return self.fixed_responses.get(prompt_hash, self.default_response)

    async def generate_streaming(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式生成确定性响应.

        注意: Stub模式下一次性返回完整响应(无真实流式)。

        参数:
            prompt: 提示词
            temperature: 忽略
            max_tokens: 忽略
            **kwargs: 忽略

        生成:
            完整的stub响应(单个chunk)
        """
        response = await self.generate(
            prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        yield response

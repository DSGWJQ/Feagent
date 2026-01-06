"""LLM Replay Adapter - 回放预录制的LLM响应.

职责:
- 从JSON文件加载预录制的prompt-response对
- 实现确定性回放(无LLM调用,无成本)
- 适用于需要真实但可控的LLM输出的场景

适用场景:
- 集成回归测试(Hybrid模式)
- 需要特定LLM输出的测试用例
- 降低测试成本
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any


class LLMReplayAdapter:
    """LLM Replay实现 - 回放录制的响应.

    模式B (Hybrid)的核心组件。
    """

    def __init__(self, replay_file: str) -> None:
        """初始化Replay Adapter.

        参数:
            replay_file: 录制文件路径(JSON格式)
                        格式: [{"prompt": "...", "response": "..."}, ...]

        异常:
            FileNotFoundError: 录制文件不存在
            json.JSONDecodeError: 录制文件格式无效
        """
        replay_path = Path(replay_file)
        if not replay_path.exists():
            raise FileNotFoundError(
                f"LLM replay file not found: {replay_file}\n"
                f"Please create the file or check LLM_REPLAY_FILE configuration."
            )

        with replay_path.open(encoding="utf-8") as f:
            self.recordings: list[dict[str, str]] = json.load(f)

        if not isinstance(self.recordings, list):
            raise ValueError(
                f"Invalid replay file format: expected list, got {type(self.recordings)}"
            )

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """从录制中查找匹配的响应.

        参数:
            prompt: 提示词(必须与录制时完全匹配)
            temperature: 忽略(回放不需要随机性)
            max_tokens: 忽略(返回录制内容)
            **kwargs: 忽略

        返回:
            匹配的录制响应

        异常:
            ValueError: 未找到匹配的录制(prompt不匹配)
        """
        # 精确匹配prompt
        for record in self.recordings:
            if record.get("prompt") == prompt:
                return record["response"]

        # 未找到匹配
        raise ValueError(
            f"No recording found for prompt: {prompt[:100]}...\n"
            f"Available recordings: {len(self.recordings)}\n"
            f"Please re-record or check prompt consistency."
        )

    async def generate_streaming(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式回放录制响应.

        注意: 回放模式下一次性返回完整录制内容。

        参数:
            prompt: 提示词
            temperature: 忽略
            max_tokens: 忽略
            **kwargs: 忽略

        生成:
            完整的录制响应(单个chunk)

        异常:
            ValueError: 未找到匹配的录制
        """
        response = await self.generate(
            prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        yield response

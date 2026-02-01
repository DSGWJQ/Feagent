"""Audio Executor（音频执行器）

Infrastructure 层：实现语音生成节点执行器
"""

from __future__ import annotations

import base64
import inspect
import json
from collections.abc import Awaitable
from typing import Any, cast

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor
from src.infrastructure.executors.deterministic_mode import is_deterministic_mode


class AudioExecutor(NodeExecutor):
    """语音生成节点执行器"""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        model = node.config.get("model", "openai/tts-1")
        voice = node.config.get("voice", "alloy")
        speed = node.config.get("speed", 1.0)
        text = (
            node.config.get("text")
            or node.config.get("input")
            or node.config.get("prompt")
            or node.config.get("content")
        )

        if text is None:
            text = _resolve_text_input(inputs)

        if is_deterministic_mode():
            return {
                "stub": True,
                "mode": "deterministic",
                "model": model,
                "voice": voice,
                "speed": speed,
                "text_preview": _preview_text(text),
                "audio_b64": "",
                "format": "mp3",
            }

        provider, model_name = _parse_model_provider(model)
        if provider != "openai":
            raise DomainError(f"Audio 模型仅支持 OpenAI（当前: {provider}）")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise DomainError("未安装 openai 库，请运行: pip install openai") from exc

        client = AsyncOpenAI(api_key=self.api_key)

        try:
            response = await client.audio.speech.create(
                model=model_name,
                voice=str(voice),
                input=str(text),
                speed=float(speed) if speed is not None else 1.0,
            )
        except Exception as exc:  # noqa: BLE001
            raise DomainError(f"Audio 调用失败: {str(exc)}") from exc

        audio_bytes = await _read_audio_bytes(response)
        encoded = base64.b64encode(audio_bytes).decode("ascii")

        return {
            "model": getattr(response, "model", model_name),
            "voice": voice,
            "format": "mp3",
            "audio_b64": encoded,
        }


def _parse_model_provider(model: str) -> tuple[str, str]:
    raw = (model or "").strip()
    if not raw:
        return "openai", "tts-1"
    if "/" in raw:
        provider, name = raw.split("/", 1)
        return provider.lower(), name
    return "openai", raw


def _resolve_text_input(inputs: dict[str, Any]) -> str:
    if not inputs:
        raise DomainError("Audio 节点缺少输入")
    if len(inputs) == 1:
        return _stringify_value(next(iter(inputs.values())))
    return json.dumps(inputs, ensure_ascii=False)


def _stringify_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _preview_text(value: Any, limit: int = 240) -> str:
    text = _stringify_value(value)
    return text[:limit]


async def _read_audio_bytes(response: Any) -> bytes:
    if hasattr(response, "content") and response.content is not None:
        return response.content
    if hasattr(response, "read") and callable(response.read):
        data = response.read()
        if isinstance(data, bytes):
            return data
        if inspect.isawaitable(data):
            awaited = await cast(Awaitable[Any], data)
            if isinstance(awaited, bytes):
                return awaited
        raise DomainError("Audio 响应 read() 返回值不支持读取为 bytes")
    if hasattr(response, "aread") and callable(response.aread):
        data = response.aread()
        if isinstance(data, bytes):
            return data
        if inspect.isawaitable(data):
            awaited = await cast(Awaitable[Any], data)
            if isinstance(awaited, bytes):
                return awaited
        raise DomainError("Audio 响应 aread() 返回值不支持读取为 bytes")
    if hasattr(response, "iter_bytes"):
        chunks: list[bytes] = []
        async for chunk in response.iter_bytes():
            chunks.append(chunk)
        return b"".join(chunks)
    raise DomainError("Audio 响应格式不支持读取")

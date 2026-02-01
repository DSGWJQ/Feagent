"""Image Generation Executor（图像生成执行器）

Infrastructure 层：实现图像生成节点执行器
"""

from __future__ import annotations

import json
from typing import Any, Literal

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor
from src.infrastructure.executors.deterministic_mode import is_deterministic_mode


class ImageGenerationExecutor(NodeExecutor):
    """图像生成节点执行器"""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        model = node.config.get("model", "openai/dall-e-3")
        aspect_ratio = node.config.get("aspectRatio", "1:1")
        output_format = node.config.get("outputFormat", "png")
        prompt = (
            node.config.get("prompt")
            or node.config.get("text")
            or node.config.get("input")
            or node.config.get("content")
        )

        if prompt is None:
            prompt = _resolve_text_input(inputs)

        if is_deterministic_mode():
            return {
                "stub": True,
                "mode": "deterministic",
                "model": model,
                "aspectRatio": aspect_ratio,
                "outputFormat": output_format,
                "prompt_preview": _preview_text(prompt),
                "image_b64": "",
            }

        provider, model_name = _parse_model_provider(model)
        if provider != "openai":
            raise DomainError(f"ImageGeneration 模型仅支持 OpenAI（当前: {provider}）")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise DomainError("未安装 openai 库，请运行: pip install openai") from exc

        client = AsyncOpenAI(api_key=self.api_key)

        size = _map_aspect_ratio(aspect_ratio)

        try:
            response = await client.images.generate(
                model=model_name,
                prompt=str(prompt),
                size=size,
                response_format="b64_json",
            )
        except Exception as exc:  # noqa: BLE001
            raise DomainError(f"ImageGeneration 调用失败: {str(exc)}") from exc

        if not response.data:
            raise DomainError("ImageGeneration 未返回结果")

        image_payload = response.data[0]
        image_b64 = getattr(image_payload, "b64_json", None)
        image_url = getattr(image_payload, "url", None)

        return {
            "model": getattr(response, "model", model_name),
            "size": size,
            "outputFormat": output_format,
            "image_b64": image_b64,
            "image_url": image_url,
        }


def _parse_model_provider(model: str) -> tuple[str, str]:
    raw = (model or "").strip()
    if not raw:
        return "openai", "dall-e-3"
    if "/" in raw:
        provider, name = raw.split("/", 1)
        return provider.lower(), name
    return "openai", raw


ImageSize = Literal["1024x1024", "1792x1024", "1024x1792"]


def _map_aspect_ratio(ratio: str) -> ImageSize:
    mapping: dict[str, ImageSize] = {
        "1:1": "1024x1024",
        "16:9": "1792x1024",
        "9:16": "1024x1792",
    }
    return mapping.get(ratio, "1024x1024")


def _resolve_text_input(inputs: dict[str, Any]) -> str:
    if not inputs:
        raise DomainError("ImageGeneration 节点缺少输入")
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

"""Embedding Executor（Embedding 执行器）

Infrastructure 层：实现向量嵌入节点执行器
"""

from __future__ import annotations

import json
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor
from src.infrastructure.executors.deterministic_mode import is_deterministic_mode


class EmbeddingExecutor(NodeExecutor):
    """向量嵌入节点执行器"""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        model = node.config.get("model", "openai/text-embedding-3-small")
        dimensions = node.config.get("dimensions")
        input_value = (
            node.config.get("input")
            or node.config.get("text")
            or node.config.get("prompt")
            or node.config.get("content")
        )

        if input_value is None:
            input_value = _resolve_text_input(inputs)

        payload = _normalize_embedding_input(input_value)

        if is_deterministic_mode():
            dim_value = _coerce_int(dimensions)
            dim = dim_value if dim_value is not None else 3
            return {
                "stub": True,
                "mode": "deterministic",
                "model": model,
                "dimensions": dim,
                "embeddings": [[0.0 for _ in range(dim)]],
                "input_preview": _preview_text(input_value),
            }

        provider, model_name = _parse_model_provider(model)
        if provider != "openai":
            raise DomainError(f"Embedding 模型仅支持 OpenAI（当前: {provider}）")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise DomainError("未安装 openai 库，请运行: pip install openai") from exc

        client = AsyncOpenAI(api_key=self.api_key)

        kwargs: dict[str, Any] = {
            "model": model_name,
            "input": payload,
        }
        dim_value = _coerce_int(dimensions)
        if dim_value is not None:
            kwargs["dimensions"] = dim_value

        try:
            response = await client.embeddings.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise DomainError(f"Embedding 调用失败: {str(exc)}") from exc

        embeddings = [item.embedding for item in response.data]
        usage = _extract_usage(response)

        result: dict[str, Any] = {
            "model": getattr(response, "model", model_name),
            "embeddings": embeddings,
        }
        if usage is not None:
            result["usage"] = usage

        return result


def _parse_model_provider(model: str) -> tuple[str, str]:
    raw = (model or "").strip()
    if not raw:
        return "openai", "text-embedding-3-small"
    if "/" in raw:
        provider, name = raw.split("/", 1)
        return provider.lower(), name
    return "openai", raw


def _resolve_text_input(inputs: dict[str, Any]) -> str:
    if not inputs:
        raise DomainError("Embedding 节点缺少输入")
    if len(inputs) == 1:
        return _stringify_value(next(iter(inputs.values())))
    return json.dumps(inputs, ensure_ascii=False)


def _normalize_embedding_input(value: Any) -> Any:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict | tuple | set):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _stringify_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _preview_text(value: Any, limit: int = 240) -> str:
    text = _stringify_value(value)
    return text[:limit]


def _extract_usage(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {"usage": str(usage)}


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw and raw.isdigit():
            return int(raw)
    return None

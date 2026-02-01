"""Structured Output Executor（结构化输出执行器）

Infrastructure 层：实现结构化输出节点执行器
"""

from __future__ import annotations

import json
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor
from src.infrastructure.executors.deterministic_mode import is_deterministic_mode


class StructuredOutputExecutor(NodeExecutor):
    """结构化输出节点执行器"""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        model = node.config.get("model", "openai/gpt-4")
        temperature = node.config.get("temperature", 0.2)
        max_tokens = node.config.get("maxTokens") or node.config.get("max_tokens", 2000)
        schema_name = node.config.get("schemaName", "StructuredOutput")
        mode = node.config.get("mode", "object")
        schema_raw = node.config.get("schema")
        system_prompt = node.config.get("system_prompt", "")
        prompt = (
            node.config.get("prompt")
            or node.config.get("text")
            or node.config.get("input")
            or node.config.get("content")
        )

        if not schema_raw:
            raise DomainError("StructuredOutput 节点缺少 schema 配置")

        if prompt is None:
            prompt = _resolve_text_input(inputs)

        json_schema = _normalize_json_schema(schema_raw, schema_name, mode)

        if is_deterministic_mode():
            return {
                "stub": True,
                "mode": "deterministic",
                "schemaName": schema_name,
                "schema": json_schema,
                "output": {"message": "deterministic stub"},
            }

        provider, model_name = _parse_model_provider(model)
        if provider != "openai":
            raise DomainError(f"StructuredOutput 仅支持 OpenAI（当前: {provider}）")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise DomainError("未安装 openai 库，请运行: pip install openai") from exc

        client = AsyncOpenAI(api_key=self.api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": str(system_prompt)})
        messages.append({"role": "user", "content": str(prompt)})

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": float(temperature) if temperature is not None else 0.2,
            "max_tokens": int(max_tokens) if _is_int_like(max_tokens) else 2000,
            "response_format": {"type": "json_schema", "json_schema": json_schema},
        }

        content = await _call_openai_with_retry(client, kwargs)
        if content is None:
            raise DomainError("StructuredOutput 未返回内容")

        parsed = _parse_json_content(content)
        if parsed is None:
            raise DomainError("StructuredOutput 返回内容无法解析为 JSON")

        return parsed


def _parse_model_provider(model: str) -> tuple[str, str]:
    raw = (model or "").strip()
    if not raw:
        return "openai", "gpt-4"
    if "/" in raw:
        provider, name = raw.split("/", 1)
        return provider.lower(), name
    return "openai", raw


def _resolve_text_input(inputs: dict[str, Any]) -> str:
    if not inputs:
        raise DomainError("StructuredOutput 节点缺少输入")
    if len(inputs) == 1:
        return _stringify_value(next(iter(inputs.values())))
    return json.dumps(inputs, ensure_ascii=False)


def _stringify_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _normalize_json_schema(schema_raw: Any, schema_name: str, mode: str) -> dict[str, Any]:
    if isinstance(schema_raw, str):
        try:
            parsed = json.loads(schema_raw)
        except json.JSONDecodeError as exc:
            raise DomainError("StructuredOutput schema 格式错误") from exc
    elif isinstance(schema_raw, dict):
        parsed = schema_raw
    else:
        raise DomainError("StructuredOutput schema 必须是 JSON 字符串或对象")

    if "schema" in parsed or "name" in parsed or "strict" in parsed:
        json_schema = dict(parsed)
        json_schema.setdefault("name", schema_name or "StructuredOutput")
        if "schema" not in json_schema and "type" in json_schema:
            json_schema = {
                "name": json_schema.get("name"),
                "schema": parsed,
                "strict": json_schema.get("strict", True),
            }
    else:
        json_schema = {
            "name": schema_name or "StructuredOutput",
            "schema": parsed,
            "strict": True,
        }

    if mode in {"object", "array"}:
        schema_body = json_schema.get("schema")
        if isinstance(schema_body, dict) and "type" not in schema_body:
            schema_body = {"type": mode, **schema_body}
            json_schema["schema"] = schema_body

    return json_schema


def _parse_json_content(content: str) -> Any | None:
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return value.strip().isdigit()
    return False


async def _call_openai_with_retry(client: Any, kwargs: dict[str, Any]) -> str | None:
    content = await _call_openai_once(client, kwargs)
    if content and _parse_json_content(content) is not None:
        return content

    # Retry once with stronger instruction
    retry_kwargs = dict(kwargs)
    retry_messages = list(kwargs.get("messages", []))
    retry_messages.append(
        {
            "role": "user",
            "content": "Please return only valid JSON that matches the schema.",
        }
    )
    retry_kwargs["messages"] = retry_messages
    return await _call_openai_once(client, retry_kwargs)


async def _call_openai_once(client: Any, kwargs: dict[str, Any]) -> str | None:
    try:
        response = await client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        raise DomainError(f"StructuredOutput 调用失败: {str(exc)}") from exc

    if not response.choices:
        return None
    message = response.choices[0].message
    return getattr(message, "content", None)

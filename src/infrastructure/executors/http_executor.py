"""HTTP Executor（HTTP 执行器）

Infrastructure 层：实现 HTTP 请求节点执行器
"""

import json
from typing import Any

import httpx

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor
from src.infrastructure.executors.deterministic_mode import is_deterministic_mode


class HttpExecutor(NodeExecutor):
    """HTTP 请求节点执行器"""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 HTTP 请求节点

        配置参数：
            url: 请求 URL
            path: (legacy) 请求 URL 的兼容字段（历史数据/旧客户端可能使用）
            method: 请求方法（GET, POST, PUT, DELETE, PATCH）
            headers: 请求头（JSON 字符串）
            body: 请求体（JSON 字符串）
        """
        # 获取配置
        # Canonical field is `url`; accept legacy `path` for backward compatibility.
        url = node.config.get("url") or node.config.get("path") or ""
        method = node.config.get("method", "GET").upper()
        headers_value = node.config.get("headers", {})
        body_value = node.config.get("body", {})

        if not isinstance(url, str) or not url.strip():
            raise DomainError("HTTP 节点缺少 URL 配置")
        url = url.strip()

        headers = self._parse_json_value(headers_value, field="headers", default={})

        # 验证 headers 类型
        if headers is None:
            headers = {}
        if not isinstance(headers, dict):
            raise DomainError("HTTP 节点 headers 必须是 JSON 对象")
        normalized_headers: dict[str, str] = {}
        for key, value in headers.items():
            if not isinstance(key, str):
                raise DomainError("HTTP 节点 headers 必须是字符串键值对")
            if value is None:
                normalized_headers[key] = ""
            else:
                normalized_headers[key] = str(value)

        body = None
        if method in ["POST", "PUT", "PATCH"]:
            body = self._parse_json_value(body_value, field="body", default=None)

        # Deterministic E2E mode: never hit external HTTP endpoints.
        if is_deterministic_mode():
            mock_response = node.config.get("mock_response", None)
            if mock_response is not None:
                return self._parse_json_value(
                    mock_response, field="mock_response", default=mock_response
                )

            return {
                "stub": True,
                "mode": "deterministic",
                "status": 200,
                "data": {
                    "url": url,
                    "method": method,
                    "headers": normalized_headers,
                    "body": body,
                },
            }

        # 发送请求
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=normalized_headers,
                    json=body,
                )
                response.raise_for_status()

                # 尝试解析 JSON 响应
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return response.text

        except httpx.InvalidURL as e:
            raise DomainError("HTTP 节点 URL 格式错误") from e
        except httpx.HTTPStatusError as e:
            raise DomainError(f"HTTP 请求失败: {e.response.status_code} {e.response.text}") from e
        except httpx.RequestError as e:
            raise DomainError(f"HTTP 请求错误: {str(e)}") from e

    @staticmethod
    def _parse_json_value(value: Any, *, field: str, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, dict | list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return default
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DomainError(f"HTTP 节点 {field} 格式错误: {value}") from exc
        return value

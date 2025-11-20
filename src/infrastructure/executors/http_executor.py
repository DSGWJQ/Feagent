"""HTTP Executor（HTTP 执行器）

Infrastructure 层：实现 HTTP 请求节点执行器
"""

import json
from typing import Any

import httpx

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class HttpExecutor(NodeExecutor):
    """HTTP 请求节点执行器"""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 HTTP 请求节点

        配置参数：
            url: 请求 URL
            method: 请求方法（GET, POST, PUT, DELETE, PATCH）
            headers: 请求头（JSON 字符串）
            body: 请求体（JSON 字符串）
        """
        # 获取配置
        url = node.config.get("url", "")
        method = node.config.get("method", "GET").upper()
        headers_str = node.config.get("headers", "{}")
        body_str = node.config.get("body", "{}")

        if not url:
            raise DomainError("HTTP 节点缺少 URL 配置")

        # 解析 headers 和 body
        try:
            headers = json.loads(headers_str) if headers_str else {}
        except json.JSONDecodeError:
            raise DomainError(f"HTTP 节点 headers 格式错误: {headers_str}")

        try:
            body = json.loads(body_str) if body_str and method in ["POST", "PUT", "PATCH"] else None
        except json.JSONDecodeError:
            raise DomainError(f"HTTP 节点 body 格式错误: {body_str}")

        # 发送请求
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()

                # 尝试解析 JSON 响应
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return response.text

        except httpx.HTTPStatusError as e:
            raise DomainError(f"HTTP 请求失败: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise DomainError(f"HTTP 请求错误: {str(e)}")

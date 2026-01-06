"""HTTP WireMock Adapter - 通过WireMock服务器代理请求.

职责:
- 转发请求到WireMock服务器
- 支持复杂的stubbing规则
- 适用于需要外部服务mock的集成测试

适用场景:
- 集成测试(Hybrid模式)
- 需要复杂HTTP交互的测试
- 多服务协同测试
"""

from typing import Any
from urllib.parse import urlsplit


class HTTPWireMockAdapter:
    """HTTP WireMock实现 - 通过WireMock服务器.

    模式B (Hybrid)的核心组件。

    注意:
        需要预先启动WireMock服务器,并配置stubbing规则。
        参考: http://wiremock.org/docs/running-standalone/
    """

    def __init__(self, wiremock_url: str = "http://localhost:8080") -> None:
        """初始化WireMock Adapter.

        参数:
            wiremock_url: WireMock服务器地址

        注意:
            WireMock服务器需要预先启动并配置stub规则。
        """
        self.wiremock_url = wiremock_url.rstrip("/")

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """通过WireMock执行HTTP请求.

        工作流程:
        1. 将请求转发到WireMock服务器
        2. WireMock根据配置的stub规则返回响应
        3. 返回WireMock的响应

        参数:
            method: HTTP方法
            url: 目标URL(将被WireMock stub拦截)
            headers: 请求头
            json_body: JSON请求体
            timeout: 超时时间

        返回:
            WireMock返回的响应JSON

        异常:
            RuntimeError: WireMock服务器不可用
            httpx.TimeoutException: 请求超时
        """
        # 延迟导入httpx
        import httpx

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 将原始 URL 映射到 WireMock 服务器（避免在 Hybrid 模式下走真实外网）
                target_url = self._map_to_wiremock(url)

                response = await client.request(
                    method=method.upper(),
                    url=target_url,
                    headers=headers,
                    json=json_body,
                )

                # 返回响应JSON
                response.raise_for_status()
                return response.json()

        except httpx.ConnectError as e:
            raise RuntimeError(
                f"WireMock server unavailable at {self.wiremock_url}\n"
                f"Please start WireMock: java -jar wiremock-standalone.jar\n"
                f"Error: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"WireMock request timeout after {timeout}s: {url}") from e

    def _map_to_wiremock(self, url: str) -> str:
        """将任意 URL 映射到 WireMock 服务地址.

        约定:
        - 若传入的是完整 URL（https://example.com/path?x=1），则只保留 path/query，拼到 wiremock_url 上。
        - 若传入的是相对路径（/path 或 path），则直接拼到 wiremock_url 上。
        """
        if url.startswith(("http://", "https://")):
            parsed = urlsplit(url)
            path = parsed.path or "/"
            query = f"?{parsed.query}" if parsed.query else ""
            return f"{self.wiremock_url}{path}{query}"

        if url.startswith("/"):
            return f"{self.wiremock_url}{url}"

        return f"{self.wiremock_url}/{url}"

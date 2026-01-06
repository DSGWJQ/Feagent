"""HTTP Httpx Adapter - 真实HTTP请求实现.

职责:
- 使用httpx执行真实HTTP请求
- 支持所有标准HTTP方法
- 提供生产级错误处理

适用场景:
- 生产环境
- Full-real测试模式(nightly)
- 真实外部服务调用
"""

from typing import Any


class HTTPHttpxAdapter:
    """HTTP Httpx实现 - 真实HTTP客户端.

    模式C (Full-real)的核心组件。
    """

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """执行真实HTTP请求.

        参数:
            method: HTTP方法(GET/POST/PUT/DELETE/PATCH等)
            url: 完整的请求URL
            headers: 请求头(可选)
            json_body: JSON请求体(可选)
            timeout: 超时时间(秒)

        返回:
            响应JSON字典

        异常:
            httpx.HTTPStatusError: HTTP错误状态码(4xx/5xx)
            httpx.TimeoutException: 请求超时
            httpx.NetworkError: 网络错误
            json.JSONDecodeError: 响应非JSON格式
        """
        # 延迟导入httpx
        import httpx

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=json_body,
                )

                # 检查HTTP状态码
                response.raise_for_status()

                # 解析JSON响应
                return response.json()

        except httpx.HTTPStatusError as e:
            # HTTP错误(4xx/5xx)
            raise RuntimeError(
                f"HTTP error {e.response.status_code} for {method.upper()} {url}\n"
                f"Response: {e.response.text[:200]}"
            ) from e

        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"HTTP request timeout after {timeout}s: {method.upper()} {url}"
            ) from e

        except httpx.NetworkError as e:
            raise RuntimeError(f"Network error for {method.upper()} {url}: {e}") from e

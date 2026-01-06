"""HTTP客户端抽象接口(Domain Port) - 隔离Domain与具体HTTP实现.

职责:
- 定义HTTP请求的标准接口
- 支持GET/POST/PUT/DELETE等方法
- 隔离httpx/requests/WireMock等具体实现

设计原则:
- 使用Protocol实现结构化子类型
- 不依赖任何具体HTTP库
- 符合依赖倒置原则(DIP)
"""

from typing import Any, Protocol


class HTTPClientPort(Protocol):
    """HTTP客户端抽象接口(Domain Port).

    所有HTTP Adapter必须实现此Protocol的所有方法。
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
        """执行HTTP请求.

        参数:
            method: HTTP方法(GET/POST/PUT/DELETE等), 大小写不敏感
            url: 请求URL(完整URL或相对路径)
            headers: 请求头(可选)
            json_body: JSON请求体(可选), 仅用于POST/PUT等方法
            timeout: 超时时间(秒), 默认30秒

        返回:
            响应JSON字典

        异常:
            ValueError: 参数验证失败
            RuntimeError: HTTP请求失败
            TimeoutError: 请求超时
        """
        ...

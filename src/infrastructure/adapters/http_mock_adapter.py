"""HTTP Mock Adapter - 本地mock响应实现.

职责:
- 提供基于URL pattern的mock响应
- 无需外部HTTP服务器
- 完全确定性,零延迟

适用场景:
- CI回归测试(Deterministic模式)
- 快速单元测试
- 无网络环境测试
"""

import re
from typing import Any


class HTTPMockAdapter:
    """HTTP Mock实现 - 本地pattern匹配.

    模式A (Deterministic)的核心组件。
    """

    def __init__(self, mock_responses: dict[str, dict[str, Any]] | None = None) -> None:
        """初始化Mock Adapter.

        参数:
            mock_responses: URL正则pattern -> 响应JSON的映射
                          如果未提供,使用默认mock规则
        """
        self.mock_responses = mock_responses or {
            # 默认mock规则
            r"https://httpbin\.org/.*": {"mock": True, "status": "ok", "service": "httpbin"},
            r"https://api\.example\.com/.*": {"mock": True, "status": "ok", "service": "example"},
        }

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """执行mock HTTP请求.

        参数:
            method: HTTP方法(忽略,所有请求返回相同mock)
            url: 请求URL(用于pattern匹配)
            headers: 请求头(忽略)
            json_body: 请求体(忽略)
            timeout: 超时时间(忽略)

        返回:
            匹配的mock响应JSON

        异常:
            ValueError: URL未被mock覆盖
        """
        # 按顺序匹配pattern
        for pattern, response in self.mock_responses.items():
            if re.match(pattern, url):
                # 返回mock响应(可以包含请求信息用于调试)
                return {
                    **response,
                    "_mock_meta": {
                        "matched_pattern": pattern,
                        "original_url": url,
                        "method": method.upper(),
                    },
                }

        # 未找到匹配的mock规则
        raise ValueError(
            f"Unmocked URL: {url}\n"
            f"Available patterns: {list(self.mock_responses.keys())}\n"
            f"Please add a mock rule for this URL in HTTPMockAdapter configuration."
        )

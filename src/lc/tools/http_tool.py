"""HTTP 请求工具

这个工具允许 Agent 发送 HTTP 请求（GET、POST 等）。

为什么需要这个工具？
- Agent 需要与外部 API 交互
- 获取网页内容、调用 REST API 等

设计原则：
1. 简单易用：只需要 URL 和 HTTP 方法
2. 安全：限制请求大小、超时时间
3. 容错：捕获所有异常，返回错误信息而不是抛出异常
4. 清晰的描述：让 LLM 知道如何使用这个工具

为什么使用 @tool 装饰器？
- 简单：自动生成工具的 schema
- 类型安全：支持类型注解
- 文档友好：自动从 docstring 生成描述
"""

import json

import requests
from langchain_core.tools import tool


@tool
def http_request(
    url: str,
    method: str = "GET",
    headers: str | None = None,
    body: str | None = None,
) -> str:
    """发送 HTTP 请求并返回响应内容

    这个工具可以发送 HTTP 请求到指定的 URL，支持 GET、POST、PUT、DELETE 等方法。

    参数：
        url: 请求的 URL（必填）
        method: HTTP 方法，如 GET、POST、PUT、DELETE（默认：GET）
        headers: 请求头，JSON 格式字符串（可选）
        body: 请求体，JSON 格式字符串（可选，仅用于 POST/PUT）

    返回：
        响应内容（字符串）或错误信息

    示例：
        # GET 请求
        http_request(url="https://api.example.com/users", method="GET")

        # POST 请求
        http_request(
            url="https://api.example.com/users",
            method="POST",
            headers='{"Content-Type": "application/json"}',
            body='{"name": "John", "age": 30}'
        )
    """
    try:
        # 验证 HTTP 方法
        method = method.upper()
        allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]
        if method not in allowed_methods:
            return f"错误：不支持的 HTTP 方法 '{method}'。支持的方法：{', '.join(allowed_methods)}"

        # 解析 headers
        headers_dict = {}
        if headers:
            try:
                headers_dict = json.loads(headers)
            except json.JSONDecodeError:
                return f"错误：headers 不是有效的 JSON 格式：{headers}"

        # 解析 body
        body_data = None
        if body:
            try:
                body_data = json.loads(body)
            except json.JSONDecodeError:
                # 如果不是 JSON，就当作普通字符串
                body_data = body

        # 发送请求
        # 为什么设置 timeout？
        # - 避免请求挂起太久
        # - 提高用户体验
        timeout = 30  # 30 秒超时

        response = requests.request(
            method=method,
            url=url,
            headers=headers_dict,
            json=body_data if isinstance(body_data, dict) else None,
            data=body_data if isinstance(body_data, str) else None,
            timeout=timeout,
        )

        # 检查响应状态
        # 为什么不使用 response.raise_for_status()？
        # - 我们希望返回错误信息，而不是抛出异常
        # - Agent 需要知道发生了什么错误
        if response.status_code >= 400:
            return (
                f"HTTP 错误：状态码 {response.status_code}\n"
                f"URL: {url}\n"
                f"响应内容：{response.text[:500]}"  # 只返回前 500 个字符
            )

        # 返回响应内容
        # 为什么限制长度？
        # - 避免返回太大的内容（LLM 有 token 限制）
        # - 提高性能
        max_length = 10000  # 最多返回 10000 个字符
        content = response.text

        if len(content) > max_length:
            return (
                f"响应内容（已截断，原始长度：{len(content)} 字符）：\n"
                f"{content[:max_length]}\n"
                f"...\n"
                f"（内容太长，已截断）"
            )

        return f"HTTP {response.status_code} - 成功\n\n{content}"

    except requests.exceptions.Timeout:
        return f"错误：请求超时（超过 {timeout} 秒）\nURL: {url}"

    except requests.exceptions.ConnectionError:
        return f"错误：无法连接到服务器\nURL: {url}"

    except requests.exceptions.RequestException as e:
        return f"错误：请求失败\nURL: {url}\n详细信息：{str(e)}"

    except Exception as e:
        return f"错误：未知错误\nURL: {url}\n详细信息：{str(e)}"


def get_http_request_tool():
    """获取 HTTP 请求工具

    为什么使用工厂函数？
    - 统一入口：所有工具都通过工厂函数获取
    - 便于测试：可以在测试中 Mock
    - 便于管理：可以在应用启动时创建工具列表

    返回：
        Tool: HTTP 请求工具

    示例：
    >>> tool = get_http_request_tool()
    >>> result = tool.func(url="https://httpbin.org/get", method="GET")
    >>> print(result)
    """
    return http_request

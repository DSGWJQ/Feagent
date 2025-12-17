"""LangChain 工具模块

这个模块提供了 Agent 可以使用的工具。

工具列表：
1. HTTP 请求工具 - 发送 HTTP 请求
2. 文件读取工具 - 读取文件内容
3. Python 执行工具 - 执行 Python 代码
4. 数据库查询工具 - 查询数据库（只读）

使用示例：
>>> from src.infrastructure.lc_adapters.tools import get_http_request_tool, get_read_file_tool
>>>
>>> # 获取工具
>>> http_tool = get_http_request_tool()
>>> file_tool = get_read_file_tool()
>>>
>>> # 调用工具
>>> result = http_tool.func(url="https://httpbin.org/get", method="GET")
>>> print(result)
>>>
>>> # 获取所有工具
>>> from src.infrastructure.lc_adapters.tools import get_all_tools
>>> tools = get_all_tools()
>>> print(f"可用工具：{[tool.name for tool in tools]}")
"""

from src.infrastructure.lc_adapters.tools.database_tool import get_database_query_tool
from src.infrastructure.lc_adapters.tools.file_tool import get_read_file_tool
from src.infrastructure.lc_adapters.tools.http_tool import get_http_request_tool
from src.infrastructure.lc_adapters.tools.python_tool import get_python_execution_tool

__all__ = [
    "get_http_request_tool",
    "get_read_file_tool",
    "get_python_execution_tool",
    "get_database_query_tool",
    "get_all_tools",
]


def get_all_tools():
    """获取所有可用的工具

    为什么需要这个函数？
    - 统一入口：一次性获取所有工具
    - 便于管理：添加新工具时只需修改这里
    - 便于使用：Agent 可以直接使用所有工具

    返回：
        list[Tool]: 所有可用的工具列表

    示例：
    >>> tools = get_all_tools()
    >>> print(f"可用工具：{[tool.name for tool in tools]}")
    ['http_request', 'read_file', 'execute_python', 'query_database']
    """
    return [
        get_http_request_tool(),
        get_read_file_tool(),
        get_python_execution_tool(),
        get_database_query_tool(),
    ]

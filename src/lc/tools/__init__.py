from __future__ import annotations

from src.lc.tools.database_tool import get_database_query_tool
from src.lc.tools.file_tool import get_read_file_tool
from src.lc.tools.http_tool import get_http_request_tool
from src.lc.tools.python_tool import get_python_execution_tool

__all__ = [
    "get_http_request_tool",
    "get_read_file_tool",
    "get_python_execution_tool",
    "get_database_query_tool",
    "get_all_tools",
]


def get_all_tools():
    return [
        get_http_request_tool(),
        get_read_file_tool(),
        get_python_execution_tool(),
        get_database_query_tool(),
    ]

"""数据库查询工具（LangChain Tool）

说明：
- 该模块是测试与对外使用的稳定入口（tests 会 patch 这里的符号）。
- 只允许 SELECT 查询，禁止写操作（fail-closed）。
"""

from __future__ import annotations

import sqlite3
from typing import Any, cast

from langchain_core.tools import tool

from src.infrastructure.database.engine import get_sync_engine

# 禁止的 SQL 关键字
FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "REPLACE",
    "MERGE",
}


def is_safe_sql(sql: str) -> tuple[bool, str]:
    """检查 SQL 是否安全（只允许 SELECT）。"""
    sql_upper = sql.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"禁止使用 {keyword} 操作，只允许 SELECT 查询"
    if not sql_upper.strip().startswith("SELECT"):
        return False, "只允许 SELECT 查询"
    return True, ""


def get_database_connection() -> Any:
    """获取数据库连接（同步 DB-API connection）。"""
    engine = get_sync_engine()
    connection = engine.raw_connection()
    return cast(Any, connection)


@tool
def query_database(sql: str, max_rows: int = 100) -> str:
    """执行数据库查询并返回结果（只读）。"""
    try:
        if not sql or not sql.strip():
            return "错误：SQL 查询不能为空"

        is_safe, error_msg = is_safe_sql(sql)
        if not is_safe:
            return f"错误：{error_msg}"

        try:
            connection = get_database_connection()
        except Exception as exc:
            return f"错误：无法连接到数据库\n详细信息：{exc}"

        try:
            cursor = connection.cursor()
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError as exc:
                return f"错误：SQL 语法错误或表不存在\n详细信息：{exc}"
            except Exception as exc:
                return f"错误：查询执行失败\n详细信息：{exc}"

            rows = cursor.fetchall()
            if not rows:
                return "查询成功，但没有找到匹配的数据（返回 0 行）"

            if len(rows) > max_rows:
                rows = rows[:max_rows]
                truncated_msg = f"\n\n注意：结果已截断，只显示前 {max_rows} 行"
            else:
                truncated_msg = ""

            column_names = [description[0] for description in cursor.description]
            header = " | ".join(column_names)

            result_lines: list[str] = []
            result_lines.append(f"查询成功，返回 {len(rows)} 行数据：")
            result_lines.append("")
            result_lines.append(header)
            result_lines.append("-" * len(header))
            for row in rows:
                row_str = " | ".join(str(value) if value is not None else "NULL" for value in row)
                result_lines.append(row_str)
            if truncated_msg:
                result_lines.append(truncated_msg)
            return "\n".join(result_lines)
        finally:
            connection.close()
    except Exception as exc:
        return f"错误：查询失败\n详细信息：{exc}"


def get_database_query_tool():
    """获取数据库查询工具（Tool 实例）。"""
    return query_database

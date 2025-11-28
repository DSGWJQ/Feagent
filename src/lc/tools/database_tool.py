"""数据库查询工具

这个工具允许 Agent 执行数据库查询（只读）。

为什么需要这个工具？
- Agent 需要查询数据库获取数据
- 支持数据分析、报表生成等任务
- 提供结构化数据访问能力

设计原则：
1. 安全：只允许 SELECT 查询，禁止 INSERT/UPDATE/DELETE/DROP
2. 只读：不允许修改数据库
3. 容错：捕获所有异常，返回错误信息
4. 限制：限制返回行数，避免返回过多数据

安全限制：
1. 只允许 SELECT 查询
2. 禁止 INSERT、UPDATE、DELETE、DROP 等修改操作
3. 禁止 CREATE、ALTER 等 DDL 操作
4. 限制返回行数（默认最多 100 行）

为什么使用 @tool 装饰器？
- 简单：自动生成工具的 schema
- 类型安全：支持类型注解
- 文档友好：自动从 docstring 生成描述

注意事项：
- 这是一个简化版的实现，使用项目的数据库连接
- 生产环境需要更严格的权限控制
- 建议使用只读数据库用户
- 可以考虑使用查询缓存提高性能
"""

import sqlite3
from typing import Any, cast

from langchain_core.tools import tool

from src.infrastructure.database.engine import get_engine

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
    """检查 SQL 是否安全

    参数：
        sql: SQL 查询语句

    返回：
        (is_safe, error_message): 是否安全，错误信息
    """
    # 转换为大写以便检查
    sql_upper = sql.upper()

    # 检查是否包含禁止的关键字
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"禁止使用 {keyword} 操作，只允许 SELECT 查询"

    # 检查是否是 SELECT 查询
    if not sql_upper.strip().startswith("SELECT"):
        return False, "只允许 SELECT 查询"

    return True, ""


def get_database_connection() -> Any:
    """获取数据库连接

    返回：
        数据库连接对象
    """
    # 使用项目的数据库引擎
    engine = get_engine()

    # 获取原始连接
    # 注意：这里使用 SQLAlchemy 的 raw_connection()
    connection = engine.raw_connection()

    return cast(Any, connection)


@tool
def query_database(sql: str, max_rows: int = 100) -> str:
    """执行数据库查询并返回结果

    这个工具可以执行 SELECT 查询，获取数据库中的数据。

    安全限制：
    - 只允许 SELECT 查询
    - 禁止 INSERT、UPDATE、DELETE、DROP 等修改操作
    - 限制返回行数（默认最多 100 行）

    支持的功能：
    - SELECT 查询
    - WHERE 条件过滤
    - JOIN 多表查询
    - GROUP BY 分组
    - ORDER BY 排序
    - LIMIT 限制行数
    - 聚合函数（COUNT, SUM, AVG, MAX, MIN）

    参数：
        sql: SQL 查询语句（只支持 SELECT）
        max_rows: 最大返回行数，默认 100

    返回：
        查询结果（格式化的字符串）或错误信息

    示例：
        # 简单查询
        query_database("SELECT * FROM users")

        # 带条件查询
        query_database("SELECT name, age FROM users WHERE age > 25")

        # JOIN 查询
        query_database("SELECT u.name, o.order_id FROM users u JOIN orders o ON u.id = o.user_id")

        # 聚合查询
        query_database("SELECT department, COUNT(*) as count FROM employees GROUP BY department")
    """
    try:
        # 验证输入
        if not sql or not sql.strip():
            return "错误：SQL 查询不能为空"

        # 安全检查
        is_safe, error_msg = is_safe_sql(sql)
        if not is_safe:
            return f"错误：{error_msg}"

        # 获取数据库连接
        try:
            connection = get_database_connection()
        except Exception as e:
            return f"错误：无法连接到数据库\n详细信息：{str(e)}"

        try:
            # 创建游标
            cursor = connection.cursor()

            # 执行查询
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError as e:
                return f"错误：SQL 语法错误或表不存在\n详细信息：{str(e)}"
            except Exception as e:
                return f"错误：查询执行失败\n详细信息：{str(e)}"

            # 获取结果
            rows = cursor.fetchall()

            # 检查是否有结果
            if not rows:
                return "查询成功，但没有找到匹配的数据（返回 0 行）"

            # 限制返回行数
            if len(rows) > max_rows:
                rows = rows[:max_rows]
                truncated_msg = f"\n\n注意：结果已截断，只显示前 {max_rows} 行"
            else:
                truncated_msg = ""

            # 获取列名
            column_names = [description[0] for description in cursor.description]

            # 格式化结果
            result_lines = []
            result_lines.append(f"查询成功，返回 {len(rows)} 行数据：")
            result_lines.append("")

            # 添加列名
            result_lines.append(" | ".join(column_names))
            result_lines.append("-" * (len(" | ".join(column_names))))

            # 添加数据行
            for row in rows:
                # 将每个值转换为字符串
                row_str = " | ".join(str(value) if value is not None else "NULL" for value in row)
                result_lines.append(row_str)

            # 添加截断提示
            if truncated_msg:
                result_lines.append(truncated_msg)

            return "\n".join(result_lines)

        finally:
            # 关闭连接
            connection.close()

    except Exception as e:
        # 捕获所有未预期的异常
        return f"错误：查询失败\n详细信息：{str(e)}"


def get_database_query_tool():
    """获取数据库查询工具

    返回：
        Tool: 数据库查询工具

    示例：
    >>> tool = get_database_query_tool()
    >>> result = tool.func(sql="SELECT * FROM users LIMIT 5")
    >>> print(result)
    """
    return query_database

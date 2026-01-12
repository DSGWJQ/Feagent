"""Database Executor（数据库执行器）

Infrastructure 层：实现数据库查询节点执行器

支持的操作：
- SQL 查询（SELECT）
- SQL 写入/DDL（INSERT/UPDATE/DELETE/CREATE/ALTER/...）
"""

import json
import sqlite3
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class DatabaseExecutor(NodeExecutor):
    """数据库查询节点执行器

    配置参数：
        database_url: 数据库连接字符串（目前仅支持 sqlite:/// 格式）
        sql: SQL 查询语句
        params: 查询参数（JSON 字符串或对象）
    """

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行数据库查询节点

        参数：
            node: 节点实体
            inputs: 输入数据（来自前驱节点）
            context: 执行上下文

        返回：
            查询结果（列表或更新行数）
        """
        # 获取配置
        database_url = node.config.get("database_url", "sqlite:///agent_data.db")
        sql = node.config.get("sql", "")
        params_config = node.config.get("params", {})

        if not sql:
            raise DomainError("数据库节点缺少 SQL 语句")

        # 解析数据库 URL
        if not database_url.startswith("sqlite:///"):
            raise DomainError(f"不支持的数据库类型: {database_url}")

        db_path = database_url.replace("sqlite:///", "")

        conn: sqlite3.Connection | None = None
        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # 返回字典格式的结果
            cursor = conn.cursor()

            # 处理参数
            params = self._prepare_params(params_config, inputs)

            # 执行 SQL
            cursor.execute(sql, params)

            # sqlite3: cursor.description != None indicates a result set is available.
            if cursor.description is not None:
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

            conn.commit()
            return {
                "rows_affected": cursor.rowcount,
                "lastrowid": cursor.lastrowid,
            }

        except sqlite3.Error as e:
            raise DomainError(f"数据库查询失败: {str(e)}") from e
        except Exception as e:
            raise DomainError(f"数据库操作错误: {str(e)}") from e
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    @staticmethod
    def _prepare_params(params_config: Any, inputs: dict[str, Any]) -> tuple:
        """准备 SQL 参数

        参数：
            params_config: 参数配置
            inputs: 输入数据

        返回：
            参数元组
        """
        if isinstance(params_config, dict):
            # 字典格式参数，按键值顺序转换为元组
            return tuple(params_config.values())
        elif isinstance(params_config, list):
            # 列表格式参数
            return tuple(params_config)
        elif isinstance(params_config, str):
            # JSON 字符串参数（允许 "[]" / "{}" / ""）
            raw = params_config.strip()
            if not raw:
                return ()
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DomainError(f"数据库节点 params JSON 格式错误: {params_config}") from exc
            return DatabaseExecutor._prepare_params(decoded, inputs)
        else:
            return ()

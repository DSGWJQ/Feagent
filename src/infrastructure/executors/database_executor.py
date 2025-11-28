"""Database Executor（数据库执行器）

Infrastructure 层：实现数据库查询节点执行器

支持的操作：
- SQL 查询（SELECT）
- 数据插入（INSERT）
- 数据更新（UPDATE）
- 数据删除（DELETE）
"""

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

        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # 返回字典格式的结果
            cursor = conn.cursor()

            # 处理参数
            params = self._prepare_params(params_config, inputs)

            # 执行 SQL
            cursor.execute(sql, params)

            # 获取操作类型
            sql_upper = sql.strip().upper()
            if sql_upper.startswith("SELECT"):
                # 查询操作
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
            elif sql_upper.startswith(("INSERT", "UPDATE", "DELETE")):
                # 修改操作
                conn.commit()
                result = {"rows_affected": cursor.rowcount}
            else:
                raise DomainError(f"不支持的 SQL 操作: {sql_upper}")

            conn.close()
            return result

        except sqlite3.Error as e:
            raise DomainError(f"数据库查询失败: {str(e)}") from e
        except Exception as e:
            raise DomainError(f"数据库操作错误: {str(e)}") from e

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
        elif isinstance(params_config, str) and params_config:
            # 空字符串，无参数
            return ()
        else:
            return ()

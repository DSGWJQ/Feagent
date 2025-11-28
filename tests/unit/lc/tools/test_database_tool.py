"""数据库查询工具单元测试

测试场景：
1. 执行简单的 SELECT 查询
2. 执行带 WHERE 条件的查询
3. 执行 JOIN 查询
4. 执行聚合查询（COUNT、SUM 等）
5. 执行 GROUP BY 查询
6. 执行 ORDER BY 查询
7. 执行 LIMIT 查询
8. 禁止 INSERT 操作
9. 禁止 UPDATE 操作
10. 禁止 DELETE 操作
11. 禁止 DROP 操作
12. 捕获 SQL 语法错误
13. 捕获表不存在错误
14. 返回结果为空
15. 返回多行结果
"""

from unittest.mock import MagicMock, patch

from src.lc.tools.database_tool import get_database_query_tool

# 获取工具实例
database_tool = get_database_query_tool()


class TestDatabaseTool:
    """数据库查询工具测试类"""

    def test_execute_simple_select(self):
        """测试场景 1: 执行简单的 SELECT 查询"""
        # Arrange
        sql = "SELECT * FROM users"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                (1, "Alice", 30),
                (2, "Bob", 25),
            ]
            mock_cursor.description = [("id",), ("name",), ("age",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "Alice" in result
            assert "Bob" in result

    def test_execute_select_with_where(self):
        """测试场景 2: 执行带 WHERE 条件的查询"""
        # Arrange
        sql = "SELECT name, age FROM users WHERE age > 25"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("Alice", 30),
            ]
            mock_cursor.description = [("name",), ("age",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "Alice" in result
            assert "30" in result

    def test_execute_join_query(self):
        """测试场景 3: 执行 JOIN 查询"""
        # Arrange
        sql = """
        SELECT u.name, o.order_id
        FROM users u
        JOIN orders o ON u.id = o.user_id
        """

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("Alice", 101),
                ("Alice", 102),
            ]
            mock_cursor.description = [("name",), ("order_id",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "Alice" in result
            assert "101" in result

    def test_execute_aggregate_query(self):
        """测试场景 4: 执行聚合查询（COUNT、SUM 等）"""
        # Arrange
        sql = "SELECT COUNT(*) as total FROM users"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                (10,),
            ]
            mock_cursor.description = [
                ("total",),
            ]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "10" in result

    def test_execute_group_by_query(self):
        """测试场景 5: 执行 GROUP BY 查询"""
        # Arrange
        sql = "SELECT department, COUNT(*) as count FROM employees GROUP BY department"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("Engineering", 5),
                ("Sales", 3),
            ]
            mock_cursor.description = [("department",), ("count",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "Engineering" in result
            assert "5" in result

    def test_execute_order_by_query(self):
        """测试场景 6: 执行 ORDER BY 查询"""
        # Arrange
        sql = "SELECT name, age FROM users ORDER BY age DESC"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("Alice", 30),
                ("Bob", 25),
            ]
            mock_cursor.description = [("name",), ("age",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "Alice" in result

    def test_execute_limit_query(self):
        """测试场景 7: 执行 LIMIT 查询"""
        # Arrange
        sql = "SELECT * FROM users LIMIT 5"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                (1, "Alice", 30),
            ]
            mock_cursor.description = [("id",), ("name",), ("age",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")

    def test_forbid_insert_operation(self):
        """测试场景 8: 禁止 INSERT 操作"""
        # Arrange
        sql = "INSERT INTO users (name, age) VALUES ('Charlie', 35)"

        # Act
        result = database_tool.func(sql=sql)

        # Assert
        assert result.startswith("错误")
        assert "禁止" in result or "不允许" in result
        assert "INSERT" in result.upper()

    def test_forbid_update_operation(self):
        """测试场景 9: 禁止 UPDATE 操作"""
        # Arrange
        sql = "UPDATE users SET age = 31 WHERE name = 'Alice'"

        # Act
        result = database_tool.func(sql=sql)

        # Assert
        assert result.startswith("错误")
        assert "禁止" in result or "不允许" in result
        assert "UPDATE" in result.upper()

    def test_forbid_delete_operation(self):
        """测试场景 10: 禁止 DELETE 操作"""
        # Arrange
        sql = "DELETE FROM users WHERE id = 1"

        # Act
        result = database_tool.func(sql=sql)

        # Assert
        assert result.startswith("错误")
        assert "禁止" in result or "不允许" in result
        assert "DELETE" in result.upper()

    def test_forbid_drop_operation(self):
        """测试场景 11: 禁止 DROP 操作"""
        # Arrange
        sql = "DROP TABLE users"

        # Act
        result = database_tool.func(sql=sql)

        # Assert
        assert result.startswith("错误")
        assert "禁止" in result or "不允许" in result
        assert "DROP" in result.upper()

    def test_sql_syntax_error(self):
        """测试场景 12: 捕获 SQL 语法错误"""
        # Arrange
        sql = "SELECT * FORM users"  # FORM 应该是 FROM

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("syntax error near 'FORM'")
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert result.startswith("错误")
            assert "syntax" in result.lower() or "语法" in result

    def test_table_not_found_error(self):
        """测试场景 13: 捕获表不存在错误"""
        # Arrange
        sql = "SELECT * FROM non_existent_table"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("no such table: non_existent_table")
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert result.startswith("错误")
            assert "table" in result.lower() or "表" in result

    def test_empty_result(self):
        """测试场景 14: 返回结果为空"""
        # Arrange
        sql = "SELECT * FROM users WHERE age > 100"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.description = [("id",), ("name",), ("age",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "0" in result or "空" in result or "没有" in result

    def test_multiple_rows_result(self):
        """测试场景 15: 返回多行结果"""
        # Arrange
        sql = "SELECT * FROM users"

        # Mock 数据库连接
        with patch("src.lc.tools.database_tool.get_database_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                (1, "Alice", 30),
                (2, "Bob", 25),
                (3, "Charlie", 35),
            ]
            mock_cursor.description = [("id",), ("name",), ("age",)]
            mock_conn.return_value.cursor.return_value = mock_cursor

            # Act
            result = database_tool.func(sql=sql)

            # Assert
            assert not result.startswith("错误")
            assert "Alice" in result
            assert "Bob" in result
            assert "Charlie" in result

"""TaskExecutorAgent 增强功能集成测试

测试场景：
1. 使用 Python 工具执行计算任务
2. 使用 Python 工具执行数据处理任务
3. 使用数据库工具查询数据
4. 使用 HTTP 工具获取数据
5. 组合使用多个工具（HTTP + Python）
6. 组合使用多个工具（Database + Python）
7. 错误处理：Python 代码错误
8. 错误处理：数据库查询错误
9. 错误处理：HTTP 请求错误
10. 上下文传递：使用前置任务结果
"""

from unittest.mock import patch

import pytest

from src.lc.agents.task_executor import (
    create_task_executor_agent,
    execute_task,
    execute_task_with_context,
)


class TestTaskExecutorAgentEnhanced:
    """TaskExecutorAgent 增强功能集成测试类"""

    @pytest.mark.integration
    def test_execute_python_calculation_task(self):
        """测试场景 1: 使用 Python 工具执行计算任务"""
        # Arrange
        task_name = "计算斐波那契数列"
        task_description = "计算斐波那契数列的第 10 项"

        # Mock Python 工具
        with patch("src.lc.tools.python_tool.execute_python") as mock_python:
            mock_python.return_value = "Fibonacci(10) = 55"

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert not result.startswith("错误")
            # 注意：由于使用了 LLM，结果可能包含额外的文本
            # 我们只检查是否成功执行

    @pytest.mark.integration
    def test_execute_python_data_processing_task(self):
        """测试场景 2: 使用 Python 工具执行数据处理任务"""
        # Arrange
        task_name = "数据处理"
        task_description = "计算列表 [1, 2, 3, 4, 5] 的平均值"

        # Mock Python 工具
        with patch("src.lc.tools.python_tool.execute_python") as mock_python:
            mock_python.return_value = "Average: 3.0"

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert not result.startswith("错误")

    @pytest.mark.integration
    def test_execute_database_query_task(self):
        """测试场景 3: 使用数据库工具查询数据"""
        # Arrange
        task_name = "查询用户数据"
        task_description = "查询所有年龄大于 25 岁的用户"

        # Mock 数据库工具
        with patch("src.lc.tools.database_tool.query_database") as mock_db:
            mock_db.return_value = "查询结果：\nAlice (30)\nBob (28)"

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert not result.startswith("错误")

    @pytest.mark.integration
    def test_execute_http_request_task(self):
        """测试场景 4: 使用 HTTP 工具获取数据"""
        # Arrange
        task_name = "获取 API 数据"
        task_description = "访问 https://api.example.com/users 并获取用户列表"

        # Mock HTTP 工具
        with patch("src.lc.tools.http_tool.http_request") as mock_http:
            mock_http.return_value = '{"users": [{"name": "Alice"}, {"name": "Bob"}]}'

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert not result.startswith("错误")

    @pytest.mark.integration
    def test_combine_http_and_python_tools(self):
        """测试场景 5: 组合使用多个工具（HTTP + Python）"""
        # Arrange
        task_name = "获取并分析数据"
        task_description = "访问 https://api.example.com/sales 获取销售数据，然后计算总销售额"

        # Mock HTTP 工具
        with patch("src.lc.tools.http_tool.http_request") as mock_http:
            mock_http.return_value = '{"sales": [100, 200, 300]}'

            # Mock Python 工具
            with patch("src.lc.tools.python_tool.execute_python") as mock_python:
                mock_python.return_value = "Total sales: 600"

                # Act
                result = execute_task(task_name, task_description)

                # Assert
                assert not result.startswith("错误")

    @pytest.mark.integration
    def test_combine_database_and_python_tools(self):
        """测试场景 6: 组合使用多个工具（Database + Python）"""
        # Arrange
        task_name = "查询并分析数据"
        task_description = "查询所有用户的年龄，然后计算平均年龄"

        # Mock 数据库工具
        with patch("src.lc.tools.database_tool.query_database") as mock_db:
            mock_db.return_value = "Ages: 25, 30, 35, 40"

            # Mock Python 工具
            with patch("src.lc.tools.python_tool.execute_python") as mock_python:
                mock_python.return_value = "Average age: 32.5"

                # Act
                result = execute_task(task_name, task_description)

                # Assert
                assert not result.startswith("错误")

    @pytest.mark.integration
    def test_handle_python_code_error(self):
        """测试场景 7: 错误处理：Python 代码错误"""
        # Arrange
        task_name = "执行错误的 Python 代码"
        task_description = "执行 Python 代码：x = 10 / 0"

        # Mock Python 工具返回错误
        with patch("src.lc.tools.python_tool.execute_python") as mock_python:
            mock_python.return_value = "错误：ZeroDivisionError: division by zero"

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            # Agent 应该能够处理工具返回的错误
            assert "错误" in result or "失败" in result or "无法" in result

    @pytest.mark.integration
    def test_handle_database_query_error(self):
        """测试场景 8: 错误处理：数据库查询错误"""
        # Arrange
        task_name = "查询不存在的表"
        task_description = "查询表 non_existent_table"

        # Mock 数据库工具返回错误
        with patch("src.lc.tools.database_tool.query_database") as mock_db:
            mock_db.return_value = "错误：no such table: non_existent_table"

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert "错误" in result or "失败" in result or "无法" in result

    @pytest.mark.integration
    def test_handle_http_request_error(self):
        """测试场景 9: 错误处理：HTTP 请求错误"""
        # Arrange
        task_name = "访问无效的 URL"
        task_description = "访问 https://invalid-url-that-does-not-exist.com"

        # Mock HTTP 工具返回错误
        with patch("src.lc.tools.http_tool.http_request") as mock_http:
            mock_http.return_value = "错误：Connection failed"

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert "错误" in result or "失败" in result or "无法" in result

    @pytest.mark.integration
    def test_execute_with_context(self):
        """测试场景 10: 上下文传递：使用前置任务结果"""
        # Arrange
        task_name = "分析数据"
        task_description = "分析前一个任务获取的数据"
        context = {
            "Task 1": {"result": "数据已下载"},
            "Task 2": {"result": "数据已清洗"},
        }

        # Mock Python 工具
        with patch("src.lc.tools.python_tool.execute_python") as mock_python:
            mock_python.return_value = "Analysis complete"

            # Act
            result = execute_task_with_context(task_name, task_description, context)

            # Assert
            assert not result.startswith("错误")

    def test_create_agent_with_all_tools(self):
        """测试场景 11: 创建 Agent 时包含所有工具"""
        # Act
        agent = create_task_executor_agent()

        # Assert
        assert agent is not None
        # 验证 Agent 是 Runnable
        assert hasattr(agent, "invoke")

    @pytest.mark.integration
    def test_execute_task_empty_name(self):
        """测试场景 12: 错误处理：任务名称为空"""
        # Arrange
        task_name = ""
        task_description = "这是一个任务描述"

        # Act
        result = execute_task(task_name, task_description)

        # Assert
        assert result.startswith("错误")
        assert "任务名称" in result

    @pytest.mark.integration
    def test_execute_task_empty_description(self):
        """测试场景 13: 错误处理：任务描述为空"""
        # Arrange
        task_name = "任务名称"
        task_description = ""

        # Act
        result = execute_task(task_name, task_description)

        # Assert
        assert result.startswith("错误")
        assert "任务描述" in result

    @pytest.mark.integration
    def test_execute_python_with_json_output(self):
        """测试场景 14: Python 工具返回 JSON 格式数据"""
        # Arrange
        task_name = "生成 JSON 数据"
        task_description = "生成一个包含用户信息的 JSON 对象"

        # Mock Python 工具
        with patch("src.lc.tools.python_tool.execute_python") as mock_python:
            mock_python.return_value = '{"name": "Alice", "age": 30, "city": "Beijing"}'

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert not result.startswith("错误")

    @pytest.mark.integration
    def test_execute_database_with_aggregation(self):
        """测试场景 15: 数据库工具执行聚合查询"""
        # Arrange
        task_name = "统计用户数量"
        task_description = "统计每个部门的用户数量"

        # Mock 数据库工具
        with patch("src.lc.tools.database_tool.query_database") as mock_db:
            mock_db.return_value = """
查询结果：
Engineering: 10
Sales: 5
Marketing: 3
"""

            # Act
            result = execute_task(task_name, task_description)

            # Assert
            assert not result.startswith("错误")

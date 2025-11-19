"""Python 执行工具单元测试

测试场景：
1. 执行简单的 Python 代码（print）
2. 执行数学计算
3. 执行字符串操作
4. 执行列表操作
5. 执行字典操作
6. 执行导入标准库（math、json 等）
7. 执行多行代码
8. 捕获标准输出
9. 捕获错误（语法错误）
10. 捕获错误（运行时错误）
11. 超时控制（防止无限循环）
12. 禁止危险操作（文件写入、系统调用等）
13. 返回变量值
14. 执行函数定义和调用
"""

import platform

import pytest

from src.lc.tools.python_tool import get_python_execution_tool

# 获取工具实例
python_tool = get_python_execution_tool()


class TestPythonTool:
    """Python 执行工具测试类"""

    def test_execute_simple_print(self):
        """测试场景 1: 执行简单的 Python 代码（print）"""
        # Arrange
        code = "print('Hello, World!')"

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "Hello, World!" in result
        assert not result.startswith("错误")

    def test_execute_math_calculation(self):
        """测试场景 2: 执行数学计算"""
        # Arrange
        code = "result = 2 + 3 * 4\nprint(result)"

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "14" in result
        assert not result.startswith("错误")

    def test_execute_string_operation(self):
        """测试场景 3: 执行字符串操作"""
        # Arrange
        code = """
text = "hello world"
result = text.upper()
print(result)
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "HELLO WORLD" in result
        assert not result.startswith("错误")

    def test_execute_list_operation(self):
        """测试场景 4: 执行列表操作"""
        # Arrange
        code = """
numbers = [1, 2, 3, 4, 5]
total = sum(numbers)
print(f"Total: {total}")
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "Total: 15" in result
        assert not result.startswith("错误")

    def test_execute_dict_operation(self):
        """测试场景 5: 执行字典操作"""
        # Arrange
        code = """
data = {"name": "Alice", "age": 30}
print(f"Name: {data['name']}, Age: {data['age']}")
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "Name: Alice" in result
        assert "Age: 30" in result
        assert not result.startswith("错误")

    def test_execute_import_stdlib(self):
        """测试场景 6: 执行导入标准库（math、json 等）"""
        # Arrange
        code = """
import math
import json

result = math.sqrt(16)
data = json.dumps({"value": result})
print(data)
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "4.0" in result or "4" in result
        assert not result.startswith("错误")

    def test_execute_multiline_code(self):
        """测试场景 7: 执行多行代码"""
        # Arrange
        code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(10)
print(f"Fibonacci(10) = {result}")
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "55" in result
        assert not result.startswith("错误")

    def test_capture_stdout(self):
        """测试场景 8: 捕获标准输出"""
        # Arrange
        code = """
print("Line 1")
print("Line 2")
print("Line 3")
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        assert not result.startswith("错误")

    def test_syntax_error(self):
        """测试场景 9: 捕获错误（语法错误）"""
        # Arrange
        code = "print('Hello"  # 缺少右引号

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert result.startswith("错误")
        assert "语法错误" in result or "SyntaxError" in result

    def test_runtime_error(self):
        """测试场景 10: 捕获错误（运行时错误）"""
        # Arrange
        code = """
x = 10
y = 0
result = x / y  # 除以零
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert result.startswith("错误")
        assert "ZeroDivisionError" in result or "除" in result

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Windows 不支持 signal.alarm，超时控制需要其他实现方式",
    )
    def test_timeout_control(self):
        """测试场景 11: 超时控制（防止无限循环）"""
        # Arrange
        code = """
while True:
    pass  # 无限循环
"""

        # Act
        result = python_tool.func(code=code, timeout=1)

        # Assert
        assert result.startswith("错误")
        assert "超时" in result or "timeout" in result.lower()

    def test_forbidden_file_write(self):
        """测试场景 12: 禁止危险操作（文件写入）"""
        # Arrange
        code = """
with open('/tmp/test.txt', 'w') as f:
    f.write('test')
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        # 应该被禁止或返回错误
        assert result.startswith("错误") or "禁止" in result

    def test_forbidden_system_call(self):
        """测试场景 12.2: 禁止危险操作（系统调用）"""
        # Arrange
        code = """
import os
os.system('ls')
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        # 应该被禁止或返回错误
        assert result.startswith("错误") or "禁止" in result

    def test_return_variable_value(self):
        """测试场景 13: 返回变量值"""
        # Arrange
        code = """
result = 42
print(f"The answer is {result}")
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "42" in result
        assert not result.startswith("错误")

    def test_execute_function_definition(self):
        """测试场景 14: 执行函数定义和调用"""
        # Arrange
        code = """
def greet(name):
    return f"Hello, {name}!"

message = greet("Alice")
print(message)
"""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert "Hello, Alice!" in result
        assert not result.startswith("错误")

    def test_empty_code(self):
        """测试场景 15: 空代码"""
        # Arrange
        code = ""

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert result.startswith("错误")
        assert "不能为空" in result

    def test_whitespace_only_code(self):
        """测试场景 16: 只有空白字符的代码"""
        # Arrange
        code = "   \n\n   "

        # Act
        result = python_tool.func(code=code)

        # Assert
        assert result.startswith("错误")
        assert "不能为空" in result

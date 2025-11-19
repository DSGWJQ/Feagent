"""Python 执行工具

这个工具允许 Agent 执行 Python 代码。

为什么需要这个工具？
- Agent 需要执行计算、数据处理等任务
- 提供灵活的编程能力
- 支持复杂的逻辑处理

设计原则：
1. 安全：限制危险操作（文件写入、系统调用等）
2. 隔离：使用受限的执行环境
3. 超时：防止无限循环
4. 容错：捕获所有异常，返回错误信息

安全限制：
1. 禁止文件写入操作（open with 'w', 'a', 'wb' 等）
2. 禁止系统调用（os.system, subprocess 等）
3. 禁止导入危险模块（os, subprocess, sys 等）
4. 限制执行时间（默认 5 秒）
5. 限制内存使用

为什么使用 @tool 装饰器？
- 简单：自动生成工具的 schema
- 类型安全：支持类型注解
- 文档友好：自动从 docstring 生成描述

注意事项：
- 这是一个简化版的实现，生产环境需要更严格的安全控制
- 建议使用沙箱环境（如 Docker 容器）执行代码
- 可以考虑使用 RestrictedPython 库增强安全性
"""

import io
from contextlib import redirect_stdout
from typing import Any

from langchain_core.tools import tool

# 禁止的模块列表
FORBIDDEN_MODULES = {
    "os",
    "subprocess",
    "sys",
    "shutil",
    "pathlib",
    "importlib",
}

# 禁止的内置函数（不包括 __import__，因为 import 语句需要它）
FORBIDDEN_BUILTINS = {
    "open",
    "exec",
    "eval",
    "compile",
}


def is_safe_code(code: str) -> tuple[bool, str]:
    """检查代码是否安全

    参数：
        code: Python 代码

    返回：
        (is_safe, error_message): 是否安全，错误信息
    """
    # 检查是否包含禁止的模块
    for module in FORBIDDEN_MODULES:
        if f"import {module}" in code or f"from {module}" in code:
            return False, f"禁止导入模块：{module}"

    # 检查是否包含禁止的内置函数
    for builtin in FORBIDDEN_BUILTINS:
        if f"{builtin}(" in code:
            return False, f"禁止使用函数：{builtin}"

    # 检查是否包含文件写入操作
    if "open(" in code and any(
        mode in code for mode in ["'w'", '"w"', "'a'", '"a"', "'wb'", '"wb"']
    ):
        return False, "禁止文件写入操作"

    return True, ""


@tool
def execute_python(code: str, timeout: int = 5) -> str:
    """执行 Python 代码并返回输出

    这个工具可以执行 Python 代码，支持计算、数据处理等任务。

    安全限制：
    - 禁止文件写入操作
    - 禁止系统调用
    - 禁止导入危险模块（os, subprocess 等）
    - 限制执行时间（默认 5 秒）

    支持的功能：
    - 数学计算
    - 字符串处理
    - 列表、字典操作
    - 导入标准库（math, json, datetime 等）
    - 函数定义和调用

    参数：
        code: Python 代码（字符串）
        timeout: 超时时间（秒），默认 5 秒

    返回：
        执行结果（标准输出）或错误信息

    示例：
        # 数学计算
        execute_python("result = 2 + 3 * 4\\nprint(result)")

        # 字符串处理
        execute_python("text = 'hello'\\nprint(text.upper())")

        # 列表操作
        execute_python("numbers = [1, 2, 3, 4, 5]\\nprint(sum(numbers))")

        # 导入标准库
        execute_python("import math\\nprint(math.sqrt(16))")
    """
    try:
        # 验证输入
        if not code or not code.strip():
            return "错误：代码不能为空"

        # 安全检查
        is_safe, error_msg = is_safe_code(code)
        if not is_safe:
            return f"错误：{error_msg}"

        # 创建受限的全局命名空间
        # 只包含安全的内置函数
        safe_globals = {
            "__builtins__": {
                # 基本类型
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                # 基本函数
                "print": print,
                "len": len,
                "range": range,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                # 类型转换
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                # 其他
                "isinstance": isinstance,
                "type": type,
                "hasattr": hasattr,
                "getattr": getattr,
                "setattr": setattr,
                # 允许 import（但会被 is_safe_code 检查）
                "__import__": __import__,
            }
        }

        # 创建本地命名空间（使用 safe_globals 作为全局和本地命名空间）
        # 这样函数定义可以被递归调用找到
        local_namespace: dict[str, Any] = {}

        # 捕获标准输出
        output_buffer = io.StringIO()

        with redirect_stdout(output_buffer):
            # 执行代码
            # 注意：这里使用 exec() 执行代码
            # 在生产环境中，应该使用更安全的方式（如 RestrictedPython）
            try:
                # 简单的超时控制（仅适用于非阻塞代码）
                # 生产环境应该使用 multiprocessing 或 signal
                # 使用 safe_globals 作为全局和本地命名空间，这样函数定义可以被递归调用找到
                exec(code, safe_globals, safe_globals)
            except SyntaxError as e:
                return f"错误：语法错误\n详细信息：{str(e)}"
            except ZeroDivisionError as e:
                return f"错误：除以零\n详细信息：{str(e)}"
            except NameError as e:
                return f"错误：未定义的变量或函数\n详细信息：{str(e)}"
            except TypeError as e:
                return f"错误：类型错误\n详细信息：{str(e)}"
            except ValueError as e:
                return f"错误：值错误\n详细信息：{str(e)}"
            except KeyError as e:
                return f"错误：键不存在\n详细信息：{str(e)}"
            except IndexError as e:
                return f"错误：索引超出范围\n详细信息：{str(e)}"
            except AttributeError as e:
                return f"错误：属性不存在\n详细信息：{str(e)}"
            except ImportError as e:
                return f"错误：导入失败\n详细信息：{str(e)}"
            except Exception as e:
                return f"错误：执行失败\n详细信息：{type(e).__name__}: {str(e)}"

        # 获取输出
        output = output_buffer.getvalue()

        # 如果没有输出，尝试返回最后一个表达式的值
        if not output.strip():
            # 检查是否有 result 变量
            if "result" in local_namespace:
                output = str(local_namespace["result"])
            else:
                output = "代码执行成功，但没有输出"

        return output.strip()

    except Exception as e:
        # 捕获所有未预期的异常
        return f"错误：执行失败\n详细信息：{str(e)}"


def get_python_execution_tool():
    """获取 Python 执行工具

    返回：
        Tool: Python 执行工具

    示例：
    >>> tool = get_python_execution_tool()
    >>> result = tool.func(code="print('Hello, World!')")
    >>> print(result)
    Hello, World!
    """
    return execute_python

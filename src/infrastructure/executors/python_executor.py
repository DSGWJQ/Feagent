"""Python Executor（Python 执行器）

Infrastructure 层：实现 Python 代码执行节点执行器

设计原则：
- 使用 Python 的 exec 和 eval 执行代码
- 为了安全性，限制访问危险的模块和内置函数
- 提供安全的执行环境
"""

import asyncio
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class PythonExecutor(NodeExecutor):
    """Python 代码执行节点执行器

    配置参数：
        code: Python 代码字符串

    返回：
        代码执行后 result 变量的值
    """

    # 被禁止的关键字（出于安全考虑）
    FORBIDDEN_KEYWORDS = [
        "import os",
        "import sys",
        "import subprocess",
        "import socket",
        "import pickle",
        "import marshal",
        "__import__",
        "from os",
        "from sys",
        "from subprocess",
    ]

    # 允许的安全内置函数
    SAFE_BUILTINS = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "format": format,
        "frozenset": frozenset,
        "int": int,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "pow": pow,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 Python 代码节点

        参数：
            node: 节点实体
            inputs: 输入数据（来自前驱节点）
            context: 执行上下文

        返回：
            代码执行后 result 变量的值
        """
        code = node.config.get("code", "")

        if not code:
            raise DomainError("Python 节点缺少代码")

        # 检查禁止的模块和操作
        code_lower = code.lower()
        for forbidden in self.FORBIDDEN_KEYWORDS:
            if forbidden.lower() in code_lower:
                raise DomainError(f"Python 代码包含被禁止的操作: {forbidden}")

        # 准备执行环境
        exec_context = {
            "__builtins__": self.SAFE_BUILTINS,
        }

        # 将输入映射为 input1, input2, ...
        for i, (_key, value) in enumerate(inputs.items(), 1):
            exec_context[f"input{i}"] = value

        # 添加上下文变量
        exec_context["context"] = context

        try:
            # KISS: offload CPU-bound exec to keep the event loop responsive for SSE.
            await asyncio.to_thread(exec, code, exec_context)

            # 返回结果（假设代码中有 result 变量赋值）
            return exec_context.get("result")

        except SyntaxError as e:
            raise DomainError(f"Python 代码执行失败: 语法错误 - {str(e)}") from e
        except Exception as e:
            raise DomainError(f"Python 代码执行失败: {str(e)}") from e

"""JavaScript Executor（JavaScript 执行器）

Infrastructure 层：实现 JavaScript 代码执行节点执行器

注意：由于安全原因，实际生产环境应该使用沙箱环境执行 JavaScript
这里使用 Python 的 eval 作为简化实现
"""

from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class JavaScriptExecutor(NodeExecutor):
    """JavaScript 代码执行节点执行器

    注意：这是一个简化实现，实际应该使用 Node.js 或 QuickJS 等 JS 引擎
    """

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 JavaScript 节点

        配置参数：
            code: JavaScript 代码
        """
        code = node.config.get("code", "")

        if not code:
            raise DomainError("JavaScript 节点缺少代码")

        # 准备执行环境
        # 将输入映射为 input1, input2, ...
        exec_context = {}
        for i, (_key, value) in enumerate(inputs.items(), 1):
            exec_context[f"input{i}"] = value

        # 添加上下文变量
        exec_context["context"] = context

        # 简化实现：将 JavaScript 代码转换为 Python 代码
        # 实际应该使用 JS 引擎
        try:
            # 移除 JavaScript 特有的语法
            python_code = code.replace("const ", "").replace("let ", "").replace("var ", "")
            python_code = python_code.replace("===", "==").replace("!==", "!=")

            # 执行代码
            exec(python_code, exec_context)

            # 返回结果（假设代码中有 return 语句）
            # 这是一个简化实现，实际应该捕获 return 值
            return exec_context.get("result", inputs.get(next(iter(inputs))) if inputs else None)

        except Exception as e:
            raise DomainError(f"JavaScript 代码执行失败: {str(e)}") from e


class ConditionalExecutor(NodeExecutor):
    """条件分支节点执行器"""

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 Conditional 节点

        配置参数：
            condition: 条件表达式
        """
        condition = node.config.get("condition", "")

        if not condition:
            raise DomainError("Conditional 节点缺少条件表达式")

        # 准备执行环境
        exec_context = {}
        for i, (_key, value) in enumerate(inputs.items(), 1):
            exec_context[f"input{i}"] = value

        exec_context["context"] = context

        # 评估条件
        try:
            # 简化实现：使用 eval 评估条件
            # 实际应该使用更安全的表达式解析器
            # 提供一些安全的内置函数
            safe_builtins = {
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "len": len,
                "abs": abs,
                "min": min,
                "max": max,
            }
            result = eval(condition, {"__builtins__": safe_builtins}, exec_context)
            return {"result": bool(result), "branch": "true" if result else "false"}
        except Exception as e:
            raise DomainError(f"条件表达式评估失败: {str(e)}") from e

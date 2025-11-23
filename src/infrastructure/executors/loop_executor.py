"""Loop Executor（循环执行器）

Infrastructure 层：实现循环节点执行器

支持的循环类型：
- for_each: 遍历数组的for循环
- range: 指定范围的循环
- while: 基于条件的while循环
"""

from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class LoopExecutor(NodeExecutor):
    """循环节点执行器

    支持多种循环类型，包括for_each、range、while等

    配置参数：
        type: 循环类型（for_each, range, while）
        [其他参数根据循环类型不同而不同]
    """

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
        """执行循环节点

        参数：
            node: 节点实体
            inputs: 输入数据（来自前驱节点）
            context: 执行上下文

        返回：
            所有迭代结果的数组
        """
        loop_type = node.config.get("type", "")

        if not loop_type:
            raise DomainError("Loop 节点缺少循环类型")

        if loop_type == "for_each":
            return await self._for_each_loop(node.config, inputs, context)
        elif loop_type == "range":
            return await self._range_loop(node.config, inputs, context)
        elif loop_type == "while":
            return await self._while_loop(node.config, inputs, context)
        else:
            raise DomainError(f"不支持的循环类型: {loop_type}")

    async def _for_each_loop(
        self, config: dict, inputs: dict[str, Any], context: dict[str, Any]
    ) -> list:
        """for_each循环：遍历数组中的每个元素

        配置参数：
            array: 数组字段名
            code: 执行的Python代码（可选）
            operation: 简单操作类型（可选，如multiply）
            multiplier: 操作参数（可选）
            skip_none: 是否跳过None结果（默认False）
        """
        array_field = config.get("array", "")
        code = config.get("code", "")
        operation = config.get("operation", "")
        skip_none = config.get("skip_none", False)

        if not array_field:
            raise DomainError("for_each 循环缺少 array 配置")

        # 获取数组数据
        first_input = next(iter(inputs.values())) if inputs else {}
        array = self._get_nested_value(first_input, array_field)

        if not isinstance(array, list):
            raise DomainError(f"字段 {array_field} 不是数组")

        results = []

        for index, item in enumerate(array):
            # 准备执行环境
            exec_context = {
                "__builtins__": self.SAFE_BUILTINS,
                "item": item,
                "index": index,
                "context": context,
            }

            try:
                if code:
                    # 执行Python代码
                    exec(code, exec_context)
                    result = exec_context.get("result")
                elif operation == "multiply":
                    # 简单的乘法操作
                    multiplier = config.get("multiplier", 1)
                    result = item * multiplier
                else:
                    # 默认返回元素本身
                    result = item

                # 跳过None结果（如果配置了skip_none）
                if skip_none and result is None:
                    continue

                results.append(result)

            except Exception as e:
                raise DomainError(f"循环执行失败（索引 {index}）: {str(e)}")

        return results

    async def _range_loop(
        self, config: dict, inputs: dict[str, Any], context: dict[str, Any]
    ) -> list:
        """range循环：指定范围的循环

        配置参数：
            start: 起始值（默认0）
            end: 结束值（必需）
            step: 步长（默认1）
            code: 执行的Python代码
        """
        start = config.get("start", 0)
        end = config.get("end")
        step = config.get("step", 1)
        code = config.get("code", "")

        if end is None:
            raise DomainError("range 循环缺少 end 配置")

        if not code:
            raise DomainError("range 循环缺少 code 配置")

        results = []

        for i in range(start, end, step):
            # 准备执行环境
            exec_context = {
                "__builtins__": self.SAFE_BUILTINS,
                "i": i,
                "context": context,
            }

            try:
                exec(code, exec_context)
                result = exec_context.get("result")
                results.append(result)

            except Exception as e:
                raise DomainError(f"循环执行失败（i={i}）: {str(e)}")

        return results

    async def _while_loop(
        self, config: dict, inputs: dict[str, Any], context: dict[str, Any]
    ) -> list:
        """while循环：基于条件的循环

        配置参数：
            condition: 循环条件表达式
            code: 执行的Python代码
            max_iterations: 最大迭代次数（必需，防止无限循环）
            initial_vars: 初始变量字典（可选）
        """
        condition = config.get("condition", "")
        code = config.get("code", "")
        max_iterations = config.get("max_iterations", 100)
        initial_vars = config.get("initial_vars", {})

        if not condition:
            raise DomainError("while 循环缺少 condition 配置")

        if not code:
            raise DomainError("while 循环缺少 code 配置")

        results = []
        iteration_count = 0

        # 准备执行环境
        exec_context = {
            "__builtins__": self.SAFE_BUILTINS,
            "context": context,
        }

        # 添加初始变量
        exec_context.update(initial_vars)

        while iteration_count < max_iterations:
            try:
                # 评估条件
                condition_result = eval(condition, exec_context)

                if not condition_result:
                    break

                # 执行代码
                exec(code, exec_context)
                result = exec_context.get("result")
                results.append(result)

                iteration_count += 1

            except Exception as e:
                raise DomainError(f"循环执行失败（迭代 {iteration_count}）: {str(e)}")

        return results

    @staticmethod
    def _get_nested_value(data: Any, path: str) -> Any:
        """获取嵌套值

        参数：
            data: 数据对象
            path: 路径 (e.g., "user.items")

        返回：
            路径指向的值
        """
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    raise DomainError(f"字段不存在: {path}")
            else:
                raise DomainError(f"无法访问嵌套字段: {path}")

        return current

"""Transform Executor（数据转换执行器）

Infrastructure 层：实现数据转换节点执行器

支持的转换类型：
- field_mapping：字段映射（重命名字段）
- type_conversion：类型转换
- field_extraction：提取嵌套字段
- array_mapping：数组元素映射
- filtering：过滤数组
- aggregation：聚合数据
- custom：自定义转换函数
"""

import statistics
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class TransformExecutor(NodeExecutor):
    """数据转换节点执行器

    支持多种数据转换操作，包括字段映射、类型转换、数据提取等

    配置参数：
        type: 转换类型（field_mapping, type_conversion, field_extraction等）
        [其他参数根据转换类型不同而不同]
    """

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行数据转换节点

        参数：
            node: 节点实体
            inputs: 输入数据（来自前驱节点）
            context: 执行上下文

        返回：
            转换后的数据
        """
        transform_type = node.config.get("type", "")

        if not transform_type:
            raise DomainError("Transform 节点缺少转换类型")

        if transform_type == "field_mapping":
            return self._field_mapping(node.config, inputs)
        elif transform_type == "type_conversion":
            return self._type_conversion(node.config, inputs)
        elif transform_type == "field_extraction":
            return self._field_extraction(node.config, inputs)
        elif transform_type == "array_mapping":
            return self._array_mapping(node.config, inputs)
        elif transform_type == "filtering":
            return self._filtering(node.config, inputs)
        elif transform_type == "aggregation":
            return self._aggregation(node.config, inputs)
        elif transform_type == "custom":
            return self._custom_transform(node.config, inputs)
        else:
            raise DomainError(f"不支持的转换类型: {transform_type}")

    @staticmethod
    def _field_mapping(config: dict, inputs: dict[str, Any]) -> dict:
        """字段映射：重命名和重组字段

        配置参数：
            mapping: 映射字典 {新字段名: 路径}
        """
        mapping = config.get("mapping", {})
        if not mapping:
            raise DomainError("field_mapping 转换缺少 mapping 配置")

        result = {}
        first_input = next(iter(inputs.values())) if inputs else {}

        for output_key, input_path in mapping.items():
            # 处理路径：如果以 "input." 开头，则从输入数据获取
            if input_path.startswith("input."):
                # 去掉 "input." 前缀
                actual_path = input_path[6:]
                value = TransformExecutor._get_nested_value(first_input, actual_path)
            else:
                # 直接从inputs获取
                value = TransformExecutor._get_nested_value(inputs, input_path)
            result[output_key] = value

        return result

    @staticmethod
    def _type_conversion(config: dict, inputs: dict[str, Any]) -> dict:
        """类型转换

        配置参数：
            conversions: 转换配置 {字段: 目标类型}
        """
        conversions = config.get("conversions", {})
        if not conversions:
            raise DomainError("type_conversion 转换缺少 conversions 配置")

        # 获取第一个输入的值
        first_input = next(iter(inputs.values())) if inputs else {}
        if not isinstance(first_input, dict):
            first_input = {"value": first_input}

        result = {}
        for field, target_type in conversions.items():
            value = first_input.get(field)
            if value is None:
                continue

            try:
                if target_type == "int":
                    result[field] = int(value)
                elif target_type == "float":
                    result[field] = float(value)
                elif target_type == "str":
                    result[field] = str(value)
                elif target_type == "bool":
                    # 处理字符串布尔值
                    if isinstance(value, str):
                        value_lower = value.lower()
                        if value_lower in ["true", "1"]:
                            result[field] = True
                        elif value_lower in ["false", "0"]:
                            result[field] = False
                        else:
                            # 其他字符串按标准bool()处理（非空为True）
                            result[field] = bool(value)
                    else:
                        result[field] = bool(value)
                else:
                    result[field] = value
            except (ValueError, TypeError) as e:
                raise DomainError(f"类型转换失败: {field} -> {target_type}: {str(e)}") from e

        return result

    @staticmethod
    def _field_extraction(config: dict, inputs: dict[str, Any]) -> Any:
        """提取嵌套字段

        配置参数：
            path: 字段路径 (e.g., "user.profile.address.city")
        """
        path = config.get("path", "")
        if not path:
            raise DomainError("field_extraction 转换缺少 path 配置")

        first_input = next(iter(inputs.values())) if inputs else {}
        return TransformExecutor._get_nested_value({"data": first_input}, f"data.{path}")

    @staticmethod
    def _array_mapping(config: dict, inputs: dict[str, Any]) -> list:
        """数组元素映射

        配置参数：
            field: 数组字段名
            mapping: 字段映射配置
        """
        field = config.get("field", "")
        mapping = config.get("mapping", {})

        if not field or not mapping:
            raise DomainError("array_mapping 转换缺少 field 或 mapping 配置")

        first_input = next(iter(inputs.values())) if inputs else {}
        array = TransformExecutor._get_nested_value(first_input, field)

        if not isinstance(array, list):
            raise DomainError(f"字段 {field} 不是数组")

        result = []
        for item in array:
            mapped_item = {}
            for output_key, input_key in mapping.items():
                mapped_item[output_key] = item.get(input_key) if isinstance(item, dict) else item
            result.append(mapped_item)

        return result

    @staticmethod
    def _filtering(config: dict, inputs: dict[str, Any]) -> list:
        """过滤数据

        配置参数：
            field: 数组字段名
            condition: 条件表达式 (e.g., "price > 100")
        """
        field = config.get("field", "")
        condition = config.get("condition", "")

        if not field or not condition:
            raise DomainError("filtering 转换缺少 field 或 condition 配置")

        first_input = next(iter(inputs.values())) if inputs else {}
        array = TransformExecutor._get_nested_value(first_input, field)

        if not isinstance(array, list):
            raise DomainError(f"字段 {field} 不是数组")

        result = []
        for item in array:
            # 构建条件表达式的上下文
            if isinstance(item, dict):
                context = item
            else:
                context = {"value": item}

            # 安全的条件评估
            safe_builtins = {
                "len": len,
                "abs": abs,
                "min": min,
                "max": max,
            }

            try:
                if eval(condition, {"__builtins__": safe_builtins}, context):
                    result.append(item)
            except Exception as e:
                raise DomainError(f"条件评估失败: {str(e)}") from e

        return result

    @staticmethod
    def _aggregation(config: dict, inputs: dict[str, Any]) -> dict:
        """聚合数据

        配置参数：
            field: 数组字段名
            operations: 操作列表 (e.g., ["sum:price", "count", "avg:price"])
        """
        field = config.get("field", "")
        operations = config.get("operations", [])

        if not field or not operations:
            raise DomainError("aggregation 转换缺少 field 或 operations 配置")

        first_input = next(iter(inputs.values())) if inputs else {}
        array = TransformExecutor._get_nested_value(first_input, field)

        if not isinstance(array, list):
            raise DomainError(f"字段 {field} 不是数组")

        result = {}

        for operation in operations:
            if operation == "count":
                result["count"] = len(array)
            elif operation.startswith("sum:"):
                field_name = operation[4:]
                values = [
                    item.get(field_name, 0) if isinstance(item, dict) else 0 for item in array
                ]
                result[f"sum_{field_name}"] = sum(values)
            elif operation.startswith("avg:"):
                field_name = operation[4:]
                values = [
                    item.get(field_name, 0) if isinstance(item, dict) else 0 for item in array
                ]
                result[f"avg_{field_name}"] = statistics.mean(values) if values else 0
            elif operation.startswith("max:"):
                field_name = operation[4:]
                values = [
                    item.get(field_name, 0) if isinstance(item, dict) else 0 for item in array
                ]
                result[f"max_{field_name}"] = max(values) if values else 0
            elif operation.startswith("min:"):
                field_name = operation[4:]
                values = [
                    item.get(field_name, 0) if isinstance(item, dict) else 0 for item in array
                ]
                result[f"min_{field_name}"] = min(values) if values else 0

        return result

    @staticmethod
    def _custom_transform(config: dict, inputs: dict[str, Any]) -> Any:
        """自定义转换函数

        配置参数：
            function: 函数名 (upper, lower, reverse, len等)
            field: 目标字段（可选，默认为 input1）
        """
        function_name = config.get("function", "")

        if not function_name:
            raise DomainError("custom 转换缺少 function 配置")

        first_input = next(iter(inputs.values())) if inputs else None

        try:
            if function_name == "upper":
                return (
                    first_input.upper()
                    if isinstance(first_input, str)
                    else str(first_input).upper()
                )
            elif function_name == "lower":
                return (
                    first_input.lower()
                    if isinstance(first_input, str)
                    else str(first_input).lower()
                )
            elif function_name == "reverse":
                return first_input[::-1] if isinstance(first_input, (str | list)) else first_input
            elif function_name == "len":
                return len(first_input) if isinstance(first_input, (str | list | dict)) else 0
            elif function_name == "abs":
                return abs(first_input) if isinstance(first_input, (int | float)) else first_input
            else:
                raise DomainError(f"不支持的自定义函数: {function_name}")
        except Exception as e:
            raise DomainError(f"自定义转换失败: {str(e)}") from e

    @staticmethod
    def _get_nested_value(data: Any, path: str) -> Any:
        """获取嵌套值

        参数：
            data: 数据对象
            path: 路径 (e.g., "user.profile.name")

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

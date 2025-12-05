"""ToolParameterValidator - 工具参数验证器 - 阶段 3

业务定义：
- 根据工具定义验证调用参数
- 检查必填参数、类型匹配、枚举值、多余参数
- 返回结构化的验证错误供协调者/Agent 处理

设计原则：
- 支持严格模式和宽松模式
- 提供详细的错误信息
- 支持默认值填充
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.domain.entities.tool import Tool

# =============================================================================
# 错误类型定义
# =============================================================================


class ValidationErrorType(str, Enum):
    """验证错误类型枚举"""

    MISSING_REQUIRED = "missing_required"  # 缺少必填参数
    TYPE_MISMATCH = "type_mismatch"  # 类型不匹配
    INVALID_ENUM = "invalid_enum"  # 枚举值无效
    EXTRA_PARAMETER = "extra_parameter"  # 多余参数
    CONSTRAINT_VIOLATION = "constraint_violation"  # 约束违反


@dataclass
class ValidationErrorDetail:
    """验证错误详情

    属性说明：
    - error_type: 错误类型
    - parameter_name: 参数名称
    - message: 错误消息
    - expected: 期望值（可选）
    - actual: 实际值（可选）
    """

    error_type: ValidationErrorType
    parameter_name: str
    message: str
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "error_type": self.error_type.value,
            "parameter_name": self.parameter_name,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class ValidationResult:
    """验证结果

    属性说明：
    - is_valid: 是否有效
    - errors: 错误列表
    - validated_params: 验证后的参数（包含默认值）
    """

    is_valid: bool
    errors: list[ValidationErrorDetail]
    validated_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "validated_params": self.validated_params,
        }


# =============================================================================
# 异常定义
# =============================================================================


class ToolValidationError(Exception):
    """工具验证异常

    当参数验证失败时抛出，包含结构化的错误信息
    """

    def __init__(self, tool_name: str, errors: list[ValidationErrorDetail]):
        self.tool_name = tool_name
        self.errors = errors
        error_msgs = [f"{e.parameter_name}: {e.message}" for e in errors]
        message = f"工具 '{tool_name}' 参数验证失败: {'; '.join(error_msgs)}"
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "tool_name": self.tool_name,
            "errors": [e.to_dict() for e in self.errors],
            "error_count": len(self.errors),
        }


# =============================================================================
# 类型检查器
# =============================================================================


class TypeChecker:
    """类型检查器

    根据参数类型定义检查实际值的类型
    """

    # 类型映射
    TYPE_VALIDATORS = {
        "string": lambda v: isinstance(v, str),
        "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "any": lambda v: True,  # any 类型接受任何值
    }

    @classmethod
    def check(cls, param_type: str, value: Any) -> bool:
        """检查值是否符合类型

        参数：
            param_type: 参数类型（string/number/boolean/object/array/any）
            value: 实际值

        返回：
            是否类型匹配
        """
        validator = cls.TYPE_VALIDATORS.get(param_type.lower())
        if validator is None:
            return True  # 未知类型默认通过
        return validator(value)

    @classmethod
    def get_actual_type(cls, value: Any) -> str:
        """获取值的实际类型名称"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, str):
            return "string"
        if isinstance(value, int | float):
            return "number"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        return type(value).__name__


# =============================================================================
# 参数验证器
# =============================================================================


class ToolParameterValidator:
    """工具参数验证器

    功能：
    1. 验证必填参数
    2. 验证参数类型
    3. 验证枚举值
    4. 检测多余参数（严格模式）
    5. 填充默认值
    """

    def __init__(self, strict_mode: bool = False):
        """初始化验证器

        参数：
            strict_mode: 严格模式，检测多余参数
        """
        self._strict_mode = strict_mode

    @property
    def strict_mode(self) -> bool:
        """是否严格模式"""
        return self._strict_mode

    def validate(self, tool: Tool, params: dict[str, Any]) -> ValidationResult:
        """验证参数

        参数：
            tool: 工具定义
            params: 调用参数

        返回：
            ValidationResult 验证结果
        """
        errors: list[ValidationErrorDetail] = []
        validated_params: dict[str, Any] = {}

        # 获取参数定义
        param_definitions = {p.name: p for p in tool.parameters}
        defined_param_names = set(param_definitions.keys())
        provided_param_names = set(params.keys())

        # 1. 检查必填参数（有默认值的参数不报缺失错误）
        for param in tool.parameters:
            if param.required:
                if param.name not in params:
                    # 如果有默认值，则不报错（后面会填充默认值）
                    if param.default is None:
                        errors.append(
                            ValidationErrorDetail(
                                error_type=ValidationErrorType.MISSING_REQUIRED,
                                parameter_name=param.name,
                                message=f"缺少必填参数: {param.name}",
                            )
                        )
                elif params[param.name] is None:
                    # 如果有默认值，则不报错（后面会填充默认值）
                    if param.default is None:
                        errors.append(
                            ValidationErrorDetail(
                                error_type=ValidationErrorType.MISSING_REQUIRED,
                                parameter_name=param.name,
                                message=f"必填参数 '{param.name}' 不能为 null",
                            )
                        )

        # 2. 验证已提供的参数
        for param_name, value in params.items():
            # 跳过 None 值的可选参数
            if value is None:
                param_def = param_definitions.get(param_name)
                if param_def and not param_def.required:
                    continue

            if param_name in param_definitions:
                param_def = param_definitions[param_name]

                # 跳过已标记为缺失必填的参数（避免重复错误）
                if param_def.required and (param_name not in params or params[param_name] is None):
                    continue

                # 检查类型
                if value is not None and not TypeChecker.check(param_def.type, value):
                    errors.append(
                        ValidationErrorDetail(
                            error_type=ValidationErrorType.TYPE_MISMATCH,
                            parameter_name=param_name,
                            message=f"参数 '{param_name}' 类型不匹配，期望 {param_def.type}，实际 {TypeChecker.get_actual_type(value)}",
                            expected=param_def.type,
                            actual=TypeChecker.get_actual_type(value),
                        )
                    )
                    continue

                # 检查枚举值
                if param_def.enum is not None and value is not None:
                    # 将值转换为字符串进行比较
                    str_value = str(value) if not isinstance(value, str) else value
                    if str_value not in param_def.enum and value not in param_def.enum:
                        errors.append(
                            ValidationErrorDetail(
                                error_type=ValidationErrorType.INVALID_ENUM,
                                parameter_name=param_name,
                                message=f"参数 '{param_name}' 的值 '{value}' 不在枚举列表中",
                                expected=param_def.enum,
                                actual=value,
                            )
                        )
                        continue

                # 添加到验证后的参数
                validated_params[param_name] = value

        # 3. 检查多余参数（严格模式）
        if self._strict_mode:
            extra_params = provided_param_names - defined_param_names
            for extra_name in sorted(extra_params):
                errors.append(
                    ValidationErrorDetail(
                        error_type=ValidationErrorType.EXTRA_PARAMETER,
                        parameter_name=extra_name,
                        message=f"未定义的参数: {extra_name}",
                    )
                )

        # 4. 填充默认值
        for param in tool.parameters:
            if param.name not in validated_params:
                if param.default is not None:
                    validated_params[param.name] = param.default

        # 返回结果
        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            validated_params=validated_params if is_valid else {},
        )

    def validate_or_raise(self, tool: Tool, params: dict[str, Any]) -> dict[str, Any]:
        """验证参数，失败时抛出异常

        参数：
            tool: 工具定义
            params: 调用参数

        返回：
            验证后的参数（包含默认值）

        抛出：
            ToolValidationError: 验证失败时
        """
        result = self.validate(tool, params)
        if not result.is_valid:
            raise ToolValidationError(tool_name=tool.name, errors=result.errors)
        return result.validated_params

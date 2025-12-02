"""执行结果标准化模块 - Phase 11

定义结构化执行结果、错误码、重试策略和输出校验器。

业务场景：
- 节点执行返回结构化结果（成功/错误码/可重试）
- 根据规则判断失败（超过重试次数、输出校验不合格）
- 支持自动重试可重试的错误
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """错误码枚举

    定义所有可能的执行错误类型。
    """

    SUCCESS = "SUCCESS"
    TIMEOUT = "E_TIMEOUT"
    VALIDATION_FAILED = "E_VALIDATION"
    NETWORK_ERROR = "E_NETWORK"
    RESOURCE_LIMIT = "E_RESOURCE"
    INTERNAL_ERROR = "E_INTERNAL"
    DEPENDENCY_FAILED = "E_DEPENDENCY"

    def is_retryable(self) -> bool:
        """判断错误是否可重试"""
        retryable_codes = {
            ErrorCode.TIMEOUT,
            ErrorCode.NETWORK_ERROR,
            ErrorCode.RESOURCE_LIMIT,
        }
        return self in retryable_codes


# 异常类型到错误码的映射
EXCEPTION_TO_ERROR_CODE: dict[type, ErrorCode] = {
    TimeoutError: ErrorCode.TIMEOUT,
    ConnectionError: ErrorCode.NETWORK_ERROR,
    MemoryError: ErrorCode.RESOURCE_LIMIT,
    ValueError: ErrorCode.VALIDATION_FAILED,
    TypeError: ErrorCode.VALIDATION_FAILED,
}


class ExecutionResult:
    """结构化执行结果

    属性：
        success: 是否成功
        error_code: 错误码
        error_message: 错误消息
        retryable: 是否可重试
        output: 输出数据
        metadata: 执行元数据（时间、重试次数等）
    """

    __slots__ = (
        "_success",
        "error_code",
        "error_message",
        "retryable",
        "output",
        "metadata",
    )

    def __init__(
        self,
        success: bool = False,
        error_code: ErrorCode = ErrorCode.SUCCESS,
        error_message: str | None = None,
        retryable: bool = False,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self._success = success
        self.error_code = error_code
        self.error_message = error_message
        self.retryable = retryable
        self.output = output or {}
        self.metadata = metadata or {}

    @property
    def success(self) -> bool:
        """是否成功"""
        return self._success

    @success.setter
    def success(self, value: bool) -> None:
        self._success = value

    @classmethod
    def ok(
        cls,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionResult":
        """创建成功结果"""
        return cls(
            success=True,
            error_code=ErrorCode.SUCCESS,
            error_message=None,
            retryable=False,
            output=output,
            metadata=metadata,
        )

    @classmethod
    def failure(
        cls,
        error_code: ErrorCode,
        error_message: str,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionResult":
        """创建失败结果"""
        return cls(
            success=False,
            error_code=error_code,
            error_message=error_message,
            retryable=error_code.is_retryable(),
            output=output,
            metadata=metadata,
        )

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionResult":
        """从异常创建失败结果"""
        error_code = EXCEPTION_TO_ERROR_CODE.get(type(exception), ErrorCode.INTERNAL_ERROR)
        return cls.failure(
            error_code=error_code,
            error_message=str(exception),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "success": self.success,
            "error_code": self.error_code.value,
            "error_message": self.error_message,
            "retryable": self.retryable,
            "output": self.output,
            "metadata": self.metadata,
        }


@dataclass
class RetryPolicy:
    """重试策略

    属性：
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_backoff: 是否使用指数退避
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True

    def get_delay(self, attempt: int) -> float:
        """计算第 N 次重试的延迟

        参数：
            attempt: 重试次数（从 0 开始）

        返回：
            延迟秒数
        """
        if self.exponential_backoff:
            delay = self.base_delay * (2**attempt)
        else:
            delay = self.base_delay

        return min(delay, self.max_delay)

    def should_retry(self, error_code: ErrorCode, attempt: int) -> bool:
        """判断是否应该重试

        参数：
            error_code: 错误码
            attempt: 当前重试次数（从 0 开始）

        返回：
            是否应该重试
        """
        if attempt >= self.max_retries:
            return False
        return error_code.is_retryable()


@dataclass
class ValidationResult:
    """校验结果"""

    is_valid: bool
    error_message: str | None = None
    failed_field: str | None = None


@dataclass
class OutputValidator:
    """输出校验器

    属性：
        schema: 字段 schema 定义
        constraints: 自定义约束函数列表
    """

    schema: dict[str, dict[str, Any]] = field(default_factory=dict)
    constraints: list[Callable[[dict[str, Any]], bool]] = field(default_factory=list)

    # 类型映射
    TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    def validate(self, output: dict[str, Any]) -> ValidationResult:
        """校验输出

        参数：
            output: 输出数据

        返回：
            校验结果
        """
        # 校验 schema
        for field_name, field_schema in self.schema.items():
            # 检查必填字段
            if field_schema.get("required", False) and field_name not in output:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Required field '{field_name}' is missing",
                    failed_field=field_name,
                )

            # 检查类型
            if field_name in output:
                expected_type = field_schema.get("type")
                if expected_type:
                    python_type = self.TYPE_MAP.get(expected_type)
                    if python_type and not isinstance(output[field_name], python_type):
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Field '{field_name}' has wrong type, " f"expected {expected_type}"
                            ),
                            failed_field=field_name,
                        )

        # 校验自定义约束
        for constraint in self.constraints:
            if not constraint(output):
                return ValidationResult(
                    is_valid=False,
                    error_message="Custom constraint validation failed",
                    failed_field=None,
                )

        return ValidationResult(is_valid=True)


@dataclass
class WorkflowExecutionResult:
    """工作流执行结果"""

    success: bool
    node_results: dict[str, ExecutionResult] = field(default_factory=dict)
    failed_node_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# 导出
__all__ = [
    "ErrorCode",
    "ExecutionResult",
    "RetryPolicy",
    "ValidationResult",
    "OutputValidator",
    "WorkflowExecutionResult",
]

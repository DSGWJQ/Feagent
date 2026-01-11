"""领域层异常定义

为什么需要领域异常？
1. 业务语义清晰：DomainError 表示业务规则违反，不是技术错误
2. 异常分层：Domain 异常 vs Infrastructure 异常 vs API 异常
3. 统一处理：上层可以统一捕获 DomainError 并转换为 4xx 错误

设计原则：
- 继承自 Exception（Python 标准异常基类）
- 简单明了（不过度设计）
- 可扩展（未来可以添加错误码、详情等）
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """领域层异常基类

    用途：
    - 表示业务规则违反（如：start 不能为空）
    - 表示领域不变式违反（如：状态流转非法）

    为什么继承 Exception？
    - Python 标准做法
    - 可以被 try-except 捕获
    - 可以携带错误消息

    示例：
        if not start:
            raise DomainError("start 不能为空")

    未来扩展：
    - 可以添加 error_code 属性
    - 可以添加 details 字典
    - 可以添加子类（如 ValidationError、StateError）
    """

    pass


class DomainValidationError(DomainError):
    """结构化的领域校验错误（前端友好）"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "validation_error",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.errors = errors or []
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "errors": self.errors,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return self.message


class NotFoundError(DomainError):
    """实体不存在异常

    用途：
    - 表示查询的实体不存在（如：Agent 不存在、Run 不存在）
    - 用于 Repository 的 get_by_id() 方法

    为什么需要单独的异常类？
    - 语义清晰：区分"实体不存在"和"业务规则违反"
    - 便于统一处理：API 层可以统一捕获并返回 404
    - 符合 HTTP 语义：404 Not Found

    示例：
        agent = await repository.get_by_id(agent_id)
        # 如果不存在，抛出 NotFoundError

    参数：
        entity_type: 实体类型（如："Agent"、"Run"）
        entity_id: 实体 ID
    """

    def __init__(self, entity_type: str, entity_id: str | None = None):
        self.entity_type = entity_type
        self.entity_id = entity_id
        detail = f"{entity_type} 不存在"
        if entity_id is not None:
            detail = f"{detail}: {entity_id}"
        super().__init__(detail)


# EntityNotFoundError是NotFoundError的别名，用于Repository层
EntityNotFoundError = NotFoundError


class RunGateError(DomainError):
    """Run 执行门禁失败（语义上对应 HTTP 409 冲突）。"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "run_gate_rejected",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


class _ToolErrorBase(DomainError):
    """Structured tool-related execution errors (SSE contract friendly)."""

    def __init__(
        self,
        message: str,
        *,
        tool_id: str,
        error_type: str,
        error_level: str,
        retryable: bool,
        hint: str,
    ) -> None:
        self.tool_id = tool_id
        self.error_type = error_type
        self.error_level = error_level
        self.retryable = retryable
        self.hint = hint
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_level": self.error_level,
            "error_type": self.error_type,
            "retryable": self.retryable,
            "hint": self.hint,
            "message": self.message,
        }

    def __str__(self) -> str:  # pragma: no cover
        return self.message


class ToolNotFoundError(_ToolErrorBase):
    def __init__(self, tool_id: str):
        super().__init__(
            f"Tool not found: {tool_id}",
            tool_id=tool_id,
            error_type="tool_not_found",
            error_level="user_action_required",
            retryable=False,
            hint=f"未找到工具: {tool_id}（请检查 tool_id 或重新选择工具）",
        )


class ToolDeprecatedError(_ToolErrorBase):
    def __init__(self, tool_id: str):
        super().__init__(
            f"Tool is deprecated: {tool_id}",
            tool_id=tool_id,
            error_type="tool_deprecated",
            error_level="user_action_required",
            retryable=False,
            hint=f"工具已废弃: {tool_id}（请替换为未废弃的工具版本）",
        )


class ToolExecutionError(_ToolErrorBase):
    def __init__(
        self,
        tool_id: str,
        error_type: str = "execution_error",
        error_message: str = "Tool execution failed",
    ):
        normalized_type = (error_type or "execution_error").strip() or "execution_error"
        retryable = normalized_type in {"timeout", "execution_error"}
        level = "retryable" if retryable else "system_error"
        hint = (
            f"工具执行超时: {tool_id}"
            if normalized_type == "timeout"
            else f"工具执行失败: {tool_id}"
        )
        super().__init__(
            error_message,
            tool_id=tool_id,
            error_type=normalized_type,
            error_level=level,
            retryable=retryable,
            hint=hint,
        )

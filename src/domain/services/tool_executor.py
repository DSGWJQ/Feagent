"""ToolExecutor - 工具执行器 - 阶段 4

业务定义：
- ToolExecutionContext: 工具执行上下文
- ToolExecutionResult: 工具执行结果
- ToolExecutor: 工具执行器协议
- ToolSubAgent: 工具子 Agent
- KnowledgeRecorder: 知识库记录器协议

设计原则：
- 统一的执行接口
- 上下文隔离
- 结果可追溯
- 支持知识库记录
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from src.domain.entities.tool import Tool
    from src.domain.value_objects.execution_context import ExecutionContext

logger = logging.getLogger(__name__)


# =============================================================================
# 执行上下文
# =============================================================================


@dataclass
class ToolExecutionContext:
    """工具执行上下文

    提供工具执行所需的上下文信息：
    - 调用者信息（Agent ID、会话 ID、工作流 ID）
    - 执行配置（超时、重试）
    - 共享变量
    """

    # 调用者信息
    caller_id: str | None = None
    caller_type: str = "unknown"  # conversation_agent, workflow_node, direct
    conversation_id: str | None = None
    workflow_id: str | None = None

    # 执行配置
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3

    # 共享变量
    variables: dict[str, Any] = field(default_factory=dict)

    # 元数据
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    trace_id: str | None = None

    @classmethod
    def for_conversation(
        cls,
        agent_id: str,
        conversation_id: str,
        user_message: str | None = None,
        **kwargs: Any,
    ) -> ToolExecutionContext:
        """为对话 Agent 创建上下文

        参数：
            agent_id: Agent ID
            conversation_id: 会话 ID
            user_message: 用户消息
            **kwargs: 其他参数

        返回：
            ToolExecutionContext 实例
        """
        variables = kwargs.pop("variables", {})
        if user_message:
            variables["user_message"] = user_message

        return cls(
            caller_id=agent_id,
            caller_type="conversation_agent",
            conversation_id=conversation_id,
            variables=variables,
            **kwargs,
        )

    @classmethod
    def for_workflow(
        cls,
        workflow_id: str,
        node_id: str,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ToolExecutionContext:
        """为工作流节点创建上下文

        参数：
            workflow_id: 工作流 ID
            node_id: 节点 ID
            inputs: 节点输入
            **kwargs: 其他参数

        返回：
            ToolExecutionContext 实例
        """
        variables = kwargs.pop("variables", {})
        variables["node_id"] = node_id
        if inputs:
            variables["inputs"] = inputs

        return cls(
            caller_type="workflow_node",
            workflow_id=workflow_id,
            variables=variables,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "caller_id": self.caller_id,
            "caller_type": self.caller_type,
            "conversation_id": self.conversation_id,
            "workflow_id": self.workflow_id,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "variables": self.variables,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "trace_id": self.trace_id,
        }


# =============================================================================
# 执行结果
# =============================================================================


@dataclass
class ToolExecutionResult:
    """工具执行结果

    包含执行的所有信息：
    - 成功/失败状态
    - 输出数据
    - 错误信息
    - 执行元数据
    """

    # 基本状态
    is_success: bool
    tool_name: str
    output: dict[str, Any] = field(default_factory=dict)

    # 错误信息
    error: str | None = None
    error_type: str | None = None  # validation_error, execution_error, timeout, tool_not_found
    validation_errors: list[dict[str, Any]] = field(default_factory=list)

    # 执行元数据
    execution_time: float = 0.0
    executed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        tool_name: str,
        output: dict[str, Any] | Any,
        execution_time: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """创建成功结果

        参数：
            tool_name: 工具名称
            output: 输出数据
            execution_time: 执行时间
            metadata: 元数据

        返回：
            ToolExecutionResult 实例
        """
        # 确保 output 是字典
        if not isinstance(output, dict):
            output = {"result": output}

        return cls(
            is_success=True,
            tool_name=tool_name,
            output=output,
            execution_time=execution_time,
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        tool_name: str,
        error: str,
        error_type: str = "execution_error",
        execution_time: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """创建失败结果

        参数：
            tool_name: 工具名称
            error: 错误信息
            error_type: 错误类型
            execution_time: 执行时间
            metadata: 元数据

        返回：
            ToolExecutionResult 实例
        """
        return cls(
            is_success=False,
            tool_name=tool_name,
            error=error,
            error_type=error_type,
            execution_time=execution_time,
            metadata=metadata or {},
        )

    @classmethod
    def validation_failure(
        cls,
        tool_name: str,
        validation_errors: list[dict[str, Any]],
    ) -> ToolExecutionResult:
        """创建验证失败结果

        参数：
            tool_name: 工具名称
            validation_errors: 验证错误列表

        返回：
            ToolExecutionResult 实例
        """
        error_msg = "; ".join(
            f"{e.get('parameter', 'unknown')}: {e.get('error', 'unknown error')}"
            for e in validation_errors
        )
        return cls(
            is_success=False,
            tool_name=tool_name,
            error=f"参数验证失败: {error_msg}",
            error_type="validation_error",
            validation_errors=validation_errors,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "is_success": self.is_success,
            "tool_name": self.tool_name,
            "output": self.output,
            "error": self.error,
            "error_type": self.error_type,
            "validation_errors": self.validation_errors,
            "execution_time": self.execution_time,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "metadata": self.metadata,
        }


# =============================================================================
# 执行器协议
# =============================================================================


class ToolExecutor(Protocol):
    """工具执行器协议

    定义工具执行器必须实现的方法。
    每种工具类型（builtin, external, custom）有对应的执行器实现。
    """

    async def execute(
        self,
        tool: Tool,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """执行工具

        参数：
            tool: 工具定义
            params: 调用参数（已验证）
            context: 执行上下文

        返回：
            执行结果字典

        异常：
            任何异常都会被 ToolEngine 捕获并转换为失败结果
        """
        ...


# =============================================================================
# 知识库记录器协议
# =============================================================================


class KnowledgeRecorder(Protocol):
    """知识库记录器协议

    用于将工具执行结果记录到知识库。
    """

    async def record(self, data: dict[str, Any]) -> None:
        """记录数据到知识库

        参数：
            data: 要记录的数据
        """
        ...


# =============================================================================
# 工具子 Agent
# =============================================================================


class ToolSubAgent:
    """工具子 Agent

    在隔离环境中执行工具调用：
    - 从 ToolEngine 获取工具并执行
    - 维护自己的执行上下文
    - 向父 Agent 报告结果
    - 支持结果回调
    """

    def __init__(
        self,
        agent_id: str,
        tool_engine: Any,  # ToolEngine 类型，避免循环导入
        parent_agent_id: str | None = None,
        parent_context: ExecutionContext | None = None,
        on_result_callback: Callable[[ToolExecutionResult], None] | None = None,
    ):
        """初始化工具子 Agent

        参数：
            agent_id: 子 Agent ID
            tool_engine: ToolEngine 实例
            parent_agent_id: 父 Agent ID
            parent_context: 父执行上下文
            on_result_callback: 结果回调函数
        """
        self._agent_id = agent_id
        self._tool_engine = tool_engine
        self._parent_agent_id = parent_agent_id
        self._parent_context = parent_context
        self._on_result_callback = on_result_callback
        self._execution_history: list[ToolExecutionResult] = []

    @property
    def agent_id(self) -> str:
        """获取 Agent ID"""
        return self._agent_id

    @property
    def parent_agent_id(self) -> str | None:
        """获取父 Agent ID"""
        return self._parent_agent_id

    @property
    def execution_history(self) -> list[ToolExecutionResult]:
        """获取执行历史"""
        return self._execution_history.copy()

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolExecutionResult:
        """执行工具

        参数：
            tool_name: 工具名称
            params: 调用参数
            timeout: 超时时间（可选）

        返回：
            ToolExecutionResult 执行结果
        """
        # 创建执行上下文
        context = ToolExecutionContext(
            caller_id=self._agent_id,
            caller_type="tool_sub_agent",
            timeout=timeout or 30.0,
        )

        # 如果有父上下文，复制部分变量
        if self._parent_context:
            context.variables["parent_agent_id"] = self._parent_agent_id
            # 可以从父上下文复制需要的变量

        # 执行工具
        logger.debug(f"ToolSubAgent {self._agent_id} executing {tool_name}")
        result = await self._tool_engine.execute(
            tool_name=tool_name,
            params=params,
            context=context,
        )

        # 记录历史
        self._execution_history.append(result)

        # 回调通知
        if self._on_result_callback:
            try:
                self._on_result_callback(result)
            except Exception as e:
                logger.error(f"Result callback error: {e}")

        return result

    async def execute_batch(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
    ) -> list[ToolExecutionResult]:
        """批量执行工具

        参数：
            tool_calls: 工具调用列表 [(tool_name, params), ...]

        返回：
            执行结果列表
        """
        results = []
        for tool_name, params in tool_calls:
            result = await self.execute(tool_name, params)
            results.append(result)
        return results

    def get_execution_summary(self) -> dict[str, Any]:
        """获取执行摘要

        返回包含工具调用统计的摘要信息，
        可用于传递给 WorkflowAgent 或前端。

        返回：
            摘要字典
        """
        history = self._execution_history
        total_calls = len(history)
        successful_calls = sum(1 for r in history if r.is_success)
        failed_calls = total_calls - successful_calls
        total_time = sum(r.execution_time for r in history)

        # 统计工具使用
        tool_usage: dict[str, int] = {}
        for r in history:
            tool_usage[r.tool_name] = tool_usage.get(r.tool_name, 0) + 1

        # 收集错误信息
        errors = [
            {
                "tool_name": r.tool_name,
                "error": r.error,
                "error_type": r.error_type,
            }
            for r in history
            if not r.is_success
        ]

        return {
            "agent_id": self._agent_id,
            "parent_agent_id": self._parent_agent_id,
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate": round(successful_calls / total_calls * 100, 2)
            if total_calls > 0
            else 0.0,
            "total_execution_time": round(total_time, 4),
            "avg_execution_time": round(total_time / total_calls, 4) if total_calls > 0 else 0.0,
            "tool_usage": tool_usage,
            "errors": errors,
            "call_details": [
                {
                    "tool_name": r.tool_name,
                    "is_success": r.is_success,
                    "execution_time": r.execution_time,
                    "error": r.error if not r.is_success else None,
                }
                for r in history
            ],
        }

    def get_brief_summary(self) -> dict[str, Any]:
        """获取简要摘要（给前端用）

        返回：
            简要摘要字典
        """
        history = self._execution_history
        total_calls = len(history)
        successful_calls = sum(1 for r in history if r.is_success)
        total_time = sum(r.execution_time for r in history)

        # 统计工具使用
        tool_usage: dict[str, int] = {}
        for r in history:
            tool_usage[r.tool_name] = tool_usage.get(r.tool_name, 0) + 1

        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": total_calls - successful_calls,
            "success_rate": round(successful_calls / total_calls * 100, 2)
            if total_calls > 0
            else 0.0,
            "total_execution_time": round(total_time, 4),
            "tool_usage": tool_usage,
            "has_errors": any(not r.is_success for r in history),
        }

    def clear_history(self) -> None:
        """清空执行历史"""
        self._execution_history.clear()


# =============================================================================
# 内置执行器
# =============================================================================


class EchoExecutor:
    """回显执行器（用于测试）"""

    async def execute(
        self,
        tool: Tool,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """回显输入参数"""
        return {"echoed": params.get("message", "")}


class NoOpExecutor:
    """空操作执行器"""

    async def execute(
        self,
        tool: Tool,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """不执行任何操作，返回空结果"""
        return {"status": "no_op"}


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "ToolExecutionContext",
    "ToolExecutionResult",
    "ToolExecutor",
    "KnowledgeRecorder",
    "ToolSubAgent",
    "EchoExecutor",
    "NoOpExecutor",
]

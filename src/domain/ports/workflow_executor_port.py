"""Workflow Executor Port

定义工作流执行器的端口协议（Protocol/TypeAlias），供调度器等领域服务注入使用。

约束：
- 为兼容历史执行器，允许实现 `execute()` 或 `execute_workflow()` 任一方法。
"""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias


class WorkflowExecutorExecutePort(Protocol):
    def execute(self, workflow_id: str, input_data: dict[str, Any]) -> Any: ...


class WorkflowExecutorExecuteWorkflowPort(Protocol):
    def execute_workflow(self, workflow_id: str, input_data: dict[str, Any]) -> Any: ...


WorkflowExecutorPort: TypeAlias = WorkflowExecutorExecutePort | WorkflowExecutorExecuteWorkflowPort

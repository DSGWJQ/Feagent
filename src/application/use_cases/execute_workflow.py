"""ExecuteWorkflowUseCase - 执行工作流

业务场景：
- 用户触发工作流执行
- 按拓扑顺序执行节点
- 支持流式返回（SSE）实时推送执行状态

设计原则：
- 单一职责：只负责业务编排，不包含执行逻辑
- 依赖倒置：依赖 Repository 接口，不依赖具体实现
- 输入输出明确：使用 Input/Output 对象
"""

import asyncio
import contextlib
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.domain.events.workflow_execution_events import (
    NodeExecutionEvent,
    WorkflowExecutionCompletedEvent,
)
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_executor import WorkflowExecutor

WORKFLOW_EXECUTION_KERNEL_ID = "workflow_engine_v1"


@dataclass
class ExecuteWorkflowInput:
    """ExecuteWorkflow 输入参数

    为什么需要 Input 对象？
    1. 类型安全：明确输入参数类型
    2. 验证集中：可以在 Input 对象中验证参数
    3. 可测试性：测试时容易构造输入
    4. 文档化：清晰表达 Use Case 需要什么输入

    属性说明：
    - workflow_id: 工作流 ID
    - initial_input: 初始输入（传递给 Start 节点）
    """

    workflow_id: str
    initial_input: Any = None


class ExecuteWorkflowUseCase:
    """ExecuteWorkflow Use Case

    职责：
    1. 获取工作流
    2. 调用 WorkflowExecutor 执行工作流
    3. 返回执行结果（支持流式返回）

    为什么不在这里实现执行逻辑？
    - 执行逻辑在 Domain 层（WorkflowExecutor 服务）
    - Use Case 只负责编排（获取 → 执行 → 返回）
    - 符合单一职责原则

    依赖：
    - WorkflowRepository: 工作流仓储接口
    - NodeExecutorRegistry: 节点执行器注册表
    """

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        executor_registry: NodeExecutorRegistry | None = None,
        *,
        event_bus: EventBus | None = None,
    ):
        """初始化 Use Case

        参数：
            workflow_repository: 工作流仓储接口
            executor_registry: 节点执行器注册表

        为什么通过构造函数注入依赖？
        - 依赖倒置：Use Case 依赖接口，不依赖具体实现
        - 可测试性：测试时可以注入 Mock Repository
        - 灵活性：可以轻松切换不同的 Repository 实现
        """
        self.workflow_repository = workflow_repository
        self.executor_registry = executor_registry
        self._event_bus = event_bus

    def _default_correlation_id(self, workflow_id: str) -> str:
        return f"workflow_execute:{workflow_id}:{uuid4().hex[:12]}"

    def _to_sse_node_event(
        self, *, event: NodeExecutionEvent, correlation_id: str
    ) -> dict[str, Any] | None:
        if event.correlation_id != correlation_id:
            return None

        status = (event.status or "").strip().lower()
        if status not in {"running", "completed", "failed", "skipped"}:
            return None

        base: dict[str, Any] = {
            "executor_id": WORKFLOW_EXECUTION_KERNEL_ID,
            "node_id": event.node_id,
            "node_type": event.node_type,
        }

        if status == "running":
            payload = {"type": "node_start", **base}
            if event.inputs is not None:
                payload["inputs"] = event.inputs
            return payload

        if status == "completed":
            return {"type": "node_complete", **base, "output": event.result}

        if status == "failed":
            payload: dict[str, Any] = {"type": "node_error", **base, "error": event.error or ""}
            error_type = event.metadata.get("error_type")
            if isinstance(error_type, str) and error_type.strip():
                payload["error_type"] = error_type
            return payload

        # skipped
        payload = {"type": "node_skipped", **base, "reason": event.reason or ""}
        incoming = event.metadata.get("incoming_edge_conditions")
        if incoming is not None:
            payload["incoming_edge_conditions"] = incoming
        return payload

    def _to_sse_terminal_event(
        self, *, event: WorkflowExecutionCompletedEvent, correlation_id: str
    ) -> dict[str, Any] | None:
        if event.correlation_id != correlation_id:
            return None

        status = (event.status or "").strip().lower()
        if status == "completed":
            return {
                "type": "workflow_complete",
                "executor_id": WORKFLOW_EXECUTION_KERNEL_ID,
                "result": event.final_result,
                "execution_log": list(event.execution_log or []),
                "execution_summary": dict(event.execution_summary or {}),
            }

        if status == "failed":
            error = event.error
            if not error and isinstance(event.result, dict):
                candidate = event.result.get("error")
                if isinstance(candidate, str):
                    error = candidate
            return {
                "type": "workflow_error",
                "executor_id": WORKFLOW_EXECUTION_KERNEL_ID,
                "error": error or "workflow_failed",
            }

        return None

    async def execute(
        self, input_data: ExecuteWorkflowInput, *, correlation_id: str | None = None
    ) -> dict[str, Any]:
        """执行工作流（非流式）

        业务流程：
        1. 获取工作流（不存在抛出 NotFoundError）
        2. 创建 WorkflowExecutor
        3. 设置事件回调（同步 streaming() 行为）
        4. 执行工作流
        5. 返回执行结果及收集的事件

        参数：
            input_data: 输入参数

        返回：
            执行结果字典：
            - execution_log: 执行日志（每个节点的执行记录）
            - final_result: 最终结果（End 节点的输出）
            - events: 执行过程中收集的事件列表

        异常：
            NotFoundError: 工作流不存在
            DomainError: 工作流执行失败（例如包含环）
        """
        workflow = self.workflow_repository.get_by_id(input_data.workflow_id)
        if not workflow:
            raise NotFoundError(entity_type="Workflow", entity_id=input_data.workflow_id)

        event_bus = self._event_bus or EventBus()
        correlation_id = correlation_id or self._default_correlation_id(workflow.id)

        events: list[dict[str, Any]] = []

        async def _on_node_event(raw_event: Any) -> None:
            if not isinstance(raw_event, NodeExecutionEvent):
                return
            mapped = self._to_sse_node_event(event=raw_event, correlation_id=correlation_id)
            if mapped is None:
                return
            events.append(mapped)

        event_bus.subscribe(NodeExecutionEvent, _on_node_event)

        executor = WorkflowExecutor(executor_registry=self.executor_registry, event_bus=event_bus)

        started_at = time.perf_counter()
        try:
            final_result = await executor.execute(
                workflow, input_data.initial_input, correlation_id=correlation_id
            )
        finally:
            event_bus.unsubscribe(NodeExecutionEvent, _on_node_event)

        duration_ms = int((time.perf_counter() - started_at) * 1000)

        # 6. 返回结果
        return {
            "execution_log": executor.execution_log,
            "final_result": final_result,
            "events": events,
            "executor_id": WORKFLOW_EXECUTION_KERNEL_ID,
            "execution_summary": {
                "total_nodes": len(executor.execution_log),
                "success_nodes": len(executor.execution_log),
                "failed_nodes": 0,
                "duration_ms": duration_ms,
            },
        }

    async def execute_streaming(
        self, input_data: ExecuteWorkflowInput, *, correlation_id: str | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """执行工作流（流式返回）

        业务流程：
        1. 获取工作流
        2. 创建 WorkflowExecutor
        3. 设置事件回调
        4. 执行工作流，通过回调生成事件
        5. 生成最终完成事件

        参数：
            input_data: 输入参数

        生成：
            事件字典（SSE 格式）：
            - node_start: 节点开始执行
            - node_complete: 节点执行完成
            - node_error: 节点执行失败
            - workflow_complete: 工作流执行完成
            - workflow_error: 工作流执行失败

        异常：
            NotFoundError: 工作流不存在
        """
        workflow = self.workflow_repository.get_by_id(input_data.workflow_id)
        if not workflow:
            raise NotFoundError(entity_type="Workflow", entity_id=input_data.workflow_id)

        event_bus = self._event_bus or EventBus()
        correlation_id = correlation_id or self._default_correlation_id(workflow.id)

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        done = asyncio.Event()
        started_at = time.perf_counter()

        async def _on_node_event(raw_event: Any) -> None:
            if not isinstance(raw_event, NodeExecutionEvent):
                return
            mapped = self._to_sse_node_event(event=raw_event, correlation_id=correlation_id)
            if mapped is None:
                return
            try:
                queue.put_nowait(mapped)
            except asyncio.QueueFull:
                # KISS: drop on overflow (same as legacy callback path).
                return

        event_bus.subscribe(NodeExecutionEvent, _on_node_event)

        executor = WorkflowExecutor(executor_registry=self.executor_registry, event_bus=event_bus)

        async def _run_workflow() -> None:
            try:
                final_result = await executor.execute(
                    workflow, input_data.initial_input, correlation_id=correlation_id
                )
                duration_ms = int((time.perf_counter() - started_at) * 1000)

                terminal_event = WorkflowExecutionCompletedEvent(
                    source="execute_workflow",
                    correlation_id=correlation_id,
                    workflow_id=workflow.id,
                    status="completed",
                    success=True,
                    final_result=final_result,
                    execution_log=executor.execution_log,
                    execution_summary={
                        "total_nodes": len(executor.execution_log),
                        "success_nodes": len(executor.execution_log),
                        "failed_nodes": 0,
                        "duration_ms": duration_ms,
                    },
                )
            except DomainError as exc:
                terminal_event = WorkflowExecutionCompletedEvent(
                    source="execute_workflow",
                    correlation_id=correlation_id,
                    workflow_id=workflow.id,
                    status="failed",
                    success=False,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            except Exception as exc:  # noqa: BLE001 - use case boundary
                terminal_event = WorkflowExecutionCompletedEvent(
                    source="execute_workflow",
                    correlation_id=correlation_id,
                    workflow_id=workflow.id,
                    status="failed",
                    success=False,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

            # Publish to EventBus for monitors (best-effort).
            try:
                await event_bus.publish(terminal_event)
            except Exception:
                pass

            mapped_terminal = self._to_sse_terminal_event(
                event=terminal_event, correlation_id=correlation_id
            )
            if mapped_terminal is not None:
                try:
                    queue.put_nowait(mapped_terminal)
                except asyncio.QueueFull:
                    pass
            done.set()

        task = asyncio.create_task(_run_workflow())
        try:
            while True:
                if done.is_set() and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                except TimeoutError:
                    continue
                yield event
        finally:
            event_bus.unsubscribe(NodeExecutionEvent, _on_node_event)
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

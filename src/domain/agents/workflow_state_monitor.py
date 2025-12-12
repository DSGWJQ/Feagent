"""WorkflowStateMonitor - 工作流状态监控器

Phase 35.5: 从 CoordinatorAgent 提取工作流状态监听与管理功能。

职责：
1. 监听工作流事件（WorkflowExecutionStartedEvent, WorkflowExecutionCompletedEvent, NodeExecutionEvent）
2. 维护工作流状态字典（workflow_states）
3. 提供查询接口（get_workflow_state, get_all_workflow_states, get_system_status）
4. 清理策略（clear_old_states, clear_workflow_state）
5. 线程安全保护（threading.Lock）

关键修复：
- 订阅残留bug：_subscriptions 记录实际订阅的 handler
- 并发安全：移除 _current_workflow_id，强制从事件读取 workflow_id
- 深拷贝保护：查询方法返回 deepcopy
- 清理策略：按时间或手动清理旧状态
- 错误防御：缺失状态时防御性创建
- 线程安全：threading.Lock 保护所有状态更新
"""

import copy
import threading
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any


class WorkflowStateMonitor:
    """工作流状态监控器

    监听工作流执行事件，维护状态字典，提供查询和清理接口。

    使用示例：
        event_bus = EventBus()
        workflow_states = {}
        monitor = WorkflowStateMonitor(
            workflow_states=workflow_states,
            event_bus=event_bus,
        )
        monitor.start_monitoring()
    """

    def __init__(
        self,
        workflow_states: dict[str, dict[str, Any]],
        event_bus: Any,
        is_compressing_context: bool | Callable[[], bool] = False,
        compression_callback: Callable[[str, str, dict[str, Any]], Awaitable[None]] | None = None,
    ):
        """初始化工作流状态监控器

        参数：
            workflow_states: 共享的工作流状态字典（由调用方维护）
            event_bus: 事件总线
            is_compressing_context: 是否启用压缩（布尔值或 Callable）
            compression_callback: 可选的压缩回调函数
        """
        self.workflow_states = workflow_states
        self.event_bus = event_bus
        self._is_monitoring = False
        self._lock = threading.Lock()
        self._is_compressing_context = is_compressing_context
        self._compression_callback = compression_callback
        self._subscriptions: list[tuple[type, Callable]] = []

    def _compressing(self) -> bool:
        """检查是否启用压缩"""
        if callable(self._is_compressing_context):
            return self._is_compressing_context()
        return bool(self._is_compressing_context)

    # === 监听生命周期 ===

    def start_monitoring(self) -> None:
        """开始监听工作流事件

        订阅 WorkflowExecutionStartedEvent, WorkflowExecutionCompletedEvent, NodeExecutionEvent。
        根据压缩开关选择普通或压缩处理器。
        """
        if self._is_monitoring:
            return  # 幂等操作

        if not self.event_bus:
            raise ValueError("EventBus is required for monitoring")

        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
            WorkflowExecutionStartedEvent,
        )

        # 根据压缩开关选择处理器
        started_handler = (
            self._handle_workflow_started_with_compression
            if self._compressing()
            else self._handle_workflow_started
        )
        node_handler = (
            self._handle_node_execution_with_compression
            if self._compressing()
            else self._handle_node_execution
        )

        # 订阅事件并记录（修复订阅残留bug）
        subscriptions = [
            (WorkflowExecutionStartedEvent, started_handler),
            (WorkflowExecutionCompletedEvent, self._handle_workflow_completed),
            (NodeExecutionEvent, node_handler),
        ]

        for event_cls, handler in subscriptions:
            self.event_bus.subscribe(event_cls, handler)

        self._subscriptions = subscriptions
        self._is_monitoring = True

    def stop_monitoring(self) -> None:
        """停止监听工作流事件

        取消所有订阅（修复订阅残留bug）。
        """
        if not self._is_monitoring or not self.event_bus:
            return

        # 使用记录的订阅列表取消订阅
        for event_cls, handler in self._subscriptions:
            self.event_bus.unsubscribe(event_cls, handler)

        self._subscriptions.clear()
        self._is_monitoring = False

    # === 事件处理器 ===

    async def _handle_workflow_started(self, event: Any) -> None:
        """处理工作流启动事件

        创建初始状态快照（线程安全）。

        参数：
            event: WorkflowExecutionStartedEvent 实例
        """
        workflow_id = getattr(event, "workflow_id", None)
        if not workflow_id:
            return  # 忽略缺失 workflow_id 的事件（并发安全）

        with self._lock:
            self.workflow_states[workflow_id] = {
                "workflow_id": workflow_id,
                "status": "running",
                "node_count": getattr(event, "node_count", 0),
                "started_at": datetime.now(),
                "completed_at": None,
                "result": None,
                "executed_nodes": [],
                "running_nodes": [],
                "failed_nodes": [],
                "node_inputs": {},
                "node_outputs": {},
                "node_errors": {},
            }

    async def _handle_workflow_completed(self, event: Any) -> None:
        """处理工作流完成事件

        更新状态为 completed/failed（防御性编程 + 线程安全）。

        参数：
            event: WorkflowExecutionCompletedEvent 实例
        """
        workflow_id = getattr(event, "workflow_id", None)
        if not workflow_id:
            return

        status = getattr(event, "status", "completed")
        result = getattr(event, "result", None)

        with self._lock:
            state = self.workflow_states.get(workflow_id)

            # 错误防御：缺失状态时创建最小状态
            if not state:
                state = {
                    "workflow_id": workflow_id,
                    "status": status,
                    "node_count": getattr(event, "node_count", 0),
                    "started_at": getattr(event, "started_at", datetime.now()),
                    "executed_nodes": [],
                    "running_nodes": [],
                    "failed_nodes": [],
                    "node_inputs": {},
                    "node_outputs": {},
                    "node_errors": {},
                }
                self.workflow_states[workflow_id] = state

            state["status"] = status
            state["completed_at"] = datetime.now()
            state["result"] = result

    async def _handle_node_execution(self, event: Any) -> None:
        """处理节点执行事件

        更新节点运行状态、输入/输出/错误（线程安全）。

        参数：
            event: NodeExecutionEvent 实例
        """
        workflow_id = getattr(event, "workflow_id", None)
        if not workflow_id:
            return  # 忽略缺失 workflow_id 的事件

        node_id = getattr(event, "node_id", None)
        status = getattr(event, "status", None)

        if not node_id or not status:
            return

        with self._lock:
            state = self.workflow_states.get(workflow_id)
            if not state:
                return  # 状态不存在，忽略

            # 记录节点输入
            if getattr(event, "inputs", None):
                state["node_inputs"][node_id] = event.inputs

            # 更新节点状态
            if status == "running":
                if node_id not in state["running_nodes"]:
                    state["running_nodes"].append(node_id)

            elif status == "completed":
                if node_id in state["running_nodes"]:
                    state["running_nodes"].remove(node_id)
                if node_id not in state["executed_nodes"]:
                    state["executed_nodes"].append(node_id)
                if getattr(event, "result", None) is not None:
                    state["node_outputs"][node_id] = event.result

            elif status == "failed":
                if node_id in state["running_nodes"]:
                    state["running_nodes"].remove(node_id)
                if node_id not in state["failed_nodes"]:
                    state["failed_nodes"].append(node_id)
                if getattr(event, "error", None) is not None:
                    state["node_errors"][node_id] = event.error

    async def _handle_workflow_started_with_compression(self, event: Any) -> None:
        """处理工作流启动事件（带压缩）

        复用普通处理器，再调用压缩回调。
        """
        await self._handle_workflow_started(event)

        if self._compressing() and self._compression_callback:
            workflow_id = getattr(event, "workflow_id", None)
            if workflow_id:
                await self._compression_callback(
                    workflow_id,
                    "execution",
                    {
                        "workflow_status": "running",
                        "node_count": getattr(event, "node_count", 0),
                    },
                )

    async def _handle_node_execution_with_compression(self, event: Any) -> None:
        """处理节点执行事件（带压缩）

        复用普通处理器，再调用压缩回调。
        """
        await self._handle_node_execution(event)

        if self._compressing() and self._compression_callback:
            workflow_id = getattr(event, "workflow_id", None)
            if workflow_id:
                # 构建压缩数据
                payload = {
                    "executed_nodes": [
                        {
                            "node_id": getattr(event, "node_id", None),
                            "status": getattr(event, "status", None),
                            "output": getattr(event, "result", None),
                            "error": getattr(event, "error", None),
                        }
                    ],
                    "workflow_status": "running",
                }

                # 计算进度
                with self._lock:
                    state = self.workflow_states.get(workflow_id)
                    if state:
                        total = state.get("node_count", 0)
                        executed = len(state.get("executed_nodes", []))
                        if total > 0:
                            payload["progress"] = executed / total

                await self._compression_callback(workflow_id, "execution", payload)

    # === 查询接口 ===

    def get_workflow_state(self, workflow_id: str) -> dict[str, Any] | None:
        """获取工作流状态（深拷贝保护）

        参数：
            workflow_id: 工作流ID

        返回：
            工作流状态字典（深拷贝），如果不存在返回 None
        """
        with self._lock:
            state = self.workflow_states.get(workflow_id)
            return copy.deepcopy(state) if state else None

    def get_all_workflow_states(self) -> dict[str, dict[str, Any]]:
        """获取所有工作流状态（深拷贝保护）

        返回：
            所有工作流状态字典（深拷贝）
        """
        with self._lock:
            return {wf_id: copy.deepcopy(s) for wf_id, s in self.workflow_states.items()}

    def get_system_status(self) -> dict[str, Any]:
        """获取系统状态统计

        返回：
            包含统计信息的字典：
            - total_workflows: 总工作流数
            - running_workflows: 运行中工作流数
            - completed_workflows: 已完成工作流数
            - failed_workflows: 失败工作流数
            - active_nodes: 活跃节点数
        """
        with self._lock:
            total = len(self.workflow_states)
            running = sum(1 for s in self.workflow_states.values() if s.get("status") == "running")
            completed = sum(
                1 for s in self.workflow_states.values() if s.get("status") == "completed"
            )
            failed = sum(1 for s in self.workflow_states.values() if s.get("status") == "failed")
            active_nodes = sum(
                len(s.get("running_nodes", [])) for s in self.workflow_states.values()
            )

        return {
            "total_workflows": total,
            "running_workflows": running,
            "completed_workflows": completed,
            "failed_workflows": failed,
            "active_nodes": active_nodes,
        }

    # === 清理策略 ===

    def clear_old_states(self, max_age_seconds: int) -> int:
        """清理旧状态

        删除超过指定时间的工作流状态。

        参数：
            max_age_seconds: 最大年龄（秒）

        返回：
            删除的状态数量
        """
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        removed = 0

        with self._lock:
            for wf_id in list(self.workflow_states.keys()):
                started_at = self.workflow_states[wf_id].get("started_at")
                if isinstance(started_at, datetime) and started_at < cutoff:
                    self.workflow_states.pop(wf_id, None)
                    removed += 1

        return removed

    def clear_workflow_state(self, workflow_id: str) -> bool:
        """清理单个工作流状态

        参数：
            workflow_id: 工作流ID

        返回：
            是否成功删除
        """
        with self._lock:
            return self.workflow_states.pop(workflow_id, None) is not None


__all__ = ["WorkflowStateMonitor"]

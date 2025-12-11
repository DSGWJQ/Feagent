"""ContainerExecutionMonitor - 容器执行监控服务

职责:
- 订阅容器开始/完成/日志事件
- 记录工作流级别的容器执行信息与单容器日志
- 提供执行统计，兼容 status/success 两种结果格式
- 使用有界列表防止日志内存泄漏

设计要点:
- 从 CoordinatorAgent 提取的独立服务
- 事件类型懒加载避免循环依赖
- 方法签名与 CoordinatorAgent 完全一致（便于代理）
- 提供别名方法供独立使用

使用示例::

    monitor = ContainerExecutionMonitor(event_bus=bus)
    monitor.start_container_execution_listening()
    ...
    executions = monitor.get_workflow_container_executions("wf-1")
    stats = monitor.get_container_execution_statistics()
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class ContainerExecutionMonitor:
    """监听并记录容器执行事件的监控器

    属性:
        event_bus: 事件总线实例
        max_log_size: 单容器日志最大条目数（防止内存泄漏）
        container_executions: workflow_id -> 执行记录列表
        container_logs: container_id -> 日志列表
    """

    def __init__(self, event_bus: EventBus | None, max_log_size: int = 500) -> None:
        """初始化容器执行监控器

        参数:
            event_bus: 事件总线实例，可以为None（后续注入）
            max_log_size: 单容器日志最大条目数，默认500
        """
        self.event_bus = event_bus
        self.max_log_size = max_log_size

        # workflow_id -> executions list
        self.container_executions: dict[str, list[dict[str, Any]]] = {}

        # container_id -> logs list
        self.container_logs: dict[str, list[dict[str, Any]]] = {}

        # 监听状态标记
        self._is_listening_container_events = False

    # ==================== 公开接口：重置方法 ====================

    def reset_executions(self) -> None:
        """重置所有执行记录（用于测试或清理）"""
        self.container_executions.clear()

    def reset_logs(self) -> None:
        """重置所有日志（用于测试或清理）"""
        self.container_logs.clear()

    def reset_all(self) -> None:
        """重置所有数据（执行记录 + 日志）"""
        self.reset_executions()
        self.reset_logs()

    # ==================== 事件订阅/取消订阅（向后兼容） ====================

    def start_container_execution_listening(self) -> None:
        """启动容器执行事件监听

        订阅三种事件:
        - ContainerExecutionStartedEvent
        - ContainerExecutionCompletedEvent
        - ContainerLogEvent

        异常:
            ValueError: 如果 event_bus 为 None
        """
        if self._is_listening_container_events:
            return

        if not self.event_bus:
            raise ValueError("EventBus is required for container execution listening")

        # 懒加载事件类型以避免循环依赖
        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
            ContainerExecutionStartedEvent,
            ContainerLogEvent,
        )

        self.event_bus.subscribe(ContainerExecutionStartedEvent, self._handle_container_started)
        self.event_bus.subscribe(ContainerExecutionCompletedEvent, self._handle_container_completed)
        self.event_bus.subscribe(ContainerLogEvent, self._handle_container_log)

        self._is_listening_container_events = True

        logger.info("ContainerExecutionMonitor started listening to container events")

    def stop_container_execution_listening(self) -> None:
        """停止容器执行事件监听

        取消所有事件订阅，复位监听状态。
        """
        if not self._is_listening_container_events:
            return

        if not self.event_bus:
            return

        from src.domain.agents.container_events import (
            ContainerExecutionCompletedEvent,
            ContainerExecutionStartedEvent,
            ContainerLogEvent,
        )

        self.event_bus.unsubscribe(ContainerExecutionStartedEvent, self._handle_container_started)
        self.event_bus.unsubscribe(
            ContainerExecutionCompletedEvent, self._handle_container_completed
        )
        self.event_bus.unsubscribe(ContainerLogEvent, self._handle_container_log)

        self._is_listening_container_events = False

        logger.info("ContainerExecutionMonitor stopped listening to container events")

    # ==================== 事件处理器 ====================

    async def _handle_container_started(self, event: Any) -> None:
        """处理容器执行开始事件

        记录容器开始信息到工作流执行列表。

        参数:
            event: ContainerExecutionStartedEvent 实例
        """
        workflow_id = event.workflow_id

        if workflow_id not in self.container_executions:
            self.container_executions[workflow_id] = []

        self.container_executions[workflow_id].append(
            {
                "container_id": event.container_id,
                "node_id": event.node_id,
                "image": getattr(event, "image", None),
                "status": "running",
                "started_at": getattr(event, "timestamp", None),
            }
        )

    async def _handle_container_completed(self, event: Any) -> None:
        """处理容器执行完成事件

        记录容器完成/失败信息到工作流执行列表。

        参数:
            event: ContainerExecutionCompletedEvent 实例
        """
        workflow_id = event.workflow_id

        if workflow_id not in self.container_executions:
            self.container_executions[workflow_id] = []

        self.container_executions[workflow_id].append(
            {
                "container_id": event.container_id,
                "node_id": event.node_id,
                "success": event.success,
                "exit_code": getattr(event, "exit_code", None),
                "stdout": getattr(event, "stdout", None),
                "stderr": getattr(event, "stderr", None),
                "execution_time": getattr(event, "execution_time", 0.0),
                "status": "completed" if event.success else "failed",
                "completed_at": getattr(event, "timestamp", None),
            }
        )

    async def _handle_container_log(self, event: Any) -> None:
        """处理容器日志事件

        使用有界列表记录日志，防止内存泄漏。

        参数:
            event: ContainerLogEvent 实例
        """
        container_id = event.container_id

        if container_id not in self.container_logs:
            self.container_logs[container_id] = []

        # 使用有界列表添加日志
        self._add_to_bounded_list(
            self.container_logs[container_id],
            {
                "level": getattr(event, "log_level", None),
                "message": getattr(event, "message", None),
                "timestamp": getattr(event, "timestamp", None),
                "node_id": getattr(event, "node_id", None),
            },
            self.max_log_size,
        )

    # ==================== 查询方法（向后兼容） ====================

    def get_workflow_container_executions(self, workflow_id: str) -> list[dict[str, Any]]:
        """获取工作流的容器执行记录

        参数:
            workflow_id: 工作流ID

        返回:
            执行记录列表，如果不存在返回空列表
        """
        return self.container_executions.get(workflow_id, [])

    def get_container_logs(self, container_id: str) -> list[dict[str, Any]]:
        """获取容器日志

        参数:
            container_id: 容器ID

        返回:
            日志列表，如果不存在返回空列表
        """
        return self.container_logs.get(container_id, [])

    def get_container_execution_statistics(self) -> dict[str, Any]:
        """获取容器执行统计

        兼容两种数据格式:
        - status 字段（completed/failed）
        - success 字段（仅存在success字段）

        返回:
            统计字典，包含:
            - total_executions: 总执行次数
            - successful: 成功次数
            - failed: 失败次数
            - total_execution_time: 总执行时间
        """
        total = 0
        successful = 0
        failed = 0
        total_time = 0.0

        for _workflow_id, executions in self.container_executions.items():
            for execution in executions:
                # 兼容两种格式：status 字段 或 success 字段
                status = execution.get("status")
                has_result = status in {"completed", "failed"} or "success" in execution

                if has_result:
                    total += 1
                    # 优先使用 success 字段，如果不存在则从 status 推断
                    if "success" in execution:
                        is_success = execution["success"]
                    else:
                        is_success = status == "completed"

                    if is_success:
                        successful += 1
                    else:
                        failed += 1
                    total_time += execution.get("execution_time", 0.0)

        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "total_execution_time": total_time,
        }

    # ==================== 便捷别名（独立使用时更简短） ====================

    def start_listening(self) -> None:
        """别名: start_container_execution_listening"""
        self.start_container_execution_listening()

    def stop_listening(self) -> None:
        """别名: stop_container_execution_listening"""
        self.stop_container_execution_listening()

    async def handle_container_started(self, event: Any) -> None:
        """别名: _handle_container_started（供外部直接调用）"""
        await self._handle_container_started(event)

    async def handle_completed(self, event: Any) -> None:
        """别名: _handle_container_completed（供外部直接调用）"""
        await self._handle_container_completed(event)

    async def handle_log(self, event: Any) -> None:
        """别名: _handle_container_log（供外部直接调用）"""
        await self._handle_container_log(event)

    def get_workflow_executions(self, workflow_id: str) -> list[dict[str, Any]]:
        """别名: get_workflow_container_executions"""
        return self.get_workflow_container_executions(workflow_id)

    def get_statistics(self) -> dict[str, Any]:
        """别名: get_container_execution_statistics"""
        return self.get_container_execution_statistics()

    # ==================== 内部工具方法 ====================

    def _add_to_bounded_list(self, target_list: list[Any], item: Any, max_size: int) -> None:
        """添加项目到有界列表，超出限制时移除最旧项

        防止无限增长导致内存泄漏。

        参数:
            target_list: 目标列表
            item: 要添加的项目
            max_size: 最大大小限制
        """
        target_list.append(item)
        while len(target_list) > max_size:
            target_list.pop(0)  # 移除最旧的


__all__ = ["ContainerExecutionMonitor"]

"""ExecutionSummaryManager - 执行总结管理器

业务职责：
- 存储与查询执行总结
- 发布执行总结记录事件
- 提供统计信息
- 集成通道桥接器推送到前端

设计原则：
- 懒加载初始化存储
- 支持同步与异步操作
- 可选的 EventBus 与 ChannelBridge
- 返回副本保证数据不可变性

使用示例：
    manager = ExecutionSummaryManager(event_bus=event_bus)
    manager.set_channel_bridge(bridge)

    # 异步记录并推送
    await manager.record_and_push_summary(summary)

    # 查询
    summary = manager.get_execution_summary(workflow_id)
    stats = manager.get_summary_statistics()
"""

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionSummaryManager:
    """执行总结管理器

    负责执行总结的存储、查询、事件发布和前端推送。
    """

    def __init__(self, event_bus: Any | None = None):
        """初始化执行总结管理器

        参数：
            event_bus: 事件总线（可选）
        """
        self.event_bus = event_bus
        self._execution_summaries: dict[str, Any] = {}
        self._channel_bridge: Any | None = None

    def set_channel_bridge(self, bridge: Any) -> None:
        """设置通信桥接器

        参数：
            bridge: AgentChannelBridge 实例
        """
        self._channel_bridge = bridge

    def record_execution_summary(self, summary: Any) -> None:
        """同步记录执行总结

        参数：
            summary: ExecutionSummary 实例
        """
        workflow_id = getattr(summary, "workflow_id", "")
        if workflow_id:
            self._execution_summaries[workflow_id] = summary

    async def record_execution_summary_async(self, summary: Any) -> None:
        """异步记录执行总结并发布事件

        参数：
            summary: ExecutionSummary 实例
        """
        from src.domain.agents.execution_summary import ExecutionSummaryRecordedEvent

        workflow_id = getattr(summary, "workflow_id", "")
        session_id = getattr(summary, "session_id", "")
        # Fix: 确保 success 默认值与统计逻辑一致（默认 False）
        success = getattr(summary, "success", False)
        summary_id = getattr(summary, "summary_id", "")

        if workflow_id:
            self._execution_summaries[workflow_id] = summary

        # 发布事件
        if self.event_bus:
            event = ExecutionSummaryRecordedEvent(
                source="execution_summary_manager",
                workflow_id=workflow_id,
                session_id=session_id,
                success=success,
                summary_id=summary_id,
            )
            await self.event_bus.publish(event)

    def get_execution_summary(self, workflow_id: str) -> Any | None:
        """获取执行总结

        参数：
            workflow_id: 工作流ID

        返回：
            ExecutionSummary 实例的副本，如果不存在返回 None
        """
        summary = self._execution_summaries.get(workflow_id)
        # Fix: 返回副本保护内部状态
        return copy.copy(summary) if summary is not None else None

    def get_summary_statistics(self) -> dict[str, Any]:
        """获取总结统计

        返回：
            包含统计信息的字典：
            - total: 总数
            - successful: 成功数
            - failed: 失败数
        """
        total = len(self._execution_summaries)
        successful = sum(
            1 for s in self._execution_summaries.values() if getattr(s, "success", False)
        )
        failed = total - successful

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
        }

    async def record_and_push_summary(self, summary: Any) -> None:
        """记录总结并推送到前端

        参数：
            summary: ExecutionSummary 实例
        """
        # Fix: 确保事件发布失败不影响通道推送
        try:
            # 记录总结（异步，发布事件）
            await self.record_execution_summary_async(summary)
        except Exception as e:
            # 记录异常但不中断流程
            logger.warning(
                f"Failed to record execution summary for workflow {getattr(summary, 'workflow_id', 'unknown')}: {e}"
            )

        # 推送到前端（如果有桥接器且有 session_id）
        if self._channel_bridge:
            session_id = getattr(summary, "session_id", "")
            if session_id:
                try:
                    await self._channel_bridge.push_execution_summary(session_id, summary)
                except Exception as e:
                    logger.warning(
                        f"Failed to push execution summary to channel for session {session_id}: {e}"
                    )

    def get_all_summaries(self) -> dict[str, Any]:
        """获取所有总结

        返回：
            工作流ID到总结的映射（副本）
        """
        return self._execution_summaries.copy()

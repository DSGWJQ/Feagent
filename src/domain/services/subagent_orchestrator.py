"""SubAgentOrchestrator - 子Agent编排器

从 CoordinatorAgent 提取的子Agent管理能力，封装：
- 子Agent类型注册与实例化
- 事件订阅（SpawnSubAgentEvent）
- 子Agent执行生命周期
- 结果存储与状态查询

设计要点：
- 方法签名与 CoordinatorAgent 现有接口完全一致（向后兼容）
- 默认内部创建依赖，也支持依赖注入以便测试/替换实现
- 延迟导入避免循环依赖
- 日志格式与 CoordinatorAgent 保持一致
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class SubAgentOrchestrator:
    """子Agent编排器

    管理子Agent的完整生命周期：类型注册、事件监听、执行、结果存储。

    使用示例：
        orchestrator = SubAgentOrchestrator(event_bus=event_bus)
        orchestrator.register_type(SubAgentType.SEARCH, SearchAgent)
        orchestrator.start_listening()
        # 通过事件或直接调用执行子Agent
        result = await orchestrator.execute("search", {"query": "test"}, session_id="s1")
    """

    def __init__(
        self,
        event_bus: Any | None = None,
        log_collector: Any | None = None,
        registry: Any | None = None,
    ) -> None:
        """初始化子Agent编排器

        参数：
            event_bus: 事件总线（可选，用于事件订阅/发布）
            log_collector: 日志收集器（可选）
            registry: 子Agent注册表（可选，默认创建新实例）
        """
        self._event_bus = event_bus
        self._log_collector = log_collector

        # 延迟导入以减少上层初始化开销
        if registry is not None:
            self._registry = registry
        else:
            from src.domain.services.sub_agent_scheduler import SubAgentRegistry

            self._registry = SubAgentRegistry()

        # 状态容器
        self._active_subagents: dict[str, dict[str, Any]] = {}
        self._results: dict[str, list[dict[str, Any]]] = {}
        self._is_listening = False

        # 事件处理器引用（用于取消订阅）
        self._spawn_event_handler: Any = None

    def _log(self, level: str, message: str, context: dict[str, Any] | None = None) -> None:
        """内部日志记录（带标准 logging 兜底）"""
        ctx = context or {}
        if self._log_collector is not None:
            log_method = getattr(self._log_collector, level.lower(), None)
            if log_method:
                log_method("SubAgentOrchestrator", message, ctx)
        else:
            # 兜底：使用标准 logging
            log_fn = getattr(logger, level.lower(), logger.info)
            log_fn(f"SubAgentOrchestrator: {message} | {ctx}")

    # ==================== 类型注册 ====================

    def register_type(self, agent_type: Any, agent_class: type) -> None:
        """注册子Agent类型

        参数：
            agent_type: SubAgentType 枚举值
            agent_class: 子Agent类
        """
        self._registry.register(agent_type, agent_class)

    def list_types(self) -> list[Any]:
        """获取已注册的子Agent类型列表

        返回：
            SubAgentType 列表
        """
        return self._registry.list_types()

    # ==================== 事件监听控制 ====================

    def start_listening(self) -> None:
        """启动子Agent事件监听器

        订阅 SpawnSubAgentEvent 以处理子Agent生成请求。
        """
        if self._is_listening:
            return

        if self._event_bus is None:
            return  # 无EventBus时静默返回，不报错

        from src.domain.agents.conversation_agent import SpawnSubAgentEvent

        # 保存处理器引用以便取消订阅
        self._spawn_event_handler = self._handle_spawn_event_wrapper
        self._event_bus.subscribe(SpawnSubAgentEvent, self._spawn_event_handler)
        self._is_listening = True

        self._log("info", "子Agent事件监听已启动", {})

    def stop_listening(self) -> None:
        """停止子Agent事件监听"""
        if not self._is_listening:
            return

        if self._event_bus is None:
            return

        from src.domain.agents.conversation_agent import SpawnSubAgentEvent

        if self._spawn_event_handler is not None:
            self._event_bus.unsubscribe(SpawnSubAgentEvent, self._spawn_event_handler)
        self._is_listening = False

        self._log("info", "子Agent事件监听已停止", {})

    async def _handle_spawn_event_wrapper(self, event: Any) -> None:
        """SpawnSubAgentEvent 处理器包装器（不返回值，符合 EventBus handler 约定）"""
        await self.handle_spawn_event(event)

    async def handle_spawn_event(self, event: Any) -> Any:
        """处理子Agent生成事件

        参数：
            event: SpawnSubAgentEvent 事件

        返回：
            SubAgentResult 执行结果
        """
        return await self.execute(
            subagent_type=event.subagent_type,
            task_payload=event.task_payload,
            context=event.context_snapshot,
            session_id=event.session_id,
        )

    # ==================== 子Agent执行 ====================

    async def execute(
        self,
        subagent_type: str,
        task_payload: dict[str, Any],
        context: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> Any:
        """执行子Agent任务

        参数：
            subagent_type: 子Agent类型（字符串）
            task_payload: 任务负载
            context: 执行上下文
            session_id: 会话ID

        返回：
            SubAgentResult 执行结果
        """
        from src.domain.services.sub_agent_scheduler import (
            SubAgentResult,
            SubAgentType,
        )

        # 转换类型字符串为枚举
        try:
            agent_type_enum = SubAgentType(subagent_type)
        except ValueError:
            return SubAgentResult(
                agent_id="",
                agent_type=subagent_type,
                success=False,
                error=f"Unknown subagent type: {subagent_type}",
            )

        # 创建子Agent实例
        agent = self._registry.create_instance(agent_type_enum)
        if agent is None:
            return SubAgentResult(
                agent_id="",
                agent_type=subagent_type,
                success=False,
                error=f"SubAgent type not registered: {subagent_type}",
            )

        subagent_id = agent.agent_id

        # 记录活跃子Agent
        self._active_subagents[subagent_id] = {
            "type": subagent_type,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "session_id": session_id,
        }

        try:
            # 执行子Agent
            result = await agent.execute(task_payload, context or {})

            # 更新状态
            self._active_subagents[subagent_id]["status"] = (
                "completed" if result.success else "failed"
            )
            self._active_subagents[subagent_id]["completed_at"] = datetime.now().isoformat()

            # 存储结果到会话
            if session_id:
                if session_id not in self._results:
                    self._results[session_id] = []
                self._results[session_id].append(
                    {
                        "subagent_id": subagent_id,
                        "subagent_type": subagent_type,
                        "success": result.success,
                        "result": result.output,
                        "error": result.error,
                        "execution_time": result.execution_time,
                    }
                )

            # 发布完成事件
            await self._publish_completed_event(
                subagent_id=subagent_id,
                subagent_type=subagent_type,
                session_id=session_id,
                success=result.success,
                result=result.output,
                error=result.error,
                execution_time=result.execution_time,
            )

            self._log(
                "info",
                f"子Agent执行完成: {subagent_type}",
                {
                    "subagent_id": subagent_id,
                    "session_id": session_id,
                    "success": result.success,
                },
            )

            # 清理已完成的子Agent
            del self._active_subagents[subagent_id]

            return result

        except Exception as e:
            # 记录失败
            self._active_subagents[subagent_id]["status"] = "failed"
            self._active_subagents[subagent_id]["error"] = str(e)

            # 发布失败事件
            await self._publish_completed_event(
                subagent_id=subagent_id,
                subagent_type=subagent_type,
                session_id=session_id,
                success=False,
                error=str(e),
            )

            self._log(
                "error",
                f"子Agent执行失败: {subagent_type}",
                {
                    "subagent_id": subagent_id,
                    "session_id": session_id,
                    "error": str(e),
                },
            )

            # 清理
            del self._active_subagents[subagent_id]

            return SubAgentResult(
                agent_id=subagent_id,
                agent_type=subagent_type,
                success=False,
                error=str(e),
            )

    async def _publish_completed_event(
        self,
        subagent_id: str,
        subagent_type: str,
        session_id: str,
        success: bool,
        result: Any = None,
        error: str | None = None,
        execution_time: int = 0,
    ) -> None:
        """发布子Agent完成事件"""
        if self._event_bus is None:
            return

        from src.domain.agents.coordinator_agent import SubAgentCompletedEvent

        await self._event_bus.publish(
            SubAgentCompletedEvent(
                subagent_id=subagent_id,
                subagent_type=subagent_type,
                session_id=session_id,
                success=success,
                result=result,
                error=error,
                execution_time=execution_time,
                source="subagent_orchestrator",
            )
        )

    # ==================== 状态查询 ====================

    def get_status(self, subagent_id: str) -> dict[str, Any] | None:
        """获取子Agent状态

        参数：
            subagent_id: 子Agent实例ID

        返回：
            状态字典，如果不存在返回None
        """
        return self._active_subagents.get(subagent_id)

    def get_session_results(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话的子Agent执行结果列表

        参数：
            session_id: 会话ID

        返回：
            该会话的所有子Agent执行结果列表，如果不存在返回空列表
        """
        return self._results.get(session_id, [])


__all__ = ["SubAgentOrchestrator"]

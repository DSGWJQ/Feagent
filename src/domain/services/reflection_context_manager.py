"""ReflectionContextManager - 反思上下文管理器

Phase 35.4: 从 CoordinatorAgent 提取反思上下文追踪与压缩集成功能。

职责：
1. 监听 WorkflowReflectionCompletedEvent 并记录到 reflection_contexts
2. 集成上下文压缩器（ContextCompressor + ContextSnapshotManager）
3. 提供反思摘要和压缩上下文查询接口
4. 修复取消订阅bug：记录当前订阅的handler

关键修复：
- _current_reflection_handler: 记录实际订阅的handler，确保取消订阅正确
"""

from typing import Any


class ReflectionContextManager:
    """反思上下文管理器

    管理工作流反思事件的追踪、压缩与查询。

    使用示例：
        event_bus = EventBus()
        reflection_contexts = {}
        compressed_contexts = {}
        manager = ReflectionContextManager(
            event_bus=event_bus,
            reflection_contexts=reflection_contexts,
            compressed_contexts=compressed_contexts,
        )
        manager.start_reflection_listening()
    """

    def __init__(
        self,
        event_bus: Any | None,
        reflection_contexts: dict[str, dict[str, Any]],
        compressed_contexts: dict[str, Any],
        compressor: Any = None,  # ContextCompressor
        snapshot_manager: Any = None,  # ContextSnapshotManager
    ):
        """初始化反思上下文管理器

        参数：
            event_bus: 事件总线（允许为 None，在 start_reflection_listening 时验证）
            reflection_contexts: 共享的反思上下文字典（由调用方维护）
            compressed_contexts: 共享的压缩上下文字典（由调用方维护）
            compressor: 上下文压缩器（可选，懒加载）
            snapshot_manager: 快照管理器（可选，懒加载）
        """
        self.event_bus = event_bus
        self.reflection_contexts = reflection_contexts
        self._compressed_contexts = compressed_contexts
        self.context_compressor = compressor
        self.snapshot_manager = snapshot_manager

        self._is_listening_reflections = False
        self._is_compressing_context = False
        self._current_reflection_handler = None  # 修复取消订阅bug

    # === 反思监听 ===

    def start_reflection_listening(self, enable_compression: bool = False) -> None:
        """开始监听反思事件

        订阅 WorkflowReflectionCompletedEvent，记录反思结果到上下文。
        根据 enable_compression 参数选择处理器。

        参数：
            enable_compression: 是否启用压缩模式

        异常：
            ValueError: event_bus 为 None 时抛出
        """
        if self._is_listening_reflections:
            return  # 已经在监听，避免重复订阅

        if self.event_bus is None:
            raise ValueError("EventBus is required for reflection listening")

        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        # 根据是否启用压缩选择处理器
        if enable_compression:
            self.start_context_compression()
            handler = self._handle_reflection_event_with_compression
        else:
            handler = self._handle_reflection_event

        self.event_bus.subscribe(WorkflowReflectionCompletedEvent, handler)
        self._current_reflection_handler = handler  # 关键：记录实际订阅的handler
        self._is_listening_reflections = True

    def stop_reflection_listening(self) -> None:
        """停止监听反思事件

        取消订阅 WorkflowReflectionCompletedEvent。
        使用 _current_reflection_handler 确保取消订阅正确（修复bug）。
        """
        if not self._is_listening_reflections:
            return  # 未在监听，无需取消订阅

        if self.event_bus is None or self._current_reflection_handler is None:
            return

        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

        self.event_bus.unsubscribe(
            WorkflowReflectionCompletedEvent, self._current_reflection_handler
        )
        self._current_reflection_handler = None
        self._is_listening_reflections = False

    async def _handle_reflection_event(self, event: Any) -> None:
        """处理反思事件

        将反思结果记录到 reflection_contexts，维护最新值与 history。

        参数：
            event: WorkflowReflectionCompletedEvent 实例
        """
        workflow_id = event.workflow_id

        reflection_record = {
            "assessment": event.assessment,
            "should_retry": event.should_retry,
            "confidence": event.confidence,
            "timestamp": event.timestamp,
        }

        if workflow_id not in self.reflection_contexts:
            # 首次创建上下文
            self.reflection_contexts[workflow_id] = {
                "workflow_id": workflow_id,
                "assessment": event.assessment,
                "should_retry": event.should_retry,
                "confidence": event.confidence,
                "timestamp": event.timestamp,
                "history": [reflection_record],
            }
        else:
            # 更新现有上下文
            context = self.reflection_contexts[workflow_id]
            context["assessment"] = event.assessment
            context["should_retry"] = event.should_retry
            context["confidence"] = event.confidence
            context["timestamp"] = event.timestamp
            context.setdefault("history", []).append(reflection_record)

    async def _handle_reflection_event_with_compression(self, event: Any) -> None:
        """处理反思事件（带压缩）

        先调用 _handle_reflection_event 记录反思，
        再调用 _compress_and_save_context 压缩数据。

        参数：
            event: WorkflowReflectionCompletedEvent 实例
        """
        await self._handle_reflection_event(event)

        if self._is_compressing_context:
            workflow_id = event.workflow_id
            self._compress_and_save_context(
                workflow_id=workflow_id,
                source_type="reflection",
                raw_data={
                    "assessment": event.assessment,
                    "should_retry": getattr(event, "should_retry", False),
                    "confidence": event.confidence,
                    "recommendations": getattr(event, "recommendations", []),
                },
            )

    def get_reflection_summary(self, workflow_id: str) -> dict[str, Any] | None:
        """获取反思摘要

        返回：
            反思摘要字典，包含：
            - workflow_id: 工作流ID
            - assessment: 最新评估
            - should_retry: 是否应重试
            - confidence: 置信度
            - total_reflections: 反思总数
            - last_updated: 最后更新时间

            如果 workflow_id 不存在则返回 None
        """
        context = self.reflection_contexts.get(workflow_id)
        if not context:
            return None

        return {
            "workflow_id": workflow_id,
            "assessment": context.get("assessment", ""),
            "should_retry": context.get("should_retry", False),
            "confidence": context.get("confidence", 0.0),
            "total_reflections": len(context.get("history", [])),
            "last_updated": context.get("timestamp"),
        }

    # === 上下文压缩 ===

    def start_context_compression(self) -> None:
        """启动上下文压缩

        初始化压缩器和快照管理器（懒加载），启用压缩标志。
        如果已经在压缩，则不执行任何操作（幂等操作）。
        """
        if self._is_compressing_context:
            return  # 已经在压缩

        # 懒加载压缩器
        if not self.context_compressor:
            from src.domain.services.context_compressor import ContextCompressor

            self.context_compressor = ContextCompressor()

        # 懒加载快照管理器
        if not self.snapshot_manager:
            from src.domain.services.context_compressor import ContextSnapshotManager

            self.snapshot_manager = ContextSnapshotManager()

        self._is_compressing_context = True

    def stop_context_compression(self) -> None:
        """停止上下文压缩

        禁用压缩标志（保留压缩器实例）。
        """
        self._is_compressing_context = False

    def _compress_and_save_context(
        self,
        workflow_id: str,
        source_type: str,
        raw_data: dict[str, Any],
    ) -> None:
        """压缩并保存上下文

        将原始数据压缩后保存到 _compressed_contexts 和快照管理器。

        参数：
            workflow_id: 工作流ID
            source_type: 数据来源类型（如 "reflection", "execution"）
            raw_data: 原始数据字典
        """
        if not self._is_compressing_context:
            return  # 压缩未启用

        if not self.context_compressor or not self.snapshot_manager:
            return  # 压缩器或快照管理器未初始化

        from src.domain.services.context_compressor import CompressionInput

        input_data = CompressionInput(
            source_type=source_type,
            workflow_id=workflow_id,
            raw_data=raw_data,
        )

        # 如果已有上下文，则合并；否则压缩
        existing = self._compressed_contexts.get(workflow_id)
        if existing:
            new_context = self.context_compressor.merge(existing, input_data)
        else:
            new_context = self.context_compressor.compress(input_data)

        self._compressed_contexts[workflow_id] = new_context
        self.snapshot_manager.save_snapshot(new_context)

    def get_compressed_context(self, workflow_id: str) -> Any:
        """获取压缩上下文

        优先从缓存读取，缓存未命中则从快照管理器读取。

        参数：
            workflow_id: 工作流ID

        返回：
            压缩上下文对象，如果不存在则返回 None
        """
        # 优先从缓存读取
        if workflow_id in self._compressed_contexts:
            return self._compressed_contexts[workflow_id]

        # 缓存未命中，从快照读取
        if self.snapshot_manager:
            return self.snapshot_manager.get_latest_snapshot(workflow_id)

        return None

    def get_context_summary_text(self, workflow_id: str) -> str | None:
        """获取上下文摘要文本

        返回人类可读的摘要文本。

        参数：
            workflow_id: 工作流ID

        返回：
            摘要文本字符串，如果不存在或不支持则返回 None
        """
        context = self.get_compressed_context(workflow_id)
        if context and hasattr(context, "to_summary_text"):
            return context.to_summary_text()
        return None


__all__ = ["ReflectionContextManager"]

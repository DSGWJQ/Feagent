"""MessageLogListener - 简单消息监听器

Phase 35.3: 从 CoordinatorAgent 提取消息日志监听与统计功能。

职责：
1. 订阅 SimpleMessageEvent 并记录到 message_log
2. 维护有界列表（MAX_SIZE 限制）
3. 提供消息统计功能（按意图分类）
4. 为 UnifiedLogIntegration 提供只读访问接口
"""

from typing import Any

from src.domain.services.event_bus import EventBus

# 默认最大消息日志大小
DEFAULT_MAX_MESSAGE_LOG_SIZE = 1000


class MessageLogAccessor:
    """Message Log Accessor for UnifiedLogIntegration

    提供对 message_log 的只读访问接口。
    """

    def __init__(self, messages_ref: list[dict[str, Any]]):
        """初始化访问器

        参数：
            messages_ref: message_log 引用（append-only list）
        """
        self._messages = messages_ref

    def get_messages(self) -> list[dict[str, Any]]:
        """获取消息日志列表

        返回：
            消息日志列表（只读访问）
        """
        return self._messages


class MessageLogListener:
    """简单消息监听器

    负责订阅 SimpleMessageEvent，将事件记录到 message_log，
    并提供按意图的统计功能。

    使用示例：
        event_bus = EventBus()
        message_log = []
        listener = MessageLogListener(
            event_bus=event_bus,
            message_log=message_log,
            max_size=1000
        )
        listener.start()
    """

    def __init__(
        self,
        event_bus: EventBus | None,
        message_log: list[dict[str, Any]],
        max_size: int = DEFAULT_MAX_MESSAGE_LOG_SIZE,
    ):
        """初始化消息监听器

        参数：
            event_bus: 事件总线（允许为 None，在 start() 时验证）
            message_log: 共享的消息日志列表（由调用方维护）
            max_size: 消息日志最大大小限制（默认 1000）

        注意：
            允许 event_bus=None 以支持延迟初始化和向后兼容，
            实际验证在 start() 方法中进行。
        """
        self.event_bus = event_bus
        self.message_log = message_log
        self.max_size = max_size
        self.is_listening = False

    def start(self) -> None:
        """开始监听简单消息事件

        订阅 SimpleMessageEvent，将消息记录到 message_log。
        如果已经在监听，则不重复订阅（幂等操作）。

        异常：
            ValueError: event_bus 为 None 时抛出
        """
        if self.is_listening:
            return  # 已经在监听，避免重复订阅

        if self.event_bus is None:
            raise ValueError("event_bus is required to start MessageLogListener")

        from src.domain.agents.conversation_agent import SimpleMessageEvent

        self.event_bus.subscribe(SimpleMessageEvent, self._handle_simple_message_event)
        self.is_listening = True

    def stop(self) -> None:
        """停止监听简单消息事件

        取消订阅 SimpleMessageEvent。
        如果未在监听，则不执行任何操作（幂等操作）。
        """
        if not self.is_listening:
            return  # 未在监听，无需取消订阅

        if self.event_bus is None:
            # 如果 event_bus 为 None，不应该处于监听状态，
            # 但为了安全起见，重置标志
            self.is_listening = False
            return

        from src.domain.agents.conversation_agent import SimpleMessageEvent

        self.event_bus.unsubscribe(SimpleMessageEvent, self._handle_simple_message_event)
        self.is_listening = False

    async def _handle_simple_message_event(self, event: Any) -> None:
        """处理简单消息事件

        将消息记录到 message_log（带大小限制防止内存泄漏）。

        参数：
            event: SimpleMessageEvent 实例
        """
        # 使用有界列表防止内存泄漏
        self._add_to_bounded_list(
            self.message_log,
            {
                "user_input": event.user_input,
                "response": event.response,
                "intent": event.intent,
                "confidence": event.confidence,
                "session_id": event.session_id,
                "timestamp": event.timestamp,
            },
        )

    def _add_to_bounded_list(
        self,
        target_list: list[Any],
        item: Any,
    ) -> None:
        """添加项目到有界列表，超出限制时移除最旧的项

        参数：
            target_list: 目标列表
            item: 要添加的项目
        """
        target_list.append(item)
        while len(target_list) > self.max_size:
            target_list.pop(0)  # 移除最旧的

    def get_statistics(self) -> dict[str, Any]:
        """获取消息统计

        返回：
            包含消息统计的字典：
            - total_messages: 总消息数
            - by_intent: 按意图分类的消息数
        """
        by_intent: dict[str, int] = {}

        for msg in self.message_log:
            intent = msg.get("intent", "unknown")
            by_intent[intent] = by_intent.get(intent, 0) + 1

        return {
            "total_messages": len(self.message_log),
            "by_intent": by_intent,
        }


__all__ = ["MessageLogListener", "MessageLogAccessor", "DEFAULT_MAX_MESSAGE_LOG_SIZE"]

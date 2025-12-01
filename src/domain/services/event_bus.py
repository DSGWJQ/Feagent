"""事件总线 (EventBus) - 多Agent协作系统的通信基础设施

业务定义：
- EventBus 是对话Agent、工作流Agent、协调者Agent之间的解耦通信机制
- 通过发布/订阅模式实现Agent间的异步通信
- 支持中间件机制，用于协调者Agent拦截和验证决策

设计原则：
- 纯 Python 实现，不依赖外部消息队列（MVP阶段）
- 使用 asyncio 支持异步处理
- 支持类型过滤，订阅者只收到关心的事件类型
- 中间件可以阻止事件传播（用于协调者纠偏）

核心概念：
- Event: 事件基类，所有业务事件继承此类
- EventBus: 事件总线，负责事件的发布和分发
- Middleware: 中间件，在事件传递到处理器之前进行拦截处理
"""

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件基类

    所有业务事件都应该继承此类。

    属性说明：
    - id: 事件唯一标识符（UUID），用于追踪和关联
    - timestamp: 事件创建时间，用于排序和审计
    - source: 事件来源（哪个Agent发布的）
    - correlation_id: 关联ID，用于追踪事件因果关系

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__
    2. 子类可以轻松添加额外字段
    3. 纯 Python，符合 DDD 要求

    使用示例：
        @dataclass
        class DecisionMadeEvent(Event):
            decision_type: str = ""
            payload: dict = field(default_factory=dict)
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    correlation_id: str | None = None


# 类型定义
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]
EventMiddleware = Callable[[Event], Coroutine[Any, Any, Event | None]]


class EventBus:
    """事件总线

    职责：
    1. 管理事件订阅关系
    2. 分发事件到对应的处理器
    3. 执行中间件链
    4. 记录事件日志

    设计决策：
    - 单一数据源：所有状态变更都通过事件传递
    - 类型过滤：订阅者只收到指定类型的事件
    - 中间件链：按添加顺序执行，任何中间件返回None则阻止传播
    - 错误隔离：单个处理器异常不影响其他处理器

    使用示例：
        event_bus = EventBus()

        # 订阅事件
        event_bus.subscribe(DecisionMadeEvent, handler)

        # 添加中间件（协调者验证）
        event_bus.add_middleware(coordinator_middleware)

        # 发布事件
        await event_bus.publish(DecisionMadeEvent(...))
    """

    def __init__(self):
        """初始化事件总线"""
        # 订阅者映射：事件类型 -> 处理器列表
        self._subscribers: dict[type[Event], list[EventHandler]] = {}

        # 中间件列表（按添加顺序执行）
        self._middlewares: list[EventMiddleware] = []

        # 事件日志（用于审计和调试）
        self._event_log: list[Event] = []

    @property
    def event_log(self) -> list[Event]:
        """获取事件日志（只读）

        用途：
        - 审计：追踪所有Agent的决策历史
        - 调试：回放事件序列定位问题
        - 分析：统计事件分布和频率
        """
        return self._event_log

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        """订阅特定类型的事件

        参数：
            event_type: 要订阅的事件类型
            handler: 异步处理器函数

        设计说明：
        - 类型过滤：只有匹配类型的事件才会传递给处理器
        - 多订阅者：同一事件类型可以有多个订阅者
        - 顺序保证：订阅者按添加顺序被调用

        使用示例：
            async def handle_decision(event: DecisionMadeEvent):
                print(f"收到决策: {event.decision_type}")

            event_bus.subscribe(DecisionMadeEvent, handle_decision)
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(handler)
        logger.debug(
            f"订阅事件: {event_type.__name__}, 当前订阅者数: {len(self._subscribers[event_type])}"
        )

    def unsubscribe(self, event_type: type[Event], handler: EventHandler) -> bool:
        """取消订阅特定类型的事件

        参数：
            event_type: 事件类型
            handler: 要移除的处理器函数

        返回：
            是否成功移除

        使用示例：
            event_bus.unsubscribe(DecisionMadeEvent, handle_decision)
        """
        if event_type not in self._subscribers:
            return False

        handlers = self._subscribers[event_type]
        if handler in handlers:
            handlers.remove(handler)
            logger.debug(f"取消订阅: {event_type.__name__}, 剩余订阅者数: {len(handlers)}")
            return True

        return False

    def add_middleware(self, middleware: EventMiddleware) -> None:
        """添加中间件

        参数：
            middleware: 异步中间件函数，接收Event，返回Event或None

        中间件职责：
        - 验证：检查事件合法性（如协调者验证决策）
        - 转换：修改或增强事件数据
        - 拦截：返回None阻止事件继续传播

        执行顺序：
        - 中间件按添加顺序链式执行
        - 任何中间件返回None，后续中间件和处理器都不执行

        使用示例：
            async def coordinator_middleware(event: Event) -> Event | None:
                if is_valid(event):
                    return event  # 验证通过，继续传播
                else:
                    return None   # 验证失败，阻止传播
        """
        self._middlewares.append(middleware)
        logger.debug(f"添加中间件, 当前中间件数: {len(self._middlewares)}")

    async def publish(self, event: Event) -> None:
        """发布事件

        参数：
            event: 要发布的事件

        执行流程：
        1. 执行所有中间件（按顺序）
        2. 如果中间件返回None，停止传播
        3. 记录事件到日志
        4. 分发给所有匹配类型的订阅者
        5. 捕获并记录处理器异常（不影响其他处理器）

        错误处理：
        - 中间件异常：记录日志，阻止事件传播
        - 处理器异常：记录日志，继续调用其他处理器
        """
        logger.debug(f"发布事件: {type(event).__name__}, id={event.id}")

        # 1. 执行中间件链
        processed_event = await self._execute_middlewares(event)

        if processed_event is None:
            logger.debug(f"事件被中间件阻止: {event.id}")
            return

        # 2. 记录到事件日志
        self._event_log.append(processed_event)

        # 3. 分发给订阅者
        await self._dispatch_to_subscribers(processed_event)

    async def _execute_middlewares(self, event: Event) -> Event | None:
        """执行中间件链

        按添加顺序执行所有中间件：
        - 每个中间件接收前一个的输出
        - 任何中间件返回None，立即停止

        返回：
            处理后的事件，或None（如果被阻止）
        """
        current_event = event

        for middleware in self._middlewares:
            try:
                result = await middleware(current_event)

                if result is None:
                    # 中间件阻止了事件传播
                    return None

                current_event = result

            except Exception as e:
                logger.error(f"中间件执行异常: {e}", exc_info=True)
                # 中间件异常视为阻止传播
                return None

        return current_event

    async def _dispatch_to_subscribers(self, event: Event) -> None:
        """分发事件给订阅者

        类型匹配规则：
        - 精确匹配事件类型
        - 调用所有匹配的处理器

        错误隔离：
        - 单个处理器异常不影响其他处理器
        - 异常被记录到日志
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])

        logger.debug(f"分发事件 {event_type.__name__} 给 {len(handlers)} 个订阅者")

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                # 记录异常，但继续执行其他处理器
                logger.error(
                    f"事件处理器异常: {handler.__name__}, "
                    f"event_type={event_type.__name__}, "
                    f"event_id={event.id}, "
                    f"error={e}",
                    exc_info=True,
                )


# 导出
__all__ = ["Event", "EventBus", "EventHandler", "EventMiddleware"]

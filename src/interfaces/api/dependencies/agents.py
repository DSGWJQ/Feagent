"""EventBus Dependencies (compat module name kept for backward compatibility)

提供 EventBus 的依赖注入，供 Interface / Application 复用。

Author: Claude Code
Date: 2025-12-17 (P1-2 Fix: Agent Collaboration Integration)
Updated: 2025-12-17 (P1-1 Fix: ModelMetadataPort Injection)
"""

from typing import Annotated

from fastapi import Depends, Request

from src.domain.services.event_bus import EventBus

_fallback_event_bus: EventBus | None = None


def _get_fallback_event_bus() -> EventBus:
    """内部 fallback：供非 Request 上下文使用"""
    global _fallback_event_bus
    if _fallback_event_bus is None:
        _fallback_event_bus = EventBus()
    return _fallback_event_bus


def set_event_bus(event_bus: EventBus) -> None:
    """设置全局 EventBus 单例（由 main.py lifespan 调用）

    Args:
        event_bus: 应用级 EventBus 实例
    """
    global _fallback_event_bus
    _fallback_event_bus = event_bus


def get_event_bus(request: Request) -> EventBus:
    """获取 EventBus 单例（优先从 FastAPI app.state 获取）

    Args:
        request: FastAPI Request 对象（通过 Depends 自动注入）

    Returns:
        EventBus 实例
    """
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        # Fallback：如果 app.state 未初始化，使用内部单例
        bus = _get_fallback_event_bus()
        request.app.state.event_bus = bus
    return bus


# Type aliases for FastAPI dependency injection
EventBusDep = Annotated[EventBus, Depends(get_event_bus)]

"""
Memory Dependencies

内存系统的依赖注入配置，提供：
- MemoryServicePort 端口协议实现
- 通过 Ports and Adapters 模式解耦接口层与基础设施层

Author: Claude Code
Date: 2025-12-17 (P1-1 Fix: Ports/Adapters Compliance)
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.application.services.composite_memory_service import CompositeMemoryService
from src.domain.ports.memory_service import MemoryServicePort
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.chat_message_repository import (
    SQLAlchemyChatMessageRepository,
)
from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore
from src.infrastructure.memory.in_memory_cache import InMemoryCache
from src.infrastructure.memory.tfidf_compressor import TFIDFCompressor


@lru_cache
def get_global_memory_cache() -> InMemoryCache:
    """
    获取全局单例缓存

    Returns:
        InMemoryCache 实例（全局共享）

    Configuration:
        - TTL: 15 分钟
        - 最大 workflow 数: 1000
        - 每个 workflow 最大消息数: 50
    """
    return InMemoryCache(ttl_seconds=900, max_workflows=1000, max_messages_per_workflow=50)


def _create_memory_service_impl(session=None) -> CompositeMemoryService:
    """
    创建 CompositeMemoryService 实现（内部工厂函数）

    Args:
        session: 数据库会话（可选，用于测试）

    Returns:
        CompositeMemoryService 实例
    """
    if session is None:
        session = next(get_db_session())

    # 创建依赖组件
    repository = SQLAlchemyChatMessageRepository(session)
    db_store = DatabaseMemoryStore(repository)
    cache = get_global_memory_cache()
    compressor = TFIDFCompressor()

    return CompositeMemoryService(
        db_store=db_store, cache=cache, compressor=compressor, max_context_tokens=4000
    )


def get_memory_service() -> MemoryServicePort:
    """
    获取内存服务（通过端口协议）

    Returns:
        MemoryServicePort 实例

    架构说明:
        Interface Layer → MemoryServicePort (Domain Port)
                         ↑
             CompositeMemoryService (Application Layer)

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/api/memory/test")
        >>> async def test(memory: MemoryServicePort = Depends(get_memory_service)):
        ...     metrics = memory.get_metrics()
        ...     return metrics
    """
    return _create_memory_service_impl()


# Backward-compatible helper used by some route wiring.
def get_composite_memory_service(session=None) -> CompositeMemoryService:
    """Return CompositeMemoryService instance (optionally bound to a given DB session)."""

    return _create_memory_service_impl(session=session)


# Type alias for FastAPI dependency injection
MemoryServiceDep = Annotated[MemoryServicePort, Depends(get_memory_service)]

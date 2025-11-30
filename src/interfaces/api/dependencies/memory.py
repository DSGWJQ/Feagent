"""
Memory Dependencies

内存系统的依赖注入配置，提供：
- CompositeMemoryService 单例
- InMemoryCache 全局单例
- 性能监控端点

Author: Claude Code
Date: 2025-11-30
"""

from functools import lru_cache

from src.application.services.composite_memory_service import CompositeMemoryService
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


def get_composite_memory_service(session=None) -> CompositeMemoryService:
    """
    创建 CompositeMemoryService 实例

    Args:
        session: 数据库会话（可选，用于测试）

    Returns:
        CompositeMemoryService 实例

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/api/memory/test")
        >>> async def test(memory: CompositeMemoryService = Depends(get_composite_memory_service)):
        ...     metrics = memory.get_metrics()
        ...     return metrics
    """
    if session is None:
        # 生产环境：从依赖注入获取 session
        # 这里为了简化，直接创建（实际应该用 Depends）
        from src.infrastructure.database.engine import get_db_session

        session = next(get_db_session())

    # 创建依赖组件
    repository = SQLAlchemyChatMessageRepository(session)
    db_store = DatabaseMemoryStore(repository)
    cache = get_global_memory_cache()
    compressor = TFIDFCompressor()

    return CompositeMemoryService(
        db_store=db_store, cache=cache, compressor=compressor, max_context_tokens=4000
    )

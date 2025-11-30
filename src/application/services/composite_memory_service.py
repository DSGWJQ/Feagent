"""
Composite Memory Service

组合式内存服务，编排 DB + Cache + Compressor 的交互逻辑。
实现原子双写、自动回溯、智能压缩和性能监控。

Author: Claude Code
Date: 2025-11-30
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.entities.chat_message import ChatMessage
from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore
from src.infrastructure.memory.in_memory_cache import InMemoryCache
from src.infrastructure.memory.tfidf_compressor import TFIDFCompressor

logger = logging.getLogger(__name__)


@dataclass
class MemoryMetrics:
    """
    内存操作指标

    Attributes:
        cache_hit_rate: 缓存命中率（0-1）
        fallback_count: 回溯到数据库的次数
        compression_ratio: 平均压缩比（压缩后/压缩前）
        avg_fallback_time_ms: 平均回溯耗时（毫秒）
        last_updated: 最后更新时间
    """

    cache_hit_rate: float
    fallback_count: int
    compression_ratio: float
    avg_fallback_time_ms: float
    last_updated: datetime = field(default_factory=datetime.utcnow)


class CompositeMemoryService:
    """
    组合式内存服务（双写 + 回溯 + 压缩）

    核心功能：
    1. 原子双写：DB → Cache（DB 失败则回滚，Cache 失败标记失效）
    2. 智能读取：Cache 命中直接返回，未命中回溯到 DB + 压缩 + 更新缓存
    3. 性能监控：追踪命中率、回溯次数、压缩比

    Architecture:
        CompositeMemoryService (Application Layer)
            ├─ DatabaseMemoryStore (Infrastructure)
            ├─ InMemoryCache (Infrastructure)
            └─ TFIDFCompressor (Infrastructure)

    Example:
        >>> service = CompositeMemoryService(db_store, cache, compressor)
        >>> message = ChatMessage.create("wf_123", "Hello", is_user=True)
        >>> service.append(message)  # 双写
        >>> recent = service.load_recent("wf_123", last_n=10)  # 智能读取
        >>> metrics = service.get_metrics()  # 性能指标
    """

    def __init__(
        self,
        db_store: DatabaseMemoryStore,
        cache: InMemoryCache,
        compressor: TFIDFCompressor,
        max_context_tokens: int = 4000,
    ):
        """
        初始化组合式内存服务

        Args:
            db_store: 数据库存储适配器
            cache: 缓存层
            compressor: 压缩算法
            max_context_tokens: 最大上下文 token 数（默认 4000）
        """
        self._db = db_store
        self._cache = cache
        self._compressor = compressor
        self._max_tokens = max_context_tokens

        # 监控指标
        self._fallback_times = []
        self._compression_ratios = []

    def append(self, message: ChatMessage) -> None:
        """
        追加消息（原子双写：DB → Cache）

        流程：
        1. 写入数据库（失败则抛异常）
        2. 更新缓存（失败不影响主流程，但标记失效）

        Args:
            message: 要追加的聊天消息

        Raises:
            Exception: 数据库写入失败时
        """
        # 1. 写入数据库（失败则抛异常）
        try:
            self._db.append(message)
        except Exception as e:
            logger.error(f"Database write failed for message {message.id}: {e}")
            raise

        # 2. 更新缓存（失败不影响主流程）
        try:
            # 读取当前缓存
            cached = self._cache.get(message.workflow_id)
            if cached is None:
                cached = []

            # 追加新消息
            cached.append(message)

            # 更新缓存
            self._cache.put(message.workflow_id, cached)
            logger.debug(f"Message {message.id} cached successfully")
        except Exception as e:
            logger.warning(f"Cache write failed for workflow {message.workflow_id}: {e}")
            # 标记缓存失效，触发下次回溯
            self._cache.invalidate(message.workflow_id)

    def load_recent(self, workflow_id: str, last_n: int = 10) -> list[ChatMessage]:
        """
        加载最近消息（缓存优先 + 自动回溯）

        流程：
        1. 尝试从缓存读取
        2. 缓存命中 → 直接返回
        3. 缓存未命中 → 回溯到数据库 → 压缩 → 更新缓存

        Args:
            workflow_id: 工作流 ID
            last_n: 需要的消息数量（默认 10）

        Returns:
            最近 N 条消息列表（按时间升序）
        """
        # 1. 尝试从缓存读取
        cached = self._cache.get(workflow_id)
        if cached is not None:
            logger.debug(f"Cache hit for workflow {workflow_id}")
            return cached[-last_n:]

        # 2. 缓存未命中 → 回溯到数据库
        logger.info(f"Cache miss for workflow {workflow_id}, falling back to database")

        start_time = datetime.utcnow()

        # 3. 从数据库加载（多取一些用于压缩）
        messages = self._db.load_recent(workflow_id, last_n=100)

        if not messages:
            return []

        # 4. 压缩（如果超过 token 限制）
        original_count = len(messages)
        compressed = self._compressor.compress(
            messages, max_tokens=self._max_tokens, min_messages=min(2, last_n)
        )

        # 5. 更新缓存
        self._cache.put(workflow_id, compressed)

        # 6. 记录指标
        fallback_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        self._fallback_times.append(fallback_time)

        compression_ratio = len(compressed) / original_count if original_count > 0 else 1.0
        self._compression_ratios.append(compression_ratio)

        logger.info(
            f"Fallback completed in {fallback_time:.2f}ms, "
            f"compressed {original_count} → {len(compressed)} messages"
        )

        return compressed[-last_n:]

    def search(
        self, query: str, workflow_id: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """
        搜索相关消息（直接查询数据库）

        Args:
            query: 搜索查询
            workflow_id: 工作流 ID
            threshold: 相关度阈值（0-1）

        Returns:
            (message, relevance_score) 元组列表，按相关度降序
        """
        # 搜索操作直接查询 DB，因为需要全量数据
        return self._db.search(query, workflow_id, threshold)

    def clear(self, workflow_id: str) -> None:
        """
        清空记忆（DB + Cache）

        Args:
            workflow_id: 工作流 ID
        """
        self._db.clear(workflow_id)
        self._cache.invalidate(workflow_id)
        logger.info(f"Cleared memory for workflow {workflow_id}")

    def get_metrics(self) -> MemoryMetrics:
        """
        获取性能指标

        Returns:
            MemoryMetrics 实例，包含：
            - cache_hit_rate: 缓存命中率
            - fallback_count: 回溯次数
            - compression_ratio: 平均压缩比
            - avg_fallback_time_ms: 平均回溯耗时
        """
        cache_stats = self._cache.get_stats()

        avg_fallback_time = (
            sum(self._fallback_times) / len(self._fallback_times) if self._fallback_times else 0.0
        )

        avg_compression_ratio = (
            sum(self._compression_ratios) / len(self._compression_ratios)
            if self._compression_ratios
            else 1.0
        )

        return MemoryMetrics(
            cache_hit_rate=cache_stats["hit_rate"],
            fallback_count=len(self._fallback_times),
            compression_ratio=avg_compression_ratio,
            avg_fallback_time_ms=avg_fallback_time,
        )

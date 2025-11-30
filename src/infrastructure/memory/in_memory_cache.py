"""
In-Memory Cache with TTL and LRU

基于内存的缓存实现，提供：
- TTL（Time-To-Live）过期机制
- LRU（Least Recently Used）淘汰策略
- 性能监控指标

Author: Claude Code
Date: 2025-11-30
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.domain.entities.chat_message import ChatMessage


@dataclass
class CacheEntry:
    """
    缓存条目

    Attributes:
        messages: 缓存的消息列表
        last_access: 最后访问时间（UTC）
        is_valid: 有效性标记（False 表示被主动失效）
    """

    messages: list[ChatMessage]
    last_access: datetime
    is_valid: bool = True


class InMemoryCache:
    """
    基于内存的 TTL + LRU 缓存

    Features:
        - TTL 自动过期（默认 15 分钟）
        - LRU 淘汰策略（默认最多 1000 个 workflow）
        - 消息数量限制（默认每个 workflow 最多 50 条）
        - 命中率统计

    Implements:
        MemoryCache Protocol

    Example:
        >>> cache = InMemoryCache(ttl_seconds=900, max_workflows=1000)
        >>> messages = [ChatMessage.create("wf_123", "Hello", is_user=True)]
        >>> cache.put("wf_123", messages)
        >>> cached = cache.get("wf_123")
        >>> if cached is None:
        ...     # Cache miss, need to fallback to database
        ...     pass
    """

    def __init__(
        self,
        ttl_seconds: int = 900,  # 15 分钟
        max_workflows: int = 1000,
        max_messages_per_workflow: int = 50,
    ):
        """
        初始化缓存

        Args:
            ttl_seconds: TTL 时长（秒），默认 900（15分钟）
            max_workflows: 最大缓存 workflow 数量，默认 1000
            max_messages_per_workflow: 每个 workflow 最多缓存消息数，默认 50
        """
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_workflows = max_workflows
        self._max_messages = max_messages_per_workflow
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # 监控指标
        self._hits = 0
        self._misses = 0

    def get(self, workflow_id: str) -> list[ChatMessage] | None:
        """
        获取缓存的消息列表

        执行逻辑：
        1. 检查缓存是否存在
        2. 检查 TTL 是否过期
        3. 检查有效性标记
        4. 更新访问时间 + LRU 排序
        5. 返回消息副本

        Args:
            workflow_id: 工作流 ID

        Returns:
            - list[ChatMessage]: 缓存命中
            - None: 缓存未命中/过期/失效
        """
        if workflow_id not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[workflow_id]

        # 检查 TTL
        if datetime.utcnow() - entry.last_access > self._ttl:
            self._misses += 1
            del self._cache[workflow_id]
            return None

        # 检查有效性标记
        if not entry.is_valid:
            self._misses += 1
            return None

        # 命中：更新访问时间 + LRU 移动到末尾
        entry.last_access = datetime.utcnow()
        self._cache.move_to_end(workflow_id)
        self._hits += 1

        # 返回副本（避免外部修改）
        return entry.messages.copy()

    def put(self, workflow_id: str, messages: list[ChatMessage]) -> None:
        """
        更新缓存

        执行逻辑：
        1. 限制消息数量（取最后 N 条）
        2. 创建/更新缓存条目
        3. 移动到 LRU 末尾
        4. 检查容量限制，必要时淘汰最旧的

        Args:
            workflow_id: 工作流 ID
            messages: 要缓存的消息列表
        """
        # 限制消息数量
        trimmed_messages = messages[-self._max_messages :]

        # 更新或插入
        self._cache[workflow_id] = CacheEntry(
            messages=trimmed_messages, last_access=datetime.utcnow()
        )
        self._cache.move_to_end(workflow_id)

        # LRU 淘汰
        while len(self._cache) > self._max_workflows:
            self._cache.popitem(last=False)  # 移除最旧的

    def invalidate(self, workflow_id: str) -> None:
        """
        主动失效指定 workflow 的缓存

        标记为失效而不是删除，触发下次读取时回溯到数据库。
        操作幂等（重复调用不报错）。

        Args:
            workflow_id: 工作流 ID
        """
        if workflow_id in self._cache:
            self._cache[workflow_id].is_valid = False

    def is_valid(self, workflow_id: str) -> bool:
        """
        检查缓存有效性

        Args:
            workflow_id: 工作流 ID

        Returns:
            - True: 缓存存在且未过期且有效
            - False: 缓存不存在/已过期/已失效
        """
        if workflow_id not in self._cache:
            return False

        entry = self._cache[workflow_id]

        # 检查 TTL
        if datetime.utcnow() - entry.last_access > self._ttl:
            return False

        # 检查有效性标记
        return entry.is_valid

    def get_stats(self) -> dict:
        """
        获取缓存统计指标

        Returns:
            包含以下字段的字典：
            - hits: 命中次数
            - misses: 未命中次数
            - hit_rate: 命中率（0-1）
            - cached_workflows: 当前缓存的 workflow 数量
            - ttl_seconds: TTL 时长（秒）
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "cached_workflows": len(self._cache),
            "ttl_seconds": self._ttl.total_seconds(),
        }

"""
Memory Cache Protocol

定义缓存层接口抽象，支持 TTL 和失效机制。
符合 DDD 原则：Domain 层纯接口，无框架依赖。

Author: Claude Code
Date: 2025-11-30
"""

from typing import Protocol

from src.domain.entities.chat_message import ChatMessage


class MemoryCache(Protocol):
    """
    缓存接口抽象

    定义了缓存系统的核心操作契约，支持：
    - TTL（Time-To-Live）过期机制
    - 主动失效（Invalidation）
    - 有效性检查

    设计原则：
    1. 纯 Python Protocol，无框架依赖
    2. 返回 None 表示缓存未命中/过期
    3. 失效操作幂等（可重复调用）
    """

    def get(self, workflow_id: str) -> list[ChatMessage] | None:
        """
        获取缓存的消息列表

        Args:
            workflow_id: 工作流 ID

        Returns:
            - list[ChatMessage]: 缓存命中且有效
            - None: 缓存未命中或已过期

        Note:
            返回 None 会触发回溯到数据库的逻辑

        Examples:
            >>> cached = cache.get("wf_123")
            >>> if cached is None:
            ...     # 缓存未命中，需要从 DB 加载
            ...     messages = db.load_recent("wf_123")
        """
        ...

    def put(self, workflow_id: str, messages: list[ChatMessage]) -> None:
        """
        更新缓存

        Args:
            workflow_id: 工作流 ID
            messages: 要缓存的消息列表

        Note:
            - 自动更新 last_access_time
            - 超过容量限制时触发 LRU 淘汰

        Examples:
            >>> messages = [msg1, msg2, msg3]
            >>> cache.put("wf_123", messages)
        """
        ...

    def invalidate(self, workflow_id: str) -> None:
        """
        主动失效指定 workflow 的缓存

        Args:
            workflow_id: 工作流 ID

        Note:
            - 操作幂等（重复调用不报错）
            - 标记为失效，触发下次读取时回溯

        Use Cases:
            - Cache 写入失败时标记失效
            - 数据更新后主动刷新缓存
            - 手动触发缓存清理

        Examples:
            >>> try:
            ...     cache.put("wf_123", messages)
            ... except Exception:
            ...     cache.invalidate("wf_123")  # 写入失败，标记失效
        """
        ...

    def is_valid(self, workflow_id: str) -> bool:
        """
        检查缓存有效性

        Args:
            workflow_id: 工作流 ID

        Returns:
            - True: 缓存存在且未过期
            - False: 缓存不存在/已过期/已失效

        Examples:
            >>> if cache.is_valid("wf_123"):
            ...     messages = cache.get("wf_123")
            ... else:
            ...     # 需要回溯到数据库
            ...     messages = db.load_recent("wf_123")
        """
        ...

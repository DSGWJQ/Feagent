"""
Memory Provider Protocol

定义统一的 Memory 接口抽象，供不同存储实现使用。
符合 DDD 原则：Domain 层纯接口，无框架依赖。

Author: Claude Code
Date: 2025-11-30
"""

from typing import Protocol

from src.domain.entities.chat_message import ChatMessage


class MemoryProvider(Protocol):
    """
    Memory 统一接口抽象

    定义了记忆系统的核心操作契约，支持多种后端实现：
    - DatabaseMemoryStore（持久化存储）
    - InMemoryCache（缓存层）
    - CompositeMemory（组合模式）

    设计原则：
    1. 纯 Python Protocol，无框架依赖
    2. 方法签名清晰，职责单一
    3. 支持结构化子类型检查
    """

    def append(self, message: ChatMessage) -> None:
        """
        追加消息到记忆中

        Args:
            message: 要追加的聊天消息实体

        Raises:
            DomainError: 当消息无效时
            InfrastructureError: 当存储操作失败时

        Examples:
            >>> message = ChatMessage.create(
            ...     workflow_id="wf_123",
            ...     content="Hello",
            ...     is_user=True
            ... )
            >>> provider.append(message)
        """
        ...

    def load_recent(self, workflow_id: str, last_n: int = 10) -> list[ChatMessage]:
        """
        加载最近 N 条消息

        Args:
            workflow_id: 工作流 ID
            last_n: 要加载的消息数量（默认 10）

        Returns:
            按时间顺序排列的消息列表（从旧到新）

        Examples:
            >>> messages = provider.load_recent("wf_123", last_n=5)
            >>> len(messages) <= 5
            True
        """
        ...

    def search(
        self, query: str, workflow_id: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """
        搜索相关消息

        Args:
            query: 搜索查询字符串
            workflow_id: 工作流 ID（隔离不同会话）
            threshold: 相关度阈值（0-1，默认 0.5）

        Returns:
            (message, relevance_score) 元组列表，按相关度降序排列

        Examples:
            >>> results = provider.search("如何创建节点", "wf_123", threshold=0.7)
            >>> for message, score in results:
            ...     print(f"{message.content}: {score:.2f}")
        """
        ...

    def clear(self, workflow_id: str) -> None:
        """
        清空指定 workflow 的所有记忆

        Args:
            workflow_id: 工作流 ID

        Warning:
            此操作不可逆，请谨慎使用

        Examples:
            >>> provider.clear("wf_123")
        """
        ...

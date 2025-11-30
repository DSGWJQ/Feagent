"""
Database Memory Store

数据库持久化存储适配器，实现 MemoryProvider 接口。
包装现有的 ChatMessageRepository，提供统一的内存访问接口。

Author: Claude Code
Date: 2025-11-30
"""

import logging

from src.domain.entities.chat_message import ChatMessage
from src.domain.ports.chat_message_repository import ChatMessageRepository

logger = logging.getLogger(__name__)


class DatabaseWriteError(Exception):
    """数据库写入异常"""

    pass


class DatabaseMemoryStore:
    """
    数据库持久化存储

    作为 ChatMessageRepository 的适配器，提供：
    - 统一的异常处理
    - 日志记录
    - 数据加载策略（多取一些用于后续压缩）

    Implements:
        MemoryProvider Protocol

    Example:
        >>> repository = SQLAlchemyChatMessageRepository(session)
        >>> store = DatabaseMemoryStore(repository)
        >>> message = ChatMessage.create("wf_123", "Hello", is_user=True)
        >>> store.append(message)
    """

    def __init__(self, repository: ChatMessageRepository):
        """
        初始化数据库存储

        Args:
            repository: ChatMessage 仓储实现
        """
        self._repository = repository

    def append(self, message: ChatMessage) -> None:
        """
        追加消息到数据库

        Args:
            message: 要保存的消息实体

        Raises:
            DatabaseWriteError: 数据库写入失败时
        """
        try:
            self._repository.save(message)
            logger.debug(f"Message {message.id} saved to database")
        except Exception as e:
            error_msg = f"Failed to save message {message.id}: {e}"
            logger.error(error_msg)
            raise DatabaseWriteError(error_msg) from e

    def load_recent(self, workflow_id: str, last_n: int = 10) -> list[ChatMessage]:
        """
        从数据库加载最近的消息

        策略：请求 2 倍数量，为后续压缩提供更多选择

        Args:
            workflow_id: 工作流 ID
            last_n: 需要的消息数量（默认 10）

        Returns:
            最近 N 条消息列表（按时间升序）
        """
        # 请求 2 倍数量，用于后续压缩
        limit = last_n * 2

        messages = self._repository.find_by_workflow_id(workflow_id=workflow_id, limit=limit)

        # 返回最近 N 条
        return messages[-last_n:] if messages else []

    def search(
        self, query: str, workflow_id: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """
        搜索相关消息

        Args:
            query: 搜索查询
            workflow_id: 工作流 ID
            threshold: 相关度阈值（0-1）

        Returns:
            (message, relevance_score) 元组列表，按相关度降序
        """
        return self._repository.search(workflow_id, query, threshold)

    def clear(self, workflow_id: str) -> None:
        """
        清空指定 workflow 的所有消息

        Args:
            workflow_id: 工作流 ID
        """
        self._repository.delete_by_workflow_id(workflow_id)
        logger.info(f"Cleared all messages for workflow {workflow_id}")

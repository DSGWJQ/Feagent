"""Memory Service Port

定义内存服务的端口协议（Protocol），供接口层依赖注入使用。
遵循 Ports and Adapters 架构模式，实现 Domain 层与 Infrastructure 层的解耦。

Author: Claude Code
Date: 2025-12-17
"""

from typing import Any, Protocol

from src.domain.entities.chat_message import ChatMessage


class MemoryServicePort(Protocol):
    """内存服务端口协议

    定义内存服务必须实现的接口方法。
    实现类: CompositeMemoryService (Application Layer)

    架构说明:
        Interface Layer (dependencies) → MemoryServicePort (Domain Port)
                                        ↑
                        CompositeMemoryService (Application Layer)
    """

    def append(self, message: ChatMessage) -> None:
        """追加消息到内存

        Args:
            message: 要追加的聊天消息

        Raises:
            Exception: 存储写入失败时
        """
        ...

    def load_recent(self, workflow_id: str, last_n: int = 10) -> list[ChatMessage]:
        """加载最近的消息

        Args:
            workflow_id: 工作流 ID
            last_n: 需要的消息数量（默认 10）

        Returns:
            最近 N 条消息列表（按时间升序）
        """
        ...

    def search(
        self, query: str, workflow_id: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """搜索相关消息

        Args:
            query: 搜索查询
            workflow_id: 工作流 ID
            threshold: 相关度阈值（0-1）

        Returns:
            (message, relevance_score) 元组列表，按相关度降序
        """
        ...

    def clear(self, workflow_id: str) -> None:
        """清空记忆

        Args:
            workflow_id: 工作流 ID
        """
        ...

    def get_metrics(self) -> Any:
        """获取性能指标

        Returns:
            MemoryMetrics dataclass 或兼容的对象
        """
        ...

"""Memory Service Adapter

将 CompositeMemoryService 适配到 ChatHistory 接口，
实现向后兼容的同时享受新内存系统的优势。

Author: Claude Code
Date: 2025-11-30
"""

from typing import Any

from src.application.services.composite_memory_service import CompositeMemoryService
from src.domain.entities.chat_message import ChatMessage


class MemoryServiceAdapter:
    """CompositeMemoryService 适配器

    提供与 ChatHistory 兼容的接口，内部使用 CompositeMemoryService。

    优势：
    - 保持现有代码兼容性
    - 享受新内存系统的性能优化（缓存、压缩）
    - 统一内存管理

    Example:
        >>> memory = MemoryServiceAdapter(workflow_id="wf_123", service=composite_service)
        >>> memory.add_message("Hello", is_user=True)
        >>> context = memory.get_context(last_n=10)
    """

    def __init__(self, workflow_id: str, service: CompositeMemoryService):
        """初始化适配器

        Args:
            workflow_id: 工作流 ID
            service: CompositeMemoryService 实例
        """
        self.workflow_id = workflow_id
        self._service = service
        self.max_messages = 1000  # 兼容 ChatHistory 接口

    def add_message(self, content: str, is_user: bool) -> None:
        """添加消息到历史

        Args:
            content: 消息内容
            is_user: 是否来自用户
        """
        message = ChatMessage.create(workflow_id=self.workflow_id, content=content, is_user=is_user)
        self._service.append(message)

    def get_context(self, last_n: int = 10) -> str:
        """获取最近的对话上下文

        Args:
            last_n: 获取最近 n 条消息

        Returns:
            格式化的对话上下文字符串
        """
        messages = self._service.load_recent(self.workflow_id, last_n=last_n)
        context = []
        for msg in messages:
            role = "用户" if msg.is_user else "助手"
            context.append(f"{role}：{msg.content}")

        return "\n".join(context)

    def clear(self) -> None:
        """清空所有消息"""
        self._service.clear(self.workflow_id)

    def export(self) -> list[dict[str, Any]]:
        """导出消息列表

        Returns:
            消息字典列表
        """
        messages = self._service.load_recent(self.workflow_id, last_n=self.max_messages)
        return [
            {
                "id": msg.id,
                "workflow_id": msg.workflow_id,
                "content": msg.content,
                "is_user": msg.is_user,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in messages
        ]

    def search(self, query: str, threshold: float = 0.5) -> list[tuple[ChatMessage, float]]:
        """在消息历史中进行语义搜索

        Args:
            query: 搜索查询词
            threshold: 相关性阈值（0-1）

        Returns:
            [(ChatMessage, relevance_score), ...] 按相关性降序排列
        """
        if not query or not query.strip():
            return []

        return self._service.search(query, self.workflow_id, threshold=threshold)

    def filter_by_relevance(
        self, keyword: str, threshold: float = 0.5, max_results: int | None = None
    ) -> list[ChatMessage]:
        """根据关键词过滤相关的消息

        Args:
            keyword: 关键词
            threshold: 相关性阈值（0-1）
            max_results: 最大返回结果数

        Returns:
            符合条件的消息列表
        """
        search_results = self.search(keyword, threshold=threshold)

        # 提取消息（忽略分数）
        filtered = [msg for msg, score in search_results]

        # 应用最大结果数限制
        if max_results is not None:
            filtered = filtered[:max_results]

        return filtered

    def compress_history(self, max_tokens: int, min_messages: int = 2) -> list[ChatMessage]:
        """压缩历史消息以控制 token 数量

        Args:
            max_tokens: 最大允许的 token 数
            min_messages: 最小保留消息数

        Returns:
            压缩后的消息列表

        Note:
            内部使用 CompositeMemoryService 的智能压缩（TF-IDF），
            与原 ChatHistory 的简单截断策略不同，效果更优。
        """
        # 使用 CompositeMemoryService 的智能压缩
        # 注意：这里调用的是 load_recent，它会自动触发压缩
        # 我们需要先失效缓存，强制回溯 + 压缩
        self._service._cache.invalidate(self.workflow_id)

        # 临时修改 max_tokens 配置
        original_max_tokens = self._service._max_tokens
        self._service._max_tokens = max_tokens

        try:
            # 加载并压缩
            compressed = self._service.load_recent(self.workflow_id, last_n=self.max_messages)
            return compressed
        finally:
            # 恢复原配置
            self._service._max_tokens = original_max_tokens

    def estimate_tokens(self, messages: list[ChatMessage]) -> int:
        """估计消息列表的 token 数量

        Args:
            messages: 消息列表

        Returns:
            估计的 token 数
        """
        total = 0
        for msg in messages:
            total += self._estimate_message_tokens(msg)
        return total

    @staticmethod
    def _estimate_message_tokens(msg: ChatMessage) -> int:
        """估计单条消息的 token 数

        使用启发式方法：中文约1.3字符1个token，英文约4字符1个token

        Args:
            msg: 消息

        Returns:
            估计的 token 数
        """
        content = msg.content

        # 估计中文字符数（CJK 字符）
        import re

        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", content))

        # 估计其他字符
        other_count = len(content) - cjk_count

        # 中文：平均 1.3 字符 = 1 token
        # 英文：平均 4 字符 = 1 token
        tokens = int(cjk_count / 1.3) + int(other_count / 4)

        # 至少计为 1 token
        return max(1, tokens)

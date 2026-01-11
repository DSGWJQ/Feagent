"""记忆压缩处理器 (Memory Compression Handler) - Step 6

业务定义：
- 订阅 ShortTermSaturatedEvent，自动执行上下文压缩
- 冻结会话、执行压缩、回写摘要、解冻会话
- 支持失败回滚和日志记录

设计原则：
- 异步处理，不阻塞主流程
- 原子操作，保证数据一致性
- 可配置的压缩策略
"""

import logging
from typing import TYPE_CHECKING, Any

from src.domain.entities.session_context import SessionContext, ShortTermSaturatedEvent
from src.domain.services.event_bus import EventBus
from src.domain.services.structured_dialogue_summary import StructuredDialogueSummary

if TYPE_CHECKING:
    from src.domain.services.short_term_buffer import ShortTermBuffer

logger = logging.getLogger(__name__)


class BufferCompressor:
    """缓冲区压缩器

    将短期缓冲区内容压缩为结构化摘要。

    职责：
    - 分析对话内容
    - 提取核心目标、关键决策、任务进展等
    - 生成 StructuredDialogueSummary
    """

    async def compress(
        self,
        buffers: list["ShortTermBuffer"],
        existing_summary: str | None = None,
    ) -> StructuredDialogueSummary:
        """压缩缓冲区内容

        参数：
            buffers: 短期缓冲区列表
            existing_summary: 已有的摘要（用于增量压缩）

        返回：
            StructuredDialogueSummary 实例
        """
        # 提取对话内容
        conversation_text = self._extract_conversation(buffers)

        # 分析并生成摘要
        summary = self._analyze_and_summarize(conversation_text, existing_summary)

        return summary

    def _extract_conversation(self, buffers: list["ShortTermBuffer"]) -> str:
        """提取对话文本"""
        lines = []
        for buffer in buffers:
            role = "用户" if buffer.role == "user" else "助手"
            lines.append(f"{role}: {buffer.content}")
        return "\n".join(lines)

    def _analyze_and_summarize(
        self,
        conversation_text: str,
        existing_summary: str | None,
    ) -> StructuredDialogueSummary:
        """分析对话并生成摘要

        这是一个简化实现，实际应用中可以使用 LLM 进行更智能的分析。
        """
        # 提取核心目标（简化：取第一条用户消息的关键词）
        core_goal = self._extract_core_goal(conversation_text, existing_summary)

        # 提取关键决策
        key_decisions = self._extract_key_decisions(conversation_text)

        # 提取任务进展
        task_progress = self._extract_task_progress(conversation_text)

        # 提取待处理项
        pending_items = self._extract_pending_items(conversation_text)

        # 如果有已有摘要，合并
        important_context = []
        if existing_summary:
            important_context.append(f"之前的上下文: {existing_summary[:200]}...")

        return StructuredDialogueSummary(
            session_id="compressed",
            core_goal=core_goal,
            key_decisions=key_decisions,
            context_clues=important_context,
            next_steps=task_progress,
            pending_tasks=pending_items,
        )

    def _extract_core_goal(self, text: str, existing: str | None) -> str:
        """提取核心目标"""
        if existing and "核心目标" in existing:
            # 保留已有目标
            start = existing.find("核心目标")
            end = existing.find("\n", start)
            if end > start:
                return existing[start:end].replace("核心目标】", "").strip()

        # 从对话中提取
        lines = text.split("\n")
        for line in lines:
            if line.startswith("用户:"):
                return line.replace("用户:", "").strip()[:100]

        return "继续当前任务"

    def _extract_key_decisions(self, text: str) -> list[str]:
        """提取关键决策"""
        decisions = []
        keywords = ["决定", "选择", "使用", "采用", "确定"]

        for line in text.split("\n"):
            for keyword in keywords:
                if keyword in line:
                    decisions.append(line.strip()[:100])
                    break

        return decisions[:5]  # 最多5条

    def _extract_task_progress(self, text: str) -> list[str]:
        """提取任务进展"""
        progress = []
        keywords = ["完成", "进行中", "开始", "结束", "成功", "失败"]

        for line in text.split("\n"):
            for keyword in keywords:
                if keyword in line:
                    progress.append(line.strip()[:100])
                    break

        return progress[:5]

    def _extract_pending_items(self, text: str) -> list[str]:
        """提取待处理项"""
        pending = []
        keywords = ["需要", "待", "还要", "接下来", "下一步"]

        for line in text.split("\n"):
            for keyword in keywords:
                if keyword in line:
                    pending.append(line.strip()[:100])
                    break

        return pending[:5]


class MemoryCompressionHandler:
    """记忆压缩处理器

    职责：
    - 订阅 ShortTermSaturatedEvent
    - 执行自动压缩流程
    - 管理会话状态（冻结/解冻）
    - 处理压缩失败的回滚

    使用示例：
        handler = MemoryCompressionHandler(event_bus)
        handler.register()
        handler.register_session(session_context)
    """

    def __init__(
        self,
        event_bus: EventBus,
        keep_recent_turns: int = 2,
        compressor: BufferCompressor | None = None,
    ):
        """初始化处理器

        参数：
            event_bus: 事件总线
            keep_recent_turns: 压缩后保留的最近轮次数
            compressor: 压缩器实例（可选）
        """
        self._event_bus = event_bus
        self._keep_recent_turns = keep_recent_turns
        self._compressor = compressor or BufferCompressor()
        self._sessions: dict[str, SessionContext] = {}

    def register(self) -> None:
        """注册事件处理器"""
        self._event_bus.subscribe(
            ShortTermSaturatedEvent,
            self._handle_saturation_event,  # type: ignore[arg-type]
        )
        logger.info("MemoryCompressionHandler registered for ShortTermSaturatedEvent")

    def unregister(self) -> None:
        """取消注册事件处理器"""
        self._event_bus.unsubscribe(
            ShortTermSaturatedEvent,
            self._handle_saturation_event,  # type: ignore[arg-type]
        )
        logger.info("MemoryCompressionHandler unregistered")

    def register_session(self, session: SessionContext) -> None:
        """注册会话

        参数：
            session: 要管理的会话上下文
        """
        self._sessions[session.session_id] = session
        logger.debug(f"Session registered: {session.session_id}")

    def unregister_session(self, session_id: str) -> None:
        """取消注册会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"Session unregistered: {session_id}")

    async def _handle_saturation_event(self, event: ShortTermSaturatedEvent) -> None:
        """处理饱和事件

        流程：
        1. 获取会话
        2. 创建备份
        3. 冻结会话
        4. 执行压缩
        5. 回写摘要
        6. 解冻会话
        7. 重置饱和状态
        """
        session_id = event.session_id
        session = self._sessions.get(session_id)

        if not session:
            logger.warning(f"Session not found for saturation event: {session_id}")
            return

        logger.info(
            f"Handling saturation event for session {session_id}, "
            f"usage: {event.usage_ratio:.1%}, tokens: {event.total_tokens}/{event.context_limit}"
        )

        # 创建备份
        backup = session.create_backup()

        try:
            # 冻结会话
            session.freeze()
            logger.debug(f"Session {session_id} frozen for compression")

            # 执行压缩
            summary = await self._compressor.compress(
                session.short_term_buffer,
                session.conversation_summary,
            )

            # 回写摘要并清理缓冲区
            session.compress_buffer_with_summary(summary, self._keep_recent_turns)

            logger.info(
                f"Compression completed for session {session_id}, "
                f"kept {len(session.short_term_buffer)} recent turns"
            )

        except Exception as e:
            logger.error(f"Compression failed for session {session_id}: {e}")
            # 回滚
            session.restore_from_backup(backup)
            logger.info(f"Session {session_id} restored from backup")

        finally:
            # 解冻会话
            session.unfreeze()
            # 重置饱和状态
            session.reset_saturation()
            logger.debug(f"Session {session_id} unfrozen")


def get_planning_context(session: SessionContext) -> dict[str, Any]:
    """获取规划上下文

    从会话中提取用于规划的上下文信息，包括压缩摘要。

    参数：
        session: 会话上下文

    返回：
        包含规划所需信息的字典
    """
    current_goal = session.current_goal()
    return {
        "session_id": session.session_id,
        "previous_summary": session.conversation_summary,
        "current_goal": current_goal.description if current_goal else None,
        "token_usage": session.get_token_usage_summary(),
        "recent_turns": [
            {"role": b.role, "content": b.content[:200]}
            for b in session.short_term_buffer[-3:]  # 最近3轮
        ],
    }


# 导出
__all__ = [
    "BufferCompressor",
    "MemoryCompressionHandler",
    "get_planning_context",
]

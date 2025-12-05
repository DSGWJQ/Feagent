"""结构化对话摘要 (StructuredDialogueSummary) - Step 3: 中期记忆蒸馏

业务定义：
- 八段结构摘要，用于压缩对话历史
- 每段代表对话的不同维度
- 支持序列化、反序列化、合并

设计原则：
- 结构化：八段固定结构，便于理解和处理
- 可压缩：大幅减少 token 使用
- 可恢复：保留关键信息，支持上下文恢复
- 可合并：支持多个摘要合并

八段结构：
1. 核心目标 (core_goal): 对话的主要目标
2. 关键决策 (key_decisions): 已做出的重要决策
3. 重要事实 (important_facts): 需要记住的关键事实
4. 待办事项 (pending_tasks): 未完成的任务
5. 用户偏好 (user_preferences): 用户的偏好和习惯
6. 上下文线索 (context_clues): 有助于理解的背景信息
7. 未解问题 (unresolved_issues): 尚未解决的问题
8. 下一步计划 (next_steps): 接下来要做的事情
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class SummarySection(str, Enum):
    """摘要段落枚举"""

    CORE_GOAL = "core_goal"
    KEY_DECISIONS = "key_decisions"
    IMPORTANT_FACTS = "important_facts"
    PENDING_TASKS = "pending_tasks"
    USER_PREFERENCES = "user_preferences"
    CONTEXT_CLUES = "context_clues"
    UNRESOLVED_ISSUES = "unresolved_issues"
    NEXT_STEPS = "next_steps"


# 段落描述（中文）
SECTION_DESCRIPTIONS = {
    SummarySection.CORE_GOAL: "核心目标：对话的主要目标和意图",
    SummarySection.KEY_DECISIONS: "关键决策：已做出的重要决策和选择",
    SummarySection.IMPORTANT_FACTS: "重要事实：需要记住的关键事实和数据",
    SummarySection.PENDING_TASKS: "待办事项：未完成的任务和行动项",
    SummarySection.USER_PREFERENCES: "用户偏好：用户的偏好、习惯和要求",
    SummarySection.CONTEXT_CLUES: "上下文线索：有助于理解对话的背景信息",
    SummarySection.UNRESOLVED_ISSUES: "未解问题：尚未解决的问题和疑问",
    SummarySection.NEXT_STEPS: "下一步计划：接下来要做的事情和行动",
}


def get_section_description(section: SummarySection) -> str:
    """获取段落描述

    参数：
        section: 段落枚举

    返回：
        段落的中文描述
    """
    return SECTION_DESCRIPTIONS.get(section, "")


@dataclass
class StructuredDialogueSummary:
    """结构化对话摘要（八段结构）

    属性：
        session_id: 会话ID
        summary_id: 摘要唯一标识
        created_at: 创建时间

        # 八段结构
        core_goal: 核心目标
        key_decisions: 关键决策列表
        important_facts: 重要事实列表
        pending_tasks: 待办事项列表
        user_preferences: 用户偏好列表
        context_clues: 上下文线索列表
        unresolved_issues: 未解问题列表
        next_steps: 下一步计划列表

        # 压缩元数据
        compressed_from_turns: 压缩自多少轮对话
        original_token_count: 原始 token 数
        summary_token_count: 摘要 token 数
    """

    session_id: str
    core_goal: str = ""
    key_decisions: list[str] = field(default_factory=list)
    important_facts: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    user_preferences: list[str] = field(default_factory=list)
    context_clues: list[str] = field(default_factory=list)
    unresolved_issues: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    # 元数据
    summary_id: str = field(default_factory=lambda: f"summary_{uuid4().hex[:12]}")
    created_at: datetime = field(default_factory=datetime.now)
    compressed_from_turns: int = 0
    original_token_count: int = 0
    summary_token_count: int = 0

    def get_compression_ratio(self) -> float:
        """获取压缩率

        返回：
            压缩率（summary_token_count / original_token_count）
        """
        if self.original_token_count == 0:
            return 0.0
        return self.summary_token_count / self.original_token_count

    def is_empty(self) -> bool:
        """判断摘要是否为空

        返回：
            如果所有段落都为空则返回 True
        """
        return (
            not self.core_goal
            and not self.key_decisions
            and not self.important_facts
            and not self.pending_tasks
            and not self.user_preferences
            and not self.context_clues
            and not self.unresolved_issues
            and not self.next_steps
        )

    def get_all_sections(self) -> dict[str, Any]:
        """获取所有段落

        返回：
            包含所有段落的字典
        """
        return {
            "core_goal": self.core_goal,
            "key_decisions": self.key_decisions,
            "important_facts": self.important_facts,
            "pending_tasks": self.pending_tasks,
            "user_preferences": self.user_preferences,
            "context_clues": self.context_clues,
            "unresolved_issues": self.unresolved_issues,
            "next_steps": self.next_steps,
        }

    def merge(self, other: "StructuredDialogueSummary") -> "StructuredDialogueSummary":
        """合并两个摘要

        参数：
            other: 另一个摘要

        返回：
            合并后的新摘要
        """
        return StructuredDialogueSummary(
            session_id=self.session_id,
            # core_goal 使用最新的
            core_goal=other.core_goal if other.core_goal else self.core_goal,
            # 列表合并（去重）
            key_decisions=list(set(self.key_decisions + other.key_decisions)),
            important_facts=list(set(self.important_facts + other.important_facts)),
            pending_tasks=list(set(self.pending_tasks + other.pending_tasks)),
            user_preferences=list(set(self.user_preferences + other.user_preferences)),
            context_clues=list(set(self.context_clues + other.context_clues)),
            unresolved_issues=list(set(self.unresolved_issues + other.unresolved_issues)),
            next_steps=list(set(self.next_steps + other.next_steps)),
            # 元数据累加
            compressed_from_turns=self.compressed_from_turns + other.compressed_from_turns,
            original_token_count=self.original_token_count + other.original_token_count,
            summary_token_count=self.summary_token_count + other.summary_token_count,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）

        返回：
            包含所有字段的字典
        """
        return {
            "session_id": self.session_id,
            "summary_id": self.summary_id,
            "created_at": self.created_at.isoformat(),
            "core_goal": self.core_goal,
            "key_decisions": self.key_decisions.copy(),
            "important_facts": self.important_facts.copy(),
            "pending_tasks": self.pending_tasks.copy(),
            "user_preferences": self.user_preferences.copy(),
            "context_clues": self.context_clues.copy(),
            "unresolved_issues": self.unresolved_issues.copy(),
            "next_steps": self.next_steps.copy(),
            "compressed_from_turns": self.compressed_from_turns,
            "original_token_count": self.original_token_count,
            "summary_token_count": self.summary_token_count,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "StructuredDialogueSummary":
        """从字典重建摘要（用于反序列化）

        参数：
            data: 包含摘要数据的字典

        返回：
            StructuredDialogueSummary 实例
        """
        # 解析时间戳
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return StructuredDialogueSummary(
            session_id=data.get("session_id", ""),
            summary_id=data.get("summary_id", f"summary_{uuid4().hex[:12]}"),
            created_at=created_at,
            core_goal=data.get("core_goal", ""),
            key_decisions=data.get("key_decisions", []),
            important_facts=data.get("important_facts", []),
            pending_tasks=data.get("pending_tasks", []),
            user_preferences=data.get("user_preferences", []),
            context_clues=data.get("context_clues", []),
            unresolved_issues=data.get("unresolved_issues", []),
            next_steps=data.get("next_steps", []),
            compressed_from_turns=data.get("compressed_from_turns", 0),
            original_token_count=data.get("original_token_count", 0),
            summary_token_count=data.get("summary_token_count", 0),
        )

    def to_text(self) -> str:
        """转换为文本格式（用于 LLM 上下文）

        返回：
            格式化的文本摘要
        """
        lines = []

        if self.core_goal:
            lines.append(f"【核心目标】{self.core_goal}")

        if self.key_decisions:
            lines.append("【关键决策】")
            for decision in self.key_decisions:
                lines.append(f"  - {decision}")

        if self.important_facts:
            lines.append("【重要事实】")
            for fact in self.important_facts:
                lines.append(f"  - {fact}")

        if self.pending_tasks:
            lines.append("【待办事项】")
            for task in self.pending_tasks:
                lines.append(f"  - {task}")

        if self.user_preferences:
            lines.append("【用户偏好】")
            for pref in self.user_preferences:
                lines.append(f"  - {pref}")

        if self.context_clues:
            lines.append("【上下文线索】")
            for clue in self.context_clues:
                lines.append(f"  - {clue}")

        if self.unresolved_issues:
            lines.append("【未解问题】")
            for issue in self.unresolved_issues:
                lines.append(f"  - {issue}")

        if self.next_steps:
            lines.append("【下一步计划】")
            for step in self.next_steps:
                lines.append(f"  - {step}")

        return "\n".join(lines)


# 导出
__all__ = [
    "StructuredDialogueSummary",
    "SummarySection",
    "get_section_description",
]

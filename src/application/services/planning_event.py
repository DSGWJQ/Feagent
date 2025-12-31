"""PlanningEvent - 规划通道 SSE 事件契约

Step 4: SSE 契约统一
- 规划（planning）相关 SSE 事件统一输出 schema
- 所有事件强制包含 type + channel 字段
- 事件类型收敛: thinking | tool_call | tool_result | patch | final | error

设计原则:
- 与 ExecutionEvent 保持一致的结构
- 使用 frozen dataclass 确保不可变
- to_sse_dict() 输出符合 SSE 契约
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

# 预定义的事件类型常量（移到顶部供 __post_init__ 使用）
PLANNING_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "thinking",  # AI 思考过程
        "tool_call",  # 工具调用
        "tool_result",  # 工具执行结果
        "patch",  # 工作流修改预览
        "research_plan",  # 研究计划预览
        "final",  # 最终结果
        "error",  # 错误
    }
)


@dataclass(frozen=True)
class PlanningEvent:
    """类型化的规划事件，符合 Step 4 SSE 契约

    必需字段:
        type: 事件类型 (thinking|tool_call|tool_result|patch|final|error)
        channel: 事件通道，固定为 "planning"

    可选字段:
        content: 事件内容（文本消息）
        sequence: 事件序号（用于排序）
        timestamp: ISO 格式时间戳
        metadata: 扩展元数据
        is_final: 是否为结束事件
    """

    type: str
    channel: str = "planning"
    content: str = ""
    sequence: int | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_final: bool = False

    def __post_init__(self) -> None:
        """验证契约约束

        Raises:
            ValueError: channel 不是 "planning" 或 type 不在允许集合内
        """
        if self.channel != "planning":
            raise ValueError(f'PlanningEvent.channel must be "planning", got "{self.channel}"')
        if self.type not in PLANNING_EVENT_TYPES:
            raise ValueError(
                f"Invalid PlanningEvent.type: {self.type}. "
                f"Allowed: {sorted(PLANNING_EVENT_TYPES)}"
            )

    def to_sse_dict(self) -> dict[str, Any]:
        """转换为 SSE 兼容的 dict 格式

        返回:
            包含 type 和 channel 的 dict，仅包含非空字段
        """
        event: dict[str, Any] = {"type": self.type, "channel": self.channel}

        if self.content:
            event["content"] = self.content
        if self.sequence is not None:
            event["sequence"] = self.sequence
        if self.timestamp is not None:
            event["timestamp"] = self.timestamp
        if self.metadata:
            event["metadata"] = self.metadata
        if self.is_final:
            event["is_final"] = True

        return event


__all__ = ["PlanningEvent", "PLANNING_EVENT_TYPES"]

"""ConversationAgent events module.

This module contains event types that were extracted from conversation_agent.py
to break circular dependencies (P1-6 Phase 3/4).

By placing these events in a separate module, both conversation_agent.py
and its mixins (workflow/recovery) can import them without creating
circular dependency chains.

Design principles:
- Events inherit from domain Event base class
- Keep event payloads simple and serializable
- Use TYPE_CHECKING imports to avoid runtime circular dependencies
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.domain.services.event_bus import Event

if TYPE_CHECKING:
    from src.domain.agents.conversation_agent import IntentType

__all__ = [
    "DecisionMadeEvent",
    "SimpleMessageEvent",
    "IntentClassificationResult",
]


@dataclass
class DecisionMadeEvent(Event):
    """决策事件

    当对话Agent做出决策时发布此事件。
    协调者Agent订阅此事件进行验证和记录。

    属性：
    - decision_type: 决策类型（字符串形式）
    - decision_id: 决策唯一标识
    - payload: 决策负载数据
    - confidence: 决策置信度（0-1之间）

    订阅者：
    - CoordinatorAgent: 验证决策合法性、记录决策历史

    示例：
        event = DecisionMadeEvent(
            source="conversation_agent",
            decision_type="create_node",
            decision_id="uuid-xxx",
            payload={"node_type": "python"},
            confidence=0.95
        )
        await event_bus.publish(event)
    """

    decision_type: str = ""
    decision_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class SimpleMessageEvent(Event):
    """简单消息事件 (Phase 15)

    当对话不需要 ReAct 循环（普通对话、工作流查询）时发布此事件。
    协调者Agent订阅此事件进行统计记录。

    这个事件用于跟踪那些绕过ReAct循环的"快速回复"场景，
    便于统计分析和性能监控。

    属性：
    - user_input: 用户输入内容
    - response: 生成的回复内容
    - intent: 意图类型（字符串形式）
    - confidence: 意图分类置信度（0-1之间）
    - session_id: 会话ID

    订阅者：
    - CoordinatorAgent: 记录对话统计、分析意图分布

    示例：
        event = SimpleMessageEvent(
            source="conversation_agent",
            user_input="你好",
            response="您好！有什么可以帮助您的吗？",
            intent="conversation",
            confidence=0.98,
            session_id="session-xxx"
        )
        await event_bus.publish(event)
    """

    user_input: str = ""
    response: str = ""
    intent: str = ""
    confidence: float = 1.0
    session_id: str = ""


@dataclass
class IntentClassificationResult:
    """意图分类结果 (Phase 14)

    封装意图分类器的输出结果。

    属性：
    - intent: 识别的意图类型（IntentType枚举）
    - confidence: 置信度（0-1之间）
    - reasoning: 分类理由（供调试和审计使用）
    - extracted_entities: 从输入中提取的实体（字典形式）

    使用场景：
    - 意图分类阶段判断是否需要ReAct循环
    - 根据置信度阈值决定是否回退到ReAct循环
    - 提供分类理由供调试和优化使用

    示例：
        result = IntentClassificationResult(
            intent=IntentType.CONVERSATION,
            confidence=0.95,
            reasoning="用户问候，不涉及工作流操作",
            extracted_entities={}
        )
    """

    intent: IntentType
    confidence: float = 1.0
    reasoning: str = ""
    extracted_entities: dict[str, Any] = field(default_factory=dict)

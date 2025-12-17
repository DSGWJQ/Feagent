"""Agent Dependencies

Agent系统的依赖注入配置，提供：
- ConversationAgent 依赖注入
- WorkflowAgent 依赖注入
- CoordinatorAgent 依赖注入（可选）

Author: Claude Code
Date: 2025-12-17 (P1-2 Fix: Agent Collaboration Integration)
"""

from typing import Annotated

from fastapi import Depends

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_config import ConversationAgentConfig, StreamingConfig
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.event_bus import EventBus

# 全局单例
_event_bus: EventBus | None = None
_conversation_agent: ConversationAgent | None = None
_workflow_agent: WorkflowAgent | None = None


def get_event_bus() -> EventBus:
    """获取全局EventBus单例

    Returns:
        EventBus 实例
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def get_conversation_agent(
    event_bus: EventBus = Depends(get_event_bus),
) -> ConversationAgent:
    """获取ConversationAgent实例

    Args:
        event_bus: 事件总线（通过依赖注入）

    Returns:
        ConversationAgent 实例

    架构说明:
        Interface Layer → ConversationAgent (Domain Layer)
                         ↑
                      EventBus (Domain Service)

    Example:
        >>> from fastapi import Depends
        >>> @app.post("/chat")
        >>> async def chat(
        ...     agent: ConversationAgent = Depends(get_conversation_agent)
        ... ):
        ...     result = await agent.process_message(...)
        ...     return result
    """
    global _conversation_agent

    if _conversation_agent is None:
        # 创建配置（使用简化配置）
        config = ConversationAgentConfig(
            streaming=StreamingConfig(
                enable_save_request_channel=True,
            ),
            event_bus=event_bus,
        )

        # 创建Agent实例（使用config参数）
        _conversation_agent = ConversationAgent(config=config)

    return _conversation_agent


def get_workflow_agent(
    event_bus: EventBus = Depends(get_event_bus),
) -> WorkflowAgent:
    """获取WorkflowAgent实例

    Args:
        event_bus: 事件总线（通过依赖注入）

    Returns:
        WorkflowAgent 实例

    架构说明:
        Interface Layer → WorkflowAgent (Domain Layer)
                         ↑
                      EventBus (Domain Service)

    Example:
        >>> from fastapi import Depends
        >>> @app.post("/workflow/execute")
        >>> async def execute(
        ...     agent: WorkflowAgent = Depends(get_workflow_agent)
        ... ):
        ...     result = await agent.execute_workflow(...)
        ...     return result
    """
    global _workflow_agent

    if _workflow_agent is None:
        # 创建Agent实例（WorkflowAgent接受event_bus作为参数）
        _workflow_agent = WorkflowAgent(event_bus=event_bus)

    return _workflow_agent


# Type aliases for FastAPI dependency injection
ConversationAgentDep = Annotated[ConversationAgent, Depends(get_conversation_agent)]
WorkflowAgentDep = Annotated[WorkflowAgent, Depends(get_workflow_agent)]
EventBusDep = Annotated[EventBus, Depends(get_event_bus)]

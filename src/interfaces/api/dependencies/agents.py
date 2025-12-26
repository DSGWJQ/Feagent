"""Agent Dependencies

Agent系统的依赖注入配置，提供：
- ConversationAgent 依赖注入
- WorkflowAgent 依赖注入
- CoordinatorAgent 依赖注入（可选）

Author: Claude Code
Date: 2025-12-17 (P1-2 Fix: Agent Collaboration Integration)
Updated: 2025-12-17 (P1-1 Fix: ModelMetadataPort Injection)
"""

from typing import Annotated

from fastapi import Depends, Request

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.conversation_agent_config import ConversationAgentConfig, StreamingConfig
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.event_bus import EventBus
from src.infrastructure.adapters.model_metadata_adapter import create_model_metadata_adapter

# 全局单例（Agent 实例缓存）
_conversation_agent: ConversationAgent | None = None
_workflow_agent: WorkflowAgent | None = None
_fallback_event_bus: EventBus | None = None


def _get_fallback_event_bus() -> EventBus:
    """内部 fallback：供非 Request 上下文使用"""
    global _fallback_event_bus
    if _fallback_event_bus is None:
        _fallback_event_bus = EventBus()
    return _fallback_event_bus


def set_event_bus(event_bus: EventBus) -> None:
    """设置全局 EventBus 单例（由 main.py lifespan 调用）

    Args:
        event_bus: 应用级 EventBus 实例
    """
    global _fallback_event_bus
    _fallback_event_bus = event_bus


def get_event_bus(request: Request) -> EventBus:
    """获取 EventBus 单例（优先从 FastAPI app.state 获取）

    Args:
        request: FastAPI Request 对象（通过 Depends 自动注入）

    Returns:
        EventBus 实例
    """
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        # Fallback：如果 app.state 未初始化，使用内部单例
        bus = _get_fallback_event_bus()
        request.app.state.event_bus = bus
    return bus


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
                      ModelMetadataPort (P1-1)

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
        # P1-1: 创建模型元数据适配器（Infrastructure → Domain Port）
        model_metadata_port = create_model_metadata_adapter()

        # 创建配置（使用简化配置）
        config = ConversationAgentConfig(
            streaming=StreamingConfig(
                enable_save_request_channel=True,
            ),
            event_bus=event_bus,
            model_metadata_port=model_metadata_port,  # P1-1: 注入模型元数据端口
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

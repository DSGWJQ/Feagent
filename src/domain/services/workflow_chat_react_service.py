"""工作流聊天 ReAct 编排服务

职责：
1. 整合 WorkflowChatService（消息→修改指令）
2. 整合 ReActOrchestrator（编排循环）
3. 流式产生 ReAct 步骤事件
4. 处理实时推理过程

设计原则：
- 使用事件回调捕获 ReAct 循环的实时进展
- 流式产生事件供前端实时显示
- 保留完整的状态追踪
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.react_orchestrator import ReActEvent, ReActOrchestratorPort


class WorkflowChatReActService:
    """工作流对话 ReAct 编排服务

    整合 ReAct 编排引擎与工作流修改服务，提供流式处理能力。

    工作流：
    1. 创建编排器实例
    2. 注册事件处理器（捕获 ReAct 循环事件）
    3. 运行编排器（完整 ReAct 循环）
    4. 流式产生捕获的事件
    5. 返回最终状态
    """

    def __init__(
        self,
        react_orchestrator: ReActOrchestratorPort,
    ):
        """初始化服务

        参数：
            react_orchestrator: ReAct 编排器端口实现
        """
        self.react_orchestrator = react_orchestrator

    async def process_message_with_react_streaming(
        self,
        workflow: Workflow,
        user_message: str,
        event_granularity: str = "fine",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式处理消息并产生 ReAct 事件

        参数：
            workflow: 要执行的工作流
            user_message: 用户消息（当前阶段未使用，为未来扩展预留）
            event_granularity: 事件粒度 ("fine" | "coarse")

        异步生成：
            dict[str, Any]: 各种类型的事件

        过程：
        1. 产生 processing_started 事件
        2. 运行 ReAct 编排器
        3. 捕获并产生编排器事件
        4. 产生 react_complete 事件（包含最终状态）
        """
        # 1. 产生处理开始事件
        yield {
            "type": "processing_started",
            "timestamp": datetime.now(UTC).isoformat(),
            "workflow_id": workflow.id,
            "user_message": user_message,
        }

        # 2. 捕获 ReAct 事件
        captured_events: list[ReActEvent] = []

        def on_react_event(event: ReActEvent) -> None:
            """捕获 ReAct 编排器的事件"""
            captured_events.append(event)

        # 3. 注册事件处理器
        self.react_orchestrator.on_event(on_react_event)

        # 4. 运行编排器（完整 ReAct 循环）
        try:
            state = self.react_orchestrator.run(workflow)
        except Exception as e:
            yield {
                "type": "react_error",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            return

        # 5. 流式产生捕获的事件
        if event_granularity == "fine":
            # 细粒度：产生所有原始事件
            for event in captured_events:
                yield {
                    "type": "react_event",
                    "event_type": event.event_type,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                }
        elif event_granularity == "coarse":
            # 粗粒度：聚合为 react_step
            current_step = {
                "step_number": 0,
                "thought": "",
                "action": {},
                "observation": "",
                "events": [],
            }

            for event in captured_events:
                if event.event_type == "workflow_started":
                    continue
                elif event.event_type == "reasoning_started":
                    current_step["step_number"] += 1
                elif event.event_type == "reasoning_completed":
                    current_step["thought"] = event.data.get("message", "推理完成")
                elif event.event_type == "action_executed":
                    current_step["action"] = event.data
                elif event.event_type == "observation_completed":
                    current_step["observation"] = event.data.get("action_type", "")
                    # 产生聚合的 react_step
                    yield {
                        "type": "react_step",
                        "step_number": current_step["step_number"],
                        "thought": current_step["thought"],
                        "action": current_step["action"],
                        "observation": current_step["observation"],
                        "timestamp": event.timestamp.isoformat(),
                    }
                    # 重置当前步骤
                    current_step = {
                        "step_number": current_step["step_number"],
                        "thought": "",
                        "action": {},
                        "observation": "",
                        "events": [],
                    }

        # 6. 产生完成事件（包含最终状态）
        yield {
            "type": "react_complete",
            "workflow_id": workflow.id,
            "iterations": state.iteration_count,
            "status": state.loop_status,
            "message_count": len(state.messages),
            "executed_actions_count": len(state.executed_actions),
            "executed_nodes": list(state.executed_nodes.keys()),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_reactor_state(self) -> dict[str, Any]:
        """获取编排器的最终状态

        返回：
            最终状态信息
        """
        final_state = self.react_orchestrator.get_final_state()
        if final_state is None:
            raise DomainError("编排器还未运行，没有最终状态")

        return {
            "workflow_id": final_state.workflow_id,
            "workflow_name": final_state.workflow_name,
            "iteration_count": final_state.iteration_count,
            "loop_status": final_state.loop_status,
            "messages": len(final_state.messages),
            "executed_actions": len(final_state.executed_actions),
            "executed_nodes": list(final_state.executed_nodes.keys()),
        }

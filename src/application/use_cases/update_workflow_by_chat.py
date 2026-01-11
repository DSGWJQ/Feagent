"""UpdateWorkflowByChatUseCase - 对话式修改工作流用例

业务场景：
- 用户通过自然语言对话修改工作流
- AI 理解用户意图并修改工作流
- 返回修改后的工作流和AI回复消息

设计原则：
- Use Case 负责业务流程编排
- 调用 Domain Service 处理核心逻辑
- 调用 Repository 持久化数据
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.ports.workflow_chat_service import WorkflowChatServicePort
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_save_validator import WorkflowSaveValidator


@dataclass
class UpdateWorkflowByChatInput:
    """对话式修改工作流输入

    字段：
    - workflow_id: 工作流 ID
    - user_message: 用户消息
    """

    workflow_id: str
    user_message: str


@dataclass
class UpdateWorkflowByChatOutput:
    """对话式修改工作流输出（增强版）

    字段：
    - workflow: 修改后的工作流
    - ai_message: AI 回复消息
    - intent: 用户意图类型（add_node、delete_node、add_edge等）
    - confidence: AI 的信心度（0-1）
    - modifications_count: 修改数量
    - rag_sources: RAG检索来源列表
    - react_steps: ReAct推理步骤列表
    """

    workflow: Workflow
    ai_message: str
    intent: str = ""
    confidence: float = 0.0
    modifications_count: int = 0
    rag_sources: list[dict] = field(default_factory=list)
    react_steps: list[dict] = field(default_factory=list)


class UpdateWorkflowByChatUseCase:
    """对话式修改工作流用例

    职责：
    1. 验证工作流存在
    2. 调用 WorkflowChatService 处理用户消息
    3. 保存修改后的工作流
    4. 返回修改后的工作流和AI回复

    为什么是 Use Case？
    - 编排多个服务的调用（Repository + Domain Service）
    - 管理事务边界
    - 处理业务规则验证
    """

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        chat_service: WorkflowChatServicePort,
        save_validator: WorkflowSaveValidator,
        *,
        coordinator: Any | None = None,
        event_bus: Any | None = None,
        fail_closed: bool = False,
    ):
        """初始化用例

        参数：
            workflow_repository: 工作流仓储
            chat_service: 工作流对话服务（Port接口）
        """
        self.workflow_repository = workflow_repository
        self.chat_service = chat_service
        self.save_validator = save_validator
        self._coordinator = coordinator
        self._event_bus = event_bus
        self._fail_closed = fail_closed
        self._authorized = False

    def _authorization_ids(self, workflow_id: str) -> tuple[str, str]:
        correlation_id = f"workflow_edit:{workflow_id}"
        original_decision_id = f"{correlation_id}:{uuid4().hex[:12]}"
        return correlation_id, original_decision_id

    async def authorize_edit(self, input_data: UpdateWorkflowByChatInput) -> None:
        """Fail-closed coordinator guard for workflow modifications (WFCORE-060).

        Security:
        - Avoid sending user_message plaintext to coordinator; only share message length.
        """

        if self._authorized:
            return

        from src.application.services.coordinator_policy_chain import CoordinatorPolicyChain

        policy = CoordinatorPolicyChain(
            coordinator=self._coordinator,
            event_bus=self._event_bus,
            source="workflow_chat",
            fail_closed=self._fail_closed,
            supervised_decision_types={"api_request"},
        )
        correlation_id, original_decision_id = self._authorization_ids(input_data.workflow_id)
        await policy.enforce_action_or_raise(
            decision_type="api_request",
            decision={
                "decision_type": "api_request",
                "action": "workflow_edit",
                "workflow_id": input_data.workflow_id,
                "message_len": len(input_data.user_message or ""),
                "correlation_id": correlation_id,
            },
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
        )
        self._authorized = True

    def _authorize_edit_sync(self, input_data: UpdateWorkflowByChatInput) -> None:
        """Sync wrapper for coordinator guard (best effort, fail-closed)."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.authorize_edit(input_data))
            return
        raise DomainError(
            "authorize_edit requires async context; use execute_streaming in async flows"
        )

    def execute(self, input_data: UpdateWorkflowByChatInput) -> UpdateWorkflowByChatOutput:
        """执行用例

        参数：
            input_data: 输入数据

        返回：
            UpdateWorkflowByChatOutput: 包含工作流、AI消息和增强字段

        抛出：
            NotFoundError: 当工作流不存在时
            DomainError: 当消息为空或处理失败时
        """
        # 1. 验证输入
        if not input_data.user_message or not input_data.user_message.strip():
            raise DomainError("消息不能为空")

        # 2. 获取工作流
        workflow = self.workflow_repository.get_by_id(input_data.workflow_id)
        if not workflow:
            raise NotFoundError(entity_type="Workflow", entity_id=input_data.workflow_id)

        # 2.5 Coordinator gate (fail-closed, no side effects).
        self._authorize_edit_sync(input_data)

        # 3. 调用 Domain Service 处理消息
        result = self.chat_service.process_message(
            workflow=workflow,
            user_message=input_data.user_message,
        )

        # 4. 检查处理结果
        if not result.success:
            raise DomainError(result.error_message or "修改工作流失败")

        modified_workflow = result.modified_workflow
        if modified_workflow is None:
            raise DomainError("修改工作流失败：返回的工作流为空")

        # 5. 保存修改后的工作流
        self.save_validator.validate_or_raise(modified_workflow)
        self.workflow_repository.save(modified_workflow)

        # 6. 返回结果
        return UpdateWorkflowByChatOutput(
            workflow=modified_workflow,
            ai_message=result.ai_message,
            intent=result.intent,
            confidence=result.confidence,
            modifications_count=result.modifications_count,
            rag_sources=result.rag_sources,
            react_steps=result.react_steps,
        )

    async def execute_streaming(
        self, input_data: UpdateWorkflowByChatInput
    ) -> AsyncGenerator[dict[str, Any], None]:
        """执行流式对话（异步生成器）

        异步生成器，按以下顺序产生事件：
        1. processing_started - 开始处理
        2. react_step - 每个 ReAct 推理步骤（可能有多个）
        3. modifications_preview - 修改预览
        4. workflow_updated - 工作流更新完成

        参数：
            input_data: 输入数据

        异步生成：
            dict[str, Any]: 各种类型的事件

        抛出：
            NotFoundError: 当工作流不存在时
            DomainError: 当消息为空或处理失败时
        """
        # 1. 验证输入
        if not input_data.user_message or not input_data.user_message.strip():
            raise DomainError("消息不能为空")

        # 2. 获取工作流
        workflow = self.workflow_repository.get_by_id(input_data.workflow_id)
        if not workflow:
            raise NotFoundError(entity_type="Workflow", entity_id=input_data.workflow_id)

        # 2.5 Coordinator gate (fail-closed, no side effects).
        await self.authorize_edit(input_data)

        # 3. 产生开始事件
        yield {
            "type": "processing_started",
            "timestamp": datetime.now(UTC).isoformat(),
            "workflow_id": input_data.workflow_id,
        }

        # 4. 调用 Domain Service 处理消息
        result = self.chat_service.process_message(
            workflow=workflow,
            user_message=input_data.user_message,
        )

        # 5. 检查处理结果
        if not result.success:
            raise DomainError(result.error_message or "修改工作流失败")

        modified_workflow = result.modified_workflow
        if modified_workflow is None:
            raise DomainError("修改工作流失败：返回的工作流为空")

        # 6. 流式产生 react_step 事件
        for idx, react_step in enumerate(result.react_steps, start=1):
            step_number = react_step.get("step") or idx
            tool_id = f"react_{step_number}"
            yield {
                "type": "react_step",
                "step_number": step_number,
                "tool_id": tool_id,
                "thought": react_step.get("thought", ""),
                "action": react_step.get("action", {}),
                "observation": react_step.get("observation", ""),
                "timestamp": datetime.now(UTC).isoformat(),
            }

        # 7. 产生修改预览事件
        yield {
            "type": "modifications_preview",
            "modifications_count": result.modifications_count,
            "intent": result.intent,
            "confidence": result.confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # 8. 保存修改后的工作流
        self.save_validator.validate_or_raise(modified_workflow)
        self.workflow_repository.save(modified_workflow)

        # 9. 产生工作流更新完成事件
        workflow_dict = {
            "id": modified_workflow.id,
            "name": modified_workflow.name,
            "description": modified_workflow.description,
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type.value,
                    "name": node.name,
                    "config": node.config,
                    "position": {"x": node.position.x, "y": node.position.y},
                }
                for node in modified_workflow.nodes
            ],
            "edges": [
                {
                    "id": edge.id,
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "condition": edge.condition,
                }
                for edge in modified_workflow.edges
            ],
        }

        yield {
            "type": "workflow_updated",
            "workflow": workflow_dict,
            "ai_message": result.ai_message,
            "rag_sources": result.rag_sources,
            "timestamp": datetime.now(UTC).isoformat(),
        }

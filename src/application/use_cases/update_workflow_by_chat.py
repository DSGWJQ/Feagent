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

from dataclasses import dataclass, field

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_chat_service import WorkflowChatService
from src.domain.services.workflow_chat_service_enhanced import (
    EnhancedWorkflowChatService,
)


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
        chat_service: WorkflowChatService | EnhancedWorkflowChatService,
    ):
        """初始化用例

        参数：
            workflow_repository: 工作流仓储
            chat_service: 工作流对话服务（支持基础版和增强版）
        """
        self.workflow_repository = workflow_repository
        self.chat_service = chat_service

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

        # 3. 调用 Domain Service 处理消息
        result = self.chat_service.process_message(
            workflow=workflow,
            user_message=input_data.user_message,
        )

        # 4. 处理返回结果（兼容基础服务和增强服务）
        if isinstance(result, tuple):
            # 基础服务返回 tuple[Workflow, str]
            modified_workflow, ai_message = result
            intent = ""
            confidence = 0.0
            modifications_count = 0
            rag_sources = []
            react_steps = []
        else:
            # 增强服务返回 ModificationResult
            if not result.success:
                raise DomainError(result.error_message or "修改工作流失败")

            modified_workflow = result.modified_workflow
            if modified_workflow is None:
                raise DomainError("修改工作流失败：返回的工作流为空")

            ai_message = result.ai_message
            intent = result.intent
            confidence = result.confidence
            modifications_count = result.modifications_count
            rag_sources = result.rag_sources
            react_steps = result.react_steps

        # 5. 保存修改后的工作流
        self.workflow_repository.save(modified_workflow)

        # 6. 返回增强结果
        return UpdateWorkflowByChatOutput(
            workflow=modified_workflow,
            ai_message=ai_message,
            intent=intent,
            confidence=confidence,
            modifications_count=modifications_count,
            rag_sources=rag_sources,
            react_steps=react_steps,
        )

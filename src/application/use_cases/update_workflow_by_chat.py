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

from dataclasses import dataclass

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_chat_service import WorkflowChatService


@dataclass
class UpdateWorkflowByChatInput:
    """对话式修改工作流输入

    字段：
    - workflow_id: 工作流 ID
    - user_message: 用户消息
    """

    workflow_id: str
    user_message: str


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
        chat_service: WorkflowChatService,
    ):
        """初始化用例

        参数：
            workflow_repository: 工作流仓储
            chat_service: 工作流对话服务
        """
        self.workflow_repository = workflow_repository
        self.chat_service = chat_service

    def execute(self, input_data: UpdateWorkflowByChatInput) -> tuple[Workflow, str]:
        """执行用例

        参数：
            input_data: 输入数据

        返回：
            (修改后的工作流, AI回复消息)

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
        modified_workflow, ai_message = self.chat_service.process_message(
            workflow=workflow,
            user_message=input_data.user_message,
        )

        # 4. 保存修改后的工作流
        self.workflow_repository.save(modified_workflow)

        # 5. 返回结果
        return modified_workflow, ai_message

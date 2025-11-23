"""EnhancedChatWorkflowUseCase - 对话增强的工作流更新

编排：
1. 获取工作流
2. 调用对话服务处理用户消息
3. 保存更新后的工作流
4. 返回修改结果
"""

from dataclasses import dataclass

from src.domain.exceptions import NotFoundError


@dataclass
class EnhancedChatWorkflowInput:
    """输入数据"""

    workflow_id: str
    user_message: str


@dataclass
class EnhancedChatWorkflowOutput:
    """输出数据"""

    success: bool
    ai_message: str
    modifications_count: int = 0
    error_message: str = ""


class EnhancedChatWorkflowUseCase:
    """对话增强工作流用例

    职责：
    - 接收用户消息
    - 调用对话增强服务
    - 保存修改后的工作流
    - 维护对话历史
    """

    def __init__(self, workflow_repo, chat_service):
        """初始化用例

        参数：
            workflow_repo: 工作流仓库
            chat_service: 对话增强服务
        """
        self.workflow_repo = workflow_repo
        self.chat_service = chat_service

    def execute(self, input_data: EnhancedChatWorkflowInput) -> EnhancedChatWorkflowOutput:
        """处理对话消息并更新工作流

        参数：
            input_data: 输入数据

        返回：
            输出数据

        抛出：
            NotFoundError: 工作流不存在
        """
        # 1. 获取工作流
        workflow = self.workflow_repo.get_by_id(input_data.workflow_id)
        if not workflow:
            raise NotFoundError(f"工作流不存在: {input_data.workflow_id}")

        # 2. 调用对话服务处理消息
        modification_result = self.chat_service.process_message(workflow, input_data.user_message)

        # 3. 如果成功，保存修改后的工作流
        if modification_result.success and modification_result.modified_workflow:
            self.workflow_repo.save(modification_result.modified_workflow)

        # 4. 返回结果
        return EnhancedChatWorkflowOutput(
            success=modification_result.success,
            ai_message=modification_result.ai_message,
            modifications_count=modification_result.modifications_count,
            error_message=modification_result.error_message,
        )

    def clear_conversation_history(self) -> None:
        """清空对话历史"""
        self.chat_service.clear_history()

    def get_workflow_suggestions(self, workflow_id: str) -> list[str]:
        """获取工作流优化建议

        参数：
            workflow_id: 工作流ID

        返回：
            建议列表

        抛出：
            NotFoundError: 工作流不存在
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError(f"工作流不存在: {workflow_id}")

        return self.chat_service.get_workflow_suggestions(workflow)

    def search_conversation_history(
        self, keyword: str, threshold: float = 0.5
    ) -> list[tuple[str, float]]:
        """搜索对话历史

        参数：
            keyword: 搜索关键词
            threshold: 相关性阈值

        返回：
            (消息内容, 相关性分数) 的列表
        """
        search_results = self.chat_service.history.search(keyword)

        # 过滤低于阈值的结果
        filtered = [(msg.content, score) for msg, score in search_results if score >= threshold]

        return filtered

    def get_chat_history(self) -> list[dict]:
        """获取对话历史

        返回：
            对话消息列表
        """
        return self.chat_service.history.export()

    def get_compressed_context(self, max_tokens: int = 2000) -> list[dict]:
        """获取压缩后的对话上下文

        参数：
            max_tokens: 最大token数

        返回：
            压缩后的消息列表
        """
        compressed = self.chat_service.history.compress_history(max_tokens)
        return [msg.to_dict() for msg in compressed]

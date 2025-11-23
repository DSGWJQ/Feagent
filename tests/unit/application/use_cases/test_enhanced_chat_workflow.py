"""EnhancedChatWorkflowUseCase - TDD RED 阶段测试

定义对话增强工作流更新的期望行为
"""

from unittest.mock import Mock

import pytest


class TestEnhancedChatWorkflowUseCase:
    """测试对话增强工作流用例"""

    @pytest.fixture
    def mock_workflow_repo(self):
        """模拟工作流仓库"""
        return Mock()

    @pytest.fixture
    def mock_chat_service(self):
        """模拟对话服务"""
        return Mock()

    def test_process_chat_message_and_update_workflow(self, mock_workflow_repo, mock_chat_service):
        """测试：应该能处理对话消息并更新工作流"""
        from src.application.use_cases.enhanced_chat_workflow import (
            EnhancedChatWorkflowInput,
            EnhancedChatWorkflowUseCase,
        )

        use_case = EnhancedChatWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            chat_service=mock_chat_service,
        )

        # 模拟工作流
        mock_workflow = Mock()
        mock_workflow.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_workflow

        # 模拟对话服务结果
        mock_result = Mock()
        mock_result.success = True
        mock_result.modified_workflow = mock_workflow
        mock_chat_service.process_message.return_value = mock_result

        input_data = EnhancedChatWorkflowInput(
            workflow_id="wf_123",
            user_message="添加一个HTTP节点",
        )

        result = use_case.execute(input_data)

        assert result is not None
        assert result.success is True

    def test_saves_updated_workflow(self, mock_workflow_repo, mock_chat_service):
        """测试：应该保存更新后的工作流"""
        from src.application.use_cases.enhanced_chat_workflow import (
            EnhancedChatWorkflowInput,
            EnhancedChatWorkflowUseCase,
        )

        use_case = EnhancedChatWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            chat_service=mock_chat_service,
        )

        mock_workflow = Mock()
        mock_workflow.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_workflow

        mock_result = Mock()
        mock_result.success = True
        mock_modified = Mock()
        mock_result.modified_workflow = mock_modified
        mock_chat_service.process_message.return_value = mock_result

        input_data = EnhancedChatWorkflowInput(
            workflow_id="wf_123",
            user_message="修改",
        )

        use_case.execute(input_data)

        # 验证工作流被保存
        assert mock_workflow_repo.save.called

    def test_maintains_conversation_context(self, mock_workflow_repo, mock_chat_service):
        """测试：应该维护对话上下文"""
        from src.application.use_cases.enhanced_chat_workflow import (
            EnhancedChatWorkflowInput,
            EnhancedChatWorkflowUseCase,
        )

        use_case = EnhancedChatWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            chat_service=mock_chat_service,
        )

        mock_workflow = Mock()
        mock_workflow.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_workflow

        mock_result = Mock()
        mock_result.success = True
        mock_result.modified_workflow = mock_workflow
        mock_chat_service.process_message.return_value = mock_result

        # 第一条消息
        input_data1 = EnhancedChatWorkflowInput(
            workflow_id="wf_123",
            user_message="添加HTTP节点",
        )
        use_case.execute(input_data1)

        # 第二条消息应该在同一个服务实例中维护上下文
        input_data2 = EnhancedChatWorkflowInput(
            workflow_id="wf_123",
            user_message="连接到前面的节点",
        )
        use_case.execute(input_data2)

        # 验证chat_service被调用两次
        assert mock_chat_service.process_message.call_count == 2

    def test_handles_chat_failure(self, mock_workflow_repo, mock_chat_service):
        """测试：应该处理对话失败"""
        from src.application.use_cases.enhanced_chat_workflow import (
            EnhancedChatWorkflowInput,
            EnhancedChatWorkflowUseCase,
        )

        use_case = EnhancedChatWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            chat_service=mock_chat_service,
        )

        mock_workflow = Mock()
        mock_workflow.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_workflow

        # 模拟对话失败
        mock_result = Mock()
        mock_result.success = False
        mock_result.error_message = "无效的意图"
        mock_chat_service.process_message.return_value = mock_result

        input_data = EnhancedChatWorkflowInput(
            workflow_id="wf_123",
            user_message="非法消息",
        )

        result = use_case.execute(input_data)

        assert result.success is False
        assert result.error_message is not None

    def test_clear_conversation_history(self, mock_workflow_repo, mock_chat_service):
        """测试：应该能清空对话历史"""
        from src.application.use_cases.enhanced_chat_workflow import (
            EnhancedChatWorkflowUseCase,
        )

        use_case = EnhancedChatWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            chat_service=mock_chat_service,
        )

        use_case.clear_conversation_history()

        # 验证chat_service的清空方法被调用
        assert mock_chat_service.clear_history.called

    def test_get_workflow_suggestions(self, mock_workflow_repo, mock_chat_service):
        """测试：应该能获取工作流建议"""
        from src.application.use_cases.enhanced_chat_workflow import (
            EnhancedChatWorkflowUseCase,
        )

        use_case = EnhancedChatWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            chat_service=mock_chat_service,
        )

        mock_workflow = Mock()
        mock_workflow.id = "wf_123"
        mock_workflow_repo.get_by_id.return_value = mock_workflow

        # 模拟建议
        mock_suggestions = ["缺少开始节点", "缺少结束节点"]
        mock_chat_service.get_workflow_suggestions.return_value = mock_suggestions

        suggestions = use_case.get_workflow_suggestions("wf_123")

        assert len(suggestions) == 2
        assert mock_chat_service.get_workflow_suggestions.called

    def test_search_conversation_history(self, mock_workflow_repo, mock_chat_service):
        """测试：应该能搜索对话历史"""
        from src.application.use_cases.enhanced_chat_workflow import (
            EnhancedChatWorkflowUseCase,
        )

        use_case = EnhancedChatWorkflowUseCase(
            workflow_repo=mock_workflow_repo,
            chat_service=mock_chat_service,
        )

        # 模拟搜索结果
        mock_results = [
            (Mock(content="HTTP 节点"), 0.9),
            (Mock(content="API 配置"), 0.7),
        ]
        mock_chat_service.history.search.return_value = mock_results

        results = use_case.search_conversation_history("HTTP")

        assert len(results) > 0
        assert mock_chat_service.history.search.called

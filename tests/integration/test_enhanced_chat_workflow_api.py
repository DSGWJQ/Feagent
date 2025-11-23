"""Enhanced Chat Workflow API - TDD RED 阶段测试

定义增强对话工作流 API 的期望行为
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


class TestEnhancedChatWorkflowAPI:
    """测试增强对话工作流 API 端点"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.interfaces.api.main import app

        return TestClient(app)

    def test_chat_workflow_post_processes_user_message(self, client):
        """测试：POST /api/workflows/{workflow_id}/chat 应该处理用户消息"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock result
            mock_result = Mock()
            mock_result.success = True
            mock_result.response = "已添加 HTTP 节点"
            mock_result.modified_workflow = Mock()
            mock_use_case.execute.return_value = mock_result

            response = client.post(
                "/api/workflows/wf_123/chat",
                json={
                    "message": "添加一个 HTTP 节点",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "HTTP 节点" in data.get("response", "")

    def test_chat_workflow_get_chat_history(self, client):
        """测试：GET /api/workflows/{workflow_id}/chat-history 应该返回对话历史"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock chat history
            mock_history = [
                {"role": "user", "content": "添加 HTTP 节点"},
                {"role": "assistant", "content": "已添加 HTTP 节点"},
            ]
            mock_use_case.get_chat_history.return_value = mock_history

            response = client.get("/api/workflows/wf_123/chat-history")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2

    def test_chat_workflow_search_conversation_history(self, client):
        """测试：GET /api/workflows/{workflow_id}/chat-search 应该搜索对话历史"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock search results
            mock_results = [
                ("HTTP 节点配置", 0.9),
                ("API 端点", 0.7),
            ]
            mock_use_case.search_conversation_history.return_value = mock_results

            response = client.get(
                "/api/workflows/wf_123/chat-search?keyword=HTTP&threshold=0.5"
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2

    def test_chat_workflow_get_workflow_suggestions(self, client):
        """测试：GET /api/workflows/{workflow_id}/suggestions 应该返回工作流建议"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock suggestions
            mock_suggestions = [
                "缺少开始节点",
                "缺少结束节点",
                "某个节点没有配置完整",
            ]
            mock_use_case.get_workflow_suggestions.return_value = mock_suggestions

            response = client.get("/api/workflows/wf_123/suggestions")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 3

    def test_chat_workflow_clear_conversation_history(self, client):
        """测试：DELETE /api/workflows/{workflow_id}/chat-history 应该清空对话历史"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            response = client.delete("/api/workflows/wf_123/chat-history")

            assert response.status_code == 204
            mock_use_case.clear_conversation_history.assert_called_once()

    def test_chat_workflow_get_compressed_context(self, client):
        """测试：GET /api/workflows/{workflow_id}/chat-context 应该返回压缩后的上下文"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock compressed context
            mock_context = [
                {"role": "user", "content": "添加 HTTP 节点"},
                {"role": "assistant", "content": "已添加 HTTP 节点"},
            ]
            mock_use_case.get_compressed_context.return_value = mock_context

            response = client.get(
                "/api/workflows/wf_123/chat-context?max_tokens=2000"
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_chat_workflow_handles_chat_failure(self, client):
        """测试：对话失败应该返回 400"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            # Mock failure result
            mock_result = Mock()
            mock_result.success = False
            mock_result.error_message = "无法解析用户意图"
            mock_use_case.execute.return_value = mock_result

            response = client.post(
                "/api/workflows/wf_123/chat",
                json={
                    "message": "非法消息",
                },
            )

            assert response.status_code == 400

    def test_chat_workflow_handles_workflow_not_found(self, client):
        """测试：工作流不存在应该返回 404"""
        with patch(
            "src.application.use_cases.enhanced_chat_workflow.EnhancedChatWorkflowUseCase"
        ) as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case_class.return_value = mock_use_case

            from src.domain.exceptions import NotFoundError
            mock_use_case.execute.side_effect = NotFoundError("Workflow", "wf_invalid")

            response = client.post(
                "/api/workflows/wf_invalid/chat",
                json={
                    "message": "添加 HTTP 节点",
                },
            )

            assert response.status_code == 404

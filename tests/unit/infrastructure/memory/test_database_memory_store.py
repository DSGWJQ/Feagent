"""
Unit tests for DatabaseMemoryStore

测试目标：验证数据库持久化存储适配器的行为
TDD Phase: RED
"""

from unittest.mock import Mock

import pytest

from src.domain.entities.chat_message import ChatMessage


class TestDatabaseMemoryStore:
    """DatabaseMemoryStore 单元测试"""

    @pytest.fixture
    def mock_repository(self):
        """创建 mock repository"""
        return Mock()

    @pytest.fixture
    def memory_store(self, mock_repository):
        """创建 DatabaseMemoryStore 实例"""
        from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore

        return DatabaseMemoryStore(mock_repository)

    def test_database_memory_store_exists(self):
        """测试：DatabaseMemoryStore 类应该存在"""
        from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore

        assert DatabaseMemoryStore is not None

    def test_constructor_accepts_repository(self, mock_repository):
        """测试：构造函数应该接受 repository 参数"""
        from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore

        store = DatabaseMemoryStore(mock_repository)
        assert store is not None

    def test_append_calls_repository_save(self, memory_store, mock_repository):
        """测试：append 应该调用 repository.save()"""
        message = ChatMessage.create(workflow_id="wf_test123", content="Test message", is_user=True)

        memory_store.append(message)

        # 验证调用了 repository.save
        mock_repository.save.assert_called_once_with(message)

    def test_append_raises_exception_on_repository_failure(self, memory_store, mock_repository):
        """测试：repository.save() 失败时应该抛出异常"""
        from src.infrastructure.memory.database_memory_store import DatabaseWriteError

        message = ChatMessage.create(workflow_id="wf_test123", content="Test message", is_user=True)

        # 模拟 repository 失败
        mock_repository.save.side_effect = Exception("Database connection failed")

        # 应该抛出 DatabaseWriteError
        with pytest.raises(DatabaseWriteError) as exc_info:
            memory_store.append(message)

        assert "Failed to save message" in str(exc_info.value)

    def test_load_recent_calls_repository_find_by_workflow_id(self, memory_store, mock_repository):
        """测试：load_recent 应该调用 repository.find_by_workflow_id()"""
        workflow_id = "wf_test123"
        last_n = 5

        # 模拟返回值
        mock_messages = [
            ChatMessage.create(workflow_id=workflow_id, content=f"Message {i}", is_user=True)
            for i in range(10)
        ]
        mock_repository.find_by_workflow_id.return_value = mock_messages

        result = memory_store.load_recent(workflow_id, last_n=last_n)

        # 验证调用了 repository
        mock_repository.find_by_workflow_id.assert_called_once()

        # 验证返回最近 N 条
        assert len(result) == last_n
        assert result == mock_messages[-last_n:]

    def test_load_recent_default_last_n(self, memory_store, mock_repository):
        """测试：load_recent 默认返回最近 10 条"""
        workflow_id = "wf_test123"

        # 模拟返回 20 条消息
        mock_messages = [
            ChatMessage.create(workflow_id=workflow_id, content=f"Message {i}", is_user=True)
            for i in range(20)
        ]
        mock_repository.find_by_workflow_id.return_value = mock_messages

        result = memory_store.load_recent(workflow_id)

        # 默认返回最近 10 条
        assert len(result) == 10
        assert result == mock_messages[-10:]

    def test_load_recent_returns_empty_list_when_no_messages(self, memory_store, mock_repository):
        """测试：没有消息时应该返回空列表"""
        workflow_id = "wf_test123"

        # 模拟空返回
        mock_repository.find_by_workflow_id.return_value = []

        result = memory_store.load_recent(workflow_id)

        assert result == []

    def test_load_recent_requests_more_from_repository(self, memory_store, mock_repository):
        """测试：load_recent 应该从 repository 请求 2 倍数量（用于后续压缩）"""
        workflow_id = "wf_test123"
        last_n = 10

        # 模拟返回值（需要设置返回值以避免 Mock 对象不可订阅错误）
        mock_messages = [
            ChatMessage.create(workflow_id=workflow_id, content=f"Message {i}", is_user=True)
            for i in range(20)
        ]
        mock_repository.find_by_workflow_id.return_value = mock_messages

        memory_store.load_recent(workflow_id, last_n=last_n)

        # 验证请求了 2 倍数量
        call_args = mock_repository.find_by_workflow_id.call_args
        assert call_args[1]["limit"] == last_n * 2

    def test_search_calls_repository_search(self, memory_store, mock_repository):
        """测试：search 应该调用 repository.search()"""
        query = "test query"
        workflow_id = "wf_test123"
        threshold = 0.7

        # 模拟返回值
        mock_results = [
            (ChatMessage.create(workflow_id=workflow_id, content="Result 1", is_user=True), 0.9),
            (ChatMessage.create(workflow_id=workflow_id, content="Result 2", is_user=True), 0.8),
        ]
        mock_repository.search.return_value = mock_results

        result = memory_store.search(query, workflow_id, threshold)

        # 验证调用了 repository.search
        mock_repository.search.assert_called_once_with(workflow_id, query, threshold)
        assert result == mock_results

    def test_clear_calls_repository_delete(self, memory_store, mock_repository):
        """测试：clear 应该调用 repository.delete_by_workflow_id()"""
        workflow_id = "wf_test123"

        memory_store.clear(workflow_id)

        # 验证调用了 repository
        mock_repository.delete_by_workflow_id.assert_called_once_with(workflow_id)

    def test_implements_memory_provider_protocol(self, memory_store):
        """测试：DatabaseMemoryStore 应该实现 MemoryProvider Protocol"""
        # 验证所有必需方法存在
        assert hasattr(memory_store, "append")
        assert hasattr(memory_store, "load_recent")
        assert hasattr(memory_store, "search")
        assert hasattr(memory_store, "clear")

        # 验证方法可调用
        assert callable(memory_store.append)
        assert callable(memory_store.load_recent)
        assert callable(memory_store.search)
        assert callable(memory_store.clear)

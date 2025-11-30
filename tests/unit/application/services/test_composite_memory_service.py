"""
Unit tests for CompositeMemoryService

测试目标：验证组合式内存服务的编排逻辑
TDD Phase: RED
"""

from unittest.mock import Mock

import pytest

from src.domain.entities.chat_message import ChatMessage


class TestCompositeMemoryService:
    """CompositeMemoryService 单元测试"""

    @pytest.fixture
    def mock_db_store(self):
        """Mock DatabaseMemoryStore"""
        return Mock()

    @pytest.fixture
    def mock_cache(self):
        """Mock InMemoryCache"""
        return Mock()

    @pytest.fixture
    def mock_compressor(self):
        """Mock TFIDFCompressor"""
        return Mock()

    @pytest.fixture
    def service(self, mock_db_store, mock_cache, mock_compressor):
        """创建 CompositeMemoryService 实例"""
        from src.application.services.composite_memory_service import CompositeMemoryService

        return CompositeMemoryService(
            db_store=mock_db_store,
            cache=mock_cache,
            compressor=mock_compressor,
            max_context_tokens=4000,
        )

    def test_composite_memory_service_exists(self):
        """测试：CompositeMemoryService 类应该存在"""
        from src.application.services.composite_memory_service import CompositeMemoryService

        assert CompositeMemoryService is not None

    def test_append_writes_to_db_first(self, service, mock_db_store, mock_cache):
        """测试：append 应该先写入 DB"""
        message = ChatMessage.create("wf_123", "Hello", is_user=True)

        service.append(message)

        # 验证调用了 DB
        mock_db_store.append.assert_called_once_with(message)

    def test_append_writes_to_cache_after_db_success(self, service, mock_db_store, mock_cache):
        """测试：DB 成功后应该写入 Cache"""
        message = ChatMessage.create("wf_123", "Hello", is_user=True)

        # Mock cache.get 返回现有消息
        mock_cache.get.return_value = []

        service.append(message)

        # 验证调用了 Cache
        mock_cache.get.assert_called_once_with("wf_123")
        mock_cache.put.assert_called_once()

    def test_append_raises_exception_when_db_fails(self, service, mock_db_store):
        """测试：DB 写入失败时应该抛出异常"""
        message = ChatMessage.create("wf_123", "Hello", is_user=True)

        # Mock DB 失败
        mock_db_store.append.side_effect = Exception("DB error")

        # 应该抛出异常
        with pytest.raises(Exception):
            service.append(message)

    def test_append_invalidates_cache_when_cache_write_fails(
        self, service, mock_db_store, mock_cache
    ):
        """测试：Cache 写入失败时应该标记失效"""
        message = ChatMessage.create("wf_123", "Hello", is_user=True)

        # Mock cache.get 返回空
        mock_cache.get.return_value = []

        # Mock cache.put 失败
        mock_cache.put.side_effect = Exception("Cache error")

        # 应该不抛异常（Cache 失败不影响主流程）
        service.append(message)

        # 应该标记 Cache 失效
        mock_cache.invalidate.assert_called_once_with("wf_123")

    def test_load_recent_returns_from_cache_on_hit(self, service, mock_cache):
        """测试：缓存命中时直接返回"""
        cached_messages = [
            ChatMessage.create("wf_123", f"Message {i}", is_user=True) for i in range(5)
        ]
        mock_cache.get.return_value = cached_messages

        result = service.load_recent("wf_123", last_n=3)

        # 应该返回最后 3 条
        assert len(result) == 3
        assert result == cached_messages[-3:]

        # 不应该调用 DB
        service._db.load_recent.assert_not_called()

    def test_load_recent_falls_back_to_db_on_cache_miss(
        self, service, mock_db_store, mock_cache, mock_compressor
    ):
        """测试：缓存未命中时回溯到 DB"""
        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock DB 返回
        db_messages = [
            ChatMessage.create("wf_123", f"Message {i}", is_user=True) for i in range(20)
        ]
        mock_db_store.load_recent.return_value = db_messages

        # Mock compressor 返回压缩后的消息
        compressed = db_messages[-10:]
        mock_compressor.compress.return_value = compressed

        result = service.load_recent("wf_123", last_n=5)

        # 应该调用 DB
        mock_db_store.load_recent.assert_called_once_with("wf_123", last_n=100)

        # 应该调用 compressor
        mock_compressor.compress.assert_called_once()

        # 应该更新 Cache
        mock_cache.put.assert_called_once_with("wf_123", compressed)

        # 应该返回最后 5 条
        assert len(result) == 5

    def test_load_recent_returns_empty_when_no_messages(self, service, mock_db_store, mock_cache):
        """测试：没有消息时返回空列表"""
        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock DB 返回空
        mock_db_store.load_recent.return_value = []

        result = service.load_recent("wf_123")

        assert result == []

    def test_load_recent_calls_compressor_with_correct_params(
        self, service, mock_db_store, mock_cache, mock_compressor
    ):
        """测试：应该用正确的参数调用 compressor"""
        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock DB 返回
        db_messages = [
            ChatMessage.create("wf_123", f"Message {i}", is_user=True) for i in range(50)
        ]
        mock_db_store.load_recent.return_value = db_messages
        mock_compressor.compress.return_value = db_messages[:10]

        service.load_recent("wf_123", last_n=10)

        # 验证 compressor 参数
        call_args = mock_compressor.compress.call_args
        assert call_args[0][0] == db_messages  # messages
        assert call_args[1]["max_tokens"] == 4000  # max_context_tokens
        assert call_args[1]["min_messages"] == 2  # min(2, last_n)

    def test_search_delegates_to_db_store(self, service, mock_db_store):
        """测试：search 应该委托给 DB store"""
        query = "test query"
        workflow_id = "wf_123"
        threshold = 0.7

        # Mock DB 返回
        search_results = [
            (ChatMessage.create(workflow_id, "Result 1", is_user=True), 0.9),
            (ChatMessage.create(workflow_id, "Result 2", is_user=True), 0.8),
        ]
        mock_db_store.search.return_value = search_results

        result = service.search(query, workflow_id, threshold)

        # 应该调用 DB
        mock_db_store.search.assert_called_once_with(query, workflow_id, threshold)
        assert result == search_results

    def test_clear_clears_both_db_and_cache(self, service, mock_db_store, mock_cache):
        """测试：clear 应该清空 DB 和 Cache"""
        workflow_id = "wf_123"

        service.clear(workflow_id)

        # 应该调用 DB 清空
        mock_db_store.clear.assert_called_once_with(workflow_id)

        # 应该失效 Cache
        mock_cache.invalidate.assert_called_once_with(workflow_id)

    def test_get_metrics_returns_performance_data(self, service, mock_cache):
        """测试：get_metrics 应该返回性能指标"""
        # Mock cache stats
        mock_cache.get_stats.return_value = {
            "hits": 10,
            "misses": 5,
            "hit_rate": 0.67,
            "cached_workflows": 3,
            "ttl_seconds": 900.0,
        }

        metrics = service.get_metrics()

        assert metrics.cache_hit_rate == 0.67
        assert metrics.fallback_count == 0  # 初始状态
        assert isinstance(metrics.compression_ratio, float)
        assert isinstance(metrics.avg_fallback_time_ms, float)

    def test_get_metrics_tracks_fallback_count(
        self, service, mock_db_store, mock_cache, mock_compressor
    ):
        """测试：get_metrics 应该追踪回溯次数"""
        # Mock cache miss（触发回溯）
        mock_cache.get.return_value = None
        mock_db_store.load_recent.return_value = [
            ChatMessage.create("wf_123", "Message", is_user=True)
        ]
        mock_compressor.compress.return_value = mock_db_store.load_recent.return_value

        # Mock cache stats
        mock_cache.get_stats.return_value = {
            "hits": 0,
            "misses": 3,
            "hit_rate": 0.0,
            "cached_workflows": 1,
            "ttl_seconds": 900.0,
        }

        # 触发 3 次回溯
        for _ in range(3):
            service.load_recent("wf_123")

        metrics = service.get_metrics()

        assert metrics.fallback_count == 3

    def test_get_metrics_tracks_compression_ratio(
        self, service, mock_db_store, mock_cache, mock_compressor
    ):
        """测试：get_metrics 应该追踪压缩比"""
        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock DB 返回 20 条
        db_messages = [
            ChatMessage.create("wf_123", f"Message {i}", is_user=True) for i in range(20)
        ]
        mock_db_store.load_recent.return_value = db_messages

        # Mock compressor 压缩到 10 条
        mock_compressor.compress.return_value = db_messages[:10]

        # Mock cache stats
        mock_cache.get_stats.return_value = {
            "hits": 0,
            "misses": 1,
            "hit_rate": 0.0,
            "cached_workflows": 1,
            "ttl_seconds": 900.0,
        }

        service.load_recent("wf_123")

        metrics = service.get_metrics()

        # 压缩比应该是 10/20 = 0.5
        assert 0.4 < metrics.compression_ratio < 0.6

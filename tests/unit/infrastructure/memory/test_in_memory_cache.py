"""
Unit tests for InMemoryCache

测试目标：验证 TTL + LRU 缓存的行为
TDD Phase: RED
"""

from time import sleep

import pytest

from src.domain.entities.chat_message import ChatMessage


class TestInMemoryCache:
    """InMemoryCache 单元测试"""

    @pytest.fixture
    def cache(self):
        """创建缓存实例（TTL=1秒用于测试）"""
        from src.infrastructure.memory.in_memory_cache import InMemoryCache

        return InMemoryCache(ttl_seconds=1, max_workflows=3, max_messages_per_workflow=5)

    def test_in_memory_cache_exists(self):
        """测试：InMemoryCache 类应该存在"""
        from src.infrastructure.memory.in_memory_cache import InMemoryCache

        assert InMemoryCache is not None

    def test_constructor_accepts_parameters(self):
        """测试：构造函数应该接受 TTL 和容量参数"""
        from src.infrastructure.memory.in_memory_cache import InMemoryCache

        cache = InMemoryCache(ttl_seconds=900, max_workflows=1000, max_messages_per_workflow=50)
        assert cache is not None

    def test_get_returns_none_for_nonexistent_workflow(self, cache):
        """测试：不存在的 workflow 应该返回 None"""
        result = cache.get("nonexistent_workflow")
        assert result is None

    def test_put_and_get_basic_flow(self, cache):
        """测试：基本的存取流程"""
        workflow_id = "wf_test123"
        messages = [
            ChatMessage.create(workflow_id=workflow_id, content=f"Message {i}", is_user=True)
            for i in range(3)
        ]

        # 存入缓存
        cache.put(workflow_id, messages)

        # 读取缓存
        result = cache.get(workflow_id)

        assert result is not None
        assert len(result) == 3
        assert result[0].content == "Message 0"

    def test_get_returns_copy_not_reference(self, cache):
        """测试：get 应该返回副本，不是引用"""
        workflow_id = "wf_test123"
        messages = [ChatMessage.create(workflow_id=workflow_id, content="Original", is_user=True)]

        cache.put(workflow_id, messages)
        result1 = cache.get(workflow_id)
        result2 = cache.get(workflow_id)

        # 修改 result1 不应该影响 result2
        assert result1 is not result2

    def test_ttl_expiration(self, cache):
        """测试：TTL 过期后应该返回 None"""
        workflow_id = "wf_test123"
        messages = [ChatMessage.create(workflow_id=workflow_id, content="Message", is_user=True)]

        cache.put(workflow_id, messages)

        # 立即读取应该成功
        assert cache.get(workflow_id) is not None

        # 等待 TTL 过期（1.1秒）
        sleep(1.1)

        # 过期后应该返回 None
        assert cache.get(workflow_id) is None

    def test_is_valid_returns_true_for_valid_cache(self, cache):
        """测试：有效缓存时 is_valid 应该返回 True"""
        workflow_id = "wf_test123"
        messages = [ChatMessage.create(workflow_id=workflow_id, content="Message", is_user=True)]

        cache.put(workflow_id, messages)
        assert cache.is_valid(workflow_id) is True

    def test_is_valid_returns_false_for_expired_cache(self, cache):
        """测试：过期缓存时 is_valid 应该返回 False"""
        workflow_id = "wf_test123"
        messages = [ChatMessage.create(workflow_id=workflow_id, content="Message", is_user=True)]

        cache.put(workflow_id, messages)

        # 等待 TTL 过期
        sleep(1.1)

        assert cache.is_valid(workflow_id) is False

    def test_is_valid_returns_false_for_nonexistent(self, cache):
        """测试：不存在的缓存时 is_valid 应该返回 False"""
        assert cache.is_valid("nonexistent") is False

    def test_invalidate_marks_cache_invalid(self, cache):
        """测试：invalidate 应该标记缓存失效"""
        workflow_id = "wf_test123"
        messages = [ChatMessage.create(workflow_id=workflow_id, content="Message", is_user=True)]

        cache.put(workflow_id, messages)
        assert cache.is_valid(workflow_id) is True

        # 主动失效
        cache.invalidate(workflow_id)

        # 失效后 is_valid 返回 False
        assert cache.is_valid(workflow_id) is False

        # 失效后 get 返回 None
        assert cache.get(workflow_id) is None

    def test_invalidate_is_idempotent(self, cache):
        """测试：invalidate 是幂等的（重复调用不报错）"""
        workflow_id = "wf_test123"

        # 对不存在的 workflow 调用 invalidate 不应该报错
        cache.invalidate(workflow_id)
        cache.invalidate(workflow_id)

    def test_put_trims_messages_to_max_limit(self, cache):
        """测试：put 应该限制消息数量（max_messages_per_workflow=5）"""
        workflow_id = "wf_test123"
        messages = [
            ChatMessage.create(workflow_id=workflow_id, content=f"Message {i}", is_user=True)
            for i in range(10)
        ]

        cache.put(workflow_id, messages)
        result = cache.get(workflow_id)

        # 应该只保留最后 5 条
        assert len(result) == 5
        assert result[0].content == "Message 5"
        assert result[4].content == "Message 9"

    def test_lru_eviction_when_exceeding_max_workflows(self, cache):
        """测试：超过 max_workflows 时应该淘汰最旧的（LRU）"""
        # max_workflows=3
        for i in range(4):
            workflow_id = f"wf_{i}"
            messages = [
                ChatMessage.create(workflow_id=workflow_id, content=f"Message {i}", is_user=True)
            ]
            cache.put(workflow_id, messages)

        # 最旧的 wf_0 应该被淘汰
        assert cache.get("wf_0") is None

        # 最新的 3 个应该存在
        assert cache.get("wf_1") is not None
        assert cache.get("wf_2") is not None
        assert cache.get("wf_3") is not None

    def test_lru_updates_on_get(self, cache):
        """测试：get 操作应该更新 LRU 顺序"""
        # 插入 3 个 workflow
        for i in range(3):
            workflow_id = f"wf_{i}"
            messages = [
                ChatMessage.create(workflow_id=workflow_id, content=f"Message {i}", is_user=True)
            ]
            cache.put(workflow_id, messages)

        # 访问 wf_0，使其成为最新访问
        cache.get("wf_0")

        # 插入第 4 个 workflow，应该淘汰 wf_1（最旧未访问）
        cache.put(
            "wf_3", [ChatMessage.create(workflow_id="wf_3", content="Message 3", is_user=True)]
        )

        # wf_0 因为被访问过，应该还在
        assert cache.get("wf_0") is not None

        # wf_1 应该被淘汰
        assert cache.get("wf_1") is None

    def test_get_stats_returns_metrics(self, cache):
        """测试：get_stats 应该返回统计指标"""
        workflow_id = "wf_test123"
        messages = [ChatMessage.create(workflow_id=workflow_id, content="Message", is_user=True)]

        cache.put(workflow_id, messages)

        # 一次命中
        cache.get(workflow_id)

        # 一次未命中
        cache.get("nonexistent")

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["cached_workflows"] == 1
        assert stats["ttl_seconds"] == 1.0

    def test_multiple_updates_to_same_workflow(self, cache):
        """测试：多次更新同一个 workflow"""
        workflow_id = "wf_test123"

        # 第一次存入
        messages1 = [ChatMessage.create(workflow_id=workflow_id, content="Message 1", is_user=True)]
        cache.put(workflow_id, messages1)

        # 第二次存入（覆盖）
        messages2 = [ChatMessage.create(workflow_id=workflow_id, content="Message 2", is_user=True)]
        cache.put(workflow_id, messages2)

        # 应该返回最新的
        result = cache.get(workflow_id)
        assert len(result) == 1
        assert result[0].content == "Message 2"

    def test_implements_memory_cache_protocol(self, cache):
        """测试：InMemoryCache 应该实现 MemoryCache Protocol"""
        assert hasattr(cache, "get")
        assert hasattr(cache, "put")
        assert hasattr(cache, "invalidate")
        assert hasattr(cache, "is_valid")

        assert callable(cache.get)
        assert callable(cache.put)
        assert callable(cache.invalidate)
        assert callable(cache.is_valid)

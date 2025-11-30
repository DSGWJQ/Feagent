"""
Unit tests for MemoryCache Protocol

测试目标：验证 MemoryCache 协议的契约定义和实现规范
TDD Phase: RED
"""

from src.domain.entities.chat_message import ChatMessage


def test_memory_cache_protocol_exists():
    """测试：MemoryCache Protocol 应该存在"""
    from src.domain.ports.memory_cache import MemoryCache

    assert MemoryCache is not None
    assert isinstance(MemoryCache, type)


def test_memory_cache_is_protocol():
    """测试：MemoryCache 应该是一个 Protocol"""
    from src.domain.ports.memory_cache import MemoryCache

    # Protocol 应该可以被继承
    assert hasattr(MemoryCache, "__mro__")


def test_memory_cache_has_get_method():
    """测试：MemoryCache 应该定义 get 方法"""
    from src.domain.ports.memory_cache import MemoryCache

    assert hasattr(MemoryCache, "get")


def test_memory_cache_has_put_method():
    """测试：MemoryCache 应该定义 put 方法"""
    from src.domain.ports.memory_cache import MemoryCache

    assert hasattr(MemoryCache, "put")


def test_memory_cache_has_invalidate_method():
    """测试：MemoryCache 应该定义 invalidate 方法"""
    from src.domain.ports.memory_cache import MemoryCache

    assert hasattr(MemoryCache, "invalidate")


def test_memory_cache_has_is_valid_method():
    """测试：MemoryCache 应该定义 is_valid 方法"""
    from src.domain.ports.memory_cache import MemoryCache

    assert hasattr(MemoryCache, "is_valid")


class MockMemoryCache:
    """Mock implementation for testing Protocol conformance"""

    def get(self, workflow_id: str) -> list[ChatMessage] | None:
        return None

    def put(self, workflow_id: str, messages: list[ChatMessage]) -> None:
        pass

    def invalidate(self, workflow_id: str) -> None:
        pass

    def is_valid(self, workflow_id: str) -> bool:
        return False


def test_concrete_class_can_implement_memory_cache():
    """测试：具体类应该可以实现 MemoryCache Protocol"""

    # 创建实现类实例
    cache = MockMemoryCache()

    # 验证实现了所有必需方法
    assert hasattr(cache, "get")
    assert hasattr(cache, "put")
    assert hasattr(cache, "invalidate")
    assert hasattr(cache, "is_valid")

    # 验证方法可调用
    assert callable(cache.get)
    assert callable(cache.put)
    assert callable(cache.invalidate)
    assert callable(cache.is_valid)


def test_memory_cache_get_signature():
    """测试：get 方法应该返回消息列表或 None"""
    cache = MockMemoryCache()

    # 调用方法
    result = cache.get(workflow_id="wf_test123")

    # 验证返回类型（None 或 list）
    assert result is None or isinstance(result, list)


def test_memory_cache_put_signature():
    """测试：put 方法应该接受 workflow_id 和消息列表"""
    cache = MockMemoryCache()

    # 创建测试消息
    messages = [
        ChatMessage.create(workflow_id="wf_test123", content="Message 1", is_user=True),
        ChatMessage.create(workflow_id="wf_test123", content="Message 2", is_user=False),
    ]

    # 应该可以调用（不抛异常）
    cache.put(workflow_id="wf_test123", messages=messages)


def test_memory_cache_invalidate_signature():
    """测试：invalidate 方法应该接受 workflow_id 参数"""
    cache = MockMemoryCache()

    # 应该可以调用（不抛异常）
    cache.invalidate(workflow_id="wf_test123")


def test_memory_cache_is_valid_signature():
    """测试：is_valid 方法应该返回布尔值"""
    cache = MockMemoryCache()

    # 调用方法
    result = cache.is_valid(workflow_id="wf_test123")

    # 验证返回类型
    assert isinstance(result, bool)


def test_memory_cache_method_signatures_match_protocol():
    """测试：实现类的方法签名应该与 Protocol 匹配"""
    from src.domain.ports.memory_cache import MemoryCache

    cache = MockMemoryCache()

    # 验证方法存在
    protocol_methods = ["get", "put", "invalidate", "is_valid"]

    for method_name in protocol_methods:
        assert hasattr(MemoryCache, method_name), f"Protocol missing method: {method_name}"
        assert hasattr(cache, method_name), f"Implementation missing method: {method_name}"


def test_memory_cache_get_returns_none_on_miss():
    """测试：缓存未命中时 get 应该返回 None"""
    cache = MockMemoryCache()

    result = cache.get(workflow_id="nonexistent_workflow")

    assert result is None


def test_memory_cache_is_valid_returns_false_for_invalid():
    """测试：无效缓存时 is_valid 应该返回 False"""
    cache = MockMemoryCache()

    result = cache.is_valid(workflow_id="nonexistent_workflow")

    assert result is False

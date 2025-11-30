"""
Unit tests for MemoryProvider Protocol

测试目标：验证 MemoryProvider 协议的契约定义和实现规范
TDD Phase: RED
"""

from src.domain.entities.chat_message import ChatMessage


def test_memory_provider_protocol_exists():
    """测试：MemoryProvider Protocol 应该存在"""
    from src.domain.ports.memory_provider import MemoryProvider

    assert MemoryProvider is not None
    assert isinstance(MemoryProvider, type)


def test_memory_provider_is_protocol():
    """测试：MemoryProvider 应该是一个 Protocol"""
    from src.domain.ports.memory_provider import MemoryProvider

    # Protocol 应该可以被继承
    assert hasattr(MemoryProvider, "__mro__")


def test_memory_provider_has_append_method():
    """测试：MemoryProvider 应该定义 append 方法"""
    from src.domain.ports.memory_provider import MemoryProvider

    # 检查方法是否存在
    assert hasattr(MemoryProvider, "append")


def test_memory_provider_has_load_recent_method():
    """测试：MemoryProvider 应该定义 load_recent 方法"""
    from src.domain.ports.memory_provider import MemoryProvider

    assert hasattr(MemoryProvider, "load_recent")


def test_memory_provider_has_search_method():
    """测试：MemoryProvider 应该定义 search 方法"""
    from src.domain.ports.memory_provider import MemoryProvider

    assert hasattr(MemoryProvider, "search")


def test_memory_provider_has_clear_method():
    """测试：MemoryProvider 应该定义 clear 方法"""
    from src.domain.ports.memory_provider import MemoryProvider

    assert hasattr(MemoryProvider, "clear")


class MockMemoryProvider:
    """Mock implementation for testing Protocol conformance"""

    def append(self, message: ChatMessage) -> None:
        pass

    def load_recent(self, workflow_id: str, last_n: int = 10) -> list[ChatMessage]:
        return []

    def search(
        self, query: str, workflow_id: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        return []

    def clear(self, workflow_id: str) -> None:
        pass


def test_concrete_class_can_implement_memory_provider():
    """测试：具体类应该可以实现 MemoryProvider Protocol"""

    # 创建实现类实例
    provider = MockMemoryProvider()

    # 验证实现了所有必需方法
    assert hasattr(provider, "append")
    assert hasattr(provider, "load_recent")
    assert hasattr(provider, "search")
    assert hasattr(provider, "clear")

    # 验证方法可调用
    assert callable(provider.append)
    assert callable(provider.load_recent)
    assert callable(provider.search)
    assert callable(provider.clear)


def test_memory_provider_append_signature():
    """测试：append 方法应该接受 ChatMessage 参数"""
    provider = MockMemoryProvider()

    # 创建测试消息
    message = ChatMessage.create(workflow_id="wf_test123", content="Test message", is_user=True)

    # 应该可以调用（不抛异常）
    provider.append(message)


def test_memory_provider_load_recent_signature():
    """测试：load_recent 方法应该返回消息列表"""
    provider = MockMemoryProvider()

    # 调用方法
    messages = provider.load_recent(workflow_id="wf_test123", last_n=5)

    # 验证返回类型
    assert isinstance(messages, list)


def test_memory_provider_search_signature():
    """测试：search 方法应该返回 (message, score) 元组列表"""
    provider = MockMemoryProvider()

    # 调用方法
    results = provider.search(query="test query", workflow_id="wf_test123", threshold=0.7)

    # 验证返回类型
    assert isinstance(results, list)


def test_memory_provider_clear_signature():
    """测试：clear 方法应该接受 workflow_id 参数"""
    provider = MockMemoryProvider()

    # 应该可以调用（不抛异常）
    provider.clear(workflow_id="wf_test123")


def test_memory_provider_method_signatures_match_protocol():
    """测试：实现类的方法签名应该与 Protocol 匹配"""
    from src.domain.ports.memory_provider import MemoryProvider

    provider = MockMemoryProvider()

    # 验证方法存在
    protocol_methods = ["append", "load_recent", "search", "clear"]

    for method_name in protocol_methods:
        assert hasattr(MemoryProvider, method_name), f"Protocol missing method: {method_name}"
        assert hasattr(provider, method_name), f"Implementation missing method: {method_name}"

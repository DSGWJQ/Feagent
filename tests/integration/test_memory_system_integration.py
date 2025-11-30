"""
Memory System Integration Tests

真实场景的端到端测试，验证完整的 Memory + RAG 系统。

测试场景：
1. 多轮对话记忆延续
2. 缓存命中和回溯
3. 消息压缩效果
4. 性能监控指标

Author: Claude Code
Date: 2025-11-30
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.application.services.composite_memory_service import CompositeMemoryService
from src.domain.entities.chat_message import ChatMessage
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.chat_message_repository import (
    SQLAlchemyChatMessageRepository,
)
from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore
from src.infrastructure.memory.in_memory_cache import InMemoryCache
from src.infrastructure.memory.tfidf_compressor import TFIDFCompressor


class TestMemorySystemIntegration:
    """内存系统集成测试"""

    @pytest.fixture
    def engine(self):
        """创建内存数据库引擎"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()

    @pytest.fixture
    def db_session(self, engine):
        """测试数据库会话"""
        session_maker = sessionmaker(engine, class_=Session, expire_on_commit=False)
        session = session_maker()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def memory_service(self, db_session):
        """创建真实的 CompositeMemoryService"""
        repository = SQLAlchemyChatMessageRepository(db_session)
        db_store = DatabaseMemoryStore(repository)
        cache = InMemoryCache(ttl_seconds=900, max_workflows=100)
        compressor = TFIDFCompressor()

        return CompositeMemoryService(db_store, cache, compressor)

    def test_multi_turn_conversation_memory(self, memory_service):
        """
        场景：多轮对话，记忆应该被正确保存和检索

        步骤：
        1. 用户发送 5 条消息
        2. AI 回复 5 条消息
        3. 读取最近 10 条消息
        4. 验证顺序和内容
        """
        workflow_id = "wf_conversation_001"

        # 模拟对话
        conversations = [
            ("用户：你好", "AI：你好！有什么可以帮助你的吗？"),
            ("用户：创建一个 HTTP 节点", "AI：已创建 HTTP 节点"),
            ("用户：连接到 LLM 节点", "AI：已连接到 LLM 节点"),
            ("用户：设置温度为 0.7", "AI：已设置温度参数"),
            ("用户：保存工作流", "AI：工作流已保存"),
        ]

        # 写入对话
        for user_msg, ai_msg in conversations:
            memory_service.append(ChatMessage.create(workflow_id, user_msg, is_user=True))
            memory_service.append(ChatMessage.create(workflow_id, ai_msg, is_user=False))

        # 读取最近 10 条
        recent = memory_service.load_recent(workflow_id, last_n=10)

        # 验证
        assert len(recent) == 10
        assert recent[0].content == conversations[0][0]  # 第一条是最早的用户消息
        assert recent[-1].content == conversations[-1][1]  # 最后一条是最新的 AI 消息

    def test_cache_hit_and_miss(self, memory_service):
        """
        场景：缓存命中和未命中

        步骤：
        1. 第一次读取（缓存命中，因为 append 已填充缓存）
        2. 第二次读取（缓存命中 → 直接返回）
        3. 失效缓存后读取（缓存未命中 → 回溯到 DB）
        4. 验证性能指标
        """
        workflow_id = "wf_cache_test_001"

        # 写入消息（append 会同时写入 DB 和 Cache）
        for i in range(5):
            memory_service.append(ChatMessage.create(workflow_id, f"Message {i}", is_user=True))

        # 第一次读取（缓存命中，因为 append 已填充）
        result1 = memory_service.load_recent(workflow_id, last_n=5)
        assert len(result1) == 5

        # 第二次读取（缓存命中）
        result2 = memory_service.load_recent(workflow_id, last_n=5)
        assert len(result2) == 5
        assert result1[0].id == result2[0].id  # 应该是同样的消息

        # 失效缓存
        memory_service._cache.invalidate(workflow_id)

        # 第三次读取（缓存未命中 → 回溯到 DB）
        result3 = memory_service.load_recent(workflow_id, last_n=5)
        assert len(result3) == 5

        # 验证指标
        metrics = memory_service.get_metrics()
        assert metrics.cache_hit_rate > 0  # 应该有命中
        assert metrics.fallback_count >= 1  # 至少有一次回溯（第三次读取）

    def test_message_compression(self, memory_service):
        """
        场景：大量消息压缩

        步骤：
        1. 写入 100 条长消息（超过 token 限制）
        2. 失效缓存强制回溯（触发压缩）
        3. 验证压缩效果
        """
        workflow_id = "wf_compression_test_001"

        # 写入 100 条长消息（每条 ~300 tokens，总计 ~30000 tokens，超过 4000 限制）
        long_content = "这是一条很长的消息，包含大量的文本内容，用于测试消息压缩功能。" * 20
        for i in range(100):
            memory_service.append(
                ChatMessage.create(workflow_id, f"{long_content} 第 {i} 条", is_user=True)
            )

        # 失效缓存，强制下次读取回溯到 DB
        memory_service._cache.invalidate(workflow_id)

        # 读取（触发回溯 + 压缩）
        result = memory_service.load_recent(workflow_id, last_n=10)

        # 验证：压缩后应该远少于 100 条（由于 token 限制）
        assert len(result) <= 10  # 最多返回请求的数量
        assert len(result) < 100  # 应该被压缩

        # 验证指标：应该有压缩发生
        metrics = memory_service.get_metrics()
        assert metrics.fallback_count == 1  # 一次回溯
        assert 0 < metrics.compression_ratio < 1  # 应该有压缩比（压缩后 < 100 条）

    def test_search_functionality(self, memory_service):
        """
        场景：搜索历史消息

        步骤：
        1. 写入包含特定关键词的消息
        2. 搜索关键词
        3. 验证结果相关性
        """
        workflow_id = "wf_search_test_001"

        # 写入消息
        memory_service.append(ChatMessage.create(workflow_id, "创建一个 HTTP 节点", is_user=True))
        memory_service.append(ChatMessage.create(workflow_id, "添加 LLM 处理", is_user=True))
        memory_service.append(ChatMessage.create(workflow_id, "无关的消息", is_user=True))

        # 搜索
        results = memory_service.search("HTTP", workflow_id, threshold=0.3)

        # 验证
        assert len(results) > 0
        # 第一个结果应该包含 HTTP
        assert "HTTP" in results[0][0].content

    def test_performance_metrics_tracking(self, memory_service):
        """
        场景：性能指标追踪

        步骤：
        1. 执行多次操作
        2. 检查指标是否正确更新
        """
        workflow_id = "wf_metrics_test_001"

        # 写入并读取
        for i in range(3):
            memory_service.append(ChatMessage.create(workflow_id, f"Message {i}", is_user=True))

        # 触发回溯
        memory_service.load_recent(workflow_id)

        # 获取指标
        metrics = memory_service.get_metrics()

        # 验证
        assert isinstance(metrics.cache_hit_rate, float)
        assert 0 <= metrics.cache_hit_rate <= 1
        assert metrics.fallback_count >= 0
        assert metrics.compression_ratio > 0
        assert metrics.avg_fallback_time_ms >= 0

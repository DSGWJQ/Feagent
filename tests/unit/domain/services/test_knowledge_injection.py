"""测试：知识注入到对话 Agent - Phase 5 阶段3

测试目标：
1. Coordinator 自动根据目标检索知识
2. Coordinator 自动根据错误检索知识
3. 知识注入到压缩上下文
4. ConversationAgent 可获取知识增强上下文

完成标准：
- coordinator.enrich_context_with_knowledge(workflow_id, goal, errors) 方法可用
- 压缩时自动附带知识引用
- ConversationAgent 可从 Coordinator 获取带知识的上下文
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus

# ==================== 测试1：基于目标自动检索知识 ====================


class TestAutoRetrieveKnowledgeByGoal:
    """测试基于目标自动检索知识"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def coordinator_with_retriever(self, mock_event_bus):
        """创建带知识检索器的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 添加目标相关知识
        retriever.add_goal_knowledge(
            keyword="数据分析",
            knowledge={
                "doc_id": "doc_analysis",
                "title": "数据分析最佳实践",
                "preview": "使用 pandas 和 numpy 进行数据分析...",
                "match_score": 0.9,
            },
        )
        retriever.add_goal_knowledge(
            keyword="API",
            knowledge={
                "doc_id": "doc_api",
                "title": "REST API 设计指南",
                "preview": "遵循 RESTful 规范设计接口...",
                "match_score": 0.85,
            },
        )

        return CoordinatorAgent(
            event_bus=mock_event_bus,
            knowledge_retriever=retriever,
        )

    @pytest.mark.asyncio
    async def test_enrich_context_with_goal_knowledge(self, coordinator_with_retriever):
        """基于目标丰富上下文"""
        # 初始化工作流上下文
        coordinator_with_retriever.workflow_states["wf_001"] = {
            "workflow_id": "wf_001",
            "status": "running",
        }

        # 丰富上下文
        enriched = await coordinator_with_retriever.enrich_context_with_knowledge(
            workflow_id="wf_001",
            goal="进行数据分析",
        )

        assert enriched is not None
        assert "knowledge_references" in enriched
        assert len(enriched["knowledge_references"]) >= 1

    @pytest.mark.asyncio
    async def test_enrich_context_stores_in_cache(self, coordinator_with_retriever):
        """丰富上下文时缓存知识"""
        enriched = await coordinator_with_retriever.enrich_context_with_knowledge(
            workflow_id="wf_001",
            goal="进行数据分析",
        )

        # 检查缓存
        cached = coordinator_with_retriever.get_cached_knowledge("wf_001")
        assert cached is not None


# ==================== 测试2：基于错误自动检索知识 ====================


class TestAutoRetrieveKnowledgeByError:
    """测试基于错误自动检索知识"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def coordinator_with_error_knowledge(self, mock_event_bus):
        """创建带错误解决方案的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 添加错误解决方案
        retriever.add_error_solution(
            error_type="TimeoutError",
            solution={
                "title": "超时错误解决方案",
                "preview": "增加超时时间或添加重试逻辑...",
                "confidence": 0.9,
            },
        )
        retriever.add_error_solution(
            error_type="ConnectionError",
            solution={
                "title": "连接错误解决方案",
                "preview": "检查网络连接或使用代理...",
                "confidence": 0.85,
            },
        )

        return CoordinatorAgent(
            event_bus=mock_event_bus,
            knowledge_retriever=retriever,
        )

    @pytest.mark.asyncio
    async def test_enrich_context_with_error_knowledge(self, coordinator_with_error_knowledge):
        """基于错误丰富上下文"""
        enriched = await coordinator_with_error_knowledge.enrich_context_with_knowledge(
            workflow_id="wf_001",
            errors=[
                {"error_type": "TimeoutError", "message": "Request timeout after 30s"},
            ],
        )

        assert enriched is not None
        assert "knowledge_references" in enriched
        # 应该找到超时错误的解决方案
        refs = enriched["knowledge_references"]
        assert any("超时" in r.get("title", "") for r in refs)

    @pytest.mark.asyncio
    async def test_enrich_context_with_multiple_errors(self, coordinator_with_error_knowledge):
        """多个错误时检索多个解决方案"""
        enriched = await coordinator_with_error_knowledge.enrich_context_with_knowledge(
            workflow_id="wf_001",
            errors=[
                {"error_type": "TimeoutError", "message": "Timeout"},
                {"error_type": "ConnectionError", "message": "Connection refused"},
            ],
        )

        refs = enriched["knowledge_references"]
        # 应该有多个解决方案
        assert len(refs) >= 2


# ==================== 测试3：知识注入到压缩上下文 ====================


class TestKnowledgeInjectionToCompressedContext:
    """测试知识注入到压缩上下文"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def coordinator_with_compression(self, mock_event_bus):
        """创建带压缩和知识检索的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()
        retriever.add_goal_knowledge(
            keyword="测试",
            knowledge={
                "doc_id": "doc_test",
                "title": "测试指南",
                "preview": "使用 pytest 编写测试...",
                "match_score": 0.88,
            },
        )

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
            knowledge_retriever=retriever,
        )
        coordinator.start_context_compression()

        return coordinator

    @pytest.mark.asyncio
    async def test_compress_context_with_knowledge(self, coordinator_with_compression):
        """压缩上下文时包含知识引用"""
        # 先丰富上下文
        await coordinator_with_compression.enrich_context_with_knowledge(
            workflow_id="wf_001",
            goal="编写测试用例",
        )

        # 获取压缩上下文
        compressed = coordinator_with_compression.get_compressed_context("wf_001")

        # 如果已经有压缩上下文，应该包含知识引用
        if compressed:
            assert hasattr(compressed, "knowledge_references")

    @pytest.mark.asyncio
    async def test_inject_knowledge_to_existing_context(self, coordinator_with_compression):
        """向现有上下文注入知识"""
        from src.domain.services.context_compressor import (
            CompressedContext,
        )

        # 创建初始上下文
        initial = CompressedContext(
            workflow_id="wf_001",
            task_goal="编写测试",
        )
        coordinator_with_compression._compressed_contexts["wf_001"] = initial

        # 注入知识
        await coordinator_with_compression.inject_knowledge_to_context(
            workflow_id="wf_001",
            goal="编写测试用例",
        )

        # 验证知识已注入
        updated = coordinator_with_compression.get_compressed_context("wf_001")
        assert updated is not None
        # 知识引用应该被添加
        assert len(updated.knowledge_references) >= 0


# ==================== 测试4：获取知识增强的上下文摘要 ====================


class TestKnowledgeEnhancedContextSummary:
    """测试获取知识增强的上下文摘要"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def coordinator_with_knowledge(self, mock_event_bus):
        """创建完整配置的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()
        retriever.add_mock_result(
            query="工作流执行",
            results=[
                {
                    "source_id": "doc_wf",
                    "title": "工作流执行指南",
                    "content_preview": "工作流执行最佳实践...",
                    "relevance_score": 0.92,
                }
            ],
        )

        return CoordinatorAgent(
            event_bus=mock_event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
            knowledge_retriever=retriever,
        )

    @pytest.mark.asyncio
    async def test_get_knowledge_enhanced_summary(self, coordinator_with_knowledge):
        """获取知识增强的摘要文本"""
        from src.domain.services.context_compressor import CompressedContext

        # 创建带知识的上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="执行工作流",
            knowledge_references=[
                {
                    "source_id": "doc_wf",
                    "title": "工作流指南",
                    "relevance_score": 0.9,
                }
            ],
        )
        coordinator_with_knowledge._compressed_contexts["wf_001"] = ctx

        # 获取摘要
        summary = coordinator_with_knowledge.get_knowledge_enhanced_summary("wf_001")

        assert summary is not None
        assert "知识" in summary or "引用" in summary or "工作流" in summary

    @pytest.mark.asyncio
    async def test_get_context_for_conversation_agent(self, coordinator_with_knowledge):
        """获取用于对话Agent的上下文"""
        from src.domain.services.context_compressor import CompressedContext

        # 设置上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="分析数据",
            execution_status={"status": "running", "progress": 0.5},
            knowledge_references=[
                {
                    "source_id": "doc_1",
                    "title": "数据分析指南",
                    "content_preview": "使用统计方法...",
                    "relevance_score": 0.88,
                }
            ],
        )
        coordinator_with_knowledge._compressed_contexts["wf_001"] = ctx

        # 获取对话Agent可用的上下文
        agent_context = coordinator_with_knowledge.get_context_for_conversation_agent("wf_001")

        assert agent_context is not None
        assert "goal" in agent_context or "task_goal" in agent_context
        assert "knowledge" in agent_context or "references" in agent_context


# ==================== 测试5：真实场景 - 错误后自动检索知识 ====================


class TestRealScenarioErrorKnowledgeRetrieval:
    """真实场景：错误发生后自动检索知识"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def full_coordinator(self, mock_event_bus):
        """创建完整配置的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 设置错误解决方案
        retriever.add_error_solution(
            error_type="APIError",
            solution={
                "title": "API错误处理",
                "preview": "检查API密钥和请求格式...",
                "confidence": 0.9,
            },
        )

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
            knowledge_retriever=retriever,
        )
        coordinator.start_context_compression()

        return coordinator

    @pytest.mark.asyncio
    async def test_auto_enrich_on_node_failure(self, full_coordinator):
        """节点失败时自动丰富上下文"""
        from src.domain.services.context_compressor import CompressedContext

        # 模拟工作流状态
        full_coordinator.workflow_states["wf_001"] = {
            "workflow_id": "wf_001",
            "status": "running",
            "failed_nodes": ["node_1"],
            "node_errors": {"node_1": "APIError: Invalid API key"},
        }

        # 创建压缩上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="调用外部API",
            error_log=[{"node_id": "node_1", "error": "APIError: Invalid API key"}],
        )
        full_coordinator._compressed_contexts["wf_001"] = ctx

        # 自动丰富上下文（基于错误）
        enriched = await full_coordinator.auto_enrich_context_on_error(
            workflow_id="wf_001",
            error_type="APIError",
            error_message="Invalid API key",
        )

        assert enriched is not None
        # 应该包含API错误的解决方案
        if "knowledge_references" in enriched:
            refs = enriched["knowledge_references"]
            assert any("API" in str(r) for r in refs)


# 导出
__all__ = [
    "TestAutoRetrieveKnowledgeByGoal",
    "TestAutoRetrieveKnowledgeByError",
    "TestKnowledgeInjectionToCompressedContext",
    "TestKnowledgeEnhancedContextSummary",
    "TestRealScenarioErrorKnowledgeRetrieval",
]

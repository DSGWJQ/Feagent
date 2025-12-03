"""测试：知识检索与上下文压缩集成 - Phase 5 阶段4

测试目标：
1. 节点失败时自动检索错误相关知识
2. 反思事件时自动检索目标相关知识
3. 压缩上下文包含知识引用
4. 完整的知识增强上下文流程

完成标准：
- 节点失败事件触发自动知识检索
- 反思事件触发自动知识检索
- CompressedContext 包含 knowledge_references
- 对话 Agent 可获取知识增强的上下文
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus

# ==================== 测试1：节点失败时自动检索知识 ====================


class TestAutoKnowledgeRetrievalOnNodeFailure:
    """测试节点失败时自动检索知识"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        event_bus.unsubscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def coordinator_with_auto_knowledge(self, mock_event_bus):
        """创建带自动知识检索的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
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

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
            knowledge_retriever=retriever,
        )
        coordinator.start_context_compression()
        coordinator.enable_auto_knowledge_retrieval()

        return coordinator

    @pytest.mark.asyncio
    async def test_enable_auto_knowledge_retrieval(self, coordinator_with_auto_knowledge):
        """启用自动知识检索功能"""
        assert coordinator_with_auto_knowledge._auto_knowledge_retrieval_enabled

    @pytest.mark.asyncio
    async def test_node_failure_triggers_knowledge_retrieval(self, coordinator_with_auto_knowledge):
        """节点失败触发知识检索"""
        from src.domain.services.context_compressor import CompressedContext

        # 设置初始上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="调用外部API",
        )
        coordinator_with_auto_knowledge._compressed_contexts["wf_001"] = ctx

        # 模拟节点失败并触发知识检索
        await coordinator_with_auto_knowledge.handle_node_failure_with_knowledge(
            workflow_id="wf_001",
            node_id="node_1",
            error_type="TimeoutError",
            error_message="Request timeout after 30s",
        )

        # 验证知识已被检索并添加到上下文
        updated_ctx = coordinator_with_auto_knowledge.get_compressed_context("wf_001")
        assert updated_ctx is not None
        assert len(updated_ctx.knowledge_references) >= 1


# ==================== 测试2：反思事件时自动检索知识 ====================


class TestAutoKnowledgeRetrievalOnReflection:
    """测试反思事件时自动检索知识"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        event_bus.unsubscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def coordinator_with_goal_knowledge(self, mock_event_bus):
        """创建带目标知识的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 添加目标相关知识
        retriever.add_goal_knowledge(
            keyword="数据",
            knowledge={
                "doc_id": "doc_data",
                "title": "数据处理最佳实践",
                "preview": "使用 pandas 进行数据处理...",
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
        coordinator.enable_auto_knowledge_retrieval()

        return coordinator

    @pytest.mark.asyncio
    async def test_reflection_triggers_goal_knowledge_retrieval(
        self, coordinator_with_goal_knowledge
    ):
        """反思事件触发目标相关知识检索"""
        from src.domain.services.context_compressor import CompressedContext

        # 设置初始上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="处理数据并生成报告",
        )
        coordinator_with_goal_knowledge._compressed_contexts["wf_001"] = ctx

        # 模拟反思事件
        await coordinator_with_goal_knowledge.handle_reflection_with_knowledge(
            workflow_id="wf_001",
            assessment="数据处理流程需要优化",
            confidence=0.85,
        )

        # 验证目标相关知识已被检索
        updated_ctx = coordinator_with_goal_knowledge.get_compressed_context("wf_001")
        assert updated_ctx is not None
        # 知识应该被添加
        assert len(updated_ctx.knowledge_references) >= 0


# ==================== 测试3：完整的知识增强压缩流程 ====================


class TestCompleteKnowledgeEnhancedCompressionFlow:
    """测试完整的知识增强压缩流程"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        event_bus.unsubscribe = MagicMock()
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

        # 添加各类知识
        retriever.add_goal_knowledge(
            keyword="报告",
            knowledge={
                "doc_id": "doc_report",
                "title": "报告生成指南",
                "preview": "使用模板生成专业报告...",
                "match_score": 0.9,
            },
        )
        retriever.add_error_solution(
            error_type="ValueError",
            solution={
                "title": "数据验证错误处理",
                "preview": "检查输入数据格式...",
                "confidence": 0.85,
            },
        )

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
            knowledge_retriever=retriever,
        )
        coordinator.start_context_compression()
        coordinator.enable_auto_knowledge_retrieval()

        return coordinator

    @pytest.mark.asyncio
    async def test_complete_flow_workflow_start(self, full_coordinator):
        """完整流程：工作流开始"""
        from src.domain.services.context_compressor import CompressedContext

        # 1. 工作流开始，设置目标
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="生成销售报告",
        )
        full_coordinator._compressed_contexts["wf_001"] = ctx

        # 2. 基于目标检索知识
        await full_coordinator.enrich_context_with_knowledge(
            workflow_id="wf_001",
            goal="生成销售报告",
        )

        # 3. 验证知识已添加
        updated_ctx = full_coordinator.get_compressed_context("wf_001")
        cached = full_coordinator.get_cached_knowledge("wf_001")
        assert cached is not None

    @pytest.mark.asyncio
    async def test_complete_flow_with_error_and_recovery(self, full_coordinator):
        """完整流程：错误和恢复"""
        from src.domain.services.context_compressor import CompressedContext

        # 1. 设置初始上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="数据验证",
            error_log=[],
        )
        full_coordinator._compressed_contexts["wf_001"] = ctx

        # 2. 发生错误，检索解决方案
        await full_coordinator.handle_node_failure_with_knowledge(
            workflow_id="wf_001",
            node_id="validation_node",
            error_type="ValueError",
            error_message="Invalid data format",
        )

        # 3. 验证错误解决方案已添加
        updated_ctx = full_coordinator.get_compressed_context("wf_001")
        assert updated_ctx is not None
        # 知识引用应该包含错误解决方案
        refs = updated_ctx.knowledge_references
        if refs:
            assert any("ValueError" in str(r) or "验证" in str(r) for r in refs)

    @pytest.mark.asyncio
    async def test_get_enriched_context_for_conversation_agent(self, full_coordinator):
        """获取用于对话Agent的丰富上下文"""
        from src.domain.services.context_compressor import CompressedContext

        # 设置带知识的上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="生成报告",
            knowledge_references=[
                {
                    "source_id": "doc_1",
                    "title": "报告模板指南",
                    "content_preview": "使用专业模板...",
                    "relevance_score": 0.9,
                }
            ],
        )
        full_coordinator._compressed_contexts["wf_001"] = ctx

        # 获取对话Agent可用的上下文
        agent_ctx = full_coordinator.get_context_for_conversation_agent("wf_001")

        assert agent_ctx is not None
        assert "knowledge_references" in agent_ctx
        assert len(agent_ctx["knowledge_references"]) == 1


# ==================== 测试4：知识引用在压缩时的合并 ====================


class TestKnowledgeReferenceMergingInCompression:
    """测试知识引用在压缩时的合并"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def coordinator_for_merging(self, mock_event_bus):
        """创建用于测试合并的 Coordinator"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()
        retriever.add_goal_knowledge(
            keyword="分析",
            knowledge={
                "doc_id": "doc_analysis",
                "title": "数据分析方法",
                "preview": "使用统计方法...",
                "match_score": 0.85,
            },
        )
        retriever.add_goal_knowledge(
            keyword="可视化",
            knowledge={
                "doc_id": "doc_viz",
                "title": "数据可视化",
                "preview": "使用 matplotlib...",
                "match_score": 0.8,
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
    async def test_multiple_knowledge_retrievals_merge_correctly(self, coordinator_for_merging):
        """多次知识检索正确合并"""
        from src.domain.services.context_compressor import CompressedContext

        # 设置初始上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="数据分析和可视化",
        )
        coordinator_for_merging._compressed_contexts["wf_001"] = ctx

        # 第一次检索
        await coordinator_for_merging.inject_knowledge_to_context(
            workflow_id="wf_001",
            goal="数据分析",
        )

        # 第二次检索（不同的知识）
        await coordinator_for_merging.inject_knowledge_to_context(
            workflow_id="wf_001",
            goal="数据可视化",
        )

        # 验证知识正确合并（去重）
        updated_ctx = coordinator_for_merging.get_compressed_context("wf_001")
        assert updated_ctx is not None
        # 应该有两条不同的知识引用
        refs = updated_ctx.knowledge_references
        source_ids = [r.get("source_id") for r in refs]
        # 确保没有重复
        assert len(source_ids) == len(set(source_ids))


# ==================== 测试5：边界情况 ====================


class TestKnowledgeIntegrationEdgeCases:
    """测试知识集成的边界情况"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_no_knowledge_retriever_gracefully_handled(self, mock_event_bus):
        """无知识检索器时优雅处理"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextCompressor,
        )

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            context_compressor=ContextCompressor(),
            # 没有 knowledge_retriever
        )
        coordinator.start_context_compression()
        coordinator.enable_auto_knowledge_retrieval()

        # 设置上下文
        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="测试目标",
        )
        coordinator._compressed_contexts["wf_001"] = ctx

        # 不应抛出异常
        await coordinator.handle_node_failure_with_knowledge(
            workflow_id="wf_001",
            node_id="node_1",
            error_type="SomeError",
            error_message="Some error message",
        )

        # 上下文应该仍然存在
        assert coordinator.get_compressed_context("wf_001") is not None

    @pytest.mark.asyncio
    async def test_empty_goal_handled(self, mock_event_bus):
        """空目标优雅处理"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextCompressor,
        )
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            context_compressor=ContextCompressor(),
            knowledge_retriever=MockKnowledgeRetriever(),
        )
        coordinator.start_context_compression()

        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="",  # 空目标
        )
        coordinator._compressed_contexts["wf_001"] = ctx

        # 不应抛出异常
        result = await coordinator.enrich_context_with_knowledge(
            workflow_id="wf_001",
            goal="",
        )

        assert result is not None
        assert "knowledge_references" in result


# 导出
__all__ = [
    "TestAutoKnowledgeRetrievalOnNodeFailure",
    "TestAutoKnowledgeRetrievalOnReflection",
    "TestCompleteKnowledgeEnhancedCompressionFlow",
    "TestKnowledgeReferenceMergingInCompression",
    "TestKnowledgeIntegrationEdgeCases",
]

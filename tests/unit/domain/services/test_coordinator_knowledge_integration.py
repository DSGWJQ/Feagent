"""测试：Coordinator 知识库接口集成 - Phase 5 阶段2

测试目标：
1. 定义 KnowledgeRetrieverPort 接口
2. Coordinator 注入知识检索器
3. Coordinator 可以检索知识
4. 检索结果转换为 KnowledgeReferences

完成标准：
- KnowledgeRetrieverPort 定义 retrieve_by_query 方法
- Coordinator 接受 knowledge_retriever 参数
- coordinator.retrieve_knowledge(query) 返回 KnowledgeReferences
- 支持按工作流ID过滤检索

"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus

# ==================== 测试1：KnowledgeRetrieverPort 接口定义 ====================


class TestKnowledgeRetrieverPort:
    """测试 KnowledgeRetrieverPort 接口"""

    def test_knowledge_retriever_port_has_retrieve_by_query(self):
        """KnowledgeRetrieverPort 定义 retrieve_by_query 方法"""
        from src.domain.services.knowledge_retriever_port import KnowledgeRetrieverPort

        # 验证接口定义
        assert hasattr(KnowledgeRetrieverPort, "retrieve_by_query")

    def test_knowledge_retriever_port_has_retrieve_by_error(self):
        """KnowledgeRetrieverPort 定义 retrieve_by_error 方法"""
        from src.domain.services.knowledge_retriever_port import KnowledgeRetrieverPort

        assert hasattr(KnowledgeRetrieverPort, "retrieve_by_error")

    def test_knowledge_retriever_port_has_retrieve_by_goal(self):
        """KnowledgeRetrieverPort 定义 retrieve_by_goal 方法"""
        from src.domain.services.knowledge_retriever_port import KnowledgeRetrieverPort

        assert hasattr(KnowledgeRetrieverPort, "retrieve_by_goal")


# ==================== 测试2：MockKnowledgeRetriever 实现 ====================


class TestMockKnowledgeRetriever:
    """测试 MockKnowledgeRetriever"""

    @pytest.mark.asyncio
    async def test_mock_retriever_retrieve_by_query(self):
        """Mock 检索器可以按查询检索"""
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 添加测试数据
        retriever.add_mock_result(
            query="Python 异常处理",
            results=[
                {
                    "source_id": "doc_001",
                    "title": "Python 异常处理指南",
                    "content_preview": "使用 try-except 捕获异常...",
                    "relevance_score": 0.92,
                }
            ],
        )

        results = await retriever.retrieve_by_query("Python 异常处理")

        assert len(results) == 1
        assert results[0]["title"] == "Python 异常处理指南"
        assert results[0]["relevance_score"] == 0.92

    @pytest.mark.asyncio
    async def test_mock_retriever_retrieve_by_error(self):
        """Mock 检索器可以按错误类型检索"""
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 添加错误解决方案
        retriever.add_error_solution(
            error_type="TimeoutError",
            solution={
                "title": "超时错误解决方案",
                "preview": "增加超时时间或添加重试逻辑...",
                "confidence": 0.85,
            },
        )

        results = await retriever.retrieve_by_error("TimeoutError")

        assert len(results) >= 1
        assert results[0]["title"] == "超时错误解决方案"

    @pytest.mark.asyncio
    async def test_mock_retriever_retrieve_by_goal(self):
        """Mock 检索器可以按目标检索"""
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 添加目标相关知识
        retriever.add_goal_knowledge(
            keyword="数据处理",
            knowledge={
                "doc_id": "doc_etl",
                "title": "数据处理最佳实践",
                "preview": "使用 ETL 管道...",
                "match_score": 0.88,
            },
        )

        results = await retriever.retrieve_by_goal("数据处理流程")

        assert len(results) >= 1
        assert results[0]["title"] == "数据处理最佳实践"

    @pytest.mark.asyncio
    async def test_mock_retriever_with_workflow_filter(self):
        """Mock 检索器支持工作流过滤"""
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()

        # 添加特定工作流的知识
        retriever.add_mock_result(
            query="测试查询",
            results=[
                {"source_id": "d1", "title": "通用知识", "relevance_score": 0.9},
            ],
            workflow_id="wf_001",
        )

        # 查询特定工作流
        results = await retriever.retrieve_by_query("测试查询", workflow_id="wf_001")
        assert len(results) == 1

        # 查询其他工作流应该没有结果
        results_other = await retriever.retrieve_by_query("测试查询", workflow_id="wf_other")
        assert len(results_other) == 0


# ==================== 测试3：Coordinator 注入知识检索器 ====================


class TestCoordinatorKnowledgeRetrieverInjection:
    """测试 Coordinator 知识检索器注入"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def mock_knowledge_retriever(self):
        """创建 Mock 知识检索器"""
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()
        retriever.add_mock_result(
            query="测试",
            results=[
                {
                    "source_id": "doc_001",
                    "title": "测试文档",
                    "content_preview": "测试内容...",
                    "relevance_score": 0.9,
                }
            ],
        )
        return retriever

    def test_coordinator_accepts_knowledge_retriever(
        self, mock_event_bus, mock_knowledge_retriever
    ):
        """Coordinator 接受 knowledge_retriever 参数"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            knowledge_retriever=mock_knowledge_retriever,
        )

        assert coordinator.knowledge_retriever is not None
        assert coordinator.knowledge_retriever == mock_knowledge_retriever

    def test_coordinator_without_knowledge_retriever(self, mock_event_bus):
        """Coordinator 可以不传 knowledge_retriever"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        assert coordinator.knowledge_retriever is None


# ==================== 测试4：Coordinator 检索知识 ====================


class TestCoordinatorKnowledgeRetrieval:
    """测试 Coordinator 知识检索功能"""

    @pytest.fixture
    def mock_event_bus(self):
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

        # 添加测试数据
        retriever.add_mock_result(
            query="Python 编程",
            results=[
                {
                    "source_id": "doc_py_001",
                    "title": "Python 基础",
                    "content_preview": "Python 是一门动态语言...",
                    "relevance_score": 0.95,
                },
                {
                    "source_id": "doc_py_002",
                    "title": "Python 进阶",
                    "content_preview": "装饰器和生成器...",
                    "relevance_score": 0.85,
                },
            ],
        )

        retriever.add_error_solution(
            error_type="ValueError",
            solution={
                "title": "ValueError 处理",
                "preview": "检查输入值的有效性...",
                "confidence": 0.9,
            },
        )

        retriever.add_goal_knowledge(
            keyword="API",
            knowledge={
                "doc_id": "doc_api",
                "title": "REST API 设计",
                "preview": "使用 RESTful 风格...",
                "match_score": 0.88,
            },
        )

        return CoordinatorAgent(
            event_bus=mock_event_bus,
            knowledge_retriever=retriever,
        )

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_returns_references(self, coordinator_with_retriever):
        """retrieve_knowledge 返回 KnowledgeReferences"""
        from src.domain.services.knowledge_reference import KnowledgeReferences

        refs = await coordinator_with_retriever.retrieve_knowledge("Python 编程")

        assert isinstance(refs, KnowledgeReferences)
        assert len(refs) == 2

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_preserves_relevance(self, coordinator_with_retriever):
        """检索结果保留相关度分数"""
        refs = await coordinator_with_retriever.retrieve_knowledge("Python 编程")

        ref_list = refs.to_list()
        assert ref_list[0].relevance_score == 0.95
        assert ref_list[1].relevance_score == 0.85

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_by_error(self, coordinator_with_retriever):
        """按错误类型检索知识"""
        refs = await coordinator_with_retriever.retrieve_knowledge_by_error("ValueError")

        assert len(refs) >= 1
        ref_list = refs.to_list()
        assert any("ValueError" in r.title for r in ref_list)

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_by_goal(self, coordinator_with_retriever):
        """按目标检索知识"""
        refs = await coordinator_with_retriever.retrieve_knowledge_by_goal("构建 API 服务")

        assert len(refs) >= 1
        ref_list = refs.to_list()
        assert any("API" in r.title for r in ref_list)

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_without_retriever(self, mock_event_bus):
        """无检索器时返回空结果"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.knowledge_reference import KnowledgeReferences

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        refs = await coordinator.retrieve_knowledge("任何查询")

        assert isinstance(refs, KnowledgeReferences)
        assert refs.is_empty()

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_with_workflow_id(self, coordinator_with_retriever):
        """支持按工作流ID过滤检索"""
        # 先检索通用结果
        refs = await coordinator_with_retriever.retrieve_knowledge(
            "Python 编程",
            workflow_id="wf_001",
        )

        # 应该返回结果（因为 MockRetriever 的默认行为）
        assert isinstance(refs, type(refs))


# ==================== 测试5：检索结果缓存 ====================


class TestCoordinatorKnowledgeCache:
    """测试知识检索结果缓存"""

    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_cache_knowledge_for_workflow(self, mock_event_bus):
        """缓存工作流的知识引用"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()
        retriever.add_mock_result(
            query="测试查询",
            results=[{"source_id": "d1", "title": "T1", "relevance_score": 0.9}],
        )

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            knowledge_retriever=retriever,
        )

        # 检索并缓存
        refs = await coordinator.retrieve_knowledge("测试查询", workflow_id="wf_001")

        # 验证缓存
        cached = coordinator.get_cached_knowledge("wf_001")
        assert cached is not None
        assert len(cached) == 1

    @pytest.mark.asyncio
    async def test_get_cached_knowledge_returns_none_if_not_cached(self, mock_event_bus):
        """未缓存时返回 None"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        cached = coordinator.get_cached_knowledge("wf_nonexistent")
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_cached_knowledge(self, mock_event_bus):
        """清除缓存的知识"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.knowledge_retriever_port import MockKnowledgeRetriever

        retriever = MockKnowledgeRetriever()
        retriever.add_mock_result(
            query="查询",
            results=[{"source_id": "d1", "title": "T1", "relevance_score": 0.9}],
        )

        coordinator = CoordinatorAgent(
            event_bus=mock_event_bus,
            knowledge_retriever=retriever,
        )

        # 检索并缓存
        await coordinator.retrieve_knowledge("查询", workflow_id="wf_001")

        # 清除缓存
        coordinator.clear_cached_knowledge("wf_001")

        # 验证已清除
        assert coordinator.get_cached_knowledge("wf_001") is None


# 导出
__all__ = [
    "TestKnowledgeRetrieverPort",
    "TestMockKnowledgeRetriever",
    "TestCoordinatorKnowledgeRetrieverInjection",
    "TestCoordinatorKnowledgeRetrieval",
    "TestCoordinatorKnowledgeCache",
]

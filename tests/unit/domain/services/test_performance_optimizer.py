"""性能优化模块测试

Phase 4.1: 性能优化 - TDD测试

测试覆盖:
- 并行执行优化器 (ParallelOptimizer)
- 上下文缓存 (ContextCache)
- 执行计划优化 (ExecutionPlanner)
- 结果聚合器 (ResultAggregator)
"""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest


class TestParallelOptimizer:
    """并行执行优化器测试"""

    @pytest.mark.asyncio
    async def test_identify_parallelizable_nodes(self):
        """测试：识别可并行执行的节点

        真实场景：
        - 工作流有多个独立分支
        - 节点间无数据依赖

        验收标准：
        - 正确识别无依赖关系的节点
        - 返回可并行执行的节点组
        """
        from src.domain.services.performance_optimizer import ParallelOptimizer

        optimizer = ParallelOptimizer()

        # 工作流定义: A -> B, A -> C (B和C可并行)
        workflow = {
            "nodes": ["A", "B", "C", "D"],
            "edges": [
                {"source": "A", "target": "B"},
                {"source": "A", "target": "C"},
                {"source": "B", "target": "D"},
                {"source": "C", "target": "D"},
            ],
        }

        parallel_groups = optimizer.identify_parallel_groups(workflow)

        # A先执行，然后B和C可并行，最后D
        assert len(parallel_groups) == 3
        assert parallel_groups[0] == ["A"]
        assert set(parallel_groups[1]) == {"B", "C"}
        assert parallel_groups[2] == ["D"]

    @pytest.mark.asyncio
    async def test_execute_nodes_in_parallel(self):
        """测试：并行执行多个节点

        真实场景：
        - 多个API调用节点可并行
        - 使用asyncio.gather提高效率

        验收标准：
        - 并行执行比串行快
        - 收集所有结果
        """
        from src.domain.services.performance_optimizer import ParallelOptimizer

        optimizer = ParallelOptimizer()

        # Mock执行器，每个节点执行100ms
        async def mock_execute(node_id: str) -> dict[str, Any]:
            await asyncio.sleep(0.1)
            return {"node": node_id, "result": f"output_{node_id}"}

        nodes = ["node_1", "node_2", "node_3"]

        start_time = time.time()
        results = await optimizer.execute_parallel(nodes, mock_execute)
        elapsed = time.time() - start_time

        # 并行执行应该在约100ms完成（而非300ms）
        assert elapsed < 0.2  # 允许一些开销
        assert len(results) == 3
        assert all(r["result"].startswith("output_") for r in results.values())

    @pytest.mark.asyncio
    async def test_parallel_execution_with_error_handling(self):
        """测试：并行执行的错误处理

        真实场景：
        - 部分节点执行失败
        - 需要收集成功和失败的结果

        验收标准：
        - 一个节点失败不影响其他节点
        - 错误被正确记录
        """
        from src.domain.services.performance_optimizer import ParallelOptimizer

        optimizer = ParallelOptimizer()

        call_count = 0

        async def mock_execute_with_error(node_id: str) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if node_id == "node_2":
                raise ValueError("模拟执行错误")
            return {"node": node_id, "success": True}

        nodes = ["node_1", "node_2", "node_3"]

        results = await optimizer.execute_parallel(nodes, mock_execute_with_error, fail_fast=False)

        # 所有节点都应该被尝试执行
        assert call_count == 3
        assert results["node_1"]["success"] is True
        assert results["node_3"]["success"] is True
        assert "error" in results["node_2"]

    @pytest.mark.asyncio
    async def test_execution_with_concurrency_limit(self):
        """测试：限制并发数

        真实场景：
        - API有速率限制
        - 需要限制同时执行的任务数

        验收标准：
        - 同时执行的任务不超过限制
        - 所有任务最终都会执行
        """
        from src.domain.services.performance_optimizer import ParallelOptimizer

        optimizer = ParallelOptimizer()

        concurrent_count = 0
        max_concurrent = 0

        async def mock_execute(node_id: str) -> dict[str, Any]:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return {"node": node_id}

        nodes = [f"node_{i}" for i in range(10)]

        results = await optimizer.execute_parallel(nodes, mock_execute, max_concurrency=3)

        assert len(results) == 10
        assert max_concurrent <= 3


class TestContextCache:
    """上下文缓存测试"""

    @pytest.mark.asyncio
    async def test_cache_node_output(self):
        """测试：缓存节点输出

        真实场景：
        - LLM调用结果缓存
        - 避免重复计算

        验收标准：
        - 相同输入返回缓存结果
        - 缓存命中率统计
        """
        from src.domain.services.performance_optimizer import ContextCache

        cache = ContextCache()

        # 第一次计算
        result1 = await cache.get_or_compute(
            key="llm_call_1", compute_fn=AsyncMock(return_value={"response": "Hello"})
        )

        # 第二次应该从缓存获取
        compute_fn = AsyncMock(return_value={"response": "Different"})
        result2 = await cache.get_or_compute(key="llm_call_1", compute_fn=compute_fn)

        assert result1 == result2
        assert result1["response"] == "Hello"
        # 第二次不应该调用compute_fn
        compute_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_with_ttl(self):
        """测试：带TTL的缓存

        真实场景：
        - 某些数据需要定期刷新
        - 知识库检索结果可能更新

        验收标准：
        - 过期后重新计算
        - TTL可配置
        """
        from src.domain.services.performance_optimizer import ContextCache

        cache = ContextCache(default_ttl=0.1)  # 100ms TTL

        # 第一次计算
        result1 = await cache.get_or_compute(
            key="knowledge_query", compute_fn=AsyncMock(return_value={"docs": ["doc1"]})
        )

        # 等待过期
        await asyncio.sleep(0.15)

        # 应该重新计算
        compute_fn = AsyncMock(return_value={"docs": ["doc2"]})
        result2 = await cache.get_or_compute(key="knowledge_query", compute_fn=compute_fn)

        compute_fn.assert_called_once()
        assert result2["docs"] == ["doc2"]

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """测试：缓存失效

        真实场景：
        - 用户更新了数据
        - 需要清除相关缓存

        验收标准：
        - 可按key失效
        - 可按模式失效
        """
        from src.domain.services.performance_optimizer import ContextCache

        cache = ContextCache()

        # 添加多个缓存
        await cache.get_or_compute("user_1_data", AsyncMock(return_value={"a": 1}))
        await cache.get_or_compute("user_2_data", AsyncMock(return_value={"b": 2}))
        await cache.get_or_compute("system_config", AsyncMock(return_value={"c": 3}))

        # 按key失效
        cache.invalidate("user_1_data")

        # 按模式失效
        cache.invalidate_pattern("user_*")

        # user_1_data和user_2_data应该被清除
        assert not cache.has("user_1_data")
        assert not cache.has("user_2_data")
        assert cache.has("system_config")

    @pytest.mark.asyncio
    async def test_cache_size_limit(self):
        """测试：缓存大小限制

        真实场景：
        - 内存有限
        - 需要LRU淘汰策略

        验收标准：
        - 超出限制时淘汰最旧的
        - 保持最近使用的
        """
        from src.domain.services.performance_optimizer import ContextCache

        cache = ContextCache(max_size=3)

        # 添加4个缓存项
        for i in range(4):
            await cache.get_or_compute(f"key_{i}", AsyncMock(return_value={"i": i}))

        # 最早的key_0应该被淘汰
        assert not cache.has("key_0")
        assert cache.has("key_1")
        assert cache.has("key_2")
        assert cache.has("key_3")


class TestExecutionPlanner:
    """执行计划优化器测试"""

    @pytest.mark.asyncio
    async def test_create_optimized_execution_plan(self):
        """测试：创建优化的执行计划

        真实场景：
        - 复杂工作流需要优化执行顺序
        - 最大化并行度

        验收标准：
        - 生成正确的执行计划
        - 计划包含并行组
        """
        from src.domain.services.performance_optimizer import ExecutionPlanner

        planner = ExecutionPlanner()

        workflow = {
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "fetch_a", "type": "api"},
                {"id": "fetch_b", "type": "api"},
                {"id": "process", "type": "llm"},
                {"id": "end", "type": "end"},
            ],
            "edges": [
                {"source": "start", "target": "fetch_a"},
                {"source": "start", "target": "fetch_b"},
                {"source": "fetch_a", "target": "process"},
                {"source": "fetch_b", "target": "process"},
                {"source": "process", "target": "end"},
            ],
        }

        plan = planner.create_plan(workflow)

        assert plan.total_stages == 4
        assert plan.stages[0].nodes == ["start"]
        assert set(plan.stages[1].nodes) == {"fetch_a", "fetch_b"}
        assert plan.stages[1].parallel is True
        assert plan.stages[2].nodes == ["process"]
        assert plan.stages[3].nodes == ["end"]

    @pytest.mark.asyncio
    async def test_estimate_execution_time(self):
        """测试：预估执行时间

        真实场景：
        - 用户想知道工作流需要多长时间
        - 基于历史数据预估

        验收标准：
        - 考虑并行执行
        - 给出合理预估
        """
        from src.domain.services.performance_optimizer import ExecutionPlanner

        planner = ExecutionPlanner()

        # 设置节点类型的平均执行时间
        planner.set_node_time_estimate("api", 1.0)
        planner.set_node_time_estimate("llm", 2.0)

        workflow = {
            "nodes": [
                {"id": "fetch_a", "type": "api"},
                {"id": "fetch_b", "type": "api"},
                {"id": "process", "type": "llm"},
            ],
            "edges": [
                {"source": "fetch_a", "target": "process"},
                {"source": "fetch_b", "target": "process"},
            ],
        }

        plan = planner.create_plan(workflow)
        estimated_time = planner.estimate_time(plan)

        # fetch_a和fetch_b并行执行(1s) + process(2s) = 3s
        assert estimated_time == 3.0

    @pytest.mark.asyncio
    async def test_plan_with_conditional_branches(self):
        """测试：带条件分支的执行计划

        真实场景：
        - 工作流有条件判断
        - 不同分支的优化策略不同

        验收标准：
        - 识别条件节点
        - 各分支独立优化
        """
        from src.domain.services.performance_optimizer import ExecutionPlanner

        planner = ExecutionPlanner()

        workflow = {
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "condition", "type": "condition"},
                {"id": "branch_a", "type": "api"},
                {"id": "branch_b", "type": "api"},
                {"id": "end", "type": "end"},
            ],
            "edges": [
                {"source": "start", "target": "condition"},
                {"source": "condition", "target": "branch_a", "condition": "true"},
                {"source": "condition", "target": "branch_b", "condition": "false"},
                {"source": "branch_a", "target": "end"},
                {"source": "branch_b", "target": "end"},
            ],
        }

        plan = planner.create_plan(workflow)

        # 条件分支应该被识别
        assert plan.has_conditional_branches is True
        assert "condition" in [s.nodes[0] for s in plan.stages if len(s.nodes) == 1]


class TestResultAggregator:
    """结果聚合器测试"""

    @pytest.mark.asyncio
    async def test_aggregate_parallel_results(self):
        """测试：聚合并行执行结果

        真实场景：
        - 多个API调用并行返回
        - 需要合并为统一输出

        验收标准：
        - 按节点ID组织结果
        - 保持数据完整性
        """
        from src.domain.services.performance_optimizer import ResultAggregator

        aggregator = ResultAggregator()

        results = {
            "api_1": {"data": [1, 2, 3]},
            "api_2": {"data": [4, 5, 6]},
            "api_3": {"data": [7, 8, 9]},
        }

        aggregated = aggregator.aggregate(results)

        assert "api_1" in aggregated
        assert "api_2" in aggregated
        assert "api_3" in aggregated
        assert aggregated["api_1"]["data"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_aggregate_with_merge_strategy(self):
        """测试：使用合并策略聚合结果

        真实场景：
        - 多个知识库检索结果需要合并
        - 按相关度排序

        验收标准：
        - 支持多种合并策略
        - 结果正确排序
        """
        from src.domain.services.performance_optimizer import MergeStrategy, ResultAggregator

        aggregator = ResultAggregator()

        results = {
            "kb_1": {"documents": [{"id": "doc1", "score": 0.9}, {"id": "doc2", "score": 0.7}]},
            "kb_2": {"documents": [{"id": "doc3", "score": 0.8}, {"id": "doc4", "score": 0.6}]},
        }

        merged = aggregator.merge(
            results, field="documents", strategy=MergeStrategy.SORTED_BY_SCORE, top_k=3
        )

        # 应该按score排序并取top 3
        assert len(merged["documents"]) == 3
        assert merged["documents"][0]["id"] == "doc1"  # 0.9
        assert merged["documents"][1]["id"] == "doc3"  # 0.8
        assert merged["documents"][2]["id"] == "doc2"  # 0.7

    @pytest.mark.asyncio
    async def test_aggregate_with_error_results(self):
        """测试：处理包含错误的结果

        真实场景：
        - 部分节点执行失败
        - 需要区分成功和失败

        验收标准：
        - 分离成功和失败结果
        - 提供错误摘要
        """
        from src.domain.services.performance_optimizer import ResultAggregator

        aggregator = ResultAggregator()

        results = {
            "api_1": {"data": "success"},
            "api_2": {"error": "timeout"},
            "api_3": {"data": "success"},
        }

        aggregated = aggregator.aggregate_with_errors(results)

        assert len(aggregated.successes) == 2
        assert len(aggregated.failures) == 1
        assert "api_2" in aggregated.failures
        assert aggregated.error_summary == "1 of 3 nodes failed"


class TestRealWorldScenarios:
    """真实业务场景测试"""

    @pytest.mark.asyncio
    async def test_parallel_api_calls_with_caching(self):
        """测试：带缓存的并行API调用

        真实业务场景：
        - 客服系统需要同时查询多个知识库
        - 相同查询应该使用缓存

        验收标准：
        - 首次调用并行执行
        - 重复调用命中缓存
        - 性能显著提升
        """
        from src.domain.services.performance_optimizer import ContextCache, ParallelOptimizer

        cache = ContextCache()
        optimizer = ParallelOptimizer()

        call_count = 0

        async def query_knowledge_base(kb_id: str) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 模拟API延迟
            return {"kb": kb_id, "docs": [f"doc from {kb_id}"]}

        async def cached_query(kb_id: str) -> dict[str, Any]:
            return await cache.get_or_compute(
                f"kb_query_{kb_id}", lambda: query_knowledge_base(kb_id)
            )

        # 第一次查询
        kb_ids = ["kb_1", "kb_2", "kb_3"]
        start = time.time()
        results1 = await optimizer.execute_parallel(kb_ids, cached_query)
        time1 = time.time() - start

        # 第二次查询（应该命中缓存）
        start = time.time()
        results2 = await optimizer.execute_parallel(kb_ids, cached_query)
        time2 = time.time() - start

        # 第一次应该实际调用3次
        assert call_count == 3
        # 第二次应该几乎瞬间完成（从缓存）
        assert time2 < time1 * 0.1
        # 结果应该相同
        assert results1 == results2

    @pytest.mark.asyncio
    async def test_optimized_workflow_execution(self):
        """测试：优化的工作流执行

        真实业务场景：
        - 复杂客服工作流
        - 并行检索 + LLM处理 + 结果合并

        验收标准：
        - 执行计划正确
        - 并行执行有效
        - 总执行时间优化
        """
        from src.domain.services.performance_optimizer import (
            ExecutionPlanner,
            ParallelOptimizer,
            ResultAggregator,
        )

        planner = ExecutionPlanner()
        optimizer = ParallelOptimizer()
        aggregator = ResultAggregator()

        # 模拟执行函数
        async def execute_node(node_id: str) -> dict[str, Any]:
            await asyncio.sleep(0.05)  # 50ms per node
            return {"node": node_id, "output": f"result_{node_id}"}

        # 定义工作流
        workflow = {
            "nodes": [
                {"id": "query_kb1", "type": "knowledge"},
                {"id": "query_kb2", "type": "knowledge"},
                {"id": "query_kb3", "type": "knowledge"},
                {"id": "merge", "type": "transform"},
                {"id": "llm_response", "type": "llm"},
            ],
            "edges": [
                {"source": "query_kb1", "target": "merge"},
                {"source": "query_kb2", "target": "merge"},
                {"source": "query_kb3", "target": "merge"},
                {"source": "merge", "target": "llm_response"},
            ],
        }

        # 创建执行计划
        plan = planner.create_plan(workflow)

        # 执行各阶段
        start = time.time()
        all_results = {}

        for stage in plan.stages:
            if stage.parallel:
                stage_results = await optimizer.execute_parallel(stage.nodes, execute_node)
            else:
                stage_results = {}
                for node_id in stage.nodes:
                    stage_results[node_id] = await execute_node(node_id)

            all_results.update(stage_results)

        elapsed = time.time() - start

        # 3个并行查询(50ms) + merge(50ms) + llm(50ms) = ~150ms
        # 如果串行则需要 50ms * 5 = 250ms
        assert elapsed < 0.2
        assert len(all_results) == 5

    @pytest.mark.asyncio
    async def test_cache_warming_for_frequent_queries(self):
        """测试：预热频繁查询的缓存

        真实业务场景：
        - 系统启动时预热常用数据
        - 减少首次请求延迟

        验收标准：
        - 批量预热成功
        - 后续查询命中缓存
        """
        from src.domain.services.performance_optimizer import ContextCache

        cache = ContextCache()

        # 预热数据
        frequent_queries = [
            ("faq_greeting", {"response": "您好，有什么可以帮您？"}),
            ("faq_hours", {"response": "我们的营业时间是9:00-18:00"}),
            ("faq_contact", {"response": "客服电话：400-xxx-xxxx"}),
        ]

        await cache.warm_up(frequent_queries)

        # 验证缓存命中
        compute_fn = AsyncMock(return_value={"response": "should not be called"})

        for key, expected in frequent_queries:
            result = await cache.get_or_compute(key, compute_fn)
            assert result == expected

        # compute_fn不应该被调用
        compute_fn.assert_not_called()


class TestPerformanceOptimizerFactory:
    """性能优化器工厂测试"""

    def test_create_with_default_config(self):
        """测试：使用默认配置创建优化器"""
        from src.domain.services.performance_optimizer import PerformanceOptimizerFactory

        optimizer = PerformanceOptimizerFactory.create()

        assert optimizer.parallel_optimizer is not None
        assert optimizer.cache is not None
        assert optimizer.planner is not None
        assert optimizer.aggregator is not None

    def test_create_with_custom_config(self):
        """测试：使用自定义配置创建优化器"""
        from src.domain.services.performance_optimizer import PerformanceOptimizerFactory

        config = {"cache_ttl": 300, "cache_max_size": 1000, "max_concurrency": 10}

        optimizer = PerformanceOptimizerFactory.create(config)

        assert optimizer.cache.default_ttl == 300
        assert optimizer.cache.max_size == 1000
        assert optimizer.parallel_optimizer.max_concurrency == 10

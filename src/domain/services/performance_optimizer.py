"""性能优化模块（Performance Optimizer）

Phase 4.1: 性能优化

组件：
- ParallelOptimizer: 并行执行优化器
- ContextCache: 上下文缓存
- ExecutionPlanner: 执行计划优化器
- ResultAggregator: 结果聚合器
- PerformanceOptimizerFactory: 工厂类

功能：
- 识别可并行执行的节点
- 带TTL的缓存机制
- LRU淘汰策略
- 执行计划优化
- 结果合并策略

设计原则：
- 透明优化：不改变执行语义
- 可配置：支持自定义参数
- 可观测：提供性能指标

"""

import asyncio
import fnmatch
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MergeStrategy(Enum):
    """合并策略枚举"""

    CONCAT = "concat"  # 简单拼接
    SORTED_BY_SCORE = "sorted_by_score"  # 按分数排序
    DEDUPLICATE = "deduplicate"  # 去重


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    created_at: float
    ttl: float | None = None
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


@dataclass
class ExecutionStage:
    """执行阶段"""

    nodes: list[str]
    parallel: bool = False


@dataclass
class ExecutionPlan:
    """执行计划"""

    stages: list[ExecutionStage]
    has_conditional_branches: bool = False
    node_types: dict[str, str] = field(default_factory=dict)

    @property
    def total_stages(self) -> int:
        return len(self.stages)


@dataclass
class AggregatedResult:
    """聚合结果"""

    successes: dict[str, Any]
    failures: dict[str, Any]
    error_summary: str


class ParallelOptimizer:
    """并行执行优化器

    优化工作流执行，识别并行机会，控制并发度。

    使用示例：
        optimizer = ParallelOptimizer()
        results = await optimizer.execute_parallel(nodes, execute_fn)
    """

    def __init__(self, max_concurrency: int = 10):
        """初始化

        参数：
            max_concurrency: 默认最大并发数
        """
        self.max_concurrency = max_concurrency

    def identify_parallel_groups(self, workflow: dict[str, Any]) -> list[list[str]]:
        """识别可并行执行的节点组

        使用拓扑排序，将无依赖关系的节点分组。

        参数：
            workflow: 工作流定义，包含nodes和edges

        返回：
            节点组列表，每组内的节点可并行执行
        """
        nodes = workflow.get("nodes", [])
        edges = workflow.get("edges", [])

        # 如果nodes是字典列表，提取ID
        if nodes and isinstance(nodes[0], dict):
            node_ids = [n["id"] for n in nodes]
        else:
            node_ids = nodes

        # 构建入度表和邻接表
        in_degree = {node: 0 for node in node_ids}
        adjacency = {node: [] for node in node_ids}

        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            if target in in_degree:
                in_degree[target] += 1
            if source in adjacency:
                adjacency[source].append(target)

        # 分层拓扑排序
        groups = []
        remaining = set(node_ids)

        while remaining:
            # 找出当前所有入度为0的节点
            current_group = [node for node in remaining if in_degree.get(node, 0) == 0]

            if not current_group:
                # 有循环依赖，取任意节点打破
                current_group = [next(iter(remaining))]

            groups.append(current_group)

            # 更新入度
            for node in current_group:
                remaining.discard(node)
                for neighbor in adjacency.get(node, []):
                    if neighbor in in_degree:
                        in_degree[neighbor] -= 1

        return groups

    async def execute_parallel(
        self,
        nodes: list[str],
        execute_fn: Callable[[str], Any],
        fail_fast: bool = True,
        max_concurrency: int | None = None,
    ) -> dict[str, Any]:
        """并行执行节点

        参数：
            nodes: 节点ID列表
            execute_fn: 执行函数
            fail_fast: 是否快速失败
            max_concurrency: 最大并发数

        返回：
            节点ID到结果的字典
        """
        concurrency = max_concurrency or self.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)
        results = {}

        async def execute_with_semaphore(node_id: str):
            async with semaphore:
                try:
                    result = await execute_fn(node_id)
                    return node_id, result
                except Exception as e:
                    logger.error(f"节点执行失败 {node_id}: {e}")
                    return node_id, {"error": str(e)}

        # 创建任务
        tasks = [execute_with_semaphore(node) for node in nodes]

        if fail_fast:
            # 快速失败模式
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            for item in completed:
                if isinstance(item, Exception):
                    continue
                node_id, result = item
                results[node_id] = result
        else:
            # 收集所有结果（包括错误）
            completed = await asyncio.gather(*tasks, return_exceptions=False)
            for node_id, result in completed:
                results[node_id] = result

        return results


class ContextCache:
    """上下文缓存

    支持TTL、LRU淘汰、模式失效的缓存系统。

    使用示例：
        cache = ContextCache(default_ttl=300)
        result = await cache.get_or_compute("key", compute_fn)
    """

    def __init__(self, default_ttl: float | None = None, max_size: int = 1000):
        """初始化

        参数：
            default_ttl: 默认TTL（秒），None表示永不过期
            max_size: 最大缓存条目数
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    async def get_or_compute(
        self, key: str, compute_fn: Callable[[], Any], ttl: float | None = None
    ) -> Any:
        """获取缓存或计算

        参数：
            key: 缓存键
            compute_fn: 计算函数（未命中时调用）
            ttl: 可选的TTL覆盖

        返回：
            缓存或计算的值
        """
        # 检查缓存
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                self._hits += 1
                entry.last_accessed = time.time()
                # 移动到末尾（LRU）
                self._cache.move_to_end(key)
                return entry.value
            else:
                # 过期，删除
                del self._cache[key]

        # 未命中，计算
        self._misses += 1
        value = await compute_fn()

        # 存储
        entry_ttl = ttl if ttl is not None else self.default_ttl
        self._cache[key] = CacheEntry(value=value, created_at=time.time(), ttl=entry_ttl)

        # 检查大小限制
        self._evict_if_needed()

        return value

    def has(self, key: str) -> bool:
        """检查键是否存在（且未过期）"""
        if key not in self._cache:
            return False
        entry = self._cache[key]
        if entry.is_expired():
            del self._cache[key]
            return False
        return True

    def invalidate(self, key: str) -> bool:
        """失效指定键

        参数：
            key: 缓存键

        返回：
            是否成功删除
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def invalidate_pattern(self, pattern: str) -> int:
        """按模式失效

        参数：
            pattern: glob模式，如 "user_*"

        返回：
            删除的条目数
        """
        keys_to_delete = [key for key in self._cache.keys() if fnmatch.fnmatch(key, pattern)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)

    async def warm_up(self, entries: list[tuple[str, Any]]) -> None:
        """预热缓存

        参数：
            entries: (key, value) 元组列表
        """
        for key, value in entries:
            self._cache[key] = CacheEntry(value=value, created_at=time.time(), ttl=self.default_ttl)

    def _evict_if_needed(self) -> None:
        """如果超出大小限制，淘汰最旧的条目"""
        while len(self._cache) > self.max_size:
            # OrderedDict.popitem(last=False) 移除最旧的
            self._cache.popitem(last=False)

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


class ExecutionPlanner:
    """执行计划优化器

    分析工作流，生成优化的执行计划。

    使用示例：
        planner = ExecutionPlanner()
        plan = planner.create_plan(workflow)
    """

    def __init__(self):
        """初始化"""
        self._node_time_estimates: dict[str, float] = {}

    def set_node_time_estimate(self, node_type: str, seconds: float) -> None:
        """设置节点类型的预估执行时间

        参数：
            node_type: 节点类型
            seconds: 预估秒数
        """
        self._node_time_estimates[node_type] = seconds

    def create_plan(self, workflow: dict[str, Any]) -> ExecutionPlan:
        """创建执行计划

        参数：
            workflow: 工作流定义

        返回：
            优化的执行计划
        """
        nodes = workflow.get("nodes", [])
        edges = workflow.get("edges", [])

        # 构建节点ID到类型的映射
        node_types = {}
        for node in nodes:
            if isinstance(node, dict):
                node_types[node.get("id", "")] = node.get("type", "")

        # 检查是否有条件分支
        has_conditional = any(edge.get("condition") is not None for edge in edges)

        # 检查是否有条件节点
        if not has_conditional:
            has_conditional = any(
                n.get("type") == "condition" for n in nodes if isinstance(n, dict)
            )

        # 使用并行优化器识别并行组
        optimizer = ParallelOptimizer()
        groups = optimizer.identify_parallel_groups(workflow)

        # 转换为执行阶段
        stages = []
        for group in groups:
            stage = ExecutionStage(nodes=group, parallel=len(group) > 1)
            stages.append(stage)

        return ExecutionPlan(
            stages=stages, has_conditional_branches=has_conditional, node_types=node_types
        )

    def estimate_time(self, plan: ExecutionPlan) -> float:
        """预估执行时间

        参数：
            plan: 执行计划

        返回：
            预估的总执行时间（秒）
        """
        total_time = 0.0

        for stage in plan.stages:
            if stage.parallel:
                # 并行阶段，取最长的
                stage_time = 0.0
                for node_id in stage.nodes:
                    node_time = self._get_node_time(node_id, plan.node_types)
                    stage_time = max(stage_time, node_time)
            else:
                # 串行阶段，累加
                stage_time = sum(
                    self._get_node_time(node_id, plan.node_types) for node_id in stage.nodes
                )

            total_time += stage_time

        return total_time

    def _get_node_time(self, node_id: str, node_types: dict[str, str]) -> float:
        """获取节点的预估时间"""
        # 优先从节点类型映射中获取
        node_type = node_types.get(node_id, "")
        if node_type and node_type in self._node_time_estimates:
            return self._node_time_estimates[node_type]

        # 回退：尝试从节点ID推断类型
        for type_name, time_est in self._node_time_estimates.items():
            if type_name in node_id:
                return time_est

        return 1.0  # 默认1秒


class ResultAggregator:
    """结果聚合器

    合并并行执行的结果，支持多种策略。

    使用示例：
        aggregator = ResultAggregator()
        merged = aggregator.merge(results, "documents", MergeStrategy.SORTED_BY_SCORE)
    """

    def aggregate(self, results: dict[str, Any]) -> dict[str, Any]:
        """简单聚合结果

        参数：
            results: 节点ID到结果的字典

        返回：
            聚合后的结果
        """
        return results.copy()

    def merge(
        self, results: dict[str, Any], field: str, strategy: MergeStrategy, top_k: int | None = None
    ) -> dict[str, Any]:
        """按策略合并结果

        参数：
            results: 节点ID到结果的字典
            field: 要合并的字段名
            strategy: 合并策略
            top_k: 保留前k个

        返回：
            合并后的结果
        """
        # 收集所有字段值
        all_items = []
        for result in results.values():
            items = result.get(field, [])
            all_items.extend(items)

        # 应用策略
        if strategy == MergeStrategy.SORTED_BY_SCORE:
            all_items.sort(key=lambda x: x.get("score", 0), reverse=True)
        elif strategy == MergeStrategy.DEDUPLICATE:
            seen = set()
            unique_items = []
            for item in all_items:
                item_id = item.get("id", str(item))
                if item_id not in seen:
                    seen.add(item_id)
                    unique_items.append(item)
            all_items = unique_items

        # 应用top_k
        if top_k is not None:
            all_items = all_items[:top_k]

        return {field: all_items}

    def aggregate_with_errors(self, results: dict[str, Any]) -> AggregatedResult:
        """区分成功和失败的聚合

        参数：
            results: 节点ID到结果的字典

        返回：
            包含成功、失败和摘要的聚合结果
        """
        successes = {}
        failures = {}

        for node_id, result in results.items():
            if isinstance(result, dict) and "error" in result:
                failures[node_id] = result
            else:
                successes[node_id] = result

        total = len(results)
        failed_count = len(failures)

        if failed_count == 0:
            error_summary = "All nodes succeeded"
        else:
            error_summary = f"{failed_count} of {total} nodes failed"

        return AggregatedResult(successes=successes, failures=failures, error_summary=error_summary)


@dataclass
class PerformanceOptimizer:
    """性能优化器集合"""

    parallel_optimizer: ParallelOptimizer
    cache: ContextCache
    planner: ExecutionPlanner
    aggregator: ResultAggregator


class PerformanceOptimizerFactory:
    """性能优化器工厂

    创建和配置性能优化器。

    使用示例：
        optimizer = PerformanceOptimizerFactory.create(config)
    """

    @staticmethod
    def create(config: dict[str, Any] | None = None) -> PerformanceOptimizer:
        """创建性能优化器

        参数：
            config: 可选的配置字典
                - cache_ttl: 缓存TTL
                - cache_max_size: 缓存最大大小
                - max_concurrency: 最大并发数

        返回：
            性能优化器实例
        """
        config = config or {}

        cache_ttl = config.get("cache_ttl")
        cache_max_size = config.get("cache_max_size", 1000)
        max_concurrency = config.get("max_concurrency", 10)

        parallel_optimizer = ParallelOptimizer(max_concurrency=max_concurrency)

        cache = ContextCache(default_ttl=cache_ttl, max_size=cache_max_size)

        planner = ExecutionPlanner()
        aggregator = ResultAggregator()

        return PerformanceOptimizer(
            parallel_optimizer=parallel_optimizer,
            cache=cache,
            planner=planner,
            aggregator=aggregator,
        )


# 导出
__all__ = [
    "ParallelOptimizer",
    "ContextCache",
    "ExecutionPlanner",
    "ExecutionPlan",
    "ExecutionStage",
    "ResultAggregator",
    "AggregatedResult",
    "MergeStrategy",
    "PerformanceOptimizer",
    "PerformanceOptimizerFactory",
]

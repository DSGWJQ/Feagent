"""SafetyGuard - DAG 规则构建器

Phase 35.2: 从 CoordinatorAgent 提取 DAG 验证规则构建方法。

提供：
1. DagRuleBuilder: DAG 结构验证规则构建器
2. CycleDetector: Kahn 算法循环检测器
"""

from collections import Counter, deque
from typing import Any

from src.domain.services.safety_guard.rules import Rule


class CycleDetector:
    """循环检测器（使用 Kahn 算法）

    提供静态方法检测有向图中的循环依赖。
    """

    @staticmethod
    def detect_cycle_kahn(nodes: list[dict], edges: list[dict]) -> tuple[bool, list[str]]:
        """使用 Kahn's 算法检测循环依赖

        参数：
            nodes: 节点列表
            edges: 边列表

        返回：
            (是否有循环, 涉及循环的节点列表)
        """
        # 构建邻接表和入度表
        graph: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}

        for node in nodes:
            node_id = node.get("node_id")
            if node_id:
                graph[node_id] = []
                in_degree[node_id] = 0

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target and source in graph and target in graph:
                graph[source].append(target)
                in_degree[target] += 1

        # Kahn's 算法 (使用 deque 优化性能)
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        visited = []

        while queue:
            node_id = queue.popleft()
            visited.append(node_id)

            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否所有节点都被访问
        has_cycle = len(visited) != len(nodes)
        if has_cycle:
            unvisited = [
                node.get("node_id", "") for node in nodes if node.get("node_id") not in visited
            ]
            return True, unvisited

        return False, []


class DagRuleBuilder:
    """DAG 验证规则构建器

    负责构建 DAG（有向无环图）结构验证规则：
    - 节点 ID 唯一性
    - 边引用的节点存在性
    - 无循环依赖（使用 Kahn 算法）

    使用示例：
        builder = DagRuleBuilder()
        rule = builder.build_dag_validation_rule()
        coordinator.add_rule(rule)
    """

    def build_dag_validation_rule(self) -> Rule:
        """构建 DAG（有向无环图）验证规则

        验证工作流的节点和边结构：
        - 节点 ID 唯一性
        - 边引用的节点存在性
        - 无循环依赖

        返回：
            Rule: 验证规则
        """

        def condition(decision: dict[str, Any]) -> bool:
            # 只验证工作流规划决策
            if decision.get("action_type") != "create_workflow_plan":
                return True

            nodes = decision.get("nodes", [])
            edges = decision.get("edges", [])

            dag_errors = []

            # 1. 检查节点 ID 唯一性 (使用 Counter 优化性能)
            node_ids = [node.get("node_id") for node in nodes if "node_id" in node]
            if len(node_ids) != len(set(node_ids)):
                node_id_counts = Counter(node_ids)
                duplicates = [nid for nid, count in node_id_counts.items() if count > 1]
                dag_errors.append(f"节点 ID 重复: {', '.join(duplicates)}")

            node_id_set = set(node_ids)

            # 2. 检查边引用的节点存在性
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")

                if source and source not in node_id_set:
                    dag_errors.append(f"边的源节点 {source} 不存在")

                if target and target not in node_id_set:
                    dag_errors.append(f"边的目标节点 {target} 不存在")

            # 3. 检测循环依赖（使用 Kahn's 算法拓扑排序）
            # 即使有节点引用错误，也进行循环检测以报告所有问题
            if nodes and edges:
                has_cycle, unvisited = CycleDetector.detect_cycle_kahn(nodes, edges)
                if has_cycle:
                    dag_errors.append(f"工作流存在循环依赖，涉及节点: {', '.join(unvisited)}")

            if dag_errors:
                decision["_dag_errors"] = dag_errors
                return False

            return True

        rule = Rule(
            id="dag_validation",
            name="DAG 结构验证",
            condition=condition,
            priority=5,
            error_message=lambda d: "; ".join(d.get("_dag_errors", [])),
        )

        return rule


__all__ = ["DagRuleBuilder", "CycleDetector"]

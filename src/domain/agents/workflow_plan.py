"""工作流规划 (WorkflowPlan) - Phase 8.2

业务定义：
- 工作流规划是 ConversationAgent 产出的完整规划
- 包含多个节点定义和它们之间的连接关系
- 支持验证、循环检测、拓扑排序

设计原则：
- 完整性：包含所有节点和边
- 可验证：支持完整性和循环检测
- 可执行：提供拓扑执行顺序

使用示例：
    plan = WorkflowPlan(
        name="数据处理流程",
        goal="处理并分析数据",
        nodes=[node1, node2, node3],
        edges=[edge1, edge2],
    )
    errors = plan.validate()
    order = plan.get_execution_order()
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from src.domain.agents.node_definition import NodeDefinition


@dataclass
class EdgeDefinition:
    """边定义

    表示两个节点之间的连接关系。

    属性：
        source_node: 源节点名称
        target_node: 目标节点名称
        condition: 可选的条件表达式
    """

    source_node: str
    target_node: str
    condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "source_node": self.source_node,
            "target_node": self.target_node,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EdgeDefinition":
        """从字典反序列化"""
        return cls(
            source_node=data.get("source_node", ""),
            target_node=data.get("target_node", ""),
            condition=data.get("condition"),
        )


@dataclass
class WorkflowPlan:
    """工作流规划

    ConversationAgent 产出的完整规划，包含节点定义和连接关系。

    属性：
        id: 规划唯一标识
        name: 规划名称
        description: 规划描述
        goal: 对应的用户目标
        nodes: 节点定义列表
        edges: 边定义列表
    """

    name: str
    goal: str
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    nodes: list[NodeDefinition] = field(default_factory=list)
    edges: list[EdgeDefinition] = field(default_factory=list)

    def validate(self) -> list[str]:
        """验证规划完整性

        检查：
        1. 所有节点定义是否有效
        2. 边引用的节点是否存在

        返回：
            错误列表，空列表表示验证通过
        """
        errors = []

        # 获取所有节点名称
        node_names = {node.name for node in self.nodes}

        # 1. 验证每个节点定义
        for node in self.nodes:
            node_errors = node.validate()
            for err in node_errors:
                errors.append(f"节点 '{node.name}': {err}")

        # 2. 验证边引用的节点是否存在
        for edge in self.edges:
            if edge.source_node not in node_names:
                errors.append(f"边的源节点 '{edge.source_node}' 不存在")
            if edge.target_node not in node_names:
                errors.append(f"边的目标节点 (target) '{edge.target_node}' 不存在")

        return errors

    def has_circular_dependency(self) -> bool:
        """检测是否有循环依赖

        使用 DFS 检测有向图中的环。

        返回：
            True 如果存在循环依赖
        """
        # 构建邻接表
        graph: dict[str, list[str]] = {node.name: [] for node in self.nodes}
        for edge in self.edges:
            if edge.source_node in graph:
                graph[edge.source_node].append(edge.target_node)

        # DFS 检测环
        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(graph, WHITE)

        def dfs(node: str) -> bool:
            if color[node] == GRAY:
                return True  # 发现后向边，存在环
            if color[node] == BLACK:
                return False  # 已经完成访问

            color[node] = GRAY
            for neighbor in graph.get(node, []):
                if neighbor in color and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        for node in graph:
            if color[node] == WHITE:
                if dfs(node):
                    return True

        return False

    def get_execution_order(self) -> list[str]:
        """获取拓扑执行顺序

        使用 Kahn 算法进行拓扑排序。

        返回：
            按拓扑顺序排列的节点名称列表

        抛出：
            ValueError: 如果存在循环依赖
        """
        # 构建入度表和邻接表
        in_degree: dict[str, int] = {node.name: 0 for node in self.nodes}
        adjacency: dict[str, list[str]] = {node.name: [] for node in self.nodes}

        for edge in self.edges:
            if edge.source_node in adjacency and edge.target_node in in_degree:
                adjacency[edge.source_node].append(edge.target_node)
                in_degree[edge.target_node] += 1

        # Kahn 算法
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否有环
        if len(result) != len(self.nodes):
            raise ValueError("工作流存在循环依赖 (Circular dependency detected)")

        return result

    def get_node_by_name(self, name: str) -> NodeDefinition | None:
        """通过名称获取节点

        参数：
            name: 节点名称

        返回：
            节点定义，不存在时返回 None
        """
        for node in self.nodes:
            if node.name == name:
                return node
        return None

    def get_root_nodes(self) -> list[NodeDefinition]:
        """获取根节点（没有入边的节点）

        返回：
            根节点列表
        """
        # 找出所有有入边的节点
        nodes_with_incoming = {edge.target_node for edge in self.edges}

        # 返回没有入边的节点
        return [node for node in self.nodes if node.name not in nodes_with_incoming]

    def get_leaf_nodes(self) -> list[NodeDefinition]:
        """获取叶子节点（没有出边的节点）

        返回：
            叶子节点列表
        """
        # 找出所有有出边的节点
        nodes_with_outgoing = {edge.source_node for edge in self.edges}

        # 返回没有出边的节点
        return [node for node in self.nodes if node.name not in nodes_with_outgoing]

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典

        返回：
            包含完整规划的字典
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowPlan":
        """从字典反序列化

        参数：
            data: 包含规划的字典

        返回：
            WorkflowPlan 实例
        """
        nodes = [NodeDefinition.from_dict(n) for n in data.get("nodes", [])]
        edges = [EdgeDefinition.from_dict(e) for e in data.get("edges", [])]

        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            goal=data.get("goal", ""),
            nodes=nodes,
            edges=edges,
        )


# 导出
__all__ = [
    "EdgeDefinition",
    "WorkflowPlan",
]

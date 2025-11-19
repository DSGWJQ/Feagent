"""WorkflowExecutor（工作流执行器）

Domain 层服务：负责执行工作流

职责：
- 拓扑排序节点（按依赖顺序执行）
- 执行节点（HTTP、Transform、Conditional 等）
- 管理节点间的数据流
- 错误处理

为什么是 Domain 服务？
- 工作流执行是核心业务逻辑
- 不依赖任何基础设施（HTTP 客户端、数据库等）
- 纯 Python 实现
"""

from collections import defaultdict, deque
from typing import Any

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType


class WorkflowExecutor:
    """工作流执行器

    使用拓扑排序执行工作流节点

    属性：
        execution_log: 执行日志（记录每个节点的执行结果）
    """

    def __init__(self):
        self.execution_log: list[dict[str, Any]] = []
        self._node_outputs: dict[str, Any] = {}  # 存储每个节点的输出

    def execute(self, workflow: Workflow, initial_input: Any = None) -> Any:
        """执行工作流

        参数：
            workflow: 工作流实体
            initial_input: 初始输入（传递给 Start 节点）

        返回：
            工作流执行结果（End 节点的输出）

        异常：
            DomainError: 工作流包含环或其他执行错误
        """
        # 1. 拓扑排序
        sorted_nodes = self._topological_sort(workflow)

        # 2. 按顺序执行节点
        for node in sorted_nodes:
            # 获取节点的输入（来自前驱节点的输出）
            inputs = self._get_node_inputs(node, workflow)

            # 执行节点
            output = self._execute_node(node, inputs, initial_input)

            # 存储节点输出
            self._node_outputs[node.id] = output

            # 记录执行日志
            self.execution_log.append(
                {
                    "node_id": node.id,
                    "node_type": node.type.value,
                    "output": output,
                }
            )

        # 3. 返回 End 节点的输出
        end_node = next((n for n in sorted_nodes if n.type == NodeType.END), None)
        if end_node:
            return self._node_outputs.get(end_node.id)

        return None

    def _topological_sort(self, workflow: Workflow) -> list[Node]:
        """拓扑排序节点

        使用 Kahn 算法进行拓扑排序

        参数：
            workflow: 工作流实体

        返回：
            排序后的节点列表

        异常：
            DomainError: 工作流包含环
        """
        # 构建邻接表和入度表
        adj_list = defaultdict(list)
        in_degree = {node.id: 0 for node in workflow.nodes}

        for edge in workflow.edges:
            adj_list[edge.source_node_id].append(edge.target_node_id)
            in_degree[edge.target_node_id] += 1

        # Kahn 算法
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        sorted_node_ids = []

        while queue:
            node_id = queue.popleft()
            sorted_node_ids.append(node_id)

            for neighbor in adj_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否有环
        if len(sorted_node_ids) != len(workflow.nodes):
            raise DomainError("工作流包含环，无法执行")

        # 转换为 Node 对象
        node_map = {node.id: node for node in workflow.nodes}
        return [node_map[node_id] for node_id in sorted_node_ids]

    def _get_node_inputs(self, node: Node, workflow: Workflow) -> list[Any]:
        """获取节点的输入

        参数：
            node: 当前节点
            workflow: 工作流实体

        返回：
            输入列表（来自前驱节点的输出）
        """
        # 找到所有指向当前节点的边
        incoming_edges = [edge for edge in workflow.edges if edge.target_node_id == node.id]

        # 获取前驱节点的输出
        inputs = []
        for edge in incoming_edges:
            source_output = self._node_outputs.get(edge.source_node_id)
            inputs.append(source_output)

        return inputs

    def _execute_node(self, node: Node, inputs: list[Any], initial_input: Any = None) -> Any:
        """执行单个节点

        参数：
            node: 节点实体
            inputs: 输入列表
            initial_input: 初始输入（仅用于 Start 节点）

        返回：
            节点输出
        """
        # React Flow 默认节点类型（兼容处理）
        if node.type == NodeType.INPUT:
            # INPUT 节点等同于 START 节点
            return initial_input

        elif node.type == NodeType.OUTPUT:
            # OUTPUT 节点等同于 END 节点
            return inputs[0] if inputs else None

        elif node.type == NodeType.DEFAULT:
            # DEFAULT 节点：传递输入到输出
            return inputs[0] if inputs else None

        # 基础节点类型
        elif node.type == NodeType.START:
            return initial_input

        elif node.type == NodeType.END:
            # End 节点返回第一个输入
            return inputs[0] if inputs else None

        elif node.type == NodeType.HTTP:
            # HTTP 节点：暂时返回模拟数据
            # TODO: 实际实现需要调用 HTTP 客户端
            return {"status": "success", "data": "mock_http_response"}

        elif node.type == NodeType.TRANSFORM:
            # Transform 节点：暂时返回第一个输入
            # TODO: 实际实现需要执行转换逻辑
            return inputs[0] if inputs else None

        elif node.type == NodeType.CONDITIONAL:
            # Conditional 节点：暂时返回 True
            # TODO: 实际实现需要评估条件表达式
            condition = node.config.get("condition", "")
            # 简单模拟：如果条件包含 "test"，返回 True
            return "test" in condition

        elif node.type == NodeType.LLM:
            # LLM 节点：暂时返回模拟数据
            # TODO: 实际实现需要调用 LLM API
            return {"text": "mock_llm_response"}

        else:
            # 其他节点类型：返回第一个输入
            return inputs[0] if inputs else None

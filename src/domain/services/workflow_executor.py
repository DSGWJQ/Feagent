"""WorkflowExecutor（工作流执行器）

Domain 层服务：负责执行工作流

职责：
- 拓扑排序节点（按依赖顺序执行）
- 执行节点（通过 NodeExecutor 接口）
- 管理节点间的数据流
- 错误处理

为什么是 Domain 服务？
- 工作流执行是核心业务逻辑
- 通过 Port 接口与 Infrastructure 层解耦
- 纯业务逻辑实现
"""

from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.value_objects.node_type import NodeType


class WorkflowExecutor:
    """工作流执行器

    使用拓扑排序执行工作流节点

    属性：
        execution_log: 执行日志（记录每个节点的执行结果）
        executor_registry: 节点执行器注册表
    """

    def __init__(self, executor_registry: NodeExecutorRegistry | None = None):
        self.execution_log: list[dict[str, Any]] = []
        self._node_outputs: dict[str, Any] = {}  # 存储每个节点的输出
        self._executor_registry = executor_registry
        self._event_callback: Callable[[str, dict[str, Any]], None] | None = None

    def set_event_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """设置事件回调函数

        用于 SSE 流式返回执行状态

        参数：
            callback: 回调函数，接收事件类型和数据
        """
        self._event_callback = callback

    async def execute(self, workflow: Workflow, initial_input: Any = None) -> Any:
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

        # 2. 准备执行上下文
        context = {"initial_input": initial_input}

        # 3. 按顺序执行节点
        for node in sorted_nodes:
            # 发送节点开始事件
            if self._event_callback:
                self._event_callback(
                    "node_start",
                    {
                        "node_id": node.id,
                        "node_type": node.type.value,
                    },
                )

            try:
                # 获取节点的输入（来自前驱节点的输出）
                inputs = self._get_node_inputs(node, workflow)

                # 执行节点
                output = await self._execute_node(node, inputs, context)

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

                # 发送节点完成事件
                if self._event_callback:
                    self._event_callback(
                        "node_complete",
                        {
                            "node_id": node.id,
                            "node_type": node.type.value,
                            "output": output,
                        },
                    )

            except Exception as e:
                # 发送节点错误事件
                if self._event_callback:
                    self._event_callback(
                        "node_error",
                        {
                            "node_id": node.id,
                            "node_type": node.type.value,
                            "error": str(e),
                        },
                    )
                raise

        # 4. 返回 End 节点的输出
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

    def _get_node_inputs(self, node: Node, workflow: Workflow) -> dict[str, Any]:
        """获取节点的输入

        参数：
            node: 当前节点
            workflow: 工作流实体

        返回：
            输入字典（key 为源节点 ID，value 为输出）
        """
        # 找到所有指向当前节点的边
        incoming_edges = [edge for edge in workflow.edges if edge.target_node_id == node.id]

        # 获取前驱节点的输出
        inputs = {}
        for edge in incoming_edges:
            source_output = self._node_outputs.get(edge.source_node_id)
            inputs[edge.source_node_id] = source_output

        return inputs

    async def _execute_node(
        self, node: Node, inputs: dict[str, Any], context: dict[str, Any]
    ) -> Any:
        """执行单个节点

        参数：
            node: 节点实体
            inputs: 输入字典
            context: 执行上下文

        返回：
            节点输出
        """
        # 如果有注册的执行器，使用执行器
        if self._executor_registry:
            executor = self._executor_registry.get(node.type.value)
            if executor:
                return await executor.execute(node, inputs, context)

        # 回退到默认实现（兼容旧代码）
        # React Flow 默认节点类型（兼容处理）
        if node.type == NodeType.INPUT:
            # INPUT 节点等同于 START 节点
            return context.get("initial_input")

        elif node.type == NodeType.OUTPUT:
            # OUTPUT 节点等同于 END 节点
            return next(iter(inputs.values())) if inputs else None

        elif node.type == NodeType.DEFAULT:
            # DEFAULT 节点：传递输入到输出
            return next(iter(inputs.values())) if inputs else None

        # 基础节点类型
        elif node.type == NodeType.START:
            return context.get("initial_input")

        elif node.type == NodeType.END:
            # End 节点返回第一个输入
            return next(iter(inputs.values())) if inputs else None

        elif node.type == NodeType.HTTP:
            # HTTP 节点：返回模拟数据
            return {"status": "success", "data": "mock_http_response"}

        elif node.type == NodeType.TRANSFORM:
            # Transform 节点：返回第一个输入
            return next(iter(inputs.values())) if inputs else None

        elif node.type == NodeType.CONDITIONAL:
            # Conditional 节点：返回 True
            condition = node.config.get("condition", "")
            return "test" in condition

        elif node.type == NodeType.LLM:
            # LLM 节点：返回模拟数据
            return {"text": "mock_llm_response"}

        else:
            # 其他节点类型：返回第一个输入
            return next(iter(inputs.values())) if inputs else None

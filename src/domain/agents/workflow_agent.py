"""工作流Agent (WorkflowAgent) - 多Agent协作系统的"执行者"

业务定义：
- 工作流Agent负责节点执行、工作流管理、画布同步
- 接收对话Agent的决策，执行具体操作
- 管理工作流的DAG结构和执行状态

设计原则：
- 节点通过NodeFactory创建
- 工作流按拓扑顺序执行
- 执行状态通过事件同步
- 节点间通过WorkflowContext传递数据

核心能力：
- 节点管理：创建、配置、连接节点
- 工作流执行：按DAG顺序执行节点
- 状态同步：将执行状态同步到画布
- 结果汇报：向对话Agent反馈执行结果
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from src.domain.services.context_manager import WorkflowContext
from src.domain.services.event_bus import Event, EventBus
from src.domain.services.node_registry import Node, NodeFactory, NodeType


class ExecutionStatus(str, Enum):
    """执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Edge:
    """工作流边

    连接两个节点，表示数据流向。

    属性：
    - id: 边唯一标识
    - source_id: 源节点ID
    - target_id: 目标节点ID
    - condition: 可选的条件表达式
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    source_id: str = ""
    target_id: str = ""
    condition: str | None = None


@dataclass
class WorkflowExecutionStartedEvent(Event):
    """工作流执行开始事件"""

    workflow_id: str = ""
    node_count: int = 0


@dataclass
class WorkflowExecutionCompletedEvent(Event):
    """工作流执行完成事件"""

    workflow_id: str = ""
    status: str = "completed"
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecutionEvent(Event):
    """节点执行事件"""

    node_id: str = ""
    node_type: str = ""
    status: str = ""  # running, completed, failed
    result: dict[str, Any] | None = None
    error: str | None = None


class NodeExecutor(Protocol):
    """节点执行器接口"""

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行节点"""
        ...


class WorkflowAgent:
    """工作流Agent

    职责：
    1. 管理工作流节点和边
    2. 执行工作流（按拓扑顺序）
    3. 发布执行状态事件
    4. 处理对话Agent的决策

    使用示例：
        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=executor,
            event_bus=event_bus
        )
        node = agent.create_node(decision)
        agent.add_node(node)
        result = await agent.execute_workflow()
    """

    def __init__(
        self,
        workflow_context: WorkflowContext,
        node_factory: NodeFactory,
        node_executor: NodeExecutor | None = None,
        event_bus: EventBus | None = None,
    ):
        """初始化工作流Agent

        参数：
            workflow_context: 工作流上下文
            node_factory: 节点工厂
            node_executor: 节点执行器（可选）
            event_bus: 事件总线（可选）
        """
        self.workflow_context = workflow_context
        self.node_factory = node_factory
        self.node_executor = node_executor
        self.event_bus = event_bus

        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._execution_status = ExecutionStatus.PENDING

    @property
    def nodes(self) -> list[Node]:
        """获取所有节点"""
        return list(self._nodes.values())

    @property
    def edges(self) -> list[Edge]:
        """获取所有边"""
        return self._edges.copy()

    def create_node(self, decision: dict[str, Any]) -> Node:
        """根据决策创建节点

        参数：
            decision: 决策字典，包含node_type和config

        返回：
            创建的节点
        """
        node_type_str = decision.get("node_type", "GENERIC")
        config = decision.get("config", {})

        # 转换节点类型
        try:
            node_type = NodeType(node_type_str.lower())
        except ValueError:
            node_type = NodeType.GENERIC

        # 使用工厂创建节点
        node = self.node_factory.create(node_type, config)

        return node

    def add_node(self, node: Node) -> None:
        """添加节点到工作流

        参数：
            node: 要添加的节点
        """
        self._nodes[node.id] = node

    def get_node(self, node_id: str) -> Node | None:
        """根据ID获取节点

        参数：
            node_id: 节点ID

        返回：
            节点，如果不存在返回None
        """
        return self._nodes.get(node_id)

    def connect_nodes(self, source_id: str, target_id: str, condition: str | None = None) -> Edge:
        """连接两个节点

        参数：
            source_id: 源节点ID
            target_id: 目标节点ID
            condition: 可选的条件表达式

        返回：
            创建的边
        """
        edge = Edge(source_id=source_id, target_id=target_id, condition=condition)
        self._edges.append(edge)
        return edge

    async def execute_node(self, node_id: str) -> dict[str, Any]:
        """执行单个节点

        参数：
            node_id: 节点ID

        返回：
            执行结果
        """
        node = self._nodes.get(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        # 获取节点输入（从上游节点输出）
        inputs = self._collect_node_inputs(node_id)

        # 发布节点开始执行事件
        if self.event_bus:
            await self.event_bus.publish(
                NodeExecutionEvent(
                    source="workflow_agent",
                    node_id=node_id,
                    node_type=node.type.value,
                    status="running",
                )
            )

        # 执行节点
        if self.node_executor:
            result = await self.node_executor.execute(node_id, node.config, inputs)
        else:
            # 默认执行器（用于测试）
            result = {"status": "success", "executed": True}

        # 存储节点输出到上下文
        self.workflow_context.set_node_output(node_id, result)

        # 发布节点执行完成事件
        if self.event_bus:
            await self.event_bus.publish(
                NodeExecutionEvent(
                    source="workflow_agent",
                    node_id=node_id,
                    node_type=node.type.value,
                    status="completed",
                    result=result,
                )
            )

        return result

    def _collect_node_inputs(self, node_id: str) -> dict[str, Any]:
        """收集节点的输入

        从上游节点的输出中收集输入。

        参数：
            node_id: 节点ID

        返回：
            输入字典
        """
        inputs = {}

        # 找到所有指向该节点的边
        for edge in self._edges:
            if edge.target_id == node_id:
                # 获取源节点的输出
                source_output = self.workflow_context.get_node_output(edge.source_id)
                if source_output:
                    inputs[edge.source_id] = source_output

        return inputs

    async def execute_workflow(self) -> dict[str, Any]:
        """执行整个工作流

        按拓扑顺序执行所有节点。

        返回：
            执行结果
        """
        self._execution_status = ExecutionStatus.RUNNING

        # 发布工作流开始执行事件
        if self.event_bus:
            await self.event_bus.publish(
                WorkflowExecutionStartedEvent(
                    source="workflow_agent",
                    workflow_id=self.workflow_context.workflow_id,
                    node_count=len(self._nodes),
                )
            )

        try:
            # 获取拓扑排序的节点顺序
            execution_order = self._topological_sort()

            results = {}
            for node_id in execution_order:
                result = await self.execute_node(node_id)
                results[node_id] = result

            self._execution_status = ExecutionStatus.COMPLETED

            # 发布工作流完成事件
            if self.event_bus:
                await self.event_bus.publish(
                    WorkflowExecutionCompletedEvent(
                        source="workflow_agent",
                        workflow_id=self.workflow_context.workflow_id,
                        status="completed",
                        result=results,
                    )
                )

            return {"status": "completed", "results": results}

        except Exception as e:
            self._execution_status = ExecutionStatus.FAILED
            return {"status": "failed", "error": str(e)}

    def _topological_sort(self) -> list[str]:
        """对节点进行拓扑排序

        返回：
            按拓扑顺序排列的节点ID列表
        """
        # 构建邻接表和入度表
        in_degree = {node_id: 0 for node_id in self._nodes}
        adjacency = {node_id: [] for node_id in self._nodes}

        for edge in self._edges:
            if edge.source_id in adjacency and edge.target_id in in_degree:
                adjacency[edge.source_id].append(edge.target_id)
                in_degree[edge.target_id] += 1

        # Kahn算法
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 如果结果数量不等于节点数，说明有环
        if len(result) != len(self._nodes):
            raise ValueError("Workflow contains a cycle")

        return result

    async def handle_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """处理决策

        参数：
            decision: 决策字典

        返回：
            处理结果
        """
        decision_type = decision.get("decision_type", "")

        if decision_type == "create_node":
            node = self.create_node(
                {
                    "node_type": decision.get("node_type", "GENERIC"),
                    "config": decision.get("config", {}),
                }
            )
            self.add_node(node)
            return {"success": True, "node_id": node.id, "node_type": node.type.value}

        elif decision_type == "execute_workflow":
            result = await self.execute_workflow()
            return {
                "success": result["status"] == "completed",
                "status": result["status"],
                "results": result.get("results", {}),
            }

        elif decision_type == "connect_nodes":
            edge = self.connect_nodes(
                decision.get("source_id", ""),
                decision.get("target_id", ""),
                decision.get("condition"),
            )
            return {"success": True, "edge_id": edge.id}

        else:
            return {"success": False, "error": f"Unknown decision type: {decision_type}"}


# 导出
__all__ = [
    "ExecutionStatus",
    "Edge",
    "WorkflowExecutionStartedEvent",
    "WorkflowExecutionCompletedEvent",
    "NodeExecutionEvent",
    "NodeExecutor",
    "WorkflowAgent",
]

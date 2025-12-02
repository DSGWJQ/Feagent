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
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from src.domain.services.context_manager import WorkflowContext
from src.domain.services.event_bus import Event, EventBus
from src.domain.services.node_hierarchy_service import NodeHierarchyService
from src.domain.services.node_registry import Node, NodeFactory, NodeType


@dataclass
class CustomNodeType:
    """自定义节点类型定义"""

    type_name: str
    schema: dict[str, Any]
    executor_class: type | None = None


if TYPE_CHECKING:
    from src.domain.agents.node_definition import NodeDefinition
    from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan


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

        # 层级节点服务
        self.hierarchy_service = NodeHierarchyService(event_bus=event_bus)

        # 自定义节点类型存储
        self._custom_node_types: dict[str, CustomNodeType] = {}
        # 自定义节点执行器实例缓存
        self._custom_executors: dict[str, Any] = {}

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
            decision: 决策字典，包含node_type、config、parent_id、collapsed、children

        返回：
            创建的节点
        """
        node_type_str = decision.get("node_type", "GENERIC")
        config = decision.get("config", {})
        parent_id = decision.get("parent_id")
        collapsed = decision.get("collapsed")  # None 表示使用默认值
        children_defs = decision.get("children", [])

        # 检查是否是自定义节点类型
        if node_type_str.lower() in self._custom_node_types:
            custom_type = self._custom_node_types[node_type_str.lower()]
            # 验证配置
            self._validate_custom_node_config(custom_type, config)
            # 创建节点，使用 GENERIC 类型但保存原始类型名
            node = self.node_factory.create(NodeType.GENERIC, config)
            node.config["_custom_type"] = node_type_str.lower()
        else:
            # 转换预定义节点类型
            try:
                node_type = NodeType(node_type_str.lower())
            except ValueError:
                node_type = NodeType.GENERIC

            # 使用工厂创建节点
            node = self.node_factory.create(node_type, config)

        # 设置父节点ID
        if parent_id:
            node.parent_id = parent_id

        # 设置折叠状态
        if collapsed is not None:
            node.collapsed = collapsed

        # 处理内联子节点
        for child_def in children_defs:
            child = self.create_node(child_def)
            child.parent_id = node.id
            node.add_child(child)

        return node

    def _validate_custom_node_config(
        self, custom_type: CustomNodeType, config: dict[str, Any]
    ) -> None:
        """验证自定义节点配置

        参数：
            custom_type: 自定义节点类型定义
            config: 节点配置

        抛出：
            ValueError: 配置验证失败
        """
        for field_name, field_schema in custom_type.schema.items():
            if field_schema.get("required", False) and field_name not in config:
                raise ValueError(
                    f"Required field '{field_name}' is missing / 必填字段 '{field_name}' 缺失"
                )

    def add_node(self, node: Node) -> None:
        """添加节点到工作流

        参数：
            node: 要添加的节点
        """
        # 添加到 _nodes
        self._nodes[node.id] = node

        # 注册到层级服务
        self.hierarchy_service.register_node(node)

        # 如果有父节点，更新父子关系
        if node.parent_id:
            parent = self._nodes.get(node.parent_id)
            if parent and node not in parent.children:
                parent.add_child(node)

        # 递归添加子节点
        for child in node.children:
            if child.id not in self._nodes:
                self._nodes[child.id] = child
                self.hierarchy_service.register_node(child)

    def get_node(self, node_id: str) -> Node | None:
        """根据ID获取节点

        参数：
            node_id: 节点ID

        返回：
            节点，如果不存在返回None
        """
        return self._nodes.get(node_id)

    def get_root_nodes(self) -> list[Node]:
        """获取所有根节点（无父节点的节点）

        返回：
            根节点列表
        """
        return [node for node in self._nodes.values() if node.parent_id is None]

    def get_node_tree(self, node_id: str) -> dict[str, Any]:
        """获取节点的完整树结构

        参数：
            node_id: 节点ID

        返回：
            树结构字典
        """
        node = self._nodes.get(node_id)
        if not node:
            return {}

        return node.to_dict()

    def get_flat_nodes_with_hierarchy(self) -> list[dict[str, Any]]:
        """扁平化节点列表并保留层级信息

        返回：
            包含层级信息的节点列表
        """
        result = []

        def calculate_depth(node: Node) -> int:
            """计算节点深度"""
            depth = 0
            current_id = node.parent_id
            while current_id:
                depth += 1
                parent = self._nodes.get(current_id)
                current_id = parent.parent_id if parent else None
            return depth

        for node in self._nodes.values():
            result.append(
                {
                    "id": node.id,
                    "type": node.type.value,
                    "config": node.config,
                    "parent_id": node.parent_id,
                    "depth": calculate_depth(node),
                    "collapsed": node.collapsed,
                    "children_count": len(node.children),
                }
            )

        return result

    # ========== 自定义节点类型方法 ==========

    def define_custom_node_type(
        self,
        type_name: str,
        schema: dict[str, Any],
        executor_class: type | None = None,
    ) -> None:
        """定义自定义节点类型

        参数：
            type_name: 类型名称
            schema: 配置 schema
            executor_class: 可选的执行器类
        """
        custom_type = CustomNodeType(
            type_name=type_name.lower(),
            schema=schema,
            executor_class=executor_class,
        )
        self._custom_node_types[type_name.lower()] = custom_type

        # 如果有执行器类，创建实例
        if executor_class:
            self._custom_executors[type_name.lower()] = executor_class()

    def has_node_type(self, type_name: str) -> bool:
        """检查节点类型是否存在

        参数：
            type_name: 类型名称

        返回：
            是否存在
        """
        # 检查预定义类型
        try:
            NodeType(type_name.lower())
            return True
        except ValueError:
            pass

        # 检查自定义类型
        return type_name.lower() in self._custom_node_types

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
        # 检查是否是自定义节点类型
        custom_type_name = node.config.get("_custom_type")
        if custom_type_name and custom_type_name in self._custom_executors:
            # 使用自定义执行器
            executor = self._custom_executors[custom_type_name]
            result = await executor.execute(node.config, inputs)
        elif self.node_executor:
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
        in_degree = dict.fromkeys(self._nodes, 0)
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
                    "parent_id": decision.get("parent_id"),
                    "collapsed": decision.get("collapsed"),
                    "children": decision.get("children", []),
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

        elif decision_type == "create_workflow_plan":
            # 从决策创建工作流规划
            plan_dict = {
                "name": decision.get("name", ""),
                "goal": decision.get("goal", ""),
                "nodes": decision.get("nodes", []),
                "edges": decision.get("edges", []),
            }
            result = await self.execute_plan_from_dict(plan_dict)
            return {
                "success": result["status"] == "completed",
                "status": result["status"],
                "nodes_created": result.get("nodes_created", 0),
                "edges_created": result.get("edges_created", 0),
            }

        elif decision_type == "modify_node":
            node_id = decision.get("node_id", "")
            config = decision.get("config", {})
            return self.modify_node(node_id, config)

        elif decision_type == "toggle_collapse":
            node_id = decision.get("node_id", "")
            node = self.get_node(node_id)
            if node:
                node.collapsed = not node.collapsed
                return {"success": True, "node_id": node_id, "collapsed": node.collapsed}
            return {"success": False, "error": f"Node not found: {node_id}"}

        elif decision_type == "move_node":
            node_id = decision.get("node_id", "")
            new_parent_id = decision.get("new_parent_id")
            node = self.get_node(node_id)
            if not node:
                return {"success": False, "error": f"Node not found: {node_id}"}

            # 从旧父节点移除
            if node.parent_id:
                old_parent = self.get_node(node.parent_id)
                if old_parent:
                    old_parent.remove_child(node_id)

            # 添加到新父节点
            if new_parent_id:
                new_parent = self.get_node(new_parent_id)
                if new_parent:
                    new_parent.add_child(node)
                    node.parent_id = new_parent_id
            else:
                node.parent_id = None

            return {"success": True, "node_id": node_id, "new_parent_id": new_parent_id}

        else:
            return {"success": False, "error": f"Unknown decision type: {decision_type}"}

    # ========== 批量操作方法 ==========

    def create_nodes_batch(
        self, node_definitions: list["NodeDefinition"]
    ) -> list[tuple[str, Node]]:
        """批量创建节点

        参数：
            node_definitions: 节点定义列表

        返回：
            (节点名称, 节点) 元组列表
        """
        results = []
        for node_def in node_definitions:
            # 将 NodeDefinition 转换为决策格式
            decision = {
                "node_type": node_def.node_type.value,
                "config": self._node_definition_to_config(node_def),
            }
            node = self.create_node(decision)
            self.add_node(node)
            results.append((node_def.name, node))
        return results

    def _node_definition_to_config(self, node_def: "NodeDefinition") -> dict[str, Any]:
        """将 NodeDefinition 转换为节点配置

        参数：
            node_def: 节点定义

        返回：
            节点配置字典
        """
        config = dict(node_def.config)
        if node_def.code:
            config["code"] = node_def.code
        if node_def.prompt:
            config["prompt"] = node_def.prompt
        if node_def.url:
            config["url"] = node_def.url
        if node_def.query:
            config["query"] = node_def.query
        if node_def.input_schema:
            config["input_schema"] = node_def.input_schema
        if node_def.output_schema:
            config["output_schema"] = node_def.output_schema
        return config

    def connect_nodes_batch(
        self,
        edge_definitions: list["EdgeDefinition"],
        name_to_id: dict[str, str],
    ) -> list[Edge]:
        """批量连接节点

        参数：
            edge_definitions: 边定义列表
            name_to_id: 节点名称到ID的映射

        返回：
            创建的边列表
        """
        edges = []
        for edge_def in edge_definitions:
            source_id = name_to_id.get(edge_def.source_node, edge_def.source_node)
            target_id = name_to_id.get(edge_def.target_node, edge_def.target_node)
            edge = self.connect_nodes(source_id, target_id, edge_def.condition)
            edges.append(edge)
        return edges

    def modify_node(self, node_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """修改节点配置

        参数：
            node_id: 节点ID
            config: 新配置

        返回：
            操作结果
        """
        node = self.get_node(node_id)
        if not node:
            return {"success": False, "error": f"Node not found: {node_id}"}

        # 更新节点配置
        node.config.update(config)
        return {"success": True, "node_id": node_id}

    async def execute_plan(self, plan: "WorkflowPlan") -> dict[str, Any]:
        """执行工作流规划

        从 WorkflowPlan 创建节点和边，然后执行工作流。

        参数：
            plan: 工作流规划

        返回：
            执行结果
        """
        # 1. 批量创建节点
        created_nodes = self.create_nodes_batch(plan.nodes)
        name_to_id = {name: node.id for name, node in created_nodes}

        # 2. 批量创建边
        created_edges = self.connect_nodes_batch(plan.edges, name_to_id)

        # 3. 执行工作流
        execution_result = await self.execute_workflow()

        return {
            "status": execution_result["status"],
            "nodes_created": len(created_nodes),
            "edges_created": len(created_edges),
            "node_mapping": name_to_id,
            "results": execution_result.get("results", {}),
        }

    async def execute_plan_from_dict(self, plan_dict: dict[str, Any]) -> dict[str, Any]:
        """从字典格式执行工作流规划

        参数：
            plan_dict: 规划字典

        返回：
            执行结果
        """
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        # 解析节点
        nodes = []
        for node_data in plan_dict.get("nodes", []):
            node_type_str = node_data.get("type", "generic")
            try:
                node_type = NodeType(node_type_str.lower())
            except ValueError:
                node_type = NodeType.GENERIC

            node_def = NodeDefinition(
                node_type=node_type,
                name=node_data.get("name", ""),
                code=node_data.get("code"),
                prompt=node_data.get("prompt"),
                url=node_data.get("url"),
                query=node_data.get("query"),
            )
            nodes.append(node_def)

        # 解析边
        edges = []
        for edge_data in plan_dict.get("edges", []):
            edge_def = EdgeDefinition(
                source_node=edge_data.get("source", ""),
                target_node=edge_data.get("target", ""),
                condition=edge_data.get("condition"),
            )
            edges.append(edge_def)

        # 创建 WorkflowPlan
        plan = WorkflowPlan(
            name=plan_dict.get("name", ""),
            goal=plan_dict.get("goal", ""),
            nodes=nodes,
            edges=edges,
        )

        return await self.execute_plan(plan)

    # ========== 层级节点操作方法 ==========

    async def create_grouped_nodes(
        self,
        group_name: str,
        steps: list[dict[str, Any]],
    ) -> Node:
        """创建分组节点（父节点包含子节点）

        参数：
            group_name: 分组名称
            steps: 步骤配置列表

        返回：
            创建的父节点
        """
        # 转换 steps 配置格式
        children_configs = []
        for step in steps:
            step_type = step.get("type", "generic")
            if isinstance(step_type, str):
                step_type = NodeType(step_type.lower())
            children_configs.append(
                {
                    "type": step_type,
                    "config": step.get("config", {}),
                }
            )

        # 使用层级服务创建父节点
        parent = self.hierarchy_service.create_parent_node(
            name=group_name,
            children_configs=children_configs,
        )

        # 同时注册到工作流节点
        self._nodes[parent.id] = parent
        for child in parent.children:
            self._nodes[child.id] = child

        # 发布事件
        if self.event_bus:
            for child in parent.children:
                from src.domain.services.node_hierarchy_service import ChildAddedEvent

                await self.event_bus.publish(
                    ChildAddedEvent(
                        source="workflow_agent",
                        parent_id=parent.id,
                        child_id=child.id,
                        child_type=child.type.value,
                    )
                )

        return parent

    async def add_step_to_group(
        self,
        group_id: str,
        step: dict[str, Any],
    ) -> Node:
        """向已有分组添加步骤

        参数：
            group_id: 分组ID
            step: 步骤配置

        返回：
            创建的子节点
        """
        step_type = step.get("type", "generic")
        if isinstance(step_type, str):
            step_type = NodeType(step_type.lower())

        child = await self.hierarchy_service.add_child_to_parent_async(
            parent_id=group_id,
            child_type=step_type,
            child_config=step.get("config", {}),
        )

        # 注册到工作流节点
        self._nodes[child.id] = child

        return child

    async def toggle_group_collapse(self, group_id: str) -> None:
        """切换分组的折叠状态

        参数：
            group_id: 分组ID
        """
        node = self.hierarchy_service.get_node(group_id)
        if node is None:
            return

        if node.collapsed:
            await self.hierarchy_service.expand_node_async(group_id)
        else:
            await self.hierarchy_service.collapse_node_async(group_id)

    async def get_group_visible_steps(self, group_id: str) -> list[Node]:
        """获取分组的可见步骤

        参数：
            group_id: 分组ID

        返回：
            可见步骤列表
        """
        return self.hierarchy_service.get_visible_children(group_id)

    async def create_hierarchy_from_plan(
        self,
        plan: dict[str, Any],
    ) -> list[Node]:
        """从规划创建层级结构

        参数：
            plan: 规划字典，包含 groups 列表

        返回：
            创建的分组节点列表
        """
        groups = []

        for group_data in plan.get("groups", []):
            parent = await self._create_group_from_data(group_data)
            groups.append(parent)

        return groups

    async def _create_group_from_data(self, group_data: dict[str, Any]) -> Node:
        """从数据创建分组

        参数：
            group_data: 分组数据

        返回：
            创建的分组节点
        """
        # 创建主分组
        steps = group_data.get("steps", [])
        parent = await self.create_grouped_nodes(
            group_name=group_data.get("name", ""),
            steps=steps,
        )

        # 处理子分组
        for subgroup_data in group_data.get("subgroups", []):
            subgroup = await self._create_group_from_data(subgroup_data)
            # 将子分组添加到父分组
            parent.add_child(subgroup)
            subgroup.parent_id = parent.id
            self.hierarchy_service.register_node(subgroup)

        return parent

    async def get_all_groups(self) -> list[Node]:
        """获取所有分组

        返回：
            分组节点列表
        """
        return [
            node
            for node in self.hierarchy_service.get_root_nodes()
            if node.type == NodeType.GENERIC
        ]

    async def get_group_by_id(self, group_id: str) -> Node | None:
        """通过ID获取分组

        参数：
            group_id: 分组ID

        返回：
            分组节点，不存在返回 None
        """
        return self.hierarchy_service.get_node(group_id)

    async def get_hierarchy_tree(self, group_id: str) -> dict[str, Any]:
        """获取完整的层级树

        参数：
            group_id: 根节点ID

        返回：
            层级树字典
        """
        return self.hierarchy_service.get_hierarchy_tree(group_id)

    async def remove_step_from_group(self, group_id: str, step_id: str) -> None:
        """从分组移除步骤

        参数：
            group_id: 分组ID
            step_id: 步骤ID
        """
        parent = self.hierarchy_service.get_node(group_id)
        if parent:
            parent.remove_child(step_id)
            if step_id in self._nodes:
                del self._nodes[step_id]

    async def move_step_to_group(self, step_id: str, new_group_id: str) -> None:
        """在分组间移动步骤

        参数：
            step_id: 步骤ID
            new_group_id: 新分组ID
        """
        self.hierarchy_service.move_node(step_id, new_group_id)

    async def reorder_steps_in_group(
        self,
        group_id: str,
        step_ids: list[str],
    ) -> None:
        """重排序分组内的步骤

        参数：
            group_id: 分组ID
            step_ids: 新的步骤ID顺序
        """
        self.hierarchy_service.reorder_children(group_id, step_ids)

    async def remove_group(self, group_id: str) -> None:
        """删除分组及其所有步骤

        参数：
            group_id: 分组ID
        """
        node = self.hierarchy_service.get_node(group_id)
        if node:
            # 收集所有要删除的节点ID
            all_ids = [group_id] + [c.id for c in node.get_all_descendants()]

            # 从层级服务删除
            self.hierarchy_service.remove_node(group_id)

            # 从工作流节点删除
            for node_id in all_ids:
                if node_id in self._nodes:
                    del self._nodes[node_id]


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

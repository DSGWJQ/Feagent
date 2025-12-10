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

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from src.domain.services.context_manager import WorkflowContext
from src.domain.services.event_bus import Event, EventBus
from src.domain.services.execution_result import (
    ErrorCode,
    ExecutionResult,
    OutputValidator,
    RetryPolicy,
)
from src.domain.services.execution_result import (
    WorkflowExecutionResult as LegacyWorkflowExecutionResult,
)
from src.domain.services.expression_evaluator import (
    ExpressionEvaluator,
    UnsafeExpressionError,
)
from src.domain.services.node_hierarchy_service import NodeHierarchyService
from src.domain.services.node_registry import Node, NodeFactory, NodeType


@dataclass
class CustomNodeType:
    """自定义节点类型定义"""

    type_name: str
    schema: dict[str, Any]
    executor_class: type | None = None


def create_default_container_executor() -> Any:
    """创建默认容器执行器

    返回：
        容器执行器实例（带沙箱回退）
    """

    return DefaultContainerExecutor()


class DefaultContainerExecutor:
    """默认容器执行器（带沙箱回退）

    如果 Docker 不可用，自动回退到沙箱执行。
    """

    def __init__(self) -> None:
        from src.domain.agents.container_executor import ContainerExecutor

        self._container_executor = ContainerExecutor()
        self._fallback_executor: Any = None

    def is_available(self) -> bool:
        """检查是否可用（总是返回 True，因为有回退）"""
        return True

    @property
    def fallback_executor(self) -> Any:
        """获取回退执行器"""
        if self._fallback_executor is None:
            from src.domain.services.sandbox_executor import SandboxExecutor

            self._fallback_executor = SandboxExecutor()
        return self._fallback_executor

    async def execute_async(
        self,
        code: str,
        config: Any = None,
        inputs: dict[str, Any] | None = None,
    ) -> Any:
        """异步执行代码

        参数：
            code: 要执行的代码
            config: 容器配置
            inputs: 输入数据

        返回：
            执行结果
        """
        from src.domain.agents.container_executor import ContainerExecutionResult

        # 尝试使用容器执行器
        if self._container_executor.is_available():
            return await self._container_executor.execute_async(code, config, inputs)

        # 回退到沙箱
        try:
            from src.domain.services.sandbox_executor import SandboxConfig

            sandbox_config = SandboxConfig(timeout_seconds=config.timeout if config else 30)
            result = self.fallback_executor.execute(
                code=code,
                config=sandbox_config,
                input_data=inputs or {},
            )
            return ContainerExecutionResult(
                success=result.success,
                stdout=result.stdout if hasattr(result, "stdout") else "",
                stderr=result.stderr if hasattr(result, "stderr") else "",
                exit_code=0 if result.success else 1,
                execution_time=result.execution_time if hasattr(result, "execution_time") else 0.0,
                output_data=result.output_data if hasattr(result, "output_data") else {},
            )
        except Exception as e:
            return ContainerExecutionResult(
                success=False,
                stderr=str(e),
                exit_code=1,
            )


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
class WorkflowExecutionResult:
    """工作流执行结果 - Phase 16 标准结构

    属性：
        success: 是否成功
        summary: 执行摘要
        workflow_id: 工作流ID
        executed_nodes: 已执行的节点列表
        failed_node: 失败的节点ID（如果有）
        error_message: 错误消息
        diagnostics: 诊断信息
        execution_time: 执行时间（秒）
        outputs: 输出数据
    """

    success: bool = False
    summary: str = ""
    workflow_id: str = ""
    executed_nodes: list[str] = field(default_factory=list)
    failed_node: str | None = None
    error_message: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    outputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "success": self.success,
            "summary": self.summary,
            "workflow_id": self.workflow_id,
            "executed_nodes": self.executed_nodes,
            "failed_node": self.failed_node,
            "error_message": self.error_message,
            "diagnostics": self.diagnostics,
            "execution_time": self.execution_time,
            "outputs": self.outputs,
        }


@dataclass
class ReflectionResult:
    """反思结果 - Phase 16

    属性：
        assessment: 评估说明
        issues: 发现的问题列表
        recommendations: 建议列表
        confidence: 置信度 (0-1)
        should_retry: 是否建议重试
        suggested_modifications: 建议的修改
    """

    assessment: str = ""
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    should_retry: bool = False
    suggested_modifications: dict[str, Any] = field(default_factory=dict)


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
    success: bool = True
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowReflectionCompletedEvent(Event):
    """工作流反思完成事件 - Phase 16"""

    workflow_id: str = ""
    assessment: str = ""
    should_retry: bool = False
    confidence: float = 0.0


@dataclass
class NodeExecutionEvent(Event):
    """节点执行事件"""

    node_id: str = ""
    node_type: str = ""
    status: str = ""  # running, completed, failed
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class ExecutionProgressEvent(Event):
    """执行进度事件 - Phase 8.4

    在工作流执行过程中发布的进度更新事件，供 ConversationAgent 流式反馈。

    属性：
        workflow_id: 工作流ID
        node_id: 节点ID
        status: 执行状态（started/running/completed/failed）
        progress: 进度百分比（0.0-1.0）
        message: 进度描述消息
        metadata: 可选的额外元数据
    """

    workflow_id: str = ""
    node_id: str = ""
    status: str = ""
    progress: float = 0.0
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class NodeExecutor(Protocol):
    """节点执行器接口"""

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行节点"""
        ...


class WorkflowExecutorProtocol(Protocol):
    """工作流执行器协议 - Phase 16

    定义工作流执行器接口，用于执行整个工作流。
    """

    async def execute(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """执行工作流

        参数：
            workflow: 工作流定义

        返回：
            执行结果字典
        """
        ...


class ReflectionLLMProtocol(Protocol):
    """反思 LLM 协议 - Phase 16

    定义反思 LLM 接口，用于评估执行结果。
    """

    async def reflect(self, execution_result: dict[str, Any]) -> dict[str, Any]:
        """反思执行结果

        参数：
            execution_result: 执行结果

        返回：
            反思结果字典
        """
        ...


class WorkflowAgent:
    """工作流Agent

    职责：
    1. 管理工作流节点和边
    2. 执行工作流（按拓扑顺序）
    3. 发布执行状态事件
    4. 处理对话Agent的决策
    5. 执行工作流并返回标准结果 (Phase 16)
    6. 反思执行结果并生成评估 (Phase 16)

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

        # Phase 16: 新的执行和反思方式
        agent = WorkflowAgent(event_bus=event_bus, executor=executor, llm=llm)
        result = await agent.execute(workflow)
        reflection = await agent.reflect(result)
    """

    def __init__(
        self,
        workflow_context: WorkflowContext | None = None,
        node_factory: NodeFactory | None = None,
        node_executor: NodeExecutor | None = None,
        event_bus: EventBus | None = None,
        executor: WorkflowExecutorProtocol | None = None,
        llm: ReflectionLLMProtocol | None = None,
        container_executor: Any = None,
    ):
        """初始化工作流Agent

        参数：
            workflow_context: 工作流上下文（可选）
            node_factory: 节点工厂（可选）
            node_executor: 节点执行器（可选）
            event_bus: 事件总线（可选）
            executor: 工作流执行器（可选，Phase 16）
            llm: 反思 LLM（可选，Phase 16）
            container_executor: 容器执行器（可选，Phase 8.2）
        """
        self.workflow_context = workflow_context
        self.node_factory = node_factory
        self.node_executor = node_executor
        self.event_bus = event_bus

        # Phase 16: 新增执行器和 LLM
        self.executor = executor
        self.llm = llm

        # Phase 8.2: 容器执行器（支持外部注入或自动创建）
        self._container_executor = container_executor
        self._container_executor_initialized = container_executor is not None

        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._execution_status = ExecutionStatus.PENDING

        # 层级节点服务
        self.hierarchy_service = NodeHierarchyService(event_bus=event_bus)

        # 自定义节点类型存储
        self._custom_node_types: dict[str, CustomNodeType] = {}
        # 自定义节点执行器实例缓存
        self._custom_executors: dict[str, Any] = {}

        # Phase 8.4: 进度跟踪
        self._executed_nodes: list[str] = []  # 已执行的节点列表
        self._total_nodes: int = 0  # 总节点数（用于计算进度）

        # Phase 8.2: NodeDefinition 节点存储
        self._node_definitions: dict[str, NodeDefinition] = {}

    def get_container_executor(self) -> Any:
        """获取容器执行器（懒加载）

        返回：
            容器执行器实例
        """
        if not self._container_executor_initialized:
            self._container_executor = self._create_container_executor()
            self._container_executor_initialized = True
        return self._container_executor

    def _create_container_executor(self) -> Any:
        """创建默认容器执行器

        返回：
            容器执行器实例
        """
        return create_default_container_executor()

    def get_sandbox_executor(self) -> Any:
        """获取沙箱执行器（用于回退）

        返回：
            沙箱执行器实例
        """
        from src.domain.services.sandbox_executor import SandboxExecutor

        return SandboxExecutor()

    async def execute_container_node(self, node_id: str) -> dict[str, Any]:
        """执行容器节点

        参数：
            node_id: 节点 ID

        返回：
            执行结果字典
        """
        from src.domain.agents.container_executor import (
            ContainerConfig,
            ContainerExecutionResult,
        )

        # 获取节点定义
        node_def = self._node_definitions.get(node_id)
        if not node_def:
            return {"success": False, "error": f"Node {node_id} not found"}

        # 获取容器执行器
        executor = self.get_container_executor()

        # 检查执行器是否可用
        if not executor.is_available():
            # 使用沙箱回退
            return await self._execute_with_sandbox_fallback(node_def)

        # 构建容器配置
        container_config_dict = node_def.container_config or {}
        config = ContainerConfig(
            image=container_config_dict.get("image", "python:3.11-slim"),
            timeout=container_config_dict.get("timeout", 60),
            memory_limit=container_config_dict.get("memory_limit", "256m"),
        )

        # 执行
        result: ContainerExecutionResult = await executor.execute_async(
            code=node_def.code or "",
            config=config,
        )

        return result.to_dict()

    async def _execute_with_sandbox_fallback(self, node_def: "NodeDefinition") -> dict[str, Any]:
        """使用沙箱回退执行

        参数：
            node_def: 节点定义

        返回：
            执行结果
        """
        try:
            from src.domain.services.sandbox_executor import (
                SandboxConfig,
                SandboxExecutor,
            )

            sandbox = SandboxExecutor()
            config = SandboxConfig(timeout_seconds=30)
            result = sandbox.execute(
                code=node_def.code or "",
                config=config,
            )

            return {
                "success": result.success,
                "output": result.output_data if hasattr(result, "output_data") else {},
                "fallback_used": True,
                "executor_type": "sandbox",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fallback_used": True,
                "executor_type": "sandbox",
            }

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

    def add_node(
        self,
        node_or_id: "NodeDefinition | Node | str",
        node_type: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """添加节点到工作流

        支持三种调用方式：
        1. add_node(node_definition) - 传入NodeDefinition对象
        2. add_node(node) - 传入Node对象
        3. add_node(node_id, node_type, config) - 传入节点参数（便利方式）

        参数：
            node_or_id: NodeDefinition、Node对象或节点ID
            node_type: 节点类型（仅在便利方式下使用）
            config: 节点配置（仅在便利方式下使用）
        """
        # Import Node at the top to avoid UnboundLocalError
        from src.domain.agents.node_definition import NodeDefinition
        from src.domain.services.node_registry import Node, NodeType

        # 判断调用方式
        if isinstance(node_or_id, NodeDefinition):
            # 方式1：传入NodeDefinition对象
            self._node_definitions[node_or_id.id] = node_or_id
            # 如果有 node_factory，也创建 Node 实例
            if self.node_factory:
                node = self.node_factory.create(node_or_id.node_type, node_or_id.config)
                node.id = node_or_id.id
                self._nodes[node.id] = node
                self.hierarchy_service.register_node(node)
            return
        elif isinstance(node_or_id, Node):
            # 方式2：传入Node对象
            node = node_or_id
        elif isinstance(node_or_id, str):
            # 方式3：便利方式，构造Node对象
            if node_type is None:
                raise ValueError("node_type is required when using convenience method")

            # 将字符串类型转换为NodeType枚举
            if isinstance(node_type, str):
                node_type_enum = NodeType(node_type)
            else:
                node_type_enum = node_type

            node = Node(
                id=node_or_id,
                type=node_type_enum,
                config=config or {},
            )
        else:
            raise TypeError(f"Expected NodeDefinition, Node or str, got {type(node_or_id)}")

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

    async def execute_node_with_result(
        self,
        node_id: str,
        retry_policy: RetryPolicy | None = None,
        output_validator: OutputValidator | None = None,
    ) -> ExecutionResult:
        """执行节点并返回结构化结果

        支持自动重试和输出校验。

        参数：
            node_id: 节点ID
            retry_policy: 重试策略（可选）
            output_validator: 输出校验器（可选）

        返回：
            结构化执行结果
        """
        node = self._nodes.get(node_id)
        if not node:
            return ExecutionResult.failure(
                error_code=ErrorCode.INTERNAL_ERROR,
                error_message=f"Node not found: {node_id}",
            )

        policy = retry_policy or RetryPolicy(max_retries=0)
        attempt = 0
        start_time = time.time()

        while True:
            try:
                # 执行节点
                inputs = self._collect_node_inputs(node_id)

                # 检查是否是自定义节点类型
                custom_type_name = node.config.get("_custom_type")
                if custom_type_name and custom_type_name in self._custom_executors:
                    executor = self._custom_executors[custom_type_name]
                    output = await executor.execute(node.config, inputs)
                elif self.node_executor:
                    output = await self.node_executor.execute(node_id, node.config, inputs)
                else:
                    output = {"status": "success", "executed": True}

                # 校验输出
                if output_validator:
                    validation_result = output_validator.validate(output)
                    if not validation_result.is_valid:
                        execution_time_ms = (time.time() - start_time) * 1000
                        return ExecutionResult.failure(
                            error_code=ErrorCode.VALIDATION_FAILED,
                            error_message=validation_result.error_message or "Validation failed",
                            output=output,
                            metadata={
                                "execution_time_ms": execution_time_ms,
                                "retry_count": attempt,
                                "node_id": node_id,
                            },
                        )

                # 成功
                execution_time_ms = (time.time() - start_time) * 1000
                self.workflow_context.set_node_output(node_id, output)

                return ExecutionResult.ok(
                    output=output,
                    metadata={
                        "execution_time_ms": execution_time_ms,
                        "retry_count": attempt,
                        "node_id": node_id,
                    },
                )

            except Exception as e:
                error_result = ExecutionResult.from_exception(e)

                # 判断是否应该重试
                if policy.should_retry(error_result.error_code, attempt):
                    delay = policy.get_delay(attempt)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue

                # 不重试，返回失败结果
                execution_time_ms = (time.time() - start_time) * 1000
                return ExecutionResult.failure(
                    error_code=error_result.error_code,
                    error_message=str(e),
                    metadata={
                        "execution_time_ms": execution_time_ms,
                        "retry_count": attempt,
                        "node_id": node_id,
                    },
                )

    async def execute_workflow_with_results(self) -> LegacyWorkflowExecutionResult:
        """执行整个工作流并返回结构化结果

        返回：
            工作流执行结果
        """
        start_time = time.time()
        node_results: dict[str, ExecutionResult] = {}

        try:
            execution_order = self._topological_sort()

            for node_id in execution_order:
                result = await self.execute_node_with_result(node_id)
                node_results[node_id] = result

                if not result.success:
                    execution_time_ms = (time.time() - start_time) * 1000
                    return LegacyWorkflowExecutionResult(
                        success=False,
                        node_results=node_results,
                        failed_node_id=node_id,
                        error_message=result.error_message,
                        metadata={"execution_time_ms": execution_time_ms},
                    )

            execution_time_ms = (time.time() - start_time) * 1000
            return LegacyWorkflowExecutionResult(
                success=True,
                node_results=node_results,
                metadata={"execution_time_ms": execution_time_ms},
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return LegacyWorkflowExecutionResult(
                success=False,
                node_results=node_results,
                error_message=str(e),
                metadata={"execution_time_ms": execution_time_ms},
            )

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

    async def execute_workflow_with_conditions(self) -> dict[str, Any]:
        """执行支持条件分支的工作流

        核心逻辑：
        1. 获取拓扑排序的节点执行顺序
        2. 对每个节点，检查所有入边的条件
        3. 只有当至少一条入边条件满足时才执行节点
        4. 使用ExpressionEvaluator评估条件表达式
        5. 将已执行节点的输出作为条件评估的上下文

        返回：
            执行结果字典，包含：
            - status: 执行状态 (completed/failed)
            - results: 已执行节点的结果字典
            - skipped_nodes: 被跳过的节点列表（条件不满足）
        """
        self._execution_status = ExecutionStatus.RUNNING

        # 初始化表达式评估器
        evaluator = ExpressionEvaluator()

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

            # 构建入边映射：node_id -> list of incoming edges
            incoming_edges: dict[str, list[Edge]] = {}
            for edge in self._edges:
                if edge.target_id not in incoming_edges:
                    incoming_edges[edge.target_id] = []
                incoming_edges[edge.target_id].append(edge)

            results = {}
            skipped_nodes = []

            # 按拓扑顺序执行节点
            for node_id in execution_order:
                # 检查节点是否应该执行（基于条件）
                should_execute = self._should_execute_node(
                    node_id=node_id,
                    incoming_edges=incoming_edges.get(node_id, []),
                    evaluator=evaluator,
                    results=results,
                )

                if should_execute:
                    # 执行节点
                    result = await self.execute_node(node_id)
                    results[node_id] = result
                else:
                    # 跳过节点
                    skipped_nodes.append(node_id)

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

            return {
                "status": "completed",
                "results": results,
                "skipped_nodes": skipped_nodes,
            }

        except Exception as e:
            self._execution_status = ExecutionStatus.FAILED
            return {"status": "failed", "error": str(e)}

    def _should_execute_node(
        self,
        node_id: str,
        incoming_edges: list[Edge],
        evaluator: ExpressionEvaluator,
        results: dict[str, Any],
    ) -> bool:
        """判断节点是否应该执行

        逻辑：
        - 如果没有入边，则执行（起始节点）
        - 如果有入边，至少一条边的条件满足才执行
        - 如果边没有condition，视为True（无条件执行）

        参数：
            node_id: 节点ID
            incoming_edges: 入边列表
            evaluator: 表达式评估器
            results: 已执行节点的输出字典

        返回：
            是否应该执行节点
        """
        # 没有入边，则为起始节点，直接执行
        if not incoming_edges:
            return True

        # 检查是否至少有一条入边条件满足
        for edge in incoming_edges:
            # 检查源节点是否已执行
            if edge.source_id not in results:
                # 源节点未执行，该边不满足
                continue

            # 如果边没有条件，视为True
            if edge.condition is None or edge.condition.strip() == "":
                return True

            # 评估条件表达式
            try:
                # 构建评估上下文：将源节点的输出字段提升到顶层
                # 这样条件表达式可以直接使用 "score > 0.8" 而不是 "node_a.score > 0.8"
                source_output = results.get(edge.source_id, {})

                # 如果结果包含"output"键，提取它
                if isinstance(source_output, dict) and "output" in source_output:
                    evaluation_context = source_output["output"].copy()
                else:
                    evaluation_context = (
                        source_output.copy() if isinstance(source_output, dict) else {}
                    )

                # 准备多层上下文（向后兼容：不存在时为None）
                workflow_vars = None
                if self.workflow_context and hasattr(self.workflow_context, "variables"):
                    workflow_vars = self.workflow_context.variables

                global_vars = None
                if self.workflow_context and hasattr(self.workflow_context, "session_context"):
                    session_ctx = self.workflow_context.session_context
                    if session_ctx and hasattr(session_ctx, "global_context"):
                        global_ctx = session_ctx.global_context
                        if global_ctx:
                            # 合并system_config和user_preferences作为全局变量
                            global_vars = {}
                            if hasattr(global_ctx, "system_config") and global_ctx.system_config:
                                global_vars.update(global_ctx.system_config)
                            if (
                                hasattr(global_ctx, "user_preferences")
                                and global_ctx.user_preferences
                            ):
                                global_vars.update(global_ctx.user_preferences)

                # 评估条件（传递多层上下文）
                condition_result = evaluator.evaluate(
                    edge.condition,
                    evaluation_context,
                    workflow_vars=workflow_vars,
                    global_vars=global_vars,
                )

                # 记录条件求值结果到WorkflowContext（供下游诊断和使用）
                if self.workflow_context:
                    from datetime import datetime

                    condition_record = {
                        "edge_id": edge.id,
                        "source_id": edge.source_id,
                        "target_id": node_id,
                        "expression": edge.condition,
                        "result": condition_result,
                        "evaluated_at": datetime.now().isoformat(),
                    }
                    self.workflow_context.edge_conditions[edge.id] = condition_record

                if condition_result:
                    return True

            except Exception as e:
                # 条件评估失败，记录详细信息到上下文和日志
                if self.workflow_context:
                    from datetime import datetime

                    condition_record = {
                        "edge_id": edge.id,
                        "source_id": edge.source_id,
                        "target_id": node_id,
                        "expression": edge.condition,
                        "result": False,
                        "error": str(e),
                        "evaluated_at": datetime.now().isoformat(),
                    }
                    self.workflow_context.edge_conditions[edge.id] = condition_record

                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"条件评估失败 - 节点: {node_id}, 边: {edge.id}, "
                    f"条件: {edge.condition}, 错误: {e}"
                )
                continue

        # 所有入边条件都不满足，跳过节点
        return False

    # ==================== Phase 8.5: 集合操作执行方法 ====================

    async def execute_workflow_with_collection_operations(self) -> dict[str, Any]:
        """执行支持集合操作的工作流 (Loop/Map/Filter)

        核心逻辑：
        1. 识别集合操作节点（Loop类型）
        2. 对Loop节点，根据loop_type执行不同逻辑：
           - for_each: 遍历集合，对每个元素执行子节点
           - map: 转换集合元素
           - filter: 过滤集合元素
        3. 聚合子执行结果
        4. 支持条件分支与集合操作的组合

        返回：
            执行结果字典，包含：
            - status: 执行状态 (completed/failed)
            - results: 已执行节点的结果字典
            - skipped_nodes: 被跳过的节点列表
        """
        self._execution_status = ExecutionStatus.RUNNING
        evaluator = ExpressionEvaluator()

        # 发布工作流开始执行事件
        if self.event_bus:
            await self.event_bus.publish(
                WorkflowExecutionStartedEvent(
                    source="workflow_agent",
                    workflow_id=self.workflow_context.workflow_id
                    if self.workflow_context
                    else "unknown",
                    node_count=len(self._nodes),
                )
            )

        try:
            execution_order = self._topological_sort()

            # 构建入边映射
            incoming_edges: dict[str, list[Edge]] = {}
            for edge in self._edges:
                if edge.target_id not in incoming_edges:
                    incoming_edges[edge.target_id] = []
                incoming_edges[edge.target_id].append(edge)

            # 识别Loop节点的子节点（只有for_each类型会在Loop内部执行子节点）
            loop_child_nodes = set()
            for node_id, node in self._nodes.items():
                if node.type == NodeType.LOOP:
                    loop_type = node.config.get("loop_type", "for_each")
                    # 只有for_each循环才在内部执行子节点
                    if loop_type == "for_each":
                        for edge in self._edges:
                            if edge.source_id == node_id:
                                loop_child_nodes.add(edge.target_id)

            results = {}
            skipped_nodes = []

            # 按拓扑顺序执行节点
            for node_id in execution_order:
                # 跳过Loop节点的子节点（它们会在Loop内部执行）
                if node_id in loop_child_nodes:
                    continue
                node = self._nodes.get(node_id)
                if not node:
                    continue

                # 检查条件分支（如果有条件）
                should_execute = self._should_execute_node(
                    node_id=node_id,
                    incoming_edges=incoming_edges.get(node_id, []),
                    evaluator=evaluator,
                    results=results,
                )

                if not should_execute:
                    skipped_nodes.append(node_id)
                    continue

                # 检查是否是集合操作节点
                if node.type == NodeType.LOOP:
                    result = await self._execute_collection_operation_node(
                        node=node, results=results, evaluator=evaluator
                    )
                    results[node_id] = result
                    # 写回WorkflowContext
                    if self.workflow_context:
                        self.workflow_context.set_node_output(node_id, result)

                    # 检查集合操作是否失败（如不安全表达式）
                    if not result.get("success", True):
                        self._execution_status = ExecutionStatus.FAILED
                        error_msg = result.get("metadata", {}).get(
                            "error", "Collection operation failed"
                        )
                        return {
                            "status": "failed",
                            "error": error_msg,
                            "failed_node": node_id,
                            "results": results,
                            "skipped_nodes": skipped_nodes,
                        }
                else:
                    # 普通节点执行
                    result = await self.execute_node(node_id)
                    results[node_id] = result
                    if self.workflow_context:
                        self.workflow_context.set_node_output(node_id, result)

            self._execution_status = ExecutionStatus.COMPLETED

            # 发布工作流完成事件
            if self.event_bus:
                await self.event_bus.publish(
                    WorkflowExecutionCompletedEvent(
                        source="workflow_agent",
                        workflow_id=self.workflow_context.workflow_id
                        if self.workflow_context
                        else "unknown",
                        result={"status": "completed"},
                    )
                )

            return {
                "status": "completed",
                "results": results,
                "skipped_nodes": skipped_nodes,
            }
        except Exception as e:
            self._execution_status = ExecutionStatus.FAILED
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"工作流执行失败: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    async def _execute_collection_operation_node(
        self, node: Node, results: dict[str, Any], evaluator: ExpressionEvaluator
    ) -> dict[str, Any]:
        """执行集合操作节点

        参数：
            node: 集合操作节点（Loop类型）
            results: 当前已执行节点的结果
            evaluator: 表达式求值器

        返回：
            节点执行结果，根据loop_type不同返回不同格式
        """
        loop_type = node.config.get("loop_type", "for_each")
        collection_field = node.config.get("collection_field")

        if not collection_field:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Loop节点 {node.id} 缺少 collection_field 配置")
            return {
                "success": False,
                "output": {},
                "metadata": {
                    "operation_type": loop_type,
                    "error": "Missing collection_field",
                },
            }

        # 从上游节点输出中提取集合
        collection = self._extract_collection_from_results(
            node_id=node.id, collection_field=collection_field, results=results
        )

        if collection is None:
            return {
                "success": True,
                "output": {"collection": []},
                "metadata": {
                    "operation_type": loop_type,
                    "total_items": 0,
                    "message": "Collection not found",
                },
            }

        if not isinstance(collection, list):
            return {
                "success": False,
                "output": {},
                "metadata": {
                    "operation_type": loop_type,
                    "error": f"Collection field '{collection_field}' is not a list",
                },
            }

        # 根据loop_type执行不同逻辑
        if loop_type == "for_each":
            result = await self._execute_for_each_loop(node, collection, results)
        elif loop_type == "map":
            result = await self._execute_map_operation(node, collection, evaluator)
        elif loop_type == "filter":
            result = await self._execute_filter_operation(node, collection, evaluator)
        else:
            result = {
                "success": False,
                "output": {},
                "metadata": {
                    "operation_type": loop_type,
                    "error": f"Unknown loop_type: {loop_type}",
                },
            }

        # 写回WorkflowContext（确保集合操作结果可被后续节点访问）
        if self.workflow_context:
            self.workflow_context.set_node_output(node.id, result)

        return result

    def _extract_collection_from_results(
        self, node_id: str, collection_field: str, results: dict[str, Any]
    ) -> list | None:
        """从前置节点结果中提取集合

        参数：
            node_id: 当前节点ID
            collection_field: 集合字段名
            results: 已执行节点的结果

        返回：
            集合列表或None
        """
        # 查找所有指向当前节点的边
        valid_source_ids = []
        for edge in self._edges:
            if edge.target_id == node_id:
                # 检查边的条件是否满足
                if edge.condition:
                    # 如果有条件，检查条件评估记录
                    if self.workflow_context and hasattr(self.workflow_context, "edge_conditions"):
                        edge_condition = self.workflow_context.edge_conditions.get(edge.id)
                        if edge_condition and edge_condition.get("result") is True:
                            # 条件满足，且源节点已执行
                            if edge.source_id in results:
                                valid_source_ids.append(edge.source_id)
                    # 如果没有条件记录，检查源节点是否在results中
                    elif edge.source_id in results:
                        valid_source_ids.append(edge.source_id)
                else:
                    # 无条件边，只要源节点已执行就有效
                    if edge.source_id in results:
                        valid_source_ids.append(edge.source_id)

        # 按执行顺序的逆序查找（优先使用最近执行的节点）
        for source_id in reversed(valid_source_ids):
            source_output = results.get(source_id, {})

            # 如果输出包含output字段，先解包
            if isinstance(source_output, dict) and "output" in source_output:
                source_output = source_output["output"]

            # 检查是否包含目标字段
            if isinstance(source_output, dict) and collection_field in source_output:
                return source_output[collection_field]

        return None

    async def _execute_for_each_loop(
        self, loop_node: Node, collection: list, results: dict[str, Any]
    ) -> dict[str, Any]:
        """执行for_each循环

        遍历集合，对每个元素执行子节点。

        参数：
            loop_node: Loop节点
            collection: 要遍历的集合
            results: 当前执行结果

        返回：
            聚合结果
        """
        item_variable = loop_node.config.get("item_variable", "current_item")
        aggregated_results = []

        # 找到Loop节点的子节点
        child_node_ids = []
        for edge in self._edges:
            if edge.source_id == loop_node.id:
                child_node_ids.append(edge.target_id)

        # 遍历集合
        for item in collection:
            # 为每个元素执行子节点
            for child_id in child_node_ids:
                child_node = self._nodes.get(child_id)
                if not child_node:
                    continue

                # 准备输入（包含当前元素）
                inputs = {item_variable: item}

                # 执行子节点
                if self.node_executor:
                    child_result = await self.node_executor.execute(
                        child_id, child_node.config, inputs
                    )
                else:
                    child_result = {"status": "success"}

                aggregated_results.append(child_result)

        return {
            "success": True,
            "output": {
                "collection": aggregated_results,
            },
            "metadata": {
                "operation_type": "for_each",
                "total_items": len(collection),
                "iteration_count": len(collection),
                "processed_items": len(aggregated_results),
            },
        }

    async def _execute_map_operation(
        self, map_node: Node, collection: list, evaluator: ExpressionEvaluator
    ) -> dict[str, Any]:
        """执行map转换操作

        对集合中的每个元素应用转换表达式。

        参数：
            map_node: Map节点
            collection: 原始集合
            evaluator: 表达式求值器

        返回：
            转换后的集合
        """
        transform_expression = map_node.config.get("transform_expression")

        if not transform_expression:
            return {
                "success": False,
                "output": {},
                "metadata": {
                    "operation_type": "map",
                    "error": "Missing transform_expression for map operation",
                },
            }

        transformed_collection = []
        failed_count = 0  # 跟踪失败的元素数量

        for item in collection:
            # 构建求值上下文
            if isinstance(item, dict):
                context = item.copy()
            else:
                # 如果是简单值，包装到上下文中
                context = {"value": item}
                # 同时支持直接访问（用于简单表达式）
                for key in ["x", "item", "current"]:
                    context[key] = item

            try:
                # 使用安全的表达式求值器计算转换结果
                result_value = evaluator.evaluate_expression(
                    transform_expression,
                    context,
                    item=item,
                    mode="advanced",
                )

                # 保持原对象结构，更新转换字段
                if isinstance(item, dict):
                    transformed_item = item.copy()
                    # 更新被转换的字段
                    # 假设表达式引用的字段就是要更新的字段
                    for var in context.keys():
                        if var in transform_expression and var in transformed_item:
                            transformed_item[var] = result_value
                            break
                    else:
                        # 如果没有匹配字段，添加result字段
                        transformed_item["result"] = result_value
                    transformed_collection.append(transformed_item)
                else:
                    # 简单值，直接替换
                    transformed_collection.append(result_value)
            except UnsafeExpressionError as e:
                # 不安全表达式，立即终止Map操作
                import logging

                logger = logging.getLogger(__name__)
                logger.error(
                    f"Map操作中止（不安全表达式）: expression={transform_expression}, error={e}"
                )
                return {
                    "success": False,
                    "output": {},
                    "metadata": {
                        "operation_type": "map",
                        "error": f"Unsafe transform_expression: {e}",
                    },
                }
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Map转换失败: item={item}, expression={transform_expression}, error={e}"
                )
                # 转换失败，保留原值
                transformed_collection.append(item)
                failed_count += 1

        # 构建返回结果，包含部分失败信息
        return {
            "success": True,
            "output": {
                "collection": transformed_collection,
            },
            "metadata": {
                "operation_type": "map",
                "total_items": len(collection),
                "processed_items": len(transformed_collection),
                "failed_items": failed_count,
                "partial_failure": failed_count > 0,
            },
        }

    async def _execute_filter_operation(
        self, filter_node: Node, collection: list, evaluator: ExpressionEvaluator
    ) -> dict[str, Any]:
        """执行filter过滤操作

        根据条件表达式过滤集合元素。

        参数：
            filter_node: Filter节点
            collection: 原始集合
            evaluator: 表达式求值器

        返回：
            过滤后的集合
        """
        filter_condition = filter_node.config.get("filter_condition")

        if not filter_condition:
            return {
                "success": False,
                "output": {},
                "metadata": {
                    "operation_type": "filter",
                    "error": "Missing filter_condition for filter operation",
                },
            }

        filtered_collection = []
        evaluation_failed_count = 0  # 跟踪条件评估失败的元素数量

        for item in collection:
            # 构建求值上下文
            if isinstance(item, dict):
                context = item.copy()
            else:
                # 如果是简单值，包装到上下文中
                context = {"value": item, "x": item, "item": item}

            try:
                # 评估条件
                result = evaluator.evaluate(filter_condition, context)
                if result:
                    filtered_collection.append(item)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Filter评估失败: item={item}, condition={filter_condition}, error={e}"
                )
                # 评估失败，跳过该元素
                evaluation_failed_count += 1
                continue

        # 构建返回结果，包含评估失败信息
        return {
            "success": True,
            "output": {
                "collection": filtered_collection,
            },
            "metadata": {
                "operation_type": "filter",
                "total_items": len(collection),
                "processed_items": len(filtered_collection),
                "filtered_out": len(collection)
                - len(filtered_collection)
                - evaluation_failed_count,
                "evaluation_failed": evaluation_failed_count,
                "partial_failure": evaluation_failed_count > 0,
            },
        }

    # ==================== Phase 8.4: 进度事件相关方法 ====================

    async def _publish_progress_event(
        self,
        workflow_id: str,
        node_id: str,
        status: str,
        progress: float,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """发布进度事件（内部辅助方法）

        将事件发布失败视为非关键错误，不阻塞主流程执行。

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            status: 执行状态
            progress: 进度百分比
            message: 进度消息
            metadata: 可选的元数据
        """
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                ExecutionProgressEvent(
                    source="workflow_agent",
                    workflow_id=workflow_id,
                    node_id=node_id,
                    status=status,
                    progress=progress,
                    message=message,
                    metadata=metadata or {},
                )
            )
        except Exception:
            # 事件发布失败不应阻塞执行
            pass

    async def execute_node_with_progress(self, node_id: str) -> dict[str, Any]:
        """执行单个节点并发布进度事件

        参数：
            node_id: 节点ID

        返回：
            执行结果
        """
        node = self._nodes.get(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        workflow_id = self.workflow_context.workflow_id if self.workflow_context else "unknown"

        # 发布节点开始事件
        await self._publish_progress_event(
            workflow_id=workflow_id,
            node_id=node_id,
            status="started",
            progress=0.0,
            message=f"开始执行节点 {node_id}",
        )

        try:
            # 获取节点输入
            inputs = self._collect_node_inputs(node_id)

            # 发布运行中事件
            await self._publish_progress_event(
                workflow_id=workflow_id,
                node_id=node_id,
                status="running",
                progress=0.5,
                message=f"正在执行节点 {node_id}",
            )

            # 执行节点
            custom_type_name = node.config.get("_custom_type")
            if custom_type_name and custom_type_name in self._custom_executors:
                executor = self._custom_executors[custom_type_name]
                result = await executor.execute(node.config, inputs)
            elif self.node_executor:
                result = await self.node_executor.execute(node_id, node.config, inputs)
            else:
                result = {"status": "success", "executed": True}

            # 存储节点输出到上下文
            if self.workflow_context:
                self.workflow_context.set_node_output(node_id, result)

            # 更新已执行节点列表
            if node_id not in self._executed_nodes:
                self._executed_nodes.append(node_id)

            # 发布节点完成事件
            await self._publish_progress_event(
                workflow_id=workflow_id,
                node_id=node_id,
                status="completed",
                progress=1.0,
                message=f"节点 {node_id} 执行完成",
            )

            return result

        except Exception as e:
            # 发布节点失败事件
            await self._publish_progress_event(
                workflow_id=workflow_id,
                node_id=node_id,
                status="failed",
                progress=0.5,
                message=f"节点 {node_id} 执行失败: {str(e)}",
            )
            raise

    async def execute_workflow_with_progress(self) -> dict[str, Any]:
        """执行整个工作流并发布进度事件

        按拓扑顺序执行所有节点，并在每个步骤发布进度事件。

        返回：
            执行结果
        """
        self._execution_status = ExecutionStatus.RUNNING

        workflow_id = self.workflow_context.workflow_id if self.workflow_context else "unknown"

        # 初始化进度跟踪
        self._executed_nodes = []
        self._total_nodes = len(self._nodes)

        # 发布工作流开始执行事件
        if self.event_bus:
            await self.event_bus.publish(
                WorkflowExecutionStartedEvent(
                    source="workflow_agent",
                    workflow_id=workflow_id,
                    node_count=self._total_nodes,
                )
            )

        try:
            # 获取拓扑排序的节点顺序
            execution_order = self._topological_sort()

            results = {}
            for _idx, node_id in enumerate(execution_order):
                # 执行节点（会自动发布进度事件）
                result = await self.execute_node_with_progress(node_id)
                results[node_id] = result

            self._execution_status = ExecutionStatus.COMPLETED

            # 发布工作流完成事件
            if self.event_bus:
                await self.event_bus.publish(
                    WorkflowExecutionCompletedEvent(
                        source="workflow_agent",
                        workflow_id=workflow_id,
                        status="completed",
                        result=results,
                    )
                )

            return {"status": "completed", "results": results}

        except Exception as e:
            self._execution_status = ExecutionStatus.FAILED

            # 发布工作流失败事件
            if self.event_bus:
                await self.event_bus.publish(
                    WorkflowExecutionCompletedEvent(
                        source="workflow_agent",
                        workflow_id=workflow_id,
                        status="failed",
                        success=False,
                        result={"error": str(e)},
                    )
                )

            return {"status": "failed", "error": str(e)}

    def get_workflow_progress(self) -> float:
        """获取当前工作流执行进度

        返回：
            进度百分比（0.0-1.0）
        """
        # Calculate total nodes dynamically from _nodes dict
        total = self._total_nodes if self._total_nodes > 0 else len(self._nodes)

        if total == 0:
            return 0.0

        return len(self._executed_nodes) / total

    def get_progress_summary(self) -> dict[str, Any]:
        """获取执行进度摘要

        返回：
            包含进度信息的字典
        """
        # Calculate total nodes dynamically
        total = self._total_nodes if self._total_nodes > 0 else len(self._nodes)

        return {
            "total_nodes": total,
            "completed_nodes": len(self._executed_nodes),
            "progress": self.get_workflow_progress(),
            "status": self._execution_status.value,
            "executed_nodes": self._executed_nodes.copy(),
        }

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

    # ========== Phase 16: 执行和反思方法 ==========

    async def execute(self, workflow: dict[str, Any]) -> WorkflowExecutionResult:
        """执行工作流并返回标准结果

        参数：
            workflow: 工作流定义，包含 id, nodes, edges

        返回：
            WorkflowExecutionResult 标准执行结果
        """
        workflow_id = workflow.get("id", "")
        start_time = time.time()

        # 发布开始事件
        if self.event_bus:
            await self.event_bus.publish(
                WorkflowExecutionStartedEvent(
                    source="workflow_agent",
                    workflow_id=workflow_id,
                    node_count=len(workflow.get("nodes", [])),
                )
            )

        try:
            # 使用执行器执行工作流
            if self.executor:
                executor_result = await self.executor.execute(workflow)
            else:
                # 默认执行（用于测试）
                executor_result = {
                    "success": True,
                    "outputs": {},
                    "executed_nodes": [],
                }

            execution_time = time.time() - start_time

            # 构建标准执行结果
            success = executor_result.get("success", True)
            result = WorkflowExecutionResult(
                success=success,
                summary="工作流执行成功" if success else "工作流执行失败",
                workflow_id=workflow_id,
                executed_nodes=executor_result.get("executed_nodes", []),
                failed_node=executor_result.get("failed_node"),
                error_message=executor_result.get("error"),
                execution_time=executor_result.get("execution_time", execution_time),
                outputs=executor_result.get("outputs", {}),
            )

            # 发布完成事件
            if self.event_bus:
                await self.event_bus.publish(
                    WorkflowExecutionCompletedEvent(
                        source="workflow_agent",
                        workflow_id=workflow_id,
                        status="completed" if success else "failed",
                        success=success,
                        result=result.to_dict(),
                    )
                )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            result = WorkflowExecutionResult(
                success=False,
                summary=f"工作流执行异常: {e!s}",
                workflow_id=workflow_id,
                error_message=str(e),
                execution_time=execution_time,
            )

            # 发布完成事件（失败）
            if self.event_bus:
                await self.event_bus.publish(
                    WorkflowExecutionCompletedEvent(
                        source="workflow_agent",
                        workflow_id=workflow_id,
                        status="failed",
                        success=False,
                        result=result.to_dict(),
                    )
                )

            return result

    async def reflect(self, execution_result: WorkflowExecutionResult) -> ReflectionResult:
        """反思执行结果并生成评估

        参数：
            execution_result: 执行结果

        返回：
            ReflectionResult 反思结果
        """
        workflow_id = execution_result.workflow_id

        if self.llm:
            # 使用 LLM 进行反思
            llm_result = await self.llm.reflect(execution_result.to_dict())

            reflection = ReflectionResult(
                assessment=llm_result.get("assessment", ""),
                issues=llm_result.get("issues", []),
                recommendations=llm_result.get("recommendations", []),
                confidence=llm_result.get("confidence", 0.0),
                should_retry=llm_result.get("should_retry", False),
                suggested_modifications=llm_result.get("suggested_modifications", {}),
            )
        else:
            # 无 LLM 时的回退反思
            if execution_result.success:
                reflection = ReflectionResult(
                    assessment=f"工作流 {workflow_id} 执行成功",
                    issues=[],
                    recommendations=[],
                    confidence=1.0,
                    should_retry=False,
                )
            else:
                reflection = ReflectionResult(
                    assessment=f"工作流 {workflow_id} 执行失败: {execution_result.error_message}",
                    issues=[execution_result.error_message or "未知错误"],
                    recommendations=["检查执行日志"],
                    confidence=0.5,
                    should_retry=True,
                )

        # 发布反思完成事件
        if self.event_bus:
            await self.event_bus.publish(
                WorkflowReflectionCompletedEvent(
                    source="workflow_agent",
                    workflow_id=workflow_id,
                    assessment=reflection.assessment,
                    should_retry=reflection.should_retry,
                    confidence=reflection.confidence,
                )
            )

        return reflection

    # ==================== Phase 5: NodeDefinition 集成 ====================

    def create_node_from_definition(self, node_def: "NodeDefinition") -> Node:
        """从 NodeDefinition 创建 Node

        递归转换 NodeDefinition 为 Node，包括子节点。

        参数：
            node_def: NodeDefinition 实例

        返回：
            Node 实例
        """
        from src.domain.agents.node_definition import NodeType as DefNodeType

        # 映射 NodeDefinition 类型到 node_registry 类型
        # NodeDefinition 类型 -> node_registry 的 NodeType
        type_mapping = {
            DefNodeType.PYTHON: NodeType.CODE,  # PYTHON -> CODE
            DefNodeType.LLM: NodeType.LLM,
            DefNodeType.HTTP: NodeType.API,  # HTTP -> API
            DefNodeType.DATABASE: NodeType.GENERIC,  # DATABASE -> GENERIC
            DefNodeType.GENERIC: NodeType.GENERIC,
            DefNodeType.CONDITION: NodeType.CONDITION,
            DefNodeType.LOOP: NodeType.LOOP,
            DefNodeType.PARALLEL: NodeType.PARALLEL,
            DefNodeType.CONTAINER: NodeType.GENERIC,  # 容器节点使用 GENERIC 类型
        }

        # 转换节点类型
        node_type = type_mapping.get(node_def.node_type, NodeType.GENERIC)

        # 构建配置
        config = {
            "name": node_def.name,
            "description": node_def.description,
            "code": node_def.code,
            "is_container": node_def.is_container,
            "container_config": node_def.container_config,
        }

        # 使用工厂创建节点
        node = self.node_factory.create(node_type, config)

        # 设置父节点ID
        if node_def.parent_id:
            node.parent_id = node_def.parent_id

        # 设置折叠状态
        node.collapsed = node_def.collapsed

        # 递归创建子节点
        for child_def in node_def.children:
            child_node = self.create_node_from_definition(child_def)
            child_node.parent_id = node.id
            node.add_child(child_node)

        return node

    def get_hierarchical_execution_order(self, node_id: str) -> list[str]:
        """获取层次化节点的执行顺序

        返回节点及其所有后代的执行顺序。
        子节点先于父节点执行，以便父节点可以聚合子节点结果。

        参数：
            node_id: 节点ID

        返回：
            按执行顺序排列的节点ID列表
        """
        node = self._nodes.get(node_id)
        if not node:
            return []

        result: list[str] = []

        def collect_descendants(n: Node) -> None:
            """递归收集所有后代"""
            # 先收集子节点
            for child in n.children:
                collect_descendants(child)
            # 最后添加自己
            result.append(n.id)

        collect_descendants(node)
        return result

    async def execute_hierarchical_node(self, node_id: str) -> dict[str, Any]:
        """执行层次化节点（支持父节点策略传播和统一错误处理）

        按顺序执行节点及其所有子节点，并聚合结果。
        支持父节点策略继承、统一错误处理、容器化执行。

        参数：
            node_id: 节点ID

        返回：
            执行结果字典
        """
        node = self._nodes.get(node_id)
        if not node:
            return {"status": "failed", "error": f"Node not found: {node_id}"}

        # 获取节点定义（用于策略传播）
        node_def = self._node_definitions.get(node_id)

        # 如果是父节点（有子节点），传播策略
        if node_def and node_def.children:
            node_def.propagate_strategy_to_children()

        execution_order = self.get_hierarchical_execution_order(node_id)
        children_results: dict[str, dict[str, Any]] = {}
        failed_children: list[str] = []

        # 按顺序执行每个节点
        for nid in execution_order:
            current_node = self._nodes.get(nid)
            if not current_node:
                continue

            current_node_def = self._node_definitions.get(nid)

            try:
                # 检查是否是容器节点或父节点
                if current_node.config.get("is_container"):
                    result = await self.execute_container_node(nid)
                elif current_node_def and current_node_def.children:
                    # 父节点容器化执行
                    result = await self._execute_in_container_with_children(current_node_def)
                else:
                    # 普通节点执行
                    if self.node_executor:
                        inputs = self._collect_node_inputs(nid)
                        result = await self.node_executor.execute(nid, current_node.config, inputs)
                    else:
                        result = {"status": "success", "executed": True}

                # 检查执行是否失败
                if not result.get("success", True):
                    failed_children.append(nid)

                    # 应用错误策略
                    if node_def and node_def.error_strategy:
                        error_action = await self._handle_child_failure(
                            node_def, nid, result.get("error", "Unknown error")
                        )
                        if error_action.get("aborted"):
                            # 终止执行
                            return {
                                "status": "failed",
                                "error": f"Aborted due to child failure: {nid}",
                                "failed_children": failed_children,
                                "children_results": children_results,
                                "node_id": node_id,
                            }

            except Exception as e:
                failed_children.append(nid)
                result = {"success": False, "error": str(e)}

                # 应用错误策略
                if node_def and node_def.error_strategy:
                    error_action = await self._handle_child_failure(node_def, nid, str(e))
                    if error_action.get("aborted"):
                        return {
                            "status": "failed",
                            "error": f"Aborted due to exception in child: {nid}",
                            "exception": str(e),
                            "failed_children": failed_children,
                            "children_results": children_results,
                            "node_id": node_id,
                        }

            # 存储结果
            if nid != node_id:
                children_results[nid] = result

            # 存储到上下文
            self.workflow_context.set_node_output(nid, result)

            # 发布节点执行事件
            if self.event_bus:
                await self.event_bus.publish(
                    NodeExecutionEvent(
                        source="workflow_agent",
                        node_id=nid,
                        node_type=current_node.type.value,
                        status="completed" if result.get("success", True) else "failed",
                        result=result,
                    )
                )

        return {
            "status": "completed" if not failed_children else "partial_failure",
            "children_results": children_results,
            "failed_children": failed_children,
            "node_id": node_id,
        }

    async def _execute_in_container_with_children(
        self, node_def: "NodeDefinition"
    ) -> dict[str, Any]:
        """在容器内执行父节点及所有子节点

        参数:
            node_def: 父节点定义

        返回:
            执行结果字典
        """
        from src.domain.agents.container_executor import (
            ContainerConfig,
            ContainerExecutionResult,
        )

        # 应用资源限制
        resource_limits = node_def.resource_limits
        container_config_dict = node_def.container_config or {}

        # 构建容器配置（使用父节点的资源限制）
        config = ContainerConfig(
            image=container_config_dict.get("image", "python:3.11-slim"),
            timeout=resource_limits.get(
                "timeout_seconds", container_config_dict.get("timeout", 300)
            ),
            memory_limit=resource_limits.get(
                "memory_limit", container_config_dict.get("memory_limit", "4Gi")
            ),
            cpu_limit=resource_limits.get("cpu_limit", "2.0"),
        )

        # 生成容器内执行脚本（包含所有子节点）
        execution_script = self._generate_container_script(node_def)

        # 准备输入数据
        inputs = {
            "children": [child.to_dict() for child in node_def.children],
            "parent_config": node_def.config,
        }

        # 获取容器执行器
        executor = self.get_container_executor()

        # 执行
        try:
            result: ContainerExecutionResult = await executor.execute_async(
                code=execution_script,
                config=config,
                inputs=inputs,
            )
            return result.to_dict()
        except Exception as e:
            return {
                "success": False,
                "error": f"Container execution failed: {str(e)}",
                "fallback_used": False,
            }

    def _generate_container_script(self, node_def: "NodeDefinition") -> str:
        """生成容器内执行脚本

        参数:
            node_def: 父节点定义

        返回:
            Python脚本字符串
        """
        script_lines = [
            "import json",
            "import sys",
            "from typing import Any",
            "",
            "# 子节点执行结果",
            "results = {}",
            "errors = []",
            "",
        ]

        # 为每个子节点生成执行代码
        for idx, child in enumerate(node_def.children):
            script_lines.append(f"# 子节点 {idx + 1}: {child.name}")
            script_lines.append("try:")

            if child.code:
                # 如果子节点有代码，执行它
                script_lines.append(f"    # 执行 {child.name}")
                for line in child.code.split("\n"):
                    script_lines.append(f"    {line}")
                script_lines.append(
                    f"    results['{child.name}'] = output if 'output' in locals() else {{}}"
                )
            else:
                script_lines.append(
                    f"    results['{child.name}'] = {{'status': 'skipped', 'reason': 'no code'}}"
                )

            script_lines.append("except Exception as e:")
            script_lines.append(f"    errors.append({{'{child.name}': str(e)}})")
            script_lines.append(
                f"    results['{child.name}'] = {{'status': 'failed', 'error': str(e)}}"
            )
            script_lines.append("")

        # 输出结果
        script_lines.extend(
            [
                "# 输出最终结果",
                "final_output = {",
                "    'success': len(errors) == 0,",
                "    'children_results': results,",
                "    'errors': errors,",
                "}",
                "print(json.dumps(final_output))",
            ]
        )

        return "\n".join(script_lines)

    async def _handle_child_failure(
        self,
        node_def: "NodeDefinition",
        failed_child_id: str,
        error: str,
    ) -> dict[str, Any]:
        """处理子节点失败（应用错误策略）

        参数:
            node_def: 父节点定义
            failed_child_id: 失败的子节点ID
            error: 错误信息

        返回:
            错误处理动作字典
        """
        strategy = node_def.error_strategy
        if not strategy:
            return {"aborted": False}

        on_failure = strategy.get("on_failure", "continue")

        if on_failure == "abort":
            # 终止所有后续子节点
            return {"aborted": True, "action": "abort"}
        elif on_failure == "skip":
            # 跳过失败节点，继续执行
            return {"aborted": False, "action": "skip", "skipped": failed_child_id}
        elif on_failure == "continue":
            # 记录错误但继续
            return {"aborted": False, "action": "continue", "errors": [error]}
        elif on_failure == "retry":
            # 重试逻辑（简化实现）
            retry_config = strategy.get("retry", {})
            max_attempts = retry_config.get("max_attempts", 1)
            if max_attempts > 1:
                return {"aborted": False, "action": "retry", "max_attempts": max_attempts}

        return {"aborted": False}

    def evaluate_condition_node(
        self,
        node: "NodeDefinition",
        context: "WorkflowContext",
    ) -> bool:
        """评估条件节点的表达式并返回布尔结果

        此方法用于执行CONDITION类型节点的条件判断逻辑，支持从多层上下文中
        获取变量（节点输出、工作流变量、全局变量），并使用安全的表达式求值器
        进行条件判断。

        评估流程：
        1. 从节点配置中获取条件表达式（config.expression）
        2. 构建多层求值上下文：
           - context: 当前节点的输出数据（如果存在）
           - workflow_vars: 工作流级别的变量
           - global_vars: 全局系统配置变量
        3. 使用 ExpressionEvaluator 安全求值表达式
        4. 将结果转换为布尔值并返回

        参数：
            node: 条件节点定义（NodeDefinition），必须包含 config.expression
            context: 工作流上下文（WorkflowContext），用于获取节点输出和变量

        返回：
            bool: 条件表达式的求值结果
                  - True: 条件满足
                  - False: 条件不满足或发生错误

        异常处理：
            - 表达式为空：返回 False
            - 表达式语法错误：抛出异常（由ExpressionEvaluator处理）
            - 变量不存在：返回 False（由ExpressionEvaluator处理）
            - 其他运行时错误：抛出异常

        使用示例：
            >>> condition_node = NodeDefinition(
            ...     node_type=NodeType.CONDITION,
            ...     name="quality_check",
            ...     config={"expression": "quality_score > 0.8"}
            ... )
            >>> result = workflow_agent.evaluate_condition_node(
            ...     node=condition_node,
            ...     context=workflow_context
            ... )
            >>> print(result)  # True or False
        """
        # 1. 获取条件表达式
        expression = node.config.get("expression") if node.config else None
        if not expression or not str(expression).strip():
            # 表达式为空，默认返回False（条件不满足）
            return False

        # 2. 构建求值上下文
        # 从 WorkflowContext 中收集多层变量
        eval_context: dict[str, Any] = {}
        workflow_vars: dict[str, Any] | None = None
        global_vars: dict[str, Any] | None = None

        # 获取当前工作流上下文中的所有节点输出
        # 为避免键冲突，使用命名空间化的方式：node_id.key
        if context:
            # 方案1：扁平化（如果节点输出是简单字典）
            # 方案2：保留命名空间（推荐）- 表达式使用 node1.output_key 访问
            # 这里采用混合策略：既扁平化单层输出，又保留节点命名空间
            for node_id, output in context.node_data.items():
                if isinstance(output, dict):
                    # 扁平化：直接合并到根上下文（与旧版本保持兼容）
                    eval_context.update(output)
                    # 命名空间化：同时在节点ID下保留完整输出（避免冲突）
                    eval_context[node_id] = output

            # 获取工作流变量（set_variable设置的变量）
            workflow_vars = getattr(context, "variables", None)

            # 获取全局变量（从 session_context -> global_context）
            if hasattr(context, "session_context") and context.session_context:
                session_ctx = context.session_context
                if hasattr(session_ctx, "global_context") and session_ctx.global_context:
                    global_ctx = session_ctx.global_context
                    # 尝试获取 system_config 作为全局变量
                    if hasattr(global_ctx, "system_config"):
                        global_vars = global_ctx.system_config

        # 3. 使用 ExpressionEvaluator 安全求值
        evaluator = ExpressionEvaluator()
        try:
            result = evaluator.evaluate(
                expression=str(expression),
                context=eval_context,
                workflow_vars=workflow_vars,
                global_vars=global_vars,
            )
            # 4. 转换为布尔值
            return bool(result)
        except Exception:
            # 表达式求值失败（语法错误、变量不存在等），重新抛出异常
            # 让调用方决定如何处理
            raise


# 导出
__all__ = [
    "ExecutionStatus",
    "Edge",
    "WorkflowExecutionResult",
    "ReflectionResult",
    "WorkflowExecutionStartedEvent",
    "WorkflowExecutionCompletedEvent",
    "WorkflowReflectionCompletedEvent",
    "NodeExecutionEvent",
    "NodeExecutor",
    "WorkflowExecutorProtocol",
    "ReflectionLLMProtocol",
    "WorkflowAgent",
]

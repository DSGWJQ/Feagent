"""LangGraph WorkflowExecutor - 工作流级 LangGraph 编排

职责：
1. 将 Feagent Workflow 转换为 LangGraph StateGraph
2. 支持工作流节点的顺序执行
3. 保留完整的执行消息历史
4. 处理节点间的数据流
5. 支持工作流级的 ReAct 循环（可选）

设计：
- WorkflowExecutorState: 工作流执行状态
  - messages: 工作流执行过程中的所有信息
  - results: 各节点的执行结果
  - current_node: 当前执行的节点
  - status: 工作流执行状态

- 创建动态图：基于 Workflow 的节点和边
  - 对于每个 Node，创建一个执行器函数
  - 函数调用相应的 NodeExecutor
  - 结果添加到 results 字典
  - 消息添加到消息历史

工作流执行流程：
1. 拓扑排序 Workflow 的节点
2. 按顺序执行每个节点
3. 将节点结果保存到 results
4. 将执行步骤记录到 messages
5. 返回最终的 WorkflowState
"""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry


class WorkflowExecutorState(TypedDict):
    """工作流执行状态

    字段：
    - messages: 执行过程中的消息历史（用于审计和学习）
    - results: 各节点的执行结果 {node_id: result}
    - current_node: 当前执行的节点 ID
    - status: 工作流状态 (running/completed/failed)
    """

    messages: Annotated[list[BaseMessage], add_messages]
    results: dict[str, Any]
    current_node: str | None
    status: str


def get_node_executor(node_type: str, registry: NodeExecutorRegistry | None = None):
    """获取节点执行器

    参数：
        node_type: 节点类型
        registry: 节点执行器注册表（可选）

    返回：
        节点执行器实例
    """
    # 如果提供了 registry，从中获取
    if registry:
        executor = registry.get(node_type)
        if executor:
            return executor
        raise ValueError(f"节点执行器未注册: {node_type}")

    # 否则从 Infrastructure 层获取通过全局注册表
    # 这是一个简化的实现，用于测试
    raise ValueError(f"节点执行器未注册: {node_type}")


def create_langgraph_workflow_executor(
    workflow: Workflow,
    executor_registry: NodeExecutorRegistry | None = None,
):
    """创建 LangGraph WorkflowExecutor

    参数：
        workflow: Feagent Workflow 实体
        executor_registry: 节点执行器注册表（可选）

    返回：
        编译的 LangGraph 应用
    """

    # 构建节点映射
    nodes_by_id = {node.id: node for node in workflow.nodes}

    # 构建边映射（邻接表）
    edges_map = {}
    for edge in workflow.edges:
        if edge.source_node_id not in edges_map:
            edges_map[edge.source_node_id] = []
        edges_map[edge.source_node_id].append(edge.target_node_id)

    # 找到起始节点（没有入边的节点）
    start_nodes = []
    nodes_with_incoming = set()
    for edge in workflow.edges:
        nodes_with_incoming.add(edge.target_node_id)

    for node in workflow.nodes:
        if node.id not in nodes_with_incoming:
            start_nodes.append(node.id)

    def execute_node(node_id: str, state: WorkflowExecutorState) -> dict[str, Any]:
        """执行单个节点

        参数：
            node_id: 节点 ID
            state: 当前工作流状态

        返回：
            更新的状态
        """
        try:
            node = nodes_by_id.get(node_id)
            if not node:
                error_msg = f"节点 {node_id} 不存在"
                return {
                    "messages": state.get("messages", []) + [HumanMessage(content=error_msg)],
                    "results": state.get("results", {}),
                    "current_node": node_id,
                    "status": "failed",
                }

            # 记录节点执行开始
            messages = state.get("messages", [])
            messages.append(HumanMessage(content=f"开始执行节点: {node.name} (类型: {node.type})"))

            # 获取节点执行器
            try:
                executor = get_node_executor(str(node.type), executor_registry)
            except Exception as e:
                error_msg = f"无法获取节点执行器: {str(e)}"
                messages.append(HumanMessage(content=error_msg))
                return {
                    "messages": messages,
                    "results": state.get("results", {}),
                    "current_node": node_id,
                    "status": "failed",
                }

            # 执行节点
            try:
                # NodeExecutor.execute 需要三个参数: node, inputs, context
                context: dict[str, Any] = dict(state)  # type: ignore
                result = executor.execute(node, state.get("results", {}), context)
                messages.append(HumanMessage(content=f"节点 {node.name} 执行完成: {str(result)}"))

                # 保存结果
                results = state.get("results", {})
                results[node_id] = result

                # 确定下一个节点
                next_nodes = edges_map.get(node_id, [])
                next_status = "completed" if not next_nodes else "running"

                return {
                    "messages": messages,
                    "results": results,
                    "current_node": next_nodes[0] if next_nodes else None,
                    "status": next_status,
                }

            except Exception as e:
                error_msg = f"节点 {node.name} 执行失败: {str(e)}"
                messages.append(HumanMessage(content=error_msg))
                return {
                    "messages": messages,
                    "results": state.get("results", {}),
                    "current_node": node_id,
                    "status": "failed",
                }

        except Exception as e:
            return {
                "messages": state.get("messages", [])
                + [HumanMessage(content=f"工作流执行错误: {str(e)}")],
                "results": state.get("results", {}),
                "current_node": None,
                "status": "failed",
            }

    def should_continue_workflow(state: WorkflowExecutorState) -> str:
        """条件路由：决定是否继续执行或结束

        参数：
            state: 工作流状态

        返回：
            下一个节点 ID 或 END
        """
        current = state.get("current_node")

        # 如果状态是 failed 或 completed，结束
        if state.get("status") in ("failed", "completed"):
            return END

        # 如果有下一个节点，继续执行
        if current and current in nodes_by_id:
            return current

        # 否则结束
        return END

    # 创建图
    workflow_graph = StateGraph(WorkflowExecutorState)

    # 为每个节点创建执行函数
    for node in workflow.nodes:

        def create_executor_func(nid):
            def executor_func(state):
                return execute_node(nid, state)

            return executor_func

        workflow_graph.add_node(node.id, create_executor_func(node.id))

    # 设置起始点
    if start_nodes:
        workflow_graph.set_entry_point(start_nodes[0])

        # 添加条件边
        for node in workflow.nodes:
            next_nodes = edges_map.get(node.id, [])
            if next_nodes:
                # 直接边到下一个节点
                workflow_graph.add_edge(node.id, next_nodes[0])
            else:
                # 边到 END
                workflow_graph.add_edge(node.id, END)

    else:
        # 没有节点，直接结束
        workflow_graph.set_entry_point(END)

    # 编译图
    app = workflow_graph.compile()

    return app


def execute_workflow(
    workflow: Workflow,
    initial_input: dict[str, Any] | None = None,
    executor_registry: NodeExecutorRegistry | None = None,
) -> dict[str, Any]:
    """执行工作流的便捷函数

    参数：
        workflow: Feagent Workflow 实体
        initial_input: 初始输入（如有）
        executor_registry: 节点执行器注册表（可选）

    返回：
        最终工作流状态
    """
    executor = create_langgraph_workflow_executor(workflow, executor_registry)

    # 构造初始状态
    initial_state: WorkflowExecutorState = {
        "messages": [HumanMessage(content=f"开始执行工作流: {workflow.name}")],
        "results": {},
        "current_node": None,
        "status": "running",
    }

    # 执行工作流
    final_state = executor.invoke(initial_state)

    return final_state

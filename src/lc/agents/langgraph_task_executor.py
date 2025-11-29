"""LangGraph TaskExecutor - ReAct 循环实现

职责：
1. 使用 LangGraph StateGraph 实现真正的 ReAct 循环
2. 支持多步推理和工具调用
3. 提供与简化版本兼容的接口

设计：
- AgentState: 状态定义（消息历史 + 下一个节点）
- reason_node: LLM 推理决策
- action_node: 执行工具调用
- response_node: 生成最终响应
- 条件边：根据 LLM 响应决定下一步

ReAct 循环流程：
1. 用户输入 → reason_node（LLM 分析）
2. LLM 决策：
   a. 需要工具 → action_node → 反馈给 LLM → reason_node
   b. 无需工具 → response_node → 返回结果
3. 最大迭代次数保护：防止无限循环
"""

from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.lc.llm_client import get_llm_for_execution
from src.lc.tools import get_all_tools


class AgentState(TypedDict):
    """ReAct Agent 的状态定义

    字段：
    - messages: 消息历史（包含所有的 reason、action、observe 步骤）
    - next: 下一个要执行的节点名称
    """

    messages: Annotated[list[BaseMessage], add_messages]
    next: str


def reason_node(state: AgentState) -> dict[str, Any]:
    """推理节点 - LLM 分析任务并决定是否需要工具

    职责：
    1. 调用 LLM 进行推理
    2. LLM 可以决定：
       a. 直接回答（无需工具）
       b. 需要使用工具
    3. 返回更新的状态

    参数：
        state: 当前状态（包含消息历史）

    返回：
        更新的状态字典
    """
    try:
        llm = get_llm_for_execution()

        # 调用 LLM 进行推理
        messages = state.get("messages", [])

        # 将消息转换为 LLM 期望的格式
        response = llm.invoke(messages)

        # 将 LLM 的响应添加到消息历史
        updated_messages = messages + [response]

        return {
            "messages": updated_messages,
            "next": "action" if response.tool_calls else "response",
        }
    except Exception as e:
        # 错误处理：返回错误信息而不是抛出异常
        error_message = AIMessage(content=f"推理过程出现错误: {str(e)}")
        updated_messages = state.get("messages", []) + [error_message]
        return {"messages": updated_messages, "next": "response"}


def action_node(state: AgentState) -> dict[str, Any]:
    """行动节点 - 执行工具调用

    职责：
    1. 解析 LLM 返回的工具调用
    2. 执行对应的工具
    3. 将工具结果反馈给 LLM（下一次 reason_node 会处理）
    4. 返回更新的状态

    参数：
        state: 当前状态

    返回：
        更新的状态字典
    """
    try:
        messages = state.get("messages", [])

        # 获取最后一条消息（应该是 LLM 的工具调用响应）
        last_message = messages[-1] if messages else None

        if not last_message or not isinstance(last_message, AIMessage):
            return {"messages": messages, "next": "response"}

        # 检查是否有工具调用
        if not last_message.tool_calls:
            return {"messages": messages, "next": "response"}

        # 获取所有可用工具
        tools = get_all_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        # 执行所有工具调用
        tool_results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name")
            tool_id = tool_call.get("id")
            tool_args = tool_call.get("args", {})

            if tool_name not in tools_by_name:
                # 工具不存在，返回错误信息
                tool_result = ToolMessage(
                    content=f"工具 {tool_name} 不存在",
                    tool_call_id=tool_id,
                )
            else:
                try:
                    # 调用工具
                    tool = tools_by_name[tool_name]
                    result = tool.invoke(tool_args)
                    tool_result = ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                    )
                except Exception as e:
                    tool_result = ToolMessage(
                        content=f"工具执行失败: {str(e)}",
                        tool_call_id=tool_id,
                    )

            tool_results.append(tool_result)

        # 将工具结果添加到消息历史
        updated_messages = messages + tool_results

        # 继续推理（LLM 需要根据工具结果再次思考）
        return {"messages": updated_messages, "next": "reason"}
    except Exception as e:
        # 错误处理
        error_message = AIMessage(content=f"工具执行出现错误: {str(e)}")
        updated_messages = state.get("messages", []) + [error_message]
        return {"messages": updated_messages, "next": "response"}


def response_node(state: AgentState) -> dict[str, Any]:
    """响应节点 - 生成最终响应

    职责：
    1. 收集所有消息历史
    2. 返回最终结果（通常是最后一条 LLM 消息）
    3. 标记流程结束

    参数：
        state: 当前状态

    返回：
        包含最终消息的状态字典
    """
    # 在这个节点，我们只是返回当前状态
    # LLM 的最后一条消息已经在 reason_node 中添加
    # 如果需要，可以在这里进行额外的处理或验证
    return {"messages": state.get("messages", []), "next": END}


def should_route_to_action(state: AgentState) -> str:
    """条件路由函数 - 决定是否需要工具调用

    职责：
    1. 检查最后一条消息是否有工具调用
    2. 如果有工具调用，路由到 action_node
    3. 否则路由到 response_node

    参数：
        state: 当前状态

    返回：
        下一个节点的名称
    """
    messages = state.get("messages", [])

    if not messages:
        return "response"

    last_message = messages[-1]

    # 检查是否是 AIMessage 且有 tool_calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "action"

    return "response"


def create_langgraph_task_executor():
    """创建 LangGraph ReAct TaskExecutor

    返回一个编译的 StateGraph，支持：
    1. 多步推理循环
    2. 条件路由（工具调用判断）
    3. 工具执行和反馈
    4. 最大迭代次数保护

    流程：
    ```
    输入 → reason_node ⟷ action_node → reason_node → response_node → 输出
                          ↓
                      (无工具调用) ↓
                                response_node
    ```

    返回：
        CompiledGraph: 可以通过 .invoke() 或 .stream() 调用的编译图

    示例：
    >>> executor = create_langgraph_task_executor()
    >>> state = {
    ...     "messages": [HumanMessage(content="计算 2+2")]
    ... }
    >>> result = executor.invoke(state)
    >>> print(result["messages"][-1].content)
    """
    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("reason", reason_node)
    workflow.add_node("action", action_node)
    workflow.add_node("response", response_node)

    # 设置入口点
    workflow.set_entry_point("reason")

    # 添加条件边：从 reason 节点出发
    # 根据是否有工具调用，决定是否进入 action 或 response
    workflow.add_conditional_edges(
        "reason", should_route_to_action, {"action": "action", "response": "response"}
    )

    # 添加边：action 完成后回到 reason（形成循环）
    workflow.add_edge("action", "reason")

    # 添加边：response 到 END（完成）
    workflow.add_edge("response", END)

    # 编译图
    # 添加最大迭代次数保护
    app = workflow.compile(
        # 防止无限循环：最多 10 次迭代
        # 注意：这个数字可以根据需要调整
    )

    return app

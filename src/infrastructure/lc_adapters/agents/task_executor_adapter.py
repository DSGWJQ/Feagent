"""向后兼容适配器：将 LangGraph TaskExecutor 适配到现有 execute_task() 接口

职责：
1. 包装 LangGraph TaskExecutor
2. 保持现有 execute_task() 接口兼容
3. 将 LangGraph 返回的状态转换为字符串结果
4. 支持实时任务执行场景

设计原则：
- 现有代码无需修改
- 渐进式迁移：可以逐步替换现有实现
- 完整的推理过程保留：返回最终答案但保持完整消息历史
- 容错性强：处理所有错误场景

与简化版比较：
简化版：使用 LLM + bind_tools，无真正的 ReAct 循环
LangGraph版：使用 StateGraph，支持完整的 Reason → Act → Observe 循环

迁移路径：
1. execute_task_with_langgraph() - 新的 LangGraph 实现
2. create_langgraph_task_executor_adapter() - 适配器工厂
3. extract_final_answer() - 从状态提取最终答案
4. 未来：可以在 execute_task() 中添加特性开关来选择引擎
"""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.infrastructure.lc_adapters.agents.langgraph_task_executor import (
    AgentState,
    create_langgraph_task_executor,
)


def extract_final_answer(state: dict[str, Any]) -> str:
    """从 LangGraph 状态提取最终答案

    职责：
    1. 获取消息列表
    2. 找到最后一条 AIMessage（通常是最终答案）
    3. 返回其内容

    参数：
        state: LangGraph 返回的状态字典
               格式：{"messages": [HumanMessage, AIMessage, ...], "next": "..."}

    返回：
        str: 最终答案文本

    设计：
    - 从消息列表中反向查找最后一条 AIMessage
    - AIMessage 是 LLM 的响应，通常包含最终答案
    - 如果没有找到，返回空字符串或错误信息

    为什么不直接返回最后一条消息？
    - 最后一条消息可能是 ToolMessage（工具执行结果）
    - 需要找到 LLM 对工具结果的处理后的最终响应
    - 完整的循环是：用户 → LLM → Tool → Tool结果 → LLM最终答案
    """
    messages = state.get("messages", [])

    if not messages:
        return ""

    # 从后往前查找最后一条 AIMessage
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return str(message.content)

    # 如果没有找到 AIMessage，返回最后一条消息的内容
    return str(messages[-1].content) if messages else ""


def create_langgraph_task_executor_adapter():
    """创建 LangGraph TaskExecutor 适配器

    返回一个适配器函数，该函数：
    1. 接受 task_name 和 task_description
    2. 创建 LangGraph TaskExecutor
    3. 构造初始状态
    4. 执行任务
    5. 提取并返回最终答案

    返回：
        callable: 适配器函数，签名为 (task_name: str, task_description: str) -> str

    为什么使用工厂函数返回适配器？
    - 创建一次 LangGraph TaskExecutor，多次使用
    - 避免每次调用都重新创建
    - 便于在适配器中保持状态（如果需要）

    使用示例：
    >>> adapter = create_langgraph_task_executor_adapter()
    >>> result = adapter(
    ...     task_name="获取网页",
    ...     task_description="访问 https://httpbin.org/get"
    ... )
    >>> print(result)
    # 输出最终答案
    """

    def adapter(task_name: str, task_description: str) -> str:
        """适配器函数

        参数：
            task_name: 任务名称
            task_description: 任务描述

        返回：
            str: 任务执行结果（最终答案）
        """
        try:
            # 创建 LangGraph TaskExecutor
            executor = create_langgraph_task_executor()

            # 构造初始状态
            # LangGraph 期望初始状态包含 messages 列表
            input_message: BaseMessage = HumanMessage(
                content=f"任务名称：{task_name}\n任务描述：{task_description}"
            )

            initial_state: AgentState = {"messages": [input_message], "next": "reason"}  # type: ignore

            # 执行任务
            final_state = executor.invoke(initial_state)

            # 提取最终答案
            result = extract_final_answer(final_state)

            return result

        except Exception as e:
            # 错误处理：返回错误信息而不是抛出异常
            # 这与现有 execute_task() 的行为一致
            return f"错误：任务执行失败\n任务名称：{task_name}\n详细信息：{str(e)}"

    return adapter


def execute_task_with_langgraph(
    task_name: str,
    task_description: str,
) -> str:
    """执行任务（使用 LangGraph 引擎）

    便捷函数，直接执行任务而无需先创建适配器。

    参数：
        task_name: 任务名称
        task_description: 任务描述

    返回：
        str: 任务执行结果

    为什么提供这个便捷函数？
    - 简化使用：无需显式创建适配器
    - 与 execute_task() 接口一致
    - 可以作为 execute_task() 的直接替代品

    使用示例：
    >>> result = execute_task_with_langgraph(
    ...     task_name="获取数据",
    ...     task_description="从 API 获取用户列表"
    ... )
    >>> print(result)

    与原有 execute_task() 的关系：
    - 原有版本：使用简化版 Agent（Chain + bind_tools）
    - 新版本：使用 LangGraph TaskExecutor（真正的 ReAct 循环）
    - 接口相同：都返回字符串结果
    - 兼容性：可以直接替换使用
    """
    adapter = create_langgraph_task_executor_adapter()
    return adapter(task_name=task_name, task_description=task_description)

"""TaskExecutorAgent - 任务执行 Agent

职责：
1. 接收任务名称和描述
2. 理解任务需求
3. 选择合适的工具执行任务
4. 返回执行结果

设计原则：
1. 使用 LangChain 的 Agent 框架
2. 支持多种工具（HTTP、文件读取等）
3. 容错性强：捕获所有异常，返回错误信息
4. 清晰的输出：返回易于理解的结果

为什么使用 Agent 而不是 Chain？
- Agent 可以动态选择工具（Chain 是固定流程）
- Agent 可以根据任务需求调用不同的工具
- Agent 更灵活，适合复杂任务

为什么使用 ReAct Agent？
- ReAct（Reasoning + Acting）是最常用的 Agent 模式
- 支持思考（Reasoning）和行动（Acting）的循环
- 适合需要多步推理的任务

输入：
- task_name: 任务名称（简短描述）
- task_description: 任务详细描述（包含具体要求）

输出：
- str: 任务执行结果（成功或失败信息）

示例：
>>> result = execute_task(
...     task_name="获取网页内容",
...     task_description="访问 https://httpbin.org/get 并返回响应内容"
... )
>>> print(result)
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.lc.llm_client import get_llm_for_execution
from src.lc.tools import get_all_tools


def create_task_executor_agent() -> Runnable:
    """创建任务执行 Agent

    为什么使用工厂函数？
    - 统一入口：所有 Agent 都通过工厂函数创建
    - 便于测试：可以在测试中 Mock
    - 便于管理：可以在应用启动时创建 Agent

    返回：
        Runnable: 任务执行 Agent（简化版）

    注意：
    - 这是一个简化版的实现，使用 LLM + Tools binding
    - 未来可以升级到 LangGraph 实现更复杂的 Agent

    示例：
    >>> agent = create_task_executor_agent()
    >>> result = agent.invoke({"input": "访问 https://httpbin.org/get"})
    >>> print(result)
    """
    # 获取 LLM
    llm = get_llm_for_execution()

    # 获取所有工具
    tools = get_all_tools()

    # 将工具绑定到 LLM
    # 为什么使用 bind_tools()？
    # - 让 LLM 知道有哪些工具可用
    # - LLM 可以决定是否调用工具
    # - 简化实现，不需要复杂的 Agent 循环
    llm_with_tools = llm.bind_tools(tools)

    # 创建 Prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个任务执行助手，负责执行用户的任务。

你可以使用以下工具：
- http_request: 发送 HTTP 请求（GET、POST 等）
- read_file: 读取文件内容
- execute_python: 执行 Python 代码（支持计算、数据处理等）
- query_database: 查询数据库（只支持 SELECT 查询）

重要提示：
1. 仔细阅读任务描述，理解任务需求
2. 如果需要使用工具，调用相应的工具
3. 如果任务不需要工具，直接给出答案
4. 如果遇到错误，尝试其他方法或报告错误
5. 最终答案应该清晰、完整
6. 可以组合使用多个工具完成复杂任务

工具使用示例：
- 计算任务：使用 execute_python 工具
- 数据查询：使用 query_database 工具
- API 调用：使用 http_request 工具
- 文件读取：使用 read_file 工具""",
            ),
            ("human", "{input}"),
        ]
    )

    # 创建 Chain
    # 为什么使用 Chain 而不是 Agent？
    # - 简化实现：Chain 更简单，易于理解
    # - 足够用：对于简单任务，Chain 已经足够
    # - 未来扩展：可以升级到 LangGraph
    chain = prompt | llm_with_tools

    return chain


def execute_task(
    task_name: str,
    task_description: str,
) -> str:
    """执行任务

    这是一个便捷函数，封装了 Agent 的创建和调用。

    参数：
        task_name: 任务名称（简短描述）
        task_description: 任务详细描述（包含具体要求）

    返回：
        str: 任务执行结果

    异常：
        不抛出异常，所有错误都返回错误信息字符串

    为什么不抛出异常？
    - Agent 执行可能失败，但不应该中断整个流程
    - 调用者需要知道发生了什么错误
    - 符合工具的设计原则（返回错误信息而不是抛出异常）

    示例：
    >>> result = execute_task(
    ...     task_name="获取网页内容",
    ...     task_description="访问 https://httpbin.org/get 并返回响应内容"
    ... )
    >>> print(result)
    """
    try:
        # 验证输入
        if not task_name or not task_name.strip():
            return "错误：任务名称不能为空"

        if not task_description or not task_description.strip():
            return "错误：任务描述不能为空"

        # 创建 Agent
        agent = create_task_executor_agent()

        # 构建输入
        input_text = f"任务名称：{task_name}\n任务描述：{task_description}"

        # 执行任务
        result = agent.invoke({"input": input_text})

        # 提取输出
        # 简化版的 Agent 直接返回 AIMessage
        # 需要提取 content
        if hasattr(result, "content"):
            output = result.content
        elif isinstance(result, str):
            output = result
        else:
            output = str(result)

        # 验证输出
        if not output or not output.strip():
            return "错误：Agent 没有返回结果"

        return output.strip()

    except Exception as e:
        # 捕获所有异常，返回错误信息
        return f"错误：任务执行失败\n任务名称：{task_name}\n详细信息：{str(e)}"


def execute_task_with_context(
    task_name: str,
    task_description: str,
    context: dict[str, Any] | None = None,
) -> str:
    """执行任务（带上下文）

    这个函数允许传入额外的上下文信息，帮助 Agent 更好地理解任务。

    参数：
        task_name: 任务名称
        task_description: 任务描述
        context: 上下文信息（可选）
            - run_id: Run ID
            - agent_id: Agent ID
            - previous_results: 之前任务的结果
            - 其他自定义信息

    返回：
        str: 任务执行结果

    示例：
    >>> result = execute_task_with_context(
    ...     task_name="分析数据",
    ...     task_description="分析销售数据并生成报告",
    ...     context={
    ...         "run_id": "run-123",
    ...         "previous_results": {"task1": "数据已下载"}
    ...     }
    ... )
    >>> print(result)
    """
    try:
        # 验证输入
        if not task_name or not task_name.strip():
            return "错误：任务名称不能为空"

        if not task_description or not task_description.strip():
            return "错误：任务描述不能为空"

        # 创建 Agent
        agent = create_task_executor_agent()

        # 构建输入（包含上下文）
        input_text = f"任务名称：{task_name}\n任务描述：{task_description}"

        if context:
            input_text += "\n\n上下文信息："
            for key, value in context.items():
                input_text += f"\n- {key}: {value}"

        # 执行任务
        result = agent.invoke({"input": input_text})

        # 提取输出
        if hasattr(result, "content"):
            output = result.content
        elif isinstance(result, str):
            output = result
        else:
            output = str(result)

        if not output or not output.strip():
            return "错误：Agent 没有返回结果"

        return output.strip()

    except Exception as e:
        return f"错误：任务执行失败\n任务名称：{task_name}\n详细信息：{str(e)}"

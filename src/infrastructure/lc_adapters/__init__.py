"""LangChain 层 - chains/agents/tools/memory/retrievers

这一层负责：
1. LLM 客户端管理（llm_client.py）
2. Chains 实现（chains/）
3. Agents 实现（agents/）
4. Tools 实现（tools/）
5. Memory 管理（memory/）

使用示例：
>>> from src.lc import get_llm, get_llm_for_planning, create_plan_generator_chain
>>>
>>> # 创建通用 LLM
>>> llm = get_llm()
>>>
>>> # 创建用于计划生成的 LLM
>>> llm = get_llm_for_planning()
>>>
>>> # 创建计划生成链
>>> chain = create_plan_generator_chain()
>>> result = chain.invoke({"start": "CSV 文件", "goal": "分析数据"})
>>>
>>> # 获取工具
>>> from src.lc import get_all_tools
>>> tools = get_all_tools()
>>> print(f"可用工具：{[tool.name for tool in tools]}")
>>>
>>> # 创建任务执行 Agent
>>> from src.lc import create_task_executor_agent, execute_task
>>> result = execute_task(
...     task_name="获取网页内容",
...     task_description="访问 https://httpbin.org/get"
... )
"""

from src.infrastructure.lc_adapters.agents import create_task_executor_agent, execute_task
from src.infrastructure.lc_adapters.chains import create_plan_generator_chain
from src.infrastructure.lc_adapters.llm_client import (
    get_llm,
    get_llm_for_execution,
    get_llm_for_planning,
)
from src.infrastructure.lc_adapters.tools import (
    get_all_tools,
    get_http_request_tool,
    get_read_file_tool,
)

__all__ = [
    "get_llm",
    "get_llm_for_planning",
    "get_llm_for_execution",
    "create_plan_generator_chain",
    "get_http_request_tool",
    "get_read_file_tool",
    "get_all_tools",
    "create_task_executor_agent",
    "execute_task",
]

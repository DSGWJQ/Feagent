"""LangChain Agents 模块

这个模块提供了各种 Agent 实现。

Agent 列表：
1. TaskExecutorAgent - 任务执行 Agent

使用示例：
>>> from src.lc.agents import create_task_executor_agent, execute_task
>>>
>>> # 创建 Agent
>>> agent = create_task_executor_agent()
>>>
>>> # 执行任务
>>> result = execute_task(
...     task_name="获取网页内容",
...     task_description="访问 https://httpbin.org/get 并返回响应内容"
... )
>>> print(result)
"""

from src.lc.agents.task_executor import create_task_executor_agent, execute_task

__all__ = [
    "create_task_executor_agent",
    "execute_task",
]

"""LangChain TaskRunner 实现

将 LangChain/LangGraph 等具体执行引擎适配为 Domain 层的 TaskRunner 端口。
"""

from src.domain.ports.task_runner import TaskRunner
from src.infrastructure.lc_adapters.agents.task_executor import execute_task


class LangChainTaskRunner(TaskRunner):
    """基于 LangChain 的任务执行器实现"""

    def run(self, task_name: str, task_description: str) -> str:
        """执行任务并返回结果文本"""
        return execute_task(task_name=task_name, task_description=task_description)

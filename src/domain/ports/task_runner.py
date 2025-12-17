"""TaskRunner Port（任务执行器端口）

Domain 层端口：定义任务执行能力的抽象接口

为什么是 Port？
- 任务执行依赖外部实现（如 LangChain/LangGraph、工具系统等）
- Domain 层不能直接依赖这些具体实现
- 通过 Port 解耦：Domain 只依赖接口，Infrastructure/LangChain 层实现接口
"""

from typing import Protocol


class TaskRunner(Protocol):
    """任务执行器接口

    职责：
    - 接收任务名称与描述
    - 执行任务并返回结果字符串

    约定：
    - 不抛出框架相关异常到 Domain；错误以字符串（例如以"错误："开头）返回，或由上层约定处理
    """

    def run(self, task_name: str, task_description: str) -> str:
        """执行任务并返回结果文本"""
        ...

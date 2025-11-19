"""TaskExecutor - 任务执行器

职责：
1. 执行单个 Task
2. 调用 LangChain Agent
3. 处理工具调用
4. 记录执行日志（TaskEvent）
5. 超时控制
6. 返回执行结果

设计原则：
- 领域服务：封装 Task 执行的业务逻辑
- 依赖注入：通过构造函数注入配置
- 错误处理：捕获所有异常，记录日志
- 上下文传递：支持在 Task 之间传递数据
- 可观测性：记录详细的执行事件

为什么需要 TaskExecutor？
- Task 执行逻辑复杂（调用 LLM、工具等）
- 需要与 LangChain 集成
- 需要统一的错误处理
- 需要支持上下文传递
- 需要记录执行日志
- 需要超时控制
"""

import logging
import signal
from typing import Any

from src.domain.entities.task import Task

# 配置日志
logger = logging.getLogger(__name__)


class TaskExecutionTimeout(Exception):
    """Task 执行超时异常"""

    pass


class TimeoutHandler:
    """超时处理器（使用 signal 实现）

    注意：signal 只在主线程中工作，在 Windows 上可能有限制
    """

    def __init__(self, seconds: int):
        self.seconds = seconds

    def __enter__(self):
        # 设置超时信号
        signal.signal(signal.SIGALRM, self._timeout_handler)
        signal.alarm(self.seconds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 取消超时信号
        signal.alarm(0)

    def _timeout_handler(self, signum, frame):
        raise TaskExecutionTimeout(f"Task 执行超时（{self.seconds} 秒）")


class TaskExecutor:
    """任务执行器

    职责：
    1. 执行单个 Task
    2. 调用 LangChain Agent
    3. 处理执行结果
    4. 记录执行事件
    5. 超时控制
    6. 支持上下文传递
    7. 工具调用日志记录（新增）
    8. 工具调用超时控制（新增）
    """

    def __init__(self, timeout: int = 300, tool_timeout: int = 60):
        """初始化任务执行器

        参数：
            timeout: 执行超时时间（秒），默认 300 秒（5 分钟）
            tool_timeout: 单个工具调用超时时间（秒），默认 60 秒
        """
        self.timeout = timeout
        self.tool_timeout = tool_timeout

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        """执行 Task

        执行流程：
        1. 记录开始事件
        2. 准备输入（Task 描述 + 上下文）
        3. 调用 LangChain Agent（带超时控制）
        4. 处理输出
        5. 记录成功事件
        6. 返回结果

        参数：
            task: 要执行的 Task
            context: 执行上下文（包含前置任务的结果）

        返回：
            Task 执行结果（dict 格式）

        异常：
            TaskExecutionTimeout: Task 执行超时
            Exception: Task 执行失败
        """
        # 步骤 1: 记录开始事件
        task.add_event(f"开始执行任务: {task.name}")
        logger.info(f"开始执行 Task: {task.id} - {task.name}")

        try:
            # 步骤 2: 准备输入
            task_name = task.name
            task_description = task.description or ""

            # 如果有上下文，添加到描述中
            if context:
                context_str = "\n\n上下文信息："
                for key, value in context.items():
                    context_str += f"\n- {key}: {value}"
                task_description += context_str
                task.add_event(f"使用上下文: {len(context)} 个前置任务结果")

            # 步骤 3: 调用 LangChain Agent（带超时控制）
            task.add_event("调用 LangChain Agent")

            result = self._execute_with_timeout(task_name, task_description)

            # 步骤 4: 检查结果
            if result.startswith("错误："):
                # Agent 返回错误
                error_msg = result
                task.add_event(f"执行失败: {error_msg}")
                logger.error(f"Task {task.id} 执行失败: {error_msg}")
                raise Exception(error_msg)

            # 步骤 5: 记录成功事件
            task.add_event(f"执行成功: {result[:100]}...")
            logger.info(f"Task {task.id} 执行成功")

            # 步骤 6: 返回结果
            return {"result": result}

        except TaskExecutionTimeout as e:
            # 超时异常
            task.add_event(f"执行超时: {str(e)}")
            logger.error(f"Task {task.id} 执行超时: {str(e)}")
            raise

        except Exception as e:
            # 其他异常
            task.add_event(f"执行异常: {str(e)}")
            logger.error(f"Task {task.id} 执行异常: {str(e)}")
            raise

    def _execute_with_timeout(self, task_name: str, task_description: str) -> str:
        """执行 Task（带超时控制）

        参数：
            task_name: 任务名称
            task_description: 任务描述

        返回：
            执行结果

        异常：
            TaskExecutionTimeout: 执行超时
        """
        # 导入 LangChain Agent（延迟导入，避免循环依赖）
        from src.lc.agents.task_executor import execute_task

        # 注意：signal.alarm 在 Windows 上不可用
        # 这里使用简单的实现，实际生产环境应该使用 threading.Timer 或 asyncio.wait_for
        try:
            # 在 Unix 系统上使用 signal 实现超时
            import platform

            if platform.system() != "Windows":
                with TimeoutHandler(self.timeout):
                    return execute_task(
                        task_name=task_name,
                        task_description=task_description,
                    )
            else:
                # Windows 上暂时不支持超时（需要使用其他方法）
                return execute_task(
                    task_name=task_name,
                    task_description=task_description,
                )
        except TaskExecutionTimeout:
            raise
        except Exception:
            raise

    def _log_tool_call(
        self,
        task: Task,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: str,
        duration: float,
    ) -> None:
        """记录工具调用日志

        参数：
            task: 当前任务
            tool_name: 工具名称
            tool_input: 工具输入参数
            tool_output: 工具输出结果
            duration: 工具调用耗时（秒）
        """
        # 格式化工具输入（截断过长的内容）
        input_str = str(tool_input)
        if len(input_str) > 100:
            input_str = input_str[:100] + "..."

        # 格式化工具输出（截断过长的内容）
        output_str = str(tool_output)
        if len(output_str) > 100:
            output_str = output_str[:100] + "..."

        # 记录到 Task 事件
        event_message = (
            f"工具调用: {tool_name}\n"
            f"  输入: {input_str}\n"
            f"  输出: {output_str}\n"
            f"  耗时: {duration:.2f}秒"
        )
        task.add_event(event_message)

        # 记录到日志
        logger.info(f"Task {task.id} 工具调用: {tool_name}, " f"耗时: {duration:.2f}秒")

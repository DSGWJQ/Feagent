"""Executors（执行器）

Infrastructure 层：节点执行器实现

导出所有执行器和工厂函数
"""

from src.domain.ports.node_executor import NodeExecutorRegistry
from src.infrastructure.executors.base_executor import EndExecutor, StartExecutor
from src.infrastructure.executors.database_executor import DatabaseExecutor
from src.infrastructure.executors.file_executor import FileExecutor
from src.infrastructure.executors.http_executor import HttpExecutor
from src.infrastructure.executors.javascript_executor import (
    ConditionalExecutor,
    JavaScriptExecutor,
)
from src.infrastructure.executors.llm_executor import LlmExecutor
from src.infrastructure.executors.loop_executor import LoopExecutor
from src.infrastructure.executors.notification_executor import NotificationExecutor
from src.infrastructure.executors.prompt_executor import PromptExecutor
from src.infrastructure.executors.python_executor import PythonExecutor
from src.infrastructure.executors.transform_executor import TransformExecutor

__all__ = [
    "StartExecutor",
    "EndExecutor",
    "HttpExecutor",
    "DatabaseExecutor",
    "FileExecutor",
    "NotificationExecutor",
    "LlmExecutor",
    "JavaScriptExecutor",
    "PythonExecutor",
    "TransformExecutor",
    "LoopExecutor",
    "ConditionalExecutor",
    "PromptExecutor",
    "create_executor_registry",
]


def create_executor_registry(
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> NodeExecutorRegistry:
    """创建执行器注册表

    参数：
        openai_api_key: OpenAI API Key
        anthropic_api_key: Anthropic API Key

    返回：
        配置好的执行器注册表
    """
    registry = NodeExecutorRegistry()

    # 注册基础执行器
    registry.register("start", StartExecutor())
    registry.register("end", EndExecutor())

    # 注册 HTTP 执行器
    registry.register("httpRequest", HttpExecutor())
    registry.register("http", HttpExecutor())  # 兼容旧版本

    # 注册 LLM 执行器
    registry.register("textModel", LlmExecutor(api_key=openai_api_key))
    registry.register("llm", LlmExecutor(api_key=openai_api_key))  # 兼容旧版本

    # 注册 JavaScript 执行器
    registry.register("javascript", JavaScriptExecutor())

    # 注册 Python 执行器
    registry.register("python", PythonExecutor())

    # 注册条件执行器
    registry.register("conditional", ConditionalExecutor())

    # 注册 Prompt 执行器
    registry.register("prompt", PromptExecutor())

    # 注册 Transform 执行器
    registry.register("transform", TransformExecutor())

    # 注册 Loop 执行器
    registry.register("loop", LoopExecutor())

    # 注册数据库执行器
    registry.register("database", DatabaseExecutor())

    # 注册文件执行器
    registry.register("file", FileExecutor())

    # 注册通知执行器
    registry.register("notification", NotificationExecutor())

    # TODO: 注册其他执行器
    # - imageGeneration
    # - audio
    # - tool
    # - embeddingModel
    # - structuredOutput

    return registry

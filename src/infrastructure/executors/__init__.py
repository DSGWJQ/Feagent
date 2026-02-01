"""Executors（执行器）

Infrastructure 层：节点执行器实现

导出所有执行器和工厂函数
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.domain.agents.workflow_agent import register_default_container_executor_factory
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.infrastructure.executors.audio_executor import AudioExecutor
from src.infrastructure.executors.base_executor import EndExecutor, StartExecutor
from src.infrastructure.executors.database_executor import DatabaseExecutor
from src.infrastructure.executors.default_container_executor import DefaultContainerExecutor
from src.infrastructure.executors.embedding_executor import EmbeddingExecutor
from src.infrastructure.executors.file_executor import FileExecutor
from src.infrastructure.executors.http_executor import HttpExecutor
from src.infrastructure.executors.image_generation_executor import ImageGenerationExecutor
from src.infrastructure.executors.javascript_executor import (
    ConditionalExecutor,
    JavaScriptExecutor,
)
from src.infrastructure.executors.llm_executor import LlmExecutor
from src.infrastructure.executors.loop_executor import LoopExecutor
from src.infrastructure.executors.notification_executor import NotificationExecutor
from src.infrastructure.executors.prompt_executor import PromptExecutor
from src.infrastructure.executors.python_executor import PythonExecutor
from src.infrastructure.executors.structured_output_executor import StructuredOutputExecutor
from src.infrastructure.executors.tool_node_executor import ToolNodeExecutor
from src.infrastructure.executors.transform_executor import TransformExecutor

register_default_container_executor_factory(DefaultContainerExecutor)

__all__ = [
    "StartExecutor",
    "EndExecutor",
    "HttpExecutor",
    "DatabaseExecutor",
    "FileExecutor",
    "NotificationExecutor",
    "EmbeddingExecutor",
    "ImageGenerationExecutor",
    "AudioExecutor",
    "LlmExecutor",
    "StructuredOutputExecutor",
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
    session_factory: Callable[[], Any] | None = None,
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
    conditional_executor = ConditionalExecutor()
    registry.register("conditional", conditional_executor)
    registry.register("condition", conditional_executor)  # 兼容旧版本/Coze 导入

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

    # 注册向量与多模态执行器
    registry.register("embeddingModel", EmbeddingExecutor(api_key=openai_api_key))
    registry.register("imageGeneration", ImageGenerationExecutor(api_key=openai_api_key))
    registry.register("audio", AudioExecutor(api_key=openai_api_key))
    registry.register("structuredOutput", StructuredOutputExecutor(api_key=openai_api_key))

    if session_factory is not None:
        registry.register("tool", ToolNodeExecutor(session_factory=session_factory))

    return registry

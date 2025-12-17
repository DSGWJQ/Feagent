"""Model Metadata Port

定义模型元数据服务的端口协议，供Domain层依赖。
遵循 Ports and Adapters 架构模式，实现 Domain 层与 Infrastructure 层的解耦。

Author: Claude Code
Date: 2025-12-17 (P1 Optimization: Domain Layer Decoupling)
"""

from typing import Any, Protocol


class ModelInfo:
    """模型信息数据类"""

    def __init__(
        self,
        provider: str,
        model: str,
        max_tokens: int,
        supports_streaming: bool = True,
        **kwargs: Any,
    ):
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.supports_streaming = supports_streaming
        self.metadata = kwargs


class ModelMetadataPort(Protocol):
    """模型元数据端口协议

    定义获取模型元数据的接口方法。
    实现类: ModelMetadataService (Infrastructure Layer)

    架构说明:
        Domain Layer → ModelMetadataPort (Domain Port)
                      ↑
          ModelMetadataService (Infrastructure Layer)
    """

    def get_model_metadata(self, provider: str, model: str) -> ModelInfo:
        """获取模型元数据

        Args:
            provider: 模型提供商（如 "openai", "anthropic"）
            model: 模型名称（如 "gpt-4", "claude-3"）

        Returns:
            ModelInfo 对象，包含模型元数据

        Example:
            >>> metadata = port.get_model_metadata("openai", "gpt-4")
            >>> print(metadata.max_tokens)
            8192
        """
        ...

    def list_available_models(self, provider: str | None = None) -> list[str]:
        """列出可用模型

        Args:
            provider: 可选的提供商筛选

        Returns:
            可用模型名称列表
        """
        ...

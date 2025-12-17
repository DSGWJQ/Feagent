"""Model Metadata Adapter

实现 ModelMetadataPort 协议，包装 Infrastructure 层的模型元数据功能。
遵循 Adapter 模式，实现 Domain Port 与 Infrastructure 的解耦。

Author: Claude Code
Date: 2025-12-17 (P1 Optimization: Domain Layer Decoupling)
"""

from src.domain.ports.model_metadata import ModelInfo, ModelMetadataPort
from src.infrastructure.lc_adapters import model_metadata


class ModelMetadataAdapter:
    """模型元数据适配器

    适配 Infrastructure 层的模块级函数到 Domain Port 协议。
    作为薄包装层，委托调用到现有实现。
    """

    def get_model_metadata(self, provider: str, model: str) -> ModelInfo:
        """获取模型元数据

        委托到 Infrastructure 层的 get_model_metadata 函数。
        将返回的 ModelMetadata 转换为 Domain 层的 ModelInfo。

        Args:
            provider: 模型提供商（如 "openai", "anthropic"）
            model: 模型名称（如 "gpt-4", "claude-3"）

        Returns:
            ModelInfo 对象，包含模型元数据
        """
        # 调用 Infrastructure 实现
        infra_metadata = model_metadata.get_model_metadata(provider, model)

        # 转换为 Domain 数据类型
        return ModelInfo(
            provider=infra_metadata.provider,
            model=infra_metadata.model,
            max_tokens=infra_metadata.context_window,
            supports_streaming=True,  # 默认支持流式
            max_input_tokens=infra_metadata.max_input_tokens,
            max_output_tokens=infra_metadata.max_output_tokens,
        )

    def list_available_models(self, provider: str | None = None) -> list[str]:
        """列出可用模型

        Args:
            provider: 可选的提供商筛选

        Returns:
            可用模型名称列表
        """
        # 从注册表获取所有模型
        from src.infrastructure.lc_adapters.model_metadata import _MODEL_METADATA_REGISTRY

        if provider is None:
            # 返回所有模型
            return [f"{p}:{m}" for p, m in _MODEL_METADATA_REGISTRY.keys()]

        # 筛选特定提供商
        provider_lower = provider.lower()
        return [f"{p}:{m}" for p, m in _MODEL_METADATA_REGISTRY.keys() if p == provider_lower]


def create_model_metadata_adapter() -> ModelMetadataPort:
    """工厂函数：创建模型元数据适配器

    Returns:
        ModelMetadataAdapter 实例，实现 ModelMetadataPort 协议
    """
    return ModelMetadataAdapter()

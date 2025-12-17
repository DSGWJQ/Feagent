"""Infrastructure Adapters Package

提供 Domain Port 的 Infrastructure 层适配器实现。
遵循 Ports and Adapters 架构模式。

Author: Claude Code
Date: 2025-12-17 (P1 Optimization: Domain Layer Decoupling)
"""

from src.infrastructure.adapters.model_metadata_adapter import (
    ModelMetadataAdapter,
    create_model_metadata_adapter,
)

__all__ = [
    "ModelMetadataAdapter",
    "create_model_metadata_adapter",
]

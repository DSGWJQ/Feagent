"""CapabilityDefinitionSource Port（能力定义来源端口）

Domain 层端口：抽象“能力定义”的加载来源（YAML/DB/远端等）。

约束：
- 只能依赖标准库与 Domain 层类型
- 禁止在 Domain/Ports 中做 IO/解析（解析与读取由 Infrastructure 负责）
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

CapabilityDefinition = Mapping[str, Any]


class CapabilityDefinitionSource(Protocol):
    """提供能力定义的抽象来源。"""

    def load(self) -> list[CapabilityDefinition]:
        """加载全部能力定义（已解析为 Domain 可消费的数据结构）。"""
        ...

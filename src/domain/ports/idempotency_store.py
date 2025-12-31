"""IdempotencyStore Port（幂等存储端口）

Domain 层端口：提供幂等键的存在性检查与结果读取，用于避免重复执行。

约束：
- 只能依赖标准库与 Domain 层类型
- 存储介质与序列化细节由 Infrastructure 负责
"""

from __future__ import annotations

from typing import Any, Protocol


class IdempotencyStore(Protocol):
    """幂等存储端口。"""

    async def exists(self, idempotency_key: str) -> bool:
        """判断幂等键是否已存在。"""
        ...

    async def get_result(self, idempotency_key: str) -> Any:
        """读取幂等键对应的已缓存结果。"""
        ...

    async def save_result(self, idempotency_key: str, result: Any) -> None:
        """保存幂等键对应的执行结果。"""
        ...

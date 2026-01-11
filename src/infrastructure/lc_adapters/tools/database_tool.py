"""数据库查询工具（Infrastructure adapter）

保持向后兼容的导出路径：`src.infrastructure.lc_adapters.tools.database_tool`。
实际实现以 `src.lc.tools.database_tool` 为事实源（测试会 patch 该入口）。
"""

from __future__ import annotations

from src.lc.tools.database_tool import *  # noqa: F403

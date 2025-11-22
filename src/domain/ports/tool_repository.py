"""ToolRepository Port - 工具仓储接口

定义 Tool 聚合根的持久化契约

第一性原理：
- Port 定义契约，不包含实现
- 使用 Protocol 实现结构化子类型（不需要显式继承）
- Repository 负责聚合根的完整持久化和查询

为什么使用 Protocol？
1. 解耦：Domain 层不依赖 Infrastructure 层
2. 灵活性：可以有多个实现（SQLAlchemy、MongoDB、内存等）
3. 可测试性：测试时可以使用 Mock 实现
"""

from typing import Protocol

from src.domain.entities.tool import Tool


class ToolRepository(Protocol):
    """Tool Repository 接口

    定义 Tool 聚合根的持久化操作

    命名约定：
    - save(): 保存（新增或更新）
    - get_by_id(): 获取（必须存在，否则抛异常）
    - find_by_id(): 查找（可以返回 None）
    - find_all(): 查找所有
    - exists(): 检查是否存在
    - delete(): 删除
    """

    def save(self, tool: Tool) -> None:
        """保存 Tool

        新增或更新 Tool（根据 ID 判断）

        参数：
            tool: Tool 实体

        说明：
            - 如果 tool.id 不存在于数据库，则新增
            - 如果 tool.id 已存在，则更新
            - 调用者需要管理事务（commit/rollback）
        """
        ...

    def get_by_id(self, tool_id: str) -> Tool:
        """根据 ID 获取 Tool

        参数：
            tool_id: Tool ID

        返回：
            Tool 实体

        抛出：
            NotFoundError: 当 Tool 不存在时
        """
        ...

    def find_by_id(self, tool_id: str) -> Tool | None:
        """根据 ID 查找 Tool

        参数：
            tool_id: Tool ID

        返回：
            Tool 实体，如果不存在返回 None
        """
        ...

    def find_all(self) -> list[Tool]:
        """查找所有 Tool

        返回：
            Tool 列表（可能为空）
        """
        ...

    def find_by_category(self, category: str) -> list[Tool]:
        """根据分类查找 Tool

        参数：
            category: Tool 分类（http, database, file等）

        返回：
            Tool 列表（可能为空）
        """
        ...

    def find_published(self) -> list[Tool]:
        """查找所有已发布的 Tool

        返回：
            状态为 PUBLISHED 的 Tool 列表
        """
        ...

    def exists(self, tool_id: str) -> bool:
        """检查 Tool 是否存在

        参数：
            tool_id: Tool ID

        返回：
            True 表示存在，False 表示不存在
        """
        ...

    def delete(self, tool_id: str) -> None:
        """删除 Tool

        参数：
            tool_id: Tool ID

        说明：
            - 幂等操作：多次删除不报错
            - 调用者需要管理事务（commit/rollback）
        """
        ...

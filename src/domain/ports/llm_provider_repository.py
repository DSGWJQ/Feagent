"""LLMProviderRepository Port - LLM提供商仓储接口

定义 LLMProvider 聚合根的持久化契约

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

from src.domain.entities.llm_provider import LLMProvider


class LLMProviderRepository(Protocol):
    """LLMProvider Repository 接口

    定义 LLMProvider 聚合根的持久化操作

    命名约定：
    - save(): 保存（新增或更新）
    - get_by_id(): 获取（必须存在，否则抛异常）
    - get_by_name(): 按名称获取（必须存在，否则抛异常）
    - find_by_id(): 查找（可以返回 None）
    - find_by_name(): 按名称查找（可以返回 None）
    - find_all(): 查找所有
    - find_enabled(): 查找所有已启用的提供商
    - exists(): 检查是否存在
    - delete(): 删除
    """

    def save(self, provider: LLMProvider) -> None:
        """保存 LLMProvider

        新增或更新 LLMProvider（根据 ID 判断）

        参数：
            provider: LLMProvider 实体

        说明：
            - 如果 provider.id 不存在于数据库，则新增
            - 如果 provider.id 已存在，则更新
            - 调用者需要管理事务（commit/rollback）
        """
        ...

    def get_by_id(self, provider_id: str) -> LLMProvider:
        """根据 ID 获取 LLMProvider

        参数：
            provider_id: LLMProvider ID

        返回：
            LLMProvider 实体

        抛出：
            NotFoundError: 当 LLMProvider 不存在时
        """
        ...

    def get_by_name(self, name: str) -> LLMProvider:
        """根据名称获取 LLMProvider

        参数：
            name: 提供商名称（openai, deepseek, qwen等）

        返回：
            LLMProvider 实体

        抛出：
            NotFoundError: 当 LLMProvider 不存在时
        """
        ...

    def find_by_id(self, provider_id: str) -> LLMProvider | None:
        """根据 ID 查找 LLMProvider

        参数：
            provider_id: LLMProvider ID

        返回：
            LLMProvider 实体，如果不存在返回 None
        """
        ...

    def find_by_name(self, name: str) -> LLMProvider | None:
        """根据名称查找 LLMProvider

        参数：
            name: 提供商名称（openai, deepseek, qwen等）

        返回：
            LLMProvider 实体，如果不存在返回 None
        """
        ...

    def find_all(self) -> list[LLMProvider]:
        """查找所有 LLMProvider

        返回：
            LLMProvider 列表（可能为空）
        """
        ...

    def find_enabled(self) -> list[LLMProvider]:
        """查找所有已启用的 LLMProvider

        返回：
            状态为启用的 LLMProvider 列表
        """
        ...

    def exists(self, provider_id: str) -> bool:
        """检查 LLMProvider 是否存在

        参数：
            provider_id: LLMProvider ID

        返回：
            True 表示存在，False 表示不存在
        """
        ...

    def delete(self, provider_id: str) -> None:
        """删除 LLMProvider

        参数：
            provider_id: LLMProvider ID

        说明：
            - 幂等操作：多次删除不报错
            - 调用者需要管理事务（commit/rollback）
        """
        ...

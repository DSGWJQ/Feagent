"""SQLAlchemy LLMProvider Repository 实现

第一性原理：Repository 是领域对象和数据存储之间的转换器

职责：
1. 转换（Translation）：领域实体 ⇄ ORM 模型
2. 持久化（Persistence）：保存、查询、删除
3. 异常转换（Exception Translation）：数据库异常 → 领域异常

设计模式：
- Adapter 模式：实现领域层定义的 Port 接口
- Assembler 模式：负责对象转换（ORM ⇄ Entity）
- Repository 模式：封装数据访问逻辑
"""

from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.entities.llm_provider import LLMProvider
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.models import LLMProviderModel


class SQLAlchemyLLMProviderRepository:
    """SQLAlchemy LLMProvider Repository 实现

    实现领域层定义的 LLMProviderRepository Port 接口

    依赖：
    - Session: SQLAlchemy 同步会话（依赖注入）
    """

    def __init__(self, session: Session):
        """初始化 Repository

        参数：
            session: SQLAlchemy 同步会话
        """
        self.session = session

    # ==================== Assembler 方法 ====================
    # 职责：ORM 模型 ⇄ 领域实体转换

    def _to_entity(self, model: LLMProviderModel) -> LLMProvider:
        """将 ORM 模型转换为领域实体

        参数：
            model: LLMProviderModel ORM 模型

        返回：
            LLMProvider 领域实体
        """
        return LLMProvider(
            id=model.id,
            name=model.name,
            display_name=model.display_name,
            api_base=model.api_base,
            api_key=model.api_key,
            models=model.models or [],
            enabled=model.enabled,
            config=model.config or {},
            created_at=model.created_at.replace(tzinfo=UTC),
            updated_at=model.updated_at.replace(tzinfo=UTC) if model.updated_at else None,
        )

    def _to_model(self, entity: LLMProvider) -> LLMProviderModel:
        """将领域实体转换为 ORM 模型

        参数：
            entity: LLMProvider 领域实体

        返回：
            LLMProviderModel ORM 模型
        """
        return LLMProviderModel(
            id=entity.id,
            name=entity.name,
            display_name=entity.display_name,
            api_base=entity.api_base,
            api_key=entity.api_key,
            models=entity.models if entity.models else [],
            enabled=entity.enabled,
            config=entity.config if entity.config else {},
            created_at=entity.created_at.replace(tzinfo=None),
            updated_at=entity.updated_at.replace(tzinfo=None) if entity.updated_at else None,
        )

    # ==================== Repository 方法 ====================
    # 职责：持久化操作

    def save(self, provider: LLMProvider) -> None:
        """保存 LLMProvider 实体（新增或更新）

        参数：
            provider: LLMProvider 实体
        """
        model = self._to_model(provider)
        self.session.merge(model)

    def get_by_id(self, provider_id: str) -> LLMProvider:
        """根据 ID 获取 LLMProvider 实体（不存在抛异常）

        参数：
            provider_id: LLMProvider ID

        返回：
            LLMProvider 实体

        抛出：
            NotFoundError: 当 LLMProvider 不存在时
        """
        stmt = select(LLMProviderModel).where(LLMProviderModel.id == provider_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            raise NotFoundError(entity_type="LLMProvider", entity_id=provider_id)

        return self._to_entity(model)

    def get_by_name(self, name: str) -> LLMProvider:
        """根据名称获取 LLMProvider 实体（不存在抛异常）

        参数：
            name: 提供商名称（openai, deepseek, qwen等）

        返回：
            LLMProvider 实体

        抛出：
            NotFoundError: 当 LLMProvider 不存在时
        """
        stmt = select(LLMProviderModel).where(LLMProviderModel.name == name)
        model = self.session.scalars(stmt).first()

        if model is None:
            raise NotFoundError(entity_type="LLMProvider", entity_id=f"name={name}")

        return self._to_entity(model)

    def find_by_id(self, provider_id: str) -> LLMProvider | None:
        """根据 ID 查找 LLMProvider 实体（不存在返回 None）

        参数：
            provider_id: LLMProvider ID

        返回：
            LLMProvider 实体或 None
        """
        stmt = select(LLMProviderModel).where(LLMProviderModel.id == provider_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            return None

        return self._to_entity(model)

    def find_by_name(self, name: str) -> LLMProvider | None:
        """根据名称查找 LLMProvider 实体（不存在返回 None）

        参数：
            name: 提供商名称（openai, deepseek, qwen等）

        返回：
            LLMProvider 实体或 None
        """
        stmt = select(LLMProviderModel).where(LLMProviderModel.name == name)
        model = self.session.scalars(stmt).first()

        if model is None:
            return None

        return self._to_entity(model)

    def find_all(self) -> list[LLMProvider]:
        """查找所有 LLMProvider

        返回：
            LLMProvider 列表（可能为空）
        """
        stmt = select(LLMProviderModel).order_by(LLMProviderModel.created_at.desc())
        models = self.session.scalars(stmt).all()

        return [self._to_entity(model) for model in models]

    def find_enabled(self) -> list[LLMProvider]:
        """查找所有已启用的 LLMProvider

        返回：
            状态为启用的 LLMProvider 列表
        """
        stmt = (
            select(LLMProviderModel)
            .where(LLMProviderModel.enabled == True)  # noqa: E712
            .order_by(LLMProviderModel.created_at.desc())
        )
        models = self.session.scalars(stmt).all()

        return [self._to_entity(model) for model in models]

    def exists(self, provider_id: str) -> bool:
        """检查 LLMProvider 是否存在

        参数：
            provider_id: LLMProvider ID

        返回：
            True 表示存在，False 表示不存在
        """
        stmt = select(LLMProviderModel.id).where(LLMProviderModel.id == provider_id)
        return self.session.scalar(stmt) is not None

    def delete(self, provider_id: str) -> None:
        """删除 LLMProvider 实体

        参数：
            provider_id: LLMProvider ID

        说明：
            - 幂等操作：多次删除不报错
        """
        stmt = select(LLMProviderModel).where(LLMProviderModel.id == provider_id)
        model = self.session.scalars(stmt).first()

        if model is not None:
            self.session.delete(model)

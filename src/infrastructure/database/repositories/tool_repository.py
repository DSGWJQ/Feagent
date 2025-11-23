"""SQLAlchemy Tool Repository 实现

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

from src.domain.entities.tool import Tool, ToolParameter
from src.domain.exceptions import NotFoundError
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus
from src.infrastructure.database.models import ToolModel


class SQLAlchemyToolRepository:
    """SQLAlchemy Tool Repository 实现

    实现领域层定义的 ToolRepository Port 接口

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

    def _to_entity(self, model: ToolModel) -> Tool:
        """将 ORM 模型转换为领域实体

        参数：
            model: ToolModel ORM 模型

        返回：
            Tool 领域实体
        """
        # 转换参数：JSON -> ToolParameter 对象列表
        parameters = []
        if model.parameters:
            for param_dict in model.parameters:
                parameters.append(
                    ToolParameter(
                        name=param_dict.get("name", ""),
                        type=param_dict.get("type", "string"),
                        description=param_dict.get("description", ""),
                        required=param_dict.get("required", False),
                        default=param_dict.get("default"),
                        enum=param_dict.get("enum"),
                    )
                )

        # 转换 Tool
        return Tool(
            id=model.id,
            name=model.name,
            description=model.description,
            category=ToolCategory(model.category),
            status=ToolStatus(model.status),
            version=model.version,
            parameters=parameters,
            returns=model.returns or {},
            implementation_type=model.implementation_type,
            implementation_config=model.implementation_config or {},
            author=model.author,
            tags=model.tags or [],
            icon=model.icon,
            usage_count=model.usage_count,
            last_used_at=model.last_used_at.replace(tzinfo=UTC) if model.last_used_at else None,
            created_at=model.created_at.replace(tzinfo=UTC),
            updated_at=model.updated_at.replace(tzinfo=UTC) if model.updated_at else None,
            published_at=model.published_at.replace(tzinfo=UTC) if model.published_at else None,
        )

    def _to_model(self, entity: Tool) -> ToolModel:
        """将领域实体转换为 ORM 模型

        参数：
            entity: Tool 领域实体

        返回：
            ToolModel ORM 模型
        """
        # 转换参数：ToolParameter 对象列表 -> JSON
        parameters = []
        for param in entity.parameters:
            param_dict = {
                "name": param.name,
                "type": param.type,
                "description": param.description,
                "required": param.required,
            }
            if param.default is not None:
                param_dict["default"] = param.default
            if param.enum is not None:
                param_dict["enum"] = param.enum
            parameters.append(param_dict)

        # 转换 Tool
        return ToolModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            category=entity.category.value,
            status=entity.status.value,
            version=entity.version,
            parameters=parameters if parameters else None,
            returns=entity.returns if entity.returns else None,
            implementation_type=entity.implementation_type,
            implementation_config=entity.implementation_config
            if entity.implementation_config
            else None,
            author=entity.author,
            tags=entity.tags if entity.tags else None,
            icon=entity.icon,
            usage_count=entity.usage_count,
            last_used_at=entity.last_used_at.replace(tzinfo=None) if entity.last_used_at else None,
            created_at=entity.created_at.replace(tzinfo=None),
            updated_at=entity.updated_at.replace(tzinfo=None) if entity.updated_at else None,
            published_at=entity.published_at.replace(tzinfo=None) if entity.published_at else None,
        )

    # ==================== Repository 方法 ====================
    # 职责：持久化操作

    def save(self, tool: Tool) -> None:
        """保存 Tool 实体（新增或更新）

        参数：
            tool: Tool 实体
        """
        model = self._to_model(tool)
        self.session.merge(model)

    def get_by_id(self, tool_id: str) -> Tool:
        """根据 ID 获取 Tool 实体（不存在抛异常）

        参数：
            tool_id: Tool ID

        返回：
            Tool 实体

        抛出：
            NotFoundError: 当 Tool 不存在时
        """
        stmt = select(ToolModel).where(ToolModel.id == tool_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            raise NotFoundError(entity_type="Tool", entity_id=tool_id)

        return self._to_entity(model)

    def find_by_id(self, tool_id: str) -> Tool | None:
        """根据 ID 查找 Tool 实体（不存在返回 None）

        参数：
            tool_id: Tool ID

        返回：
            Tool 实体或 None
        """
        stmt = select(ToolModel).where(ToolModel.id == tool_id)
        model = self.session.scalars(stmt).first()

        if model is None:
            return None

        return self._to_entity(model)

    def find_all(self) -> list[Tool]:
        """查找所有 Tool

        返回：
            Tool 列表（可能为空）
        """
        stmt = select(ToolModel).order_by(ToolModel.created_at.desc())
        models = self.session.scalars(stmt).all()

        return [self._to_entity(model) for model in models]

    def find_by_category(self, category: str) -> list[Tool]:
        """根据分类查找 Tool

        参数：
            category: Tool 分类（http, database, file等）

        返回：
            Tool 列表（可能为空）
        """
        stmt = (
            select(ToolModel)
            .where(ToolModel.category == category)
            .order_by(ToolModel.created_at.desc())
        )
        models = self.session.scalars(stmt).all()

        return [self._to_entity(model) for model in models]

    def find_published(self) -> list[Tool]:
        """查找所有已发布的 Tool

        返回：
            状态为 PUBLISHED 的 Tool 列表
        """
        stmt = (
            select(ToolModel)
            .where(ToolModel.status == ToolStatus.PUBLISHED.value)
            .order_by(ToolModel.created_at.desc())
        )
        models = self.session.scalars(stmt).all()

        return [self._to_entity(model) for model in models]

    def exists(self, tool_id: str) -> bool:
        """检查 Tool 是否存在

        参数：
            tool_id: Tool ID

        返回：
            True 表示存在，False 表示不存在
        """
        stmt = select(ToolModel.id).where(ToolModel.id == tool_id)
        return self.session.scalar(stmt) is not None

    def delete(self, tool_id: str) -> None:
        """删除 Tool 实体

        参数：
            tool_id: Tool ID

        说明：
            - 幂等操作：多次删除不报错
        """
        stmt = select(ToolModel).where(ToolModel.id == tool_id)
        model = self.session.scalars(stmt).first()

        if model is not None:
            self.session.delete(model)

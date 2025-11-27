"""SQLAlchemy User Repository实现

第一性原理：Repository是领域对象和数据存储之间的转换器

职责：
1. 转换（Translation）：领域实体 ⇄ ORM模型
2. 持久化（Persistence）：保存、查询、删除
3. 异常转换（Exception Translation）：数据库异常 → 领域异常

设计模式：
- Adapter模式：实现领域层定义的Port接口
- Assembler模式：负责对象转换（ORM ⇄ Entity）
- Repository模式：封装数据访问逻辑

为什么使用同步Session？
- 当前实现是同步的（Use Case是同步的）
- 简单易懂，易于调试
- 未来可以迁移到异步
"""

from sqlalchemy.orm import Session

from src.domain.entities.user import User
from src.domain.exceptions import EntityNotFoundError
from src.domain.value_objects.user_role import UserRole
from src.infrastructure.database.models import UserModel


class SQLAlchemyUserRepository:
    """SQLAlchemy User Repository实现

    实现领域层定义的UserRepository Port接口

    依赖：
    - Session: SQLAlchemy同步会话（依赖注入）

    为什么不显式继承UserRepository？
    - 使用Protocol（结构化子类型）
    - 只要方法签名匹配，就符合接口
    - 更灵活，不需要显式继承
    """

    def __init__(self, session: Session):
        """初始化Repository

        参数：
            session: SQLAlchemy同步会话

        为什么通过构造函数注入session？
        - 依赖注入：由外部管理session生命周期
        - 事务控制：调用者控制事务边界
        - 可测试性：测试时可以注入Mock session
        """
        self.session = session

    # ==================== Assembler方法 ====================
    # 职责：ORM模型 ⇄ 领域实体转换

    def _to_entity(self, model: UserModel) -> User:
        """将ORM模型转换为领域实体

        为什么需要这个方法？
        - ORM模型是数据库表映射（Infrastructure层）
        - 领域实体是业务逻辑载体（Domain层）
        - 两者职责不同，需要转换

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 值对象转换：UserRole枚举

        参数：
            model: UserModel ORM模型

        返回：
            User 领域实体
        """
        return User(
            id=model.id,
            github_id=model.github_id,
            github_username=model.github_username,
            email=model.email,
            name=model.name,
            github_avatar_url=model.github_avatar_url,
            github_profile_url=model.github_profile_url,
            is_active=model.is_active,
            role=UserRole(model.role),
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login_at=model.last_login_at,
        )

    def _to_model(self, entity: User) -> UserModel:
        """将领域实体转换为ORM模型

        为什么需要这个方法？
        - 保存实体到数据库时需要ORM模型
        - 领域实体不应该知道数据库细节

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 值对象转换：UserRole枚举转字符串

        参数：
            entity: User领域实体

        返回：
            UserModel ORM模型
        """
        return UserModel(
            id=entity.id,
            github_id=entity.github_id,
            github_username=entity.github_username,
            email=entity.email,
            name=entity.name,
            github_avatar_url=entity.github_avatar_url,
            github_profile_url=entity.github_profile_url,
            is_active=entity.is_active,
            role=entity.role.value,  # 枚举转字符串
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            last_login_at=entity.last_login_at,
        )

    def _update_model(self, model: UserModel, entity: User) -> None:
        """更新ORM模型字段

        用于更新已存在的ORM模型，避免重复创建

        参数：
            model: 已存在的UserModel ORM模型
            entity: User领域实体
        """
        model.github_id = entity.github_id
        model.github_username = entity.github_username
        model.email = entity.email
        model.name = entity.name
        model.github_avatar_url = entity.github_avatar_url
        model.github_profile_url = entity.github_profile_url
        model.is_active = entity.is_active
        model.role = entity.role.value
        model.created_at = entity.created_at
        model.updated_at = entity.updated_at
        model.last_login_at = entity.last_login_at

    # ==================== Repository方法 ====================
    # 职责：持久化操作

    def save(self, user: User) -> None:
        """保存用户

        如果用户不存在，则创建新用户；
        如果用户已存在，则更新用户信息。

        参数：
            user: 用户实体

        为什么先查询再保存？
        - 区分创建和更新操作
        - 避免违反唯一约束
        - 复用已有的ORM实例（SQLAlchemy会话管理）
        """
        model = self.session.query(UserModel).filter_by(id=user.id).first()
        if model:
            # 更新已存在的用户
            self._update_model(model, user)
        else:
            # 创建新用户
            model = self._to_model(user)
            self.session.add(model)

        self.session.commit()
        self.session.refresh(model)

    def find_by_id(self, user_id: str) -> User | None:
        """根据用户ID查找用户

        参数：
            user_id: 用户ID（UUID）

        返回：
            Optional[User]: 用户实体，如果不存在则返回None
        """
        model = self.session.query(UserModel).filter_by(id=user_id).first()
        return self._to_entity(model) if model else None

    def get_by_id(self, user_id: str) -> User:
        """根据用户ID获取用户（必须存在）

        参数：
            user_id: 用户ID（UUID）

        返回：
            User: 用户实体

        异常：
            EntityNotFoundError: 当用户不存在时抛出
        """
        user = self.find_by_id(user_id)
        if user is None:
            raise EntityNotFoundError("User", user_id)
        return user

    def find_by_github_id(self, github_id: int) -> User | None:
        """根据GitHub ID查找用户

        参数：
            github_id: GitHub用户ID

        返回：
            Optional[User]: 用户实体，如果不存在则返回None
        """
        model = self.session.query(UserModel).filter_by(github_id=github_id).first()
        return self._to_entity(model) if model else None

    def find_by_email(self, email: str) -> User | None:
        """根据邮箱查找用户

        参数：
            email: 用户邮箱

        返回：
            Optional[User]: 用户实体，如果不存在则返回None
        """
        model = self.session.query(UserModel).filter_by(email=email).first()
        return self._to_entity(model) if model else None

    def exists_by_github_id(self, github_id: int) -> bool:
        """检查GitHub ID是否已存在

        参数：
            github_id: GitHub用户ID

        返回：
            bool: 如果存在返回True，否则返回False
        """
        return self.session.query(UserModel).filter_by(github_id=github_id).first() is not None

    def exists_by_email(self, email: str) -> bool:
        """检查邮箱是否已存在

        参数：
            email: 用户邮箱

        返回：
            bool: 如果存在返回True，否则返回False
        """
        return self.session.query(UserModel).filter_by(email=email).first() is not None

    def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """列出所有用户

        参数：
            skip: 跳过的记录数（用于分页）
            limit: 返回的最大记录数（用于分页）

        返回：
            list[User]: 用户实体列表
        """
        models = self.session.query(UserModel).offset(skip).limit(limit).all()
        return [self._to_entity(model) for model in models]

    def count(self) -> int:
        """统计用户总数

        返回：
            int: 用户总数
        """
        return self.session.query(UserModel).count()

    def delete(self, user_id: str) -> None:
        """删除用户

        参数：
            user_id: 用户ID（UUID）

        异常：
            EntityNotFoundError: 当用户不存在时抛出
        """
        model = self.session.query(UserModel).filter_by(id=user_id).first()
        if model is None:
            raise EntityNotFoundError("User", user_id)

        self.session.delete(model)
        self.session.commit()

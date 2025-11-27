"""用户仓储接口

UserRepository定义了用户持久化的抽象接口，遵循端口-适配器架构。

为什么需要Repository接口？
1. 依赖倒置原则（DIP）：Domain层不依赖Infrastructure层
2. 关注点分离：Domain层关注业务逻辑，Infrastructure层关注持久化
3. 可测试性：可以使用InMemory Repository进行单元测试
4. 灵活性：可以轻松切换不同的持久化实现（SQLite、PostgreSQL、MongoDB等）

为什么使用Protocol而不是ABC？
- Protocol是Python 3.8+的结构化子类型（Structural Subtyping）
- 更符合Python的"鸭子类型"哲学
- 不需要显式继承，只要实现了相同的方法签名即可
- IDE友好，类型检查更精确

命名约定：
- get_xxx: 必须存在，不存在时抛出异常
- find_xxx: 可以不存在，返回None
- exists_xxx: 返回布尔值
- list_xxx: 返回列表
"""

from typing import Protocol

from src.domain.entities.user import User


class UserRepository(Protocol):
    """用户仓储接口

    定义了用户实体的持久化操作。

    职责：
    1. 保存用户实体（创建或更新）
    2. 根据不同条件查找用户
    3. 检查用户是否存在
    4. 列出所有用户

    注意：
    - 所有方法都是同步的，因为Repository是Domain层的接口
    - 异步操作应该在Infrastructure层的实现中处理
    - Repository不应该包含业务逻辑，只负责数据持久化
    """

    def save(self, user: User) -> None:
        """保存用户

        如果用户不存在，则创建新用户；
        如果用户已存在，则更新用户信息。

        Args:
            user: 用户实体

        Raises:
            RepositoryError: 当保存失败时抛出
        """
        ...

    def find_by_id(self, user_id: str) -> User | None:
        """根据用户ID查找用户

        Args:
            user_id: 用户ID（UUID）

        Returns:
            Optional[User]: 用户实体，如果不存在则返回None
        """
        ...

    def get_by_id(self, user_id: str) -> User:
        """根据用户ID获取用户（必须存在）

        Args:
            user_id: 用户ID（UUID）

        Returns:
            User: 用户实体

        Raises:
            EntityNotFoundError: 当用户不存在时抛出
        """
        ...

    def find_by_github_id(self, github_id: int) -> User | None:
        """根据GitHub ID查找用户

        Args:
            github_id: GitHub用户ID

        Returns:
            Optional[User]: 用户实体，如果不存在则返回None
        """
        ...

    def find_by_email(self, email: str) -> User | None:
        """根据邮箱查找用户

        Args:
            email: 用户邮箱

        Returns:
            Optional[User]: 用户实体，如果不存在则返回None
        """
        ...

    def exists_by_github_id(self, github_id: int) -> bool:
        """检查GitHub ID是否已存在

        Args:
            github_id: GitHub用户ID

        Returns:
            bool: 如果存在返回True，否则返回False
        """
        ...

    def exists_by_email(self, email: str) -> bool:
        """检查邮箱是否已存在

        Args:
            email: 用户邮箱

        Returns:
            bool: 如果存在返回True，否则返回False
        """
        ...

    def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """列出所有用户

        Args:
            skip: 跳过的记录数（用于分页）
            limit: 返回的最大记录数（用于分页）

        Returns:
            list[User]: 用户实体列表
        """
        ...

    def count(self) -> int:
        """统计用户总数

        Returns:
            int: 用户总数
        """
        ...

    def delete(self, user_id: str) -> None:
        """删除用户

        Args:
            user_id: 用户ID（UUID）

        Raises:
            EntityNotFoundError: 当用户不存在时抛出
        """
        ...

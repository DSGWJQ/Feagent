"""用户聚合根

User是用户领域的聚合根，负责：
1. 用户基本信息管理（GitHub OAuth信息）
2. 用户状态管理（激活/停用）
3. 用户角色管理
4. 登录时间追踪

为什么User是聚合根？
- User拥有独立的业务标识（id）
- User有自己的生命周期（创建、更新、删除）
- User的完整性需要由User自己维护
- 其他实体（Workflow、Tool）通过user_id引用User

设计原则：
- 遵循DDD聚合根原则
- 业务逻辑封装在实体内部
- 不依赖任何框架（纯Python）
- 通过工厂方法创建实体
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from src.domain.exceptions import DomainError
from src.domain.value_objects.user_role import UserRole


@dataclass
class User:
    """用户聚合根

    属性说明：
    - id: 用户唯一标识（UUID）
    - github_id: GitHub用户ID（唯一）
    - github_username: GitHub用户名
    - email: 用户邮箱（唯一）
    - name: 用户姓名（可选）
    - github_avatar_url: GitHub头像URL（可选）
    - github_profile_url: GitHub个人主页URL（可选）
    - is_active: 是否激活（默认True）
    - role: 用户角色（默认USER）
    - created_at: 创建时间
    - updated_at: 更新时间（可选）
    - last_login_at: 最后登录时间（可选）

    不变式（Invariants）：
    1. github_id必须大于0
    2. github_username不能为空
    3. email必须是有效的邮箱格式
    4. 同一时刻，同一个github_id只能对应一个User
    """

    id: str
    github_id: int
    github_username: str
    email: str
    name: str | None = None
    github_avatar_url: str | None = None
    github_profile_url: str | None = None
    is_active: bool = True
    role: UserRole = field(default=UserRole.USER)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None
    last_login_at: datetime | None = None

    @staticmethod
    def create_from_github(
        github_id: int,
        github_username: str,
        email: str,
        name: str | None = None,
        avatar_url: str | None = None,
        profile_url: str | None = None,
    ) -> "User":
        """从GitHub OAuth信息创建用户

        工厂方法：封装创建逻辑，确保不变式

        Args:
            github_id: GitHub用户ID
            github_username: GitHub用户名
            email: 用户邮箱
            name: 用户姓名（可选）
            avatar_url: GitHub头像URL（可选）
            profile_url: GitHub个人主页URL（可选）

        Returns:
            User: 新创建的用户实体

        Raises:
            DomainError: 当违反业务规则时抛出
        """
        # 验证不变式
        if not github_id or github_id <= 0:
            raise DomainError("github_id必须大于0")
        if not github_username:
            raise DomainError("github_username不能为空")
        if not email:
            raise DomainError("email不能为空")
        if "@" not in email:
            raise DomainError("email格式无效")

        return User(
            id=str(uuid4()),
            github_id=github_id,
            github_username=github_username,
            email=email,
            name=name,
            github_avatar_url=avatar_url,
            github_profile_url=profile_url,
            is_active=True,
            role=UserRole.USER,
            created_at=datetime.now(),
            updated_at=None,
            last_login_at=None,
        )

    def update_login_time(self) -> None:
        """更新最后登录时间

        业务方法：每次用户登录时调用
        """
        self.last_login_at = datetime.now()
        self.updated_at = datetime.now()

    def update_profile(
        self,
        name: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        """更新用户资料

        业务方法：允许用户更新部分信息

        Args:
            name: 新的用户姓名
            avatar_url: 新的头像URL
        """
        if name is not None:
            self.name = name
        if avatar_url is not None:
            self.github_avatar_url = avatar_url
        self.updated_at = datetime.now()

    def deactivate(self) -> None:
        """停用用户

        业务方法：管理员可以停用用户账户
        停用后，用户无法登录系统
        """
        if not self.is_active:
            raise DomainError("用户已被停用")
        self.is_active = False
        self.updated_at = datetime.now()

    def activate(self) -> None:
        """激活用户

        业务方法：管理员可以重新激活被停用的用户
        """
        if self.is_active:
            raise DomainError("用户已处于激活状态")
        self.is_active = True
        self.updated_at = datetime.now()

    def promote_to_admin(self) -> None:
        """提升为管理员

        业务方法：只有管理员可以提升其他用户为管理员
        """
        if self.role == UserRole.ADMIN:
            raise DomainError("用户已经是管理员")
        self.role = UserRole.ADMIN
        self.updated_at = datetime.now()

    def demote_to_user(self) -> None:
        """降级为普通用户

        业务方法：只有管理员可以降级其他管理员
        """
        if self.role == UserRole.USER:
            raise DomainError("用户已经是普通用户")
        self.role = UserRole.USER
        self.updated_at = datetime.now()

    def is_admin(self) -> bool:
        """检查是否是管理员"""
        return self.role == UserRole.ADMIN

    def can_create_workflow(self) -> bool:
        """检查是否可以创建工作流

        业务规则：所有激活的用户都可以创建工作流
        """
        return self.is_active

    def can_upload_tool(self) -> bool:
        """检查是否可以上传工具

        业务规则：只有激活的用户可以上传工具
        """
        return self.is_active

    def __repr__(self) -> str:
        return f"<User(id={self.id}, github_username={self.github_username}, email={self.email}, role={self.role.value})>"

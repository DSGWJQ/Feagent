"""认证相关DTO

定义GitHub OAuth登录的请求和响应数据结构。

为什么需要DTO？
- 分离API层和业务层的数据结构
- 使用Pydantic进行请求验证
- 清晰的API文档（FastAPI自动生成）
"""

from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.entities.user import User


class GitHubCallbackRequest(BaseModel):
    """GitHub OAuth回调请求

    前端从GitHub获取授权码后，将code发送给后端。

    Attributes:
        code: GitHub OAuth授权码
    """

    code: str = Field(..., description="GitHub OAuth授权码", example="github_auth_code_12345")


class UserResponse(BaseModel):
    """用户信息响应

    Attributes:
        id: 用户ID
        github_id: GitHub用户ID
        github_username: GitHub用户名
        email: 邮箱
        name: 显示名称
        avatar_url: 头像URL
        profile_url: GitHub主页URL
        role: 用户角色
        is_active: 是否激活
        created_at: 创建时间
        last_login_at: 最后登录时间
    """

    id: str = Field(..., description="用户ID")
    github_id: int = Field(..., description="GitHub用户ID")
    github_username: str = Field(..., description="GitHub用户名")
    email: str = Field(..., description="邮箱")
    name: str | None = Field(None, description="显示名称")
    avatar_url: str | None = Field(None, description="头像URL")
    profile_url: str | None = Field(None, description="GitHub主页URL")
    role: str = Field(..., description="用户角色")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    last_login_at: datetime | None = Field(None, description="最后登录时间")

    @staticmethod
    def from_entity(user: User) -> "UserResponse":
        """从User实体创建DTO

        Args:
            user: 用户实体

        Returns:
            UserResponse: 用户响应DTO
        """
        return UserResponse(
            id=user.id,
            github_id=user.github_id,
            github_username=user.github_username,
            email=user.email,
            name=user.name,
            avatar_url=user.github_avatar_url,
            profile_url=user.github_profile_url,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


class GitHubCallbackResponse(BaseModel):
    """GitHub OAuth回调响应

    返回给前端的登录结果，包含用户信息和JWT token。

    Attributes:
        access_token: JWT访问令牌
        token_type: Token类型（固定为"bearer"）
        user: 用户信息
    """

    access_token: str = Field(..., description="JWT访问令牌")
    token_type: str = Field(default="bearer", description="Token类型")
    user: UserResponse = Field(..., description="用户信息")

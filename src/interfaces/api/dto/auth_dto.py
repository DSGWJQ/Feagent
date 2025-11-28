"""Auth DTOs for GitHub OAuth."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.entities.user import User


class GitHubCallbackRequest(BaseModel):
    """GitHub OAuth callback payload."""

    code: str = Field(
        ...,
        description="GitHub OAuth authorization code",
        examples=["github_auth_code_12345"],
    )


class UserResponse(BaseModel):
    """Serialized user info returned to the frontend."""

    id: str = Field(..., description="User ID")
    github_id: int = Field(..., description="GitHub user ID")
    github_username: str = Field(..., description="GitHub username")
    email: str = Field(..., description="Email address")
    name: str | None = Field(None, description="Display name")
    avatar_url: str | None = Field(None, description="Avatar URL")
    profile_url: str | None = Field(None, description="GitHub profile URL")
    role: str = Field(..., description="User role")
    is_active: bool = Field(..., description="Is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_login_at: datetime | None = Field(None, description="Last login timestamp")

    @staticmethod
    def from_entity(user: User) -> "UserResponse":
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
    """GitHub OAuth callback response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserResponse = Field(..., description="User info")

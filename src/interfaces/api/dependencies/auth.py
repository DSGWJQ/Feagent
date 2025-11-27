"""认证相关依赖注入

提供认证服务的依赖注入函数。

为什么使用依赖注入？
- 解耦：API路由不直接创建服务实例
- 可测试性：可以在测试中替换依赖
- 一致性：所有请求使用相同的服务配置
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.use_cases.github_auth import GitHubAuthUseCase
from src.config import settings
from src.infrastructure.auth.github_oauth_service import GitHubOAuthService
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.user_repository import (
    SQLAlchemyUserRepository,
)


def get_github_oauth_service() -> GitHubOAuthService:
    """获取GitHub OAuth服务

    从配置中读取GitHub OAuth参数并创建服务实例。

    Returns:
        GitHubOAuthService: GitHub OAuth服务实例
    """
    return GitHubOAuthService(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        redirect_uri=settings.github_redirect_uri,
    )


def get_jwt_service() -> JWTService:
    """获取JWT服务

    Returns:
        JWTService: JWT服务实例
    """
    return JWTService()


def get_user_repository(db: Session = Depends(get_db_session)) -> SQLAlchemyUserRepository:
    """获取用户仓储

    Args:
        db: 数据库会话

    Returns:
        SQLAlchemyUserRepository: 用户仓储实例
    """
    return SQLAlchemyUserRepository(db)


def get_github_auth_use_case(
    github_service: GitHubOAuthService = Depends(get_github_oauth_service),
    user_repository: SQLAlchemyUserRepository = Depends(get_user_repository),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> GitHubAuthUseCase:
    """获取GitHub登录用例

    组装GitHub登录所需的所有服务。

    Args:
        github_service: GitHub OAuth服务
        user_repository: 用户仓储
        jwt_service: JWT服务

    Returns:
        GitHubAuthUseCase: GitHub登录用例实例
    """
    return GitHubAuthUseCase(
        github_service=github_service,
        user_repository=user_repository,
        jwt_service=jwt_service,
    )

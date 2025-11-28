"""获取当前登录用户的依赖注入

职责：
1. 从请求头中提取JWT token
2. 验证token并解码获取用户ID
3. 从数据库查询用户实体
4. 支持可选认证（非登录用户也可以访问某些API）

为什么需要这个？
- 统一的用户认证逻辑
- 区分登录和非登录用户
- 实现"登录用户可保存，非登录用户只能体验"的需求
"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.domain.entities.user import User
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository


def get_current_user_optional(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db_session),
) -> User | None:
    """获取当前登录用户（可选）

    从Authorization header中提取JWT token，验证并返回用户实体。
    如果没有token或token无效，返回None（不抛出异常）。

    这个依赖用于"登录用户可以保存，非登录用户只能体验"的场景。

    Args:
        authorization: Authorization header (格式: "Bearer <token>")
        db: 数据库会话

    Returns:
        User | None: 用户实体（如果已登录）或None（如果未登录）

    示例：
        >>> @router.post("/workflows")
        >>> def create_workflow(
        >>>     request: CreateWorkflowRequest,
        >>>     current_user: User | None = Depends(get_current_user_optional)
        >>> ):
        >>>     if current_user:
        >>>         # 登录用户：保存到数据库
        >>>         workflow.user_id = current_user.id
        >>>         repository.save(workflow)
        >>>     else:
        >>>         # 非登录用户：只返回临时结果，不保存
        >>>         return workflow
    """
    if not authorization:
        return None

    # 提取token（格式: "Bearer <token>"）
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
    except ValueError:
        return None

    # 验证并解码token
    try:
        payload = JWTService.decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
    except ValueError:
        # Token无效或过期
        return None

    # 从数据库查询用户
    repository = SQLAlchemyUserRepository(db)
    user = repository.find_by_id(user_id)

    # 检查用户是否激活
    if user and not user.is_active:
        return None

    return user


def get_current_user(
    authorization: str = Header(..., description="Bearer token"),
    db: Session = Depends(get_db_session),
) -> User:
    """获取当前登录用户（必需）

    从Authorization header中提取JWT token，验证并返回用户实体。
    如果没有token或token无效，抛出401错误。

    这个依赖用于"必须登录才能访问"的API端点。

    Args:
        authorization: Authorization header (格式: "Bearer <token>")
        db: 数据库会话

    Returns:
        User: 用户实体

    Raises:
        HTTPException 401: 未认证或token无效

    示例：
        >>> @router.delete("/workflows/{workflow_id}")
        >>> def delete_workflow(
        >>>     workflow_id: str,
        >>>     current_user: User = Depends(get_current_user)
        >>> ):
        >>>     # 必须登录才能删除工作流
        >>>     # current_user保证是已登录用户
    """
    # 提取token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authorization header") from exc

    # 验证并解码token
    try:
        payload = JWTService.decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    # 从数据库查询用户
    repository = SQLAlchemyUserRepository(db)
    user = repository.find_by_id(user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")

    return user

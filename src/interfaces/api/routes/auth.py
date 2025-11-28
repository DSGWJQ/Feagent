"""GitHub OAuth认证路由

提供GitHub登录的API端点。

API端点：
- POST /auth/github/callback: 处理GitHub OAuth回调
"""

from fastapi import APIRouter, Depends, HTTPException

from src.application.use_cases.github_auth import GitHubAuthInput, GitHubAuthUseCase
from src.interfaces.api.dependencies.auth import get_github_auth_use_case
from src.interfaces.api.dto.auth_dto import (
    GitHubCallbackRequest,
    GitHubCallbackResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/github/callback", response_model=GitHubCallbackResponse)
async def github_callback(
    request: GitHubCallbackRequest,
    use_case: GitHubAuthUseCase = Depends(get_github_auth_use_case),
) -> GitHubCallbackResponse:
    """GitHub OAuth回调处理

    用户在GitHub授权后，GitHub会重定向到前端，前端获取code后调用此接口。
    后端用code换取token，创建/更新用户，返回JWT token。

    **流程：**
    1. 前端将GitHub返回的code发送给后端
    2. 后端用code换取GitHub access_token
    3. 后端获取GitHub用户信息
    4. 检查用户是否已存在，创建/更新用户
    5. 生成JWT token
    6. 返回用户信息和token给前端

    **前端使用：**
    ```typescript
    // 用户点击"GitHub登录"按钮
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=user:email`;

    // GitHub回调页面（如 /auth/callback）
    const code = new URLSearchParams(window.location.search).get('code');
    const response = await fetch('/api/auth/github/callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
    const { access_token, user } = await response.json();
    // 保存token到localStorage
    localStorage.setItem('access_token', access_token);
    ```

    Args:
        request: GitHub回调请求（包含authorization code）
        use_case: GitHub登录用例

    Returns:
        GitHubCallbackResponse: 用户信息和JWT token

    Raises:
        HTTPException 400: 授权码无效
        HTTPException 500: GitHub API错误或数据库错误
    """
    try:
        # 执行GitHub登录用例
        input_data = GitHubAuthInput(code=request.code)
        result = await use_case.execute(input_data)

        # 转换为DTO返回
        return GitHubCallbackResponse(
            access_token=result.access_token,
            token_type="bearer",
            user=UserResponse.from_entity(result.user),
        )

    except Exception as e:
        # 处理GitHub API错误
        if "Invalid code" in str(e) or "Bad request" in str(e):
            raise HTTPException(status_code=400, detail="Invalid authorization code") from e
        # 其他错误
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}") from e

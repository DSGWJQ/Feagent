"""GitHub OAuth 2.0服务

职责：
1. 将GitHub授权码（code）换取访问令牌（access_token）
2. 使用access_token获取GitHub用户信息
3. 获取用户的GitHub邮箱列表

为什么使用GitHub OAuth？
- 安全：用户无需创建新密码，使用GitHub账户登录
- 便捷：开发者熟悉GitHub登录流程
- 可信：GitHub是权威的开发者平台

设计原则：
- 使用httpx异步HTTP客户端
- 遵循GitHub OAuth 2.0标准流程
- 处理网络错误和API错误
"""

import httpx


class GitHubOAuthService:
    """GitHub OAuth 2.0服务

    提供GitHub OAuth认证流程的完整实现。

    OAuth 2.0 流程：
    1. 用户点击"GitHub登录"，跳转到GitHub授权页面
    2. 用户同意授权，GitHub回调带回授权码（code）
    3. 后端用code换取access_token
    4. 后端用access_token获取用户信息
    """

    # GitHub OAuth API endpoints
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_API_URL = "https://api.github.com/user"
    USER_EMAILS_API_URL = "https://api.github.com/user/emails"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """初始化GitHub OAuth服务

        Args:
            client_id: GitHub OAuth App的Client ID
            client_secret: GitHub OAuth App的Client Secret
            redirect_uri: 授权回调地址（必须与GitHub App配置一致）
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    async def exchange_code_for_token(self, code: str) -> str:
        """将授权码换取访问令牌

        GitHub OAuth流程的第一步：用户授权后获得code，
        后端用code换取access_token。

        Args:
            code: GitHub回调返回的授权码

        Returns:
            str: GitHub access_token

        Raises:
            Exception: 当GitHub API返回错误时（无效code、网络错误等）

        示例：
            >>> service = GitHubOAuthService(client_id="...", client_secret="...", redirect_uri="...")
            >>> token = await service.exchange_code_for_token("github-auth-code-123")
            >>> print(token)
            'gho_16C7e42F292c6912E7710c838347Ae178B4a'
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )

            # 检查HTTP状态码
            response.raise_for_status()

            # 解析响应
            data = response.json()
            return data["access_token"]

    async def get_user_info(self, access_token: str) -> dict:
        """获取GitHub用户信息

        使用access_token调用GitHub User API，获取用户的
        GitHub个人信息（id, login, name, email等）。

        Args:
            access_token: GitHub访问令牌

        Returns:
            Dict: 用户信息，包含：
                - id: GitHub用户ID
                - login: GitHub用户名
                - name: 显示名称
                - email: 公开邮箱（可能为None）
                - avatar_url: 头像URL
                - html_url: GitHub个人主页URL

        Raises:
            Exception: 当token无效或网络错误时

        示例：
            >>> user_info = await service.get_user_info("gho_16C7e42F292c...")
            >>> print(user_info["login"])
            'octocat'
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USER_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

            # 检查HTTP状态码（401表示token无效）
            response.raise_for_status()

            return response.json()

    async def get_user_emails(self, access_token: str) -> list[dict]:
        """获取GitHub用户邮箱列表

        GitHub用户可能有多个邮箱，此方法返回所有邮箱，
        包括主邮箱标识（primary=True）。

        Args:
            access_token: GitHub访问令牌

        Returns:
            list[Dict]: 邮箱列表，每个邮箱包含：
                - email: 邮箱地址
                - primary: 是否为主邮箱
                - verified: 是否已验证
                - visibility: 可见性（public/private）

        Raises:
            Exception: 当token无效或网络错误时

        示例：
            >>> emails = await service.get_user_emails("gho_16C7e42F292c...")
            >>> primary_email = next(e for e in emails if e["primary"])
            >>> print(primary_email["email"])
            'octocat@github.com'
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USER_EMAILS_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

            # 检查HTTP状态码
            response.raise_for_status()

            return response.json()

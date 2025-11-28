"""GitHub登录用例

职责：
1. 处理GitHub OAuth回调（authorization code → user + JWT token）
2. 创建新用户或更新现有用户
3. 生成JWT访问令牌

业务流程：
1. 用code换取GitHub access_token
2. 获取GitHub用户信息
3. 如果邮箱为空，从GitHub邮箱API获取主邮箱
4. 检查用户是否已存在（通过github_id）
5. 存在则更新登录时间，不存在则创建新用户
6. 保存用户到数据库
7. 生成JWT token
8. 返回用户信息和token

为什么这样设计？
- 单一职责：只负责GitHub登录这一个业务场景
- 依赖注入：通过构造函数注入服务，便于测试
- 输入/输出明确：使用Input/Output数据类
"""

from dataclasses import dataclass

from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.github_oauth_service import GitHubOAuthService
from src.infrastructure.auth.jwt_service import JWTService


@dataclass
class GitHubAuthInput:
    """GitHub登录输入

    Attributes:
        code: GitHub OAuth回调返回的授权码
    """

    code: str


@dataclass
class GitHubAuthOutput:
    """GitHub登录输出

    Attributes:
        user: 用户实体
        access_token: JWT访问令牌
    """

    user: User
    access_token: str


class GitHubAuthUseCase:
    """GitHub登录用例

    处理完整的GitHub OAuth登录流程。

    为什么使用依赖注入？
    - 方便单元测试（可以mock服务）
    - 解耦业务逻辑和基础设施实现
    - 符合依赖倒置原则（依赖抽象而非具体实现）
    """

    def __init__(
        self,
        github_service: GitHubOAuthService,
        user_repository: UserRepository,
        jwt_service: JWTService,
    ):
        """初始化GitHub登录用例

        Args:
            github_service: GitHub OAuth服务
            user_repository: 用户仓储
            jwt_service: JWT服务
        """
        self.github_service = github_service
        self.user_repository = user_repository
        self.jwt_service = jwt_service

    async def execute(self, input_data: GitHubAuthInput) -> GitHubAuthOutput:
        """执行GitHub登录

        Args:
            input_data: 登录输入（包含authorization code）

        Returns:
            GitHubAuthOutput: 用户信息和JWT token

        Raises:
            Exception: 当GitHub API错误或数据库错误时

        示例：
            >>> use_case = GitHubAuthUseCase(github_service, user_repo, jwt_service)
            >>> input_data = GitHubAuthInput(code="github-auth-code-123")
            >>> result = await use_case.execute(input_data)
            >>> print(result.access_token)
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
        """
        # Step 1: 用authorization code换取GitHub access_token
        access_token = await self.github_service.exchange_code_for_token(input_data.code)

        # Step 2: 使用access_token获取GitHub用户信息
        github_user_info = await self.github_service.get_user_info(access_token)

        # Step 3: 如果GitHub用户信息中没有email，从邮箱API获取
        email = github_user_info.get("email")
        fallback_login = github_user_info.get("login") or str(github_user_info.get("id"))
        if not email:
            # GitHub用户可能隐藏了公开邮箱，需要调用邮箱API
            emails = await self.github_service.get_user_emails(access_token)
            # 获取主邮箱（primary=True）
            primary_email = next((e for e in emails if e.get("primary")), None)
            if primary_email:
                email = primary_email["email"]
            elif emails:
                # 如果没有主邮箱，使用第一个验证过的邮箱
                verified_email = next((e for e in emails if e.get("verified")), None)
                email = verified_email["email"] if verified_email else emails[0]["email"]

        # GitHub 可能不返回任何邮箱，使用占位邮箱满足系统要求
        if not email:
            email = f"{fallback_login}@users.noreply.github.com"

        # Step 4: 检查用户是否已存在
        github_id = github_user_info["id"]
        existing_user = self.user_repository.find_by_github_id(github_id)

        if existing_user:
            # Step 5a: 用户已存在，更新登录时间
            user = existing_user
            user.update_login_time()
        else:
            # Step 5b: 新用户，创建账户
            user = User.create_from_github(
                github_id=github_id,
                github_username=github_user_info["login"],
                email=email,
                name=github_user_info.get("name"),
                avatar_url=github_user_info.get("avatar_url"),
                profile_url=github_user_info.get("html_url"),
            )

        # Step 6: 保存用户（新用户创建，老用户更新登录时间）
        self.user_repository.save(user)

        # Step 7: 生成JWT token
        token_data = {
            "sub": user.id,  # subject - 用户ID
            "email": user.email,
            "role": user.role.value,
        }
        jwt_token = self.jwt_service.create_access_token(data=token_data)

        # Step 8: 返回用户信息和token
        return GitHubAuthOutput(user=user, access_token=jwt_token)

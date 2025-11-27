"""GitHubAuthUseCase单元测试

测试真实场景：
1. 新用户通过GitHub首次登录（创建账户）
2. 老用户再次登录（更新登录时间）
3. 用户邮箱为空时使用GitHub邮箱API获取
4. GitHub API错误处理

TDD驱动：先写真实场景测试，再实现业务逻辑
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.github_auth import GitHubAuthInput, GitHubAuthUseCase
from src.domain.entities.user import User
from src.domain.value_objects.user_role import UserRole


@pytest.fixture
def mock_github_service():
    """Mock GitHub OAuth服务"""
    service = MagicMock()
    service.exchange_code_for_token = AsyncMock()
    service.get_user_info = AsyncMock()
    service.get_user_emails = AsyncMock()
    return service


@pytest.fixture
def mock_user_repository():
    """Mock用户仓储"""
    repository = MagicMock()
    repository.find_by_github_id = MagicMock()
    repository.save = MagicMock()
    return repository


@pytest.fixture
def mock_jwt_service():
    """Mock JWT服务"""
    service = MagicMock()
    service.create_access_token = MagicMock()
    return service


@pytest.fixture
def github_auth_use_case(mock_github_service, mock_user_repository, mock_jwt_service):
    """创建GitHubAuthUseCase实例"""
    return GitHubAuthUseCase(
        github_service=mock_github_service,
        user_repository=mock_user_repository,
        jwt_service=mock_jwt_service,
    )


class TestGitHubAuthUseCaseNewUser:
    """测试新用户首次登录"""

    @pytest.mark.asyncio
    async def test_new_user_login_should_create_account(
        self, github_auth_use_case, mock_github_service, mock_user_repository, mock_jwt_service
    ):
        """
        真实场景：新用户首次使用GitHub登录

        Given: GitHub返回新用户信息，数据库中不存在该用户
        When: 执行GitHub登录
        Then: 应该创建新用户账户并返回JWT token
        """
        # Arrange - Mock GitHub API返回新用户信息
        mock_github_service.exchange_code_for_token.return_value = "gho_test_token"
        mock_github_service.get_user_info.return_value = {
            "id": 12345678,
            "login": "newuser",
            "name": "New User",
            "email": "newuser@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345678",
            "html_url": "https://github.com/newuser",
        }

        # 数据库中不存在该用户
        mock_user_repository.find_by_github_id.return_value = None

        # Mock JWT token生成
        mock_jwt_service.create_access_token.return_value = "jwt_token_12345"

        # Act - 执行GitHub登录
        input_data = GitHubAuthInput(code="github-auth-code")
        result = await github_auth_use_case.execute(input_data)

        # Assert - 验证结果
        assert result is not None
        assert result.access_token == "jwt_token_12345"
        assert result.user.github_id == 12345678
        assert result.user.github_username == "newuser"
        assert result.user.email == "newuser@example.com"
        assert result.user.name == "New User"

        # 验证调用了正确的方法
        mock_github_service.exchange_code_for_token.assert_called_once_with("github-auth-code")
        mock_github_service.get_user_info.assert_called_once_with("gho_test_token")
        mock_user_repository.find_by_github_id.assert_called_once_with(12345678)
        mock_user_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_user_without_email_should_fetch_from_github(
        self, github_auth_use_case, mock_github_service, mock_user_repository, mock_jwt_service
    ):
        """
        真实场景：新用户的GitHub个人信息中没有公开邮箱

        Given: GitHub用户信息中email为null
        When: 执行GitHub登录
        Then: 应该调用GitHub邮箱API获取主邮箱
        """
        # Arrange - GitHub用户信息中email为null
        mock_github_service.exchange_code_for_token.return_value = "gho_token"
        mock_github_service.get_user_info.return_value = {
            "id": 99999,
            "login": "privateuser",
            "name": "Private User",
            "email": None,  # GitHub不返回公开邮箱
            "avatar_url": "https://avatars.githubusercontent.com/u/99999",
            "html_url": "https://github.com/privateuser",
        }

        # Mock GitHub邮箱API返回主邮箱
        mock_github_service.get_user_emails.return_value = [
            {"email": "primary@example.com", "primary": True, "verified": True},
            {"email": "secondary@example.com", "primary": False, "verified": True},
        ]

        mock_user_repository.find_by_github_id.return_value = None
        mock_jwt_service.create_access_token.return_value = "jwt_token"

        # Act
        input_data = GitHubAuthInput(code="code")
        result = await github_auth_use_case.execute(input_data)

        # Assert - 验证使用了主邮箱
        assert result.user.email == "primary@example.com"
        mock_github_service.get_user_emails.assert_called_once_with("gho_token")


class TestGitHubAuthUseCaseExistingUser:
    """测试老用户再次登录"""

    @pytest.mark.asyncio
    async def test_existing_user_login_should_update_login_time(
        self, github_auth_use_case, mock_github_service, mock_user_repository, mock_jwt_service
    ):
        """
        真实场景：老用户再次登录

        Given: 数据库中已存在该GitHub用户
        When: 执行GitHub登录
        Then: 应该更新用户的登录时间
        """
        # Arrange - Mock GitHub API
        mock_github_service.exchange_code_for_token.return_value = "gho_token"
        mock_github_service.get_user_info.return_value = {
            "id": 11111,
            "login": "existinguser",
            "name": "Existing User",
            "email": "existing@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/11111",
            "html_url": "https://github.com/existinguser",
        }

        # 数据库中已存在该用户
        existing_user = User.create_from_github(
            github_id=11111,
            github_username="existinguser",
            email="existing@example.com",
            name="Existing User",
        )
        mock_user_repository.find_by_github_id.return_value = existing_user

        mock_jwt_service.create_access_token.return_value = "jwt_token"

        # Act
        input_data = GitHubAuthInput(code="code")
        result = await github_auth_use_case.execute(input_data)

        # Assert - 验证更新了用户
        assert result.user.github_id == 11111
        mock_user_repository.save.assert_called_once()  # 应该保存更新后的用户


class TestGitHubAuthUseCaseJWTToken:
    """测试JWT token生成"""

    @pytest.mark.asyncio
    async def test_should_generate_jwt_with_user_data(
        self, github_auth_use_case, mock_github_service, mock_user_repository, mock_jwt_service
    ):
        """
        真实场景：生成包含用户信息的JWT token

        Given: 用户登录成功
        When: 生成JWT token
        Then: Token应该包含用户ID、邮箱、角色
        """
        # Arrange
        mock_github_service.exchange_code_for_token.return_value = "gho_token"
        mock_github_service.get_user_info.return_value = {
            "id": 55555,
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/55555",
            "html_url": "https://github.com/testuser",
        }

        mock_user_repository.find_by_github_id.return_value = None
        mock_jwt_service.create_access_token.return_value = "jwt_token"

        # Act
        input_data = GitHubAuthInput(code="code")
        await github_auth_use_case.execute(input_data)

        # Assert - 验证JWT生成时传入了正确的数据
        mock_jwt_service.create_access_token.assert_called_once()
        call_args = mock_jwt_service.create_access_token.call_args
        token_data = call_args[1]["data"]  # 获取data参数

        assert "sub" in token_data  # 用户ID
        assert "email" in token_data
        assert "role" in token_data
        assert token_data["role"] == UserRole.USER.value


class TestGitHubAuthUseCaseErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_invalid_code_should_raise_error(
        self, github_auth_use_case, mock_github_service, mock_user_repository, mock_jwt_service
    ):
        """
        真实场景：使用无效的授权码

        Given: GitHub API返回错误（无效code）
        When: 执行GitHub登录
        Then: 应该抛出异常
        """
        # Arrange - Mock GitHub API返回错误
        mock_github_service.exchange_code_for_token.side_effect = Exception("Invalid code")

        # Act & Assert
        input_data = GitHubAuthInput(code="invalid-code")
        with pytest.raises(Exception):
            await github_auth_use_case.execute(input_data)


class TestGitHubAuthUseCaseRealWorldScenario:
    """测试真实世界场景（端到端）"""

    @pytest.mark.asyncio
    async def test_complete_github_login_flow(
        self, github_auth_use_case, mock_github_service, mock_user_repository, mock_jwt_service
    ):
        """
        真实场景：完整的GitHub登录流程

        1. 用户在前端点击"GitHub登录"
        2. GitHub回调返回authorization code
        3. 后端用code换取token
        4. 后端获取用户信息
        5. 检查用户是否存在
        6. 创建/更新用户
        7. 生成JWT token
        8. 返回给前端
        """
        # Step 1-2: 用户授权，获得code（前端完成）

        # Step 3: 用code换取GitHub token
        mock_github_service.exchange_code_for_token.return_value = "gho_real_token"

        # Step 4: 获取用户信息
        mock_github_service.get_user_info.return_value = {
            "id": 77777,
            "login": "realuser",
            "name": "Real User",
            "email": "real@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/77777",
            "html_url": "https://github.com/realuser",
        }

        # Step 5: 检查用户是否存在
        mock_user_repository.find_by_github_id.return_value = None

        # Step 6: 创建新用户（在use case中完成）

        # Step 7: 生成JWT token
        mock_jwt_service.create_access_token.return_value = "jwt_access_token_abc123"

        # Execute complete flow
        input_data = GitHubAuthInput(code="github-callback-code")
        result = await github_auth_use_case.execute(input_data)

        # Step 8: 验证返回结果
        assert result.access_token == "jwt_access_token_abc123"
        assert result.user.github_id == 77777
        assert result.user.github_username == "realuser"
        assert result.user.email == "real@example.com"

        # 验证完整流程的方法调用
        assert mock_github_service.exchange_code_for_token.called
        assert mock_github_service.get_user_info.called
        assert mock_user_repository.find_by_github_id.called
        assert mock_user_repository.save.called
        assert mock_jwt_service.create_access_token.called

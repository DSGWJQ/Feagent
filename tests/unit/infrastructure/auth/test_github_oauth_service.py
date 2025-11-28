"""GitHubOAuthService单元测试

测试真实场景：
1. GitHub OAuth授权流程（code → access_token → user_info）
2. 处理GitHub API错误（网络错误、权限错误等）
3. 获取用户邮箱信息

使用mock模拟GitHub API调用，避免真实网络请求。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infrastructure.auth.github_oauth_service import GitHubOAuthService


@pytest.fixture
def github_service():
    """创建GitHubOAuthService实例"""
    return GitHubOAuthService(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:5173/auth/callback",
    )


class TestGitHubOAuthServiceTokenExchange:
    """测试授权码换取token（真实场景：用户点击授权后）"""

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_should_return_access_token(self, github_service):
        """
        真实场景：用户在GitHub授权后，回调带回授权码

        Given: GitHub回调返回的授权码
        When: 调用exchange_code_for_token
        Then: 应该返回GitHub access_token
        """
        # Arrange - Mock GitHub API响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "gho_test123456"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Act
            token = await github_service.exchange_code_for_token("auth-code-123")

            # Assert
            assert token == "gho_test123456"

    @pytest.mark.asyncio
    async def test_exchange_code_with_invalid_code_should_raise_error(self, github_service):
        """
        真实场景：使用无效的授权码（过期或伪造）

        Given: 一个无效的授权码
        When: 尝试换取token
        Then: 应该抛出异常
        """
        # Arrange - Mock GitHub API返回错误
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError):
                await github_service.exchange_code_for_token("invalid-code")


class TestGitHubOAuthServiceUserInfo:
    """测试获取GitHub用户信息（真实场景：用户已授权）"""

    @pytest.mark.asyncio
    async def test_get_user_info_should_return_user_data(self, github_service):
        """
        真实场景：获取已授权用户的GitHub个人信息

        Given: 有效的access_token
        When: 调用get_user_info
        Then: 应该返回用户的GitHub信息（id, login, name, email等）
        """
        # Arrange - Mock GitHub User API响应
        mock_user_data = {
            "id": 12345678,
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345678",
            "html_url": "https://github.com/testuser",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_user_data

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Act
            user_info = await github_service.get_user_info("gho_test_token")

            # Assert
            assert user_info["id"] == 12345678
            assert user_info["login"] == "testuser"
            assert user_info["name"] == "Test User"
            assert user_info["email"] == "test@example.com"
            assert user_info["avatar_url"] == "https://avatars.githubusercontent.com/u/12345678"

    @pytest.mark.asyncio
    async def test_get_user_info_with_invalid_token_should_raise_error(self, github_service):
        """
        真实场景：使用无效或过期的access_token

        Given: 一个无效的access_token
        When: 尝试获取用户信息
        Then: 应该抛出401错误
        """
        # Arrange - Mock GitHub API返回401
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError):
                await github_service.get_user_info("invalid_token")


class TestGitHubOAuthServiceUserEmails:
    """测试获取GitHub用户邮箱（真实场景：多邮箱账户）"""

    @pytest.mark.asyncio
    async def test_get_user_emails_should_return_email_list(self, github_service):
        """
        真实场景：获取用户的所有GitHub邮箱（包括主邮箱）

        Given: 有效的access_token
        When: 调用get_user_emails
        Then: 应该返回用户的邮箱列表，包含主邮箱标识
        """
        # Arrange - Mock GitHub Emails API响应
        mock_emails = [
            {
                "email": "primary@example.com",
                "primary": True,
                "verified": True,
                "visibility": "public",
            },
            {
                "email": "secondary@example.com",
                "primary": False,
                "verified": True,
                "visibility": "private",
            },
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_emails

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Act
            emails = await github_service.get_user_emails("gho_test_token")

            # Assert
            assert len(emails) == 2
            assert emails[0]["email"] == "primary@example.com"
            assert emails[0]["primary"] is True
            assert emails[1]["email"] == "secondary@example.com"
            assert emails[1]["primary"] is False

    @pytest.mark.asyncio
    async def test_get_user_emails_should_identify_primary_email(self, github_service):
        """
        真实场景：从多个邮箱中识别出主邮箱

        Given: 用户有多个GitHub邮箱
        When: 获取邮箱列表
        Then: 应该能识别哪个是主邮箱（primary=True）
        """
        # Arrange
        mock_emails = [
            {"email": "old@example.com", "primary": False, "verified": True},
            {"email": "main@example.com", "primary": True, "verified": True},
            {"email": "work@example.com", "primary": False, "verified": False},
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = mock_emails

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Act
            emails = await github_service.get_user_emails("gho_test_token")

            # Assert - 验证能找到主邮箱
            primary_emails = [e for e in emails if e["primary"]]
            assert len(primary_emails) == 1
            assert primary_emails[0]["email"] == "main@example.com"


class TestGitHubOAuthServiceRealWorldScenario:
    """测试真实世界场景（完整的OAuth流程）"""

    @pytest.mark.asyncio
    async def test_complete_oauth_flow(self, github_service):
        """
        真实场景：完整的GitHub OAuth 2.0流程

        1. 用户在GitHub授权，获得授权码
        2. 后端用授权码换取access_token
        3. 用access_token获取用户信息
        4. 用access_token获取用户邮箱列表
        """
        # Step 1: Mock token exchange
        mock_token_response = MagicMock()
        mock_token_response.json.return_value = {"access_token": "gho_real_token"}

        # Step 2: Mock user info
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {
            "id": 99999,
            "login": "realuser",
            "name": "Real User",
            "email": None,  # GitHub可能不返回email
            "avatar_url": "https://avatars.githubusercontent.com/u/99999",
            "html_url": "https://github.com/realuser",
        }

        # Step 3: Mock emails
        mock_emails_response = MagicMock()
        mock_emails_response.json.return_value = [
            {"email": "real@example.com", "primary": True, "verified": True}
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Mock POST for token exchange
            mock_instance.post = AsyncMock(return_value=mock_token_response)

            # Mock GET for user info and emails (will be called twice)
            mock_instance.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])

            # Execute complete flow
            # Step 1: Exchange code for token
            token = await github_service.exchange_code_for_token("auth-code")
            assert token == "gho_real_token"

            # Step 2: Get user info
            user_info = await github_service.get_user_info(token)
            assert user_info["id"] == 99999
            assert user_info["login"] == "realuser"

            # Step 3: Get emails
            emails = await github_service.get_user_emails(token)
            assert emails[0]["email"] == "real@example.com"
            assert emails[0]["primary"] is True


class TestGitHubOAuthServiceErrorHandling:
    """测试错误处理（真实场景：网络问题、API限流）"""

    @pytest.mark.asyncio
    async def test_network_error_should_raise_exception(self, github_service):
        """
        真实场景：网络连接失败

        Given: 网络不可用
        When: 尝试调用GitHub API
        Then: 应该抛出网络错误异常
        """
        # Arrange - Mock network error
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Network error")
            )

            # Act & Assert
            with pytest.raises(Exception, match="Network error"):
                await github_service.exchange_code_for_token("code")

    @pytest.mark.asyncio
    async def test_rate_limit_error_should_raise_exception(self, github_service):
        """
        真实场景：GitHub API rate limit exceeded

        Given: API调用超过限流
        When: 继续调用API
        Then: 应该抛出429错误
        """
        # Arrange - Mock rate limit error
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limit exceeded", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError):
                await github_service.get_user_info("token")

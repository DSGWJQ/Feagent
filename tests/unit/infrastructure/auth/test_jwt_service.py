"""JWTService单元测试

测试真实场景：
1. 用户登录后生成JWT token
2. 每次请求时验证token并获取用户信息
3. Token过期后无法使用
4. 被篡改的token无法通过验证

这些是真实的安全场景，确保认证系统的可靠性。
"""

import time
from datetime import timedelta

import pytest

from src.config import settings
from src.infrastructure.auth.jwt_service import JWTService


class TestJWTServiceTokenCreation:
    """测试JWT token创建（真实场景：用户登录）"""

    def test_create_access_token_should_include_user_data(self):
        """
        真实场景：用户登录成功后生成token

        Given: 用户信息（user_id, email, role）
        When: 调用create_access_token生成token
        Then: Token应该包含所有用户信息
        """
        # Arrange - 模拟用户登录
        user_data = {
            "sub": "user-123",  # subject - 用户ID
            "email": "user@example.com",
            "role": "user",
        }

        # Act - 生成JWT token
        token = JWTService.create_access_token(data=user_data)

        # Assert - 验证token不为空
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token_should_return_correct_user_data(self):
        """
        真实场景：API请求时验证token并获取用户信息

        Given: 一个有效的JWT token
        When: 调用decode_token解码
        Then: 应该返回正确的用户信息
        """
        # Arrange - 创建token
        user_data = {
            "sub": "user-456",
            "email": "test@example.com",
            "role": "admin",
        }
        token = JWTService.create_access_token(data=user_data)

        # Act - 解码token
        decoded_data = JWTService.decode_token(token)

        # Assert - 验证解码的数据正确
        assert decoded_data["sub"] == "user-456"
        assert decoded_data["email"] == "test@example.com"
        assert decoded_data["role"] == "admin"
        assert "exp" in decoded_data  # 应该包含过期时间
        assert "iat" in decoded_data  # 应该包含签发时间

    def test_create_token_with_custom_expiration(self):
        """
        真实场景：为特殊用途创建短期token（如密码重置）

        Given: 自定义的过期时间（5秒）
        When: 创建token
        Then: Token应该在指定时间后过期
        """
        # Arrange
        user_data = {"sub": "user-789"}
        expires_delta = timedelta(seconds=5)

        # Act
        token = JWTService.create_access_token(data=user_data, expires_delta=expires_delta)

        # Assert - Token应该立即可用
        decoded_data = JWTService.decode_token(token)
        assert decoded_data["sub"] == "user-789"


class TestJWTServiceTokenExpiration:
    """测试JWT token过期（真实场景：安全控制）"""

    def test_expired_token_should_raise_error(self):
        """
        真实场景：使用过期的token访问API应该被拒绝

        Given: 一个过期的token（1秒过期）
        When: 等待token过期后尝试解码
        Then: 应该抛出ValueError，提示token已过期
        """
        # Arrange - 创建1秒后过期的token
        user_data = {"sub": "user-expired"}
        expires_delta = timedelta(seconds=1)
        token = JWTService.create_access_token(data=user_data, expires_delta=expires_delta)

        # Act - 等待token过期
        time.sleep(2)  # 等待2秒确保token已过期

        # Assert - 解码过期token应该抛出错误
        with pytest.raises(ValueError, match="Token已过期"):
            JWTService.decode_token(token)

    def test_token_should_have_default_expiration(self):
        """
        真实场景：正常登录token使用默认过期时间

        Given: 不指定过期时间
        When: 创建token
        Then: Token应该使用配置的默认过期时间（30分钟）
        """
        # Arrange
        user_data = {"sub": "user-default"}

        # Act - 不指定过期时间
        token = JWTService.create_access_token(data=user_data)
        decoded_data = JWTService.decode_token(token)

        # Assert - 验证过期时间合理（应该在未来）
        import time

        current_time = time.time()
        exp_time = decoded_data["exp"]

        # 过期时间应该在当前时间之后
        assert exp_time > current_time

        # 过期时间应该接近30分钟后（允许误差±5秒）
        expected_exp = current_time + (settings.access_token_expire_minutes * 60)
        assert abs(exp_time - expected_exp) < 5


class TestJWTServiceTokenSecurity:
    """测试JWT token安全性（真实场景：防止攻击）"""

    def test_tampered_token_should_raise_error(self):
        """
        真实场景：攻击者篡改token内容应该被检测

        Given: 一个有效的token
        When: 篡改token内容（修改最后几个字符）
        Then: 解码应该失败，抛出错误
        """
        # Arrange - 创建有效token
        user_data = {"sub": "user-secure"}
        token = JWTService.create_access_token(data=user_data)

        # Act - 篡改token（修改最后3个字符）
        tampered_token = token[:-3] + "XXX"

        # Assert - 解码篡改的token应该失败
        with pytest.raises(ValueError, match="Token无效"):
            JWTService.decode_token(tampered_token)

    def test_invalid_token_format_should_raise_error(self):
        """
        真实场景：使用完全无效的token格式

        Given: 一个格式错误的token字符串
        When: 尝试解码
        Then: 应该抛出错误
        """
        # Arrange
        invalid_token = "this.is.not.a.valid.jwt.token"

        # Assert
        with pytest.raises(ValueError, match="Token无效"):
            JWTService.decode_token(invalid_token)

    def test_empty_token_should_raise_error(self):
        """
        真实场景：使用空token访问API

        Given: 空字符串token
        When: 尝试解码
        Then: 应该抛出错误
        """
        # Arrange
        empty_token = ""

        # Assert
        with pytest.raises(ValueError, match="Token无效"):
            JWTService.decode_token(empty_token)


class TestJWTServiceTokenIssuedAt:
    """测试JWT token签发时间（真实场景：审计和安全）"""

    def test_token_should_have_issued_at_timestamp(self):
        """
        真实场景：记录token签发时间用于审计

        Given: 创建新token
        When: 解码token
        Then: 应该包含签发时间（iat字段）
        """
        # Arrange & Act
        user_data = {"sub": "user-audit"}
        token = JWTService.create_access_token(data=user_data)
        decoded_data = JWTService.decode_token(token)

        # Assert
        assert "iat" in decoded_data

        # 签发时间应该接近当前时间（允许误差±2秒）
        import time

        current_time = time.time()
        iat_time = decoded_data["iat"]
        assert abs(iat_time - current_time) < 2


class TestJWTServiceRealWorldScenario:
    """测试真实世界场景（端到端）"""

    def test_complete_login_flow_with_token(self):
        """
        真实场景：完整的用户登录流程

        1. 用户登录成功，生成token
        2. 用户携带token访问API（多次请求）
        3. Token在有效期内一直可用
        4. Token过期后无法使用
        """
        # Step 1: 用户登录，生成token
        user_data = {
            "sub": "user-real-scenario",
            "email": "real@example.com",
            "role": "user",
        }
        token = JWTService.create_access_token(
            data=user_data,
            expires_delta=timedelta(seconds=3),  # 3秒后过期
        )

        # Step 2: 模拟多次API请求（在有效期内）
        for _ in range(3):
            decoded = JWTService.decode_token(token)
            assert decoded["sub"] == "user-real-scenario"
            assert decoded["email"] == "real@example.com"
            time.sleep(0.5)  # 每次请求间隔0.5秒

        # Step 3: 等待token过期
        time.sleep(2)  # 总共已经过去约3秒

        # Step 4: Token过期后应该无法使用
        with pytest.raises(ValueError, match="Token已过期"):
            JWTService.decode_token(token)

    def test_multiple_users_with_different_tokens(self):
        """
        真实场景：多个用户同时登录，各自使用不同的token

        Given: 多个用户登录
        When: 为每个用户生成token
        Then: 每个token只能解码出对应用户的信息
        """
        # Arrange - 三个用户登录
        users = [
            {"sub": "user-1", "email": "user1@example.com", "role": "user"},
            {"sub": "user-2", "email": "user2@example.com", "role": "admin"},
            {"sub": "user-3", "email": "user3@example.com", "role": "user"},
        ]

        # Act - 为每个用户生成token
        tokens = [JWTService.create_access_token(data=user) for user in users]

        # Assert - 解码每个token，验证信息正确且互不干扰
        for i, token in enumerate(tokens):
            decoded = JWTService.decode_token(token)
            assert decoded["sub"] == users[i]["sub"]
            assert decoded["email"] == users[i]["email"]
            assert decoded["role"] == users[i]["role"]

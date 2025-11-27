"""User实体单元测试

测试User实体的业务逻辑，遵循TDD原则。

测试范围：
1. 工厂方法测试（create_from_github）
2. 不变式验证测试
3. 业务方法测试（update_login_time, deactivate, activate等）
4. 权限检查测试

测试原则：
- 遵循AAA模式（Arrange-Act-Assert）
- 一个测试只验证一个行为
- 测试名称清晰描述测试场景
- 使用Given-When-Then注释
"""

from datetime import datetime

import pytest

from src.domain.entities.user import User
from src.domain.exceptions import DomainError
from src.domain.value_objects.user_role import UserRole


class TestUserCreation:
    """测试User创建"""

    def test_create_from_github_with_valid_data_should_succeed(self):
        """
        测试：使用有效的GitHub数据创建用户应该成功

        Given: 有效的GitHub用户信息
        When: 调用User.create_from_github
        Then: 返回User实体，字段正确设置
        """
        # Arrange
        github_id = 12345678
        github_username = "testuser"
        email = "test@example.com"
        name = "Test User"
        avatar_url = "https://avatars.githubusercontent.com/u/12345678"
        profile_url = "https://github.com/testuser"

        # Act
        user = User.create_from_github(
            github_id=github_id,
            github_username=github_username,
            email=email,
            name=name,
            avatar_url=avatar_url,
            profile_url=profile_url,
        )

        # Assert
        assert user.id is not None
        assert user.github_id == github_id
        assert user.github_username == github_username
        assert user.email == email
        assert user.name == name
        assert user.github_avatar_url == avatar_url
        assert user.github_profile_url == profile_url
        assert user.is_active is True
        assert user.role == UserRole.USER
        assert isinstance(user.created_at, datetime)
        assert user.updated_at is None
        assert user.last_login_at is None

    def test_create_from_github_with_minimal_data_should_succeed(self):
        """
        测试：使用最小必需数据创建用户应该成功

        Given: 只有必需的GitHub用户信息（github_id, username, email）
        When: 调用User.create_from_github
        Then: 返回User实体，可选字段为None
        """
        # Arrange
        github_id = 87654321
        github_username = "minimaluser"
        email = "minimal@example.com"

        # Act
        user = User.create_from_github(
            github_id=github_id,
            github_username=github_username,
            email=email,
        )

        # Assert
        assert user.id is not None
        assert user.github_id == github_id
        assert user.github_username == github_username
        assert user.email == email
        assert user.name is None
        assert user.github_avatar_url is None
        assert user.github_profile_url is None

    def test_create_from_github_with_invalid_github_id_should_raise_error(self):
        """
        测试：使用无效的github_id创建用户应该抛出DomainError

        Given: github_id为0或负数
        When: 调用User.create_from_github
        Then: 抛出DomainError，提示github_id必须大于0
        """
        # Arrange
        invalid_github_ids = [0, -1, None]

        for invalid_id in invalid_github_ids:
            # Act & Assert
            with pytest.raises(DomainError, match="github_id必须大于0"):
                User.create_from_github(
                    github_id=invalid_id,
                    github_username="testuser",
                    email="test@example.com",
                )

    def test_create_from_github_with_empty_username_should_raise_error(self):
        """
        测试：使用空的github_username创建用户应该抛出DomainError

        Given: github_username为空字符串或None
        When: 调用User.create_from_github
        Then: 抛出DomainError，提示github_username不能为空
        """
        # Arrange
        invalid_usernames = ["", None]

        for invalid_username in invalid_usernames:
            # Act & Assert
            with pytest.raises(DomainError, match="github_username不能为空"):
                User.create_from_github(
                    github_id=12345,
                    github_username=invalid_username,
                    email="test@example.com",
                )

    def test_create_from_github_with_empty_email_should_raise_error(self):
        """
        测试：使用空的email创建用户应该抛出DomainError

        Given: email为空字符串或None
        When: 调用User.create_from_github
        Then: 抛出DomainError，提示email不能为空
        """
        # Arrange
        invalid_emails = ["", None]

        for invalid_email in invalid_emails:
            # Act & Assert
            with pytest.raises(DomainError, match="email不能为空"):
                User.create_from_github(
                    github_id=12345,
                    github_username="testuser",
                    email=invalid_email,
                )

    def test_create_from_github_with_invalid_email_format_should_raise_error(self):
        """
        测试：使用无效格式的email创建用户应该抛出DomainError

        Given: email格式无效（缺少@符号）
        When: 调用User.create_from_github
        Then: 抛出DomainError，提示email格式无效
        """
        # Arrange
        invalid_email = "invalidemail.com"

        # Act & Assert
        with pytest.raises(DomainError, match="email格式无效"):
            User.create_from_github(
                github_id=12345,
                github_username="testuser",
                email=invalid_email,
            )


class TestUserLoginTracking:
    """测试用户登录时间追踪"""

    def test_update_login_time_should_update_timestamps(self):
        """
        测试：更新登录时间应该更新last_login_at和updated_at

        Given: 一个已存在的用户
        When: 调用update_login_time方法
        Then: last_login_at和updated_at应该被设置为当前时间
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        original_last_login = user.last_login_at
        original_updated_at = user.updated_at

        # Act
        user.update_login_time()

        # Assert
        assert user.last_login_at is not None
        assert user.updated_at is not None
        assert user.last_login_at != original_last_login
        assert user.updated_at != original_updated_at


class TestUserProfileUpdate:
    """测试用户资料更新"""

    def test_update_profile_with_name_should_update_name_and_timestamp(self):
        """
        测试：更新用户姓名应该更新name和updated_at

        Given: 一个已存在的用户
        When: 调用update_profile更新name
        Then: name应该被更新，updated_at应该被设置
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        new_name = "New Name"

        # Act
        user.update_profile(name=new_name)

        # Assert
        assert user.name == new_name
        assert user.updated_at is not None

    def test_update_profile_with_avatar_should_update_avatar_and_timestamp(self):
        """
        测试：更新用户头像应该更新avatar_url和updated_at

        Given: 一个已存在的用户
        When: 调用update_profile更新avatar_url
        Then: avatar_url应该被更新，updated_at应该被设置
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        new_avatar = "https://new-avatar.com/avatar.png"

        # Act
        user.update_profile(avatar_url=new_avatar)

        # Assert
        assert user.github_avatar_url == new_avatar
        assert user.updated_at is not None


class TestUserActivation:
    """测试用户激活/停用"""

    def test_deactivate_active_user_should_succeed(self):
        """
        测试：停用激活的用户应该成功

        Given: 一个激活的用户
        When: 调用deactivate方法
        Then: is_active应该变为False，updated_at应该被更新
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        assert user.is_active is True

        # Act
        user.deactivate()

        # Assert
        assert user.is_active is False
        assert user.updated_at is not None

    def test_deactivate_inactive_user_should_raise_error(self):
        """
        测试：停用已停用的用户应该抛出DomainError

        Given: 一个已停用的用户
        When: 调用deactivate方法
        Then: 抛出DomainError，提示用户已被停用
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        user.deactivate()

        # Act & Assert
        with pytest.raises(DomainError, match="用户已被停用"):
            user.deactivate()

    def test_activate_inactive_user_should_succeed(self):
        """
        测试：激活停用的用户应该成功

        Given: 一个停用的用户
        When: 调用activate方法
        Then: is_active应该变为True，updated_at应该被更新
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        user.deactivate()
        assert user.is_active is False

        # Act
        user.activate()

        # Assert
        assert user.is_active is True
        assert user.updated_at is not None

    def test_activate_active_user_should_raise_error(self):
        """
        测试：激活已激活的用户应该抛出DomainError

        Given: 一个已激活的用户
        When: 调用activate方法
        Then: 抛出DomainError，提示用户已处于激活状态
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )

        # Act & Assert
        with pytest.raises(DomainError, match="用户已处于激活状态"):
            user.activate()


class TestUserRoleManagement:
    """测试用户角色管理"""

    def test_promote_to_admin_should_succeed(self):
        """
        测试：提升普通用户为管理员应该成功

        Given: 一个普通用户
        When: 调用promote_to_admin方法
        Then: role应该变为ADMIN，updated_at应该被更新
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        assert user.role == UserRole.USER

        # Act
        user.promote_to_admin()

        # Assert
        assert user.role == UserRole.ADMIN
        assert user.updated_at is not None

    def test_promote_admin_to_admin_should_raise_error(self):
        """
        测试：提升已是管理员的用户应该抛出DomainError

        Given: 一个管理员用户
        When: 调用promote_to_admin方法
        Then: 抛出DomainError，提示用户已经是管理员
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        user.promote_to_admin()

        # Act & Assert
        with pytest.raises(DomainError, match="用户已经是管理员"):
            user.promote_to_admin()

    def test_demote_to_user_should_succeed(self):
        """
        测试：降级管理员为普通用户应该成功

        Given: 一个管理员用户
        When: 调用demote_to_user方法
        Then: role应该变为USER，updated_at应该被更新
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        user.promote_to_admin()
        assert user.role == UserRole.ADMIN

        # Act
        user.demote_to_user()

        # Assert
        assert user.role == UserRole.USER
        assert user.updated_at is not None

    def test_demote_user_to_user_should_raise_error(self):
        """
        测试：降级已是普通用户应该抛出DomainError

        Given: 一个普通用户
        When: 调用demote_to_user方法
        Then: 抛出DomainError，提示用户已经是普通用户
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )

        # Act & Assert
        with pytest.raises(DomainError, match="用户已经是普通用户"):
            user.demote_to_user()


class TestUserPermissions:
    """测试用户权限检查"""

    def test_is_admin_for_admin_user_should_return_true(self):
        """
        测试：管理员用户的is_admin应该返回True

        Given: 一个管理员用户
        When: 调用is_admin方法
        Then: 返回True
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="adminuser",
            email="admin@example.com",
        )
        user.promote_to_admin()

        # Act
        result = user.is_admin()

        # Assert
        assert result is True

    def test_is_admin_for_regular_user_should_return_false(self):
        """
        测试：普通用户的is_admin应该返回False

        Given: 一个普通用户
        When: 调用is_admin方法
        Then: 返回False
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )

        # Act
        result = user.is_admin()

        # Assert
        assert result is False

    def test_can_create_workflow_for_active_user_should_return_true(self):
        """
        测试：激活用户的can_create_workflow应该返回True

        Given: 一个激活的用户
        When: 调用can_create_workflow方法
        Then: 返回True
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )

        # Act
        result = user.can_create_workflow()

        # Assert
        assert result is True

    def test_can_create_workflow_for_inactive_user_should_return_false(self):
        """
        测试：停用用户的can_create_workflow应该返回False

        Given: 一个停用的用户
        When: 调用can_create_workflow方法
        Then: 返回False
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        user.deactivate()

        # Act
        result = user.can_create_workflow()

        # Assert
        assert result is False

    def test_can_upload_tool_for_active_user_should_return_true(self):
        """
        测试：激活用户的can_upload_tool应该返回True

        Given: 一个激活的用户
        When: 调用can_upload_tool方法
        Then: 返回True
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )

        # Act
        result = user.can_upload_tool()

        # Assert
        assert result is True

    def test_can_upload_tool_for_inactive_user_should_return_false(self):
        """
        测试：停用用户的can_upload_tool应该返回False

        Given: 一个停用的用户
        When: 调用can_upload_tool方法
        Then: 返回False
        """
        # Arrange
        user = User.create_from_github(
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
        )
        user.deactivate()

        # Act
        result = user.can_upload_tool()

        # Assert
        assert result is False

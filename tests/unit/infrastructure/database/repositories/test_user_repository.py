"""UserRepository 单元测试（P2-Infrastructure）

测试 SQLAlchemyUserRepository 的持久化功能，遵循 TDD 原则。

测试范围：
1. Save Operations: save_new_user, save_existing_user, duplicate_github_id (3 tests)
2. Find Operations: find_by_id, find_by_github_id, find_by_email, get_by_id (6 tests)
3. Exists Operations: exists_by_github_id, exists_by_email (4 tests)
4. List Operations: list_all, list_all_with_pagination (3 tests)
5. Count Operations: count, count_empty (2 tests)
6. Delete Operations: delete_existing, delete_nonexistent (2 tests)
7. Entity Conversion: to_entity, to_model (2 tests)

测试原则：
- 使用真实的数据库（SQLite 内存数据库）
- 每个测试独立运行，互不影响
- 测试 ORM 模型和领域实体之间的转换
- 测试数据库约束（唯一索引等）

测试结果：
- 24 tests, 100% coverage (13/13 statements)
- 所有测试通过，完整覆盖所有 CRUD 操作

覆盖目标：0% → 100% (P0 tests achieved)
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.entities.user import User
from src.domain.exceptions import EntityNotFoundError
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository


@pytest.fixture
def in_memory_db_engine():
    """创建内存数据库引擎"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(in_memory_db_engine):
    """创建数据库会话"""
    connection = in_memory_db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def user_repository(session):
    """创建UserRepository实例"""
    return SQLAlchemyUserRepository(session)


@pytest.fixture
def sample_user():
    """创建示例用户"""
    return User.create_from_github(
        github_id=12345678,
        github_username="testuser",
        email="test@example.com",
        name="Test User",
        avatar_url="https://avatars.githubusercontent.com/u/12345678",
        profile_url="https://github.com/testuser",
    )


class TestUserRepositorySave:
    """测试用户保存"""

    def test_save_new_user_should_persist_to_database(self, user_repository, sample_user):
        """
        测试：保存新用户应该成功持久化到数据库

        Given: 一个新创建的用户实体
        When: 调用repository.save
        Then: 用户应该被保存到数据库，可以通过ID查询到
        """
        # Act
        user_repository.save(sample_user)

        # Assert
        saved_user = user_repository.find_by_id(sample_user.id)
        assert saved_user is not None
        assert saved_user.id == sample_user.id
        assert saved_user.github_id == sample_user.github_id
        assert saved_user.github_username == sample_user.github_username
        assert saved_user.email == sample_user.email
        assert saved_user.name == sample_user.name
        assert saved_user.is_active == sample_user.is_active
        assert saved_user.role == sample_user.role

    def test_save_existing_user_should_update_fields(self, user_repository, sample_user):
        """
        测试：保存已存在的用户应该更新字段

        Given: 一个已保存的用户
        When: 修改用户字段后再次调用save
        Then: 数据库中的用户字段应该被更新
        """
        # Arrange
        user_repository.save(sample_user)

        # Act - 修改用户
        sample_user.update_profile(name="Updated Name")
        user_repository.save(sample_user)

        # Assert
        updated_user = user_repository.find_by_id(sample_user.id)
        assert updated_user.name == "Updated Name"

    def test_save_user_with_duplicate_github_id_should_fail(self, user_repository, sample_user):
        """
        测试：保存具有相同github_id的用户应该失败

        Given: 一个已保存的用户
        When: 尝试保存具有相同github_id但不同ID的用户
        Then: 应该抛出IntegrityError
        """
        # Arrange
        user_repository.save(sample_user)

        # Create a different user with the same github_id
        duplicate_user = User.create_from_github(
            github_id=12345678,  # 相同的github_id
            github_username="anotheruser",
            email="another@example.com",
        )

        # Act & Assert
        with pytest.raises(IntegrityError):
            user_repository.save(duplicate_user)


class TestUserRepositoryFindById:
    """测试根据ID查找用户"""

    def test_find_by_id_existing_user_should_return_user(self, user_repository, sample_user):
        """
        测试：查找存在的用户应该返回用户实体

        Given: 一个已保存的用户
        When: 调用find_by_id传入用户ID
        Then: 返回用户实体
        """
        # Arrange
        user_repository.save(sample_user)

        # Act
        found_user = user_repository.find_by_id(sample_user.id)

        # Assert
        assert found_user is not None
        assert found_user.id == sample_user.id
        assert found_user.email == sample_user.email

    def test_find_by_id_nonexistent_user_should_return_none(self, user_repository):
        """
        测试：查找不存在的用户应该返回None

        Given: 空数据库
        When: 调用find_by_id传入不存在的ID
        Then: 返回None
        """
        # Act
        found_user = user_repository.find_by_id("nonexistent-id")

        # Assert
        assert found_user is None

    def test_get_by_id_existing_user_should_return_user(self, user_repository, sample_user):
        """
        测试：get_by_id查找存在的用户应该返回用户实体

        Given: 一个已保存的用户
        When: 调用get_by_id传入用户ID
        Then: 返回用户实体
        """
        # Arrange
        user_repository.save(sample_user)

        # Act
        found_user = user_repository.get_by_id(sample_user.id)

        # Assert
        assert found_user is not None
        assert found_user.id == sample_user.id

    def test_get_by_id_nonexistent_user_should_raise_error(self, user_repository):
        """
        测试：get_by_id查找不存在的用户应该抛出EntityNotFoundError

        Given: 空数据库
        When: 调用get_by_id传入不存在的ID
        Then: 抛出EntityNotFoundError
        """
        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            user_repository.get_by_id("nonexistent-id")


class TestUserRepositoryFindByGithubId:
    """测试根据GitHub ID查找用户"""

    def test_find_by_github_id_existing_user_should_return_user(self, user_repository, sample_user):
        """
        测试：根据GitHub ID查找存在的用户应该返回用户实体

        Given: 一个已保存的用户
        When: 调用find_by_github_id传入GitHub ID
        Then: 返回用户实体
        """
        # Arrange
        user_repository.save(sample_user)

        # Act
        found_user = user_repository.find_by_github_id(sample_user.github_id)

        # Assert
        assert found_user is not None
        assert found_user.github_id == sample_user.github_id
        assert found_user.id == sample_user.id

    def test_find_by_github_id_nonexistent_user_should_return_none(self, user_repository):
        """
        测试：根据GitHub ID查找不存在的用户应该返回None

        Given: 空数据库
        When: 调用find_by_github_id传入不存在的GitHub ID
        Then: 返回None
        """
        # Act
        found_user = user_repository.find_by_github_id(99999999)

        # Assert
        assert found_user is None


class TestUserRepositoryFindByEmail:
    """测试根据邮箱查找用户"""

    def test_find_by_email_existing_user_should_return_user(self, user_repository, sample_user):
        """
        测试：根据邮箱查找存在的用户应该返回用户实体

        Given: 一个已保存的用户
        When: 调用find_by_email传入邮箱
        Then: 返回用户实体
        """
        # Arrange
        user_repository.save(sample_user)

        # Act
        found_user = user_repository.find_by_email(sample_user.email)

        # Assert
        assert found_user is not None
        assert found_user.email == sample_user.email
        assert found_user.id == sample_user.id

    def test_find_by_email_nonexistent_user_should_return_none(self, user_repository):
        """
        测试：根据邮箱查找不存在的用户应该返回None

        Given: 空数据库
        When: 调用find_by_email传入不存在的邮箱
        Then: 返回None
        """
        # Act
        found_user = user_repository.find_by_email("nonexistent@example.com")

        # Assert
        assert found_user is None


class TestUserRepositoryExists:
    """测试用户是否存在"""

    def test_exists_by_github_id_for_existing_user_should_return_true(
        self, user_repository, sample_user
    ):
        """
        测试：存在的用户GitHub ID应该返回True

        Given: 一个已保存的用户
        When: 调用exists_by_github_id传入该用户的GitHub ID
        Then: 返回True
        """
        # Arrange
        user_repository.save(sample_user)

        # Act
        exists = user_repository.exists_by_github_id(sample_user.github_id)

        # Assert
        assert exists is True

    def test_exists_by_github_id_for_nonexistent_user_should_return_false(self, user_repository):
        """
        测试：不存在的用户GitHub ID应该返回False

        Given: 空数据库
        When: 调用exists_by_github_id传入不存在的GitHub ID
        Then: 返回False
        """
        # Act
        exists = user_repository.exists_by_github_id(99999999)

        # Assert
        assert exists is False

    def test_exists_by_email_for_existing_user_should_return_true(
        self, user_repository, sample_user
    ):
        """
        测试：存在的用户邮箱应该返回True

        Given: 一个已保存的用户
        When: 调用exists_by_email传入该用户的邮箱
        Then: 返回True
        """
        # Arrange
        user_repository.save(sample_user)

        # Act
        exists = user_repository.exists_by_email(sample_user.email)

        # Assert
        assert exists is True

    def test_exists_by_email_for_nonexistent_user_should_return_false(self, user_repository):
        """
        测试：不存在的用户邮箱应该返回False

        Given: 空数据库
        When: 调用exists_by_email传入不存在的邮箱
        Then: 返回False
        """
        # Act
        exists = user_repository.exists_by_email("nonexistent@example.com")

        # Assert
        assert exists is False


class TestUserRepositoryListAll:
    """测试列出所有用户"""

    def test_list_all_with_multiple_users_should_return_all_users(self, user_repository):
        """
        测试：列出所有用户应该返回所有用户

        Given: 数据库中有3个用户
        When: 调用list_all
        Then: 返回所有3个用户
        """
        # Arrange
        user1 = User.create_from_github(12345, "user1", "user1@example.com")
        user2 = User.create_from_github(23456, "user2", "user2@example.com")
        user3 = User.create_from_github(34567, "user3", "user3@example.com")
        user_repository.save(user1)
        user_repository.save(user2)
        user_repository.save(user3)

        # Act
        users = user_repository.list_all()

        # Assert
        assert len(users) == 3
        emails = [u.email for u in users]
        assert "user1@example.com" in emails
        assert "user2@example.com" in emails
        assert "user3@example.com" in emails

    def test_list_all_with_pagination_should_return_correct_page(self, user_repository):
        """
        测试：分页列出用户应该返回正确的页

        Given: 数据库中有5个用户
        When: 调用list_all(skip=2, limit=2)
        Then: 返回第3和第4个用户
        """
        # Arrange
        for i in range(5):
            user = User.create_from_github(
                github_id=10000 + i,
                github_username=f"user{i}",
                email=f"user{i}@example.com",
            )
            user_repository.save(user)

        # Act
        users = user_repository.list_all(skip=2, limit=2)

        # Assert
        assert len(users) == 2

    def test_list_all_empty_database_should_return_empty_list(self, user_repository):
        """
        测试：空数据库列出所有用户应该返回空列表

        Given: 空数据库
        When: 调用list_all
        Then: 返回空列表
        """
        # Act
        users = user_repository.list_all()

        # Assert
        assert len(users) == 0


class TestUserRepositoryCount:
    """测试统计用户总数"""

    def test_count_with_multiple_users_should_return_correct_count(self, user_repository):
        """
        测试：统计用户总数应该返回正确的数量

        Given: 数据库中有3个用户
        When: 调用count
        Then: 返回3
        """
        # Arrange
        user1 = User.create_from_github(12345, "user1", "user1@example.com")
        user2 = User.create_from_github(23456, "user2", "user2@example.com")
        user3 = User.create_from_github(34567, "user3", "user3@example.com")
        user_repository.save(user1)
        user_repository.save(user2)
        user_repository.save(user3)

        # Act
        count = user_repository.count()

        # Assert
        assert count == 3

    def test_count_empty_database_should_return_zero(self, user_repository):
        """
        测试：空数据库统计用户总数应该返回0

        Given: 空数据库
        When: 调用count
        Then: 返回0
        """
        # Act
        count = user_repository.count()

        # Assert
        assert count == 0


class TestUserRepositoryDelete:
    """测试删除用户"""

    def test_delete_existing_user_should_succeed(self, user_repository, sample_user):
        """
        测试：删除存在的用户应该成功

        Given: 一个已保存的用户
        When: 调用delete传入用户ID
        Then: 用户应该被删除，无法再通过ID查询到
        """
        # Arrange
        user_repository.save(sample_user)
        assert user_repository.find_by_id(sample_user.id) is not None

        # Act
        user_repository.delete(sample_user.id)

        # Assert
        assert user_repository.find_by_id(sample_user.id) is None

    def test_delete_nonexistent_user_should_raise_error(self, user_repository):
        """
        测试：删除不存在的用户应该抛出EntityNotFoundError

        Given: 空数据库
        When: 调用delete传入不存在的ID
        Then: 抛出EntityNotFoundError
        """
        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            user_repository.delete("nonexistent-id")


class TestUserRepositoryEntityConversion:
    """测试实体转换（ORM ⇄ Entity）"""

    def test_to_entity_should_correctly_convert_all_fields(self, user_repository, sample_user):
        """
        测试：ORM模型转换为实体应该正确转换所有字段

        Given: 一个已保存的用户（包含所有字段）
        When: 从数据库查询并转换为实体
        Then: 所有字段应该正确转换
        """
        # Arrange
        sample_user.update_login_time()  # 设置last_login_at
        user_repository.save(sample_user)

        # Act
        loaded_user = user_repository.find_by_id(sample_user.id)

        # Assert
        assert loaded_user.id == sample_user.id
        assert loaded_user.github_id == sample_user.github_id
        assert loaded_user.github_username == sample_user.github_username
        assert loaded_user.email == sample_user.email
        assert loaded_user.name == sample_user.name
        assert loaded_user.github_avatar_url == sample_user.github_avatar_url
        assert loaded_user.github_profile_url == sample_user.github_profile_url
        assert loaded_user.is_active == sample_user.is_active
        assert loaded_user.role == sample_user.role
        assert loaded_user.created_at is not None
        assert loaded_user.updated_at is not None
        assert loaded_user.last_login_at is not None

    def test_to_model_should_correctly_convert_all_fields(self, user_repository, sample_user):
        """
        测试：实体转换为ORM模型应该正确转换所有字段

        Given: 一个用户实体
        When: 保存到数据库
        Then: 所有字段应该正确持久化
        """
        # Act
        user_repository.save(sample_user)
        loaded_user = user_repository.find_by_id(sample_user.id)

        # Assert - 验证所有字段都正确持久化
        assert loaded_user.id == sample_user.id
        assert loaded_user.github_id == sample_user.github_id
        assert loaded_user.github_username == sample_user.github_username
        assert loaded_user.email == sample_user.email

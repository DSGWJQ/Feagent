"""LLMProvider Repository 单元测试

测试 SQLAlchemy LLMProvider Repository 实现

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- LLMProviderRepository 是领域层定义的 Port 接口
- SQLAlchemyLLMProviderRepository 是基础设施层的实现（Adapter）
- 负责 LLMProvider 实体的持久化操作（CRUD）
- 负责 ORM 模型和领域实体之间的转换（Assembler）

测试策略：
1. 使用内存数据库（SQLite :memory:）进行测试
2. 每个测试独立（使用 fixture 创建新的数据库会话）
3. 测试所有 Repository 方法
4. 测试异常情况
5. 测试幂等性
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.llm_provider import LLMProvider
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.llm_provider_repository import (
    SQLAlchemyLLMProviderRepository,
)


# ==================== Fixtures ====================


@pytest.fixture
def engine():
    """创建同步内存数据库引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
    )

    # 创建所有表
    Base.metadata.create_all(engine)

    yield engine

    # 清理：关闭引擎
    engine.dispose()


@pytest.fixture
def db_session(engine):
    """创建同步数据库会话"""
    session_maker = sessionmaker(engine, class_=Session, expire_on_commit=False)

    session = session_maker()
    yield session
    # 测试结束后回滚（保持数据库干净）
    session.rollback()
    session.close()


@pytest.fixture
def provider_repository(db_session: Session) -> SQLAlchemyLLMProviderRepository:
    """创建 LLMProvider Repository"""
    return SQLAlchemyLLMProviderRepository(db_session)


@pytest.fixture
def sample_openai_provider() -> LLMProvider:
    """创建示例 OpenAI Provider"""
    return LLMProvider.create_openai(api_key="sk-test-openai-key")


@pytest.fixture
def sample_deepseek_provider() -> LLMProvider:
    """创建示例 DeepSeek Provider"""
    return LLMProvider.create_deepseek(api_key="sk-test-deepseek-key")


class TestLLMProviderRepositorySave:
    """保存 LLMProvider 测试"""

    def test_save_new_provider(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试保存新 LLMProvider"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        # 验证保存成功
        retrieved = provider_repository.find_by_id(sample_openai_provider.id)
        assert retrieved is not None
        assert retrieved.name == "openai"
        assert retrieved.display_name == "OpenAI"

    def test_save_multiple_providers(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        sample_deepseek_provider: LLMProvider,
        db_session: Session,
    ):
        """测试保存多个 LLMProvider"""
        provider_repository.save(sample_openai_provider)
        provider_repository.save(sample_deepseek_provider)
        db_session.commit()

        # 验证都保存成功
        all_providers = provider_repository.find_all()
        assert len(all_providers) >= 2
        provider_names = [p.name for p in all_providers]
        assert "openai" in provider_names
        assert "deepseek" in provider_names


class TestLLMProviderRepositoryRetrieval:
    """查询 LLMProvider 测试"""

    def test_get_by_id_success(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试按 ID 获取 LLMProvider（成功）"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        retrieved = provider_repository.get_by_id(sample_openai_provider.id)
        assert retrieved.id == sample_openai_provider.id
        assert retrieved.name == "openai"

    def test_get_by_id_not_found(
        self, provider_repository: SQLAlchemyLLMProviderRepository
    ):
        """测试按 ID 获取 LLMProvider（不存在）"""
        with pytest.raises(NotFoundError):
            provider_repository.get_by_id("llm_provider_nonexistent")

    def test_get_by_name_success(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试按名称获取 LLMProvider（成功）"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        retrieved = provider_repository.get_by_name("openai")
        assert retrieved.name == "openai"
        assert retrieved.display_name == "OpenAI"

    def test_get_by_name_not_found(
        self, provider_repository: SQLAlchemyLLMProviderRepository
    ):
        """测试按名称获取 LLMProvider（不存在）"""
        with pytest.raises(NotFoundError):
            provider_repository.get_by_name("nonexistent")

    def test_find_by_id_success(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试按 ID 查找 LLMProvider（成功）"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        retrieved = provider_repository.find_by_id(sample_openai_provider.id)
        assert retrieved is not None
        assert retrieved.id == sample_openai_provider.id

    def test_find_by_id_not_found(
        self, provider_repository: SQLAlchemyLLMProviderRepository
    ):
        """测试按 ID 查找 LLMProvider（不存在）"""
        result = provider_repository.find_by_id("llm_provider_nonexistent")
        assert result is None

    def test_find_by_name_success(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_deepseek_provider: LLMProvider,
        db_session: Session,
    ):
        """测试按名称查找 LLMProvider（成功）"""
        provider_repository.save(sample_deepseek_provider)
        db_session.commit()

        retrieved = provider_repository.find_by_name("deepseek")
        assert retrieved is not None
        assert retrieved.name == "deepseek"

    def test_find_by_name_not_found(
        self, provider_repository: SQLAlchemyLLMProviderRepository
    ):
        """测试按名称查找 LLMProvider（不存在）"""
        result = provider_repository.find_by_name("nonexistent")
        assert result is None

    def test_find_all(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        db_session: Session,
    ):
        """测试查找所有 LLMProvider"""
        # 创建多个提供商
        openai = LLMProvider.create_openai(api_key="test_key")
        deepseek = LLMProvider.create_deepseek(api_key="test_key")
        qwen = LLMProvider.create_qwen(api_key="test_key")

        provider_repository.save(openai)
        provider_repository.save(deepseek)
        provider_repository.save(qwen)
        db_session.commit()

        # 查找所有
        all_providers = provider_repository.find_all()
        assert len(all_providers) >= 3
        provider_names = [p.name for p in all_providers]
        assert "openai" in provider_names
        assert "deepseek" in provider_names
        assert "qwen" in provider_names


class TestLLMProviderRepositoryStatus:
    """启用/禁用状态测试"""

    def test_find_enabled(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        db_session: Session,
    ):
        """测试查找已启用的 LLMProvider"""
        # 创建已启用的提供商
        openai = LLMProvider.create_openai(api_key="test_key")

        # 创建禁用的提供商
        deepseek = LLMProvider.create_deepseek(api_key="test_key")
        deepseek.disable()

        provider_repository.save(openai)
        provider_repository.save(deepseek)
        db_session.commit()

        # 查找已启用的提供商
        enabled_providers = provider_repository.find_enabled()
        enabled_names = [p.name for p in enabled_providers]

        # openai 应该在已启用列表中
        assert "openai" in enabled_names

        # deepseek 不应该在已启用列表中
        assert "deepseek" not in enabled_names


class TestLLMProviderRepositoryUpdate:
    """更新 LLMProvider 测试"""

    def test_update_provider(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试更新 LLMProvider"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        # 更新 API 密钥
        retrieved = provider_repository.get_by_id(sample_openai_provider.id)
        retrieved.update_api_key("new-api-key")
        provider_repository.save(retrieved)
        db_session.commit()

        # 验证更新成功
        updated = provider_repository.get_by_id(sample_openai_provider.id)
        assert updated.api_key == "new-api-key"

    def test_disable_and_enable(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试禁用和启用提供商"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        # 禁用
        retrieved = provider_repository.get_by_id(sample_openai_provider.id)
        assert retrieved.enabled is True
        retrieved.disable()
        provider_repository.save(retrieved)
        db_session.commit()

        # 验证禁用
        retrieved = provider_repository.get_by_id(sample_openai_provider.id)
        assert retrieved.enabled is False

        # 启用
        retrieved.enable()
        provider_repository.save(retrieved)
        db_session.commit()

        # 验证启用
        retrieved = provider_repository.get_by_id(sample_openai_provider.id)
        assert retrieved.enabled is True

    def test_add_model(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试添加模型"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        # 获取初始模型列表
        retrieved = provider_repository.get_by_id(sample_openai_provider.id)
        initial_count = len(retrieved.models)

        # 添加新模型
        retrieved.add_model("gpt-5")
        provider_repository.save(retrieved)
        db_session.commit()

        # 验证模型已添加
        retrieved = provider_repository.get_by_id(sample_openai_provider.id)
        assert len(retrieved.models) == initial_count + 1
        assert "gpt-5" in retrieved.models


class TestLLMProviderRepositoryExists:
    """存在性检查测试"""

    def test_exists_true(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试提供商存在"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        assert provider_repository.exists(sample_openai_provider.id) is True

    def test_exists_false(
        self, provider_repository: SQLAlchemyLLMProviderRepository
    ):
        """测试提供商不存在"""
        assert provider_repository.exists("llm_provider_nonexistent") is False


class TestLLMProviderRepositoryDelete:
    """删除 LLMProvider 测试"""

    def test_delete_existing_provider(
        self,
        provider_repository: SQLAlchemyLLMProviderRepository,
        sample_openai_provider: LLMProvider,
        db_session: Session,
    ):
        """测试删除存在的提供商"""
        provider_repository.save(sample_openai_provider)
        db_session.commit()

        # 验证存在
        assert provider_repository.exists(sample_openai_provider.id) is True

        # 删除
        provider_repository.delete(sample_openai_provider.id)
        db_session.commit()

        # 验证已删除
        assert provider_repository.exists(sample_openai_provider.id) is False
        assert provider_repository.find_by_id(sample_openai_provider.id) is None

    def test_delete_nonexistent_provider(
        self, provider_repository: SQLAlchemyLLMProviderRepository
    ):
        """测试删除不存在的提供商（幂等）"""
        # 应该不抛异常
        provider_repository.delete("llm_provider_nonexistent")

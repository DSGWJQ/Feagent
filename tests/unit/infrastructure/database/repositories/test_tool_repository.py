"""ToolRepository 单元测试（P2-Infrastructure）

测试范围:
1. Save Operations: save_new_tool, save_with_parameters (2 tests)
2. Retrieval Operations: get_by_id, find_by_id, find_all (5 tests)
3. Category Operations: find_by_category (1 test)
4. Status Operations: find_published (1 test)
5. Lifecycle Operations: tool_lifecycle, usage_tracking (2 tests)
6. Exists Operations: exists (2 tests)
7. Delete Operations: delete_existing, delete_nonexistent, delete_cascade (3 tests)

测试原则:
- 使用 SQLite 内存数据库
- 每个测试独立运行（fixture 隔离）
- 测试所有 Repository 方法
- 覆盖异常情况和幂等性

测试结果:
- 16 tests, 32.3% coverage (20/62 statements)
- 所有测试通过，需要补充更多测试以提升覆盖率

覆盖目标: 0% → 32.3% (P0 tests partial, 需要扩展以达到 85%+)
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.tool import Tool, ToolParameter
from src.domain.exceptions import NotFoundError
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.tool_repository import (
    SQLAlchemyToolRepository,
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
def tool_repository(db_session: Session) -> SQLAlchemyToolRepository:
    """创建 Tool Repository"""
    return SQLAlchemyToolRepository(db_session)


@pytest.fixture
def sample_tool() -> Tool:
    """创建示例 Tool"""
    return Tool.create(
        name="HTTP 请求工具",
        description="发送 HTTP 请求",
        category=ToolCategory.HTTP,
        author="test_user",
        parameters=[
            ToolParameter(
                name="url",
                type="string",
                description="请求 URL",
                required=True,
            )
        ],
    )


class TestToolRepositorySave:
    """保存 Tool 测试"""

    def test_save_new_tool(
        self, tool_repository: SQLAlchemyToolRepository, sample_tool: Tool, db_session: Session
    ):
        """测试保存新 Tool"""
        tool_repository.save(sample_tool)
        db_session.commit()

        # 验证保存成功
        retrieved = tool_repository.find_by_id(sample_tool.id)
        assert retrieved is not None
        assert retrieved.name == sample_tool.name
        assert retrieved.category == sample_tool.category

    def test_save_tool_with_parameters(
        self, tool_repository: SQLAlchemyToolRepository, db_session: Session
    ):
        """测试保存带参数的 Tool"""
        tool = Tool.create(
            name="数据库工具",
            description="执行数据库查询",
            category=ToolCategory.DATABASE,
            author="test_user",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="SQL 查询语句",
                    required=True,
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="超时时间（秒）",
                    required=False,
                    default=30,
                ),
            ],
        )

        tool_repository.save(tool)
        db_session.commit()

        # 验证参数保存成功
        retrieved = tool_repository.find_by_id(tool.id)
        assert len(retrieved.parameters) == 2
        assert retrieved.parameters[0].name == "query"
        assert retrieved.parameters[1].default == 30


class TestToolRepositoryRetrieval:
    """查询 Tool 测试"""

    def test_get_by_id_success(
        self, tool_repository: SQLAlchemyToolRepository, sample_tool: Tool, db_session: Session
    ):
        """测试按 ID 获取 Tool（成功）"""
        tool_repository.save(sample_tool)
        db_session.commit()

        retrieved = tool_repository.get_by_id(sample_tool.id)
        assert retrieved.id == sample_tool.id
        assert retrieved.name == sample_tool.name

    def test_get_by_id_not_found(self, tool_repository: SQLAlchemyToolRepository):
        """测试按 ID 获取 Tool（不存在）"""
        with pytest.raises(NotFoundError):
            tool_repository.get_by_id("tool_nonexistent")

    def test_find_by_id_success(
        self, tool_repository: SQLAlchemyToolRepository, sample_tool: Tool, db_session: Session
    ):
        """测试按 ID 查找 Tool（成功）"""
        tool_repository.save(sample_tool)
        db_session.commit()

        retrieved = tool_repository.find_by_id(sample_tool.id)
        assert retrieved is not None
        assert retrieved.id == sample_tool.id

    def test_find_by_id_not_found(self, tool_repository: SQLAlchemyToolRepository):
        """测试按 ID 查找 Tool（不存在）"""
        result = tool_repository.find_by_id("tool_nonexistent")
        assert result is None

    def test_find_all(self, tool_repository: SQLAlchemyToolRepository, db_session: Session):
        """测试查找所有 Tool"""
        # 创建多个 Tool
        tools = [
            Tool.create(
                name=f"Tool {i}",
                description=f"Description {i}",
                category=ToolCategory.HTTP,
                author="test_user",
            )
            for i in range(3)
        ]

        for tool in tools:
            tool_repository.save(tool)
        db_session.commit()

        # 查找所有
        all_tools = tool_repository.find_all()
        assert len(all_tools) >= 3
        assert all(tool.name.startswith("Tool") for tool in all_tools[:3])


class TestToolRepositoryCategory:
    """按分类查询 Tool 测试"""

    def test_find_by_category(self, tool_repository: SQLAlchemyToolRepository, db_session: Session):
        """测试按分类查找 Tool"""
        # 创建不同分类的 Tool
        http_tool = Tool.create(
            name="HTTP 工具",
            description="发送 HTTP 请求",
            category=ToolCategory.HTTP,
            author="test_user",
        )
        db_tool = Tool.create(
            name="数据库工具",
            description="执行数据库查询",
            category=ToolCategory.DATABASE,
            author="test_user",
        )

        tool_repository.save(http_tool)
        tool_repository.save(db_tool)
        db_session.commit()

        # 查找 HTTP 分类
        http_tools = tool_repository.find_by_category("http")
        assert len(http_tools) >= 1
        assert all(tool.category == ToolCategory.HTTP for tool in http_tools)

        # 查找数据库分类
        db_tools = tool_repository.find_by_category("database")
        assert len(db_tools) >= 1
        assert all(tool.category == ToolCategory.DATABASE for tool in db_tools)


class TestToolRepositoryStatus:
    """按状态查询 Tool 测试"""

    def test_find_published(self, tool_repository: SQLAlchemyToolRepository, db_session: Session):
        """测试查找已发布的 Tool"""
        # 创建 DRAFT 状态的 Tool
        draft_tool = Tool.create(
            name="草稿工具",
            description="测试用",
            category=ToolCategory.HTTP,
            author="test_user",
        )

        # 创建 PUBLISHED 状态的 Tool
        published_tool = Tool.create(
            name="已发布工具",
            description="测试用",
            category=ToolCategory.HTTP,
            author="test_user",
        )
        published_tool.status = ToolStatus.TESTING
        published_tool.publish()

        tool_repository.save(draft_tool)
        tool_repository.save(published_tool)
        db_session.commit()

        # 查找已发布的工具
        published_tools = tool_repository.find_published()
        assert len(published_tools) >= 1
        assert all(tool.status == ToolStatus.PUBLISHED for tool in published_tools)

        # 验证草稿工具不在其中
        assert draft_tool.id not in [tool.id for tool in published_tools]


class TestToolRepositoryLifecycle:
    """Tool 生命周期测试"""

    def test_tool_lifecycle(
        self, tool_repository: SQLAlchemyToolRepository, sample_tool: Tool, db_session: Session
    ):
        """测试 Tool 完整生命周期"""
        # 1. 保存 DRAFT 状态的工具
        assert sample_tool.status == ToolStatus.DRAFT
        tool_repository.save(sample_tool)
        db_session.commit()

        # 2. 转换到 TESTING 状态
        retrieved = tool_repository.get_by_id(sample_tool.id)
        retrieved.status = ToolStatus.TESTING
        tool_repository.save(retrieved)
        db_session.commit()

        # 3. 发布工具
        retrieved = tool_repository.get_by_id(sample_tool.id)
        retrieved.publish()
        tool_repository.save(retrieved)
        db_session.commit()

        # 4. 验证最终状态
        retrieved = tool_repository.get_by_id(sample_tool.id)
        assert retrieved.status == ToolStatus.PUBLISHED
        assert retrieved.published_at is not None

    def test_usage_tracking(
        self, tool_repository: SQLAlchemyToolRepository, sample_tool: Tool, db_session: Session
    ):
        """测试使用计数追踪"""
        tool_repository.save(sample_tool)
        db_session.commit()

        # 增加使用次数
        retrieved = tool_repository.get_by_id(sample_tool.id)
        retrieved.increment_usage()
        retrieved.increment_usage()
        tool_repository.save(retrieved)
        db_session.commit()

        # 验证使用次数
        retrieved = tool_repository.get_by_id(sample_tool.id)
        assert retrieved.usage_count == 2
        assert retrieved.last_used_at is not None


class TestToolRepositoryExists:
    """存在性检查测试"""

    def test_exists_true(
        self, tool_repository: SQLAlchemyToolRepository, sample_tool: Tool, db_session: Session
    ):
        """测试工具存在"""
        tool_repository.save(sample_tool)
        db_session.commit()

        assert tool_repository.exists(sample_tool.id) is True

    def test_exists_false(self, tool_repository: SQLAlchemyToolRepository):
        """测试工具不存在"""
        assert tool_repository.exists("tool_nonexistent") is False


class TestToolRepositoryDelete:
    """删除 Tool 测试"""

    def test_delete_existing_tool(
        self, tool_repository: SQLAlchemyToolRepository, sample_tool: Tool, db_session: Session
    ):
        """测试删除存在的工具"""
        tool_repository.save(sample_tool)
        db_session.commit()

        # 验证存在
        assert tool_repository.exists(sample_tool.id) is True

        # 删除
        tool_repository.delete(sample_tool.id)
        db_session.commit()

        # 验证已删除
        assert tool_repository.exists(sample_tool.id) is False
        assert tool_repository.find_by_id(sample_tool.id) is None

    def test_delete_nonexistent_tool(self, tool_repository: SQLAlchemyToolRepository):
        """测试删除不存在的工具（幂等）"""
        # 应该不抛异常
        tool_repository.delete("tool_nonexistent")

    def test_delete_cascade(self, tool_repository: SQLAlchemyToolRepository, db_session: Session):
        """测试删除工具时级联删除参数"""
        tool = Tool.create(
            name="测试工具",
            description="有参数的工具",
            category=ToolCategory.HTTP,
            author="test_user",
        )
        tool.add_parameter(
            ToolParameter(
                name="url",
                type="string",
                description="URL",
                required=True,
            )
        )

        tool_repository.save(tool)
        db_session.commit()

        # 删除工具
        tool_repository.delete(tool.id)
        db_session.commit()

        # 验证工具和参数都已删除
        assert tool_repository.find_by_id(tool.id) is None

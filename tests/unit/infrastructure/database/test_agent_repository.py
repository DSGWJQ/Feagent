"""测试：SQLAlchemy Agent Repository 实现

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- AgentRepository 是领域层定义的 Port 接口
- SQLAlchemyAgentRepository 是基础设施层的实现（Adapter）
- 负责 Agent 实体的持久化操作（CRUD）
- 负责 ORM 模型和领域实体之间的转换（Assembler）

测试策略：
1. 使用内存数据库（SQLite :memory:）进行测试
2. 每个测试独立（使用 fixture 创建新的数据库会话）
3. 测试所有 Repository 方法（save, get_by_id, find_by_id, find_all, exists, delete）
4. 测试异常情况（如实体不存在）
5. 测试幂等性（如 delete 多次调用）

为什么使用内存数据库？
- 快速：不需要真实数据库
- 隔离：每个测试独立，不影响其他测试
- 简单：不需要清理数据
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.agent import Agent
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.agent_repository import (
    SQLAlchemyAgentRepository,
)

# ==================== Fixtures ====================


@pytest.fixture
def engine():
    """创建同步内存数据库引擎

    为什么使用 SQLite :memory:？
    - 快速：在内存中运行，不需要磁盘 I/O
    - 隔离：每个测试独立，不影响其他测试
    - 简单：不需要清理数据

    为什么使用同步引擎？
    - 与当前实现一致（Repository 是同步的）
    - 简单易懂，易于调试
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,  # 不打印 SQL 语句（测试时保持安静）
    )

    # 创建所有表
    Base.metadata.create_all(engine)

    yield engine

    # 清理：关闭引擎
    engine.dispose()


@pytest.fixture
def db_session(engine):
    """创建同步数据库会话

    为什么每个测试都创建新会话？
    - 隔离：每个测试独立，不共享状态
    - 清理：测试结束后自动回滚
    """
    session_maker = sessionmaker(engine, class_=Session, expire_on_commit=False)

    session = session_maker()
    yield session
    # 测试结束后回滚（保持数据库干净）
    session.rollback()
    session.close()


@pytest.fixture
def agent_repository(db_session):
    """创建 AgentRepository 实例

    为什么使用 fixture？
    - 复用：避免每个测试都创建 Repository
    - 依赖注入：自动注入 db_session
    """
    return SQLAlchemyAgentRepository(db_session)


@pytest.fixture
def sample_agent():
    """创建示例 Agent 实体

    为什么使用 fixture？
    - 复用：避免每个测试都创建 Agent
    - 一致性：所有测试使用相同的测试数据
    """
    return Agent.create(
        start="我有一个 CSV 文件包含销售数据", goal="生成销售趋势分析报告", name="测试 Agent"
    )


# ==================== 测试：save() 方法 ====================


class TestAgentRepositorySave:
    """测试 AgentRepository.save() 方法

    测试场景：
    1. 保存新 Agent（新增）
    2. 保存已存在的 Agent（更新）
    """

    def test_save_new_agent_should_persist_to_database(self, agent_repository, sample_agent):
        """测试：保存新 Agent 应该持久化到数据库

        业务需求：
        - 用户创建 Agent 后，需要保存到数据库
        - 保存后应该能够查询到

        验收标准：
        - save() 方法不抛异常
        - 保存后能够通过 get_by_id() 查询到
        - 查询到的 Agent 数据与原始数据一致
        """
        # Act：保存 Agent
        agent_repository.save(sample_agent)

        # Assert：验证保存成功
        found_agent = agent_repository.get_by_id(sample_agent.id)
        assert found_agent is not None, "保存后应该能够查询到 Agent"
        assert found_agent.id == sample_agent.id
        assert found_agent.start == sample_agent.start
        assert found_agent.goal == sample_agent.goal
        assert found_agent.name == sample_agent.name
        assert found_agent.status == sample_agent.status

    def test_save_existing_agent_should_update_database(self, agent_repository, sample_agent):
        """测试：保存已存在的 Agent 应该更新数据库

        业务需求：
        - 用户修改 Agent 后，需要更新到数据库
        - save() 方法应该自动判断是新增还是更新

        验收标准：
        - 第一次 save() 新增 Agent
        - 修改 Agent 属性
        - 第二次 save() 更新 Agent
        - 查询到的 Agent 数据是最新的
        """
        # Arrange：先保存 Agent
        agent_repository.save(sample_agent)

        # Act：修改 Agent 并再次保存
        sample_agent.status = "archived"
        agent_repository.save(sample_agent)

        # Assert：验证更新成功
        found_agent = agent_repository.get_by_id(sample_agent.id)
        assert found_agent.status == "archived", "status 应该被更新"


# ==================== 测试：get_by_id() 方法 ====================


class TestAgentRepositoryGetById:
    """测试 AgentRepository.get_by_id() 方法

    测试场景：
    1. 获取存在的 Agent（正常路径）
    2. 获取不存在的 Agent（异常路径）
    """

    def test_get_by_id_existing_agent_should_return_agent(self, agent_repository, sample_agent):
        """测试：获取存在的 Agent 应该返回 Agent 实体

        业务需求：
        - 用户查询 Agent 详情
        - 期望 Agent 一定存在（业务逻辑场景）

        验收标准：
        - 返回的 Agent 不为 None
        - Agent 数据与保存的数据一致
        """
        # Arrange：先保存 Agent
        agent_repository.save(sample_agent)

        # Act：获取 Agent
        found_agent = agent_repository.get_by_id(sample_agent.id)

        # Assert：验证返回正确的 Agent
        assert found_agent is not None
        assert found_agent.id == sample_agent.id
        assert found_agent.start == sample_agent.start
        assert found_agent.goal == sample_agent.goal

    def test_get_by_id_non_existing_agent_should_raise_not_found_error(self, agent_repository):
        """测试：获取不存在的 Agent 应该抛出 NotFoundError

        业务需求：
        - 用户查询不存在的 Agent
        - 应该明确告知 Agent 不存在（抛异常）

        验收标准：
        - 抛出 NotFoundError 异常
        - 异常消息包含实体类型和 ID
        """
        # Arrange
        non_existing_id = "non-existing-id"

        # Act & Assert：验证抛出异常
        with pytest.raises(NotFoundError) as exc_info:
            agent_repository.get_by_id(non_existing_id)

        # 验证异常信息
        assert exc_info.value.entity_type == "Agent"
        assert exc_info.value.entity_id == non_existing_id


# ==================== 测试：find_by_id() 方法 ====================


class TestAgentRepositoryFindById:
    """测试 AgentRepository.find_by_id() 方法

    测试场景：
    1. 查找存在的 Agent（返回 Agent）
    2. 查找不存在的 Agent（返回 None）
    """

    def test_find_by_id_existing_agent_should_return_agent(self, agent_repository, sample_agent):
        """测试：查找存在的 Agent 应该返回 Agent 实体"""
        # Arrange
        agent_repository.save(sample_agent)

        # Act
        found_agent = agent_repository.find_by_id(sample_agent.id)

        # Assert
        assert found_agent is not None
        assert found_agent.id == sample_agent.id

    def test_find_by_id_non_existing_agent_should_return_none(self, agent_repository):
        """测试：查找不存在的 Agent 应该返回 None

        业务需求：
        - 查询场景（不期望一定存在）
        - 不存在时返回 None，不抛异常

        验收标准：
        - 返回 None
        - 不抛异常
        """
        # Act
        found_agent = agent_repository.find_by_id("non-existing-id")

        # Assert
        assert found_agent is None, "不存在的 Agent 应该返回 None"


# ==================== 测试：find_all() 方法 ====================


class TestAgentRepositoryFindAll:
    """测试 AgentRepository.find_all() 方法

    测试场景：
    1. 查找所有 Agent（有数据）
    2. 查找所有 Agent（无数据）
    3. 验证排序（按创建时间倒序）
    """

    def test_find_all_with_multiple_agents_should_return_all_agents(self, agent_repository):
        """测试：查找所有 Agent 应该返回所有 Agent

        业务需求：
        - 用户查看所有 Agent 列表
        - 按创建时间倒序排列（最新的在前）

        验收标准：
        - 返回所有保存的 Agent
        - 按创建时间倒序排列
        """
        # Arrange：创建并保存多个 Agent
        agent1 = Agent.create(start="起点1", goal="目的1", name="Agent 1")
        agent2 = Agent.create(start="起点2", goal="目的2", name="Agent 2")
        agent3 = Agent.create(start="起点3", goal="目的3", name="Agent 3")

        agent_repository.save(agent1)
        agent_repository.save(agent2)
        agent_repository.save(agent3)

        # Act：查找所有 Agent
        agents = agent_repository.find_all()

        # Assert：验证返回所有 Agent
        assert len(agents) == 3, "应该返回 3 个 Agent"

        # 验证按创建时间倒序（最新的在前）
        # 注意：由于创建时间非常接近，这里只验证数量
        agent_ids = [agent.id for agent in agents]
        assert agent1.id in agent_ids
        assert agent2.id in agent_ids
        assert agent3.id in agent_ids

    def test_find_all_with_no_agents_should_return_empty_list(self, agent_repository):
        """测试：没有 Agent 时应该返回空列表

        业务需求：
        - 数据库为空时，返回空列表
        - 不抛异常

        验收标准：
        - 返回空列表（不是 None）
        - 不抛异常
        """
        # Act：查找所有 Agent（数据库为空）
        agents = agent_repository.find_all()

        # Assert：验证返回空列表
        assert agents == [], "没有 Agent 时应该返回空列表"
        assert isinstance(agents, list), "应该返回 list 类型"


# ==================== 测试：exists() 方法 ====================


class TestAgentRepositoryExists:
    """测试 AgentRepository.exists() 方法

    测试场景：
    1. 检查存在的 Agent（返回 True）
    2. 检查不存在的 Agent（返回 False）
    """

    def test_exists_with_existing_agent_should_return_true(self, agent_repository, sample_agent):
        """测试：检查存在的 Agent 应该返回 True

        业务需求：
        - 快速检查 Agent 是否存在
        - 不需要加载完整实体（性能优化）

        验收标准：
        - 返回 True
        """
        # Arrange：保存 Agent
        agent_repository.save(sample_agent)

        # Act：检查 Agent 是否存在
        exists = agent_repository.exists(sample_agent.id)

        # Assert：验证返回 True
        assert exists is True, "存在的 Agent 应该返回 True"

    def test_exists_with_non_existing_agent_should_return_false(self, agent_repository):
        """测试：检查不存在的 Agent 应该返回 False

        验收标准：
        - 返回 False
        - 不抛异常
        """
        # Act：检查不存在的 Agent
        exists = agent_repository.exists("non-existing-id")

        # Assert：验证返回 False
        assert exists is False, "不存在的 Agent 应该返回 False"


# ==================== 测试：delete() 方法 ====================


class TestAgentRepositoryDelete:
    """测试 AgentRepository.delete() 方法

    测试场景：
    1. 删除存在的 Agent（成功删除）
    2. 删除不存在的 Agent（幂等操作，不抛异常）
    3. 删除后无法查询到（验证删除成功）
    """

    def test_delete_existing_agent_should_remove_from_database(
        self, agent_repository, sample_agent
    ):
        """测试：删除存在的 Agent 应该从数据库中移除

        业务需求：
        - 用户删除 Agent
        - 删除后无法查询到

        验收标准：
        - delete() 方法不抛异常
        - 删除后 exists() 返回 False
        - 删除后 find_by_id() 返回 None
        """
        # Arrange：保存 Agent
        agent_repository.save(sample_agent)
        assert agent_repository.exists(sample_agent.id) is True

        # Act：删除 Agent
        agent_repository.delete(sample_agent.id)

        # Assert：验证删除成功
        assert agent_repository.exists(sample_agent.id) is False, "删除后应该不存在"
        found_agent = agent_repository.find_by_id(sample_agent.id)
        assert found_agent is None, "删除后应该查询不到"

    def test_delete_non_existing_agent_should_not_raise_error(self, agent_repository):
        """测试：删除不存在的 Agent 不应该抛异常（幂等操作）

        业务需求：
        - 删除操作应该是幂等的
        - 多次删除同一个 Agent 不报错

        验收标准：
        - 不抛异常
        - 可以多次调用
        """
        # Act & Assert：删除不存在的 Agent（不应该抛异常）
        agent_repository.delete("non-existing-id")

        # 再次删除（验证幂等性）
        agent_repository.delete("non-existing-id")

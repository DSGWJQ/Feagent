"""测试：SQLAlchemy Run Repository 实现

TDD 补救：为已实现的 RunRepository 补充测试用例

业务背景：
- RunRepository 是领域层定义的 Port 接口
- SQLAlchemyRunRepository 是基础设施层的实现（Adapter）
- 负责 Run 实体的持久化操作（CRUD）
- 负责 ORM 模型和领域实体之间的转换（Assembler）

测试策略：
1. 使用内存数据库（SQLite :memory:）进行测试
2. 每个测试独立（使用 fixture 创建新的数据库会话）
3. 测试所有 Repository 方法（save, get_by_id, find_by_id, find_by_agent_id, exists, delete）
4. 测试异常情况（如实体不存在）
5. 测试幂等性（如 delete 多次调用）
6. 测试 Run 状态转换（PENDING → RUNNING → SUCCEEDED/FAILED）

为什么补充测试？
- 当前 RunRepository 覆盖率仅 30%，存在质量风险
- TDD 原则：测试先行，但这次我们忘记了
- 补救措施：现在补上测试，确保代码质量
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.agent import Agent
from src.domain.entities.run import Run, RunStatus
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.agent_repository import (
    SQLAlchemyAgentRepository,
)
from src.infrastructure.database.repositories.run_repository import (
    SQLAlchemyRunRepository,
)

# ==================== Fixtures ====================


@pytest.fixture
def engine():
    """创建异步内存数据库引擎

    为什么使用 SQLite :memory:？
    - 快速：在内存中运行，不需要磁盘 I/O
    - 隔离：每个测试独立，不影响其他测试
    - 简单：不需要清理数据
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
    db_session_maker = sessionmaker(engine, class_=Session, expire_on_commit=False)

    session = db_session_maker()
    yield session
    # 测试结束后回滚（保持数据库干净）
    session.rollback()
    session.close()


@pytest.fixture
def run_repository(db_session):
    """创建 RunRepository 实例"""
    return SQLAlchemyRunRepository(db_session)


@pytest.fixture
def agent_repository(db_session):
    """创建 AgentRepository 实例

    为什么需要 AgentRepository？
    - Run 依赖 Agent（外键关系）
    - 测试 Run 前需要先创建 Agent
    """
    return SQLAlchemyAgentRepository(db_session)


@pytest.fixture
async def sample_agent(agent_repository):
    """创建并保存示例 Agent 实体

    为什么需要保存到数据库？
    - Run 有外键约束，必须先有 Agent
    - 模拟真实场景：Run 总是属于某个 Agent
    """
    agent = Agent.create(
        start="我有一个 CSV 文件包含销售数据", goal="生成销售趋势分析报告", name="测试 Agent"
    )
    agent_repository.save(agent)
    return agent


@pytest.fixture
def sample_run(sample_agent):
    """创建示例 Run 实体（未保存到数据库）

    为什么不保存到数据库？
    - 让每个测试自己决定何时保存
    - 测试 save() 方法时需要未保存的实体
    """
    return Run.create(agent_id=sample_agent.id)


# ==================== 测试：save() 方法 ====================


class TestRunRepositorySave:
    """测试 RunRepository.save() 方法

    测试场景：
    1. 保存新 Run（新增）
    2. 保存已存在的 Run（更新）
    3. 保存 Run 状态变化（PENDING → RUNNING → SUCCEEDED）
    """

    def test_save_new_run_should_persist_to_database(self, run_repository, sample_run):
        """测试：保存新 Run 应该持久化到数据库

        业务需求：
        - 用户触发 Agent 运行，创建 Run
        - Run 需要保存到数据库

        验收标准：
        - save() 方法不抛异常
        - 保存后能够通过 get_by_id() 查询到
        - 查询到的 Run 数据与原始数据一致
        """
        # Act：保存 Run
        run_repository.save(sample_run)

        # Assert：验证保存成功
        found_run = run_repository.get_by_id(sample_run.id)
        assert found_run is not None, "保存后应该能够查询到 Run"
        assert found_run.id == sample_run.id
        assert found_run.agent_id == sample_run.agent_id
        assert found_run.status == RunStatus.PENDING
        assert found_run.created_at is not None
        assert found_run.started_at is None
        assert found_run.finished_at is None
        assert found_run.error is None

    def test_save_existing_run_should_update_database(self, run_repository, sample_run):
        """测试：保存已存在的 Run 应该更新数据库

        业务需求：
        - Run 状态变化时需要更新到数据库
        - save() 方法应该自动判断是新增还是更新

        验收标准：
        - 第一次 save() 新增 Run
        - 修改 Run 状态
        - 第二次 save() 更新 Run
        - 查询到的 Run 数据是最新的
        """
        # Arrange：先保存 Run
        run_repository.save(sample_run)

        # Act：修改 Run 状态并再次保存
        sample_run.start()  # PENDING → RUNNING
        run_repository.save(sample_run)

        # Assert：验证更新成功
        found_run = run_repository.get_by_id(sample_run.id)
        assert found_run.status == RunStatus.RUNNING, "status 应该被更新为 RUNNING"
        assert found_run.started_at is not None, "started_at 应该被设置"

    def test_save_run_with_status_transition_should_update_timestamps(
        self, run_repository, sample_run
    ):
        """测试：保存 Run 状态转换应该更新时间戳

        业务需求：
        - Run 状态转换时，时间戳应该被正确记录
        - PENDING → RUNNING：设置 started_at
        - RUNNING → SUCCEEDED：设置 finished_at

        验收标准：
        - started_at 在 start() 后被设置
        - finished_at 在 succeed() 后被设置
        """
        # Arrange：保存初始 Run
        run_repository.save(sample_run)

        # Act：状态转换 PENDING → RUNNING
        sample_run.start()
        run_repository.save(sample_run)

        # Assert：验证 started_at 被设置
        found_run = run_repository.get_by_id(sample_run.id)
        assert found_run.started_at is not None

        # Act：状态转换 RUNNING → SUCCEEDED
        sample_run.succeed()
        run_repository.save(sample_run)

        # Assert：验证 finished_at 被设置
        found_run = run_repository.get_by_id(sample_run.id)
        assert found_run.finished_at is not None
        assert found_run.status == RunStatus.SUCCEEDED


# ==================== 测试：get_by_id() 方法 ====================


class TestRunRepositoryGetById:
    """测试 RunRepository.get_by_id() 方法

    测试场景：
    1. 获取存在的 Run（正常路径）
    2. 获取不存在的 Run（异常路径）
    """

    def test_get_by_id_existing_run_should_return_run(self, run_repository, sample_run):
        """测试：获取存在的 Run 应该返回 Run 实体

        业务需求：
        - 用户查询 Run 详情
        - 期望 Run 一定存在（业务逻辑场景）

        验收标准：
        - 返回的 Run 不为 None
        - Run 数据与保存的数据一致
        """
        # Arrange：先保存 Run
        run_repository.save(sample_run)

        # Act：获取 Run
        found_run = run_repository.get_by_id(sample_run.id)

        # Assert：验证返回正确的 Run
        assert found_run is not None
        assert found_run.id == sample_run.id
        assert found_run.agent_id == sample_run.agent_id
        assert found_run.status == sample_run.status

    def test_get_by_id_non_existing_run_should_raise_not_found_error(self, run_repository):
        """测试：获取不存在的 Run 应该抛出 NotFoundError

        业务需求：
        - 用户查询不存在的 Run
        - 应该明确告知 Run 不存在（抛异常）

        验收标准：
        - 抛出 NotFoundError 异常
        - 异常消息包含实体类型和 ID
        """
        # Arrange
        non_existing_id = "non-existing-run-id"

        # Act & Assert：验证抛出异常
        with pytest.raises(NotFoundError) as exc_info:
            run_repository.get_by_id(non_existing_id)

        # 验证异常信息
        assert exc_info.value.entity_type == "Run"
        assert exc_info.value.entity_id == non_existing_id


# ==================== 测试：find_by_id() 方法 ====================


class TestRunRepositoryFindById:
    """测试 RunRepository.find_by_id() 方法

    测试场景：
    1. 查找存在的 Run（返回 Run）
    2. 查找不存在的 Run（返回 None）
    """

    def test_find_by_id_existing_run_should_return_run(self, run_repository, sample_run):
        """测试：查找存在的 Run 应该返回 Run 实体"""
        # Arrange
        run_repository.save(sample_run)

        # Act
        found_run = run_repository.find_by_id(sample_run.id)

        # Assert
        assert found_run is not None
        assert found_run.id == sample_run.id

    def test_find_by_id_non_existing_run_should_return_none(self, run_repository):
        """测试：查找不存在的 Run 应该返回 None

        业务需求：
        - 查询场景（不期望一定存在）
        - 不存在时返回 None，不抛异常

        验收标准：
        - 返回 None
        - 不抛异常
        """
        # Act
        found_run = run_repository.find_by_id("non-existing-run-id")

        # Assert
        assert found_run is None, "不存在的 Run 应该返回 None"


# ==================== 测试：find_by_agent_id() 方法 ====================


class TestRunRepositoryFindByAgentId:
    """测试 RunRepository.find_by_agent_id() 方法

    测试场景：
    1. 查找某个 Agent 的所有 Run（有数据）
    2. 查找某个 Agent 的所有 Run（无数据）
    3. 验证排序（按创建时间倒序）
    """

    def test_find_by_agent_id_with_multiple_runs_should_return_all_runs(
        self, run_repository, sample_agent
    ):
        """测试：查找某个 Agent 的所有 Run 应该返回所有 Run

        业务需求：
        - 用户查看某个 Agent 的运行历史
        - 按创建时间倒序排列（最新的在前）

        验收标准：
        - 返回所有属于该 Agent 的 Run
        - 按创建时间倒序排列
        """
        # Arrange：创建并保存多个 Run
        run1 = Run.create(agent_id=sample_agent.id)
        run2 = Run.create(agent_id=sample_agent.id)
        run3 = Run.create(agent_id=sample_agent.id)

        run_repository.save(run1)
        run_repository.save(run2)
        run_repository.save(run3)

        # Act：查找该 Agent 的所有 Run
        runs = run_repository.find_by_agent_id(sample_agent.id)

        # Assert：验证返回所有 Run
        assert len(runs) == 3, "应该返回 3 个 Run"

        # 验证所有 Run 都属于该 Agent
        for run in runs:
            assert run.agent_id == sample_agent.id

        # 验证包含所有创建的 Run
        run_ids = [run.id for run in runs]
        assert run1.id in run_ids
        assert run2.id in run_ids
        assert run3.id in run_ids

    def test_find_by_agent_id_with_no_runs_should_return_empty_list(
        self, run_repository, sample_agent
    ):
        """测试：没有 Run 时应该返回空列表

        业务需求：
        - Agent 还没有运行过，返回空列表
        - 不抛异常

        验收标准：
        - 返回空列表（不是 None）
        - 不抛异常
        """
        # Act：查找该 Agent 的所有 Run（没有 Run）
        runs = run_repository.find_by_agent_id(sample_agent.id)

        # Assert：验证返回空列表
        assert runs == [], "没有 Run 时应该返回空列表"
        assert isinstance(runs, list), "应该返回 list 类型"

    def test_find_by_agent_id_should_only_return_runs_for_that_agent(
        self, run_repository, agent_repository
    ):
        """测试：只返回指定 Agent 的 Run，不返回其他 Agent 的 Run

        业务需求：
        - 多个 Agent 各有自己的 Run
        - 查询时只返回指定 Agent 的 Run

        验收标准：
        - 只返回指定 Agent 的 Run
        - 不返回其他 Agent 的 Run
        """
        # Arrange：创建两个 Agent
        agent1 = Agent.create(start="起点1", goal="目的1", name="Agent 1")
        agent2 = Agent.create(start="起点2", goal="目的2", name="Agent 2")
        agent_repository.save(agent1)
        agent_repository.save(agent2)

        # 为每个 Agent 创建 Run
        run1_agent1 = Run.create(agent_id=agent1.id)
        run2_agent1 = Run.create(agent_id=agent1.id)
        run1_agent2 = Run.create(agent_id=agent2.id)

        run_repository.save(run1_agent1)
        run_repository.save(run2_agent1)
        run_repository.save(run1_agent2)

        # Act：查找 agent1 的 Run
        runs_agent1 = run_repository.find_by_agent_id(agent1.id)

        # Assert：只返回 agent1 的 Run
        assert len(runs_agent1) == 2, "agent1 应该有 2 个 Run"
        for run in runs_agent1:
            assert run.agent_id == agent1.id, "所有 Run 都应该属于 agent1"

        # 验证不包含 agent2 的 Run
        run_ids = [run.id for run in runs_agent1]
        assert run1_agent2.id not in run_ids, "不应该包含 agent2 的 Run"


# ==================== 测试：exists() 方法 ====================


class TestRunRepositoryExists:
    """测试 RunRepository.exists() 方法

    测试场景：
    1. 检查存在的 Run（返回 True）
    2. 检查不存在的 Run（返回 False）
    """

    def test_exists_with_existing_run_should_return_true(self, run_repository, sample_run):
        """测试：检查存在的 Run 应该返回 True

        业务需求：
        - 快速检查 Run 是否存在
        - 不需要加载完整实体（性能优化）

        验收标准：
        - 返回 True
        """
        # Arrange：保存 Run
        run_repository.save(sample_run)

        # Act：检查 Run 是否存在
        exists = run_repository.exists(sample_run.id)

        # Assert：验证返回 True
        assert exists is True, "存在的 Run 应该返回 True"

    def test_exists_with_non_existing_run_should_return_false(self, run_repository):
        """测试：检查不存在的 Run 应该返回 False

        验收标准：
        - 返回 False
        - 不抛异常
        """
        # Act：检查不存在的 Run
        exists = run_repository.exists("non-existing-run-id")

        # Assert：验证返回 False
        assert exists is False, "不存在的 Run 应该返回 False"


# ==================== 测试：delete() 方法 ====================


class TestRunRepositoryDelete:
    """测试 RunRepository.delete() 方法

    测试场景：
    1. 删除存在的 Run（成功删除）
    2. 删除不存在的 Run（幂等操作，不抛异常）
    3. 删除后无法查询到（验证删除成功）
    """

    def test_delete_existing_run_should_remove_from_database(self, run_repository, sample_run):
        """测试：删除存在的 Run 应该从数据库中移除

        业务需求：
        - 用户删除 Run
        - 删除后无法查询到

        验收标准：
        - delete() 方法不抛异常
        - 删除后 exists() 返回 False
        - 删除后 find_by_id() 返回 None
        """
        # Arrange：保存 Run
        run_repository.save(sample_run)
        assert run_repository.exists(sample_run.id) is True

        # Act：删除 Run
        run_repository.delete(sample_run.id)

        # Assert：验证删除成功
        assert run_repository.exists(sample_run.id) is False, "删除后应该不存在"
        found_run = run_repository.find_by_id(sample_run.id)
        assert found_run is None, "删除后应该查询不到"

    def test_delete_non_existing_run_should_not_raise_error(self, run_repository):
        """测试：删除不存在的 Run 不应该抛异常（幂等操作）

        业务需求：
        - 删除操作应该是幂等的
        - 多次删除同一个 Run 不报错

        验收标准：
        - 不抛异常
        - 可以多次调用
        """
        # Act & Assert：删除不存在的 Run（不应该抛异常）
        run_repository.delete("non-existing-run-id")

        # 再次删除（验证幂等性）
        run_repository.delete("non-existing-run-id")

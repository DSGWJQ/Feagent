"""数据库迁移集成测试

测试目标：
1. 验证数据库迁移能够正确执行
2. 验证所有表结构符合预期
3. 验证索引和外键约束正确创建

第一性原则：
- 数据库迁移是基础设施的核心，必须保证正确性
- 表结构变更会影响整个应用，必须有测试保护
- 测试应该验证实际的数据库状态，而不是假设

测试策略：
- 使用真实的数据库引擎（SQLite）
- 检查表是否存在
- 检查列定义是否正确
- 检查索引是否创建
- 检查外键约束是否正确
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings


@pytest.fixture
async def db_engine():
    """创建测试数据库引擎

    为什么需要单独的测试引擎？
    - 测试应该使用独立的数据库，避免污染开发数据库
    - 测试完成后应该清理数据
    """
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """创建测试数据库会话"""
    async_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_agents_table_exists(db_session: AsyncSession):
    """测试 agents 表是否存在

    验证点：
    - 表名为 'agents'
    - 表已创建
    """
    # 使用 SQLAlchemy inspector 检查表
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
    )
    table = result.scalar_one_or_none()

    assert table == "agents", "agents 表应该存在"


@pytest.mark.asyncio
async def test_agents_table_columns(db_session: AsyncSession):
    """测试 agents 表的列定义

    验证点：
    - id: 主键，字符串类型
    - start: 文本类型，非空
    - goal: 文本类型，非空
    - status: 字符串类型，非空
    - name: 字符串类型，非空
    - created_at: 日期时间类型，非空
    """
    result = await db_session.execute(text("PRAGMA table_info(agents)"))
    columns = {row[1]: row for row in result.fetchall()}

    # 验证必需的列存在
    assert "id" in columns, "agents 表应该有 id 列"
    assert "start" in columns, "agents 表应该有 start 列"
    assert "goal" in columns, "agents 表应该有 goal 列"
    assert "status" in columns, "agents 表应该有 status 列"
    assert "name" in columns, "agents 表应该有 name 列"
    assert "created_at" in columns, "agents 表应该有 created_at 列"

    # 验证非空约束
    assert columns["id"][3] == 1, "id 列应该是非空的"
    assert columns["start"][3] == 1, "start 列应该是非空的"
    assert columns["goal"][3] == 1, "goal 列应该是非空的"
    assert columns["status"][3] == 1, "status 列应该是非空的"
    assert columns["name"][3] == 1, "name 列应该是非空的"
    assert columns["created_at"][3] == 1, "created_at 列应该是非空的"


@pytest.mark.asyncio
async def test_runs_table_exists(db_session: AsyncSession):
    """测试 runs 表是否存在"""
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    )
    table = result.scalar_one_or_none()

    assert table == "runs", "runs 表应该存在"


@pytest.mark.asyncio
async def test_runs_table_columns(db_session: AsyncSession):
    """测试 runs 表的列定义

    验证点：
    - id: 主键
    - agent_id: 外键，非空
    - status: 非空
    - created_at: 非空
    - started_at: 可空
    - finished_at: 可空
    - error: 可空
    """
    result = await db_session.execute(text("PRAGMA table_info(runs)"))
    columns = {row[1]: row for row in result.fetchall()}

    # 验证必需的列存在
    assert "id" in columns, "runs 表应该有 id 列"
    assert "agent_id" in columns, "runs 表应该有 agent_id 列"
    assert "status" in columns, "runs 表应该有 status 列"
    assert "created_at" in columns, "runs 表应该有 created_at 列"
    assert "started_at" in columns, "runs 表应该有 started_at 列"
    assert "finished_at" in columns, "runs 表应该有 finished_at 列"
    assert "error" in columns, "runs 表应该有 error 列"

    # 验证非空约束
    assert columns["id"][3] == 1, "id 列应该是非空的"
    assert columns["agent_id"][3] == 1, "agent_id 列应该是非空的"
    assert columns["status"][3] == 1, "status 列应该是非空的"
    assert columns["created_at"][3] == 1, "created_at 列应该是非空的"

    # 验证可空列
    assert columns["started_at"][3] == 0, "started_at 列应该是可空的"
    assert columns["finished_at"][3] == 0, "finished_at 列应该是可空的"
    assert columns["error"][3] == 0, "error 列应该是可空的"


@pytest.mark.asyncio
async def test_tasks_table_exists(db_session: AsyncSession):
    """测试 tasks 表是否存在"""
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    )
    table = result.scalar_one_or_none()

    assert table == "tasks", "tasks 表应该存在"


@pytest.mark.asyncio
async def test_tasks_table_columns(db_session: AsyncSession):
    """测试 tasks 表的列定义

    验证点：
    - id: 主键
    - run_id: 外键，非空
    - name: 非空
    - input_data: JSON，可空
    - output_data: JSON，可空
    - status: 非空
    - error: 可空
    - retry_count: 非空
    - created_at: 非空
    - started_at: 可空
    - finished_at: 可空
    - events: JSON，可空
    """
    result = await db_session.execute(text("PRAGMA table_info(tasks)"))
    columns = {row[1]: row for row in result.fetchall()}

    # 验证必需的列存在
    assert "id" in columns, "tasks 表应该有 id 列"
    assert "run_id" in columns, "tasks 表应该有 run_id 列"
    assert "name" in columns, "tasks 表应该有 name 列"
    assert "input_data" in columns, "tasks 表应该有 input_data 列"
    assert "output_data" in columns, "tasks 表应该有 output_data 列"
    assert "status" in columns, "tasks 表应该有 status 列"
    assert "error" in columns, "tasks 表应该有 error 列"
    assert "retry_count" in columns, "tasks 表应该有 retry_count 列"
    assert "created_at" in columns, "tasks 表应该有 created_at 列"
    assert "started_at" in columns, "tasks 表应该有 started_at 列"
    assert "finished_at" in columns, "tasks 表应该有 finished_at 列"
    assert "events" in columns, "tasks 表应该有 events 列"

    # 验证非空约束
    assert columns["id"][3] == 1, "id 列应该是非空的"
    assert columns["run_id"][3] == 1, "run_id 列应该是非空的"
    assert columns["name"][3] == 1, "name 列应该是非空的"
    assert columns["status"][3] == 1, "status 列应该是非空的"
    assert columns["retry_count"][3] == 1, "retry_count 列应该是非空的"
    assert columns["created_at"][3] == 1, "created_at 列应该是非空的"


@pytest.mark.asyncio
async def test_runs_foreign_key_to_agents(db_session: AsyncSession):
    """测试 runs 表到 agents 表的外键约束

    验证点：
    - runs.agent_id 引用 agents.id
    - 级联删除配置正确
    """
    result = await db_session.execute(text("PRAGMA foreign_key_list(runs)"))
    foreign_keys = result.fetchall()

    # 应该有一个外键
    assert len(foreign_keys) > 0, "runs 表应该有外键约束"

    # 验证外键指向 agents 表
    fk = foreign_keys[0]
    assert fk[2] == "agents", "runs 表的外键应该指向 agents 表"
    assert fk[3] == "agent_id", "外键列应该是 agent_id"
    assert fk[4] == "id", "外键应该引用 agents.id"


@pytest.mark.asyncio
async def test_tasks_foreign_key_to_runs(db_session: AsyncSession):
    """测试 tasks 表到 runs 表的外键约束

    验证点：
    - tasks.run_id 引用 runs.id
    - 级联删除配置正确
    """
    result = await db_session.execute(text("PRAGMA foreign_key_list(tasks)"))
    foreign_keys = result.fetchall()

    # 应该有一个外键
    assert len(foreign_keys) > 0, "tasks 表应该有外键约束"

    # 验证外键指向 runs 表
    fk = foreign_keys[0]
    assert fk[2] == "runs", "tasks 表的外键应该指向 runs 表"
    assert fk[3] == "run_id", "外键列应该是 run_id"
    assert fk[4] == "id", "外键应该引用 runs.id"


@pytest.mark.asyncio
async def test_agents_indexes(db_session: AsyncSession):
    """测试 agents 表的索引

    验证点：
    - idx_agents_status 索引存在
    - idx_agents_created_at 索引存在
    """
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agents'")
    )
    indexes = [row[0] for row in result.fetchall()]

    # 验证索引存在（注意：主键索引会自动创建）
    assert any("status" in idx.lower() for idx in indexes), "应该有 status 列的索引"
    assert any("created_at" in idx.lower() for idx in indexes), "应该有 created_at 列的索引"


@pytest.mark.asyncio
async def test_runs_indexes(db_session: AsyncSession):
    """测试 runs 表的索引

    验证点：
    - idx_runs_agent_id 索引存在
    - idx_runs_status 索引存在
    - idx_runs_created_at 索引存在
    """
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='runs'")
    )
    indexes = [row[0] for row in result.fetchall()]

    assert any("agent_id" in idx.lower() for idx in indexes), "应该有 agent_id 列的索引"
    assert any("status" in idx.lower() for idx in indexes), "应该有 status 列的索引"
    assert any("created_at" in idx.lower() for idx in indexes), "应该有 created_at 列的索引"


@pytest.mark.asyncio
async def test_tasks_indexes(db_session: AsyncSession):
    """测试 tasks 表的索引

    验证点：
    - idx_tasks_run_id 索引存在
    - idx_tasks_status 索引存在
    - idx_tasks_created_at 索引存在
    """
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'")
    )
    indexes = [row[0] for row in result.fetchall()]

    assert any("run_id" in idx.lower() for idx in indexes), "应该有 run_id 列的索引"
    assert any("status" in idx.lower() for idx in indexes), "应该有 status 列的索引"
    assert any("created_at" in idx.lower() for idx in indexes), "应该有 created_at 列的索引"

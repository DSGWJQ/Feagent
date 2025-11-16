"""测试：SQLAlchemy Task Repository 实现

TDD 实践：先写测试，再写实现

业务背景：
- TaskRepository 是领域层定义的 Port 接口
- SQLAlchemyTaskRepository 是基础设施层的实现（Adapter）
- 负责 Task 实体的持久化操作（CRUD）
- 负责 ORM 模型和领域实体之间的转换（Assembler）
- Task 是聚合根，TaskEvent 是聚合内的值对象

测试策略：
1. 使用内存数据库（SQLite :memory:）进行测试
2. 每个测试独立（使用 fixture 创建新的数据库会话）
3. 测试所有 Repository 方法（save, get_by_id, find_by_id, find_by_run_id, exists, delete）
4. 测试异常情况（如实体不存在）
5. 测试幂等性（如 delete 多次调用）
6. 测试 Task 状态转换（PENDING → RUNNING → SUCCEEDED/FAILED）
7. 测试 TaskEvent 的持久化（作为 Task 聚合的一部分）

为什么先写测试？
- TDD 原则：测试驱动开发，先定义行为，再实现功能
- 明确需求：测试用例就是需求文档
- 快速反馈：实现代码时可以立即验证是否正确
- 防止遗漏：确保所有功能都有测试覆盖
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.agent import Agent
from src.domain.entities.run import Run
from src.domain.entities.task import Task, TaskStatus
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.agent_repository import (
    SQLAlchemyAgentRepository,
)
from src.infrastructure.database.repositories.run_repository import (
    SQLAlchemyRunRepository,
)
from src.infrastructure.database.repositories.task_repository import (
    SQLAlchemyTaskRepository,
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
        echo=False,  # 不打印 SQL 语句
    )

    # 创建所有表
    Base.metadata.create_all(engine)

    yield engine

    # 清理
    engine.dispose()


@pytest.fixture
def db_session_maker(engine):
    """创建同步会话工厂

    为什么需要 session_maker？
    - 每个测试需要独立的会话
    - 避免会话之间的数据污染
    """
    return sessionmaker(engine, class_=Session, expire_on_commit=False)


@pytest.fixture
def session(db_session_maker):
    """创建同步会话

    为什么使用 fixture？
    - 自动管理会话生命周期
    - 测试结束后自动关闭会话
    """
    session = db_session_maker()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def agent_repository(session):
    """创建 AgentRepository 实例"""
    return SQLAlchemyAgentRepository(session)


@pytest.fixture
def run_repository(session):
    """创建 RunRepository 实例"""
    return SQLAlchemyRunRepository(session)


@pytest.fixture
def task_repository(session):
    """创建 TaskRepository 实例"""
    return SQLAlchemyTaskRepository(session)


@pytest.fixture
async def sample_agent(agent_repository):
    """创建并保存示例 Agent 实体

    为什么需要保存到数据库？
    - Run 有外键约束，必须先有 Agent
    - Task 有外键约束，必须先有 Run
    """
    agent = Agent.create(
        start="我想学习 Python",
        goal="掌握 Python 基础语法",
        name="Python 学习助手",
    )
    agent_repository.save(agent)
    return agent


@pytest.fixture
async def sample_run(run_repository, sample_agent):
    """创建并保存示例 Run 实体

    为什么需要保存到数据库？
    - Task 有外键约束，必须先有 Run
    """
    run = Run.create(agent_id=sample_agent.id)
    run_repository.save(run)
    return run


@pytest.fixture
def sample_task(sample_run):
    """创建示例 Task 实体（未保存到数据库）

    为什么不保存到数据库？
    - 每个测试可能需要不同的 Task 状态
    - 让测试更灵活
    """
    return Task.create(
        run_id=sample_run.id,
        name="学习 Python 变量",
        input_data={"topic": "variables"},
    )


# ==================== 测试：save() ====================


class TestTaskRepositorySave:
    """测试：TaskRepository.save() 方法

    测试场景：
    1. 保存新 Task（INSERT）
    2. 更新已存在的 Task（UPDATE）
    3. 保存 Task 状态转换（PENDING → RUNNING → SUCCEEDED）
    4. 保存 Task 的 TaskEvent（聚合内的值对象）
    """

    def test_save_new_task_should_insert_to_database(self, task_repository, sample_task):
        """测试：保存新 Task 应该插入到数据库

        验收标准：
        - 调用 save() 后，数据库中有一条记录
        - 可以通过 get_by_id() 读取
        - 所有字段值正确
        """
        # Arrange - 准备数据（sample_task 已创建）

        # Act - 执行操作
        task_repository.save(sample_task)

        # Assert - 验证结果
        retrieved_task = task_repository.get_by_id(sample_task.id)
        assert retrieved_task.id == sample_task.id
        assert retrieved_task.run_id == sample_task.run_id
        assert retrieved_task.name == sample_task.name
        assert retrieved_task.status == TaskStatus.PENDING
        assert retrieved_task.input_data == {"topic": "variables"}
        assert retrieved_task.output_data is None
        assert retrieved_task.error is None
        assert retrieved_task.retry_count == 0
        assert retrieved_task.created_at is not None
        assert retrieved_task.started_at is None
        assert retrieved_task.finished_at is None
        assert retrieved_task.events == []  # 初始没有事件

    def test_save_existing_task_should_update_in_database(self, task_repository, sample_task):
        """测试：保存已存在的 Task 应该更新数据库

        验收标准：
        - 第一次 save() 插入记录
        - 修改 Task 后再次 save() 更新记录
        - 数据库中只有一条记录
        - 字段值已更新
        """
        # Arrange - 先保存
        task_repository.save(sample_task)

        # Act - 修改并再次保存
        sample_task.start()
        task_repository.save(sample_task)

        # Assert - 验证更新
        retrieved_task = task_repository.get_by_id(sample_task.id)
        assert retrieved_task.status == TaskStatus.RUNNING
        assert retrieved_task.started_at is not None

    def test_save_task_with_state_transition_should_update_timestamps(
        self, task_repository, sample_task
    ):
        """测试：保存状态转换的 Task 应该更新时间戳

        验收标准：
        - PENDING → RUNNING：started_at 被设置
        - RUNNING → SUCCEEDED：finished_at 被设置
        - 时间戳正确保存到数据库
        """
        # Arrange - 保存初始状态
        task_repository.save(sample_task)

        # Act - 状态转换：PENDING → RUNNING
        sample_task.start()
        task_repository.save(sample_task)

        # Assert - 验证 started_at
        retrieved_task = task_repository.get_by_id(sample_task.id)
        assert retrieved_task.status == TaskStatus.RUNNING
        assert retrieved_task.started_at is not None
        assert retrieved_task.finished_at is None

        # Act - 状态转换：RUNNING → SUCCEEDED
        sample_task.succeed(output_data={"result": "success"})
        task_repository.save(sample_task)

        # Assert - 验证 finished_at
        retrieved_task = task_repository.get_by_id(sample_task.id)
        assert retrieved_task.status == TaskStatus.SUCCEEDED
        assert retrieved_task.finished_at is not None
        assert retrieved_task.output_data == {"result": "success"}

    def test_save_task_with_events_should_persist_events(self, task_repository, sample_task):
        """测试：保存带有 TaskEvent 的 Task 应该持久化事件

        验收标准：
        - Task 添加事件后保存
        - 从数据库读取的 Task 包含事件
        - 事件的 timestamp 和 message 正确
        - 事件顺序正确（按添加顺序）

        为什么测试 TaskEvent？
        - TaskEvent 是值对象，属于 Task 聚合
        - 持久化 Task 时必须同时持久化 TaskEvent
        - 验证聚合的完整性
        """
        # Arrange - 添加事件
        sample_task.add_event("开始执行任务")
        sample_task.start()
        sample_task.add_event("正在处理数据")
        task_repository.save(sample_task)

        # Act - 从数据库读取
        retrieved_task = task_repository.get_by_id(sample_task.id)

        # Assert - 验证事件
        assert len(retrieved_task.events) == 2
        assert retrieved_task.events[0].message == "开始执行任务"
        assert retrieved_task.events[1].message == "正在处理数据"
        assert retrieved_task.events[0].timestamp < retrieved_task.events[1].timestamp


# ==================== 测试：get_by_id() ====================


class TestTaskRepositoryGetById:
    """测试：TaskRepository.get_by_id() 方法

    测试场景：
    1. 获取存在的 Task
    2. 获取不存在的 Task（抛异常）
    """

    def test_get_by_id_with_existing_task_should_return_task(self, task_repository, sample_task):
        """测试：获取存在的 Task 应该返回 Task 实体

        验收标准：
        - 返回的 Task 与保存的 Task 一致
        - 所有字段值正确
        """
        # Arrange
        task_repository.save(sample_task)

        # Act
        retrieved_task = task_repository.get_by_id(sample_task.id)

        # Assert
        assert retrieved_task.id == sample_task.id
        assert retrieved_task.name == sample_task.name

    def test_get_by_id_with_non_existing_task_should_raise_not_found_error(self, task_repository):
        """测试：获取不存在的 Task 应该抛出 NotFoundError

        验收标准：
        - 抛出 NotFoundError 异常
        - 异常消息包含 Task ID

        为什么抛异常？
        - get 语义表示"期望存在"
        - 不存在是异常情况
        """
        # Arrange
        non_existing_id = "non-existing-task-id"

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            task_repository.get_by_id(non_existing_id)

        assert "Task" in str(exc_info.value)
        assert non_existing_id in str(exc_info.value)


# ==================== 测试：find_by_id() ====================


class TestTaskRepositoryFindById:
    """测试：TaskRepository.find_by_id() 方法

    测试场景：
    1. 查找存在的 Task
    2. 查找不存在的 Task（返回 None）
    """

    def test_find_by_id_with_existing_task_should_return_task(self, task_repository, sample_task):
        """测试：查找存在的 Task 应该返回 Task 实体"""
        # Arrange
        task_repository.save(sample_task)

        # Act
        found_task = task_repository.find_by_id(sample_task.id)

        # Assert
        assert found_task is not None
        assert found_task.id == sample_task.id

    def test_find_by_id_with_non_existing_task_should_return_none(self, task_repository):
        """测试：查找不存在的 Task 应该返回 None

        为什么返回 None？
        - find 语义表示"可能不存在"
        - 不存在不是异常情况
        """
        # Arrange
        non_existing_id = "non-existing-task-id"

        # Act
        found_task = task_repository.find_by_id(non_existing_id)

        # Assert
        assert found_task is None


# ==================== 测试：find_by_run_id() ====================


class TestTaskRepositoryFindByRunId:
    """测试：TaskRepository.find_by_run_id() 方法

    测试场景：
    1. 查找 Run 的所有 Task（多个 Task）
    2. 查找 Run 的所有 Task（空列表）
    3. 验证返回顺序（按 created_at 倒序）
    4. 验证隔离性（不同 Run 的 Task 不混淆）
    """

    def test_find_by_run_id_with_multiple_tasks_should_return_all_tasks(
        self, task_repository, sample_run
    ):
        """测试：查找 Run 的所有 Task 应该返回所有 Task

        验收标准：
        - 返回所有属于该 Run 的 Task
        - 按 created_at 倒序排列（最新的在前）
        """
        # Arrange - 创建 3 个 Task
        task1 = Task.create(run_id=sample_run.id, name="任务 1")
        task2 = Task.create(run_id=sample_run.id, name="任务 2")
        task3 = Task.create(run_id=sample_run.id, name="任务 3")

        task_repository.save(task1)
        task_repository.save(task2)
        task_repository.save(task3)

        # Act
        tasks = task_repository.find_by_run_id(sample_run.id)

        # Assert
        assert len(tasks) == 3
        # 验证顺序（最新的在前）
        assert tasks[0].name == "任务 3"
        assert tasks[1].name == "任务 2"
        assert tasks[2].name == "任务 1"

    def test_find_by_run_id_with_no_tasks_should_return_empty_list(
        self, task_repository, sample_run
    ):
        """测试：查找没有 Task 的 Run 应该返回空列表

        验收标准：
        - 返回空列表（不抛异常）
        """
        # Arrange - 不创建 Task

        # Act
        tasks = task_repository.find_by_run_id(sample_run.id)

        # Assert
        assert tasks == []

    def test_find_by_run_id_should_not_return_other_run_tasks(
        self, task_repository, run_repository, sample_agent
    ):
        """测试：查找 Run 的 Task 应该隔离（不返回其他 Run 的 Task）

        验收标准：
        - 只返回指定 Run 的 Task
        - 不返回其他 Run 的 Task

        为什么测试隔离性？
        - 防止 SQL 查询错误（如忘记 WHERE 条件）
        - 确保数据安全
        """
        # Arrange - 创建两个 Run
        run1 = Run.create(agent_id=sample_agent.id)
        run2 = Run.create(agent_id=sample_agent.id)
        run_repository.save(run1)
        run_repository.save(run2)

        # 为 run1 创建 Task
        task1 = Task.create(run_id=run1.id, name="Run1 的任务")
        task_repository.save(task1)

        # 为 run2 创建 Task
        task2 = Task.create(run_id=run2.id, name="Run2 的任务")
        task_repository.save(task2)

        # Act - 查询 run1 的 Task
        tasks = task_repository.find_by_run_id(run1.id)

        # Assert - 只返回 run1 的 Task
        assert len(tasks) == 1
        assert tasks[0].id == task1.id
        assert tasks[0].name == "Run1 的任务"


# ==================== 测试：exists() ====================


class TestTaskRepositoryExists:
    """测试：TaskRepository.exists() 方法

    测试场景：
    1. 检查存在的 Task
    2. 检查不存在的 Task
    """

    def test_exists_with_existing_task_should_return_true(self, task_repository, sample_task):
        """测试：检查存在的 Task 应该返回 True"""
        # Arrange
        task_repository.save(sample_task)

        # Act
        exists = task_repository.exists(sample_task.id)

        # Assert
        assert exists is True

    def test_exists_with_non_existing_task_should_return_false(self, task_repository):
        """测试：检查不存在的 Task 应该返回 False"""
        # Arrange
        non_existing_id = "non-existing-task-id"

        # Act
        exists = task_repository.exists(non_existing_id)

        # Assert
        assert exists is False


# ==================== 测试：delete() ====================


class TestTaskRepositoryDelete:
    """测试：TaskRepository.delete() 方法

    测试场景：
    1. 删除存在的 Task
    2. 删除不存在的 Task（幂等性）
    """

    def test_delete_existing_task_should_remove_from_database(self, task_repository, sample_task):
        """测试：删除存在的 Task 应该从数据库中移除

        验收标准：
        - 删除后，exists() 返回 False
        - 删除后，find_by_id() 返回 None
        """
        # Arrange
        task_repository.save(sample_task)
        assert task_repository.exists(sample_task.id)

        # Act
        task_repository.delete(sample_task.id)

        # Assert
        assert not task_repository.exists(sample_task.id)
        assert task_repository.find_by_id(sample_task.id) is None

    def test_delete_non_existing_task_should_not_raise_error(self, task_repository):
        """测试：删除不存在的 Task 不应该抛出异常（幂等性）

        验收标准：
        - 不抛出异常
        - 可以多次调用 delete()

        为什么幂等？
        - 删除操作应该是幂等的
        - 避免调用方需要先检查是否存在
        """
        # Arrange
        non_existing_id = "non-existing-task-id"

        # Act & Assert - 不抛异常
        task_repository.delete(non_existing_id)
        task_repository.delete(non_existing_id)  # 第二次调用也不抛异常

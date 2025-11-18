"""测试：Task 实体

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- Task 是 Run 中的单个执行步骤
- 一个 Run 包含多个 Task（如：分析数据、生成报告、发送邮件）
- Task 有明确的生命周期：PENDING → RUNNING → SUCCEEDED/FAILED
- Task 支持重试、超时、幂等
- Task 记录执行事件（TaskEvent）用于审计和调试

第一性原理：
1. Task 是什么？
   - Task 是 Run 的组成部分，代表一个原子操作
   - Task 是可重试的（失败后可以重新执行）
   - Task 是可观测的（记录所有执行事件）

2. Task 的核心职责：
   - 维护状态（PENDING/RUNNING/SUCCEEDED/FAILED）
   - 记录执行历史（TaskEvent 列表）
   - 支持重试逻辑（retry_count）
   - 记录时间戳（created_at/started_at/finished_at）

3. Task 与 Run 的关系：
   - Task 属于 Run（外键关系）
   - Run 的状态依赖 Task 的状态（所有 Task 成功 → Run 成功）
   - Task 失败不一定导致 Run 失败（可以重试）

测试策略：
1. 测试 Task 创建（正常路径 + 异常路径）
2. 测试 Task 状态转换（PENDING → RUNNING → SUCCEEDED/FAILED）
3. 测试 Task 事件记录（add_event）
4. 测试 Task 重试逻辑（increment_retry_count）
5. 测试边界情况（空字符串、None、重复操作）
"""

from datetime import datetime

import pytest

from src.domain.entities.task import Task, TaskStatus
from src.domain.exceptions import DomainError


class TestTaskCreation:
    """测试 Task 创建

    测试场景：
    1. 使用有效参数创建 Task（正常路径）
    2. 使用空 run_id 创建 Task（异常路径）
    3. 使用空 name 创建 Task（异常路径）
    4. 创建多个 Task 应该有唯一 ID
    """

    def test_create_task_with_valid_parameters_should_succeed(self):
        """测试：使用有效参数创建 Task 应该成功

        业务需求：
        - Task 必须关联一个 Agent
        - Task 可以关联一个 Run（执行时）
        - Task 必须有名称（描述这个任务是什么）
        - Task 可以有描述（详细说明）
        - Task 可以有输入数据（input_data）

        验收标准：
        - Task 必须有唯一 ID
        - agent_id 必须被正确保存
        - run_id 可以为 None（还没执行）
        - name 必须被正确保存
        - description 可以为 None
        - 默认状态为 PENDING
        - retry_count 初始为 0
        - 记录创建时间
        - started_at 和 finished_at 初始为 None
        - error 初始为 None
        - events 初始为空列表
        """
        # Arrange
        agent_id = "test-agent-123"
        run_id = "test-run-456"
        name = "分析销售数据"
        description = "使用 pandas 读取 CSV 文件并计算销售总额"
        input_data = {"file_path": "/data/sales.csv"}

        # Act
        task = Task.create(
            agent_id=agent_id,
            name=name,
            description=description,
            run_id=run_id,
            input_data=input_data,
        )

        # Assert
        assert task.id is not None, "Task 必须有唯一 ID"
        assert task.agent_id == agent_id, "agent_id 必须被正确保存"
        assert task.run_id == run_id, "run_id 必须被正确保存"
        assert task.name == name, "name 必须被正确保存"
        assert task.description == description, "description 必须被正确保存"
        assert task.input_data == input_data, "input_data 必须被正确保存"
        assert task.status == TaskStatus.PENDING, "默认状态应该是 PENDING"
        assert task.retry_count == 0, "retry_count 初始应该为 0"
        assert task.created_at is not None, "必须记录创建时间"
        assert isinstance(task.created_at, datetime), "创建时间必须是 datetime 类型"
        assert task.started_at is None, "started_at 初始应该为 None"
        assert task.finished_at is None, "finished_at 初始应该为 None"
        assert task.error is None, "error 初始应该为 None"
        assert task.output_data is None, "output_data 初始应该为 None"
        assert task.events == [], "events 初始应该为空列表"

    def test_create_task_without_input_data_should_succeed(self):
        """测试：不提供 input_data 创建 Task 应该成功

        业务需求：
        - 有些 Task 不需要输入数据（如：发送通知）
        - input_data 应该是可选的

        验收标准：
        - Task 创建成功
        - input_data 为 None
        """
        # Act
        task = Task.create(agent_id="test-agent-123", name="发送通知")

        # Assert
        assert task.input_data is None, "不提供 input_data 时应该为 None"

    def test_create_task_with_empty_agent_id_should_raise_error(self):
        """测试：使用空的 agent_id 创建 Task 应该抛出错误

        业务规则：
        - agent_id 是必需的，不能为空
        - Task 必须属于某个 Agent

        为什么需要这个测试？
        1. 防止孤儿 Task：Task 必须关联 Agent
        2. 符合 DDD 规范：实体必须维护不变式
        3. 数据完整性：确保 Task 和 Agent 的关联关系

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "agent_id 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="agent_id 不能为空"):
            Task.create(agent_id="", name="测试任务")

    def test_create_task_with_whitespace_agent_id_should_raise_error(self):
        """测试：使用纯空格的 agent_id 创建 Task 应该抛出错误

        业务规则：
        - agent_id 不能是纯空格
        - 防止用户输入无意义的空白字符

        验收标准：
        - 抛出 DomainError 异常
        """
        # Act & Assert
        with pytest.raises(DomainError, match="agent_id 不能为空"):
            Task.create(agent_id="   ", name="测试任务")

    def test_create_task_with_empty_name_should_raise_error(self):
        """测试：使用空的 name 创建 Task 应该抛出错误

        业务规则：
        - name 是必需的，不能为空
        - name 用于描述 Task 的用途

        为什么需要这个测试？
        1. 可读性：Task 必须有清晰的名称
        2. 可维护性：便于调试和日志记录
        3. 业务语义：Task 名称是业务逻辑的一部分

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "name 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="name 不能为空"):
            Task.create(agent_id="test-agent-123", name="")

    def test_create_task_with_whitespace_name_should_raise_error(self):
        """测试：使用纯空格的 name 创建 Task 应该抛出错误

        业务规则：
        - name 不能是纯空格
        - 防止用户输入无意义的空白字符

        验收标准：
        - 抛出 DomainError 异常
        """
        # Act & Assert
        with pytest.raises(DomainError, match="name 不能为空"):
            Task.create(agent_id="test-agent-123", name="   ")

    def test_create_multiple_tasks_should_have_unique_ids(self):
        """测试：创建多个 Task 应该有唯一的 ID

        业务规则：
        - 每个 Task 必须有全局唯一的 ID
        - 使用 UUID 保证唯一性

        为什么需要这个测试？
        1. 防止 ID 冲突：确保每个 Task 可以被唯一标识
        2. 分布式友好：UUID 可以在分布式系统中生成
        3. 数据库主键：ID 作为数据库主键

        验收标准：
        - 多个 Task 的 ID 不相同
        """
        # Act
        task1 = Task.create(agent_id="test-agent-123", name="任务1")
        task2 = Task.create(agent_id="test-agent-123", name="任务2")
        task3 = Task.create(agent_id="test-agent-123", name="任务3")

        # Assert
        assert task1.id != task2.id, "Task ID 必须唯一"
        assert task1.id != task3.id, "Task ID 必须唯一"
        assert task2.id != task3.id, "Task ID 必须唯一"

    def test_create_task_should_trim_whitespace_from_name(self):
        """测试：创建 Task 应该去除 name 的首尾空格

        业务规则：
        - 自动去除用户输入的首尾空格
        - 提升用户体验（容错）

        为什么需要这个测试？
        1. 用户体验：用户可能不小心输入空格
        2. 数据一致性：避免 "任务1" 和 " 任务1 " 被视为不同
        3. 存储优化：减少无意义的空格

        验收标准：
        - name 的首尾空格被去除
        - name 中间的空格保留
        """
        # Act
        task = Task.create(agent_id="test-agent-123", name="  分析 销售 数据  ")

        # Assert
        assert task.name == "分析 销售 数据", "应该去除首尾空格，保留中间空格"


class TestTaskStateTransition:
    """测试 Task 状态转换

    测试场景：
    1. PENDING → RUNNING（start）
    2. RUNNING → SUCCEEDED（succeed）
    3. RUNNING → FAILED（fail）
    4. 非法状态转换（应该抛出异常）
    """

    def test_start_task_from_pending_should_succeed(self):
        """测试：从 PENDING 状态启动 Task 应该成功

        业务需求：
        - Task 开始执行时，状态从 PENDING 变为 RUNNING
        - 记录开始时间（started_at）

        验收标准：
        - 状态变为 RUNNING
        - started_at 被设置为当前时间
        - finished_at 仍然为 None
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")
        assert task.status == TaskStatus.PENDING

        # Act
        task.start()

        # Assert
        assert task.status == TaskStatus.RUNNING, "状态应该变为 RUNNING"
        assert task.started_at is not None, "started_at 应该被设置"
        assert isinstance(task.started_at, datetime), "started_at 必须是 datetime 类型"
        assert task.finished_at is None, "finished_at 应该仍然为 None"

    def test_succeed_task_from_running_should_succeed(self):
        """测试：从 RUNNING 状态完成 Task 应该成功

        业务需求：
        - Task 执行成功时，状态从 RUNNING 变为 SUCCEEDED
        - 记录完成时间（finished_at）
        - 可以保存输出数据（output_data）

        验收标准：
        - 状态变为 SUCCEEDED
        - finished_at 被设置为当前时间
        - output_data 被正确保存
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")
        task.start()
        output_data = {"result": "success", "count": 100}

        # Act
        task.succeed(output_data=output_data)

        # Assert
        assert task.status == TaskStatus.SUCCEEDED, "状态应该变为 SUCCEEDED"
        assert task.finished_at is not None, "finished_at 应该被设置"
        assert isinstance(task.finished_at, datetime), "finished_at 必须是 datetime 类型"
        assert task.output_data == output_data, "output_data 应该被正确保存"
        assert task.error is None, "error 应该仍然为 None"

    def test_succeed_task_without_output_data_should_succeed(self):
        """测试：不提供 output_data 完成 Task 应该成功

        业务需求：
        - 有些 Task 不需要输出数据（如：发送邮件）
        - output_data 应该是可选的

        验收标准：
        - 状态变为 SUCCEEDED
        - output_data 为 None
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="发送邮件")
        task.start()

        # Act
        task.succeed()

        # Assert
        assert task.status == TaskStatus.SUCCEEDED
        assert task.output_data is None, "不提供 output_data 时应该为 None"

    def test_fail_task_from_running_should_succeed(self):
        """测试：从 RUNNING 状态失败 Task 应该成功

        业务需求：
        - Task 执行失败时，状态从 RUNNING 变为 FAILED
        - 记录完成时间（finished_at）
        - 记录错误信息（error）

        验收标准：
        - 状态变为 FAILED
        - finished_at 被设置为当前时间
        - error 被正确保存
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")
        task.start()
        error_message = "文件不存在: /data/sales.csv"

        # Act
        task.fail(error=error_message)

        # Assert
        assert task.status == TaskStatus.FAILED, "状态应该变为 FAILED"
        assert task.finished_at is not None, "finished_at 应该被设置"
        assert isinstance(task.finished_at, datetime), "finished_at 必须是 datetime 类型"
        assert task.error == error_message, "error 应该被正确保存"

    def test_start_task_from_running_should_raise_error(self):
        """测试：从 RUNNING 状态启动 Task 应该抛出错误

        业务规则：
        - Task 不能重复启动
        - 状态转换必须符合状态机规则

        为什么需要这个测试？
        1. 防止状态混乱：确保状态转换的正确性
        2. 防止数据不一致：started_at 不应该被覆盖
        3. 符合业务逻辑：Task 只能启动一次

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "Task 已经在运行中"
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")
        task.start()

        # Act & Assert
        with pytest.raises(DomainError, match="Task 已经在运行中"):
            task.start()

    def test_succeed_task_from_pending_should_raise_error(self):
        """测试：从 PENDING 状态完成 Task 应该抛出错误

        业务规则：
        - Task 必须先启动才能完成
        - 状态转换必须符合状态机规则：PENDING → RUNNING → SUCCEEDED

        为什么需要这个测试？
        1. 防止跳过执行：确保 Task 真正被执行
        2. 数据完整性：started_at 必须被设置
        3. 审计需求：记录完整的执行历史

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "Task 必须先启动"
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")

        # Act & Assert
        with pytest.raises(DomainError, match="Task 必须先启动"):
            task.succeed()

    def test_fail_task_from_succeeded_should_raise_error(self):
        """测试：从 SUCCEEDED 状态失败 Task 应该抛出错误

        业务规则：
        - Task 完成后不能再失败
        - 状态转换必须符合状态机规则

        为什么需要这个测试？
        1. 防止状态回退：已完成的 Task 不应该变为失败
        2. 数据一致性：finished_at 不应该被覆盖
        3. 业务语义：成功和失败是互斥的终态

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "Task 已经完成"
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")
        task.start()
        task.succeed()

        # Act & Assert
        with pytest.raises(DomainError, match="Task 已经完成"):
            task.fail(error="不应该失败")


class TestTaskRetry:
    """测试 Task 重试逻辑

    测试场景：
    1. 增加重试次数（increment_retry_count）
    2. 重试次数应该累加
    3. 重试后可以重新启动
    """

    def test_increment_retry_count_should_increase_count(self):
        """测试：增加重试次数应该累加

        业务需求：
        - Task 失败后可以重试
        - 记录重试次数用于限流和监控

        验收标准：
        - retry_count 从 0 开始
        - 每次调用 increment_retry_count() 增加 1
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")
        assert task.retry_count == 0

        # Act & Assert
        task.increment_retry_count()
        assert task.retry_count == 1, "第一次重试，retry_count 应该为 1"

        task.increment_retry_count()
        assert task.retry_count == 2, "第二次重试，retry_count 应该为 2"

        task.increment_retry_count()
        assert task.retry_count == 3, "第三次重试，retry_count 应该为 3"

    def test_retry_task_after_failure_should_reset_status(self):
        """测试：失败后重试应该重置状态

        业务需求：
        - Task 失败后可以重试
        - 重试时需要重置状态为 PENDING
        - 清除之前的错误信息

        验收标准：
        - 调用 retry() 后状态变为 PENDING
        - error 被清除
        - retry_count 增加
        - finished_at 被清除（准备重新执行）
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")
        task.start()
        task.fail(error="第一次失败")
        assert task.status == TaskStatus.FAILED

        # Act
        task.retry()

        # Assert
        assert task.status == TaskStatus.PENDING, "重试后状态应该变为 PENDING"
        assert task.error is None, "error 应该被清除"
        assert task.retry_count == 1, "retry_count 应该增加"
        assert task.finished_at is None, "finished_at 应该被清除"
        # started_at 保留（记录第一次启动时间）


class TestTaskEvents:
    """测试 Task 事件记录

    测试场景：
    1. 添加事件（add_event）
    2. 事件按时间顺序记录
    3. 事件包含时间戳和消息
    """

    def test_add_event_should_append_to_events_list(self):
        """测试：添加事件应该追加到事件列表

        业务需求：
        - Task 执行过程中记录关键事件
        - 用于审计、调试、监控

        验收标准：
        - 事件被追加到 events 列表
        - 事件包含时间戳和消息
        - 事件按添加顺序排列
        """
        # Arrange
        task = Task.create(agent_id="test-agent-123", name="测试任务")

        # Act
        task.add_event("开始下载文件")
        task.add_event("文件下载完成")
        task.add_event("开始解析数据")

        # Assert
        assert len(task.events) == 3, "应该有 3 个事件"
        assert task.events[0].message == "开始下载文件"
        assert task.events[1].message == "文件下载完成"
        assert task.events[2].message == "开始解析数据"

        # 验证事件有时间戳
        for event in task.events:
            assert event.timestamp is not None
            assert isinstance(event.timestamp, datetime)

"""测试：Run 实体

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- Run 是 Agent 的一次执行实例
- 一个 Agent 可以被执行多次，每次执行就是一个 Run
- Run 有明确的生命周期：PENDING → RUNNING → SUCCEEDED/FAILED
- 这是 P0 优先级功能
"""

from datetime import datetime

import pytest

from src.domain.entities.run import Run, RunStatus
from src.domain.exceptions import DomainError


class TestRunCreation:
    """测试 Run 创建

    测试策略：
    1. 先测试正常路径（Happy Path）
    2. 再测试异常路径（业务规则验证）
    3. 最后测试边界情况
    """

    def test_create_run_with_valid_agent_id_should_succeed(self):
        """测试：使用有效的 agent_id 创建 Run 应该成功

        业务需求：
        - Run 必须关联一个 Agent
        - Run 是 Agent 的执行实例

        验收标准：
        - Run 必须有唯一 ID
        - agent_id 必须被正确保存
        - 默认状态为 PENDING
        - 记录创建时间
        - started_at 和 finished_at 初始为 None
        """
        # Arrange
        agent_id = "test-agent-123"

        # Act
        run = Run.create(agent_id=agent_id)

        # Assert
        assert run.id is not None, "Run 必须有唯一 ID"
        assert run.agent_id == agent_id, "agent_id 必须被正确保存"
        assert run.status == RunStatus.PENDING, "默认状态应该是 PENDING"
        assert run.created_at is not None, "必须记录创建时间"
        assert isinstance(run.created_at, datetime), "创建时间必须是 datetime 类型"
        assert run.started_at is None, "started_at 初始应该为 None"
        assert run.finished_at is None, "finished_at 初始应该为 None"
        assert run.error is None, "error 初始应该为 None"

    def test_create_run_with_empty_agent_id_should_raise_error(self):
        """测试：使用空的 agent_id 创建 Run 应该抛出错误

        业务规则：
        - agent_id 是必需的，不能为空
        - Run 必须属于某个 Agent

        为什么需要这个测试？
        1. 防止孤儿 Run：Run 必须关联 Agent
        2. 符合 DDD 规范：实体必须维护不变式
        3. 数据完整性：确保 Run 和 Agent 的关联关系

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "agent_id 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="agent_id 不能为空"):
            Run.create(agent_id="")

    def test_create_run_with_whitespace_agent_id_should_raise_error(self):
        """测试：使用纯空格的 agent_id 创建 Run 应该抛出错误

        业务规则：
        - agent_id 不能是纯空格
        - 防止用户输入无意义的空白字符

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "agent_id 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="agent_id 不能为空"):
            Run.create(agent_id="   ")

    def test_create_multiple_runs_should_have_unique_ids(self):
        """测试：创建多个 Run 应该有唯一的 ID

        业务规则：
        - 每个 Run 必须有全局唯一的 ID
        - 使用 UUID 保证唯一性

        为什么需要这个测试？
        1. 核心约束：ID 唯一性是实体的基本要求
        2. 数据完整性：防止 ID 冲突
        3. 幂等性：run_id 用于幂等性控制

        验收标准：
        - 多次创建的 Run 应该有不同的 ID
        """
        # Act
        run1 = Run.create(agent_id="agent-1")
        run2 = Run.create(agent_id="agent-1")
        run3 = Run.create(agent_id="agent-2")

        # Assert
        assert run1.id != run2.id, "不同 Run 的 ID 必须不同"
        assert run1.id != run3.id, "不同 Run 的 ID 必须不同"
        assert run2.id != run3.id, "不同 Run 的 ID 必须不同"


class TestRunStateTransition:
    """测试 Run 状态转换

    业务规则：
    - Run 的状态机：PENDING → RUNNING → SUCCEEDED/FAILED
    - 状态转换必须遵循规则，不能随意跳转

    为什么需要测试状态转换？
    1. 状态机是核心业务逻辑
    2. 非法状态转换会导致数据不一致
    3. 符合 DDD 规范：实体维护不变式
    """

    def test_start_run_from_pending_should_succeed(self):
        """测试：从 PENDING 状态启动 Run 应该成功

        业务规则：
        - PENDING → RUNNING 是合法的状态转换
        - 启动后应该记录 started_at 时间

        验收标准：
        - 状态变为 RUNNING
        - started_at 被设置为当前时间
        - finished_at 仍然为 None
        """
        # Arrange
        run = Run.create(agent_id="test-agent")
        assert run.status == RunStatus.PENDING

        # Act
        run.start()

        # Assert
        assert run.status == RunStatus.RUNNING, "状态应该变为 RUNNING"
        assert run.started_at is not None, "started_at 应该被设置"
        assert isinstance(run.started_at, datetime), "started_at 必须是 datetime 类型"
        assert run.finished_at is None, "finished_at 应该仍然为 None"

    def test_succeed_run_from_running_should_succeed(self):
        """测试：从 RUNNING 状态完成 Run 应该成功

        业务规则：
        - RUNNING → SUCCEEDED 是合法的状态转换
        - 完成后应该记录 finished_at 时间

        验收标准：
        - 状态变为 SUCCEEDED
        - finished_at 被设置为当前时间
        - error 仍然为 None
        """
        # Arrange
        run = Run.create(agent_id="test-agent")
        run.start()
        assert run.status == RunStatus.RUNNING

        # Act
        run.succeed()

        # Assert
        assert run.status == RunStatus.SUCCEEDED, "状态应该变为 SUCCEEDED"
        assert run.finished_at is not None, "finished_at 应该被设置"
        assert isinstance(run.finished_at, datetime), "finished_at 必须是 datetime 类型"
        assert run.error is None, "error 应该仍然为 None"

    def test_fail_run_from_running_should_succeed(self):
        """测试：从 RUNNING 状态失败 Run 应该成功

        业务规则：
        - RUNNING → FAILED 是合法的状态转换
        - 失败后应该记录 finished_at 时间和错误信息

        验收标准：
        - 状态变为 FAILED
        - finished_at 被设置为当前时间
        - error 被设置为错误信息
        """
        # Arrange
        run = Run.create(agent_id="test-agent")
        run.start()
        assert run.status == RunStatus.RUNNING
        error_message = "执行失败：超时"

        # Act
        run.fail(error=error_message)

        # Assert
        assert run.status == RunStatus.FAILED, "状态应该变为 FAILED"
        assert run.finished_at is not None, "finished_at 应该被设置"
        assert isinstance(run.finished_at, datetime), "finished_at 必须是 datetime 类型"
        assert run.error == error_message, "error 应该被设置为错误信息"

    def test_start_run_from_running_should_raise_error(self):
        """测试：从 RUNNING 状态再次启动 Run 应该抛出错误

        业务规则：
        - RUNNING → RUNNING 是非法的状态转换
        - 防止重复启动

        为什么需要这个测试？
        1. 状态机约束：防止非法状态转换
        2. 数据一致性：防止 started_at 被覆盖
        3. 业务逻辑：一个 Run 只能启动一次

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "只能从 PENDING 状态启动"
        """
        # Arrange
        run = Run.create(agent_id="test-agent")
        run.start()
        assert run.status == RunStatus.RUNNING

        # Act & Assert
        with pytest.raises(DomainError, match="只能从 PENDING 状态启动"):
            run.start()

    def test_succeed_run_from_pending_should_raise_error(self):
        """测试：从 PENDING 状态直接完成 Run 应该抛出错误

        业务规则：
        - PENDING → SUCCEEDED 是非法的状态转换
        - 必须先启动，再完成

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "只能从 RUNNING 状态完成"
        """
        # Arrange
        run = Run.create(agent_id="test-agent")
        assert run.status == RunStatus.PENDING

        # Act & Assert
        with pytest.raises(DomainError, match="只能从 RUNNING 状态完成"):
            run.succeed()

    def test_fail_run_from_succeeded_should_raise_error(self):
        """测试：从 SUCCEEDED 状态失败 Run 应该抛出错误

        业务规则：
        - SUCCEEDED → FAILED 是非法的状态转换
        - 已完成的 Run 不能再失败

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "只能从 RUNNING 状态失败"
        """
        # Arrange
        run = Run.create(agent_id="test-agent")
        run.start()
        run.succeed()
        assert run.status == RunStatus.SUCCEEDED

        # Act & Assert
        with pytest.raises(DomainError, match="只能从 RUNNING 状态失败"):
            run.fail(error="不应该失败")

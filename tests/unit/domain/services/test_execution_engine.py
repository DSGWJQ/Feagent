"""ExecutionEngine 单元测试

测试场景：
1. 成功执行 Run（所有 Task 成功）
2. 部分 Task 失败（Run 失败）
3. Task 执行异常处理
4. Run 状态转换验证
5. Task 执行顺序验证
6. 执行上下文传递
"""

from unittest.mock import Mock

import pytest

from src.domain.entities.run import Run, RunStatus
from src.domain.entities.task import Task, TaskStatus
from src.domain.exceptions import NotFoundError


class TestExecutionEngine:
    """ExecutionEngine 测试类"""

    def test_execute_run_success_all_tasks_succeed(self):
        """测试场景 1: 所有 Task 成功，Run 成功"""
        # Arrange: 准备测试数据
        agent_id = "agent-123"
        run_id = "run-456"

        # 创建 Run（PENDING 状态）
        run = Run.create(agent_id=agent_id)
        run.id = run_id  # 手动设置 ID 便于测试

        # 创建 3 个 Task（PENDING 状态）
        task1 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 1",
            description="读取 CSV 文件",
        )
        task2 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 2",
            description="分析数据",
        )
        task3 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 3",
            description="生成报告",
        )

        # Mock Repositories
        run_repository = Mock()
        task_repository = Mock()

        # Mock Repository 行为
        run_repository.get_by_id.return_value = run
        task_repository.find_by_run_id.return_value = [task1, task2, task3]

        # Mock TaskExecutor（模拟所有 Task 执行成功）
        task_executor = Mock()
        task_executor.execute.side_effect = [
            {"result": "CSV 文件已读取"},
            {"result": "数据分析完成"},
            {"result": "报告已生成"},
        ]

        # 创建 ExecutionEngine
        from src.domain.services.execution_engine import ExecutionEngine

        engine = ExecutionEngine(
            run_repository=run_repository,
            task_repository=task_repository,
            task_executor=task_executor,
        )

        # Act: 执行 Run
        engine.execute_run(run_id)

        # Assert: 验证结果
        # 1. Run 状态应该是 SUCCEEDED
        assert run.status == RunStatus.SUCCEEDED
        assert run.started_at is not None
        assert run.finished_at is not None
        assert run.error is None

        # 2. 所有 Task 状态应该是 SUCCEEDED
        assert task1.status == TaskStatus.SUCCEEDED
        assert task2.status == TaskStatus.SUCCEEDED
        assert task3.status == TaskStatus.SUCCEEDED

        # 3. 验证 Repository 调用
        run_repository.get_by_id.assert_called_once_with(run_id)
        task_repository.find_by_run_id.assert_called_once_with(run_id)
        assert run_repository.save.call_count >= 2  # 至少调用 2 次（start + succeed）
        assert task_repository.save.call_count == 6  # 每个 Task 调用 2 次（start + succeed）

        # 4. 验证 TaskExecutor 调用
        assert task_executor.execute.call_count == 3

    def test_execute_run_failure_one_task_fails(self):
        """测试场景 2: 一个 Task 失败，Run 失败"""
        # Arrange
        agent_id = "agent-123"
        run_id = "run-456"

        run = Run.create(agent_id=agent_id)
        run.id = run_id

        task1 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 1",
            description="读取 CSV 文件",
        )
        task2 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 2",
            description="分析数据",
        )

        run_repository = Mock()
        task_repository = Mock()

        run_repository.get_by_id.return_value = run
        task_repository.find_by_run_id.return_value = [task1, task2]

        # Mock TaskExecutor（第 2 个 Task 失败）
        task_executor = Mock()
        task_executor.execute.side_effect = [
            {"result": "CSV 文件已读取"},
            Exception("文件格式错误"),  # Task 2 失败
        ]

        from src.domain.services.execution_engine import ExecutionEngine

        engine = ExecutionEngine(
            run_repository=run_repository,
            task_repository=task_repository,
            task_executor=task_executor,
        )

        # Act
        engine.execute_run(run_id)

        # Assert
        # 1. Run 状态应该是 FAILED
        assert run.status == RunStatus.FAILED
        assert run.error is not None
        # 修改：Run 的错误信息是通用的，不包含具体 Task 错误
        assert "Task 执行失败" in run.error

        # 2. Task 1 成功，Task 2 失败
        assert task1.status == TaskStatus.SUCCEEDED
        assert task2.status == TaskStatus.FAILED
        assert task2.error is not None
        assert "文件格式错误" in task2.error

    def test_execute_run_not_found(self):
        """测试场景 3: Run 不存在，抛出异常"""
        # Arrange
        run_id = "non-existent-run"

        run_repository = Mock()
        task_repository = Mock()
        task_executor = Mock()

        # Mock Repository 抛出 NotFoundError（修复：添加 entity_type 参数）
        run_repository.get_by_id.side_effect = NotFoundError("Run", run_id)

        from src.domain.services.execution_engine import ExecutionEngine

        engine = ExecutionEngine(
            run_repository=run_repository,
            task_repository=task_repository,
            task_executor=task_executor,
        )

        # Act & Assert
        with pytest.raises(NotFoundError):
            engine.execute_run(run_id)

    def test_execute_run_no_tasks(self):
        """测试场景 4: Run 没有 Task，直接成功"""
        # Arrange
        agent_id = "agent-123"
        run_id = "run-456"

        run = Run.create(agent_id=agent_id)
        run.id = run_id

        run_repository = Mock()
        task_repository = Mock()
        task_executor = Mock()

        run_repository.get_by_id.return_value = run
        task_repository.find_by_run_id.return_value = []  # 没有 Task

        from src.domain.services.execution_engine import ExecutionEngine

        engine = ExecutionEngine(
            run_repository=run_repository,
            task_repository=task_repository,
            task_executor=task_executor,
        )

        # Act
        engine.execute_run(run_id)

        # Assert
        # Run 应该成功（没有 Task 也算成功）
        assert run.status == RunStatus.SUCCEEDED
        assert task_executor.execute.call_count == 0  # 没有调用 TaskExecutor

    def test_execute_run_task_execution_order(self):
        """测试场景 5: Task 按顺序执行"""
        # Arrange
        agent_id = "agent-123"
        run_id = "run-456"

        run = Run.create(agent_id=agent_id)
        run.id = run_id

        task1 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 1",
            description="第一步",
        )
        task2 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 2",
            description="第二步",
        )
        task3 = Task.create(
            agent_id=agent_id,
            run_id=run_id,
            name="Task 3",
            description="第三步",
        )

        run_repository = Mock()
        task_repository = Mock()

        run_repository.get_by_id.return_value = run
        task_repository.find_by_run_id.return_value = [task1, task2, task3]

        # 记录执行顺序
        execution_order = []

        def mock_execute(task, context):
            execution_order.append(task.name)
            return {"result": f"{task.name} 完成"}

        task_executor = Mock()
        task_executor.execute.side_effect = mock_execute

        from src.domain.services.execution_engine import ExecutionEngine

        engine = ExecutionEngine(
            run_repository=run_repository,
            task_repository=task_repository,
            task_executor=task_executor,
        )

        # Act
        engine.execute_run(run_id)

        # Assert
        # 验证执行顺序
        assert execution_order == ["Task 1", "Task 2", "Task 3"]

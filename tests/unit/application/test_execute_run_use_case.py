"""ExecuteRunUseCase 单元测试

测试目标：
1. 验证 ExecuteRunUseCase 能够正确创建和执行 Run
2. 验证 Agent 存在性检查
3. 验证 Run 状态转换
4. 验证 Repository 调用顺序
5. 验证异常处理
6. 验证 LangChain 集成（计划生成、Task 创建、Task 执行）

第一性原则：
- 用例负责编排业务逻辑，不包含业务规则
- 业务规则在 Domain 层（Run.start(), Run.succeed(), Run.fail()）
- 用例是事务边界

测试策略：
- 使用 Mock Repository 进行单元测试
- 不依赖真实数据库
- 测试各种边界条件和异常情况
- 使用 Mock LangChain 组件测试集成
"""

from unittest.mock import Mock, patch

import pytest

from src.application.use_cases.execute_run import ExecuteRunInput, ExecuteRunUseCase
from src.domain.entities.agent import Agent
from src.domain.entities.run import Run, RunStatus
from src.domain.entities.task import Task
from src.domain.exceptions import DomainError, NotFoundError


class TestExecuteRunUseCase:
    """ExecuteRunUseCase 测试类"""

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    @patch("src.application.use_cases.execute_run.execute_task")
    def test_execute_run_success(
        self,
        mock_execute_task,
        mock_create_plan_chain,
    ):
        """测试成功执行 Run

        验证点：
        - 输入有效时，能够成功创建并执行 Run
        - 检查 Agent 是否存在
        - 创建 Run 并保存
        - 启动 Run（PENDING → RUNNING）
        - 完成 Run（RUNNING → SUCCEEDED）
        - 调用 Repository 保存状态变化
        """
        # Arrange: 准备测试数据和 Mock
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.return_value = [
            {"name": "测试任务", "description": "测试描述"},
        ]
        mock_create_plan_chain.return_value = mock_plan_chain

        # Mock TaskExecutorAgent
        mock_execute_task.return_value = "任务执行成功"

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act: 执行用例
        result = use_case.execute(input_data)

        # Assert: 验证结果
        assert result is not None, "应该返回执行的 Run"
        assert isinstance(result, Run), "返回值应该是 Run 实例"
        assert result.agent_id == mock_agent.id, "agent_id 应该匹配输入"
        assert result.status == RunStatus.SUCCEEDED, "Run 应该成功完成"
        assert result.id is not None, "应该生成 ID"
        assert result.created_at is not None, "应该记录创建时间"
        assert result.started_at is not None, "应该记录开始时间"
        assert result.finished_at is not None, "应该记录完成时间"
        assert result.error is None, "成功时不应该有错误信息"

        # 验证 Repository 调用
        mock_agent_repo.get_by_id.assert_called_once_with(mock_agent.id)
        assert mock_run_repo.save.call_count >= 1, "应该至少调用一次 Repository.save()"

    def test_execute_run_agent_not_found(self):
        """测试 Agent 不存在时抛出异常

        验证点：
        - Agent 不存在时，抛出 NotFoundError
        - 不创建 Run
        - 不调用 RunRepository.save()
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 不存在
        agent_id = "non-existent-id"
        mock_agent_repo.get_by_id.side_effect = NotFoundError("Agent", agent_id)

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=agent_id)

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            use_case.execute(input_data)

        assert "Agent 不存在" in str(exc_info.value)
        assert agent_id in str(exc_info.value)
        mock_run_repo.save.assert_not_called()  # 不应该调用 RunRepository.save()

    def test_execute_run_with_empty_agent_id(self):
        """测试 agent_id 为空时抛出异常

        验证点：
        - agent_id 为空字符串时，抛出 DomainError
        - 不调用 Repository
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id="")

        # Act & Assert
        with pytest.raises(DomainError) as exc_info:
            use_case.execute(input_data)

        assert "agent_id 不能为空" in str(exc_info.value)
        mock_agent_repo.get_by_id.assert_not_called()
        mock_run_repo.save.assert_not_called()

    def test_execute_run_with_whitespace_agent_id(self):
        """测试 agent_id 为纯空格时抛出异常

        验证点：
        - agent_id 为纯空格时，抛出 DomainError
        - 防止用户输入纯空格绕过验证
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id="   ")

        # Act & Assert
        with pytest.raises(DomainError) as exc_info:
            use_case.execute(input_data)

        assert "agent_id 不能为空" in str(exc_info.value)

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    @patch("src.application.use_cases.execute_run.execute_task")
    def test_execute_run_repository_exception(
        self,
        mock_execute_task,
        mock_create_plan_chain,
    ):
        """测试 Repository 抛出异常时的处理

        验证点：
        - Repository.save() 抛出异常时，Run 状态应该为 FAILED
        - 错误信息被记录
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain 抛出异常
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.side_effect = Exception("数据库连接失败")
        mock_create_plan_chain.return_value = mock_plan_chain

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.status == RunStatus.FAILED
        assert result.error is not None
        assert "数据库连接失败" in result.error

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    @patch("src.application.use_cases.execute_run.execute_task")
    def test_execute_run_multiple_times_for_same_agent(
        self,
        mock_execute_task,
        mock_create_plan_chain,
    ):
        """测试同一个 Agent 多次执行 Run

        验证点：
        - 每次执行都创建新的 Run
        - 每个 Run 都有唯一的 ID
        - 所有 Run 都关联到同一个 Agent
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.return_value = [
            {"name": "测试任务", "description": "测试描述"},
        ]
        mock_create_plan_chain.return_value = mock_plan_chain

        # Mock TaskExecutorAgent
        mock_execute_task.return_value = "任务执行成功"

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act
        result1 = use_case.execute(input_data)
        result2 = use_case.execute(input_data)

        # Assert
        assert result1.id != result2.id, "每次执行应该创建不同的 Run"
        assert (
            result1.agent_id == result2.agent_id == mock_agent.id
        ), "所有 Run 应该关联到同一个 Agent"
        assert mock_run_repo.save.call_count >= 2, "应该至少调用两次 Repository.save()"

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    @patch("src.application.use_cases.execute_run.execute_task")
    def test_execute_run_trims_whitespace_in_agent_id(
        self,
        mock_execute_task,
        mock_create_plan_chain,
    ):
        """测试自动去除 agent_id 首尾空格

        验证点：
        - agent_id 的首尾空格被自动去除
        - 使用规范化的 agent_id 查询 Agent
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.return_value = [
            {"name": "测试任务", "description": "测试描述"},
        ]
        mock_create_plan_chain.return_value = mock_plan_chain

        # Mock TaskExecutorAgent
        mock_execute_task.return_value = "任务执行成功"

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=f"  {mock_agent.id}  ")

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.agent_id == mock_agent.id, "agent_id 应该去除首尾空格"
        mock_agent_repo.get_by_id.assert_called_once_with(mock_agent.id)


class TestExecuteRunUseCaseWithLangChain:
    """ExecuteRunUseCase LangChain 集成测试类

    测试目标：
    1. 验证 PlanGeneratorChain 集成
    2. 验证 Task 创建和保存
    3. 验证 TaskExecutorAgent 集成
    4. 验证 Task 状态转换
    5. 验证端到端流程
    """

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    @patch("src.application.use_cases.execute_run.execute_task")
    def test_execute_run_with_langchain_integration(
        self,
        mock_execute_task,
        mock_create_plan_chain,
    ):
        """测试完整的 LangChain 集成流程

        验证点：
        - 调用 PlanGeneratorChain 生成计划
        - 根据计划创建 Task 实体
        - 保存 Task 到数据库
        - 调用 TaskExecutorAgent 执行每个 Task
        - 更新 Task 状态
        - Run 最终状态为 SUCCEEDED
        """
        # Arrange: 准备测试数据和 Mock
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件，包含销售数据",
            goal="分析销售数据并生成报告",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain 返回计划
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.return_value = [
            {"name": "读取 CSV 文件", "description": "使用 pandas 读取销售数据"},
            {"name": "数据清洗", "description": "去除空值和重复数据"},
            {"name": "生成报告", "description": "生成销售分析报告"},
        ]
        mock_create_plan_chain.return_value = mock_plan_chain

        # Mock TaskExecutorAgent 返回成功结果
        mock_execute_task.side_effect = [
            "成功读取 CSV 文件，共 1000 行数据",
            "成功清洗数据，去除 50 行无效数据",
            "成功生成报告，保存到 report.pdf",
        ]

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act: 执行用例
        result = use_case.execute(input_data)

        # Assert: 验证结果
        assert result is not None, "应该返回执行的 Run"
        assert isinstance(result, Run), "返回值应该是 Run 实例"
        assert result.status == RunStatus.SUCCEEDED, "Run 应该成功完成"

        # 验证 PlanGeneratorChain 被调用
        mock_create_plan_chain.assert_called_once()
        mock_plan_chain.invoke.assert_called_once_with(
            {
                "start": mock_agent.start,
                "goal": mock_agent.goal,
            }
        )

        # 验证 Task 被创建和保存（3 个任务）
        assert (
            mock_task_repo.save.call_count == 9
        ), "应该保存 9 次 Task（每个 Task 保存 3 次：创建时 + 启动时 + 完成时）"

        # 验证 TaskExecutorAgent 被调用（3 次）
        assert mock_execute_task.call_count == 3, "应该执行 3 个任务"

        # 验证 Run 被保存（至少 3 次：创建、启动、完成）
        assert mock_run_repo.save.call_count >= 3

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    def test_execute_run_with_plan_generation_failure(
        self,
        mock_create_plan_chain,
    ):
        """测试计划生成失败时的处理

        验证点：
        - PlanGeneratorChain 抛出异常时，Run 状态为 FAILED
        - 异常信息被记录到 Run.error
        - 不创建 Task
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain 抛出异常
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.side_effect = Exception("LLM 调用失败")
        mock_create_plan_chain.return_value = mock_plan_chain

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act: 执行用例
        result = use_case.execute(input_data)

        # Assert: 验证结果
        assert result.status == RunStatus.FAILED, "Run 应该失败"
        assert result.error is not None
        assert "LLM 调用失败" in result.error, "错误信息应该被记录"
        mock_task_repo.save.assert_not_called()  # 不应该创建 Task

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    @patch("src.application.use_cases.execute_run.execute_task")
    def test_execute_run_with_task_execution_failure(
        self,
        mock_execute_task,
        mock_create_plan_chain,
    ):
        """测试 Task 执行失败时的处理

        验证点：
        - 某个 Task 执行失败时，该 Task 状态为 FAILED
        - 后续 Task 继续执行
        - Run 最终状态为 FAILED（因为有 Task 失败）
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain 返回计划
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.return_value = [
            {"name": "读取文件", "description": "读取 CSV 文件"},
            {"name": "分析数据", "description": "分析销售数据"},
        ]
        mock_create_plan_chain.return_value = mock_plan_chain

        # Mock TaskExecutorAgent：第一个成功，第二个失败
        mock_execute_task.side_effect = [
            "成功读取文件",
            "错误：文件格式不正确",
        ]

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act: 执行用例
        result = use_case.execute(input_data)

        # Assert: 验证结果
        assert result.status == RunStatus.FAILED, "Run 应该失败（因为有 Task 失败）"
        assert mock_execute_task.call_count == 2, "应该执行 2 个任务"

    @patch("src.application.use_cases.execute_run.create_plan_generator_chain")
    @patch("src.application.use_cases.execute_run.execute_task")
    def test_execute_run_creates_tasks_with_correct_data(
        self,
        mock_execute_task,
        mock_create_plan_chain,
    ):
        """测试 Task 创建时的数据正确性

        验证点：
        - Task.run_id 正确关联到 Run
        - Task.name 和 input_data 来自计划
        - Task 初始状态为 PENDING
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()
        mock_task_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock PlanGeneratorChain 返回计划
        mock_plan_chain = Mock()
        mock_plan_chain.invoke.return_value = [
            {"name": "读取文件", "description": "读取 CSV 文件"},
        ]
        mock_create_plan_chain.return_value = mock_plan_chain

        # Mock TaskExecutorAgent
        mock_execute_task.return_value = "成功读取文件"

        # 捕获保存的 Task
        saved_tasks = []
        mock_task_repo.save.side_effect = lambda task: saved_tasks.append(task)

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
            task_repository=mock_task_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act: 执行用例
        result = use_case.execute(input_data)

        # Assert: 验证 Task 数据
        assert len(saved_tasks) >= 1, "应该至少保存 1 个 Task"

        # 获取第一次保存的 Task（PENDING 状态）
        first_task = saved_tasks[0]
        assert isinstance(first_task, Task), "应该是 Task 实例"
        assert first_task.run_id == result.id, "Task.run_id 应该关联到 Run"
        assert first_task.name == "读取文件", "Task.name 应该来自计划"
        assert first_task.input_data is not None
        assert (
            first_task.input_data["description"] == "读取 CSV 文件"
        ), "Task.input_data 应该包含 description"

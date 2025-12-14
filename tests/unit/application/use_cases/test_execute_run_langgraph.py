"""ExecuteRunUseCase 单元测试（LangGraph版本）

TDD Red 阶段：先写测试，后实现功能

测试策略：
1. Mock LangGraph executor（create_langgraph_task_executor）
2. 测试用例编排逻辑，不测试LangGraph内部
3. 验证Repository方法调用顺序和参数
4. 验证异常处理和状态转换

覆盖场景：
- 正常流程（Happy Path with LangGraph）
- 输入验证（空agent_id）
- Agent不存在（NotFoundError）
- Run创建和状态转换
- LangGraph执行成功
- LangGraph执行失败
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.application.use_cases.execute_run import ExecuteRunInput, ExecuteRunUseCase
from src.domain.entities.agent import Agent
from src.domain.entities.run import Run, RunStatus
from src.domain.exceptions import DomainError, NotFoundError


class TestExecuteRunUseCaseLangGraph:
    """ExecuteRunUseCase 单元测试（LangGraph版本）"""

    @pytest.fixture
    def mock_agent_repository(self):
        """Mock AgentRepository"""
        return MagicMock()

    @pytest.fixture
    def mock_run_repository(self):
        """Mock RunRepository"""
        return MagicMock()

    @pytest.fixture
    def use_case(self, mock_agent_repository, mock_run_repository):
        """创建UseCase实例（不再需要TaskRepository）"""
        return ExecuteRunUseCase(
            agent_repository=mock_agent_repository,
            run_repository=mock_run_repository,
        )

    @pytest.fixture
    def sample_agent(self):
        """创建示例Agent"""
        return Agent.create(
            name="Test Agent",
            start="I have a CSV file with sales data",
            goal="Generate a sales trend analysis report",
        )

    def test_execute_run_with_empty_agent_id_should_raise_domain_error(self, use_case):
        """测试：空agent_id应该抛出DomainError"""
        # Arrange
        input_data = ExecuteRunInput(agent_id="")

        # Act & Assert
        with pytest.raises(DomainError, match="agent_id 不能为空"):
            use_case.execute(input_data)

    def test_execute_run_with_nonexistent_agent_should_raise_not_found_error(
        self, use_case, mock_agent_repository
    ):
        """测试：Agent不存在应该抛出NotFoundError"""
        # Arrange
        input_data = ExecuteRunInput(agent_id="nonexistent-agent-id")
        mock_agent_repository.get_by_id.side_effect = NotFoundError("Agent not found")

        # Act & Assert
        with pytest.raises(NotFoundError, match="Agent not found"):
            use_case.execute(input_data)

        mock_agent_repository.get_by_id.assert_called_once_with("nonexistent-agent-id")

    @patch("src.application.use_cases.execute_run.create_langgraph_task_executor")
    def test_execute_run_should_create_and_start_run(
        self,
        mock_create_executor,
        use_case,
        mock_agent_repository,
        mock_run_repository,
        sample_agent,
    ):
        """测试：execute应该创建并启动Run（PENDING → RUNNING）"""
        # Arrange
        input_data = ExecuteRunInput(agent_id=sample_agent.id)
        mock_agent_repository.get_by_id.return_value = sample_agent

        # Mock LangGraph executor
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {
            "messages": [
                HumanMessage(content="Task description"),
                AIMessage(content="Task completed successfully"),
            ]
        }
        mock_create_executor.return_value = mock_executor

        # Capture status values at each save call (避免突变陷阱)
        saved_statuses = []

        def capture_status(run):
            saved_statuses.append(run.status)

        mock_run_repository.save.side_effect = capture_status

        # Act
        use_case.execute(input_data)

        # Assert - 验证Run被保存至少3次（PENDING + RUNNING + SUCCEEDED/FAILED）
        assert mock_run_repository.save.call_count >= 3

        # 第一次save: PENDING状态
        assert saved_statuses[0] == RunStatus.PENDING

        # 第二次save: RUNNING状态
        assert saved_statuses[1] == RunStatus.RUNNING

        # 第三次save: 最终状态（SUCCEEDED或FAILED）
        assert saved_statuses[2] in [RunStatus.SUCCEEDED, RunStatus.FAILED]

    @patch("src.application.use_cases.execute_run.create_langgraph_task_executor")
    def test_execute_run_success_with_langgraph(
        self,
        mock_create_executor,
        use_case,
        mock_agent_repository,
        mock_run_repository,
        sample_agent,
    ):
        """测试：LangGraph执行成功应该将Run标记为SUCCEEDED"""
        # Arrange
        input_data = ExecuteRunInput(agent_id=sample_agent.id)
        mock_agent_repository.get_by_id.return_value = sample_agent

        # Mock LangGraph executor返回成功消息
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {
            "messages": [
                HumanMessage(content=f"Start: {sample_agent.start}\nGoal: {sample_agent.goal}"),
                AIMessage(content="Analysis completed. Generated sales trend report successfully."),
            ]
        }
        mock_create_executor.return_value = mock_executor

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert isinstance(result, Run)
        assert result.status == RunStatus.SUCCEEDED
        assert result.agent_id == sample_agent.id
        assert result.error is None

        # Verify LangGraph executor was called
        mock_create_executor.assert_called_once()
        mock_executor.invoke.assert_called_once()

        # Verify invoke was called with correct structure
        invoke_call_args = mock_executor.invoke.call_args[0][0]
        assert "messages" in invoke_call_args
        assert isinstance(invoke_call_args["messages"][0], HumanMessage)

    @patch("src.application.use_cases.execute_run.create_langgraph_task_executor")
    def test_execute_run_fails_when_langgraph_returns_error(
        self,
        mock_create_executor,
        use_case,
        mock_agent_repository,
        mock_run_repository,
        sample_agent,
    ):
        """测试：LangGraph返回错误消息应该将Run标记为FAILED"""
        # Arrange
        input_data = ExecuteRunInput(agent_id=sample_agent.id)
        mock_agent_repository.get_by_id.return_value = sample_agent

        # Mock LangGraph executor返回错误消息
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {
            "messages": [
                HumanMessage(content="Task description"),
                AIMessage(content="错误：无法访问数据源"),
            ]
        }
        mock_create_executor.return_value = mock_executor

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.status == RunStatus.FAILED
        assert "无法访问数据源" in result.error

    @patch("src.application.use_cases.execute_run.create_langgraph_task_executor")
    def test_execute_run_fails_when_langgraph_raises_exception(
        self,
        mock_create_executor,
        use_case,
        mock_agent_repository,
        mock_run_repository,
        sample_agent,
    ):
        """测试：LangGraph抛出异常应该将Run标记为FAILED"""
        # Arrange
        input_data = ExecuteRunInput(agent_id=sample_agent.id)
        mock_agent_repository.get_by_id.return_value = sample_agent

        # Mock LangGraph executor抛出异常
        mock_executor = MagicMock()
        mock_executor.invoke.side_effect = Exception("LangGraph execution failed")
        mock_create_executor.return_value = mock_executor

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.status == RunStatus.FAILED
        assert "执行失败" in result.error
        assert "LangGraph execution failed" in result.error

    @patch("src.application.use_cases.execute_run.create_langgraph_task_executor")
    def test_execute_run_constructs_proper_input_message(
        self, mock_create_executor, use_case, mock_agent_repository, sample_agent
    ):
        """测试：execute应该从Agent的start和goal构建正确的输入消息"""
        # Arrange
        input_data = ExecuteRunInput(agent_id=sample_agent.id)
        mock_agent_repository.get_by_id.return_value = sample_agent

        # Mock LangGraph executor
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {
            "messages": [HumanMessage(content="Test"), AIMessage(content="Success")]
        }
        mock_create_executor.return_value = mock_executor

        # Act
        use_case.execute(input_data)

        # Assert - 验证输入消息包含start和goal
        invoke_call_args = mock_executor.invoke.call_args[0][0]
        input_message = invoke_call_args["messages"][0]

        assert isinstance(input_message, HumanMessage)
        assert sample_agent.start in input_message.content
        assert sample_agent.goal in input_message.content

"""ExecuteRunUseCase 单元测试

测试目标：
1. 验证 ExecuteRunUseCase 能够正确创建和执行 Run
2. 验证 Agent 存在性检查
3. 验证 Run 状态转换
4. 验证 Repository 调用顺序
5. 验证异常处理

第一性原则：
- 用例负责编排业务逻辑，不包含业务规则
- 业务规则在 Domain 层（Run.start(), Run.succeed(), Run.fail()）
- 用例是事务边界

测试策略：
- 使用 Mock Repository 进行单元测试
- 不依赖真实数据库
- 测试各种边界条件和异常情况
"""

from unittest.mock import Mock

import pytest

from src.application.use_cases.execute_run import ExecuteRunInput, ExecuteRunUseCase
from src.domain.entities.agent import Agent
from src.domain.entities.run import Run, RunStatus
from src.domain.exceptions import DomainError, NotFoundError


class TestExecuteRunUseCase:
    """ExecuteRunUseCase 测试类"""

    def test_execute_run_success(self):
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

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
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

        # Mock Agent 不存在
        agent_id = "non-existent-id"
        mock_agent_repo.get_by_id.side_effect = NotFoundError("Agent", agent_id)

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
        )

        input_data = ExecuteRunInput(agent_id=agent_id)

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            use_case.execute(input_data)

        assert "Agent 不存在" in str(exc_info.value)
        assert agent_id in str(exc_info.value)
        mock_run_repo.save.assert_not_called(), "不应该调用 RunRepository.save()"

    def test_execute_run_with_empty_agent_id(self):
        """测试 agent_id 为空时抛出异常

        验证点：
        - agent_id 为空字符串时，抛出 DomainError
        - 不调用 Repository
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
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

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
        )

        input_data = ExecuteRunInput(agent_id="   ")

        # Act & Assert
        with pytest.raises(DomainError) as exc_info:
            use_case.execute(input_data)

        assert "agent_id 不能为空" in str(exc_info.value)

    def test_execute_run_repository_exception(self):
        """测试 Repository 抛出异常时的处理

        验证点：
        - Repository.save() 抛出异常时，异常应该向上传播
        - 用例不捕获 Repository 异常（让上层处理）
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        # Mock Repository 抛出异常
        mock_run_repo.save.side_effect = Exception("数据库连接失败")

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            use_case.execute(input_data)

        assert "数据库连接失败" in str(exc_info.value)

    def test_execute_run_multiple_times_for_same_agent(self):
        """测试同一个 Agent 多次执行 Run

        验证点：
        - 每次执行都创建新的 Run
        - 每个 Run 都有唯一的 ID
        - 所有 Run 都关联到同一个 Agent
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
        )

        input_data = ExecuteRunInput(agent_id=mock_agent.id)

        # Act
        result1 = use_case.execute(input_data)
        result2 = use_case.execute(input_data)

        # Assert
        assert result1.id != result2.id, "每次执行应该创建不同的 Run"
        assert result1.agent_id == result2.agent_id == mock_agent.id, (
            "所有 Run 应该关联到同一个 Agent"
        )
        assert mock_run_repo.save.call_count >= 2, "应该至少调用两次 Repository.save()"

    def test_execute_run_trims_whitespace_in_agent_id(self):
        """测试自动去除 agent_id 首尾空格

        验证点：
        - agent_id 的首尾空格被自动去除
        - 使用规范化的 agent_id 查询 Agent
        """
        # Arrange
        mock_agent_repo = Mock()
        mock_run_repo = Mock()

        # Mock Agent 存在
        mock_agent = Agent.create(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )
        mock_agent_repo.get_by_id.return_value = mock_agent

        use_case = ExecuteRunUseCase(
            agent_repository=mock_agent_repo,
            run_repository=mock_run_repo,
        )

        input_data = ExecuteRunInput(agent_id=f"  {mock_agent.id}  ")

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.agent_id == mock_agent.id, "agent_id 应该去除首尾空格"
        mock_agent_repo.get_by_id.assert_called_once_with(mock_agent.id)

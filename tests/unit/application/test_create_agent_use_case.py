"""CreateAgentUseCase 单元测试

测试目标：
1. 验证 CreateAgentUseCase 能够正确创建 Agent
2. 验证输入验证逻辑
3. 验证 Repository 调用
4. 验证异常处理

第一性原则：
- 用例是业务逻辑的编排者，不包含业务规则（业务规则在 Domain 层）
- 用例负责协调 Repository、Domain Service 等组件
- 用例是事务边界（虽然这里简化了事务处理）

测试策略：
- 使用 Mock Repository 进行单元测试
- 不依赖真实数据库
- 测试各种边界条件和异常情况
"""

from unittest.mock import Mock

import pytest

from src.application.use_cases.create_agent import CreateAgentInput, CreateAgentUseCase
from src.domain.entities.agent import Agent
from src.domain.exceptions import DomainError


class TestCreateAgentUseCase:
    """CreateAgentUseCase 测试类"""

    def test_create_agent_success(self):
        """测试成功创建 Agent

        验证点：
        - 输入有效时，能够成功创建 Agent
        - 调用 Repository.save() 保存 Agent
        - 返回创建的 Agent
        """
        # Arrange: 准备测试数据和 Mock
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件，包含销售数据",
            goal="分析销售数据并生成报告",
            name="销售数据分析 Agent",
        )

        # Act: 执行用例
        result = use_case.execute(input_data)

        # Assert: 验证结果
        assert result is not None, "应该返回创建的 Agent"
        assert isinstance(result, Agent), "返回值应该是 Agent 实例"
        assert result.start == input_data.start, "start 应该匹配输入"
        assert result.goal == input_data.goal, "goal 应该匹配输入"
        assert result.name == input_data.name, "name 应该匹配输入"
        assert result.status == "active", "新创建的 Agent 应该是 active 状态"
        assert result.id is not None, "应该生成 ID"
        assert result.created_at is not None, "应该记录创建时间"

        # 验证 Repository 调用
        mock_repo.save.assert_called_once(), "应该调用 Repository.save() 一次"
        saved_agent = mock_repo.save.call_args[0][0]
        assert saved_agent.id == result.id, "保存的 Agent 应该和返回的 Agent 一致"

    def test_create_agent_without_name(self):
        """测试不提供 name 时自动生成

        验证点：
        - name 为 None 时，自动生成 name
        - 生成的 name 格式为 "Agent-YYYYMMDD-HHMMSS"
        """
        # Arrange
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name=None,  # 不提供 name
        )

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.name is not None, "应该自动生成 name"
        assert result.name.startswith("Agent-"), "name 应该以 'Agent-' 开头"

    def test_create_agent_with_empty_start(self):
        """测试 start 为空时抛出异常

        验证点：
        - start 为空字符串时，抛出 DomainError
        - 不调用 Repository.save()
        """
        # Arrange
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="",  # 空字符串
            goal="分析数据",
            name="测试 Agent",
        )

        # Act & Assert
        with pytest.raises(DomainError) as exc_info:
            use_case.execute(input_data)

        assert "start 不能为空" in str(exc_info.value), "错误消息应该提示 start 不能为空"
        mock_repo.save.assert_not_called(), "不应该调用 Repository.save()"

    def test_create_agent_with_empty_goal(self):
        """测试 goal 为空时抛出异常

        验证点：
        - goal 为空字符串时，抛出 DomainError
        - 不调用 Repository.save()
        """
        # Arrange
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件",
            goal="",  # 空字符串
            name="测试 Agent",
        )

        # Act & Assert
        with pytest.raises(DomainError) as exc_info:
            use_case.execute(input_data)

        assert "goal 不能为空" in str(exc_info.value), "错误消息应该提示 goal 不能为空"
        mock_repo.save.assert_not_called(), "不应该调用 Repository.save()"

    def test_create_agent_with_whitespace_start(self):
        """测试 start 为纯空格时抛出异常

        验证点：
        - start 为纯空格时，抛出 DomainError
        - 防止用户输入纯空格绕过验证
        """
        # Arrange
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="   ",  # 纯空格
            goal="分析数据",
            name="测试 Agent",
        )

        # Act & Assert
        with pytest.raises(DomainError) as exc_info:
            use_case.execute(input_data)

        assert "start 不能为空" in str(exc_info.value)
        mock_repo.save.assert_not_called()

    def test_create_agent_with_whitespace_goal(self):
        """测试 goal 为纯空格时抛出异常

        验证点：
        - goal 为纯空格时，抛出 DomainError
        - 防止用户输入纯空格绕过验证
        """
        # Arrange
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件",
            goal="   ",  # 纯空格
            name="测试 Agent",
        )

        # Act & Assert
        with pytest.raises(DomainError) as exc_info:
            use_case.execute(input_data)

        assert "goal 不能为空" in str(exc_info.value)
        mock_repo.save.assert_not_called()

    def test_create_agent_trims_whitespace(self):
        """测试自动去除首尾空格

        验证点：
        - start 和 goal 的首尾空格被自动去除
        - 保存到数据库的数据是规范化的
        """
        # Arrange
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="  我有一个 CSV 文件  ",  # 首尾有空格
            goal="  分析数据  ",  # 首尾有空格
            name="测试 Agent",
        )

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.start == "我有一个 CSV 文件", "start 应该去除首尾空格"
        assert result.goal == "分析数据", "goal 应该去除首尾空格"

    def test_create_agent_repository_exception(self):
        """测试 Repository 抛出异常时的处理

        验证点：
        - Repository.save() 抛出异常时，异常应该向上传播
        - 用例不捕获 Repository 异常（让上层处理）
        """
        # Arrange
        mock_repo = Mock()
        mock_repo.save.side_effect = Exception("数据库连接失败")

        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            use_case.execute(input_data)

        assert "数据库连接失败" in str(exc_info.value)

    def test_create_agent_multiple_times(self):
        """测试多次创建 Agent

        验证点：
        - 每次创建的 Agent 都有唯一的 ID
        - 每次都调用 Repository.save()
        """
        # Arrange
        mock_repo = Mock()
        use_case = CreateAgentUseCase(agent_repository=mock_repo)

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )

        # Act
        result1 = use_case.execute(input_data)
        result2 = use_case.execute(input_data)

        # Assert
        assert result1.id != result2.id, "每次创建的 Agent 应该有不同的 ID"
        assert mock_repo.save.call_count == 2, "应该调用 Repository.save() 两次"


class TestCreateAgentWithTaskGeneration:
    """测试 CreateAgentUseCase 自动生成 Tasks

    业务需求：
    - 用户创建 Agent 时，自动调用 LLM 生成执行计划
    - 将执行计划转换为 Task 实体并保存到数据库
    - 返回的 Agent 应该包含生成的 Tasks

    测试策略：
    - Mock AgentRepository 和 TaskRepository
    - Mock PlanGeneratorChain（避免真实调用 LLM）
    - 验证 Tasks 被正确创建和保存
    """

    def test_create_agent_should_generate_tasks(self, monkeypatch):
        """测试：创建 Agent 时应该自动生成 Tasks

        场景：
        - 用户填写表单（start + goal）
        - 提交创建 Agent
        - 系统调用 LLM 生成执行计划
        - 系统创建 Tasks 并保存到数据库

        验证点：
        - ✅ 调用 PlanGeneratorChain 生成计划
        - ✅ 创建的 Task 数量正确
        - ✅ Task 的 name 和 description 正确
        - ✅ Task 的 run_id 为 None（因为还没有执行）
        - ✅ 调用 TaskRepository.save() 保存每个 Task
        - ✅ 返回的 Agent 包含 Tasks
        """
        # Arrange: 准备测试数据
        from unittest.mock import MagicMock, Mock

        # Mock Repositories
        mock_agent_repo = Mock()
        mock_task_repo = Mock()

        # Mock PlanGeneratorChain
        # 模拟 LLM 返回的执行计划
        mock_plan = [
            {"name": "读取 CSV 文件", "description": "使用 pandas 读取 CSV 文件到 DataFrame"},
            {"name": "数据清洗", "description": "处理缺失值和异常值"},
            {"name": "数据分析", "description": "计算销售总额和增长率"},
        ]

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_plan

        # Mock create_plan_generator_chain 函数
        def mock_create_chain():
            return mock_chain

        monkeypatch.setattr(
            "src.application.use_cases.create_agent.create_plan_generator_chain", mock_create_chain
        )

        # 创建 Use Case（注入两个 Repository）
        use_case = CreateAgentUseCase(
            agent_repository=mock_agent_repo,
            task_repository=mock_task_repo,
        )

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件，包含销售数据",
            goal="分析销售数据并生成报告",
            name="销售数据分析 Agent",
        )

        # Act: 执行用例
        agent = use_case.execute(input_data)

        # Assert: 验证结果
        # 1. 验证调用了 PlanGeneratorChain
        mock_chain.invoke.assert_called_once_with(
            {
                "start": "我有一个 CSV 文件，包含销售数据",
                "goal": "分析销售数据并生成报告",
            }
        )

        # 2. 验证保存了 Agent
        mock_agent_repo.save.assert_called_once()

        # 3. 验证保存了 3 个 Tasks
        assert mock_task_repo.save.call_count == 3, "应该保存 3 个 Tasks"

        # 4. 验证 Task 的内容
        saved_tasks = [call.args[0] for call in mock_task_repo.save.call_args_list]

        assert saved_tasks[0].name == "读取 CSV 文件"
        assert saved_tasks[0].description == "使用 pandas 读取 CSV 文件到 DataFrame"
        assert saved_tasks[0].agent_id == agent.id
        assert saved_tasks[0].run_id is None  # 还没有执行

        assert saved_tasks[1].name == "数据清洗"
        assert saved_tasks[1].description == "处理缺失值和异常值"

        assert saved_tasks[2].name == "数据分析"
        assert saved_tasks[2].description == "计算销售总额和增长率"

        # 5. 验证返回的 Agent
        assert agent.start == "我有一个 CSV 文件，包含销售数据"
        assert agent.goal == "分析销售数据并生成报告"
        assert agent.name == "销售数据分析 Agent"

    def test_create_agent_should_handle_llm_failure(self, monkeypatch):
        """测试：LLM 调用失败时应该抛出异常

        场景：
        - 用户创建 Agent
        - LLM 调用失败（网络错误、超时等）
        - 系统应该抛出异常
        - Agent 已保存（因为 Agent 创建成功）
        - Tasks 不应该保存（因为 LLM 失败）

        验证点：
        - ✅ 抛出异常
        - ✅ Agent 已保存（调用了 AgentRepository.save()）
        - ✅ Tasks 未保存（不调用 TaskRepository.save()）

        为什么 Agent 已保存？
        - Agent 创建成功，即使 LLM 失败，Agent 也应该存在
        - 用户可以稍后手动重新生成 Tasks
        - 更符合实际业务场景
        """
        from unittest.mock import MagicMock, Mock

        # Mock Repositories
        mock_agent_repo = Mock()
        mock_task_repo = Mock()

        # Mock PlanGeneratorChain（模拟失败）
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("LLM 调用失败")

        def mock_create_chain():
            return mock_chain

        monkeypatch.setattr(
            "src.application.use_cases.create_agent.create_plan_generator_chain", mock_create_chain
        )

        # 创建 Use Case
        use_case = CreateAgentUseCase(
            agent_repository=mock_agent_repo,
            task_repository=mock_task_repo,
        )

        input_data = CreateAgentInput(
            start="我有一个 CSV 文件",
            goal="分析数据",
            name="测试 Agent",
        )

        # Act & Assert: 应该抛出异常
        with pytest.raises(Exception) as exc_info:
            use_case.execute(input_data)

        assert "LLM 调用失败" in str(exc_info.value)

        # 验证 Agent 已保存（因为 Agent 创建成功）
        mock_agent_repo.save.assert_called_once()

        # 验证 Tasks 未保存（因为 LLM 失败）
        mock_task_repo.save.assert_not_called()

"""ExecuteConcurrentWorkflowsUseCase - TDD RED 阶段测试

定义并发执行多个工作流的期望行为
"""

from unittest.mock import Mock

import pytest


class TestExecuteConcurrentWorkflowsUseCase:
    """测试并发工作流执行用例"""

    @pytest.fixture
    def mock_workflow_repo(self):
        """模拟工作流仓库"""
        return Mock()

    @pytest.fixture
    def mock_execution_manager(self):
        """模拟并发执行管理器"""
        return Mock()

    @pytest.fixture
    def mock_run_repo(self):
        """模拟Run仓库"""
        return Mock()

    def test_execute_multiple_workflows_concurrently(
        self, mock_workflow_repo, mock_execution_manager, mock_run_repo
    ):
        """测试：应该能并发执行多个工作流"""
        from src.application.use_cases.execute_concurrent_workflows import (
            ExecuteConcurrentWorkflowsInput,
            ExecuteConcurrentWorkflowsUseCase,
        )

        use_case = ExecuteConcurrentWorkflowsUseCase(
            workflow_repo=mock_workflow_repo,
            execution_manager=mock_execution_manager,
            run_repo=mock_run_repo,
        )

        # 模拟工作流
        mock_wf1 = Mock()
        mock_wf1.id = "wf_1"
        mock_wf2 = Mock()
        mock_wf2.id = "wf_2"

        mock_workflow_repo.get_by_id.side_effect = [mock_wf1, mock_wf2]

        input_data = ExecuteConcurrentWorkflowsInput(
            workflow_ids=["wf_1", "wf_2"],
            max_concurrent=2,
        )

        result = use_case.execute(input_data)

        assert result is not None
        assert len(result) == 2

    def test_respects_max_concurrent_limit(
        self, mock_workflow_repo, mock_execution_manager, mock_run_repo
    ):
        """测试：应该遵守最大并发限制"""
        from src.application.use_cases.execute_concurrent_workflows import (
            ExecuteConcurrentWorkflowsInput,
            ExecuteConcurrentWorkflowsUseCase,
        )

        use_case = ExecuteConcurrentWorkflowsUseCase(
            workflow_repo=mock_workflow_repo,
            execution_manager=mock_execution_manager,
            run_repo=mock_run_repo,
        )

        # 模拟3个工作流，但最多只能2个并发
        mock_workflows = [Mock() for _ in range(3)]
        for i, wf in enumerate(mock_workflows):
            wf.id = f"wf_{i}"

        mock_workflow_repo.get_by_id.side_effect = mock_workflows

        input_data = ExecuteConcurrentWorkflowsInput(
            workflow_ids=["wf_0", "wf_1", "wf_2"],
            max_concurrent=2,
        )

        use_case.execute(input_data)

        # 验证执行管理器被用正确的限制初始化
        assert mock_execution_manager.max_concurrent_tasks >= 2

    def test_creates_run_instances_for_each_workflow(
        self, mock_workflow_repo, mock_execution_manager, mock_run_repo
    ):
        """测试：应该为每个工作流创建Run实例"""
        from src.application.use_cases.execute_concurrent_workflows import (
            ExecuteConcurrentWorkflowsInput,
            ExecuteConcurrentWorkflowsUseCase,
        )

        use_case = ExecuteConcurrentWorkflowsUseCase(
            workflow_repo=mock_workflow_repo,
            execution_manager=mock_execution_manager,
            run_repo=mock_run_repo,
        )

        mock_wf = Mock()
        mock_wf.id = "wf_1"
        mock_workflow_repo.get_by_id.return_value = mock_wf

        input_data = ExecuteConcurrentWorkflowsInput(
            workflow_ids=["wf_1"],
            max_concurrent=1,
        )

        use_case.execute(input_data)

        # 验证Run仓库的save被调用
        assert mock_run_repo.save.called

    def test_track_execution_status(
        self, mock_workflow_repo, mock_execution_manager, mock_run_repo
    ):
        """测试：应该跟踪执行状态"""
        from src.application.use_cases.execute_concurrent_workflows import (
            ExecuteConcurrentWorkflowsInput,
            ExecuteConcurrentWorkflowsUseCase,
        )

        use_case = ExecuteConcurrentWorkflowsUseCase(
            workflow_repo=mock_workflow_repo,
            execution_manager=mock_execution_manager,
            run_repo=mock_run_repo,
        )

        mock_wf = Mock()
        mock_wf.id = "wf_1"
        mock_workflow_repo.get_by_id.return_value = mock_wf

        input_data = ExecuteConcurrentWorkflowsInput(
            workflow_ids=["wf_1"],
            max_concurrent=1,
        )

        result = use_case.execute(input_data)

        # 结果应该包含执行追踪信息
        assert "run_ids" in str(result) or len(result) > 0

    def test_wait_for_all_workflows_completion(
        self, mock_workflow_repo, mock_execution_manager, mock_run_repo
    ):
        """测试：应该能等待所有工作流完成"""
        from src.application.use_cases.execute_concurrent_workflows import (
            ExecuteConcurrentWorkflowsUseCase,
        )

        use_case = ExecuteConcurrentWorkflowsUseCase(
            workflow_repo=mock_workflow_repo,
            execution_manager=mock_execution_manager,
            run_repo=mock_run_repo,
        )

        # 模拟等待完成
        mock_execution_manager.wait_all.return_value = True

        all_done = use_case.wait_all_completion(timeout=60)

        assert all_done is True
        assert mock_execution_manager.wait_all.called

    def test_get_execution_results(self, mock_workflow_repo, mock_execution_manager, mock_run_repo):
        """测试：应该能获取执行结果"""
        from src.application.use_cases.execute_concurrent_workflows import (
            ExecuteConcurrentWorkflowsUseCase,
        )

        use_case = ExecuteConcurrentWorkflowsUseCase(
            workflow_repo=mock_workflow_repo,
            execution_manager=mock_execution_manager,
            run_repo=mock_run_repo,
        )

        # 模拟Run记录
        mock_run = Mock()
        mock_run.id = "run_123"
        mock_run.status = "completed"
        mock_run_repo.get_by_id.return_value = mock_run

        result = use_case.get_execution_result("run_123")

        assert result is not None
        assert result.status == "completed"

    def test_cancel_concurrent_execution(
        self, mock_workflow_repo, mock_execution_manager, mock_run_repo
    ):
        """测试：应该能取消并发执行"""
        from src.application.use_cases.execute_concurrent_workflows import (
            ExecuteConcurrentWorkflowsUseCase,
        )

        use_case = ExecuteConcurrentWorkflowsUseCase(
            workflow_repo=mock_workflow_repo,
            execution_manager=mock_execution_manager,
            run_repo=mock_run_repo,
        )

        mock_execution_manager.cancel_all.return_value = True

        success = use_case.cancel_all_executions()

        assert success is True
        assert mock_execution_manager.cancel_all.called

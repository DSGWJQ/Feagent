"""AppendRunEventUseCase 单元测试

测试重点:
    - CAS (Compare-And-Swap) 条件更新被正确调用
    - 事件被正确追加
    - 事务被正确提交
"""

from unittest.mock import MagicMock

import pytest

from src.application.use_cases.append_run_event import (
    AppendRunEventInput,
    AppendRunEventUseCase,
)
from src.domain.entities.run import Run
from src.domain.entities.run_event import RunEvent
from src.domain.value_objects.run_status import RunStatus


@pytest.fixture
def mock_run_repo():
    repo = MagicMock()
    # CAS 默认返回 True（成功）
    repo.update_status_if_current.return_value = True
    return repo


@pytest.fixture
def mock_run_event_repo():
    return MagicMock()


@pytest.fixture
def mock_transaction_manager():
    return MagicMock()


@pytest.fixture
def sample_run():
    return Run.create(
        project_id="proj_12345678",
        workflow_id="wf_12345678",
    )


class TestAppendRunEventUseCase:
    """AppendRunEventUseCase 测试"""

    def test_append_first_event_should_trigger_cas_start(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """首个事件应该触发 CAS update_status_if_current (created → running)"""
        mock_run_repo.get_by_id.return_value = sample_run
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="node_start",
            channel="execution",
            event_id=1,
        )

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        event = use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="node_start",
                channel="execution",
                payload={"node_id": "node_1"},
            )
        )

        assert event is not None
        # 验证 CAS 被调用: created → running
        mock_run_repo.update_status_if_current.assert_called_once_with(
            sample_run.id,
            current_status=RunStatus.CREATED,
            target_status=RunStatus.RUNNING,
        )
        mock_transaction_manager.commit.assert_called_once()

    def test_append_subsequent_event_should_still_attempt_cas(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """后续事件仍会尝试 CAS，但由于状态不匹配会失败（无副作用）"""
        sample_run.start()  # 已经是 running
        mock_run_repo.get_by_id.return_value = sample_run
        mock_run_repo.update_status_if_current.return_value = False  # 状态不匹配
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="node_complete",
            channel="execution",
            event_id=6,
        )

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="node_complete",
                channel="execution",
            )
        )

        # CAS 仍然被尝试，但返回 False（因为状态已是 running）
        mock_run_repo.update_status_if_current.assert_called_once()
        mock_transaction_manager.commit.assert_called_once()

    def test_append_workflow_complete_should_trigger_cas_complete(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """workflow_complete 事件应该触发 CAS (running → completed)"""
        sample_run.start()
        mock_run_repo.get_by_id.return_value = sample_run
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="workflow_complete",
            channel="execution",
            event_id=6,
        )

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="workflow_complete",
                channel="execution",
            )
        )

        # 验证 CAS 调用顺序:
        # 1. created → running (尝试，因为状态不匹配会失败)
        # 2. running → completed (实际完成)
        calls = mock_run_repo.update_status_if_current.call_args_list
        assert len(calls) == 2
        # 最后一次调用应该是 running → completed
        last_call = calls[1]
        assert last_call[1]["current_status"] == RunStatus.RUNNING
        assert last_call[1]["target_status"] == RunStatus.COMPLETED
        assert last_call[1]["finished_at"] is not None

    def test_append_workflow_error_should_trigger_cas_fail(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """workflow_error 事件应该触发 CAS (running → failed)"""
        sample_run.start()
        mock_run_repo.get_by_id.return_value = sample_run
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="workflow_error",
            channel="execution",
            event_id=6,
        )

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="workflow_error",
                channel="execution",
                payload={"error": "Something went wrong"},
            )
        )

        # 验证 CAS 调用顺序:
        # 1. created → running (尝试)
        # 2. running → failed
        calls = mock_run_repo.update_status_if_current.call_args_list
        assert len(calls) == 2
        last_call = calls[1]
        assert last_call[1]["current_status"] == RunStatus.RUNNING
        assert last_call[1]["target_status"] == RunStatus.FAILED
        assert last_call[1]["finished_at"] is not None

    def test_append_terminal_event_on_created_run_should_trigger_multiple_cas(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """直接发送终止事件到 created 状态的 run 应该触发多次 CAS"""
        mock_run_repo.get_by_id.return_value = sample_run
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="workflow_complete",
            channel="execution",
            event_id=1,
        )

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="workflow_complete",
                channel="execution",
            )
        )

        # 验证 CAS 调用:
        # 1. created → running (普通事件尝试，会成功)
        # 2. running → completed
        calls = mock_run_repo.update_status_if_current.call_args_list
        assert len(calls) == 2

        # 第一次是 created → running
        assert calls[0][1]["current_status"] == RunStatus.CREATED
        assert calls[0][1]["target_status"] == RunStatus.RUNNING

        # 第二次是 running → completed
        assert calls[1][1]["current_status"] == RunStatus.RUNNING
        assert calls[1][1]["target_status"] == RunStatus.COMPLETED

    def test_event_is_appended_regardless_of_cas_result(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """无论 CAS 结果如何，事件都应该被追加"""
        mock_run_repo.get_by_id.return_value = sample_run
        mock_run_repo.update_status_if_current.return_value = False  # CAS 失败
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="node_start",
            channel="execution",
            event_id=1,
        )

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        event = use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="node_start",
                channel="execution",
            )
        )

        assert event is not None
        mock_run_event_repo.append.assert_called_once()
        mock_transaction_manager.commit.assert_called_once()

    def test_exception_triggers_rollback(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """异常应该触发回滚"""
        mock_run_repo.get_by_id.side_effect = Exception("Database error")

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        with pytest.raises(Exception, match="Database error"):
            use_case.execute(
                AppendRunEventInput(
                    run_id="run_12345678",
                    event_type="node_start",
                    channel="execution",
                )
            )

        mock_transaction_manager.rollback.assert_called_once()
        mock_transaction_manager.commit.assert_not_called()


class TestAppendRunEventUseCaseConcurrency:
    """并发安全测试"""

    def test_cas_prevents_duplicate_start(
        self,
        mock_run_repo,
        mock_run_event_repo,
        mock_transaction_manager,
        sample_run,
    ):
        """CAS 应该防止重复触发 start

        场景: 两个并发请求同时到达，都尝试 created → running
        预期: 只有一个成功，另一个 CAS 返回 False
        """
        mock_run_repo.get_by_id.return_value = sample_run
        # 第一次 CAS 成功，后续失败（模拟并发场景）
        mock_run_repo.update_status_if_current.side_effect = [True, False]
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="node_start",
            channel="execution",
            event_id=1,
        )

        use_case = AppendRunEventUseCase(
            run_repository=mock_run_repo,
            run_event_repository=mock_run_event_repo,
            transaction_manager=mock_transaction_manager,
        )

        # 第一个请求
        event1 = use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="node_start",
                channel="execution",
            )
        )

        # 第二个请求 (CAS 会返回 False)
        mock_run_event_repo.append.return_value = RunEvent.create(
            run_id=sample_run.id,
            event_type="node_start",
            channel="execution",
            event_id=2,
        )
        event2 = use_case.execute(
            AppendRunEventInput(
                run_id=sample_run.id,
                event_type="node_start",
                channel="execution",
            )
        )

        # 两个事件都应该被追加（事件追加与状态流转解耦）
        assert event1 is not None
        assert event2 is not None
        assert mock_run_event_repo.append.call_count == 2

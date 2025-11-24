"""Scheduled Workflow Integration Tests - GREEN 阶段

跨 Domain → Application → Infrastructure 层的定时工作流端到端集成测试。

测试覆盖：
1. 端到端 UseCase 调用链：API → UseCase → Repository → Database
2. 实体生命周期：创建 → 状态转换 → 禁用 → 删除
3. 执行追踪：记录成功、失败和自动禁用
4. 查询操作：按 ID、按 workflow_id、查找活跃等
5. 并发场景：多个定时任务的独立管理
"""

from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.application.use_cases.schedule_workflow import (
    ScheduleWorkflowInput,
    ScheduleWorkflowUseCase,
)
from src.domain.entities.scheduled_workflow import ScheduledWorkflow
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import WorkflowModel
from src.infrastructure.database.repositories.scheduled_workflow_repository import (
    SQLAlchemyScheduledWorkflowRepository,
)


class TestScheduledWorkflowIntegration:
    """端到端定时工作流集成测试

    测试跨越以下层次的完整工作流：
    - Domain: ScheduledWorkflow 实体及其业务逻辑
    - Application: ScheduleWorkflowUseCase 用例编排
    - Infrastructure: SQLAlchemyScheduledWorkflowRepository 持久化
    """

    @pytest.fixture
    def db_setup(self):
        """创建内存数据库和会话

        提供：
        - SQLite 内存数据库
        - 预加载的工作流模型（用于外键约束）
        """
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # 创建测试工作流（用于外键约束）
        workflow = WorkflowModel(
            id="wf_123",
            name="Test Workflow",
            description="A test workflow",
            nodes=[],
            edges=[],
            status="active",
        )
        session.add(workflow)
        session.commit()

        yield session
        session.close()

    def _create_repository(self, session: Session) -> SQLAlchemyScheduledWorkflowRepository:
        """创建 ScheduledWorkflow 仓库

        参数：
            session: SQLAlchemy 会话

        返回：
            SQLAlchemyScheduledWorkflowRepository 实例
        """
        return SQLAlchemyScheduledWorkflowRepository(session)

    def _create_use_case(
        self, repo: SQLAlchemyScheduledWorkflowRepository
    ) -> ScheduleWorkflowUseCase:
        """创建 UseCase 用于端到端测试

        参数：
            repo: 真实的 ScheduledWorkflowRepository

        返回：
            配置好的 ScheduleWorkflowUseCase
        """
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(id="wf_123")
        scheduler = Mock()

        return ScheduleWorkflowUseCase(
            workflow_repo=workflow_repo,
            scheduled_workflow_repo=repo,
            scheduler=scheduler,
        )

    def test_end_to_end_schedule_workflow_creation(self, db_setup):
        """测试：应该能从 API 到数据库完整创建定时工作流

        验证链路：
        1. UseCase 接收输入数据
        2. 创建 ScheduledWorkflow 实体
        3. Repository 保存到数据库
        4. 可以从数据库检索确认持久化
        """
        # 设置
        repo = self._create_repository(db_setup)
        use_case = self._create_use_case(repo)

        # 执行：通过 UseCase 创建定时工作流
        input_data = ScheduleWorkflowInput(
            workflow_id="wf_123",
            cron_expression="0 9 * * MON-FRI",
            max_retries=3,
        )
        result = use_case.execute(input_data)

        # 验证：UseCase 返回正确的实体
        assert result is not None
        assert result.workflow_id == "wf_123"
        assert result.cron_expression == "0 9 * * MON-FRI"
        assert result.status == "active"

        # 验证：实体已持久化到数据库
        retrieved = repo.get_by_id(result.id)
        assert retrieved is not None
        assert retrieved.workflow_id == "wf_123"
        assert retrieved.cron_expression == "0 9 * * MON-FRI"

    def test_schedule_workflow_lifecycle(self, db_setup):
        """测试：定时工作流的完整生命周期

        验证状态转换：
        active → disabled → active → deleted

        业务规则：
        - 创建时默认 active
        - 禁用时拒绝再次禁用
        - 启用时重置失败计数
        - 删除后无法查询
        """
        repo = self._create_repository(db_setup)

        # 1. 创建定时工作流（默认 active）
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_456",
            cron_expression="0 12 * * *",
            max_retries=5,
        )
        repo.save(scheduled)

        created = repo.get_by_id(scheduled.id)
        assert created.status == "active", "新创建的定时工作流应该是 active"

        # 2. 禁用定时工作流
        created.disable()
        repo.save(created)

        disabled = repo.get_by_id(created.id)
        assert disabled.status == "disabled", "禁用后应该变成 disabled"

        # 3. 重新启用定时工作流（应重置失败计数）
        disabled.enable()
        repo.save(disabled)

        enabled = repo.get_by_id(disabled.id)
        assert enabled.status == "active", "启用后应该变回 active"
        assert enabled.consecutive_failures == 0, "启用时应重置失败计数"

        # 4. 删除定时工作流
        repo.delete(enabled.id)

        # 验证已删除
        with pytest.raises(NotFoundError):
            repo.get_by_id(enabled.id)

    def test_execution_tracking_workflow(self, db_setup):
        """测试：执行追踪与自动禁用

        验证执行记录和状态管理：
        1. 记录成功执行：清除失败计数
        2. 记录失败执行：增加失败计数
        3. 自动禁用：当失败计数 >= max_retries 时

        业务规则：
        - 成功执行：consecutive_failures 重置为 0
        - 失败执行：consecutive_failures 递增
        - 自动禁用：consecutive_failures >= max_retries
        """
        repo = self._create_repository(db_setup)

        # 1. 创建定时工作流（max_retries=3）
        scheduled = ScheduledWorkflow.create(
            workflow_id="wf_789",
            cron_expression="*/5 * * * *",
            max_retries=3,
        )
        repo.save(scheduled)

        # 2. 模拟一次成功执行
        fetched = repo.get_by_id(scheduled.id)
        fetched.record_execution_success()
        repo.save(fetched)

        # 验证成功记录
        after_success = repo.get_by_id(fetched.id)
        assert after_success.last_execution_status == "success", "应该记录成功状态"
        assert after_success.consecutive_failures == 0, "成功执行应重置失败计数"
        assert after_success.last_execution_at is not None, "应该记录执行时间"
        assert after_success.status == "active", "成功后仍应保持 active"

        # 3. 模拟连续 3 次失败（达到 max_retries）
        for i in range(1, 4):
            after_success.record_execution_failure(f"Error {i}")
            repo.save(after_success)

        # 验证失败记录和自动禁用
        after_failures = repo.get_by_id(after_success.id)
        assert after_failures.last_execution_status == "failure", "应该记录失败状态"
        assert after_failures.consecutive_failures == 3, "应该计数 3 次失败"
        assert after_failures.status == "disabled", "达到 max_retries 时应自动禁用"
        assert after_failures.last_error_message == "Error 3", "应该记录最后的错误信息"

    def test_multiple_scheduled_workflows_for_same_workflow(self, db_setup):
        """测试：一对多关系 - 同一工作流可有多个定时任务

        业务场景：
        - 一个工作流可能需要在多个时间点执行
        - 例如：晨间、下午和特定周期执行
        """
        repo = self._create_repository(db_setup)

        # 为同一工作流创建多个定时任务
        scheduled1 = ScheduledWorkflow.create(
            workflow_id="wf_999",
            cron_expression="0 9 * * MON-FRI",  # 工作日上午9点
            max_retries=3,
        )
        scheduled2 = ScheduledWorkflow.create(
            workflow_id="wf_999",
            cron_expression="0 18 * * MON-FRI",  # 工作日下午6点
            max_retries=3,
        )
        scheduled3 = ScheduledWorkflow.create(
            workflow_id="wf_999",
            cron_expression="0 12 * * 0",  # 周日中午12点
            max_retries=5,
        )

        repo.save(scheduled1)
        repo.save(scheduled2)
        repo.save(scheduled3)

        # 按 workflow_id 查询所有定时任务
        all_for_workflow = repo.find_by_workflow_id("wf_999")
        assert len(all_for_workflow) == 3, "应该查到 3 个定时任务"

        # 验证每个定时任务的配置都已正确保存
        cron_expressions = {s.cron_expression for s in all_for_workflow}
        assert "0 9 * * MON-FRI" in cron_expressions
        assert "0 18 * * MON-FRI" in cron_expressions
        assert "0 12 * * 0" in cron_expressions

    def test_find_active_scheduled_workflows_across_multiple(self, db_setup):
        """测试：过滤查询 - 从多个定时任务中查找活跃的任务

        业务场景：
        - 需要快速查询活跃的定时任务
        - 已禁用的任务不应该被返回
        """
        repo = self._create_repository(db_setup)

        # 创建 5 个定时任务，其中后两个禁用
        scheduled_list = []
        for i in range(5):
            scheduled = ScheduledWorkflow.create(
                workflow_id=f"wf_{i}",
                cron_expression="0 9 * * *",
                max_retries=3,
            )
            if i >= 3:  # 最后两个禁用
                scheduled.disable()
            scheduled_list.append(scheduled)
            repo.save(scheduled)

        # 查找所有活跃的定时任务
        active = repo.find_active()
        assert len(active) == 3, "应该找到 3 个活跃的定时任务"

        # 验证所有返回的都是活跃状态
        for sched in active:
            assert sched.status == "active", "所有返回的定时任务都应该是 active"

    def test_cron_expression_validation_in_storage(self, db_setup):
        """测试：无效的 cron 表达式在创建时被拒绝

        业务规则：
        - 创建时必须验证 cron 表达式
        - 无效表达式应立即抛出异常
        """

        # 尝试创建无效 cron 表达式的定时任务
        with pytest.raises(DomainError):
            ScheduledWorkflow.create(
                workflow_id="wf_invalid",
                cron_expression="invalid cron",
                max_retries=3,
            )

    def test_concurrent_scheduled_workflows(self, db_setup):
        """测试：并发场景 - 多个独立定时任务的并发管理

        业务场景：
        - 系统需要同时管理多个定时任务
        - 每个任务的状态变更应独立不影响其他任务
        """
        repo = self._create_repository(db_setup)

        # 创建 10 个独立的定时任务
        scheduled_workflows = []
        for i in range(10):
            scheduled = ScheduledWorkflow.create(
                workflow_id=f"wf_parallel_{i}",
                cron_expression="0 * * * *",  # 每小时执行
                max_retries=2,
            )
            scheduled_workflows.append(scheduled)
            repo.save(scheduled)

        # 验证可以独立检索所有任务
        all_scheduled = repo.find_all()
        assert len(all_scheduled) >= 10, "应该查到至少 10 个定时任务"

        # 验证前 5 个任务可以独立修改（记录执行成功）
        for scheduled in scheduled_workflows[:5]:
            fetched = repo.get_by_id(scheduled.id)
            fetched.record_execution_success()
            repo.save(fetched)

        # 验证其他任务的状态不受影响
        unmodified = repo.get_by_id(scheduled_workflows[5].id)
        assert unmodified.last_execution_status is None, "未修改的任务不应有执行记录"

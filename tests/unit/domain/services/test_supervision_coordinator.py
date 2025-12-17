"""SupervisionCoordinator 单元测试

Phase: P0-7 Coverage Improvement (48% → 85%+)
Coverage targets:
- __init__: 子模块初始化（conversation_supervision, efficiency_monitor, strategy_repository）
- initiate_termination: graceful/immediate 类型，事件创建，结果返回
- record_intervention: 有/无 session_id，事件记录
- get_termination_events / get_intervention_events: 事件检索
"""

from datetime import datetime

import pytest

from src.domain.services.supervision.conversation import ConversationSupervisionModule
from src.domain.services.supervision.coordinator import SupervisionCoordinator
from src.domain.services.supervision.efficiency import WorkflowEfficiencyMonitor
from src.domain.services.supervision.events import (
    InterventionEvent,
    TaskTerminationEvent,
)
from src.domain.services.supervision.strategy_repo import StrategyRepository


@pytest.fixture
def coordinator():
    """创建协调器实例"""
    return SupervisionCoordinator()


# ==================== TestInit ====================


class TestInit:
    """测试初始化"""

    def test_init_constructs_submodules_and_empty_event_lists(self, coordinator):
        """测试初始化创建子模块和空事件列表"""
        # 验证子模块类型
        assert isinstance(coordinator.conversation_supervision, ConversationSupervisionModule)
        assert isinstance(coordinator.efficiency_monitor, WorkflowEfficiencyMonitor)
        assert isinstance(coordinator.strategy_repository, StrategyRepository)

        # 验证事件列表为空
        assert coordinator.intervention_events == []
        assert coordinator.termination_events == []


# ==================== TestInitiateTermination ====================


class TestInitiateTermination:
    """测试任务终止"""

    def test_initiate_termination_graceful_creates_event_and_returns_result(self, coordinator):
        """测试优雅终止创建事件并返回结果"""
        result = coordinator.initiate_termination(
            task_id="task123",
            reason="Test termination",
            severity="high",
            graceful=True,
            workflow_id="wf456",
        )

        # 验证返回结果
        assert result.success is True
        assert result.task_id == "task123"
        assert result.termination_type == "graceful"
        assert result.severity == "high"
        assert "task123" in result.message
        assert "Test termination" in result.message

        # 验证事件已记录
        assert len(coordinator.termination_events) == 1
        event = coordinator.termination_events[0]

        # 验证事件字段
        assert isinstance(event, TaskTerminationEvent)
        assert event.task_id == "task123"
        assert event.workflow_id == "wf456"
        assert event.reason == "Test termination"
        assert event.initiated_by == "supervision_coordinator"
        assert event.termination_type == "graceful"
        assert event.severity == "high"
        assert event.event_type == "task_termination"
        assert isinstance(event.timestamp, datetime)

    def test_initiate_termination_immediate_creates_event_and_returns_result(self, coordinator):
        """测试立即终止创建事件并返回结果"""
        result = coordinator.initiate_termination(
            task_id="task456",
            reason="Immediate stop",
            severity="critical",
            graceful=False,
            workflow_id="wf789",
        )

        # 验证返回结果
        assert result.termination_type == "immediate"

        # 验证事件
        event = coordinator.termination_events[0]
        assert event.termination_type == "immediate"

    def test_initiate_termination_allows_empty_workflow_id_default(self, coordinator):
        """测试允许省略 workflow_id（使用默认值）"""
        result = coordinator.initiate_termination(
            task_id="task789",
            reason="Test",
            severity="medium",
        )

        # 验证事件中 workflow_id 为空字符串
        event = coordinator.termination_events[0]
        assert event.workflow_id == ""


# ==================== TestInterventionRecording ====================


class TestInterventionRecording:
    """测试干预记录"""

    def test_record_intervention_without_session_id_records_event(self, coordinator):
        """测试不提供 session_id 时记录干预事件"""
        event = coordinator.record_intervention(
            intervention_type="bias_check",
            reason="Detected bias",
            source="conversation_supervision",
            target_id="message123",
            severity="medium",
        )

        # 验证返回的事件
        assert isinstance(event, InterventionEvent)
        assert event.intervention_type == "bias_check"
        assert event.reason == "Detected bias"
        assert event.source == "conversation_supervision"
        assert event.target_id == "message123"
        assert event.severity == "medium"
        assert event.session_id is None
        assert event.event_type == "intervention"
        assert isinstance(event.timestamp, datetime)

        # 验证事件已存储
        assert len(coordinator.intervention_events) == 1
        assert coordinator.intervention_events[0] is event

    def test_record_intervention_with_session_id_records_event(self, coordinator):
        """测试提供 session_id 时记录干预事件"""
        event = coordinator.record_intervention(
            intervention_type="harmful_content",
            reason="Harmful detected",
            source="supervision_module",
            target_id="message456",
            severity="high",
            session_id="session789",
        )

        # 验证 session_id 被保留
        assert event.session_id == "session789"

    def test_record_intervention_default_severity_medium(self, coordinator):
        """测试 severity 默认为 medium"""
        event = coordinator.record_intervention(
            intervention_type="test",
            reason="test",
            source="test",
            target_id="test",
        )

        assert event.severity == "medium"


# ==================== TestEventRetrieval ====================


class TestEventRetrieval:
    """测试事件检索"""

    def test_get_termination_events_returns_accumulated_in_order(self, coordinator):
        """测试 get_termination_events 返回累积的事件（按添加顺序）"""
        coordinator.initiate_termination("task1", "reason1", "low")
        coordinator.initiate_termination("task2", "reason2", "high")
        coordinator.initiate_termination("task3", "reason3", "medium")

        events = coordinator.get_termination_events()

        # 验证数量
        assert len(events) == 3

        # 验证顺序（按添加顺序）
        assert events[0].task_id == "task1"
        assert events[1].task_id == "task2"
        assert events[2].task_id == "task3"

    def test_get_intervention_events_returns_accumulated_in_order(self, coordinator):
        """测试 get_intervention_events 返回累积的事件（按添加顺序）"""
        coordinator.record_intervention("type1", "reason1", "source1", "target1")
        coordinator.record_intervention("type2", "reason2", "source2", "target2")

        events = coordinator.get_intervention_events()

        # 验证数量
        assert len(events) == 2

        # 验证顺序
        assert events[0].intervention_type == "type1"
        assert events[1].intervention_type == "type2"

    def test_get_events_empty_initially(self, coordinator):
        """测试初始时获取事件为空"""
        assert coordinator.get_termination_events() == []
        assert coordinator.get_intervention_events() == []


# ==================== TestEdgeCases ====================


class TestEdgeCases:
    """测试边缘情况"""

    def test_multiple_terminations_all_recorded(self, coordinator):
        """测试多次终止调用都被记录"""
        for i in range(5):
            coordinator.initiate_termination(f"task{i}", f"reason{i}", "medium")

        events = coordinator.get_termination_events()
        assert len(events) == 5

        # 验证所有任务 ID 都被记录
        task_ids = {e.task_id for e in events}
        assert task_ids == {"task0", "task1", "task2", "task3", "task4"}

    def test_multiple_interventions_all_recorded(self, coordinator):
        """测试多次干预调用都被记录"""
        for i in range(5):
            coordinator.record_intervention(f"type{i}", f"reason{i}", f"source{i}", f"target{i}")

        events = coordinator.get_intervention_events()
        assert len(events) == 5

        # 验证所有类型都被记录
        types = {e.intervention_type for e in events}
        assert types == {"type0", "type1", "type2", "type3", "type4"}

    def test_initiate_termination_result_fields_complete(self, coordinator):
        """测试 initiate_termination 返回的 TerminationResult 所有字段完整"""
        result = coordinator.initiate_termination(
            task_id="complete_test",
            reason="Complete check",
            severity="high",
            graceful=True,
            workflow_id="wf_complete",
        )

        # 验证所有必需字段都存在
        assert hasattr(result, "success")
        assert hasattr(result, "task_id")
        assert hasattr(result, "termination_type")
        assert hasattr(result, "message")
        assert hasattr(result, "severity")

        # 验证值的正确性
        assert result.success is True
        assert result.task_id == "complete_test"
        assert result.severity == "high"

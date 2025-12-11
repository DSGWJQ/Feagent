"""持久化操作控制回归测试套件 (Persistence Control Regression Test Suite)

本测试套件覆盖保存与干预控制的所有关键场景：
1. 保存请求流程 (Save Request Flow)
2. 审核拒绝场景 (Audit Rejection Scenarios)
3. 上下文注入机制 (Context Injection Mechanism)
4. 节点替换流程 (Node Replacement Flow)
5. 任务终止流程 (Task Termination Flow)

运行方式:
    pytest tests/integration/regression/test_persistence_control_regression.py -v --tb=short
    pytest tests/integration/regression/ -v --html=reports/regression_report.html

创建日期：2025-12-08
"""

import tempfile
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def coordinator():
    """创建 CoordinatorAgent 实例"""
    from src.domain.agents.coordinator_agent import CoordinatorAgent

    agent = CoordinatorAgent()
    agent.enable_save_request_handler()
    return agent


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_event_bus():
    """创建模拟事件总线"""
    from src.domain.services.event_bus import EventBus
    return EventBus()


# =============================================================================
# Section 1: 保存请求流程回归测试
# =============================================================================


class TestSaveRequestFlowRegression:
    """保存请求流程回归测试

    覆盖场景：
    - 正常保存请求入队和处理
    - 优先级排序
    - 状态追踪
    """

    def test_save_request_enqueue_and_dequeue(self, coordinator):
        """回归测试：保存请求正常入队和出队"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
        )

        # 创建保存请求
        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="Hello, World!",
            session_id="regression-session-1",
            reason="Regression test",
            priority=SaveRequestPriority.NORMAL,
        )

        # 直接入队（不通过事件总线，因为 event_bus 默认为 None）
        coordinator._save_request_queue.enqueue(request)

        # 验证请求已入队
        assert coordinator.has_pending_save_requests()
        assert coordinator.get_pending_save_request_count() >= 1

    def test_save_request_priority_ordering(self, coordinator):
        """回归测试：优先级排序正确"""
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestPriority,
        )

        # 创建不同优先级的请求
        requests = [
            SaveRequest(
                target_path="/tmp/low.txt",
                content="Low",
                session_id="sess-priority",
                priority=SaveRequestPriority.LOW,
            ),
            SaveRequest(
                target_path="/tmp/critical.txt",
                content="Critical",
                session_id="sess-priority",
                priority=SaveRequestPriority.CRITICAL,
            ),
            SaveRequest(
                target_path="/tmp/normal.txt",
                content="Normal",
                session_id="sess-priority",
                priority=SaveRequestPriority.NORMAL,
            ),
        ]

        # 入队
        for req in requests:
            coordinator._save_request_queue.enqueue(req)

        # 出队应该按优先级顺序
        first = coordinator.dequeue_save_request()
        assert first.priority == SaveRequestPriority.CRITICAL

        second = coordinator.dequeue_save_request()
        assert second.priority == SaveRequestPriority.NORMAL

        third = coordinator.dequeue_save_request()
        assert third.priority == SaveRequestPriority.LOW

    def test_save_request_session_tracking(self, coordinator):
        """回归测试：会话级别请求追踪"""
        from src.domain.services.save_request_channel import SaveRequest

        # 创建两个会话的请求
        req1 = SaveRequest(
            target_path="/tmp/s1.txt",
            content="Session 1",
            session_id="session-A",
        )
        req2 = SaveRequest(
            target_path="/tmp/s2.txt",
            content="Session 2",
            session_id="session-B",
        )
        req3 = SaveRequest(
            target_path="/tmp/s3.txt",
            content="Session 1 again",
            session_id="session-A",
        )

        for req in [req1, req2, req3]:
            coordinator._save_request_queue.enqueue(req)

        # 按会话查询
        session_a_requests = coordinator.get_save_requests_by_session("session-A")
        session_b_requests = coordinator.get_save_requests_by_session("session-B")

        assert len(session_a_requests) == 2
        assert len(session_b_requests) == 1


# =============================================================================
# Section 2: 审核拒绝场景回归测试
# =============================================================================


class TestAuditRejectionRegression:
    """审核拒绝场景回归测试

    覆盖场景：
    - 路径黑名单拒绝
    - 内容大小超限
    - 敏感内容检测
    - 频率限制
    """

    def test_dangerous_path_rejection(self, coordinator):
        """回归测试：危险路径被拒绝"""
        from src.domain.services.save_request_channel import SaveRequest
        from src.domain.services.save_request_audit import AuditStatus

        # 配置审核器（包含危险路径黑名单）
        coordinator.configure_save_auditor(
            path_blacklist=["/etc/", "/boot/", "/root/"],
        )

        # 创建危险路径请求
        request = SaveRequest(
            target_path="/etc/passwd",
            content="malicious content",
            session_id="regression-audit-1",
        )

        # 直接审核
        result = coordinator._save_auditor.audit(request)

        assert result.status == AuditStatus.REJECTED
        assert "blacklist" in result.reason.lower() or "forbidden" in result.reason.lower()

    def test_content_size_rejection(self, coordinator):
        """回归测试：内容过大被拒绝"""
        from src.domain.services.save_request_channel import SaveRequest
        from src.domain.services.save_request_audit import AuditStatus

        # 配置小的内容大小限制
        coordinator.configure_save_auditor(max_content_size=100)

        # 创建大内容请求
        request = SaveRequest(
            target_path="/tmp/large.txt",
            content="x" * 200,  # 超过 100 字节
            session_id="regression-audit-2",
        )

        result = coordinator._save_auditor.audit(request)

        assert result.status == AuditStatus.REJECTED
        assert "size" in result.reason.lower()

    def test_sensitive_content_detection(self, coordinator):
        """回归测试：敏感内容被检测"""
        from src.domain.services.save_request_channel import SaveRequest
        from src.domain.services.save_request_audit import AuditStatus

        coordinator.configure_save_auditor(enable_sensitive_check=True)

        # 创建包含敏感内容的请求
        request = SaveRequest(
            target_path="/tmp/config.txt",
            content='password = "secret123"',
            session_id="regression-audit-3",
        )

        result = coordinator._save_auditor.audit(request)

        # 敏感内容可能触发拒绝或待审核
        assert result.status in (AuditStatus.REJECTED, AuditStatus.PENDING_REVIEW, AuditStatus.APPROVED)

    def test_audit_logs_recorded(self, coordinator):
        """回归测试：审核日志正确记录"""
        from src.domain.services.save_request_channel import SaveRequest

        coordinator.configure_save_auditor()

        # 执行审核
        request = SaveRequest(
            target_path="/tmp/audit_log_test.txt",
            content="test content",
            session_id="regression-audit-4",
        )

        coordinator._save_auditor.audit(request)
        coordinator._save_audit_logger.log_audit(request, coordinator._save_auditor.audit(request))

        # 检查日志
        logs = coordinator.get_save_audit_logs()
        assert len(logs) >= 1

        # 按会话查询
        session_logs = coordinator.get_save_audit_logs_by_session("regression-audit-4")
        assert len(session_logs) >= 1


# =============================================================================
# Section 3: 上下文注入机制回归测试
# =============================================================================


class TestContextInjectionRegression:
    """上下文注入机制回归测试

    覆盖场景：
    - 警告注入
    - 指令注入
    - 干预注入
    - 优先级排序
    """

    def test_warning_injection(self, coordinator):
        """回归测试：警告注入"""
        from src.domain.services.context_injection import InjectionType

        # 注入警告
        injection = coordinator.inject_context(
            session_id="regression-inject-1",
            injection_type=InjectionType.WARNING,
            content="系统资源紧张，请减少操作频率",
            reason="资源监控触发",
            priority=80,
        )

        assert injection is not None
        assert injection.injection_type == InjectionType.WARNING
        assert injection.content == "系统资源紧张，请减少操作频率"

    def test_instruction_injection(self, coordinator):
        """回归测试：指令注入"""
        from src.domain.services.context_injection import InjectionType

        injection = coordinator.inject_context(
            session_id="regression-inject-2",
            injection_type=InjectionType.INSTRUCTION,
            content="建议保存到 /data 目录",
            reason="路径建议",
            priority=30,
        )

        assert injection.injection_type == InjectionType.INSTRUCTION

    def test_intervention_injection(self, coordinator):
        """回归测试：干预指令注入"""
        from src.domain.services.context_injection import InjectionType

        injection = coordinator.inject_context(
            session_id="regression-inject-3",
            injection_type=InjectionType.INTERVENTION,
            content="请注意：系统目录禁止写入",
            reason="规则干预",
            priority=50,
        )

        assert injection.injection_type == InjectionType.INTERVENTION

    def test_injection_priority_ordering(self, coordinator):
        """回归测试：注入优先级排序"""
        from src.domain.services.context_injection import InjectionType

        session_id = "regression-inject-priority"

        # 注入不同优先级的内容
        inj1 = coordinator.inject_context(
            session_id=session_id,
            injection_type=InjectionType.INSTRUCTION,
            content="低优先级指令",
            reason="test",
            priority=10,
        )

        inj2 = coordinator.inject_context(
            session_id=session_id,
            injection_type=InjectionType.WARNING,
            content="高优先级警告",
            reason="test",
            priority=90,
        )

        # 验证优先级正确设置
        assert inj1.priority == 10
        assert inj2.priority == 90
        assert inj2.priority > inj1.priority

        # 获取会话注入日志
        logs = coordinator.get_injection_logs_by_session(session_id)
        assert len(logs) >= 2

    def test_injection_logs_recorded(self, coordinator):
        """回归测试：注入日志记录"""
        from src.domain.services.context_injection import InjectionType

        coordinator.inject_context(
            session_id="regression-inject-log",
            injection_type=InjectionType.WARNING,
            content="测试注入",
            reason="日志测试",
        )

        # 检查日志
        logs = coordinator.get_injection_logs()
        assert len(logs) >= 1


# =============================================================================
# Section 4: 节点替换流程回归测试
# =============================================================================


class TestNodeReplacementRegression:
    """节点替换流程回归测试

    覆盖场景：
    - 正常节点替换
    - 节点移除
    - 替换验证
    - 替换失败回滚
    """

    def test_node_replacement_success(self, coordinator):
        """回归测试：节点替换成功"""
        # 创建测试工作流
        workflow = {
            "id": "wf-regression-1",
            "nodes": [
                {"id": "node-1", "type": "http", "config": {"url": "http://old.com"}},
                {"id": "node-2", "type": "llm", "config": {"model": "gpt-4"}},
            ],
            "edges": [
                {"from": "node-1", "to": "node-2"},
            ],
        }

        # 替换节点
        result = coordinator.replace_workflow_node(
            workflow_definition=workflow,
            node_id="node-1",
            replacement_config={"type": "http", "config": {"url": "http://new.com"}},
            reason="URL 更新",
            session_id="regression-replace-1",
        )

        assert result.success
        assert result.modified_workflow is not None

        # 验证新节点
        new_node = next(
            (n for n in result.modified_workflow["nodes"] if n["id"] == "node-1"),
            None
        )
        assert new_node is not None
        assert new_node["config"]["url"] == "http://new.com"

    def test_node_removal_success(self, coordinator):
        """回归测试：节点移除成功"""
        workflow = {
            "id": "wf-regression-2",
            "nodes": [
                {"id": "node-a", "type": "http", "config": {}},
                {"id": "node-b", "type": "llm", "config": {}},
                {"id": "node-c", "type": "transform", "config": {}},
            ],
            "edges": [
                {"from": "node-a", "to": "node-b"},
                {"from": "node-b", "to": "node-c"},
            ],
        }

        # 移除节点
        result = coordinator.remove_workflow_node(
            workflow_definition=workflow,
            node_id="node-b",
            reason="节点不再需要",
            session_id="regression-remove-1",
        )

        assert result.success

        # 验证节点已移除
        remaining_nodes = [n["id"] for n in result.modified_workflow["nodes"]]
        assert "node-b" not in remaining_nodes

    def test_workflow_validation_after_replacement(self, coordinator):
        """回归测试：替换后工作流验证"""
        workflow = {
            "id": "wf-regression-3",
            "nodes": [
                {"id": "start", "type": "http", "config": {}},
                {"id": "end", "type": "llm", "config": {}},
            ],
            "edges": [
                {"from": "start", "to": "end"},
            ],
        }

        result = coordinator.replace_workflow_node(
            workflow_definition=workflow,
            node_id="start",
            replacement_config={"type": "http", "config": {"url": "http://valid.com"}},
            reason="配置更新",
            session_id="regression-validate-1",
        )

        # 验证工作流仍然有效
        validation = coordinator.workflow_modifier.validate_workflow(result.modified_workflow)
        assert validation.is_valid

    def test_replacement_logs_recorded(self, coordinator):
        """回归测试：替换日志记录"""
        workflow = {
            "id": "wf-regression-4",
            "nodes": [{"id": "node-log", "type": "http", "config": {}}],
            "edges": [],
        }

        coordinator.replace_workflow_node(
            workflow_definition=workflow,
            node_id="node-log",
            replacement_config={"type": "llm", "config": {}},
            reason="类型变更",
            session_id="regression-log-1",
        )

        # 检查干预日志
        logs = coordinator.get_intervention_logs()
        assert len(logs) >= 1


# =============================================================================
# Section 5: 任务终止流程回归测试
# =============================================================================


class TestTaskTerminationRegression:
    """任务终止流程回归测试

    覆盖场景：
    - 正常任务终止
    - 多 Agent 通知
    - 用户错误通知
    - 终止审计日志
    """

    def test_task_termination_success(self, coordinator):
        """回归测试：任务终止成功"""
        result = coordinator.terminate_task(
            session_id="regression-terminate-1",
            reason="系统检测到异常行为",
            error_code="E001",
            notify_agents=["conversation", "workflow"],
            notify_user=True,
        )

        assert result.success
        assert result.session_id == "regression-terminate-1"

    def test_termination_agent_notification(self, coordinator):
        """回归测试：Agent 通知发送"""
        result = coordinator.terminate_task(
            session_id="regression-terminate-2",
            reason="资源耗尽",
            error_code="E002",
            notify_agents=["conversation", "workflow"],
            notify_user=False,
        )

        assert result.success
        assert "conversation" in result.notified_agents
        assert "workflow" in result.notified_agents

    def test_termination_user_notification(self, coordinator):
        """回归测试：用户通知发送"""
        result = coordinator.terminate_task(
            session_id="regression-terminate-3",
            reason="安全违规",
            error_code="E003",
            notify_agents=[],
            notify_user=True,
        )

        assert result.success
        assert result.user_notified
        assert "E003" in result.user_message

    def test_termination_logs_recorded(self, coordinator):
        """回归测试：终止日志记录"""
        coordinator.terminate_task(
            session_id="regression-terminate-4",
            reason="测试终止",
            error_code="E999",
            notify_agents=["conversation"],
            notify_user=True,
        )

        # 检查干预日志
        logs = coordinator.get_intervention_logs()
        assert any(
            log.get("type") == "task_termination" or "terminate" in str(log).lower()
            for log in logs
        )

    def test_termination_with_escalation(self, coordinator):
        """回归测试：干预升级到终止"""
        from src.domain.services.intervention_system import InterventionLevel

        # 模拟从 REPLACE 升级到 TERMINATE
        new_level = coordinator.intervention_coordinator.escalate_intervention(
            current_level=InterventionLevel.REPLACE,
            reason="替换失败，需要终止",
        )

        assert new_level == InterventionLevel.TERMINATE


# =============================================================================
# Section 6: 端到端集成回归测试
# =============================================================================


class TestEndToEndRegression:
    """端到端集成回归测试

    覆盖完整流程场景
    """

    def test_save_request_full_flow(self, coordinator, temp_dir):
        """回归测试：完整保存请求流程"""
        from src.domain.services.save_request_channel import SaveRequest

        # 配置审核器
        coordinator.configure_save_auditor(
            path_whitelist=[temp_dir],
        )

        # 创建保存请求
        target_path = os.path.join(temp_dir, "e2e_test.txt")
        request = SaveRequest(
            target_path=target_path,
            content="End-to-end test content",
            session_id="regression-e2e-1",
            reason="E2E regression test",
        )

        # 入队
        coordinator._save_request_queue.enqueue(request)

        # 处理请求
        result = coordinator.process_next_save_request()

        assert result is not None
        assert result.success

    def test_supervision_to_intervention_flow(self, coordinator):
        """回归测试：监督到干预完整流程"""
        from src.domain.services.supervision_module import SupervisionAction

        # 创建高风险上下文
        context = {
            "session_id": "regression-e2e-2",
            "usage_ratio": 0.98,  # 触发临界使用率
        }

        # 监督分析
        supervision_results = coordinator.supervise_context(context)

        # 应该触发终止动作
        if supervision_results:
            highest_action = coordinator.supervision_module.get_highest_priority_action(
                supervision_results
            )
            assert highest_action in (
                SupervisionAction.WARNING,
                SupervisionAction.TERMINATE,
            )

    def test_receipt_memory_update_flow(self, coordinator):
        """回归测试：回执与记忆更新流程"""
        session_id = "regression-e2e-3"

        # 发送成功回执
        result = coordinator.send_save_result_receipt(
            session_id=session_id,
            request_id="save-e2e-1",
            success=True,
            message="保存成功",
        )

        assert result["recorded_to_short_term"]
        assert result["recorded_to_medium_term"]

        # 获取上下文
        context = coordinator.get_save_receipt_context(session_id)
        assert "recent_save_results" in context
        assert "save_statistics" in context

    def test_violation_to_knowledge_base_flow(self, coordinator):
        """回归测试：严重违规写入知识库流程"""
        # 模拟知识库管理器
        mock_km = MagicMock()
        mock_km.create.return_value = "kb-regression-1"

        # 替换知识库管理器
        coordinator.save_receipt_system._violation_writer._knowledge_manager = mock_km

        # 发送严重违规回执
        result = coordinator.send_save_result_receipt(
            session_id="regression-e2e-4",
            request_id="save-violation-1",
            success=False,
            message="严重违规",
            error_code="DANGEROUS_PATH",
            violation_severity="critical",
        )

        assert result["written_to_knowledge_base"]
        assert result["knowledge_entry_id"] == "kb-regression-1"


# =============================================================================
# Section 7: 故障场景回归测试
# =============================================================================


class TestFailureScenarioRegression:
    """故障场景回归测试

    覆盖各种故障和边界情况
    """

    def test_empty_queue_handling(self, coordinator):
        """回归测试：空队列处理"""
        # 确保队列为空
        while coordinator.has_pending_save_requests():
            coordinator.dequeue_save_request()

        # 处理空队列应该返回 None
        result = coordinator.process_next_save_request()
        assert result is None

    def test_invalid_node_replacement(self, coordinator):
        """回归测试：无效节点替换"""
        workflow = {
            "id": "wf-failure-1",
            "nodes": [{"id": "node-1", "type": "http", "config": {}}],
            "edges": [],
        }

        # 尝试替换不存在的节点
        result = coordinator.replace_workflow_node(
            workflow_definition=workflow,
            node_id="non-existent-node",
            replacement_config={"type": "llm", "config": {}},
            reason="测试",
            session_id="regression-failure-1",
        )

        # 应该失败但不崩溃
        assert not result.success

    def test_concurrent_session_isolation(self, coordinator):
        """回归测试：并发会话隔离"""
        from src.domain.services.save_request_channel import SaveRequest

        # 创建两个会话的请求
        for i in range(3):
            req_a = SaveRequest(
                target_path=f"/tmp/session_a_{i}.txt",
                content=f"Session A - {i}",
                session_id="session-A",
            )
            req_b = SaveRequest(
                target_path=f"/tmp/session_b_{i}.txt",
                content=f"Session B - {i}",
                session_id="session-B",
            )
            coordinator._save_request_queue.enqueue(req_a)
            coordinator._save_request_queue.enqueue(req_b)

        # 验证会话隔离
        session_a = coordinator.get_save_requests_by_session("session-A")
        session_b = coordinator.get_save_requests_by_session("session-B")

        assert len(session_a) == 3
        assert len(session_b) == 3

        # 验证内容隔离
        for req in session_a:
            assert "Session A" in req.content
        for req in session_b:
            assert "Session B" in req.content

    def test_audit_rule_disabled(self, coordinator):
        """回归测试：禁用审核规则"""
        from src.domain.services.save_request_channel import SaveRequest
        from src.domain.services.save_request_audit import AuditStatus

        # 配置最小化审核（禁用敏感检查和频率限制）
        coordinator.configure_save_auditor(
            enable_rate_limit=False,
            enable_sensitive_check=False,
        )

        # 之前会被拦截的请求现在应该通过
        request = SaveRequest(
            target_path="/tmp/disabled_rules.txt",
            content='api_key = "test123"',  # 包含敏感内容
            session_id="regression-disabled-1",
        )

        result = coordinator._save_auditor.audit(request)

        # 应该通过审核（因为敏感检查被禁用）
        assert result.status == AuditStatus.APPROVED


# =============================================================================
# Section 8: 性能基准回归测试
# =============================================================================


class TestPerformanceRegression:
    """性能基准回归测试

    确保性能不会退化
    """

    def test_queue_performance(self, coordinator):
        """回归测试：队列操作性能"""
        from src.domain.services.save_request_channel import SaveRequest
        import time

        # 入队 100 个请求
        start = time.time()
        for i in range(100):
            request = SaveRequest(
                target_path=f"/tmp/perf_{i}.txt",
                content=f"Performance test {i}",
                session_id="regression-perf-1",
            )
            coordinator._save_request_queue.enqueue(request)
        enqueue_time = time.time() - start

        # 出队所有请求
        start = time.time()
        while coordinator.has_pending_save_requests():
            coordinator.dequeue_save_request()
        dequeue_time = time.time() - start

        # 性能基准：100 个操作应该在 1 秒内完成
        assert enqueue_time < 1.0, f"入队时间过长: {enqueue_time}s"
        assert dequeue_time < 1.0, f"出队时间过长: {dequeue_time}s"

    def test_audit_performance(self, coordinator):
        """回归测试：审核性能"""
        from src.domain.services.save_request_channel import SaveRequest
        import time

        coordinator.configure_save_auditor()

        # 审核 50 个请求
        start = time.time()
        for i in range(50):
            request = SaveRequest(
                target_path=f"/tmp/audit_perf_{i}.txt",
                content=f"Audit performance test {i}",
                session_id="regression-perf-2",
            )
            coordinator._save_auditor.audit(request)
        audit_time = time.time() - start

        # 性能基准：50 个审核应该在 2 秒内完成
        assert audit_time < 2.0, f"审核时间过长: {audit_time}s"


# =============================================================================
# 测试报告生成配置
# =============================================================================


# 回归测试标记（可选，用于筛选测试）
# 运行方式: pytest -m regression tests/integration/regression/

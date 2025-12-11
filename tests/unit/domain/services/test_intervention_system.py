"""干预系统测试 (Intervention System Tests)

TDD 测试用例，覆盖：
1. InterventionLevel 干预级别测试
2. NodeReplacementRequest 节点替换请求测试
3. TaskTerminationRequest 任务终止请求测试
4. WorkflowModifier 工作流修改器测试
5. TaskTerminator 任务终止器测试
6. InterventionCoordinator 干预协调器测试
7. CoordinatorAgent 集成测试
8. 集成测试：异常→替换节点→工作流继续
9. 集成测试：极端异常→强制终止→用户收到错误

实现日期：2025-12-08
"""


# =============================================================================
# TestInterventionLevel - 干预级别测试
# =============================================================================


class TestInterventionLevel:
    """干预级别枚举测试"""

    def test_level_none(self):
        """测试：NONE 级别"""
        from src.domain.services.intervention_system import InterventionLevel

        assert InterventionLevel.NONE.value == "none"

    def test_level_notify(self):
        """测试：NOTIFY 级别"""
        from src.domain.services.intervention_system import InterventionLevel

        assert InterventionLevel.NOTIFY.value == "notify"

    def test_level_warn(self):
        """测试：WARN 级别"""
        from src.domain.services.intervention_system import InterventionLevel

        assert InterventionLevel.WARN.value == "warn"

    def test_level_replace(self):
        """测试：REPLACE 级别"""
        from src.domain.services.intervention_system import InterventionLevel

        assert InterventionLevel.REPLACE.value == "replace"

    def test_level_terminate(self):
        """测试：TERMINATE 级别"""
        from src.domain.services.intervention_system import InterventionLevel

        assert InterventionLevel.TERMINATE.value == "terminate"

    def test_level_severity_order(self):
        """测试：级别严重程度顺序 TERMINATE > REPLACE > WARN > NOTIFY > NONE"""
        from src.domain.services.intervention_system import InterventionLevel

        assert InterventionLevel.get_severity(
            InterventionLevel.TERMINATE
        ) > InterventionLevel.get_severity(InterventionLevel.REPLACE)
        assert InterventionLevel.get_severity(
            InterventionLevel.REPLACE
        ) > InterventionLevel.get_severity(InterventionLevel.WARN)
        assert InterventionLevel.get_severity(
            InterventionLevel.WARN
        ) > InterventionLevel.get_severity(InterventionLevel.NOTIFY)
        assert InterventionLevel.get_severity(
            InterventionLevel.NOTIFY
        ) > InterventionLevel.get_severity(InterventionLevel.NONE)

    def test_level_can_escalate(self):
        """测试：级别升级判断"""
        from src.domain.services.intervention_system import InterventionLevel

        assert InterventionLevel.can_escalate(InterventionLevel.WARN, InterventionLevel.REPLACE)
        assert InterventionLevel.can_escalate(
            InterventionLevel.REPLACE, InterventionLevel.TERMINATE
        )
        assert not InterventionLevel.can_escalate(
            InterventionLevel.TERMINATE, InterventionLevel.WARN
        )


# =============================================================================
# TestNodeReplacementRequest - 节点替换请求测试
# =============================================================================


class TestNodeReplacementRequest:
    """节点替换请求测试"""

    def test_request_creation(self):
        """测试：请求创建"""
        from src.domain.services.intervention_system import NodeReplacementRequest

        request = NodeReplacementRequest(
            workflow_id="wf-001",
            original_node_id="node-A",
            replacement_node_config={"type": "http", "url": "https://example.com"},
            reason="节点超时",
            session_id="session-123",
        )

        assert request.workflow_id == "wf-001"
        assert request.original_node_id == "node-A"
        assert request.replacement_node_config["type"] == "http"
        assert request.reason == "节点超时"
        assert request.request_id.startswith("nrr-")

    def test_request_for_removal(self):
        """测试：移除节点请求（replacement 为 None）"""
        from src.domain.services.intervention_system import NodeReplacementRequest

        request = NodeReplacementRequest(
            workflow_id="wf-001",
            original_node_id="node-B",
            replacement_node_config=None,  # 表示移除
            reason="节点不可用",
            session_id="session-123",
        )

        assert request.replacement_node_config is None
        assert request.is_removal() is True

    def test_request_to_dict(self):
        """测试：序列化为字典"""
        from src.domain.services.intervention_system import NodeReplacementRequest

        request = NodeReplacementRequest(
            workflow_id="wf-001",
            original_node_id="node-A",
            replacement_node_config={"type": "llm"},
            reason="替换原因",
            session_id="session-123",
        )

        data = request.to_dict()

        assert data["workflow_id"] == "wf-001"
        assert data["original_node_id"] == "node-A"
        assert "timestamp" in data


# =============================================================================
# TestTaskTerminationRequest - 任务终止请求测试
# =============================================================================


class TestTaskTerminationRequest:
    """任务终止请求测试"""

    def test_request_creation(self):
        """测试：请求创建"""
        from src.domain.services.intervention_system import TaskTerminationRequest

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="检测到危险操作",
            error_code="E001",
        )

        assert request.session_id == "session-123"
        assert request.reason == "检测到危险操作"
        assert request.error_code == "E001"
        assert request.request_id.startswith("ttr-")

    def test_request_with_notify_agents(self):
        """测试：指定通知的 Agent"""
        from src.domain.services.intervention_system import TaskTerminationRequest

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="终止原因",
            error_code="E002",
            notify_agents=["conversation", "workflow"],
        )

        assert "conversation" in request.notify_agents
        assert "workflow" in request.notify_agents

    def test_request_notify_user_default_true(self):
        """测试：默认通知用户"""
        from src.domain.services.intervention_system import TaskTerminationRequest

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="原因",
            error_code="E001",
        )

        assert request.notify_user is True

    def test_request_to_dict(self):
        """测试：序列化为字典"""
        from src.domain.services.intervention_system import TaskTerminationRequest

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="原因",
            error_code="E001",
            notify_agents=["conversation"],
            notify_user=True,
        )

        data = request.to_dict()

        assert data["session_id"] == "session-123"
        assert data["error_code"] == "E001"
        assert "timestamp" in data


# =============================================================================
# TestWorkflowModifier - 工作流修改器测试
# =============================================================================


class TestWorkflowModifier:
    """工作流修改器测试"""

    def test_modifier_creation(self):
        """测试：修改器创建"""
        from src.domain.services.intervention_system import WorkflowModifier

        modifier = WorkflowModifier()

        assert modifier is not None

    def test_replace_node_success(self):
        """测试：替换节点成功"""
        from src.domain.services.intervention_system import (
            NodeReplacementRequest,
            WorkflowModifier,
        )

        modifier = WorkflowModifier()

        # 模拟工作流定义
        workflow_definition = {
            "id": "wf-001",
            "nodes": [
                {"id": "node-A", "type": "http", "config": {"url": "http://old.com"}},
                {"id": "node-B", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "node-A", "to": "node-B"}],
        }

        request = NodeReplacementRequest(
            workflow_id="wf-001",
            original_node_id="node-A",
            replacement_node_config={"type": "http", "config": {"url": "http://new.com"}},
            reason="更换 URL",
            session_id="session-123",
        )

        result = modifier.replace_node(workflow_definition, request)

        assert result.success is True
        assert result.modified_workflow is not None

    def test_replace_node_not_found(self):
        """测试：替换节点 - 节点不存在"""
        from src.domain.services.intervention_system import (
            NodeReplacementRequest,
            WorkflowModifier,
        )

        modifier = WorkflowModifier()

        workflow_definition = {
            "id": "wf-001",
            "nodes": [{"id": "node-A", "type": "http", "config": {}}],
            "edges": [],
        }

        request = NodeReplacementRequest(
            workflow_id="wf-001",
            original_node_id="node-X",  # 不存在
            replacement_node_config={"type": "http"},
            reason="替换",
            session_id="session-123",
        )

        result = modifier.replace_node(workflow_definition, request)

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_remove_node_success(self):
        """测试：移除节点成功"""
        from src.domain.services.intervention_system import (
            NodeReplacementRequest,
            WorkflowModifier,
        )

        modifier = WorkflowModifier()

        workflow_definition = {
            "id": "wf-001",
            "nodes": [
                {"id": "node-A", "type": "http", "config": {}},
                {"id": "node-B", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "node-A", "to": "node-B"}],
        }

        request = NodeReplacementRequest(
            workflow_id="wf-001",
            original_node_id="node-A",
            replacement_node_config=None,  # 移除
            reason="移除不需要的节点",
            session_id="session-123",
        )

        result = modifier.remove_node(workflow_definition, request)

        assert result.success is True
        # 检查节点已被移除
        remaining_nodes = [n["id"] for n in result.modified_workflow["nodes"]]
        assert "node-A" not in remaining_nodes

    def test_remove_node_updates_edges(self):
        """测试：移除节点 - 同时更新边"""
        from src.domain.services.intervention_system import (
            NodeReplacementRequest,
            WorkflowModifier,
        )

        modifier = WorkflowModifier()

        workflow_definition = {
            "id": "wf-001",
            "nodes": [
                {"id": "node-A", "type": "http", "config": {}},
                {"id": "node-B", "type": "llm", "config": {}},
                {"id": "node-C", "type": "output", "config": {}},
            ],
            "edges": [
                {"from": "node-A", "to": "node-B"},
                {"from": "node-B", "to": "node-C"},
            ],
        }

        request = NodeReplacementRequest(
            workflow_id="wf-001",
            original_node_id="node-B",
            replacement_node_config=None,
            reason="移除中间节点",
            session_id="session-123",
        )

        result = modifier.remove_node(workflow_definition, request)

        assert result.success is True
        # 检查边已更新
        edges = result.modified_workflow["edges"]
        assert not any(e["from"] == "node-B" or e["to"] == "node-B" for e in edges)

    def test_validate_workflow_valid(self):
        """测试：验证工作流 - 有效"""
        from src.domain.services.intervention_system import WorkflowModifier

        modifier = WorkflowModifier()

        workflow_definition = {
            "id": "wf-001",
            "nodes": [
                {"id": "node-A", "type": "http", "config": {}},
                {"id": "node-B", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "node-A", "to": "node-B"}],
        }

        result = modifier.validate_workflow(workflow_definition)

        assert result.is_valid is True

    def test_validate_workflow_invalid_no_nodes(self):
        """测试：验证工作流 - 无效（无节点）"""
        from src.domain.services.intervention_system import WorkflowModifier

        modifier = WorkflowModifier()

        workflow_definition = {
            "id": "wf-001",
            "nodes": [],
            "edges": [],
        }

        result = modifier.validate_workflow(workflow_definition)

        assert result.is_valid is False


# =============================================================================
# TestTaskTerminator - 任务终止器测试
# =============================================================================


class TestTaskTerminator:
    """任务终止器测试"""

    def test_terminator_creation(self):
        """测试：终止器创建"""
        from src.domain.services.intervention_system import TaskTerminator

        terminator = TaskTerminator()

        assert terminator is not None

    def test_terminate_task(self):
        """测试：终止任务"""
        from src.domain.services.intervention_system import (
            TaskTerminationRequest,
            TaskTerminator,
        )

        terminator = TaskTerminator()

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="测试终止",
            error_code="E001",
        )

        result = terminator.terminate(request)

        assert result.success is True
        assert result.session_id == "session-123"

    def test_terminate_notifies_conversation_agent(self):
        """测试：终止通知 ConversationAgent"""
        from src.domain.services.intervention_system import (
            TaskTerminationRequest,
            TaskTerminator,
        )

        terminator = TaskTerminator()

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="终止原因",
            error_code="E001",
            notify_agents=["conversation"],
        )

        result = terminator.terminate(request)

        assert "conversation" in result.notified_agents

    def test_terminate_notifies_workflow_agent(self):
        """测试：终止通知 WorkflowAgent"""
        from src.domain.services.intervention_system import (
            TaskTerminationRequest,
            TaskTerminator,
        )

        terminator = TaskTerminator()

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="终止原因",
            error_code="E001",
            notify_agents=["workflow"],
        )

        result = terminator.terminate(request)

        assert "workflow" in result.notified_agents

    def test_terminate_notifies_user(self):
        """测试：终止通知用户"""
        from src.domain.services.intervention_system import (
            TaskTerminationRequest,
            TaskTerminator,
        )

        terminator = TaskTerminator()

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="终止原因",
            error_code="E001",
            notify_user=True,
        )

        result = terminator.terminate(request)

        assert result.user_notified is True
        assert result.user_message is not None

    def test_terminate_creates_error_event(self):
        """测试：终止创建错误事件"""
        from src.domain.services.intervention_system import (
            TaskTerminationRequest,
            TaskTerminator,
        )

        terminator = TaskTerminator()

        request = TaskTerminationRequest(
            session_id="session-123",
            reason="终止原因",
            error_code="E001",
        )

        result = terminator.terminate(request)

        assert result.error_event is not None
        assert result.error_event.error_code == "E001"


# =============================================================================
# TestInterventionCoordinator - 干预协调器测试
# =============================================================================


class TestInterventionCoordinator:
    """干预协调器测试"""

    def test_coordinator_creation(self):
        """测试：协调器创建"""
        from src.domain.services.intervention_system import InterventionCoordinator

        coordinator = InterventionCoordinator()

        assert coordinator is not None

    def test_handle_intervention_none(self):
        """测试：处理干预 - NONE 级别"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        result = coordinator.handle_intervention(
            level=InterventionLevel.NONE,
            context={"session_id": "session-123"},
        )

        assert result.action_taken == "none"

    def test_handle_intervention_notify(self):
        """测试：处理干预 - NOTIFY 级别"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        result = coordinator.handle_intervention(
            level=InterventionLevel.NOTIFY,
            context={"session_id": "session-123", "message": "通知消息"},
        )

        assert result.action_taken == "logged"

    def test_handle_intervention_warn(self):
        """测试：处理干预 - WARN 级别"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        result = coordinator.handle_intervention(
            level=InterventionLevel.WARN,
            context={"session_id": "session-123", "warning": "警告消息"},
        )

        assert result.action_taken == "warning_injected"

    def test_handle_intervention_replace(self):
        """测试：处理干预 - REPLACE 级别"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        result = coordinator.handle_intervention(
            level=InterventionLevel.REPLACE,
            context={
                "session_id": "session-123",
                "workflow_id": "wf-001",
                "node_id": "node-A",
                "replacement": {"type": "http"},
            },
        )

        assert result.action_taken == "node_replaced"

    def test_handle_intervention_terminate(self):
        """测试：处理干预 - TERMINATE 级别"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        result = coordinator.handle_intervention(
            level=InterventionLevel.TERMINATE,
            context={
                "session_id": "session-123",
                "reason": "极端异常",
                "error_code": "E999",
            },
        )

        assert result.action_taken == "task_terminated"

    def test_escalate_intervention(self):
        """测试：升级干预级别"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        new_level = coordinator.escalate_intervention(
            current_level=InterventionLevel.WARN,
            reason="警告无效，需要升级",
        )

        assert new_level == InterventionLevel.REPLACE

    def test_escalate_from_replace_to_terminate(self):
        """测试：从 REPLACE 升级到 TERMINATE"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        new_level = coordinator.escalate_intervention(
            current_level=InterventionLevel.REPLACE,
            reason="替换失败",
        )

        assert new_level == InterventionLevel.TERMINATE

    def test_cannot_escalate_from_terminate(self):
        """测试：无法从 TERMINATE 继续升级"""
        from src.domain.services.intervention_system import (
            InterventionCoordinator,
            InterventionLevel,
        )

        coordinator = InterventionCoordinator()

        new_level = coordinator.escalate_intervention(
            current_level=InterventionLevel.TERMINATE,
            reason="已是最高级别",
        )

        assert new_level == InterventionLevel.TERMINATE


# =============================================================================
# TestCoordinatorAgentIntegration - CoordinatorAgent 集成测试
# =============================================================================


class TestCoordinatorAgentIntegration:
    """CoordinatorAgent 集成测试"""

    def test_coordinator_has_intervention_coordinator(self):
        """测试：Coordinator 拥有干预协调器"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "intervention_coordinator")
        assert coordinator.intervention_coordinator is not None

    def test_coordinator_has_workflow_modifier(self):
        """测试：Coordinator 拥有工作流修改器"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "workflow_modifier")
        assert coordinator.workflow_modifier is not None

    def test_coordinator_has_task_terminator(self):
        """测试：Coordinator 拥有任务终止器"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "task_terminator")
        assert coordinator.task_terminator is not None

    def test_coordinator_replace_workflow_node(self):
        """测试：Coordinator 替换工作流节点"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        workflow_definition = {
            "id": "wf-001",
            "nodes": [{"id": "node-A", "type": "http", "config": {}}],
            "edges": [],
        }

        result = coordinator.replace_workflow_node(
            workflow_definition=workflow_definition,
            node_id="node-A",
            replacement_config={"type": "llm", "config": {}},
            reason="替换节点",
            session_id="session-123",
        )

        assert result is not None

    def test_coordinator_remove_workflow_node(self):
        """测试：Coordinator 移除工作流节点"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        workflow_definition = {
            "id": "wf-001",
            "nodes": [
                {"id": "node-A", "type": "http", "config": {}},
                {"id": "node-B", "type": "llm", "config": {}},
            ],
            "edges": [],
        }

        result = coordinator.remove_workflow_node(
            workflow_definition=workflow_definition,
            node_id="node-A",
            reason="移除节点",
            session_id="session-123",
        )

        assert result is not None

    def test_coordinator_terminate_task(self):
        """测试：Coordinator 终止任务"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        result = coordinator.terminate_task(
            session_id="session-123",
            reason="终止原因",
            error_code="E001",
        )

        assert result is not None
        assert result.success is True

    def test_coordinator_handle_intervention(self):
        """测试：Coordinator 处理干预"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.intervention_system import InterventionLevel

        coordinator = CoordinatorAgent()

        result = coordinator.handle_intervention(
            level=InterventionLevel.WARN,
            context={"session_id": "session-123", "warning": "警告"},
        )

        assert result is not None


# =============================================================================
# TestIntegrationAnomalyReplaceAndContinue - 集成测试：异常→替换节点→继续
# =============================================================================


class TestIntegrationAnomalyReplaceAndContinue:
    """集成测试：检测异常 → 替换节点 → 工作流继续"""

    def test_detect_anomaly_replace_node_workflow_continues(self):
        """测试：检测异常后替换节点，工作流继续执行"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 1. 设置工作流
        workflow_definition = {
            "id": "wf-test",
            "nodes": [
                {"id": "node-problematic", "type": "http", "config": {"url": "http://broken.com"}},
                {"id": "node-next", "type": "llm", "config": {}},
            ],
            "edges": [{"from": "node-problematic", "to": "node-next"}],
        }

        # 2. 添加检测规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="detect-broken-url",
                name="检测损坏 URL",
                description="检测不可用的 HTTP 节点",
                action=SupervisionAction.REPLACE,
                condition=lambda ctx: "broken.com" in ctx.get("node_config", {}).get("url", ""),
            )
        )

        # 3. 模拟检测异常
        context = {
            "session_id": "session-123",
            "workflow_id": "wf-test",
            "node_id": "node-problematic",
            "node_config": {"url": "http://broken.com"},
        }

        supervision_results = coordinator.supervise_context(context)

        # 4. 验证检测到异常
        assert len(supervision_results) >= 1
        assert any(r.action == SupervisionAction.REPLACE for r in supervision_results)

        # 5. 执行替换
        replace_result = coordinator.replace_workflow_node(
            workflow_definition=workflow_definition,
            node_id="node-problematic",
            replacement_config={"type": "http", "config": {"url": "http://working.com"}},
            reason="替换损坏的节点",
            session_id="session-123",
        )

        # 6. 验证替换成功
        assert replace_result.success is True

        # 7. 验证工作流仍然有效
        modified_workflow = replace_result.modified_workflow
        validation = coordinator.workflow_modifier.validate_workflow(modified_workflow)
        assert validation.is_valid is True

    def test_replace_failed_escalate_to_terminate(self):
        """测试：替换失败时升级到终止"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.intervention_system import InterventionLevel

        coordinator = CoordinatorAgent()

        # 1. 尝试替换不存在的节点（模拟失败）
        workflow_definition = {
            "id": "wf-test",
            "nodes": [{"id": "node-A", "type": "http", "config": {}}],
            "edges": [],
        }

        replace_result = coordinator.replace_workflow_node(
            workflow_definition=workflow_definition,
            node_id="node-nonexistent",  # 不存在
            replacement_config={"type": "llm"},
            reason="尝试替换",
            session_id="session-123",
        )

        # 2. 验证替换失败
        assert replace_result.success is False

        # 3. 升级干预级别
        new_level = coordinator.intervention_coordinator.escalate_intervention(
            current_level=InterventionLevel.REPLACE,
            reason="替换失败",
        )

        # 4. 验证升级到 TERMINATE
        assert new_level == InterventionLevel.TERMINATE


# =============================================================================
# TestIntegrationExtremeAnomalyTerminate - 集成测试：极端异常→终止→用户收到错误
# =============================================================================


class TestIntegrationExtremeAnomalyTerminate:
    """集成测试：极端异常 → 强制终止 → 用户收到错误"""

    def test_extreme_anomaly_terminate_user_receives_error(self):
        """测试：极端异常触发终止，用户收到错误消息"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 1. 添加极端异常检测规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="detect-extreme-error",
                name="极端异常检测",
                description="检测无法恢复的错误",
                action=SupervisionAction.TERMINATE,
                condition=lambda ctx: ctx.get("error_type") == "unrecoverable",
            )
        )

        # 2. 模拟极端异常
        context = {
            "session_id": "session-456",
            "error_type": "unrecoverable",
            "error_message": "系统崩溃",
        }

        supervision_results = coordinator.supervise_context(context)

        # 3. 验证检测到 TERMINATE 级别
        assert len(supervision_results) >= 1
        terminate_result = next(
            (r for r in supervision_results if r.action == SupervisionAction.TERMINATE), None
        )
        assert terminate_result is not None

        # 4. 执行终止
        termination_result = coordinator.terminate_task(
            session_id="session-456",
            reason="极端异常：系统崩溃",
            error_code="E999",
        )

        # 5. 验证终止成功
        assert termination_result.success is True

        # 6. 验证用户收到错误
        assert termination_result.user_notified is True
        assert termination_result.user_message is not None
        assert (
            "E999" in termination_result.user_message or "错误" in termination_result.user_message
        )

    def test_terminate_notifies_all_agents(self):
        """测试：终止时通知所有相关 Agent"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 执行终止，通知所有 Agent
        result = coordinator.terminate_task(
            session_id="session-789",
            reason="测试终止",
            error_code="E001",
            notify_agents=["conversation", "workflow"],
        )

        # 验证所有 Agent 被通知
        assert "conversation" in result.notified_agents
        assert "workflow" in result.notified_agents

    def test_terminate_creates_audit_log(self):
        """测试：终止创建审计日志"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 执行终止
        coordinator.terminate_task(
            session_id="session-audit",
            reason="审计测试",
            error_code="E_AUDIT",
        )

        # 获取干预日志
        logs = coordinator.get_intervention_logs()

        # 验证日志记录
        assert isinstance(logs, list)


# =============================================================================
# TestInterventionEvents - 干预事件测试
# =============================================================================


class TestInterventionEvents:
    """干预事件测试"""

    def test_node_replaced_event(self):
        """测试：节点替换事件"""
        from src.domain.services.intervention_system import NodeReplacedEvent

        event = NodeReplacedEvent(
            workflow_id="wf-001",
            original_node_id="node-A",
            replacement_node_id="node-A-new",
            reason="替换原因",
            session_id="session-123",
        )

        assert event.event_type == "node_replaced"
        assert event.workflow_id == "wf-001"

    def test_task_terminated_event(self):
        """测试：任务终止事件"""
        from src.domain.services.intervention_system import TaskTerminatedEvent

        event = TaskTerminatedEvent(
            session_id="session-123",
            reason="终止原因",
            error_code="E001",
        )

        assert event.event_type == "task_terminated"
        assert event.error_code == "E001"

    def test_user_error_notification_event(self):
        """测试：用户错误通知事件"""
        from src.domain.services.intervention_system import UserErrorNotificationEvent

        event = UserErrorNotificationEvent(
            session_id="session-123",
            error_code="E001",
            error_message="发生错误",
            user_friendly_message="抱歉，出现了问题",
        )

        assert event.event_type == "user_error_notification"
        assert event.user_friendly_message is not None


# =============================================================================
# TestInterventionLogger - 干预日志测试
# =============================================================================


class TestInterventionLogger:
    """干预日志测试"""

    def test_logger_creation(self):
        """测试：日志记录器创建"""
        from src.domain.services.intervention_system import InterventionLogger

        logger = InterventionLogger()

        assert logger is not None

    def test_log_node_replacement(self):
        """测试：记录节点替换"""
        from src.domain.services.intervention_system import InterventionLogger

        logger = InterventionLogger()

        logger.log_node_replacement(
            workflow_id="wf-001",
            original_node_id="node-A",
            replacement_node_id="node-A-new",
            reason="替换原因",
            session_id="session-123",
        )

        logs = logger.get_logs()
        assert len(logs) >= 1
        assert logs[-1]["type"] == "node_replacement"

    def test_log_task_termination(self):
        """测试：记录任务终止"""
        from src.domain.services.intervention_system import InterventionLogger

        logger = InterventionLogger()

        logger.log_task_termination(
            session_id="session-123",
            reason="终止原因",
            error_code="E001",
        )

        logs = logger.get_logs()
        assert len(logs) >= 1
        assert logs[-1]["type"] == "task_termination"

    def test_get_logs_by_session(self):
        """测试：按会话获取日志"""
        from src.domain.services.intervention_system import InterventionLogger

        logger = InterventionLogger()

        logger.log_task_termination("session-A", "原因A", "E001")
        logger.log_task_termination("session-B", "原因B", "E002")

        logs_a = logger.get_logs_by_session("session-A")
        logs_b = logger.get_logs_by_session("session-B")

        assert len(logs_a) == 1
        assert len(logs_b) == 1

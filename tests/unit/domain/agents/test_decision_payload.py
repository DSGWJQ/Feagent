"""
测试决策载荷 Pydantic Schema

本测试文件遵循 TDD 原则：
1. Red：编写失败的测试，明确需求
2. Green：实现最少代码让测试通过
3. Refactor：重构优化

测试覆盖：
- 每种 DecisionType 的有效 payload 验证
- 无效 payload 的错误处理
- 边界条件测试
- 工厂函数测试
"""

import pytest
from pydantic import ValidationError

from src.domain.agents.decision_payload import (
    ActionType,
    ContinuePayload,
    CreateNodePayload,
    CreateWorkflowPlanPayload,
    ErrorRecoveryPayload,
    ExecuteWorkflowPayload,
    IntentType,
    ModifyNodePayload,
    NodeType,
    RecoveryAction,
    RecoveryPlan,
    ReplanWorkflowPayload,
    RequestClarificationPayload,
    RespondPayload,
    SpawnSubagentPayload,
    WorkflowEdge,
    WorkflowNode,
    create_payload_from_dict,
)

# ========================================
# RespondPayload 测试
# ========================================


class TestRespondPayload:
    """测试 RESPOND 决策的 payload 验证"""

    def test_valid_respond_payload_should_pass(self):
        """测试：有效的 RESPOND payload 应该通过验证"""
        payload = RespondPayload(
            action_type=ActionType.RESPOND,
            response="您好！我是智能助手。",
            intent=IntentType.GREETING,
            confidence=1.0,
            requires_followup=False,
        )

        assert payload.action_type == ActionType.RESPOND
        assert payload.response == "您好！我是智能助手。"
        assert payload.intent == IntentType.GREETING
        assert payload.confidence == 1.0
        assert payload.requires_followup is False

    def test_respond_without_response_should_fail(self):
        """测试：缺少 response 的 RESPOND payload 应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            RespondPayload(
                action_type=ActionType.RESPOND,
                intent=IntentType.GREETING,
                confidence=1.0,
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("response",) for error in errors)

    def test_respond_with_empty_response_should_fail(self):
        """测试：空 response 的 RESPOND payload 应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            RespondPayload(
                action_type=ActionType.RESPOND,
                response="   ",
                intent=IntentType.GREETING,
                confidence=1.0,
            )

        errors = exc_info.value.errors()
        assert any("response" in str(error) for error in errors)

    def test_respond_with_invalid_confidence_should_fail(self):
        """测试：confidence 超出范围应该失败"""
        with pytest.raises(ValidationError):
            RespondPayload(
                action_type=ActionType.RESPOND,
                response="Hello",
                intent=IntentType.GREETING,
                confidence=1.5,  # 超出 [0, 1] 范围
            )

        with pytest.raises(ValidationError):
            RespondPayload(
                action_type=ActionType.RESPOND,
                response="Hello",
                intent=IntentType.GREETING,
                confidence=-0.1,  # 负数
            )


# ========================================
# CreateNodePayload 测试
# ========================================


class TestCreateNodePayload:
    """测试 CREATE_NODE 决策的 payload 验证"""

    def test_valid_http_node_payload_should_pass(self):
        """测试：有效的 HTTP 节点 payload 应该通过验证"""
        payload = CreateNodePayload(
            action_type=ActionType.CREATE_NODE,
            node_type=NodeType.HTTP,
            node_name="获取天气",
            config={"url": "https://api.weather.com", "method": "GET"},
            description="调用天气API",
        )

        assert payload.node_type == NodeType.HTTP
        assert payload.node_name == "获取天气"
        assert payload.config["url"] == "https://api.weather.com"

    def test_valid_llm_node_payload_should_pass(self):
        """测试：有效的 LLM 节点 payload 应该通过验证"""
        payload = CreateNodePayload(
            action_type=ActionType.CREATE_NODE,
            node_type=NodeType.LLM,
            node_name="数据分析",
            config={
                "model": "gpt-4",
                "prompt": "请分析数据",
                "temperature": 0.7,
            },
        )

        assert payload.node_type == NodeType.LLM
        assert payload.config["model"] == "gpt-4"

    def test_create_node_without_config_should_fail(self):
        """测试：缺少 config 的 CREATE_NODE 应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            CreateNodePayload(
                action_type=ActionType.CREATE_NODE,
                node_type=NodeType.HTTP,
                node_name="获取天气",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("config",) for error in errors)

    def test_create_node_with_empty_config_should_fail(self):
        """测试：空 config 的 CREATE_NODE 应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            CreateNodePayload(
                action_type=ActionType.CREATE_NODE,
                node_type=NodeType.HTTP,
                node_name="获取天气",
                config={},
            )

        errors = exc_info.value.errors()
        assert any("config" in str(error).lower() for error in errors)

    def test_create_node_with_empty_name_should_fail(self):
        """测试：空节点名称应该失败"""
        with pytest.raises(ValidationError):
            CreateNodePayload(
                action_type=ActionType.CREATE_NODE,
                node_type=NodeType.HTTP,
                node_name="",
                config={"url": "https://api.weather.com"},
            )


# ========================================
# CreateWorkflowPlanPayload 测试
# ========================================


class TestCreateWorkflowPlanPayload:
    """测试 CREATE_WORKFLOW_PLAN 决策的 payload 验证"""

    def test_valid_workflow_plan_should_pass(self):
        """测试：有效的工作流规划 payload 应该通过验证"""
        payload = CreateWorkflowPlanPayload(
            action_type=ActionType.CREATE_WORKFLOW_PLAN,
            name="数据分析工作流",
            description="获取并分析数据",
            nodes=[
                WorkflowNode(
                    node_id="node_1",
                    type=NodeType.HTTP,
                    name="获取数据",
                    config={"url": "https://api.data.com"},
                ),
                WorkflowNode(
                    node_id="node_2",
                    type=NodeType.LLM,
                    name="分析数据",
                    config={"model": "gpt-4", "prompt": "分析数据"},
                ),
            ],
            edges=[
                WorkflowEdge(source="node_1", target="node_2"),
            ],
        )

        assert payload.name == "数据分析工作流"
        assert len(payload.nodes) == 2
        assert len(payload.edges) == 1

    def test_workflow_plan_without_nodes_should_fail(self):
        """测试：没有节点的工作流规划应该失败"""
        with pytest.raises(ValidationError):
            CreateWorkflowPlanPayload(
                action_type=ActionType.CREATE_WORKFLOW_PLAN,
                name="空工作流",
                description="测试",
                nodes=[],
                edges=[],
            )

    def test_workflow_plan_with_duplicate_node_ids_should_fail(self):
        """测试：节点 ID 重复应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            CreateWorkflowPlanPayload(
                action_type=ActionType.CREATE_WORKFLOW_PLAN,
                name="工作流",
                description="测试",
                nodes=[
                    WorkflowNode(
                        node_id="node_1",
                        type=NodeType.HTTP,
                        name="节点1",
                        config={"url": "https://api.com"},
                    ),
                    WorkflowNode(
                        node_id="node_1",  # 重复 ID
                        type=NodeType.LLM,
                        name="节点2",
                        config={"model": "gpt-4", "prompt": "test"},
                    ),
                ],
                edges=[],
            )

        assert "唯一" in str(exc_info.value)

    def test_workflow_plan_with_invalid_edge_should_fail(self):
        """测试：边引用不存在的节点应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            CreateWorkflowPlanPayload(
                action_type=ActionType.CREATE_WORKFLOW_PLAN,
                name="工作流",
                description="测试",
                nodes=[
                    WorkflowNode(
                        node_id="node_1",
                        type=NodeType.HTTP,
                        name="节点1",
                        config={"url": "https://api.com"},
                    ),
                ],
                edges=[
                    WorkflowEdge(source="node_1", target="node_999"),  # node_999 不存在
                ],
            )

        assert "不存在" in str(exc_info.value)


# ========================================
# ExecuteWorkflowPayload 测试
# ========================================


class TestExecuteWorkflowPayload:
    """测试 EXECUTE_WORKFLOW 决策的 payload 验证"""

    def test_valid_execute_workflow_payload_should_pass(self):
        """测试：有效的执行工作流 payload 应该通过验证"""
        payload = ExecuteWorkflowPayload(
            action_type=ActionType.EXECUTE_WORKFLOW,
            workflow_id="workflow_123",
            input_params={"date_range": "last_3_months"},
            execution_mode="async",
            notify_on_completion=True,
        )

        assert payload.workflow_id == "workflow_123"
        assert payload.input_params["date_range"] == "last_3_months"
        assert payload.execution_mode == "async"

    def test_execute_workflow_without_workflow_id_should_fail(self):
        """测试：缺少 workflow_id 应该失败"""
        with pytest.raises(ValidationError):
            ExecuteWorkflowPayload(
                action_type=ActionType.EXECUTE_WORKFLOW,
            )

    def test_execute_workflow_with_empty_workflow_id_should_fail(self):
        """测试：空 workflow_id 应该失败"""
        with pytest.raises(ValidationError):
            ExecuteWorkflowPayload(
                action_type=ActionType.EXECUTE_WORKFLOW,
                workflow_id="",
            )


# ========================================
# RequestClarificationPayload 测试
# ========================================


class TestRequestClarificationPayload:
    """测试 REQUEST_CLARIFICATION 决策的 payload 验证"""

    def test_valid_clarification_payload_should_pass(self):
        """测试：有效的澄清请求 payload 应该通过验证"""
        payload = RequestClarificationPayload(
            action_type=ActionType.REQUEST_CLARIFICATION,
            question="您想分析哪个数据源？",
            options=["销售数据库", "用户行为日志"],
            required_fields=["data_source"],
        )

        assert payload.question == "您想分析哪个数据源？"
        assert len(payload.options) == 2

    def test_clarification_without_question_should_fail(self):
        """测试：缺少 question 应该失败"""
        with pytest.raises(ValidationError):
            RequestClarificationPayload(
                action_type=ActionType.REQUEST_CLARIFICATION,
            )

    def test_clarification_with_empty_options_should_fail(self):
        """测试：空 options 列表应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            RequestClarificationPayload(
                action_type=ActionType.REQUEST_CLARIFICATION,
                question="请选择",
                options=[],  # 空列表
            )

        assert "不能为空" in str(exc_info.value)


# ========================================
# ContinuePayload 测试
# ========================================


class TestContinuePayload:
    """测试 CONTINUE 决策的 payload 验证"""

    def test_valid_continue_payload_should_pass(self):
        """测试：有效的继续推理 payload 应该通过验证"""
        payload = ContinuePayload(
            action_type=ActionType.CONTINUE,
            thought="需要先确定数据范围",
            next_step="询问用户时间范围",
            progress=0.3,
        )

        assert payload.thought == "需要先确定数据范围"
        assert payload.progress == 0.3

    def test_continue_without_thought_should_fail(self):
        """测试：缺少 thought 应该失败"""
        with pytest.raises(ValidationError):
            ContinuePayload(
                action_type=ActionType.CONTINUE,
            )

    def test_continue_with_invalid_progress_should_fail(self):
        """测试：progress 超出范围应该失败"""
        with pytest.raises(ValidationError):
            ContinuePayload(
                action_type=ActionType.CONTINUE,
                thought="test",
                progress=1.5,  # 超出 [0, 1]
            )


# ========================================
# ModifyNodePayload 测试
# ========================================


class TestModifyNodePayload:
    """测试 MODIFY_NODE 决策的 payload 验证"""

    def test_valid_modify_node_payload_should_pass(self):
        """测试：有效的修改节点 payload 应该通过验证"""
        payload = ModifyNodePayload(
            action_type=ActionType.MODIFY_NODE,
            node_id="node_2",
            updates={"config.temperature": 0.9},
            reason="用户要求提高创造性",
        )

        assert payload.node_id == "node_2"
        assert payload.updates["config.temperature"] == 0.9

    def test_modify_node_without_updates_should_fail(self):
        """测试：缺少 updates 应该失败"""
        with pytest.raises(ValidationError):
            ModifyNodePayload(
                action_type=ActionType.MODIFY_NODE,
                node_id="node_2",
            )

    def test_modify_node_with_empty_updates_should_fail(self):
        """测试：空 updates 应该失败"""
        with pytest.raises(ValidationError):
            ModifyNodePayload(
                action_type=ActionType.MODIFY_NODE,
                node_id="node_2",
                updates={},
            )


# ========================================
# ErrorRecoveryPayload 测试
# ========================================


class TestErrorRecoveryPayload:
    """测试 ERROR_RECOVERY 决策的 payload 验证"""

    def test_valid_error_recovery_with_retry_should_pass(self):
        """测试：有效的错误恢复（RETRY）payload 应该通过验证"""
        payload = ErrorRecoveryPayload(
            action_type=ActionType.ERROR_RECOVERY,
            workflow_id="workflow_123",
            failed_node_id="node_1",
            failure_reason="HTTP timeout",
            error_code="TIMEOUT",
            recovery_plan=RecoveryPlan(
                action=RecoveryAction.RETRY,
                delay=5.0,
                max_attempts=3,
            ),
            execution_context={"retry_count": 1},
        )

        assert payload.recovery_plan.action == RecoveryAction.RETRY
        assert payload.recovery_plan.max_attempts == 3

    def test_error_recovery_retry_without_max_attempts_should_fail(self):
        """测试：RETRY 恢复计划缺少 max_attempts 应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            ErrorRecoveryPayload(
                action_type=ActionType.ERROR_RECOVERY,
                workflow_id="workflow_123",
                failed_node_id="node_1",
                failure_reason="timeout",
                recovery_plan=RecoveryPlan(
                    action=RecoveryAction.RETRY,
                    delay=5.0,
                    # 缺少 max_attempts
                ),
                execution_context={},
            )

        assert "max_attempts" in str(exc_info.value)

    def test_error_recovery_modify_without_modifications_should_fail(self):
        """测试：MODIFY 恢复计划缺少 modifications 应该失败"""
        with pytest.raises(ValidationError) as exc_info:
            ErrorRecoveryPayload(
                action_type=ActionType.ERROR_RECOVERY,
                workflow_id="workflow_123",
                failed_node_id="node_1",
                failure_reason="config error",
                recovery_plan=RecoveryPlan(
                    action=RecoveryAction.MODIFY,
                    # 缺少 modifications
                ),
                execution_context={},
            )

        assert "modifications" in str(exc_info.value)


# ========================================
# ReplanWorkflowPayload 测试
# ========================================


class TestReplanWorkflowPayload:
    """测试 REPLAN_WORKFLOW 决策的 payload 验证"""

    def test_valid_replan_workflow_payload_should_pass(self):
        """测试：有效的重新规划 payload 应该通过验证"""
        payload = ReplanWorkflowPayload(
            action_type=ActionType.REPLAN_WORKFLOW,
            workflow_id="workflow_123",
            reason="API持续超时",
            execution_context={"failed_attempts": 3},
            preserve_nodes=["node_2", "node_3"],
        )

        assert payload.workflow_id == "workflow_123"
        assert payload.reason == "API持续超时"

    def test_replan_workflow_without_reason_should_fail(self):
        """测试：缺少 reason 应该失败"""
        with pytest.raises(ValidationError):
            ReplanWorkflowPayload(
                action_type=ActionType.REPLAN_WORKFLOW,
                workflow_id="workflow_123",
                execution_context={},
            )


# ========================================
# SpawnSubagentPayload 测试
# ========================================


class TestSpawnSubagentPayload:
    """测试 SPAWN_SUBAGENT 决策的 payload 验证"""

    def test_valid_spawn_subagent_payload_should_pass(self):
        """测试：有效的生成子Agent payload 应该通过验证"""
        payload = SpawnSubagentPayload(
            action_type=ActionType.SPAWN_SUBAGENT,
            subagent_type="researcher",
            task_payload={"query": "machine learning papers"},
            priority=8,
            timeout=120.0,
        )

        assert payload.subagent_type == "researcher"
        assert payload.priority == 8

    def test_spawn_subagent_without_task_payload_should_fail(self):
        """测试：缺少 task_payload 应该失败"""
        with pytest.raises(ValidationError):
            SpawnSubagentPayload(
                action_type=ActionType.SPAWN_SUBAGENT,
                subagent_type="researcher",
            )

    def test_spawn_subagent_with_invalid_priority_should_fail(self):
        """测试：priority 超出范围应该失败"""
        with pytest.raises(ValidationError):
            SpawnSubagentPayload(
                action_type=ActionType.SPAWN_SUBAGENT,
                subagent_type="researcher",
                task_payload={"query": "test"},
                priority=15,  # 超出 [0, 10]
            )

    def test_spawn_subagent_with_negative_timeout_should_fail(self):
        """测试：负数 timeout 应该失败"""
        with pytest.raises(ValidationError):
            SpawnSubagentPayload(
                action_type=ActionType.SPAWN_SUBAGENT,
                subagent_type="researcher",
                task_payload={"query": "test"},
                timeout=-10.0,
            )


# ========================================
# 工厂函数测试
# ========================================


class TestCreatePayloadFromDict:
    """测试 create_payload_from_dict 工厂函数"""

    def test_create_respond_payload_from_dict_should_work(self):
        """测试：从字典创建 RespondPayload 应该成功"""
        payload_dict = {
            "action_type": "respond",
            "response": "Hello",
            "intent": "greeting",
            "confidence": 1.0,
        }

        payload = create_payload_from_dict("respond", payload_dict)

        assert isinstance(payload, RespondPayload)
        assert payload.response == "Hello"

    def test_create_create_node_payload_from_dict_should_work(self):
        """测试：从字典创建 CreateNodePayload 应该成功"""
        payload_dict = {
            "action_type": "create_node",
            "node_type": "HTTP",
            "node_name": "获取数据",
            "config": {"url": "https://api.com"},
        }

        payload = create_payload_from_dict("create_node", payload_dict)

        assert isinstance(payload, CreateNodePayload)
        assert payload.node_type == NodeType.HTTP

    def test_create_payload_with_invalid_action_type_should_fail(self):
        """测试：无效的 action_type 应该失败"""
        with pytest.raises(ValueError) as exc_info:
            create_payload_from_dict("invalid_action", {})

        assert "未知的 action_type" in str(exc_info.value)

    def test_create_payload_with_invalid_data_should_fail(self):
        """测试：无效的数据应该失败"""
        with pytest.raises(ValidationError):
            create_payload_from_dict(
                "respond",
                {
                    "action_type": "respond",
                    # 缺少必填字段
                },
            )


# ========================================
# NodeConfig 子类验证器测试
# ========================================


class TestNodeConfigValidators:
    """测试各种 NodeConfig 子类的 Pydantic 验证器"""

    def test_llm_node_config_missing_both_prompt_and_messages_should_fail(self):
        """测试：LLMNodeConfig 缺少 prompt 和 messages 应该失败 (lines 166-168)"""
        from src.domain.agents.decision_payload import LLMNodeConfig

        with pytest.raises(ValidationError) as exc_info:
            LLMNodeConfig(
                model="gpt-4",
                temperature=0.7,
                max_tokens=1000,
                # 故意不提供 prompt 和 messages
            )

        assert "prompt 或 messages 必须提供其中之一" in str(exc_info.value)

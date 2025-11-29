"""RED 测试：WorkflowAction 值对象 - 工作流动作模型

TDD RED 阶段：定义 WorkflowAction、LLMResponse 和 WorkflowExecutionContext 的期望行为

测试场景：
1. ActionType 枚举 - REASON, EXECUTE_NODE, WAIT, FINISH, ERROR_RECOVERY
2. WorkflowAction 字段验证 - 必填字段, 类型检查, 枚举约束
3. 自定义验证器 - node_id 为 EXECUTE_NODE 时必填, reasoning 为 REASON 时必填
4. LLMResponse 模型 - 捕获原始内容和解析状态
5. WorkflowExecutionContext - 跟踪执行状态和可用节点
"""

import pytest
from pydantic import ValidationError

from src.domain.value_objects.workflow_action import (
    ActionType,
    LLMResponse,
    WorkflowAction,
    WorkflowExecutionContext,
)


class TestActionTypeEnum:
    """测试：ActionType 枚举定义"""

    def test_action_type_has_reason(self):
        """RED：ActionType 应该有 REASON 成员"""
        assert hasattr(ActionType, "REASON")
        assert ActionType.REASON == "reason"

    def test_action_type_has_execute_node(self):
        """RED：ActionType 应该有 EXECUTE_NODE 成员"""
        assert hasattr(ActionType, "EXECUTE_NODE")
        assert ActionType.EXECUTE_NODE == "execute_node"

    def test_action_type_has_wait(self):
        """RED：ActionType 应该有 WAIT 成员"""
        assert hasattr(ActionType, "WAIT")
        assert ActionType.WAIT == "wait"

    def test_action_type_has_finish(self):
        """RED：ActionType 应该有 FINISH 成员"""
        assert hasattr(ActionType, "FINISH")
        assert ActionType.FINISH == "finish"

    def test_action_type_has_error_recovery(self):
        """RED：ActionType 应该有 ERROR_RECOVERY 成员"""
        assert hasattr(ActionType, "ERROR_RECOVERY")
        assert ActionType.ERROR_RECOVERY == "error_recovery"


class TestWorkflowActionCreation:
    """测试：WorkflowAction 创建和基本验证"""

    def test_workflow_action_can_be_created_with_reason_type(self):
        """RED：应该能用 REASON 类型创建 WorkflowAction"""
        action = WorkflowAction(
            type=ActionType.REASON,
            reasoning="分析当前状态",
        )

        assert action.type == ActionType.REASON
        assert action.reasoning == "分析当前状态"
        assert action.node_id is None
        assert action.params == {}
        assert action.retry_count == 0

    def test_workflow_action_can_be_created_with_execute_node_type(self):
        """RED：应该能用 EXECUTE_NODE 类型创建 WorkflowAction"""
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_123",
            params={"key": "value"},
        )

        assert action.type == ActionType.EXECUTE_NODE
        assert action.node_id == "node_123"
        assert action.params == {"key": "value"}

    def test_workflow_action_can_be_created_with_wait_type(self):
        """RED：应该能用 WAIT 类型创建 WorkflowAction"""
        action = WorkflowAction(
            type=ActionType.WAIT,
            reasoning="等待外部输入",
        )

        assert action.type == ActionType.WAIT
        assert action.reasoning == "等待外部输入"

    def test_workflow_action_can_be_created_with_finish_type(self):
        """RED：应该能用 FINISH 类型创建 WorkflowAction"""
        action = WorkflowAction(
            type=ActionType.FINISH,
            reasoning="工作流完成",
        )

        assert action.type == ActionType.FINISH
        assert action.reasoning == "工作流完成"

    def test_workflow_action_can_be_created_with_error_recovery_type(self):
        """RED：应该能用 ERROR_RECOVERY 类型创建 WorkflowAction"""
        action = WorkflowAction(
            type=ActionType.ERROR_RECOVERY,
            node_id="node_failed",
            reasoning="节点失败，需要恢复",
        )

        assert action.type == ActionType.ERROR_RECOVERY
        assert action.node_id == "node_failed"
        assert action.reasoning == "节点失败，需要恢复"


class TestWorkflowActionValidation:
    """测试：WorkflowAction 字段级验证"""

    def test_workflow_action_requires_type(self):
        """RED：WorkflowAction 类型字段是必填的"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowAction()  # type: ignore

        assert "type" in str(exc_info.value)

    def test_workflow_action_rejects_invalid_type(self):
        """RED：WorkflowAction 不接受无效的 ActionType 值"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowAction(type="invalid_type")  # type: ignore

        assert "type" in str(exc_info.value)

    def test_workflow_action_retry_count_must_be_non_negative(self):
        """RED：retry_count 必须非负"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowAction(
                type=ActionType.REASON,
                retry_count=-1,  # type: ignore
            )

        assert "retry_count" in str(exc_info.value)

    def test_workflow_action_params_defaults_to_empty_dict(self):
        """RED：params 应该默认为空字典"""
        action = WorkflowAction(type=ActionType.REASON)

        assert action.params == {}
        assert isinstance(action.params, dict)

    def test_workflow_action_retry_count_defaults_to_zero(self):
        """RED：retry_count 应该默认为 0"""
        action = WorkflowAction(type=ActionType.REASON)

        assert action.retry_count == 0

    def test_workflow_action_can_have_all_optional_fields(self):
        """RED：WorkflowAction 应该接受所有可选字段"""
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_456",
            reasoning="执行节点",
            params={"timeout": 30, "retry": True},
            retry_count=2,
        )

        assert action.node_id == "node_456"
        assert action.reasoning == "执行节点"
        assert action.params == {"timeout": 30, "retry": True}
        assert action.retry_count == 2


class TestWorkflowActionCustomValidators:
    """测试：WorkflowAction 自定义验证器"""

    def test_execute_node_requires_node_id(self):
        """RED：EXECUTE_NODE 类型必须提供 node_id"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowAction(
                type=ActionType.EXECUTE_NODE,
                node_id=None,
            )

        error_str = str(exc_info.value)
        assert "node_id" in error_str

    def test_execute_node_accepts_node_id(self):
        """RED：EXECUTE_NODE 类型可以包含有效的 node_id"""
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="valid_node",
        )

        assert action.node_id == "valid_node"

    def test_reason_action_can_have_reasoning(self):
        """RED：REASON 类型应该能有 reasoning 字段"""
        action = WorkflowAction(
            type=ActionType.REASON,
            reasoning="这是我的推理",
        )

        assert action.reasoning == "这是我的推理"

    def test_reason_action_without_reasoning_is_valid(self):
        """RED：REASON 类型 reasoning 字段是可选的"""
        action = WorkflowAction(
            type=ActionType.REASON,
            reasoning=None,
        )

        assert action.reasoning is None

    def test_wait_action_accepts_reasoning(self):
        """RED：WAIT 类型应该能有 reasoning"""
        action = WorkflowAction(
            type=ActionType.WAIT,
            reasoning="等待用户输入",
        )

        assert action.reasoning == "等待用户输入"

    def test_error_recovery_accepts_node_id_and_reasoning(self):
        """RED：ERROR_RECOVERY 类型可以同时有 node_id 和 reasoning"""
        action = WorkflowAction(
            type=ActionType.ERROR_RECOVERY,
            node_id="failed_node",
            reasoning="节点执行失败，尝试恢复",
        )

        assert action.node_id == "failed_node"
        assert action.reasoning == "节点执行失败，尝试恢复"


class TestWorkflowActionJSONSerialization:
    """测试：WorkflowAction JSON 序列化和反序列化"""

    def test_workflow_action_can_be_serialized_to_dict(self):
        """RED：WorkflowAction 应该能转换为字典"""
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_123",
            params={"key": "value"},
        )

        data = action.model_dump()

        assert data["type"] == "execute_node"
        assert data["node_id"] == "node_123"
        assert data["params"] == {"key": "value"}

    def test_workflow_action_can_be_serialized_to_json(self):
        """RED：WorkflowAction 应该能序列化为 JSON 字符串"""
        action = WorkflowAction(
            type=ActionType.REASON,
            reasoning="推理中",
        )

        json_str = action.model_dump_json()

        assert "reason" in json_str
        assert "推理中" in json_str

    def test_workflow_action_can_be_deserialized_from_dict(self):
        """RED：WorkflowAction 应该能从字典反序列化"""
        data = {
            "type": "execute_node",
            "node_id": "node_789",
            "params": {"timeout": 60},
        }

        action = WorkflowAction(**data)

        assert action.type == ActionType.EXECUTE_NODE
        assert action.node_id == "node_789"
        assert action.params == {"timeout": 60}

    def test_workflow_action_can_be_deserialized_from_json(self):
        """RED：WorkflowAction 应该能从 JSON 字符串反序列化"""
        json_str = '{"type": "reason", "reasoning": "thinking"}'

        action = WorkflowAction.model_validate_json(json_str)

        assert action.type == ActionType.REASON
        assert action.reasoning == "thinking"


class TestLLMResponseModel:
    """测试：LLMResponse 模型"""

    def test_llm_response_can_be_created_with_raw_content(self):
        """RED：应该能用原始内容创建 LLMResponse"""
        response = LLMResponse(raw_content='{"type": "reason"}')

        assert response.raw_content == '{"type": "reason"}'
        assert response.action is None
        assert response.is_valid is False
        assert response.parse_attempt == 1

    def test_llm_response_can_be_created_with_parsed_action(self):
        """RED：应该能创建包含解析后 action 的 LLMResponse"""
        action = WorkflowAction(type=ActionType.REASON, reasoning="thinking")
        response = LLMResponse(
            raw_content='{"type": "reason", "reasoning": "thinking"}',
            action=action,
            is_valid=True,
        )

        assert response.action == action
        assert response.is_valid is True

    def test_llm_response_can_have_error_message(self):
        """RED：LLMResponse 应该能包含错误信息"""
        response = LLMResponse(
            raw_content="invalid json",
            is_valid=False,
            error_message="JSON 解析失败: 无效的 JSON 格式",
        )

        assert response.error_message == "JSON 解析失败: 无效的 JSON 格式"

    def test_llm_response_parse_attempt_tracks_retries(self):
        """RED：parse_attempt 应该跟踪重试次数"""
        response = LLMResponse(
            raw_content="content",
            parse_attempt=3,
        )

        assert response.parse_attempt == 3

    def test_llm_response_parse_attempt_must_be_positive(self):
        """RED：parse_attempt 必须是正整数"""
        with pytest.raises(ValidationError) as exc_info:
            LLMResponse(
                raw_content="content",
                parse_attempt=0,  # type: ignore
            )

        assert "parse_attempt" in str(exc_info.value)

    def test_llm_response_defaults(self):
        """RED：LLMResponse 字段应该有正确的默认值"""
        response = LLMResponse(raw_content="test")

        assert response.action is None
        assert response.is_valid is False
        assert response.error_message is None
        assert response.parse_attempt == 1


class TestWorkflowExecutionContextModel:
    """测试：WorkflowExecutionContext 模型"""

    def test_workflow_execution_context_can_be_created(self):
        """RED：应该能创建 WorkflowExecutionContext"""
        context = WorkflowExecutionContext(
            workflow_id="wf_123",
            workflow_name="数据处理",
            available_nodes=["node_1", "node_2", "node_3"],
        )

        assert context.workflow_id == "wf_123"
        assert context.workflow_name == "数据处理"
        assert context.available_nodes == ["node_1", "node_2", "node_3"]
        assert context.executed_nodes == {}
        assert context.current_step == 0
        assert context.max_steps == 50

    def test_workflow_execution_context_tracks_executed_nodes(self):
        """RED：WorkflowExecutionContext 应该跟踪已执行的节点"""
        context = WorkflowExecutionContext(
            workflow_id="wf_456",
            workflow_name="测试",
            available_nodes=["a", "b", "c"],
            executed_nodes={"a": {"status": "success", "result": "data"}},
        )

        assert "a" in context.executed_nodes
        assert context.executed_nodes["a"]["status"] == "success"

    def test_workflow_execution_context_current_step_defaults_to_zero(self):
        """RED：current_step 应该默认为 0"""
        context = WorkflowExecutionContext(
            workflow_id="wf",
            workflow_name="test",
            available_nodes=[],
        )

        assert context.current_step == 0

    def test_workflow_execution_context_max_steps_defaults_to_50(self):
        """RED：max_steps 应该默认为 50"""
        context = WorkflowExecutionContext(
            workflow_id="wf",
            workflow_name="test",
            available_nodes=[],
        )

        assert context.max_steps == 50

    def test_workflow_execution_context_requires_workflow_id(self):
        """RED：workflow_id 是必填字段"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowExecutionContext(
                workflow_name="test",
                available_nodes=[],
            )  # type: ignore

        assert "workflow_id" in str(exc_info.value)

    def test_workflow_execution_context_requires_workflow_name(self):
        """RED：workflow_name 是必填字段"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowExecutionContext(
                workflow_id="wf_123",
                available_nodes=[],
            )  # type: ignore

        assert "workflow_name" in str(exc_info.value)

    def test_workflow_execution_context_requires_available_nodes(self):
        """RED：available_nodes 是必填字段"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowExecutionContext(
                workflow_id="wf_123",
                workflow_name="test",
            )  # type: ignore

        assert "available_nodes" in str(exc_info.value)

    def test_workflow_execution_context_current_step_must_be_non_negative(self):
        """RED：current_step 必须非负"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowExecutionContext(
                workflow_id="wf",
                workflow_name="test",
                available_nodes=[],
                current_step=-1,  # type: ignore
            )

        assert "current_step" in str(exc_info.value)

    def test_workflow_execution_context_max_steps_must_be_positive(self):
        """RED：max_steps 必须是正整数"""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowExecutionContext(
                workflow_id="wf",
                workflow_name="test",
                available_nodes=[],
                max_steps=0,  # type: ignore
            )

        assert "max_steps" in str(exc_info.value)

    def test_workflow_execution_context_can_track_multiple_nodes(self):
        """RED：ExecutionContext 应该能跟踪多个已执行节点"""
        context = WorkflowExecutionContext(
            workflow_id="wf",
            workflow_name="test",
            available_nodes=["n1", "n2", "n3"],
            executed_nodes={
                "n1": {"status": "success"},
                "n2": {"status": "failed", "error": "timeout"},
            },
        )

        assert len(context.executed_nodes) == 2
        assert "n1" in context.executed_nodes
        assert "n2" in context.executed_nodes
        assert context.executed_nodes["n2"]["error"] == "timeout"

"""RED 测试：WorkflowActionValidator 服务 - 工作流动作验证

TDD RED 阶段：定义 WorkflowActionValidator 的业务规则验证

验证规则：
1. 节点存在验证 - 节点必须在 available_nodes 中
2. 重复执行检查 - 同一个节点不能被执行多次（在同一个工作流中）
3. 步骤限制 - 当前步骤不能超过 max_steps
4. 节点 ID 格式 - node_id 必须符合格式
5. 错误消息格式化 - 验证失败时返回用户友好的错误消息
"""

import pytest
from pydantic import ValidationError

from src.domain.services.workflow_action_validator import (
    ValidationResult,
    WorkflowActionValidator,
)
from src.domain.value_objects.workflow_action import (
    ActionType,
    WorkflowAction,
    WorkflowExecutionContext,
)


class TestWorkflowActionValidatorBasics:
    """测试：WorkflowActionValidator 基础功能"""

    def test_workflow_action_validator_can_be_created(self):
        """RED：应该能创建 WorkflowActionValidator 实例"""
        validator = WorkflowActionValidator()

        assert validator is not None

    def test_workflow_action_validator_has_validate_method(self):
        """RED：WorkflowActionValidator 应该有 validate 方法"""
        validator = WorkflowActionValidator()

        assert hasattr(validator, "validate")
        assert callable(validator.validate)

    def test_validation_result_has_is_valid_field(self):
        """RED：ValidationResult 应该有 is_valid 字段"""
        # 这个测试验证 ValidationResult 类型存在并有预期的结构
        # 实际验证会在下面的测试中进行
        assert ValidationResult is not None


class TestWorkflowActionValidatorForReasonType:
    """测试：REASON 类型的验证"""

    def test_reason_action_is_always_valid(self):
        """RED：REASON 类型动作总是有效的（不需要节点验证）"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.REASON,
            reasoning="分析当前状态",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = validator.validate(action, context)

        assert result.is_valid is True

    def test_reason_action_without_reasoning_is_valid(self):
        """RED：REASON 类型即使没有 reasoning 也有效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(type=ActionType.REASON)
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = validator.validate(action, context)

        assert result.is_valid is True


class TestWorkflowActionValidatorForExecuteNodeType:
    """测试：EXECUTE_NODE 类型的验证"""

    def test_execute_node_with_valid_node_id_is_valid(self):
        """RED：EXECUTE_NODE 如果 node_id 在 available_nodes 中，应该有效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_a",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
        )

        result = validator.validate(action, context)

        assert result.is_valid is True

    def test_execute_node_with_nonexistent_node_id_is_invalid(self):
        """RED：EXECUTE_NODE 如果 node_id 不在 available_nodes 中，应该无效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="nonexistent",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
        )

        result = validator.validate(action, context)

        assert result.is_valid is False
        assert "nonexistent" in result.error_message or "节点" in result.error_message

    def test_execute_node_without_node_id_is_invalid(self):
        """RED：EXECUTE_NODE 如果没有 node_id，应该无效"""
        # 注意：这个验证在 Pydantic 级别进行，不需要通过 validator service

        with pytest.raises(ValidationError) as exc_info:
            WorkflowAction(
                type=ActionType.EXECUTE_NODE,
                node_id=None,
            )

        assert "node_id" in str(exc_info.value)

    def test_execute_node_with_empty_string_node_id_is_invalid(self):
        """RED：EXECUTE_NODE 如果 node_id 是空字符串，应该无效"""
        # 注意：这个验证在 Pydantic 级别进行

        with pytest.raises(ValidationError) as exc_info:
            WorkflowAction(
                type=ActionType.EXECUTE_NODE,
                node_id="",
            )

        assert "node_id" in str(exc_info.value)


class TestWorkflowActionValidatorDuplicateExecution:
    """测试：防止重复执行同一个节点"""

    def test_execute_node_not_in_executed_nodes_is_valid(self):
        """RED：如果节点还没被执行过，应该能执行"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_a",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
            executed_nodes={},  # node_a 还没被执行
        )

        result = validator.validate(action, context)

        assert result.is_valid is True

    def test_execute_node_already_in_executed_nodes_is_invalid(self):
        """RED：如果节点已经被执行过，应该无法再执行"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_a",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
            executed_nodes={"node_a": {"status": "success", "result": "data"}},
        )

        result = validator.validate(action, context)

        assert result.is_valid is False
        assert "node_a" in result.error_message or "已执行" in result.error_message

    def test_execute_node_with_multiple_executed_nodes(self):
        """RED：在多个已执行节点的情况下，应该检查重复"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_b",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b", "node_c"],
            executed_nodes={
                "node_a": {"status": "success"},
                "node_b": {"status": "failed"},
            },
        )

        result = validator.validate(action, context)

        assert result.is_valid is False


class TestWorkflowActionValidatorStepLimit:
    """测试：步骤限制验证"""

    def test_action_within_step_limit_is_valid(self):
        """RED：当前步骤在限制范围内的动作应该有效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.REASON,
            reasoning="thinking",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
            current_step=10,
            max_steps=50,
        )

        result = validator.validate(action, context)

        assert result.is_valid is True

    def test_action_at_step_limit_boundary_is_valid(self):
        """RED：恰好在步骤限制边界的动作应该有效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(type=ActionType.REASON)
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
            current_step=50,
            max_steps=50,
        )

        result = validator.validate(action, context)

        assert result.is_valid is True

    def test_action_exceeding_step_limit_is_invalid(self):
        """RED：超过步骤限制的动作应该无效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(type=ActionType.REASON)
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
            current_step=51,
            max_steps=50,
        )

        result = validator.validate(action, context)

        assert result.is_valid is False
        assert "步骤" in result.error_message or "limit" in result.error_message


class TestWorkflowActionValidatorForWaitType:
    """测试：WAIT 类型的验证"""

    def test_wait_action_is_always_valid(self):
        """RED：WAIT 类型动作总是有效的"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.WAIT,
            reasoning="等待外部输入",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = validator.validate(action, context)

        assert result.is_valid is True

    def test_wait_action_without_reasoning_is_valid(self):
        """RED：WAIT 类型即使没有 reasoning 也有效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(type=ActionType.WAIT)
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = validator.validate(action, context)

        assert result.is_valid is True


class TestWorkflowActionValidatorForFinishType:
    """测试：FINISH 类型的验证"""

    def test_finish_action_is_always_valid(self):
        """RED：FINISH 类型动作总是有效的"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.FINISH,
            reasoning="工作流完成",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = validator.validate(action, context)

        assert result.is_valid is True


class TestWorkflowActionValidatorForErrorRecoveryType:
    """测试：ERROR_RECOVERY 类型的验证"""

    def test_error_recovery_with_valid_node_id_is_valid(self):
        """RED：ERROR_RECOVERY 如果 node_id 有效，应该有效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.ERROR_RECOVERY,
            node_id="node_a",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = validator.validate(action, context)

        assert result.is_valid is True

    def test_error_recovery_with_nonexistent_node_id_is_invalid(self):
        """RED：ERROR_RECOVERY 如果 node_id 不存在，应该无效"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.ERROR_RECOVERY,
            node_id="nonexistent",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = validator.validate(action, context)

        assert result.is_valid is False

    def test_error_recovery_without_node_id_is_invalid(self):
        """RED：ERROR_RECOVERY 如果没有 node_id，应该无效"""
        # 注意：这个验证在 Pydantic 级别进行

        with pytest.raises(ValidationError) as exc_info:
            WorkflowAction(
                type=ActionType.ERROR_RECOVERY,
                node_id=None,
            )

        assert "node_id" in str(exc_info.value)


class TestWorkflowActionValidatorErrorMessages:
    """测试：验证失败时的错误消息"""

    def test_error_message_is_user_friendly(self):
        """RED：错误消息应该是用户友好的"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="nonexistent",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
        )

        result = validator.validate(action, context)

        # 错误消息应该是字符串，不是空的
        assert isinstance(result.error_message, str)
        assert len(result.error_message) > 0
        # 应该包含有用的信息
        assert "nonexistent" in result.error_message or "节点" in result.error_message

    def test_error_message_for_duplicate_execution(self):
        """RED：重复执行的错误消息应该清晰"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="node_a",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
            executed_nodes={"node_a": {"status": "success"}},
        )

        result = validator.validate(action, context)

        assert "node_a" in result.error_message or "已" in result.error_message

    def test_error_message_for_step_limit(self):
        """RED：步骤超限的错误消息应该清晰"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(type=ActionType.REASON)
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
            current_step=51,
            max_steps=50,
        )

        result = validator.validate(action, context)

        assert result.error_message is not None
        assert len(result.error_message) > 0


class TestWorkflowActionValidatorComplexScenarios:
    """测试：复杂验证场景"""

    def test_validate_multiple_nodes_in_sequence(self):
        """RED：应该能验证多个动作的序列"""
        validator = WorkflowActionValidator()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b", "node_c"],
        )

        # 第一个动作应该有效
        action1 = WorkflowAction(type=ActionType.REASON)
        result1 = validator.validate(action1, context)
        assert result1.is_valid is True

        # 执行第一个节点
        action2 = WorkflowAction(type=ActionType.EXECUTE_NODE, node_id="node_a")
        result2 = validator.validate(action2, context)
        assert result2.is_valid is True

        # 更新上下文（模拟节点已执行）
        context.executed_nodes["node_a"] = {"status": "success"}

        # 重新执行同一个节点应该失败
        result3 = validator.validate(action2, context)
        assert result3.is_valid is False

    def test_validation_with_empty_available_nodes(self):
        """RED：当没有可用节点时，执行节点动作应该失败"""
        validator = WorkflowActionValidator()
        action = WorkflowAction(
            type=ActionType.EXECUTE_NODE,
            node_id="any_node",
        )
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],  # 没有可用节点
        )

        result = validator.validate(action, context)

        assert result.is_valid is False

    def test_validation_respects_current_step_progression(self):
        """RED：验证器应该能处理递增的 current_step"""
        validator = WorkflowActionValidator()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
            current_step=48,
            max_steps=50,
        )

        # 步骤 48 应该有效
        action = WorkflowAction(type=ActionType.REASON)
        result1 = validator.validate(action, context)
        assert result1.is_valid is True

        # 步骤 49 应该有效
        context.current_step = 49
        result2 = validator.validate(action, context)
        assert result2.is_valid is True

        # 步骤 50 应该有效（边界）
        context.current_step = 50
        result3 = validator.validate(action, context)
        assert result3.is_valid is True

        # 步骤 51 应该无效
        context.current_step = 51
        result4 = validator.validate(action, context)
        assert result4.is_valid is False

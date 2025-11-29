"""WorkflowActionValidator 服务 - 工作流动作业务规则验证

职责：
1. 验证 WorkflowAction 是否符合业务规则
2. 检查节点是否存在于工作流中
3. 防止同一节点被执行多次
4. 检查步骤数是否超过限制
5. 生成用户友好的错误消息

这是应用层的验证服务，在 Pydantic 字段级验证之后进行。
"""

from dataclasses import dataclass

from src.domain.value_objects.workflow_action import (
    ActionType,
    WorkflowAction,
    WorkflowExecutionContext,
)


@dataclass
class ValidationResult:
    """验证结果

    属性：
    - is_valid: 验证是否通过
    - error_message: 验证失败时的错误消息
    """

    is_valid: bool
    error_message: str | None = None


class WorkflowActionValidator:
    """工作流动作验证器"""

    def validate(
        self,
        action: WorkflowAction,
        context: WorkflowExecutionContext,
    ) -> ValidationResult:
        """验证工作流动作

        参数：
            action: 工作流动作
            context: 执行上下文

        返回：
            验证结果
        """
        # 检查步骤限制
        if context.current_step > context.max_steps:
            return ValidationResult(
                is_valid=False,
                error_message=f"工作流已超过最大步骤数限制（当前：{context.current_step}，最大：{context.max_steps}）",
            )

        # 根据动作类型进行验证
        if action.type == ActionType.EXECUTE_NODE:
            return self._validate_execute_node(action, context)
        elif action.type == ActionType.ERROR_RECOVERY:
            return self._validate_error_recovery(action, context)
        elif action.type in (ActionType.REASON, ActionType.WAIT, ActionType.FINISH):
            # 这些类型总是有效的（不需要特殊验证）
            return ValidationResult(is_valid=True)

        # 未知的动作类型
        return ValidationResult(
            is_valid=False,
            error_message=f"未知的动作类型：{action.type}",
        )

    def _validate_execute_node(
        self,
        action: WorkflowAction,
        context: WorkflowExecutionContext,
    ) -> ValidationResult:
        """验证 EXECUTE_NODE 动作

        参数：
            action: 工作流动作
            context: 执行上下文

        返回：
            验证结果
        """
        # 检查 node_id 是否提供
        if not action.node_id:
            return ValidationResult(
                is_valid=False,
                error_message="EXECUTE_NODE 动作必须提供 node_id",
            )

        # 检查 node_id 是否为空字符串
        if action.node_id.strip() == "":
            return ValidationResult(
                is_valid=False,
                error_message="node_id 不能是空字符串",
            )

        # 检查节点是否存在
        if action.node_id not in context.available_nodes:
            available = ", ".join(context.available_nodes) if context.available_nodes else "无"
            return ValidationResult(
                is_valid=False,
                error_message=f"节点 '{action.node_id}' 不存在。可用节点：{available}",
            )

        # 检查是否重复执行
        if action.node_id in context.executed_nodes:
            return ValidationResult(
                is_valid=False,
                error_message=f"节点 '{action.node_id}' 已被执行过，不能重复执行",
            )

        return ValidationResult(is_valid=True)

    def _validate_error_recovery(
        self,
        action: WorkflowAction,
        context: WorkflowExecutionContext,
    ) -> ValidationResult:
        """验证 ERROR_RECOVERY 动作

        参数：
            action: 工作流动作
            context: 执行上下文

        返回：
            验证结果
        """
        # 检查 node_id 是否提供
        if not action.node_id:
            return ValidationResult(
                is_valid=False,
                error_message="ERROR_RECOVERY 动作必须提供 node_id",
            )

        # 检查节点是否存在
        if action.node_id not in context.available_nodes:
            available = ", ".join(context.available_nodes) if context.available_nodes else "无"
            return ValidationResult(
                is_valid=False,
                error_message=f"节点 '{action.node_id}' 不存在。可用节点：{available}",
            )

        return ValidationResult(is_valid=True)

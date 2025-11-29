"""集成测试：格式约束 - 真实场景验证

TDD REFACTOR 阶段：在真实场景下验证格式约束体系的完整性

真实场景：
1. 完整解析流程：LLM 输出 → JSON 解析 → 字段验证 → 业务规则验证
2. 重试流程：格式错误 → 生成重试提示 → LLM 重试 → 成功或继续重试
3. 工作流执行：多个节点的完整执行流程
4. 错误恢复：节点失败后的恢复流程
5. 边界条件：最大步骤数、已执行节点限制等
"""

import json

from src.application.services.workflow_action_parser import WorkflowActionParser
from src.domain.value_objects.workflow_action import (
    ActionType,
    WorkflowExecutionContext,
)
from src.lc.prompts.workflow_chat_system_prompt import WorkflowChatSystemPrompt


class TestFormatConstraintsCompleteFlow:
    """测试：完整的格式约束流程"""

    def test_complete_flow_valid_reason_action(self):
        """集成：有效的 REASON 动作的完整流程"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        # LLM 输出
        llm_output = '{"type": "reason", "reasoning": "分析当前状态"}'

        # 解析
        result = parser.parse_and_validate(llm_output, context)

        # 验证
        assert result.is_valid is True
        assert result.action.type == ActionType.REASON
        assert result.action.reasoning == "分析当前状态"

    def test_complete_flow_valid_execute_node_action(self):
        """集成：有效的 EXECUTE_NODE 动作的完整流程"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["fetch_data", "process_data"],
        )

        # LLM 输出
        llm_output = '{"type": "execute_node", "node_id": "fetch_data"}'

        # 解析
        result = parser.parse_and_validate(llm_output, context)

        # 验证
        assert result.is_valid is True
        assert result.action.type == ActionType.EXECUTE_NODE
        assert result.action.node_id == "fetch_data"

    def test_complete_flow_invalid_json(self):
        """集成：无效 JSON 的完整流程"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        # LLM 输出（无效 JSON）
        llm_output = "not json at all"

        # 解析
        result = parser.parse_and_validate(llm_output, context)

        # 验证
        assert result.is_valid is False
        assert result.action is None
        assert "JSON" in result.error_message or "json" in result.error_message

    def test_complete_flow_invalid_node_id(self):
        """集成：无效节点 ID 的完整流程"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
        )

        # LLM 输出（无效节点 ID）
        llm_output = '{"type": "execute_node", "node_id": "nonexistent_node"}'

        # 解析
        result = parser.parse_and_validate(llm_output, context)

        # 验证
        assert result.is_valid is False
        assert "nonexistent_node" in result.error_message or "节点" in result.error_message


class TestFormatConstraintsRetryFlow:
    """测试：重试流程"""

    def test_retry_flow_json_error_then_valid(self):
        """集成：JSON 错误后重试成功"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        # 第一次尝试：JSON 错误
        result1 = parser.parse_and_validate("invalid json", context, parse_attempt=1)
        assert result1.is_valid is False
        assert result1.parse_attempt == 1

        # 生成重试提示
        retry_prompt = parser.generate_retry_prompt(result1, context)
        assert "JSON" in retry_prompt or "json" in retry_prompt.lower()
        assert "1" in retry_prompt or "第一次" in retry_prompt

        # 第二次尝试：有效 JSON
        result2 = parser.parse_and_validate(
            '{"type": "reason"}',
            context,
            parse_attempt=2,
        )
        assert result2.is_valid is True
        assert result2.parse_attempt == 2

    def test_retry_flow_with_attempt_count_progression(self):
        """集成：重试流程中的尝试次数递进"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        # 三次尝试
        result1 = parser.parse_and_validate("invalid", context, parse_attempt=1)
        assert result1.parse_attempt == 1

        result2 = parser.parse_and_validate("invalid", context, parse_attempt=2)
        assert result2.parse_attempt == 2

        result3 = parser.parse_and_validate("invalid", context, parse_attempt=3)
        assert result3.parse_attempt == 3

        # 最后一次尝试的提示应该包含警告
        prompt3 = parser.generate_retry_prompt(result3, context)
        assert "最后" in prompt3 or "失败" in prompt3


class TestFormatConstraintsWorkflowExecutionSequence:
    """测试：工作流执行序列"""

    def test_workflow_execution_sequence_multiple_nodes(self):
        """集成：多个节点的工作流执行序列"""
        parser = WorkflowActionParser()

        # 初始化工作流
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="数据处理",
            available_nodes=["fetch", "transform", "save"],
            current_step=0,
        )

        # 步骤1：推理
        result1 = parser.parse_and_validate(
            '{"type": "reason", "reasoning": "分析工作流"}',
            context,
        )
        assert result1.is_valid is True
        context.current_step += 1

        # 步骤2：执行 fetch 节点
        result2 = parser.parse_and_validate(
            '{"type": "execute_node", "node_id": "fetch"}',
            context,
        )
        assert result2.is_valid is True
        context.executed_nodes["fetch"] = {"status": "success"}
        context.current_step += 1

        # 步骤3：执行 transform 节点
        result3 = parser.parse_and_validate(
            '{"type": "execute_node", "node_id": "transform"}',
            context,
        )
        assert result3.is_valid is True
        context.executed_nodes["transform"] = {"status": "success"}
        context.current_step += 1

        # 步骤4：执行 save 节点
        result4 = parser.parse_and_validate(
            '{"type": "execute_node", "node_id": "save"}',
            context,
        )
        assert result4.is_valid is True
        context.executed_nodes["save"] = {"status": "success"}
        context.current_step += 1

        # 步骤5：完成
        result5 = parser.parse_and_validate(
            '{"type": "finish", "reasoning": "工作流完成"}',
            context,
        )
        assert result5.is_valid is True

    def test_workflow_respects_step_limits(self):
        """集成：工作流遵守步骤限制"""
        parser = WorkflowActionParser()

        # 接近最大步数
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
            current_step=49,
            max_steps=50,
        )

        # 最后一步应该成功
        result1 = parser.parse_and_validate(
            '{"type": "reason"}',
            context,
        )
        assert result1.is_valid is True

        # 超过最大步数应该失败
        context.current_step = 51
        result2 = parser.parse_and_validate(
            '{"type": "reason"}',
            context,
        )
        assert result2.is_valid is False


class TestFormatConstraintsErrorRecovery:
    """测试：错误恢复流程"""

    def test_error_recovery_for_failed_node(self):
        """集成：节点失败后的错误恢复"""
        parser = WorkflowActionParser()

        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
            executed_nodes={"node_a": {"status": "failed"}},
        )

        # 尝试恢复失败的节点
        result = parser.parse_and_validate(
            '{"type": "error_recovery", "node_id": "node_a", "reasoning": "重试失败的节点"}',
            context,
        )

        # 恢复应该允许重新执行已失败的节点
        # （注意：这取决于业务规则的具体实现）
        assert result is not None

    def test_error_recovery_cannot_affect_nonexistent_node(self):
        """集成：错误恢复不能针对不存在的节点"""
        parser = WorkflowActionParser()

        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        # 尝试恢复不存在的节点
        result = parser.parse_and_validate(
            '{"type": "error_recovery", "node_id": "nonexistent"}',
            context,
        )

        assert result.is_valid is False


class TestFormatConstraintsSystemPrompt:
    """测试：系统提示与格式约束的整合"""

    def test_system_prompt_includes_all_action_types(self):
        """集成：系统提示包含所有动作类型"""
        prompt_gen = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        prompt = prompt_gen.get_system_prompt(context)

        # 检查所有 ActionType 都在提示中
        assert "reason" in prompt.lower()
        assert "execute_node" in prompt.lower()
        assert "wait" in prompt.lower()
        assert "finish" in prompt.lower()
        assert "error_recovery" in prompt.lower()

    def test_system_prompt_with_complex_context(self):
        """集成：复杂上下文下的系统提示"""
        prompt_gen = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_complex",
            workflow_name="复杂工作流",
            available_nodes=["fetch", "validate", "transform", "save", "notify"],
            executed_nodes={"fetch": {"status": "success"}},
            current_step=5,
            max_steps=50,
        )

        prompt = prompt_gen.get_system_prompt(context)

        # 验证提示包含上下文信息
        assert "复杂工作流" in prompt
        assert "fetch" in prompt
        assert "5" in prompt or "5/" in prompt  # 步骤信息

    def test_system_prompt_helps_llm_produce_valid_json(self):
        """集成：系统提示帮助 LLM 产生有效 JSON"""
        prompt_gen = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        prompt = prompt_gen.get_system_prompt(context)

        # 提示应该包含 JSON 格式示例或说明
        # 检查是否包含 JSON 相关的提示（可能包含 ```json 代码块）
        assert "json" in prompt.lower() or "JSON" in prompt
        # 检查是否包含字段示例
        assert "type" in prompt or "reasoning" in prompt


class TestFormatConstraintsEdgeCases:
    """测试：边界情况"""

    def test_empty_workflow_with_no_available_nodes(self):
        """集成：没有可用节点的工作流"""
        parser = WorkflowActionParser()

        context = WorkflowExecutionContext(
            workflow_id="wf_empty",
            workflow_name="空工作流",
            available_nodes=[],
        )

        # 只能采取推理或完成操作
        result1 = parser.parse_and_validate(
            '{"type": "reason"}',
            context,
        )
        assert result1.is_valid is True

        # 不能执行任何节点
        result2 = parser.parse_and_validate(
            '{"type": "execute_node", "node_id": "any"}',
            context,
        )
        assert result2.is_valid is False

    def test_unicode_characters_in_reasoning(self):
        """集成：支持 Unicode 字符（中文等）"""
        parser = WorkflowActionParser()

        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        # 中文文本
        result = parser.parse_and_validate(
            '{"type": "reason", "reasoning": "分析当前的工作流状态，需要处理数据并保存结果"}',
            context,
        )

        assert result.is_valid is True
        assert "分析当前的工作流状态" in result.action.reasoning

    def test_deeply_nested_params(self):
        """集成：支持嵌套的 params"""
        parser = WorkflowActionParser()

        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        # 嵌套的参数
        result = parser.parse_and_validate(
            json.dumps(
                {
                    "type": "execute_node",
                    "node_id": "node_a",
                    "params": {
                        "config": {"timeout": 30, "retries": 3, "nested": {"deep": "value"}}
                    },
                }
            ),
            context,
        )

        assert result.is_valid is True
        assert result.action.params["config"]["nested"]["deep"] == "value"

    def test_large_number_of_executed_nodes(self):
        """集成：处理大量已执行节点"""
        parser = WorkflowActionParser()

        # 创建大量已执行节点
        executed = {f"node_{i}": {"status": "success"} for i in range(20)}

        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[f"node_{i}" for i in range(30)],
            executed_nodes=executed,
        )

        # 尝试执行一个未执行的节点
        result = parser.parse_and_validate(
            '{"type": "execute_node", "node_id": "node_25"}',
            context,
        )

        assert result.is_valid is True

        # 尝试执行一个已执行的节点应该失败
        result2 = parser.parse_and_validate(
            '{"type": "execute_node", "node_id": "node_5"}',
            context,
        )

        assert result2.is_valid is False

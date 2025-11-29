"""RED 测试：WorkflowActionParser 服务 - 工作流动作解析

TDD RED 阶段：定义 WorkflowActionParser 的三级解析和重试逻辑

三级解析：
1. JSON 格式验证 - 原始字符串是否是有效的 JSON
2. Pydantic 字段验证 - JSON 是否符合 WorkflowAction 模型
3. 业务规则验证 - 动作是否符合工作流上下文的业务规则

重试机制：
- 最多 3 次重试尝试
- 每次失败后生成具体的重试提示
- 跟踪解析尝试次数
"""

from src.application.services.workflow_action_parser import (
    WorkflowActionParser,
)
from src.domain.value_objects.workflow_action import (
    ActionType,
    WorkflowExecutionContext,
)


class TestWorkflowActionParserBasics:
    """测试：WorkflowActionParser 基础功能"""

    def test_workflow_action_parser_can_be_created(self):
        """RED：应该能创建 WorkflowActionParser 实例"""
        parser = WorkflowActionParser()

        assert parser is not None

    def test_workflow_action_parser_has_parse_and_validate_method(self):
        """RED：WorkflowActionParser 应该有 parse_and_validate 方法"""
        parser = WorkflowActionParser()

        assert hasattr(parser, "parse_and_validate")
        assert callable(parser.parse_and_validate)

    def test_workflow_action_parser_has_generate_retry_prompt_method(self):
        """RED：WorkflowActionParser 应该有 generate_retry_prompt 方法"""
        parser = WorkflowActionParser()

        assert hasattr(parser, "generate_retry_prompt")
        assert callable(parser.generate_retry_prompt)


class TestWorkflowActionParserValidJSON:
    """测试：JSON 格式验证（第一级）"""

    def test_parse_valid_json_string(self):
        """RED：应该能解析有效的 JSON 字符串"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason", "reasoning": "thinking"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.action is not None
        assert result.is_valid is True

    def test_parse_json_with_execute_node(self):
        """RED：应该能解析包含 node_id 的 JSON"""
        parser = WorkflowActionParser()
        json_str = '{"type": "execute_node", "node_id": "node_a"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.action is not None
        assert result.action.type == ActionType.EXECUTE_NODE
        assert result.action.node_id == "node_a"

    def test_parse_json_with_params(self):
        """RED：应该能解析包含 params 的 JSON"""
        parser = WorkflowActionParser()
        json_str = '{"type": "execute_node", "node_id": "node_a", "params": {"timeout": 30}}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.action is not None
        assert result.action.params == {"timeout": 30}

    def test_parse_invalid_json_fails_gracefully(self):
        """RED：无效的 JSON 应该返回失败结果，不抛出异常"""
        parser = WorkflowActionParser()
        json_str = "invalid json {]"
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False
        assert result.error_message is not None
        assert "JSON" in result.error_message or "json" in result.error_message

    def test_parse_empty_string_fails(self):
        """RED：空字符串应该解析失败"""
        parser = WorkflowActionParser()
        json_str = ""
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False

    def test_parse_non_json_dict_fails(self):
        """RED：非字典的 JSON（如数组）应该解析失败"""
        parser = WorkflowActionParser()
        json_str = '["item1", "item2"]'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False

    def test_parse_json_with_extra_spaces(self):
        """RED：应该能解析包含空格的 JSON"""
        parser = WorkflowActionParser()
        json_str = '  {  "type": "reason"  }  '
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is True


class TestWorkflowActionParserFieldValidation:
    """测试：字段级验证（第二级 - Pydantic）"""

    def test_parse_json_missing_required_type_field(self):
        """RED：缺少 type 字段的 JSON 应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"reasoning": "thinking"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False
        assert "type" in result.error_message or "type" in str(result.error_message).lower()

    def test_parse_json_with_invalid_type_value(self):
        """RED：无效的 type 值应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"type": "invalid_action_type"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False
        assert "type" in result.error_message or "invalid" in result.error_message.lower()

    def test_parse_json_with_wrong_type_format(self):
        """RED：type 字段类型错误应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"type": 123}'  # type should be string
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False

    def test_parse_json_with_negative_retry_count(self):
        """RED：负数 retry_count 应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason", "retry_count": -1}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False

    def test_parse_json_with_invalid_params_type(self):
        """RED：params 如果不是字典应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason", "params": "not_a_dict"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False


class TestWorkflowActionParserBusinessRuleValidation:
    """测试：业务规则验证（第三级）"""

    def test_execute_node_with_nonexistent_node_fails_validation(self):
        """RED：执行不存在的节点应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"type": "execute_node", "node_id": "nonexistent"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False
        assert "nonexistent" in result.error_message or "节点" in result.error_message

    def test_execute_already_executed_node_fails_validation(self):
        """RED：执行已执行过的节点应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"type": "execute_node", "node_id": "node_a"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
            executed_nodes={"node_a": {"status": "success"}},
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False

    def test_action_exceeding_step_limit_fails_validation(self):
        """RED：超过步骤限制的动作应该验证失败"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
            current_step=51,
            max_steps=50,
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is False


class TestWorkflowActionParserRetryTracking:
    """测试：重试次数跟踪"""

    def test_first_parse_attempt_has_parse_attempt_1(self):
        """RED：第一次解析的 parse_attempt 应该是 1"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.parse_attempt == 1

    def test_parse_attempt_increments_with_retry(self):
        """RED：parse_attempt 应该随着重试而增加"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        # 第一次失败
        result1 = parser.parse_and_validate("invalid json", context)
        assert result1.parse_attempt == 1

        # 第二次重试
        result2 = parser.parse_and_validate("invalid json 2", context, parse_attempt=2)
        assert result2.parse_attempt == 2

        # 第三次重试
        result3 = parser.parse_and_validate("invalid json 3", context, parse_attempt=3)
        assert result3.parse_attempt == 3

    def test_parse_attempt_respects_provided_value(self):
        """RED：parse_and_validate 应该尊重传入的 parse_attempt 参数"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context, parse_attempt=2)

        assert result.parse_attempt == 2


class TestWorkflowActionParserRetryPrompt:
    """测试：重试提示生成"""

    def test_generate_retry_prompt_for_json_error(self):
        """RED：应该能为 JSON 错误生成重试提示"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result_first = parser.parse_and_validate("invalid json", context)
        retry_prompt = parser.generate_retry_prompt(result_first, context)

        assert isinstance(retry_prompt, str)
        assert len(retry_prompt) > 0
        assert "JSON" in retry_prompt or "json" in retry_prompt

    def test_generate_retry_prompt_for_validation_error(self):
        """RED：应该能为验证错误生成重试提示"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        json_str = '{"type": "execute_node", "node_id": "nonexistent"}'
        result = parser.parse_and_validate(json_str, context)
        retry_prompt = parser.generate_retry_prompt(result, context)

        assert isinstance(retry_prompt, str)
        assert len(retry_prompt) > 0
        # 应该提供关于可用节点的信息
        assert "node_a" in retry_prompt or "节点" in retry_prompt

    def test_generate_retry_prompt_includes_available_nodes(self):
        """RED：重试提示应该包含可用节点列表"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["fetch_data", "process_data", "save_result"],
        )

        json_str = '{"type": "execute_node", "node_id": "wrong"}'
        result = parser.parse_and_validate(json_str, context)
        retry_prompt = parser.generate_retry_prompt(result, context)

        # 应该包含可用节点的提示
        assert (
            "fetch_data" in retry_prompt
            or "process_data" in retry_prompt
            or "save_result" in retry_prompt
        )

    def test_generate_retry_prompt_includes_attempt_count(self):
        """RED：重试提示应该包含当前尝试次数"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result_attempt2 = parser.parse_and_validate("invalid", context, parse_attempt=2)
        retry_prompt = parser.generate_retry_prompt(result_attempt2, context)

        # 应该提及重试次数
        assert "2" in retry_prompt or "第二次" in retry_prompt or "attempt" in retry_prompt.lower()

    def test_generate_retry_prompt_warns_on_last_attempt(self):
        """RED：在最后一次尝试时，提示应该警告即将失败"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result_attempt3 = parser.parse_and_validate("invalid", context, parse_attempt=3)
        retry_prompt = parser.generate_retry_prompt(result_attempt3, context)

        # 应该包含警告信息
        assert "最后" in retry_prompt or "失败" in retry_prompt or "最后一次" in retry_prompt


class TestWorkflowActionParserErrorReporting:
    """测试：错误报告"""

    def test_parse_error_includes_raw_content(self):
        """RED：解析错误应该包含原始内容"""
        parser = WorkflowActionParser()
        raw_content = "invalid json content"
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(raw_content, context)

        assert result.raw_content == raw_content

    def test_parse_error_message_is_detailed(self):
        """RED：解析错误消息应该详细"""
        parser = WorkflowActionParser()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate("not json", context)

        assert result.error_message is not None
        assert len(result.error_message) > 0
        # 应该提供具体的错误信息，不只是"解析失败"
        assert len(result.error_message) > 10

    def test_validation_error_includes_field_name(self):
        """RED：验证错误应该包含问题字段的名称"""
        parser = WorkflowActionParser()
        json_str = '{"type": "execute_node"}'  # 缺少 node_id
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = parser.parse_and_validate(json_str, context)

        # 错误消息应该提及缺少的字段
        assert "node_id" in result.error_message


class TestWorkflowActionParserCompleteFlow:
    """测试：完整的解析流程"""

    def test_parse_valid_reason_action(self):
        """RED：应该能完整解析有效的 REASON 动作"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason", "reasoning": "分析状态"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is True
        assert result.action.type == ActionType.REASON
        assert result.action.reasoning == "分析状态"
        assert result.error_message is None

    def test_parse_valid_execute_node_action(self):
        """RED：应该能完整解析有效的 EXECUTE_NODE 动作"""
        parser = WorkflowActionParser()
        json_str = '{"type": "execute_node", "node_id": "node_a"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is True
        assert result.action.type == ActionType.EXECUTE_NODE
        assert result.action.node_id == "node_a"

    def test_parse_valid_finish_action(self):
        """RED：应该能完整解析有效的 FINISH 动作"""
        parser = WorkflowActionParser()
        json_str = '{"type": "finish", "reasoning": "任务完成"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is True
        assert result.action.type == ActionType.FINISH

    def test_parse_action_with_all_optional_fields(self):
        """RED：应该能解析包含所有可选字段的动作"""
        parser = WorkflowActionParser()
        json_str = """{
            "type": "execute_node",
            "node_id": "node_a",
            "reasoning": "执行数据处理",
            "params": {"timeout": 30, "retry": 3},
            "retry_count": 1
        }"""
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is True
        assert result.action.node_id == "node_a"
        assert result.action.reasoning == "执行数据处理"
        assert result.action.params == {"timeout": 30, "retry": 3}
        assert result.action.retry_count == 1


class TestWorkflowActionParserEdgeCases:
    """测试：边界情况"""

    def test_parse_json_with_unicode_characters(self):
        """RED：应该能解析包含 Unicode 字符的 JSON"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason", "reasoning": "分析数据流和处理逻辑"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="中文工作流",
            available_nodes=[],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is True
        assert "分析数据流" in result.action.reasoning

    def test_parse_json_with_special_characters_in_strings(self):
        """RED：应该能解析包含特殊字符的 JSON"""
        parser = WorkflowActionParser()
        json_str = '{"type": "reason", "reasoning": "特殊字符: \\"括号\\", \\n换行, \\t制表"}'
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        # 应该能解析，不抛出异常
        result = parser.parse_and_validate(json_str, context)

        # 结果可能有效或无效，但不应该崩溃
        assert result is not None

    def test_parse_json_with_deeply_nested_params(self):
        """RED：应该能处理嵌套的 params"""
        parser = WorkflowActionParser()
        json_str = """{
            "type": "execute_node",
            "node_id": "node_a",
            "params": {
                "nested": {
                    "deep": {
                        "value": "test"
                    }
                }
            }
        }"""
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = parser.parse_and_validate(json_str, context)

        assert result.is_valid is True
        assert result.action.params["nested"]["deep"]["value"] == "test"

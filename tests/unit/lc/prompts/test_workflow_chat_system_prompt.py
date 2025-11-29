"""RED 测试：Workflow Chat System Prompt 工程

TDD RED 阶段：定义系统提示的期望行为和格式约束

系统提示职责：
1. 教导 LLM 各个 ActionType 的含义和字段
2. 提供每个 ActionType 的精确 JSON 例子
3. 明确列出所有验证规则和约束
4. 显示当前工作流的执行状态
5. 指导 LLM 如何产生有效的 JSON

测试覆盖：
- 提示包含所有 ActionType 定义
- 提示包含每个 ActionType 的 JSON 例子
- 提示包含验证规则说明
- 提示支持动态上下文注入
- 提示字符串长度合理（不超过 Token 限制）
"""

from src.domain.value_objects.workflow_action import (
    WorkflowExecutionContext,
)
from src.lc.prompts.workflow_chat_system_prompt import (
    WorkflowChatSystemPrompt,
)


class TestWorkflowChatSystemPromptBasics:
    """测试：系统提示基础功能"""

    def test_workflow_chat_system_prompt_can_be_created(self):
        """RED：应该能创建 WorkflowChatSystemPrompt 实例"""
        prompt = WorkflowChatSystemPrompt()

        assert prompt is not None

    def test_system_prompt_has_get_system_prompt_method(self):
        """RED：应该有 get_system_prompt 方法"""
        prompt = WorkflowChatSystemPrompt()

        assert hasattr(prompt, "get_system_prompt")
        assert callable(prompt.get_system_prompt)

    def test_system_prompt_has_get_system_prompt_with_context_method(self):
        """RED：应该有支持上下文参数的 get_system_prompt 方法"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        # 应该接受 context 参数
        result = prompt.get_system_prompt(context)

        assert isinstance(result, str)
        assert len(result) > 0


class TestWorkflowChatSystemPromptContent:
    """测试：系统提示内容"""

    def test_system_prompt_includes_reason_action_type(self):
        """RED：系统提示应该包含 REASON ActionType 的说明"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        assert "reason" in result.lower() or "REASON" in result

    def test_system_prompt_includes_execute_node_action_type(self):
        """RED：系统提示应该包含 EXECUTE_NODE ActionType 的说明"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        assert "execute_node" in result.lower() or "EXECUTE_NODE" in result

    def test_system_prompt_includes_wait_action_type(self):
        """RED：系统提示应该包含 WAIT ActionType 的说明"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        assert "wait" in result.lower() or "WAIT" in result

    def test_system_prompt_includes_finish_action_type(self):
        """RED：系统提示应该包含 FINISH ActionType 的说明"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        assert "finish" in result.lower() or "FINISH" in result

    def test_system_prompt_includes_error_recovery_action_type(self):
        """RED：系统提示应该包含 ERROR_RECOVERY ActionType 的说明"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        assert "error_recovery" in result.lower() or "ERROR_RECOVERY" in result


class TestWorkflowChatSystemPromptJSONExamples:
    """测试：JSON 示例"""

    def test_system_prompt_includes_json_example_for_reason(self):
        """RED：系统提示应该包含 REASON 的 JSON 示例"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        # 应该包含包含 "reason" 的 JSON 例子
        assert '"type"' in result and "reason" in result.lower()

    def test_system_prompt_includes_json_example_for_execute_node(self):
        """RED：系统提示应该包含 EXECUTE_NODE 的 JSON 示例"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = prompt.get_system_prompt(context)

        # 应该包含包含 "execute_node" 和 "node_id" 的 JSON 例子
        assert '"type"' in result and "execute_node" in result.lower()
        assert '"node_id"' in result

    def test_system_prompt_includes_json_example_for_wait(self):
        """RED：系统提示应该包含 WAIT 的 JSON 示例"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        # 应该包含包含 "wait" 的 JSON 例子
        assert '"type"' in result and "wait" in result.lower()

    def test_system_prompt_includes_json_example_for_finish(self):
        """RED：系统提示应该包含 FINISH 的 JSON 示例"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        # 应该包含包含 "finish" 的 JSON 例子
        assert '"type"' in result and "finish" in result.lower()

    def test_system_prompt_includes_json_example_for_error_recovery(self):
        """RED：系统提示应该包含 ERROR_RECOVERY 的 JSON 示例"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
        )

        result = prompt.get_system_prompt(context)

        # 应该包含包含 "error_recovery" 和 "node_id" 的 JSON 例子
        assert '"type"' in result and "error_recovery" in result.lower()
        assert '"node_id"' in result


class TestWorkflowChatSystemPromptValidationRules:
    """测试：验证规则说明"""

    def test_system_prompt_mentions_json_format(self):
        """RED：系统提示应该强调返回有效的 JSON 格式"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        assert "json" in result.lower() or "JSON" in result

    def test_system_prompt_mentions_required_fields(self):
        """RED：系统提示应该说明必填字段"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        # 应该提及必填字段
        assert "type" in result or "必填" in result or "required" in result.lower()

    def test_system_prompt_mentions_node_execution_restriction(self):
        """RED：系统提示应该说明节点不能重复执行"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a"],
            executed_nodes={"node_a": {"status": "success"}},
        )

        result = prompt.get_system_prompt(context)

        # 应该提及重复执行的限制
        assert "已执行" in result or "执行过" in result or "重复" in result

    def test_system_prompt_mentions_available_nodes(self):
        """RED：系统提示应该列出可用的节点"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["fetch_data", "process_data"],
        )

        result = prompt.get_system_prompt(context)

        # 应该提到可用节点
        assert "fetch_data" in result or "process_data" in result or "可用" in result


class TestWorkflowChatSystemPromptContextInjection:
    """测试：上下文注入"""

    def test_system_prompt_includes_workflow_name(self):
        """RED：系统提示应该包含工作流名称"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_123",
            workflow_name="数据处理管道",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        assert "数据处理管道" in result

    def test_system_prompt_includes_available_nodes_list(self):
        """RED：系统提示应该包含可用节点列表"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["fetch", "transform", "upload"],
        )

        result = prompt.get_system_prompt(context)

        # 应该包含至少一个节点名称
        assert "fetch" in result or "transform" in result or "upload" in result

    def test_system_prompt_includes_executed_nodes_info(self):
        """RED：系统提示应该包含已执行节点的信息"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["node_a", "node_b"],
            executed_nodes={"node_a": {"status": "success"}},
        )

        result = prompt.get_system_prompt(context)

        # 应该提到已执行的节点
        assert "node_a" in result or "已执行" in result

    def test_system_prompt_includes_current_step_info(self):
        """RED：系统提示应该包含当前步骤信息"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
            current_step=5,
            max_steps=20,
        )

        result = prompt.get_system_prompt(context)

        # 应该提到步骤信息
        assert "5" in result or "20" in result or "步骤" in result

    def test_system_prompt_respects_different_contexts(self):
        """RED：系统提示应该随着上下文变化而变化"""
        prompt = WorkflowChatSystemPrompt()

        context1 = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="工作流A",
            available_nodes=["node_1"],
        )

        context2 = WorkflowExecutionContext(
            workflow_id="wf_2",
            workflow_name="工作流B",
            available_nodes=["node_2", "node_3"],
        )

        result1 = prompt.get_system_prompt(context1)
        result2 = prompt.get_system_prompt(context2)

        # 提示内容应该不同（至少工作流名称不同）
        assert "工作流A" in result1
        assert "工作流B" in result2
        # 也可能节点信息不同
        assert result1 != result2 or ("工作流A" in result1 and "工作流B" in result2)


class TestWorkflowChatSystemPromptLength:
    """测试：提示长度"""

    def test_system_prompt_length_is_reasonable(self):
        """RED：系统提示长度应该在合理范围内"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["a", "b", "c"],
        )

        result = prompt.get_system_prompt(context)

        # 应该足够详细（至少 100 字符）
        assert len(result) > 100
        # 但不应该过长（一般 Token 限制在 2000 以内）
        assert len(result) < 5000

    def test_system_prompt_scales_with_available_nodes(self):
        """RED：系统提示长度应该随可用节点数量增加"""
        prompt = WorkflowChatSystemPrompt()

        context_small = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["a"],
        )

        context_large = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=["a", "b", "c", "d", "e"],
        )

        result_small = prompt.get_system_prompt(context_small)
        result_large = prompt.get_system_prompt(context_large)

        # 较大的上下文应该产生相对较长的提示（因为包含更多节点）
        assert len(result_large) >= len(result_small)


class TestWorkflowChatSystemPromptLanguageAndClarity:
    """测试：语言和清晰度"""

    def test_system_prompt_uses_clear_language(self):
        """RED：系统提示应该使用清晰的语言"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        # 应该是中文或英文，不应该有乱码
        assert len(result) > 0
        # 检查不包含常见的编码错误
        assert "\\u" not in result or "\\x" not in result

    def test_system_prompt_provides_instructions(self):
        """RED：系统提示应该提供明确的指示"""
        prompt = WorkflowChatSystemPrompt()
        context = WorkflowExecutionContext(
            workflow_id="wf_1",
            workflow_name="test",
            available_nodes=[],
        )

        result = prompt.get_system_prompt(context)

        # 应该包含指导 LLM 的说明（如"返回"、"生成"等）
        assert any(
            word in result
            for word in ["返回", "生成", "输出", "提供", "return", "generate", "provide"]
        )

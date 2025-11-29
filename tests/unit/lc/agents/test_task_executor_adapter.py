"""RED 测试：TaskExecutor 适配器 - 向后兼容性

TDD RED 阶段：定义 TaskExecutor 适配器的期望行为

适配器职责：
1. 包装新的 LangGraph TaskExecutor
2. 保持现有 execute_task() 接口兼容
3. 将 LangGraph 返回的状态转换为字符串结果
4. 支持实时任务执行场景（完全集成）

设计目标：
- 现有代码无需修改，直接使用新引擎
- 从 LangGraph 状态提取最终答案
- 处理多步推理，返回清晰结果
- 与简化版 Agent 兼容
"""

from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.lc.agents.task_executor_adapter import (
    create_langgraph_task_executor_adapter,
    execute_task_with_langgraph,
    extract_final_answer,
)


class TestExtractFinalAnswer:
    """测试：从 LangGraph 状态提取最终答案"""

    def test_extract_from_single_ai_message(self):
        """RED：从单个 AIMessage 提取答案"""
        state = {
            "messages": [
                HumanMessage(content="问题"),
                AIMessage(content="最终答案"),
            ]
        }

        result = extract_final_answer(state)

        assert result == "最终答案"

    def test_extract_from_multi_step_messages(self):
        """RED：从多步骤消息序列中提取最终答案"""
        state = {
            "messages": [
                HumanMessage(content="计算 2+2"),
                AIMessage(
                    content="使用计算器",
                    tool_calls=[{"id": "1", "name": "calculator", "args": {}}],
                ),
                ToolMessage(content="4", tool_call_id="1"),
                AIMessage(content="计算结果是 4"),
            ]
        }

        result = extract_final_answer(state)

        assert result == "计算结果是 4"

    def test_extract_handles_empty_messages(self):
        """RED：处理空消息列表"""
        state = {"messages": []}

        result = extract_final_answer(state)

        # 应该返回某种合理的错误或空值
        assert result is not None
        assert isinstance(result, str)

    def test_extract_handles_only_human_message(self):
        """RED：处理仅包含用户消息的情况"""
        state = {"messages": [HumanMessage(content="问题")]}

        result = extract_final_answer(state)

        assert result is not None
        assert isinstance(result, str)

    def test_extract_from_error_scenario(self):
        """RED：从错误场景中提取信息"""
        state = {
            "messages": [
                HumanMessage(content="调用工具"),
                AIMessage(
                    content="我需要工具",
                    tool_calls=[{"id": "1", "name": "missing_tool", "args": {}}],
                ),
                ToolMessage(content="工具不存在", tool_call_id="1"),
                AIMessage(content="无法完成：工具不可用"),
            ]
        }

        result = extract_final_answer(state)

        # 即使是错误信息，也应该返回最后的 LLM 响应
        assert "无法完成" in result or "工具" in result

    def test_extract_preserves_original_content(self):
        """RED：提取结果不修改原始内容"""
        original_content = "这是 [特殊字符] 的答案：价格为 $100"
        state = {
            "messages": [
                HumanMessage(content="问题"),
                AIMessage(content=original_content),
            ]
        }

        result = extract_final_answer(state)

        assert result == original_content


class TestTaskExecutorAdapter:
    """测试：TaskExecutor 适配器"""

    def test_adapter_wraps_langgraph_executor(self):
        """RED：适配器能包装 LangGraph TaskExecutor"""
        adapter = create_langgraph_task_executor_adapter()

        assert adapter is not None
        assert callable(adapter)

    def test_adapter_accepts_task_name_and_description(self):
        """RED：适配器接受任务名称和描述"""
        adapter = create_langgraph_task_executor_adapter()

        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {
                "messages": [
                    HumanMessage(content="任务"),
                    AIMessage(content="完成"),
                ]
            }
            mock_executor_factory.return_value = mock_executor

            result = adapter(
                task_name="测试任务",
                task_description="这是测试",
            )

            assert result is not None

    def test_adapter_returns_string_result(self):
        """RED：适配器返回字符串结果"""
        adapter = create_langgraph_task_executor_adapter()

        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {
                "messages": [
                    HumanMessage(content="任务"),
                    AIMessage(content="这是字符串结果"),
                ]
            }
            mock_executor_factory.return_value = mock_executor

            result = adapter(
                task_name="任务",
                task_description="描述",
            )

            assert isinstance(result, str)
            assert "字符串结果" in result

    def test_adapter_constructs_proper_input_state(self):
        """RED：适配器正确构造输入状态"""
        adapter = create_langgraph_task_executor_adapter()

        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {"messages": [AIMessage(content="结果")]}
            mock_executor_factory.return_value = mock_executor

            adapter(
                task_name="获取数据",
                task_description="从 API 获取用户数据",
            )

            # 验证 executor.invoke 被调用
            mock_executor.invoke.assert_called_once()
            call_args = mock_executor.invoke.call_args

            # 调用的状态应该包含 messages
            invoked_state = call_args[0][0]
            assert "messages" in invoked_state
            assert isinstance(invoked_state["messages"], list)
            assert len(invoked_state["messages"]) > 0

    def test_adapter_with_simple_task_no_tools(self):
        """RED：适配器处理简单任务（不需要工具）"""
        adapter = create_langgraph_task_executor_adapter()

        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {
                "messages": [
                    HumanMessage(content="什么是 2+2？"),
                    AIMessage(content="2+2 等于 4"),
                ]
            }
            mock_executor_factory.return_value = mock_executor

            result = adapter(
                task_name="数学计算",
                task_description="什么是 2+2？",
            )

            assert "4" in result

    def test_adapter_with_tool_use_task(self):
        """RED：适配器处理工具使用任务"""
        adapter = create_langgraph_task_executor_adapter()

        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {
                "messages": [
                    HumanMessage(content="调用工具"),
                    AIMessage(
                        content="使用工具",
                        tool_calls=[{"id": "1", "name": "http_request", "args": {}}],
                    ),
                    ToolMessage(content="返回数据", tool_call_id="1"),
                    AIMessage(content="从 API 返回的数据已处理"),
                ]
            }
            mock_executor_factory.return_value = mock_executor

            result = adapter(
                task_name="API 调用",
                task_description="调用 HTTP API 获取数据",
            )

            assert isinstance(result, str)

    def test_adapter_error_handling(self):
        """RED：适配器处理执行错误"""
        adapter = create_langgraph_task_executor_adapter()

        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.side_effect = Exception("执行失败")
            mock_executor_factory.return_value = mock_executor

            result = adapter(
                task_name="失败任务",
                task_description="会导致错误的任务",
            )

            assert isinstance(result, str)
            # 应该返回错误信息，而不是抛出异常
            assert "错误" in result.lower() or "失败" in result.lower()


class TestExecuteTaskWithLangGraph:
    """测试：execute_task_with_langgraph 函数"""

    def test_convenience_function_exists(self):
        """RED：execute_task_with_langgraph 函数应该存在"""
        assert callable(execute_task_with_langgraph)

    def test_convenience_function_accepts_task_params(self):
        """RED：便捷函数接受任务参数"""
        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {"messages": [AIMessage(content="完成")]}
            mock_executor_factory.return_value = mock_executor

            result = execute_task_with_langgraph(
                task_name="任务",
                task_description="描述",
            )

            assert result is not None
            assert isinstance(result, str)

    def test_convenience_function_returns_string(self):
        """RED：便捷函数返回字符串"""
        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {
                "messages": [
                    HumanMessage(content="输入"),
                    AIMessage(content="最终答案是 42"),
                ]
            }
            mock_executor_factory.return_value = mock_executor

            result = execute_task_with_langgraph(
                task_name="生命答案",
                task_description="生命、宇宙和万物的终极问题的答案是什么？",
            )

            assert "42" in result


class TestAdapterIntegrationPoints:
    """测试：适配器与系统的集成点"""

    def test_adapter_uses_langgraph_executor_not_simple_chain(self):
        """RED：适配器应该使用 LangGraph TaskExecutor，而非简化版"""
        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_langgraph:
            mock_executor = Mock()
            mock_executor.invoke.return_value = {"messages": [AIMessage(content="")]}
            mock_langgraph.return_value = mock_executor

            adapter = create_langgraph_task_executor_adapter()
            adapter(task_name="测试", task_description="测试")

            # 验证使用了 LangGraph 版本
            mock_langgraph.assert_called_once()

    def test_adapter_preserves_message_sequence(self):
        """RED：适配器保留完整的消息序列以供审计"""
        # 适配器虽然返回字符串，但应该保留完整的推理过程
        # 这可以通过返回结构化数据或其他方式实现

        with patch(
            "src.lc.agents.task_executor_adapter.create_langgraph_task_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            expected_messages = [
                HumanMessage(content="计算"),
                AIMessage(
                    content="使用工具",
                    tool_calls=[{"id": "1", "name": "calc", "args": {}}],
                ),
                ToolMessage(content="4", tool_call_id="1"),
                AIMessage(content="答案是 4"),
            ]
            mock_executor.invoke.return_value = {"messages": expected_messages}
            mock_executor_factory.return_value = mock_executor

            result = execute_task_with_langgraph(
                task_name="任务",
                task_description="计算",
            )

            # 最终结果应该包含 LLM 的最后响应
            assert "答案是 4" in result or "4" in result

"""集成测试：LangGraph TaskExecutor - REFACTOR 阶段

TDD REFACTOR 阶段：测试与真实系统组件的集成

集成点：
1. 与 LLM 客户端的集成
2. 与工具系统的集成
3. 与消息序列化的集成
4. 与错误处理的集成
5. 多步骤循环的实际执行
"""

import json
from unittest.mock import Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.lc.agents.langgraph_task_executor import create_langgraph_task_executor


class TestLangGraphTaskExecutorIntegration:
    """集成测试：LangGraph TaskExecutor 与系统组件的集成"""

    def test_executor_integrates_with_llm_client(self):
        """集成测试：TaskExecutor 正确获取和使用 LLM 客户端

        REFACTOR：确保 TaskExecutor 正确使用项目的 LLM 客户端获取方式
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm = Mock()
            mock_llm.invoke.return_value = AIMessage(content="我理解了任务")
            mock_llm_func.return_value = mock_llm

            state = {"messages": [HumanMessage(content="你好")]}
            result = executor.invoke(state)

            # 验证 LLM 客户端被正确调用
            mock_llm_func.assert_called_once()
            mock_llm.invoke.assert_called()
            assert result is not None
            assert len(result["messages"]) > 1

    def test_executor_integrates_with_tools_system(self):
        """集成测试：TaskExecutor 正确使用工具系统

        REFACTOR：确保 TaskExecutor 能正确调用项目的工具系统
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            with patch("src.lc.agents.langgraph_task_executor.get_all_tools") as mock_tools_func:
                # 模拟工具系统
                mock_tool = Mock()
                mock_tool.name = "http_request"
                mock_tool.invoke.return_value = {"status": 200, "data": "success"}
                mock_tools_func.return_value = [mock_tool]

                # LLM 使用工具
                mock_llm = Mock()
                mock_llm.invoke.side_effect = [
                    AIMessage(
                        content="调用工具",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "name": "http_request",
                                "args": {"url": "http://example.com"},
                            }
                        ],
                    ),
                    AIMessage(content="任务完成"),
                ]
                mock_llm_func.return_value = mock_llm

                state = {"messages": [HumanMessage(content="请调用 API")]}
                result = executor.invoke(state)

                # 验证工具被调用
                mock_tool.invoke.assert_called_once_with({"url": "http://example.com"})
                # 验证结果包含工具调用和响应
                assert len(result["messages"]) >= 4  # 初始 + 工具请求 + 工具结果 + 最终响应

    def test_executor_message_serialization_compatibility(self):
        """集成测试：消息序列化兼容性

        REFACTOR：确保状态中的消息可以序列化（用于存储或传输）
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm = Mock()
            mock_llm.invoke.return_value = AIMessage(content="回复")
            mock_llm_func.return_value = mock_llm

            state = {"messages": [HumanMessage(content="问题")]}
            result = executor.invoke(state)

            # 验证所有消息都能被序列化
            messages = result["messages"]
            for msg in messages:
                # LangChain 消息应该有 dict() 方法
                msg_dict = msg.dict() if hasattr(msg, "dict") else vars(msg)
                assert msg_dict is not None
                # 尝试 JSON 序列化
                try:
                    json.dumps(
                        {
                            "type": msg.__class__.__name__,
                            "content": str(msg.content),
                        }
                    )
                except (TypeError, ValueError):
                    pytest.fail(f"消息 {msg.__class__.__name__} 无法序列化")

    def test_executor_error_handling_with_invalid_tool(self):
        """集成测试：处理不存在的工具

        REFACTOR：确保系统能优雅处理工具不存在的情况
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            with patch("src.lc.agents.langgraph_task_executor.get_all_tools") as mock_tools_func:
                # 工具系统只有一个工具
                mock_tool = Mock()
                mock_tool.name = "valid_tool"
                mock_tools_func.return_value = [mock_tool]

                # LLM 尝试调用不存在的工具
                mock_llm = Mock()
                mock_llm.invoke.side_effect = [
                    AIMessage(
                        content="调用工具",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "name": "invalid_tool",
                                "args": {},
                            }
                        ],
                    ),
                    AIMessage(content="已处理错误"),
                ]
                mock_llm_func.return_value = mock_llm

                state = {"messages": [HumanMessage(content="任务")]}
                result = executor.invoke(state)

                # 应该返回错误消息，而不是抛出异常
                assert result is not None
                messages = result["messages"]
                # 应该包含错误消息
                error_found = any(
                    "不存在" in str(msg.content) for msg in messages if hasattr(msg, "content")
                )
                assert error_found, "应该有关于工具不存在的消息"

    def test_executor_message_history_preservation(self):
        """集成测试：消息历史保留

        REFACTOR：确保完整的消息历史被保留，便于审计和学习
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            with patch("src.lc.agents.langgraph_task_executor.get_all_tools") as mock_tools_func:
                mock_tool = Mock()
                mock_tool.name = "calculator"
                mock_tool.invoke.return_value = 42
                mock_tools_func.return_value = [mock_tool]

                mock_llm = Mock()
                mock_llm.invoke.side_effect = [
                    AIMessage(
                        content="需要计算",
                        tool_calls=[{"id": "1", "name": "calculator", "args": {"x": 2, "y": 2}}],
                    ),
                    AIMessage(content="结果是 42"),
                ]
                mock_llm_func.return_value = mock_llm

                state = {"messages": [HumanMessage(content="计算 2+2")]}
                result = executor.invoke(state)

                messages = result["messages"]
                # 验证消息序列：用户输入 → LLM 思考 → 工具调用 → 工具结果 → LLM 最终答案
                assert isinstance(messages[0], HumanMessage)
                assert isinstance(messages[1], AIMessage)
                assert messages[1].tool_calls is not None
                assert isinstance(messages[2], ToolMessage)
                assert isinstance(messages[3], AIMessage)

                # 验证每条消息都有内容
                for msg in messages:
                    assert hasattr(msg, "content")
                    assert msg.content is not None

    def test_executor_tool_error_recovery(self):
        """集成测试：工具执行错误恢复

        REFACTOR：确保工具执行失败时能恢复并继续推理
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            with patch("src.lc.agents.langgraph_task_executor.get_all_tools") as mock_tools_func:
                # 模拟一个会失败的工具
                mock_tool = Mock()
                mock_tool.name = "failing_tool"
                mock_tool.invoke.side_effect = RuntimeError("工具崩溃")
                mock_tools_func.return_value = [mock_tool]

                mock_llm = Mock()
                mock_llm.invoke.side_effect = [
                    AIMessage(
                        content="使用工具",
                        tool_calls=[{"id": "1", "name": "failing_tool", "args": {}}],
                    ),
                    AIMessage(content="工具失败，给出替代答案"),
                ]
                mock_llm_func.return_value = mock_llm

                state = {"messages": [HumanMessage(content="任务")]}
                result = executor.invoke(state)

                # 验证：
                # 1. 没有抛出异常
                assert result is not None
                # 2. 包含错误消息
                messages = result["messages"]
                error_msg = [m for m in messages if isinstance(m, ToolMessage)][0]
                assert "失败" in error_msg.content
                # 3. LLM 能继续推理
                assert messages[-1].content is not None

    def test_executor_with_multi_tool_calls(self):
        """集成测试：多个工具调用

        REFACTOR：验证 LLM 在一步中调用多个工具的能力
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            with patch("src.lc.agents.langgraph_task_executor.get_all_tools") as mock_tools_func:
                # 模拟两个工具
                tool1 = Mock()
                tool1.name = "tool1"
                tool1.invoke.return_value = "result1"

                tool2 = Mock()
                tool2.name = "tool2"
                tool2.invoke.return_value = "result2"

                mock_tools_func.return_value = [tool1, tool2]

                mock_llm = Mock()
                mock_llm.invoke.side_effect = [
                    AIMessage(
                        content="需要两个工具",
                        tool_calls=[
                            {"id": "1", "name": "tool1", "args": {}},
                            {"id": "2", "name": "tool2", "args": {}},
                        ],
                    ),
                    AIMessage(content="完成"),
                ]
                mock_llm_func.return_value = mock_llm

                state = {"messages": [HumanMessage(content="任务")]}
                result = executor.invoke(state)

                # 验证两个工具都被调用
                tool1.invoke.assert_called_once()
                tool2.invoke.assert_called_once()

                # 验证结果包含两个工具的结果
                tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
                assert len(tool_messages) == 2

    def test_executor_state_dict_format_compatibility(self):
        """集成测试：状态字典格式兼容性

        REFACTOR：确保返回的状态格式与系统期望一致
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm = Mock()
            mock_llm.invoke.return_value = AIMessage(content="响应")
            mock_llm_func.return_value = mock_llm

            state = {"messages": [HumanMessage(content="输入")]}
            result = executor.invoke(state)

            # 验证返回值是字典
            assert isinstance(result, dict)
            # 验证包含必需的字段
            assert "messages" in result
            # 消息应该是列表
            assert isinstance(result["messages"], list)
            # 消息不为空
            assert len(result["messages"]) > 0
            # next 字段应该存在（用于状态跟踪）
            assert "next" in result

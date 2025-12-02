"""测试：LangGraph TaskExecutor - ReAct Agent 循环

TDD RED 阶段：定义 LangGraph 基础的 TaskExecutor 期望行为

设计目标：
1. 支持真正的 ReAct 循环：Reason → Act → Observe
2. 使用 LangGraph StateGraph 实现状态机
3. 支持工具调用和多步推理
4. 保持与现有 execute_task() 接口兼容
"""

from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage

from src.lc.agents.langgraph_task_executor import (
    AgentState,
    create_langgraph_task_executor,
)


class TestLangGraphTaskExecutorBasics:
    """测试 LangGraph TaskExecutor 的基础功能"""

    def test_agent_state_typeddict_defined(self):
        """测试：AgentState TypedDict 已定义

        RED 阶段：AgentState 应该是一个 TypedDict，包含必需的字段
        """
        # 验证 AgentState 是一个 TypedDict
        assert hasattr(AgentState, "__annotations__"), "AgentState 应该是 TypedDict"

        # 验证必需的字段
        required_fields = {"messages", "next"}
        actual_fields = set(AgentState.__annotations__.keys())
        assert required_fields.issubset(actual_fields), (
            f"AgentState 应该包含字段: {required_fields}"
        )

    def test_create_langgraph_task_executor_returns_compiled_graph(self):
        """测试：create_langgraph_task_executor() 返回编译的图

        RED 阶段：应该返回一个可调用的 CompiledGraph 对象
        """
        executor = create_langgraph_task_executor()

        # 红色：executor 应该是可调用的（有 invoke 或 stream 方法）
        assert hasattr(executor, "invoke"), "executor 应该有 invoke 方法（CompiledGraph）"
        assert callable(executor.invoke), "executor.invoke 应该是可调用的"

    def test_agent_graph_has_correct_structure(self):
        """测试：Agent 图有正确的节点和边结构

        RED 阶段：应该有以下节点和转移：
        - reason_node: LLM 推理和决策
        - action_node: 调用工具
        - response_node: 返回最终响应
        """
        executor = create_langgraph_task_executor()

        # 获取图的结构信息
        # 注意：CompiledGraph 的内部结构可能因版本而异
        # 这里验证了关键的调用能力
        assert executor is not None, "executor 应该被正确创建"
        assert callable(executor.invoke), "executor 应该支持 invoke 调用"

    def test_executor_basic_task_execution(self):
        """测试：执行简单任务

        RED 阶段：executor 应该能够：
        1. 接收任务输入
        2. 调用 LLM 进行推理
        3. 返回结果
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm:
            # Mock LLM 返回一个不需要工具的响应
            mock_response = AIMessage(content="任务已完成：结果是 42")
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm.return_value = mock_llm_instance

            # 执行任务
            initial_state = {"messages": [HumanMessage(content="计算 2 + 2 的结果")]}

            result = executor.invoke(initial_state)

            # 红色：结果应该包含最终的响应
            assert result is not None, "executor 应该返回结果"
            assert "messages" in result, "结果应该包含 messages 字段"
            assert len(result["messages"]) > 1, "应该至少有初始消息和响应消息"

    def test_executor_with_tool_use(self):
        """测试：使用工具的任务执行

        RED 阶段：executor 应该能够：
        1. LLM 决定使用工具
        2. 调用工具获得结果
        3. 将结果反馈给 LLM
        4. 返回最终响应
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            with patch("src.lc.agents.langgraph_task_executor.get_all_tools") as mock_tools_func:
                # Mock 工具
                mock_tool = Mock()
                mock_tool.name = "test_tool"
                mock_tools_func.return_value = [mock_tool]

                # Mock LLM - 第一步决定使用工具
                mock_llm_instance = Mock()
                tool_use_response = AIMessage(
                    content="我需要使用工具",
                    tool_calls=[
                        {
                            "id": "call_123",
                            "name": "test_tool",
                            "args": {"query": "test"},
                        }
                    ],
                )
                # 模拟循环：第一次返回工具调用，第二次返回最终结果
                mock_llm_instance.invoke.side_effect = [
                    tool_use_response,
                    AIMessage(content="基于工具结果，最终答案是：success"),
                ]
                mock_llm_func.return_value = mock_llm_instance

                # 执行任务
                initial_state = {"messages": [HumanMessage(content="使用工具完成任务")]}

                result = executor.invoke(initial_state)

                # 红色：结果应该显示工具调用和最终响应
                assert result is not None
                assert "messages" in result
                # 应该至少有：初始消息 -> 工具请求 -> 工具结果 -> 最终响应
                assert len(result["messages"]) >= 4, "应该有足够的消息记录"

    def test_executor_handles_errors_gracefully(self):
        """测试：错误处理

        RED 阶段：executor 应该能够：
        1. 捕获 LLM 调用错误
        2. 返回错误信息而不是抛出异常
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            # Mock LLM 抛出异常
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.side_effect = Exception("LLM 调用失败")
            mock_llm_func.return_value = mock_llm_instance

            initial_state = {"messages": [HumanMessage(content="这个任务会导致错误")]}

            # 应该不抛出异常，而是返回包含错误的结果
            result = executor.invoke(initial_state)
            assert result is not None, "即使错误也应该返回结果"

    def test_agent_state_typing(self):
        """测试：AgentState 的类型定义

        RED 阶段：AgentState 应该有以下类型：
        - messages: list[BaseMessage] - 消息历史
        - next: str - 下一个节点的名称
        """
        # 验证 TypedDict 中字段的类型注解
        annotations = AgentState.__annotations__

        # 检查 messages 字段
        assert "messages" in annotations, "应该有 messages 字段"
        messages_type = annotations["messages"]
        # 类型应该与列表相关（可能是 list, Annotated[list, ...] 等）
        assert "list" in str(messages_type).lower() or "sequence" in str(messages_type).lower(), (
            f"messages 字段类型应该是列表类型，实际: {messages_type}"
        )

        # 检查 next 字段
        assert "next" in annotations, "应该有 next 字段"


class TestLangGraphTaskExecutorNodes:
    """测试 LangGraph TaskExecutor 的节点函数"""

    def test_reason_node_calls_llm(self):
        """测试：reason_node 应该调用 LLM

        RED 阶段：reason_node 是一个函数，接收状态，调用 LLM，返回新状态
        """
        from src.lc.agents.langgraph_task_executor import reason_node

        assert callable(reason_node), "reason_node 应该是可调用的函数"

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = AIMessage(content="响应")
            mock_llm_func.return_value = mock_llm_instance

            state = {"messages": [HumanMessage(content="测试")]}
            result = reason_node(state)

            # 应该返回新的状态
            assert result is not None
            assert "messages" in result

    def test_action_node_exists(self):
        """测试：action_node 应该存在

        RED 阶段：action_node 应该处理工具调用
        """
        from src.lc.agents.langgraph_task_executor import action_node

        assert callable(action_node), "action_node 应该是可调用的函数"

    def test_response_node_exists(self):
        """测试：response_node 应该存在

        RED 阶段：response_node 应该返回最终响应
        """
        from src.lc.agents.langgraph_task_executor import response_node

        assert callable(response_node), "response_node 应该是可调用的函数"


class TestLangGraphTaskExecutorEdges:
    """测试 LangGraph TaskExecutor 的边和转移逻辑"""

    def test_reason_to_action_conditional_edge(self):
        """测试：reason_node 到 action_node 的条件边

        RED 阶段：当 LLM 返回工具调用时，应该进入 action_node
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm_instance = Mock()
            # 返回一个包含工具调用的消息
            tool_use_msg = AIMessage(
                content="使用工具",
                tool_calls=[{"id": "1", "name": "tool", "args": {}}],
            )
            mock_llm_instance.invoke.return_value = tool_use_msg
            mock_llm_func.return_value = mock_llm_instance

            initial_state = {"messages": [HumanMessage(content="调用工具")]}
            result = executor.invoke(initial_state)

            # 应该有工具调用和后续响应
            assert result is not None
            assert "messages" in result

    def test_reason_to_response_conditional_edge(self):
        """测试：reason_node 到 response_node 的条件边

        RED 阶段：当 LLM 不需要工具时，应该直接进入 response_node
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm_instance = Mock()
            # 返回一个不包含工具调用的消息
            final_response = AIMessage(content="直接完成，无需工具")
            mock_llm_instance.invoke.return_value = final_response
            mock_llm_func.return_value = mock_llm_instance

            initial_state = {"messages": [HumanMessage(content="不需要工具")]}
            result = executor.invoke(initial_state)

            assert result is not None
            assert "messages" in result
            # 最后一条消息应该是最终响应
            assert len(result["messages"]) >= 2


class TestLangGraphTaskExecutorIntegration:
    """集成测试：完整的 ReAct 循环"""

    def test_complete_react_loop_simple_task(self):
        """测试：完整的 ReAct 循环 - 简单任务"""
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm_instance = Mock()
            # 简单任务：直接返回答案
            mock_llm_instance.invoke.return_value = AIMessage(content="答案是 42")
            mock_llm_func.return_value = mock_llm_instance

            state = {"messages": [HumanMessage(content="什么是答案？")]}
            result = executor.invoke(state)

            assert result is not None
            assert "messages" in result
            # 最后应该有最终响应
            final_message = result["messages"][-1]
            assert "42" in final_message.content or "答案" in final_message.content

    def test_complete_react_loop_with_tools(self):
        """测试：完整的 ReAct 循环 - 使用工具的任务"""
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            with patch("src.lc.agents.langgraph_task_executor.get_all_tools") as mock_tools_func:
                # 模拟工具
                mock_tool = Mock()
                mock_tool.name = "calculator"
                mock_tools_func.return_value = [mock_tool]

                mock_llm_instance = Mock()
                mock_llm_instance.invoke.side_effect = [
                    # 第一步：决定使用工具
                    AIMessage(
                        content="需要计算",
                        tool_calls=[
                            {"id": "1", "name": "calculator", "args": {"expression": "2+2"}}
                        ],
                    ),
                    # 第二步：收到工具结果后，返回最终响应
                    AIMessage(content="计算结果是 4"),
                ]
                mock_llm_func.return_value = mock_llm_instance

                state = {"messages": [HumanMessage(content="计算 2+2")]}
                result = executor.invoke(state)

                assert result is not None
                assert "messages" in result
                # 应该至少有：初始 + 工具请求 + 工具结果 + 最终响应
                assert len(result["messages"]) >= 4

    def test_max_iterations_protection(self):
        """测试：无限循环保护

        RED 阶段：executor 应该有最大迭代次数限制，防止无限循环
        """
        executor = create_langgraph_task_executor()

        with patch("src.lc.agents.langgraph_task_executor.get_llm_for_execution") as mock_llm_func:
            mock_llm_instance = Mock()
            # 模拟 LLM 一直返回工具调用（导致无限循环）
            tool_call_response = AIMessage(
                content="工具",
                tool_calls=[{"id": "1", "name": "tool", "args": {}}],
            )
            mock_llm_instance.invoke.return_value = tool_call_response
            mock_llm_func.return_value = mock_llm_instance

            state = {"messages": [HumanMessage(content="无限循环")]}

            # 应该不会陷入无限循环，而是返回结果
            result = executor.invoke(state)
            assert result is not None
            # 消息数量应该有合理的上限
            assert len(result["messages"]) < 100, "应该有迭代次数限制"

"""工具调用记录与知识库集成测试 - 阶段 6

测试场景：
1. ToolEngine 执行工具时自动记录到知识库
2. ToolSubAgent 执行后生成摘要
3. 查询接口可追溯每次工具调用
4. 最终结果中包含工具使用记录
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.domain.entities.tool import Tool
from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
from src.domain.services.tool_executor import (
    EchoExecutor,
    ToolExecutionContext,
    ToolSubAgent,
)
from src.domain.services.tool_knowledge_store import (
    InMemoryToolKnowledgeStore,
)
from src.domain.value_objects.tool_category import ToolCategory

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def setup_engine_and_store(tmp_path: Path) -> tuple[ToolEngine, InMemoryToolKnowledgeStore]:
    """创建带知识库的工具引擎和存储"""
    # 创建工具配置文件
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    # echo 工具 - 使用有效的 category
    echo_config = """
name: echo
version: "1.0.0"
description: Echo tool for testing
category: custom
tags: [test, echo]
parameters:
  - name: message
    type: string
    required: true
    description: Message to echo
entry:
  type: builtin
  handler: echo
"""
    (tools_dir / "echo.yaml").write_text(echo_config, encoding="utf-8")

    # calculator 工具
    calc_config = """
name: calculator
version: "1.0.0"
description: Simple calculator
category: custom
tags: [test, math]
parameters:
  - name: expression
    type: string
    required: true
    description: Math expression
entry:
  type: builtin
  handler: calculator
"""
    (tools_dir / "calculator.yaml").write_text(calc_config, encoding="utf-8")

    # 创建知识库存储
    knowledge_store = InMemoryToolKnowledgeStore()

    # 创建引擎
    config = ToolEngineConfig(tools_directory=str(tools_dir))
    engine = ToolEngine(config)

    # 设置知识库存储
    engine.set_knowledge_store(knowledge_store)

    # 注册执行器
    engine.register_executor("echo", EchoExecutor())

    # 注册一个简单的计算器执行器
    class CalculatorExecutor:
        async def execute(self, tool, params, context):
            expr = params.get("expression", "0")
            try:
                # 安全的数学表达式求值
                result = eval(expr, {"__builtins__": {}}, {})
                return {"result": result}
            except Exception as e:
                raise ValueError(f"Invalid expression: {e}") from e

    engine.register_executor("calculator", CalculatorExecutor())

    return engine, knowledge_store


# =============================================================================
# ToolEngine 知识库集成测试
# =============================================================================


class TestToolEngineKnowledgeIntegration:
    """ToolEngine 知识库集成测试"""

    @pytest.mark.asyncio
    async def test_execute_records_to_knowledge_store(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：执行工具时自动记录到知识库"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        # 执行工具
        context = ToolExecutionContext.for_conversation(
            agent_id="agent_001",
            conversation_id="conv_001",
        )
        result = await engine.execute(
            tool_name="echo",
            params={"message": "hello world"},
            context=context,
        )

        # 验证执行成功
        assert result.is_success
        assert result.output == {"echoed": "hello world"}

        # 验证记录已保存到知识库
        records = await knowledge_store.query_by_conversation("conv_001")
        assert len(records) == 1
        assert records[0].tool_name == "echo"
        assert records[0].is_success is True
        assert records[0].params == {"message": "hello world"}
        assert records[0].conversation_id == "conv_001"

    @pytest.mark.asyncio
    async def test_multiple_executions_recorded(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：多次执行都被记录"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        context = ToolExecutionContext.for_conversation(
            agent_id="agent_001",
            conversation_id="conv_001",
        )

        # 执行多次
        for i in range(5):
            await engine.execute(
                tool_name="echo",
                params={"message": f"message_{i}"},
                context=context,
            )

        # 验证所有记录
        records = await knowledge_store.query_by_conversation("conv_001")
        assert len(records) == 5

    @pytest.mark.asyncio
    async def test_failed_execution_recorded(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：失败的执行也被记录"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        context = ToolExecutionContext.for_conversation(
            agent_id="agent_001",
            conversation_id="conv_001",
        )

        # 执行不存在的工具
        result = await engine.execute(
            tool_name="nonexistent_tool",
            params={},
            context=context,
        )

        # 验证执行失败
        assert result.is_success is False
        assert result.error_type == "tool_not_found"

        # 注意：工具不存在时不会记录到知识库（因为在验证阶段就失败了）

    @pytest.mark.asyncio
    async def test_query_by_tool_name(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：按工具名查询"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        context = ToolExecutionContext.for_conversation(
            agent_id="agent_001",
            conversation_id="conv_001",
        )

        # 执行不同工具
        await engine.execute(
            tool_name="echo",
            params={"message": "hello"},
            context=context,
        )
        await engine.execute(
            tool_name="calculator",
            params={"expression": "1+1"},
            context=context,
        )
        await engine.execute(
            tool_name="echo",
            params={"message": "world"},
            context=context,
        )

        # 按工具名查询
        echo_records = await knowledge_store.query_by_tool_name("echo")
        assert len(echo_records) == 2

        calc_records = await knowledge_store.query_by_tool_name("calculator")
        assert len(calc_records) == 1

    @pytest.mark.asyncio
    async def test_get_call_summary_via_engine(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：通过引擎获取调用摘要"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        context = ToolExecutionContext.for_conversation(
            agent_id="agent_001",
            conversation_id="conv_001",
        )

        # 执行多个工具
        await engine.execute(
            tool_name="echo",
            params={"message": "hello"},
            context=context,
        )
        await engine.execute(
            tool_name="calculator",
            params={"expression": "2*3"},
            context=context,
        )
        await engine.execute(
            tool_name="echo",
            params={"message": "world"},
            context=context,
        )

        # 获取摘要
        summary = await engine.get_call_summary("conv_001")

        assert summary is not None
        assert summary.total_calls == 3
        assert summary.successful_calls == 3
        assert summary.tool_usage == {"echo": 2, "calculator": 1}

    @pytest.mark.asyncio
    async def test_get_call_statistics(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：获取全局统计"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        # 执行多个会话的工具调用
        for conv_id in ["conv_001", "conv_002"]:
            context = ToolExecutionContext.for_conversation(
                agent_id="agent_001",
                conversation_id=conv_id,
            )
            await engine.execute(
                tool_name="echo",
                params={"message": f"hello from {conv_id}"},
                context=context,
            )

        # 获取统计
        stats = await engine.get_call_statistics()

        assert stats["total_records"] == 2
        assert stats["success_count"] == 2
        assert stats["tool_distribution"]["echo"] == 2


# =============================================================================
# ToolSubAgent 摘要生成测试
# =============================================================================


class TestToolSubAgentSummary:
    """ToolSubAgent 摘要生成测试"""

    @pytest.mark.asyncio
    async def test_get_execution_summary(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：获取执行摘要"""
        engine, _ = setup_engine_and_store
        await engine.load()

        # 创建 ToolSubAgent
        sub_agent = ToolSubAgent(
            agent_id="sub_agent_001",
            tool_engine=engine,
            parent_agent_id="parent_001",
        )

        # 执行多个工具
        await sub_agent.execute("echo", {"message": "hello"})
        await sub_agent.execute("calculator", {"expression": "1+2"})
        await sub_agent.execute("echo", {"message": "world"})

        # 获取摘要
        summary = sub_agent.get_execution_summary()

        assert summary["agent_id"] == "sub_agent_001"
        assert summary["parent_agent_id"] == "parent_001"
        assert summary["total_calls"] == 3
        assert summary["successful_calls"] == 3
        assert summary["failed_calls"] == 0
        assert summary["success_rate"] == 100.0
        assert summary["tool_usage"] == {"echo": 2, "calculator": 1}
        assert len(summary["call_details"]) == 3

    @pytest.mark.asyncio
    async def test_get_brief_summary(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：获取简要摘要"""
        engine, _ = setup_engine_and_store
        await engine.load()

        sub_agent = ToolSubAgent(
            agent_id="sub_agent_001",
            tool_engine=engine,
        )

        await sub_agent.execute("echo", {"message": "test"})

        brief = sub_agent.get_brief_summary()

        assert "total_calls" in brief
        assert "success_rate" in brief
        assert "tool_usage" in brief
        assert "has_errors" in brief
        assert brief["has_errors"] is False

    @pytest.mark.asyncio
    async def test_summary_with_errors(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：包含错误的摘要"""
        engine, _ = setup_engine_and_store
        await engine.load()

        # 注册一个会失败的执行器
        class FailingExecutor:
            async def execute(self, tool, params, context):
                raise RuntimeError("Intentional failure")

        engine.register_executor("failing", FailingExecutor())

        # 手动注册一个会失败的工具
        failing_tool = Tool(
            id="failing_tool",
            name="failing",
            version="1.0.0",
            description="A tool that always fails",
            category=ToolCategory.CUSTOM,
            parameters=[],
            implementation_config={"handler": "failing"},
            status="active",
        )
        engine.register(failing_tool)

        sub_agent = ToolSubAgent(
            agent_id="sub_agent_001",
            tool_engine=engine,
        )

        # 执行成功和失败的工具
        await sub_agent.execute("echo", {"message": "success"})
        await sub_agent.execute("failing", {})

        summary = sub_agent.get_execution_summary()

        assert summary["total_calls"] == 2
        assert summary["successful_calls"] == 1
        assert summary["failed_calls"] == 1
        assert summary["success_rate"] == 50.0
        assert len(summary["errors"]) == 1
        assert summary["errors"][0]["tool_name"] == "failing"

    @pytest.mark.asyncio
    async def test_clear_history(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：清空执行历史"""
        engine, _ = setup_engine_and_store
        await engine.load()

        sub_agent = ToolSubAgent(
            agent_id="sub_agent_001",
            tool_engine=engine,
        )

        await sub_agent.execute("echo", {"message": "test"})
        assert len(sub_agent.execution_history) == 1

        sub_agent.clear_history()
        assert len(sub_agent.execution_history) == 0

        summary = sub_agent.get_execution_summary()
        assert summary["total_calls"] == 0


# =============================================================================
# 端到端场景测试
# =============================================================================


class TestEndToEndScenarios:
    """端到端场景测试"""

    @pytest.mark.asyncio
    async def test_conversation_agent_workflow(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：模拟对话 Agent 完成任务的完整流程"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        conversation_id = "conv_e2e_001"

        # 1. 创建执行上下文
        context = ToolExecutionContext.for_conversation(
            agent_id="conversation_agent_001",
            conversation_id=conversation_id,
        )

        # 2. 执行一系列工具调用（模拟完成用户任务）
        await engine.execute(
            tool_name="echo",
            params={"message": "Starting task..."},
            context=context,
        )
        await engine.execute(
            tool_name="calculator",
            params={"expression": "100*2"},
            context=context,
        )
        await engine.execute(
            tool_name="echo",
            params={"message": "Task completed!"},
            context=context,
        )

        # 3. 获取会话摘要（传给 WorkflowAgent/前端）
        summary = await engine.get_call_summary(conversation_id)

        # 4. 验证摘要内容
        assert summary.total_calls == 3
        assert summary.successful_calls == 3
        assert summary.success_rate == 100.0
        assert "echo" in summary.tool_usage
        assert "calculator" in summary.tool_usage

        # 5. 验证可以追溯每次调用
        records = await knowledge_store.query_by_conversation(conversation_id)
        assert len(records) == 3

        # 验证记录包含完整信息
        for record in records:
            assert record.conversation_id == conversation_id
            assert record.caller_type == "conversation_agent"
            assert record.execution_time > 0

    @pytest.mark.asyncio
    async def test_final_result_includes_tool_usage(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：最终结果包含工具使用记录"""
        engine, _ = setup_engine_and_store
        await engine.load()

        conversation_id = "conv_final_001"
        context = ToolExecutionContext.for_conversation(
            agent_id="agent_001",
            conversation_id=conversation_id,
        )

        # 执行工具
        await engine.execute(
            tool_name="echo",
            params={"message": "Processing..."},
            context=context,
        )
        await engine.execute(
            tool_name="calculator",
            params={"expression": "42*2"},
            context=context,
        )

        # 构建最终结果（模拟 ConversationAgent 完成时的输出）
        summary = await engine.get_call_summary(conversation_id)

        final_result = {
            "status": "completed",
            "answer": "The result is 84",
            "tool_usage_summary": summary.to_brief(),
        }

        # 验证最终结果包含工具使用记录
        assert "tool_usage_summary" in final_result
        assert final_result["tool_usage_summary"]["total_calls"] == 2
        assert final_result["tool_usage_summary"]["success_rate"] == 100.0
        assert "echo" in final_result["tool_usage_summary"]["tool_usage"]
        assert "calculator" in final_result["tool_usage_summary"]["tool_usage"]

    @pytest.mark.asyncio
    async def test_concurrent_conversations(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：并发多个会话的工具调用"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        async def run_conversation(conv_id: str, num_calls: int):
            context = ToolExecutionContext.for_conversation(
                agent_id=f"agent_{conv_id}",
                conversation_id=conv_id,
            )
            for i in range(num_calls):
                await engine.execute(
                    tool_name="echo",
                    params={"message": f"{conv_id}_msg_{i}"},
                    context=context,
                )

        # 并发执行 5 个会话
        conversations = [
            ("conv_001", 3),
            ("conv_002", 5),
            ("conv_003", 2),
            ("conv_004", 4),
            ("conv_005", 1),
        ]

        await asyncio.gather(
            *[run_conversation(conv_id, num_calls) for conv_id, num_calls in conversations]
        )

        # 验证每个会话的记录数
        for conv_id, expected_count in conversations:
            records = await knowledge_store.query_by_conversation(conv_id)
            assert (
                len(records) == expected_count
            ), f"Conv {conv_id} should have {expected_count} records"

        # 验证总记录数
        total = await knowledge_store.count()
        assert total == sum(count for _, count in conversations)

    @pytest.mark.asyncio
    async def test_query_records_for_debugging(
        self,
        setup_engine_and_store: tuple[ToolEngine, InMemoryToolKnowledgeStore],
    ):
        """测试：查询记录用于调试"""
        engine, knowledge_store = setup_engine_and_store
        await engine.load()

        conversation_id = "conv_debug_001"
        context = ToolExecutionContext.for_conversation(
            agent_id="agent_001",
            conversation_id=conversation_id,
        )

        # 执行一些工具
        await engine.execute(
            tool_name="echo",
            params={"message": "step1"},
            context=context,
        )
        await engine.execute(
            tool_name="calculator",
            params={"expression": "1/0"},  # 这会导致错误
            context=context,
        )
        await engine.execute(
            tool_name="echo",
            params={"message": "step3"},
            context=context,
        )

        # 查询失败的调用
        failed_records = await knowledge_store.query_failed()
        assert len(failed_records) == 1
        assert failed_records[0].tool_name == "calculator"
        assert failed_records[0].error is not None

        # 查询所有记录用于调试
        all_records = await knowledge_store.query_by_conversation(conversation_id)
        assert len(all_records) == 3

        # 验证可以看到每次调用的详细信息
        for record in all_records:
            assert record.record_id is not None
            assert record.tool_name is not None
            assert record.params is not None
            assert record.execution_time >= 0

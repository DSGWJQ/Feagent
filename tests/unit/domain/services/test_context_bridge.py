"""ContextBridge 上下文桥接测试

TDD测试 - 高级上下文管理功能

Phase 3.3: 高级上下文 (ContextBridge)

测试分类：
1. 上下文数据结构测试 - GlobalContext, SessionContext, WorkflowContext, NodeContext
2. 上下文继承测试 - 分层继承关系
3. 上下文桥接测试 - 工作流间上下文传递
4. 上下文摘要测试 - LLM智能摘要
5. 真实业务场景测试 - 复杂上下文管理
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestGlobalContext:
    """全局上下文测试"""

    def test_create_global_context(self):
        """测试：创建全局上下文

        真实业务场景：
        - 用户登录系统，创建全局上下文
        - 包含用户偏好、系统配置等只读信息

        验收标准：
        - 全局上下文不可变
        - 包含用户ID和偏好
        """
        from src.domain.services.context_bridge import GlobalContext

        ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"theme": "dark", "language": "zh-CN"},
            system_config={"max_tokens": 4096},
            global_goals=[],
        )

        assert ctx.user_id == "user_123"
        assert ctx.user_preferences["theme"] == "dark"
        assert ctx.system_config["max_tokens"] == 4096

    def test_global_context_is_immutable(self):
        """测试：全局上下文不可变

        验收标准：
        - 尝试修改全局上下文应该失败或产生副本
        """
        from src.domain.services.context_bridge import GlobalContext

        ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"theme": "dark"},
            system_config={},
            global_goals=[],
        )

        # 全局上下文应该是只读的
        assert ctx.is_readonly() is True


class TestSessionContext:
    """会话上下文测试"""

    def test_create_session_context(self):
        """测试：创建会话上下文

        真实业务场景：
        - 用户开始一个对话会话
        - 会话上下文继承全局上下文

        验收标准：
        - 会话上下文包含对话历史
        - 会话上下文引用全局上下文
        """
        from src.domain.services.context_bridge import GlobalContext, SessionContext

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        assert session_ctx.session_id == "session_abc"
        assert session_ctx.global_context.user_id == "user_123"
        assert session_ctx.conversation_history == []

    def test_push_and_pop_goal(self):
        """测试：目标栈操作

        真实业务场景：
        - 用户说："帮我创建一个用户管理系统"
        - 系统分解为多个子目标，入栈
        - 完成一个子目标后，出栈

        验收标准：
        - 目标可以入栈
        - 目标可以出栈
        - 可以获取当前目标
        """
        from src.domain.services.context_bridge import GlobalContext, SessionContext
        from src.domain.services.goal_decomposer import Goal

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 入栈目标
        goal1 = Goal(id="goal_1", description="创建用户表")
        goal2 = Goal(id="goal_2", description="创建API接口")

        session_ctx.push_goal(goal1)
        session_ctx.push_goal(goal2)

        # 当前目标是最后入栈的
        assert session_ctx.current_goal().id == "goal_2"

        # 出栈
        popped = session_ctx.pop_goal()
        assert popped.id == "goal_2"
        assert session_ctx.current_goal().id == "goal_1"

    def test_add_conversation_history(self):
        """测试：添加对话历史

        真实业务场景：
        - 用户和系统多轮对话
        - 每轮对话记录到历史

        验收标准：
        - 可以添加对话消息
        - 对话历史按时间顺序
        """
        from src.domain.services.context_bridge import GlobalContext, SessionContext

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.add_message("user", "帮我创建一个TODO应用")
        session_ctx.add_message("assistant", "好的，我来帮您创建TODO应用")

        assert len(session_ctx.conversation_history) == 2
        assert session_ctx.conversation_history[0]["role"] == "user"
        assert session_ctx.conversation_history[1]["role"] == "assistant"


class TestWorkflowContext:
    """工作流上下文测试"""

    def test_create_workflow_context(self):
        """测试：创建工作流上下文

        真实业务场景：
        - 执行一个工作流
        - 工作流有自己的上下文，引用会话上下文

        验收标准：
        - 工作流上下文与会话上下文关联
        - 工作流上下文隔离
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        assert workflow_ctx.workflow_id == "workflow_xyz"
        assert workflow_ctx.session_context.session_id == "session_abc"

    def test_set_and_get_node_output(self):
        """测试：设置和获取节点输出

        真实业务场景：
        - 节点A执行完成，输出数据
        - 节点B需要获取节点A的输出

        验收标准：
        - 可以存储节点输出
        - 可以通过节点ID获取输出
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # 设置节点输出
        workflow_ctx.set_node_output("node_a", {"result": "success", "data": [1, 2, 3]})

        # 获取完整输出
        output = workflow_ctx.get_node_output("node_a")
        assert output["result"] == "success"

        # 获取特定字段
        data = workflow_ctx.get_node_output("node_a", "data")
        assert data == [1, 2, 3]

    def test_workflow_variables(self):
        """测试：工作流变量

        真实业务场景：
        - 工作流执行过程中需要共享变量
        - 如：计数器、累加器、状态标志

        验收标准：
        - 可以设置工作流级变量
        - 可以获取和更新变量
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # 设置变量
        workflow_ctx.set_variable("counter", 0)
        workflow_ctx.set_variable("status", "running")

        assert workflow_ctx.get_variable("counter") == 0
        assert workflow_ctx.get_variable("status") == "running"

        # 更新变量
        workflow_ctx.set_variable("counter", 5)
        assert workflow_ctx.get_variable("counter") == 5


class TestNodeContext:
    """节点上下文测试"""

    def test_create_node_context(self):
        """测试：创建节点上下文

        真实业务场景：
        - 执行单个节点
        - 节点有临时的输入输出上下文

        验收标准：
        - 节点上下文引用工作流上下文
        - 节点上下文是临时的
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        node_ctx = NodeContext(node_id="node_1", workflow_context=workflow_ctx)

        assert node_ctx.node_id == "node_1"
        assert node_ctx.workflow_context.workflow_id == "workflow_xyz"
        assert node_ctx.execution_state == "pending"

    def test_node_input_output(self):
        """测试：节点输入输出

        真实业务场景：
        - 节点接收输入数据
        - 节点处理后产生输出数据

        验收标准：
        - 节点可以设置输入
        - 节点可以设置输出
        - 执行状态可以更新
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        node_ctx = NodeContext(node_id="node_1", workflow_context=workflow_ctx)

        # 设置输入
        node_ctx.set_inputs({"query": "hello", "limit": 10})
        assert node_ctx.inputs["query"] == "hello"

        # 更新状态
        node_ctx.start()
        assert node_ctx.execution_state == "running"

        # 设置输出
        node_ctx.set_outputs({"result": "world", "count": 1})
        assert node_ctx.outputs["result"] == "world"

        # 完成
        node_ctx.complete()
        assert node_ctx.execution_state == "completed"


class TestContextBridge:
    """上下文桥接测试"""

    @pytest.mark.asyncio
    async def test_transfer_context_between_workflows(self):
        """测试：在工作流之间传递上下文

        真实业务场景：
        - 工作流A完成，需要把结果传给工作流B
        - 例如：数据获取工作流 -> 数据处理工作流

        验收标准：
        - 源工作流的输出能传递到目标工作流
        - 目标工作流能访问传递的数据
        """
        from src.domain.services.context_bridge import (
            ContextBridge,
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 源工作流
        source_workflow = WorkflowContext(workflow_id="workflow_a", session_context=session_ctx)
        source_workflow.set_node_output("fetch_node", {"data": [1, 2, 3]})
        source_workflow.set_variable("total", 6)

        # 目标工作流
        target_workflow = WorkflowContext(workflow_id="workflow_b", session_context=session_ctx)

        # Mock摘要器
        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(
            return_value={
                "summary": "获取了3个数据项",
                "key_outputs": {"data": [1, 2, 3]},
                "important_values": {"total": 6},
            }
        )

        bridge = ContextBridge(summarizer=mock_summarizer)

        # 传递上下文（不摘要）
        transferred = await bridge.transfer(
            source=source_workflow, target=target_workflow, summarize=False
        )

        # 目标工作流可以访问传递的数据
        assert "__transferred__" in target_workflow.variables
        assert "data" in transferred["outputs"]["fetch_node"]

    @pytest.mark.asyncio
    async def test_transfer_with_summarization(self):
        """测试：传递上下文时进行摘要

        真实业务场景：
        - 大量数据需要传递给下一个工作流
        - 使用LLM摘要减少token消耗

        验收标准：
        - 传递时调用摘要器
        - 传递的数据是摘要后的
        """
        from src.domain.services.context_bridge import (
            ContextBridge,
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        source_workflow = WorkflowContext(workflow_id="workflow_a", session_context=session_ctx)
        source_workflow.set_node_output("big_data_node", {"data": list(range(1000))})

        target_workflow = WorkflowContext(workflow_id="workflow_b", session_context=session_ctx)

        # Mock摘要器
        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(
            return_value={
                "summary": "包含1000个数据项，范围0-999",
                "key_outputs": {"count": 1000, "range": [0, 999]},
                "important_values": {},
            }
        )

        bridge = ContextBridge(summarizer=mock_summarizer)

        transferred = await bridge.transfer(
            source=source_workflow, target=target_workflow, summarize=True, max_tokens=500
        )

        # 验证摘要器被调用
        mock_summarizer.summarize.assert_called_once()

        # 传递的是摘要数据
        assert "summary" in transferred


class TestContextSummarizer:
    """上下文摘要测试"""

    @pytest.mark.asyncio
    async def test_summarize_context_data(self):
        """测试：摘要上下文数据

        真实业务场景：
        - 工作流执行产生大量数据
        - 需要摘要以减少后续处理的token

        验收标准：
        - 摘要包含关键信息
        - 摘要控制在指定token内
        """
        from src.domain.services.context_bridge import ContextSummarizer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "summary": "用户数据获取成功，包含10个用户",
                "key_outputs": {"user_count": 10, "status": "success"},
                "important_values": {"first_user": "Alice", "last_user": "John"},
            }
        )

        summarizer = ContextSummarizer(llm_client=mock_llm)

        data = {
            "outputs": {"users": [{"name": f"User{i}"} for i in range(10)]},
            "variables": {"status": "success"},
        }

        summary = await summarizer.summarize(data, max_tokens=500)

        assert "summary" in summary
        assert summary["key_outputs"]["user_count"] == 10

    @pytest.mark.asyncio
    async def test_handle_llm_error_in_summarization(self):
        """测试：处理摘要时LLM错误

        验收标准：
        - LLM返回无效JSON时抛出明确异常
        """
        from src.domain.services.context_bridge import ContextSummarizer, SummarizationError

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "这不是有效JSON"

        summarizer = ContextSummarizer(llm_client=mock_llm)

        with pytest.raises(SummarizationError):
            await summarizer.summarize({}, max_tokens=500)


class TestRealWorldScenarios:
    """真实业务场景测试"""

    @pytest.mark.asyncio
    async def test_multi_workflow_pipeline(self):
        """测试：多工作流管道

        真实业务场景：
        - 数据获取工作流 -> 数据清洗工作流 -> 数据分析工作流
        - 每个工作流的输出传递给下一个

        验收标准：
        - 上下文能够在多个工作流之间正确传递
        - 每个工作流能访问前置工作流的关键数据
        """
        from src.domain.services.context_bridge import (
            ContextBridge,
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(
            user_id="user_123", user_preferences={}, system_config={}, global_goals=[]
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 工作流1: 数据获取
        fetch_workflow = WorkflowContext(workflow_id="fetch_workflow", session_context=session_ctx)
        fetch_workflow.set_node_output(
            "api_call", {"raw_data": [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]}
        )

        # 工作流2: 数据清洗
        clean_workflow = WorkflowContext(workflow_id="clean_workflow", session_context=session_ctx)

        # 工作流3: 数据分析
        analyze_workflow = WorkflowContext(
            workflow_id="analyze_workflow", session_context=session_ctx
        )

        # Mock摘要器
        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(
            side_effect=[
                {"summary": "获取2条原始数据", "key_outputs": {"count": 2}, "important_values": {}},
                {
                    "summary": "清洗后2条有效数据",
                    "key_outputs": {"valid_count": 2},
                    "important_values": {},
                },
            ]
        )

        bridge = ContextBridge(summarizer=mock_summarizer)

        # 传递: fetch -> clean
        await bridge.transfer(fetch_workflow, clean_workflow, summarize=True)
        assert "__transferred__" in clean_workflow.variables

        # 模拟clean工作流执行
        clean_workflow.set_node_output("clean_node", {"cleaned_data": [1, 2]})

        # 传递: clean -> analyze
        await bridge.transfer(clean_workflow, analyze_workflow, summarize=True)
        assert "__transferred__" in analyze_workflow.variables

    @pytest.mark.asyncio
    async def test_context_inheritance_chain(self):
        """测试：上下文继承链

        真实业务场景：
        - 用户在会话中执行多个工作流
        - 每个工作流都能访问会话级和全局级上下文

        验收标准：
        - 工作流能访问会话上下文
        - 会话能访问全局上下文
        - 节点能访问所有上层上下文
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        # 全局上下文
        global_ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN"},
            system_config={"max_tokens": 4096},
            global_goals=[],
        )

        # 会话上下文
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        session_ctx.add_message("user", "开始数据处理")

        # 工作流上下文
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)
        workflow_ctx.set_variable("current_step", "processing")

        # 节点上下文
        node_ctx = NodeContext(node_id="node_1", workflow_context=workflow_ctx)

        # 验证继承链
        # 节点 -> 工作流
        assert node_ctx.workflow_context.get_variable("current_step") == "processing"
        # 工作流 -> 会话
        assert len(node_ctx.workflow_context.session_context.conversation_history) == 1
        # 会话 -> 全局
        assert (
            node_ctx.workflow_context.session_context.global_context.user_preferences["language"]
            == "zh-CN"
        )

    def test_context_manager_create_and_manage(self):
        """测试：上下文管理器创建和管理

        真实业务场景：
        - 系统启动时创建上下文管理器
        - 管理器负责创建和跟踪所有上下文

        验收标准：
        - 管理器能创建各级上下文
        - 管理器能通过ID获取上下文
        """
        from src.domain.services.context_bridge import ContextManager

        manager = ContextManager()

        # 创建全局上下文
        global_ctx = manager.create_global_context(
            user_id="user_123", user_preferences={"theme": "dark"}
        )

        # 创建会话上下文
        session_ctx = manager.create_session_context(
            session_id="session_abc", global_context=global_ctx
        )

        # 创建工作流上下文
        workflow_ctx = manager.create_workflow_context(
            workflow_id="workflow_xyz", session_context=session_ctx
        )

        # 通过ID获取
        assert manager.get_session_context("session_abc") == session_ctx
        assert manager.get_workflow_context("workflow_xyz") == workflow_ctx

    def test_context_cleanup(self):
        """测试：上下文清理

        真实业务场景：
        - 工作流执行完成后清理上下文
        - 会话结束后清理会话上下文

        验收标准：
        - 可以清理指定上下文
        - 清理后无法获取该上下文
        """
        from src.domain.services.context_bridge import ContextManager

        manager = ContextManager()

        global_ctx = manager.create_global_context(user_id="user_123", user_preferences={})

        session_ctx = manager.create_session_context(
            session_id="session_abc", global_context=global_ctx
        )

        workflow_ctx = manager.create_workflow_context(
            workflow_id="workflow_xyz", session_context=session_ctx
        )

        # 清理工作流上下文
        manager.cleanup_workflow_context("workflow_xyz")
        assert manager.get_workflow_context("workflow_xyz") is None

        # 会话上下文仍然存在
        assert manager.get_session_context("session_abc") is not None

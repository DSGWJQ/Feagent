"""ToolExecutor 测试 - 阶段 4

测试目标：
1. 验证 ToolExecutionContext 上下文管理
2. 验证 ToolExecutionResult 结果结构
3. 验证 ToolEngine.execute() 方法
4. 验证工具子 Agent 协作机制
5. 验证知识库记录
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# 第一部分：ToolExecutionContext 测试
# =============================================================================


class TestToolExecutionContext:
    """工具执行上下文测试"""

    def test_create_context_with_defaults(self):
        """测试：创建默认上下文"""
        from src.domain.services.tool_executor import ToolExecutionContext

        context = ToolExecutionContext()

        assert context.caller_id is None
        assert context.conversation_id is None
        assert context.workflow_id is None
        assert context.timeout == 30.0
        assert context.retry_count == 0
        assert context.max_retries == 3
        assert context.variables == {}

    def test_create_context_with_caller_info(self):
        """测试：创建带调用者信息的上下文"""
        from src.domain.services.tool_executor import ToolExecutionContext

        context = ToolExecutionContext(
            caller_id="agent_123",
            conversation_id="conv_456",
            workflow_id="wf_789",
        )

        assert context.caller_id == "agent_123"
        assert context.conversation_id == "conv_456"
        assert context.workflow_id == "wf_789"

    def test_context_with_variables(self):
        """测试：带变量的上下文"""
        from src.domain.services.tool_executor import ToolExecutionContext

        context = ToolExecutionContext(variables={"user_input": "hello", "api_key": "secret"})

        assert context.variables["user_input"] == "hello"
        assert context.variables["api_key"] == "secret"

    def test_context_timeout_setting(self):
        """测试：超时设置"""
        from src.domain.services.tool_executor import ToolExecutionContext

        context = ToolExecutionContext(timeout=60.0, max_retries=5)

        assert context.timeout == 60.0
        assert context.max_retries == 5

    def test_context_to_dict(self):
        """测试：上下文转换为字典"""
        from src.domain.services.tool_executor import ToolExecutionContext

        context = ToolExecutionContext(
            caller_id="agent_123",
            conversation_id="conv_456",
            timeout=45.0,
        )

        data = context.to_dict()

        assert data["caller_id"] == "agent_123"
        assert data["conversation_id"] == "conv_456"
        assert data["timeout"] == 45.0

    def test_context_for_conversation_agent(self):
        """测试：为对话 Agent 创建上下文"""
        from src.domain.services.tool_executor import ToolExecutionContext

        context = ToolExecutionContext.for_conversation(
            agent_id="conv_agent_1",
            conversation_id="conv_123",
            user_message="请帮我查询天气",
        )

        assert context.caller_id == "conv_agent_1"
        assert context.conversation_id == "conv_123"
        assert context.variables.get("user_message") == "请帮我查询天气"
        assert context.caller_type == "conversation_agent"

    def test_context_for_workflow_node(self):
        """测试：为工作流节点创建上下文"""
        from src.domain.services.tool_executor import ToolExecutionContext

        context = ToolExecutionContext.for_workflow(
            workflow_id="wf_123",
            node_id="node_456",
            inputs={"data": "value"},
        )

        assert context.workflow_id == "wf_123"
        assert context.variables.get("node_id") == "node_456"
        assert context.variables.get("inputs") == {"data": "value"}
        assert context.caller_type == "workflow_node"


# =============================================================================
# 第二部分：ToolExecutionResult 测试
# =============================================================================


class TestToolExecutionResult:
    """工具执行结果测试"""

    def test_create_success_result(self):
        """测试：创建成功结果"""
        from src.domain.services.tool_executor import ToolExecutionResult

        result = ToolExecutionResult.success(
            tool_name="http_request",
            output={"status": 200, "data": "response"},
        )

        assert result.is_success is True
        assert result.tool_name == "http_request"
        assert result.output["status"] == 200
        assert result.error is None

    def test_create_failure_result(self):
        """测试：创建失败结果"""
        from src.domain.services.tool_executor import ToolExecutionResult

        result = ToolExecutionResult.failure(
            tool_name="http_request",
            error="Connection timeout",
            error_type="timeout",
        )

        assert result.is_success is False
        assert result.tool_name == "http_request"
        assert result.error == "Connection timeout"
        assert result.error_type == "timeout"

    def test_result_with_execution_time(self):
        """测试：带执行时间的结果"""
        from src.domain.services.tool_executor import ToolExecutionResult

        result = ToolExecutionResult.success(
            tool_name="llm_call",
            output={"content": "Hello!"},
            execution_time=1.5,
        )

        assert result.execution_time == 1.5

    def test_result_with_metadata(self):
        """测试：带元数据的结果"""
        from src.domain.services.tool_executor import ToolExecutionResult

        result = ToolExecutionResult.success(
            tool_name="http_request",
            output={"data": "response"},
            metadata={
                "request_id": "req_123",
                "retry_count": 2,
            },
        )

        assert result.metadata["request_id"] == "req_123"
        assert result.metadata["retry_count"] == 2

    def test_result_to_dict(self):
        """测试：结果转换为字典"""
        from src.domain.services.tool_executor import ToolExecutionResult

        result = ToolExecutionResult.success(
            tool_name="test_tool",
            output={"key": "value"},
        )

        data = result.to_dict()

        assert data["is_success"] is True
        assert data["tool_name"] == "test_tool"
        assert data["output"]["key"] == "value"
        assert "executed_at" in data

    def test_result_validation_errors(self):
        """测试：包含验证错误的结果"""
        from src.domain.services.tool_executor import ToolExecutionResult

        result = ToolExecutionResult.validation_failure(
            tool_name="http_request",
            validation_errors=[
                {"parameter": "url", "error": "缺少必填参数"},
                {"parameter": "method", "error": "无效的枚举值"},
            ],
        )

        assert result.is_success is False
        assert result.error_type == "validation_error"
        assert len(result.validation_errors) == 2


# =============================================================================
# 第三部分：ToolEngine.execute() 测试
# =============================================================================


class TestToolEngineExecute:
    """ToolEngine.execute() 方法测试"""

    @pytest.fixture
    def tool_with_handler(self, tmp_path):
        """创建带执行器的工具"""
        tool_yaml = """
name: test_echo_tool
description: 回显工具，返回输入参数
category: custom
version: "1.0.0"
parameters:
  - name: message
    type: string
    required: true
    description: 要回显的消息
entry:
  type: builtin
  handler: echo
"""
        (tmp_path / "test_echo_tool.yaml").write_text(tool_yaml, encoding="utf-8")
        return tmp_path

    @pytest.mark.asyncio
    async def test_execute_validates_params_first(self, tool_with_handler):
        """测试：执行前先验证参数"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        config = ToolEngineConfig(tools_directory=str(tool_with_handler))
        engine = ToolEngine(config=config)
        await engine.load()

        context = ToolExecutionContext()

        # 缺少必填参数
        result = await engine.execute(
            tool_name="test_echo_tool",
            params={},
            context=context,
        )

        assert result.is_success is False
        assert result.error_type == "validation_error"

    @pytest.mark.asyncio
    async def test_execute_with_valid_params(self, tool_with_handler):
        """测试：有效参数执行"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import (
            ToolExecutionContext,
        )

        config = ToolEngineConfig(tools_directory=str(tool_with_handler))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册模拟执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"echoed": "hello world"}
        engine.register_executor("echo", mock_executor)

        context = ToolExecutionContext()

        result = await engine.execute(
            tool_name="test_echo_tool",
            params={"message": "hello world"},
            context=context,
        )

        assert result.is_success is True
        assert result.output["echoed"] == "hello world"
        mock_executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, tool_with_handler):
        """测试：工具不存在"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        config = ToolEngineConfig(tools_directory=str(tool_with_handler))
        engine = ToolEngine(config=config)
        await engine.load()

        context = ToolExecutionContext()

        result = await engine.execute(
            tool_name="nonexistent_tool",
            params={"param": "value"},
            context=context,
        )

        assert result.is_success is False
        assert result.error_type == "tool_not_found"

    @pytest.mark.asyncio
    async def test_execute_emits_events(self, tool_with_handler):
        """测试：执行时发送事件"""
        from src.domain.services.tool_engine import (
            ToolEngine,
            ToolEngineConfig,
            ToolEngineEventType,
        )
        from src.domain.services.tool_executor import ToolExecutionContext

        config = ToolEngineConfig(tools_directory=str(tool_with_handler))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"result": "ok"}
        engine.register_executor("echo", mock_executor)

        events = []

        def on_event(event):
            events.append(event)

        engine.subscribe(on_event)

        context = ToolExecutionContext()
        await engine.execute(
            tool_name="test_echo_tool",
            params={"message": "test"},
            context=context,
        )

        event_types = [e.event_type for e in events]
        assert ToolEngineEventType.EXECUTION_STARTED in event_types
        assert ToolEngineEventType.EXECUTION_COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, tool_with_handler):
        """测试：执行超时"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        config = ToolEngineConfig(tools_directory=str(tool_with_handler))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册一个慢执行器
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(5)
            return {"result": "ok"}

        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = slow_execute
        engine.register_executor("echo", mock_executor)

        context = ToolExecutionContext(timeout=0.1)  # 100ms 超时

        result = await engine.execute(
            tool_name="test_echo_tool",
            params={"message": "test"},
            context=context,
        )

        assert result.is_success is False
        assert result.error_type == "timeout"

    @pytest.mark.asyncio
    async def test_execute_handles_executor_error(self, tool_with_handler):
        """测试：处理执行器错误"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        config = ToolEngineConfig(tools_directory=str(tool_with_handler))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册一个会抛出异常的执行器
        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = RuntimeError("执行器内部错误")
        engine.register_executor("echo", mock_executor)

        context = ToolExecutionContext()

        result = await engine.execute(
            tool_name="test_echo_tool",
            params={"message": "test"},
            context=context,
        )

        assert result.is_success is False
        assert result.error_type == "execution_error"
        assert "执行器内部错误" in result.error


# =============================================================================
# 第四部分：ToolSubAgent 测试
# =============================================================================


class TestToolSubAgent:
    """工具子 Agent 测试"""

    @pytest.fixture
    def mock_tool_engine(self):
        """创建模拟的 ToolEngine"""
        engine = MagicMock()
        engine.execute = AsyncMock()
        return engine

    @pytest.mark.asyncio
    async def test_create_tool_sub_agent(self, mock_tool_engine):
        """测试：创建工具子 Agent"""
        from src.domain.services.tool_executor import ToolSubAgent

        sub_agent = ToolSubAgent(
            agent_id="tool_sub_1",
            tool_engine=mock_tool_engine,
            parent_agent_id="conv_agent_1",
        )

        assert sub_agent.agent_id == "tool_sub_1"
        assert sub_agent.parent_agent_id == "conv_agent_1"

    @pytest.mark.asyncio
    async def test_sub_agent_execute_tool(self, mock_tool_engine):
        """测试：子 Agent 执行工具"""
        from src.domain.services.tool_executor import (
            ToolExecutionResult,
            ToolSubAgent,
        )

        # 设置模拟返回
        mock_tool_engine.execute.return_value = ToolExecutionResult.success(
            tool_name="http_request",
            output={"data": "response"},
        )

        sub_agent = ToolSubAgent(
            agent_id="tool_sub_1",
            tool_engine=mock_tool_engine,
            parent_agent_id="conv_agent_1",
        )

        result = await sub_agent.execute(
            tool_name="http_request",
            params={"url": "https://api.example.com"},
        )

        assert result.is_success is True
        mock_tool_engine.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_sub_agent_isolated_execution(self, mock_tool_engine):
        """测试：子 Agent 隔离执行"""
        from src.domain.services.tool_executor import (
            ToolExecutionResult,
            ToolSubAgent,
        )
        from src.domain.value_objects.execution_context import ExecutionContext

        mock_tool_engine.execute.return_value = ToolExecutionResult.success(
            tool_name="test_tool",
            output={"result": "value"},
        )

        # 创建父上下文
        parent_context = ExecutionContext.create()
        parent_context.set_variable("shared_data", "original")

        sub_agent = ToolSubAgent(
            agent_id="tool_sub_1",
            tool_engine=mock_tool_engine,
            parent_agent_id="conv_agent_1",
            parent_context=parent_context,
        )

        result = await sub_agent.execute(
            tool_name="test_tool",
            params={"input": "test"},
        )

        # 验证子 Agent 使用了隔离上下文
        assert result.is_success is True
        # 父上下文不应被修改
        assert parent_context.get_variable("shared_data") == "original"

    @pytest.mark.asyncio
    async def test_sub_agent_reports_to_parent(self, mock_tool_engine):
        """测试：子 Agent 向父 Agent 报告结果"""
        from src.domain.services.tool_executor import (
            ToolExecutionResult,
            ToolSubAgent,
        )

        mock_tool_engine.execute.return_value = ToolExecutionResult.success(
            tool_name="test_tool",
            output={"key": "value"},
        )

        results_received = []

        def on_result(result):
            results_received.append(result)

        sub_agent = ToolSubAgent(
            agent_id="tool_sub_1",
            tool_engine=mock_tool_engine,
            parent_agent_id="conv_agent_1",
            on_result_callback=on_result,
        )

        await sub_agent.execute(
            tool_name="test_tool",
            params={},
        )

        assert len(results_received) == 1
        assert results_received[0].is_success is True


# =============================================================================
# 第五部分：知识库记录测试
# =============================================================================


class TestToolExecutionKnowledgeRecording:
    """工具执行知识库记录测试"""

    @pytest.fixture
    def mock_knowledge_recorder(self):
        """创建模拟的知识库记录器"""
        recorder = MagicMock()
        recorder.record = AsyncMock()
        return recorder

    @pytest.mark.asyncio
    async def test_record_successful_execution(self, tmp_path, mock_knowledge_recorder):
        """测试：记录成功的执行"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        # 创建工具
        tool_yaml = """
name: test_tool
description: 测试工具
category: custom
parameters:
  - name: input
    type: string
    required: true
    description: 输入参数
entry:
  type: builtin
  handler: test
"""
        (tmp_path / "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册执行器和知识库记录器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"output": "result"}
        engine.register_executor("test", mock_executor)
        engine.set_knowledge_recorder(mock_knowledge_recorder)

        context = ToolExecutionContext(
            caller_id="agent_1",
            conversation_id="conv_1",
        )

        result = await engine.execute(
            tool_name="test_tool",
            params={"input": "test_input"},
            context=context,
        )

        # 验证执行成功
        assert result.is_success is True

        # 验证知识库被调用
        mock_knowledge_recorder.record.assert_called_once()
        call_args = mock_knowledge_recorder.record.call_args
        record_data = call_args[0][0]

        assert record_data["tool_name"] == "test_tool"
        assert record_data["success"] is True
        assert "output" in record_data

    @pytest.mark.asyncio
    async def test_record_failed_execution(self, tmp_path, mock_knowledge_recorder):
        """测试：记录失败的执行"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        tool_yaml = """
name: test_tool
description: 测试工具
category: custom
parameters:
  - name: input
    type: string
    required: true
    description: 输入参数
entry:
  type: builtin
  handler: test
"""
        (tmp_path / "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册会失败的执行器
        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = RuntimeError("执行失败")
        engine.register_executor("test", mock_executor)
        engine.set_knowledge_recorder(mock_knowledge_recorder)

        context = ToolExecutionContext()

        result = await engine.execute(
            tool_name="test_tool",
            params={"input": "test"},
            context=context,
        )

        # 验证执行失败
        assert result.is_success is False

        # 验证失败也被记录
        mock_knowledge_recorder.record.assert_called_once()
        call_args = mock_knowledge_recorder.record.call_args
        record_data = call_args[0][0]

        assert record_data["success"] is False
        assert "error" in record_data


# =============================================================================
# 第六部分：ConversationAgent 集成测试
# =============================================================================


class TestConversationAgentToolIntegration:
    """ConversationAgent 工具调用集成测试"""

    @pytest.mark.asyncio
    async def test_conversation_agent_triggers_tool(self, tmp_path):
        """测试：对话 Agent 触发工具调用"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import (
            ToolSubAgent,
        )

        # 创建工具
        tool_yaml = """
name: weather_query
description: 查询天气
category: custom
parameters:
  - name: city
    type: string
    required: true
    description: 城市名称
entry:
  type: builtin
  handler: weather
"""
        (tmp_path / "weather_query.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册模拟执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {
            "city": "北京",
            "weather": "晴",
            "temperature": 25,
        }
        engine.register_executor("weather", mock_executor)

        # 模拟 ConversationAgent 创建子 Agent 执行工具
        sub_agent = ToolSubAgent(
            agent_id="tool_sub_weather",
            tool_engine=engine,
            parent_agent_id="conversation_agent_1",
        )

        result = await sub_agent.execute(
            tool_name="weather_query",
            params={"city": "北京"},
        )

        assert result.is_success is True
        assert result.output["city"] == "北京"
        assert result.output["weather"] == "晴"


# =============================================================================
# 第七部分：Workflow 节点工具调用测试
# =============================================================================


class TestWorkflowNodeToolExecution:
    """Workflow 节点工具调用测试"""

    @pytest.mark.asyncio
    async def test_workflow_node_uses_same_tool_engine(self, tmp_path):
        """测试：Workflow 节点使用相同的 ToolEngine"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        # 创建工具
        tool_yaml = """
name: data_transform
description: 数据转换工具
category: custom
parameters:
  - name: data
    type: object
    required: true
    description: 待转换数据
  - name: format
    type: string
    required: true
    enum: [json, xml, csv]
    description: 目标格式
entry:
  type: builtin
  handler: transform
"""
        (tmp_path / "data_transform.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 注册执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"transformed": "data"}
        engine.register_executor("transform", mock_executor)

        # 模拟 Workflow 节点调用
        context = ToolExecutionContext.for_workflow(
            workflow_id="wf_123",
            node_id="transform_node_1",
            inputs={"previous_result": "data"},
        )

        result = await engine.execute(
            tool_name="data_transform",
            params={"data": {"key": "value"}, "format": "json"},
            context=context,
        )

        assert result.is_success is True
        # 验证上下文包含工作流信息
        assert context.workflow_id == "wf_123"

    @pytest.mark.asyncio
    async def test_tool_result_flows_to_next_node(self, tmp_path):
        """测试：工具结果流向下一个节点"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.tool_executor import ToolExecutionContext

        tool_yaml = """
name: api_call
description: API 调用工具
category: http
parameters:
  - name: endpoint
    type: string
    required: true
    description: API 端点
entry:
  type: builtin
  handler: api
"""
        (tmp_path / "api_call.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {
            "status": "success",
            "data": {"users": [{"id": 1}, {"id": 2}]},
        }
        engine.register_executor("api", mock_executor)

        context = ToolExecutionContext.for_workflow(
            workflow_id="wf_user_flow",
            node_id="api_node",
            inputs={},
        )

        result = await engine.execute(
            tool_name="api_call",
            params={"endpoint": "/api/users"},
            context=context,
        )

        # 结果可以传递给下一个节点
        assert result.is_success is True
        assert result.output["data"]["users"][0]["id"] == 1

        # 结果可序列化（用于节点间传递）
        result_dict = result.to_dict()
        assert "output" in result_dict

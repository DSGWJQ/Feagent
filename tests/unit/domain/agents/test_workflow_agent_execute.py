"""Phase 16: WorkflowAgent 重写 - TDD 测试

测试功能：
1. WorkflowExecutionResult 标准结构
2. ReflectionResult 反思结果结构
3. execute(workflow) 执行工作流
4. reflect(result) 反思评估
5. 事件传递链路：WorkflowAgent → CoordinatorAgent → ConversationAgent
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus

# ==================== Phase 16.1: 执行结果标准结构 ====================


class TestWorkflowExecutionResult:
    """测试工作流执行结果结构"""

    def test_execution_result_exists(self):
        """测试：WorkflowExecutionResult 应存在"""
        from src.domain.agents.workflow_agent import WorkflowExecutionResult

        assert WorkflowExecutionResult is not None

    def test_execution_result_success_case(self):
        """测试：成功的执行结果"""
        from src.domain.agents.workflow_agent import WorkflowExecutionResult

        result = WorkflowExecutionResult(
            success=True,
            summary="工作流执行成功",
            workflow_id="wf_1",
            executed_nodes=["node_1", "node_2", "node_3"],
            outputs={"final_output": "数据处理完成"},
        )

        assert result.success is True
        assert result.summary == "工作流执行成功"
        assert len(result.executed_nodes) == 3
        assert result.failed_node is None
        assert result.error_message is None

    def test_execution_result_failure_case(self):
        """测试：失败的执行结果"""
        from src.domain.agents.workflow_agent import WorkflowExecutionResult

        result = WorkflowExecutionResult(
            success=False,
            summary="节点执行失败",
            workflow_id="wf_1",
            executed_nodes=["node_1", "node_2"],
            failed_node="node_3",
            error_message="API 调用超时",
            diagnostics={"timeout": 30, "retries": 3},
        )

        assert result.success is False
        assert result.failed_node == "node_3"
        assert result.error_message == "API 调用超时"
        assert result.diagnostics["timeout"] == 30

    def test_execution_result_has_execution_time(self):
        """测试：执行结果应包含执行时间"""
        from src.domain.agents.workflow_agent import WorkflowExecutionResult

        result = WorkflowExecutionResult(
            success=True,
            summary="完成",
            workflow_id="wf_1",
            execution_time=2.5,
        )

        assert result.execution_time == 2.5

    def test_execution_result_to_dict(self):
        """测试：执行结果应能转换为字典"""
        from src.domain.agents.workflow_agent import WorkflowExecutionResult

        result = WorkflowExecutionResult(
            success=True,
            summary="完成",
            workflow_id="wf_1",
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert result_dict["workflow_id"] == "wf_1"


# ==================== Phase 16.2: 反思结果结构 ====================


class TestReflectionResult:
    """测试反思结果结构"""

    def test_reflection_result_exists(self):
        """测试：ReflectionResult 应存在"""
        from src.domain.agents.workflow_agent import ReflectionResult

        assert ReflectionResult is not None

    def test_reflection_result_success_assessment(self):
        """测试：成功执行的反思"""
        from src.domain.agents.workflow_agent import ReflectionResult

        reflection = ReflectionResult(
            assessment="执行成功，所有节点按预期完成",
            issues=[],
            recommendations=[],
            confidence=0.95,
            should_retry=False,
        )

        assert reflection.assessment.startswith("执行成功")
        assert len(reflection.issues) == 0
        assert reflection.should_retry is False

    def test_reflection_result_failure_assessment(self):
        """测试：失败执行的反思"""
        from src.domain.agents.workflow_agent import ReflectionResult

        reflection = ReflectionResult(
            assessment="执行失败，数据验证节点出错",
            issues=["数据格式不正确", "缺少必要字段"],
            recommendations=["检查输入数据格式", "添加数据预处理步骤"],
            confidence=0.85,
            should_retry=True,
            suggested_modifications={"node_3": {"add_validation": True}},
        )

        assert len(reflection.issues) == 2
        assert len(reflection.recommendations) == 2
        assert reflection.should_retry is True
        assert "node_3" in reflection.suggested_modifications


# ==================== Phase 16.3: WorkflowAgent execute() ====================


class TestWorkflowAgentExecute:
    """测试 WorkflowAgent execute() 方法"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def mock_executor(self):
        """模拟工作流执行器"""
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value={
                "success": True,
                "outputs": {"result": "数据处理完成"},
                "executed_nodes": ["node_1", "node_2"],
            }
        )
        return executor

    def test_workflow_agent_exists(self):
        """测试：WorkflowAgent 应存在"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        assert WorkflowAgent is not None

    def test_workflow_agent_has_execute_method(self, event_bus):
        """测试：WorkflowAgent 应有 execute 方法"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        agent = WorkflowAgent(event_bus=event_bus)

        assert hasattr(agent, "execute")

    @pytest.mark.asyncio
    async def test_execute_returns_execution_result(self, event_bus, mock_executor):
        """测试：execute 应返回 WorkflowExecutionResult"""
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionResult,
        )

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor)

        workflow = {"id": "wf_1", "nodes": [], "edges": []}
        result = await agent.execute(workflow)

        assert isinstance(result, WorkflowExecutionResult)

    @pytest.mark.asyncio
    async def test_execute_success_workflow(self, event_bus, mock_executor):
        """测试：成功执行工作流"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor)

        workflow = {
            "id": "wf_1",
            "name": "数据处理",
            "nodes": [{"id": "node_1"}, {"id": "node_2"}],
            "edges": [],
        }

        result = await agent.execute(workflow)

        assert result.success is True
        assert result.workflow_id == "wf_1"
        assert "node_1" in result.executed_nodes

    @pytest.mark.asyncio
    async def test_execute_failure_workflow(self, event_bus):
        """测试：执行失败的工作流"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": False,
                "error": "节点执行失败",
                "failed_node": "node_2",
                "executed_nodes": ["node_1"],
            }
        )

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor)

        workflow = {"id": "wf_1", "nodes": [], "edges": []}
        result = await agent.execute(workflow)

        assert result.success is False
        assert result.failed_node == "node_2"

    @pytest.mark.asyncio
    async def test_execute_publishes_start_event(self, event_bus, mock_executor):
        """测试：执行时应发布开始事件"""
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionStartedEvent,
        )

        received_events = []

        async def capture_event(event):
            received_events.append(event)

        event_bus.subscribe(WorkflowExecutionStartedEvent, capture_event)

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor)
        await agent.execute({"id": "wf_1", "nodes": [], "edges": []})

        assert len(received_events) == 1
        assert received_events[0].workflow_id == "wf_1"

    @pytest.mark.asyncio
    async def test_execute_publishes_completed_event(self, event_bus, mock_executor):
        """测试：执行完成后应发布完成事件"""
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionCompletedEvent,
        )

        received_events = []

        async def capture_event(event):
            received_events.append(event)

        event_bus.subscribe(WorkflowExecutionCompletedEvent, capture_event)

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor)
        await agent.execute({"id": "wf_1", "nodes": [], "edges": []})

        assert len(received_events) == 1
        assert received_events[0].success is True


# ==================== Phase 16.4: WorkflowAgent reflect() ====================


class TestWorkflowAgentReflect:
    """测试 WorkflowAgent reflect() 方法"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def mock_llm(self):
        """模拟反思 LLM"""
        llm = MagicMock()
        llm.reflect = AsyncMock(
            return_value={
                "assessment": "执行成功，所有节点正常完成",
                "issues": [],
                "recommendations": [],
                "confidence": 0.9,
                "should_retry": False,
            }
        )
        return llm

    def test_workflow_agent_has_reflect_method(self, event_bus):
        """测试：WorkflowAgent 应有 reflect 方法"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        agent = WorkflowAgent(event_bus=event_bus)

        assert hasattr(agent, "reflect")

    @pytest.mark.asyncio
    async def test_reflect_returns_reflection_result(self, event_bus, mock_llm):
        """测试：reflect 应返回 ReflectionResult"""
        from src.domain.agents.workflow_agent import (
            ReflectionResult,
            WorkflowAgent,
            WorkflowExecutionResult,
        )

        agent = WorkflowAgent(event_bus=event_bus, llm=mock_llm)

        execution_result = WorkflowExecutionResult(
            success=True,
            summary="完成",
            workflow_id="wf_1",
        )

        reflection = await agent.reflect(execution_result)

        assert isinstance(reflection, ReflectionResult)

    @pytest.mark.asyncio
    async def test_reflect_success_result(self, event_bus, mock_llm):
        """测试：成功执行的反思"""
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionResult,
        )

        agent = WorkflowAgent(event_bus=event_bus, llm=mock_llm)

        execution_result = WorkflowExecutionResult(
            success=True,
            summary="所有节点执行成功",
            workflow_id="wf_1",
            executed_nodes=["node_1", "node_2", "node_3"],
        )

        reflection = await agent.reflect(execution_result)

        assert reflection.should_retry is False
        assert len(reflection.issues) == 0

    @pytest.mark.asyncio
    async def test_reflect_failure_result(self, event_bus):
        """测试：失败执行的反思"""
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionResult,
        )

        mock_llm = MagicMock()
        mock_llm.reflect = AsyncMock(
            return_value={
                "assessment": "执行失败，需要修复",
                "issues": ["数据验证失败"],
                "recommendations": ["添加数据清洗步骤"],
                "confidence": 0.85,
                "should_retry": True,
                "suggested_modifications": {"node_2": {"fix": "validation"}},
            }
        )

        agent = WorkflowAgent(event_bus=event_bus, llm=mock_llm)

        execution_result = WorkflowExecutionResult(
            success=False,
            summary="数据验证节点失败",
            workflow_id="wf_1",
            failed_node="node_2",
            error_message="数据格式错误",
        )

        reflection = await agent.reflect(execution_result)

        assert reflection.should_retry is True
        assert len(reflection.issues) > 0
        assert len(reflection.recommendations) > 0

    @pytest.mark.asyncio
    async def test_reflect_publishes_reflection_event(self, event_bus, mock_llm):
        """测试：反思完成后应发布事件"""
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionResult,
            WorkflowReflectionCompletedEvent,
        )

        received_events = []

        async def capture_event(event):
            received_events.append(event)

        event_bus.subscribe(WorkflowReflectionCompletedEvent, capture_event)

        agent = WorkflowAgent(event_bus=event_bus, llm=mock_llm)

        execution_result = WorkflowExecutionResult(
            success=True,
            summary="完成",
            workflow_id="wf_1",
        )

        await agent.reflect(execution_result)

        assert len(received_events) == 1
        assert received_events[0].workflow_id == "wf_1"


# ==================== Phase 16.5: 事件传递链路 ====================


class TestEventChain:
    """测试事件传递链路：WorkflowAgent → CoordinatorAgent → ConversationAgent"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.asyncio
    async def test_coordinator_receives_reflection_event(self, event_bus):
        """测试：CoordinatorAgent 应接收反思事件"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionResult,
            WorkflowReflectionCompletedEvent,
        )

        _coordinator = CoordinatorAgent(event_bus=event_bus)  # noqa: F841

        received_reflections = []

        async def handle_reflection(event):
            received_reflections.append(event)

        event_bus.subscribe(WorkflowReflectionCompletedEvent, handle_reflection)

        mock_llm = MagicMock()
        mock_llm.reflect = AsyncMock(
            return_value={
                "assessment": "完成",
                "issues": [],
                "recommendations": [],
                "confidence": 0.9,
                "should_retry": False,
            }
        )

        workflow_agent = WorkflowAgent(event_bus=event_bus, llm=mock_llm)

        execution_result = WorkflowExecutionResult(
            success=True,
            summary="完成",
            workflow_id="wf_1",
        )

        await workflow_agent.reflect(execution_result)

        assert len(received_reflections) == 1

    @pytest.mark.asyncio
    async def test_execute_and_reflect_flow(self, event_bus):
        """测试：执行 + 反思完整流程"""
        from src.domain.agents.workflow_agent import (
            WorkflowAgent,
            WorkflowExecutionCompletedEvent,
            WorkflowReflectionCompletedEvent,
        )

        execution_events = []
        reflection_events = []

        async def capture_execution(event):
            execution_events.append(event)

        async def capture_reflection(event):
            reflection_events.append(event)

        event_bus.subscribe(WorkflowExecutionCompletedEvent, capture_execution)
        event_bus.subscribe(WorkflowReflectionCompletedEvent, capture_reflection)

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": True,
                "outputs": {},
                "executed_nodes": ["node_1"],
            }
        )

        mock_llm = MagicMock()
        mock_llm.reflect = AsyncMock(
            return_value={
                "assessment": "完成",
                "issues": [],
                "recommendations": [],
                "confidence": 0.9,
                "should_retry": False,
            }
        )

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor, llm=mock_llm)

        # 执行工作流
        result = await agent.execute({"id": "wf_1", "nodes": [], "edges": []})

        # 反思结果
        await agent.reflect(result)

        # 验证事件链
        assert len(execution_events) == 1
        assert len(reflection_events) == 1
        assert execution_events[0].workflow_id == "wf_1"
        assert reflection_events[0].workflow_id == "wf_1"


# ==================== Phase 16.6: 真实场景测试 ====================


class TestRealWorldScenarios:
    """真实场景测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.asyncio
    async def test_scenario_successful_data_pipeline(self, event_bus):
        """场景：成功的数据处理流水线"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": True,
                "outputs": {
                    "processed_count": 1000,
                    "output_file": "/data/output.csv",
                },
                "executed_nodes": ["fetch_data", "transform", "save"],
                "execution_time": 5.2,
            }
        )

        mock_llm = MagicMock()
        mock_llm.reflect = AsyncMock(
            return_value={
                "assessment": "数据处理成功完成，共处理 1000 条记录",
                "issues": [],
                "recommendations": [],
                "confidence": 0.98,
                "should_retry": False,
            }
        )

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor, llm=mock_llm)

        workflow = {
            "id": "data_pipeline_1",
            "name": "数据处理流水线",
            "nodes": [
                {"id": "fetch_data", "type": "http"},
                {"id": "transform", "type": "code"},
                {"id": "save", "type": "database"},
            ],
            "edges": [
                {"source": "fetch_data", "target": "transform"},
                {"source": "transform", "target": "save"},
            ],
        }

        # 执行
        result = await agent.execute(workflow)
        assert result.success is True
        assert len(result.executed_nodes) == 3

        # 反思
        reflection = await agent.reflect(result)
        assert reflection.should_retry is False
        assert reflection.confidence > 0.9

    @pytest.mark.asyncio
    async def test_scenario_failed_workflow_with_retry_recommendation(self, event_bus):
        """场景：失败的工作流，建议重试"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": False,
                "error": "API 请求超时",
                "failed_node": "fetch_data",
                "executed_nodes": [],
            }
        )

        mock_llm = MagicMock()
        mock_llm.reflect = AsyncMock(
            return_value={
                "assessment": "工作流因网络超时失败",
                "issues": ["API 请求超时", "网络不稳定"],
                "recommendations": ["增加超时时间", "添加重试机制"],
                "confidence": 0.8,
                "should_retry": True,
                "suggested_modifications": {"fetch_data": {"timeout": 60, "retries": 3}},
            }
        )

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor, llm=mock_llm)

        workflow = {"id": "wf_1", "nodes": [{"id": "fetch_data"}], "edges": []}

        result = await agent.execute(workflow)
        reflection = await agent.reflect(result)

        assert result.success is False
        assert reflection.should_retry is True
        assert "fetch_data" in reflection.suggested_modifications

    @pytest.mark.asyncio
    async def test_scenario_partial_success_workflow(self, event_bus):
        """场景：部分成功的工作流"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": False,
                "error": "数据验证失败",
                "failed_node": "validate",
                "executed_nodes": ["fetch", "transform"],
                "outputs": {"partial_result": "已处理部分数据"},
            }
        )

        mock_llm = MagicMock()
        mock_llm.reflect = AsyncMock(
            return_value={
                "assessment": "工作流部分完成，验证步骤失败",
                "issues": ["数据格式不符合预期"],
                "recommendations": ["检查数据源格式", "添加数据清洗步骤"],
                "confidence": 0.75,
                "should_retry": False,  # 不建议直接重试，需要修改
            }
        )

        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor, llm=mock_llm)

        result = await agent.execute({"id": "wf_1", "nodes": [], "edges": []})
        reflection = await agent.reflect(result)

        assert result.success is False
        assert len(result.executed_nodes) == 2
        assert reflection.should_retry is False
        assert len(reflection.recommendations) > 0

    @pytest.mark.asyncio
    async def test_scenario_no_llm_fallback_reflection(self, event_bus):
        """场景：无 LLM 时的回退反思"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value={
                "success": True,
                "outputs": {},
                "executed_nodes": ["node_1"],
            }
        )

        # 不提供 LLM
        agent = WorkflowAgent(event_bus=event_bus, executor=mock_executor)

        result = await agent.execute({"id": "wf_1", "nodes": [], "edges": []})
        reflection = await agent.reflect(result)

        # 应该有基本的反思结果
        assert reflection is not None
        assert reflection.assessment != ""

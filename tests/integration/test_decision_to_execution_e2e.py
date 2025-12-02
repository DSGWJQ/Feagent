"""决策到执行端到端测试 - Phase 8.6

真实场景测试：用户输入 -> ConversationAgent规划 -> DecisionExecutionBridge -> WorkflowAgent执行

测试场景：
1. 用户请求"分析销售数据"
2. ConversationAgent 生成工作流规划
3. 发布 DecisionMadeEvent
4. DecisionExecutionBridge 接收并验证
5. WorkflowAgent 批量创建节点并执行
6. 返回执行结果
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestEndToEndDecisionExecution:
    """端到端决策执行测试"""

    @pytest.mark.asyncio
    async def test_full_pipeline_from_user_input_to_execution(self):
        """测试完整管道：用户输入 -> 规划 -> 执行"""
        from src.domain.agents.conversation_agent import (
            ConversationAgent,
            DecisionType,
        )
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.decision_execution_bridge import (
            DecisionExecutionBridge,
            ExecutionResultEvent,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 1. 设置基础设施
        event_bus = EventBus()
        global_ctx = GlobalContext(user_id="user_001")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_001", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 2. 设置 Mock LLM（模拟 ConversationAgent 的规划能力）
        # 注意：使用与 NodeRegistry 兼容的节点格式
        mock_llm = MagicMock()
        mock_llm.plan_workflow = AsyncMock(
            return_value={
                "name": "销售数据分析流程",
                "nodes": [
                    {"name": "读取数据", "type": "python", "code": "data = read_csv('sales.csv')"},
                    {"name": "数据清洗", "type": "python", "code": "clean_data = clean(data)"},
                    {"name": "统计分析", "type": "python", "code": "stats = analyze(clean_data)"},
                ],
                "edges": [
                    {"source": "读取数据", "target": "数据清洗"},
                    {"source": "数据清洗", "target": "统计分析"},
                ],
            }
        )
        mock_llm.decide_action = AsyncMock(
            return_value={
                "action_type": "create_workflow_plan",
                "plan": mock_llm.plan_workflow.return_value,
            }
        )

        # 3. 设置 Mock 执行器
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"status": "success", "output": "executed"})

        # 4. 创建 ConversationAgent
        conversation_agent = ConversationAgent(
            session_context=session_ctx,
            llm=mock_llm,
            event_bus=event_bus,
        )

        # 5. 创建 WorkflowAgent 工厂
        def create_workflow_agent():
            return WorkflowAgent(
                workflow_context=workflow_ctx,
                node_factory=factory,
                node_executor=mock_executor,
                event_bus=event_bus,
            )

        # 6. 创建并启动 DecisionExecutionBridge
        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            workflow_agent_factory=create_workflow_agent,
        )
        await bridge.start()

        # 7. 收集执行结果
        execution_results = []

        async def result_collector(event):
            execution_results.append(event)

        event_bus.subscribe(ExecutionResultEvent, result_collector)

        # 8. 模拟用户输入 -> ConversationAgent 生成规划并发布决策
        user_input = "分析销售数据并生成报告"
        await conversation_agent.create_workflow_plan_and_publish(user_input)

        # 9. 验证结果
        # 应该收到执行结果事件
        assert len(execution_results) >= 1
        result = execution_results[0]
        assert result.status == "completed"
        assert result.decision_type == DecisionType.CREATE_WORKFLOW_PLAN.value

        # 清理
        await bridge.stop()

    @pytest.mark.asyncio
    async def test_complex_workflow_with_parallel_branches(self):
        """测试复杂工作流：带并行分支的执行"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 设置
        event_bus = EventBus()
        global_ctx = GlobalContext(user_id="user_001")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_001", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # Mock 执行器
        execution_order = []
        mock_executor = MagicMock()

        async def track_execution(node_id, config, inputs):
            execution_order.append(node_id)
            return {"status": "success", "node_id": node_id}

        mock_executor.execute = AsyncMock(side_effect=track_execution)

        # 创建复杂规划（有并行分支）- 只使用 Python 节点以避免 LLM 配置要求
        #     读取数据
        #        |
        #     数据清洗
        #      /    \
        #   图表    报告
        #      \    /
        #      汇总
        plan = WorkflowPlan(
            name="复杂分析流程",
            goal="多分支分析",
            nodes=[
                NodeDefinition(node_type=NodeType.PYTHON, name="读取数据", code="data = read()"),
                NodeDefinition(
                    node_type=NodeType.PYTHON, name="数据清洗", code="clean = process(data)"
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON, name="生成图表", code="chart = plot(clean)"
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON, name="生成报告", code="report = create_report(clean)"
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON, name="汇总", code="summary = merge(chart, report)"
                ),
            ],
            edges=[
                EdgeDefinition(source_node="读取数据", target_node="数据清洗"),
                EdgeDefinition(source_node="数据清洗", target_node="生成图表"),
                EdgeDefinition(source_node="数据清洗", target_node="生成报告"),
                EdgeDefinition(source_node="生成图表", target_node="汇总"),
                EdgeDefinition(source_node="生成报告", target_node="汇总"),
            ],
        )

        # 创建 WorkflowAgent 并执行
        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        result = await agent.execute_plan(plan)

        # 验证
        assert result["status"] == "completed"
        assert result["nodes_created"] == 5
        assert result["edges_created"] == 5

        # 验证执行顺序（拓扑排序）
        # 读取数据 必须在 数据清洗 之前
        assert execution_order.index(result["node_mapping"]["读取数据"]) < execution_order.index(
            result["node_mapping"]["数据清洗"]
        )
        # 数据清洗 必须在 生成图表 和 生成报告 之前
        clean_idx = execution_order.index(result["node_mapping"]["数据清洗"])
        chart_idx = execution_order.index(result["node_mapping"]["生成图表"])
        report_idx = execution_order.index(result["node_mapping"]["生成报告"])
        assert clean_idx < chart_idx
        assert clean_idx < report_idx
        # 汇总 必须在最后
        assert execution_order.index(result["node_mapping"]["汇总"]) == len(execution_order) - 1

    @pytest.mark.asyncio
    async def test_validation_rejection_flow(self):
        """测试验证拒绝流程"""
        from src.domain.agents.conversation_agent import (
            DecisionMadeEvent,
            DecisionType,
        )
        from src.domain.services.decision_execution_bridge import (
            DecisionExecutionBridge,
            ValidationRejectedEvent,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        # 创建拒绝验证的验证器（使用 MagicMock 模拟）
        validator = MagicMock()
        validator.validate = MagicMock(
            return_value=MagicMock(
                status=MagicMock(value="rejected"),
                violations=["操作被拒绝：不安全的操作"],
            )
        )

        # 收集拒绝事件
        rejection_events = []

        async def rejection_collector(event):
            rejection_events.append(event)

        event_bus.subscribe(ValidationRejectedEvent, rejection_collector)

        # 创建桥接器
        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            decision_validator=validator,
        )
        await bridge.start()

        # 发布决策
        decision_event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.CREATE_WORKFLOW_PLAN.value,
            decision_id="dec_001",
            payload={"nodes": [], "edges": []},
        )
        await event_bus.publish(decision_event)

        # 验证拒绝事件
        assert len(rejection_events) == 1
        assert rejection_events[0].decision_id == "dec_001"
        assert "不安全的操作" in rejection_events[0].violations[0]

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_error_recovery_in_execution(self):
        """测试执行中的错误恢复"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_001")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_001", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 第一次调用失败，第二次成功
        call_count = 0
        mock_executor = MagicMock()

        async def flaky_executor(node_id, config, inputs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("网络超时")
            return {"status": "success"}

        mock_executor.execute = AsyncMock(side_effect=flaky_executor)

        plan = WorkflowPlan(
            name="恢复测试",
            goal="测试错误恢复",
            nodes=[
                NodeDefinition(node_type=NodeType.PYTHON, name="Step1", code="x=1"),
            ],
            edges=[],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
        )

        # 第一次执行应该失败
        result1 = await agent.execute_plan(plan)
        assert result1["status"] == "failed"

        # 重置 agent 并再次执行
        agent2 = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
        )
        result2 = await agent2.execute_plan(plan)
        assert result2["status"] == "completed"


class TestRealWorldScenarios:
    """真实世界场景测试"""

    @pytest.mark.asyncio
    async def test_data_processing_pipeline(self):
        """测试：数据处理管道场景"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 场景：ETL 数据处理管道
        # 1. 从数据库读取原始数据
        # 2. 数据清洗和转换
        # 3. 聚合统计
        # 4. 写入目标表

        global_ctx = GlobalContext(user_id="data_engineer")
        session_ctx = SessionContext(session_id="etl_session", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="etl_pipeline", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 模拟执行结果
        node_outputs = {}
        mock_executor = MagicMock()

        async def etl_executor(node_id, config, inputs):
            # 模拟不同节点的输出
            if "extract" in str(config).lower():
                output = {"rows": 1000, "columns": 10}
            elif "transform" in str(config).lower():
                output = {"rows": 950, "cleaned": True}
            elif "aggregate" in str(config).lower():
                output = {"summary": {"total": 50000, "avg": 52.6}}
            else:
                output = {"loaded": True, "rows_written": 950}
            node_outputs[node_id] = output
            return output

        mock_executor.execute = AsyncMock(side_effect=etl_executor)

        plan = WorkflowPlan(
            name="ETL Pipeline",
            goal="Process daily sales data",
            nodes=[
                NodeDefinition(
                    node_type=NodeType.DATABASE,
                    name="Extract",
                    query="SELECT * FROM raw_sales WHERE date = TODAY()",
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="Transform",
                    code="cleaned = clean_nulls(data); normalized = normalize(cleaned)",
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="Aggregate",
                    code="summary = data.groupby('region').agg({'sales': 'sum'})",
                ),
                NodeDefinition(
                    node_type=NodeType.DATABASE,
                    name="Load",
                    query="INSERT INTO daily_summary VALUES (...)",
                ),
            ],
            edges=[
                EdgeDefinition(source_node="Extract", target_node="Transform"),
                EdgeDefinition(source_node="Transform", target_node="Aggregate"),
                EdgeDefinition(source_node="Aggregate", target_node="Load"),
            ],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
        )

        result = await agent.execute_plan(plan)

        # 验证
        assert result["status"] == "completed"
        assert result["nodes_created"] == 4
        assert mock_executor.execute.call_count == 4

    @pytest.mark.asyncio
    async def test_customer_support_automation(self):
        """测试：客服自动化场景"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 场景：客服工单自动处理 - 使用 Python 节点模拟各步骤
        # 1. 分析客户问题
        # 2. 查询知识库
        # 3. 生成回复
        # 4. 发送邮件

        global_ctx = GlobalContext(user_id="support_system")
        session_ctx = SessionContext(session_id="ticket_123", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="auto_reply", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value={"status": "success", "processed": True})

        plan = WorkflowPlan(
            name="客服自动回复",
            goal="自动处理客户工单",
            nodes=[
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="问题分析",
                    code="keywords = analyze_question(ticket)",
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="知识库查询",
                    code="results = search_kb(keywords)",
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="生成回复",
                    code="reply = generate_reply(results)",
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="发送邮件",
                    code="send_email(customer, reply)",
                ),
            ],
            edges=[
                EdgeDefinition(source_node="问题分析", target_node="知识库查询"),
                EdgeDefinition(source_node="知识库查询", target_node="生成回复"),
                EdgeDefinition(source_node="生成回复", target_node="发送邮件"),
            ],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
        )

        result = await agent.execute_plan(plan)

        assert result["status"] == "completed"
        assert result["nodes_created"] == 4
        assert "问题分析" in result["node_mapping"]
        assert "发送邮件" in result["node_mapping"]


class TestIntegrationWithExistingComponents:
    """与现有组件的集成测试"""

    @pytest.mark.asyncio
    async def test_integration_with_event_bus_middleware(self):
        """测试与事件总线中间件的集成"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        events_logged = []

        # 添加日志中间件
        def logging_middleware(event):
            events_logged.append(
                {
                    "type": type(event).__name__,
                    "source": event.source,
                }
            )
            return event

        event_bus.add_middleware(logging_middleware)

        # 创建桥接器
        bridge = DecisionExecutionBridge(event_bus=event_bus)
        await bridge.start()

        # 发布事件
        event = DecisionMadeEvent(
            source="test_source",
            decision_type=DecisionType.RESPOND.value,  # 非可执行类型，会被忽略
            decision_id="dec_001",
            payload={"message": "Hello"},
        )
        await event_bus.publish(event)

        # 验证中间件记录了事件
        assert len(events_logged) >= 1
        assert events_logged[0]["type"] == "DecisionMadeEvent"

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_context_propagation_through_workflow(self):
        """测试上下文在工作流中的传播"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # GlobalContext 不支持动态属性，直接使用构造函数参数
        global_ctx = GlobalContext(user_id="user_001")

        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        workflow_ctx = WorkflowContext(workflow_id="wf_001", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 验证上下文传播
        captured_contexts = []
        mock_executor = MagicMock()

        async def context_capturing_executor(node_id, config, inputs):
            # 捕获当前上下文信息
            captured_contexts.append(
                {
                    "node_id": node_id,
                    "inputs": inputs,
                }
            )
            return {"output": f"processed_{node_id}"}

        mock_executor.execute = AsyncMock(side_effect=context_capturing_executor)

        plan = WorkflowPlan(
            name="Context Test",
            goal="Test context propagation",
            nodes=[
                NodeDefinition(node_type=NodeType.PYTHON, name="Step1", code="x=1"),
                NodeDefinition(node_type=NodeType.PYTHON, name="Step2", code="y=x+1"),
            ],
            edges=[
                EdgeDefinition(source_node="Step1", target_node="Step2"),
            ],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
        )

        result = await agent.execute_plan(plan)

        # 验证上下文传播
        assert result["status"] == "completed"
        assert len(captured_contexts) == 2

        # 第二个节点应该接收到第一个节点的输出
        step2_context = captured_contexts[1]
        assert len(step2_context["inputs"]) > 0

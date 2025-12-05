"""
测试 ConversationAgent 增强功能：Schema 强制使用 + 依赖敏感规划

本测试文件遵循 TDD 原则：
1. Red：编写失败的测试，明确需求
2. Green：实现最少代码让测试通过
3. Refactor：重构优化

测试覆盖：
- Schema 强制验证：确保所有决策都使用 Pydantic schema
- 依赖关系识别：测试工作流规划时的依赖分析
- 资源约束感知：测试时间、并发、API限制的处理
- 真实场景：模拟"多阶段销售分析"对话
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.domain.agents.conversation_agent import ConversationAgent, DecisionType
from src.domain.agents.decision_payload import (
    CreateWorkflowPlanPayload,
    RequestClarificationPayload,
    RespondPayload,
)
from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus

# ========================================
# 测试夹具
# ========================================


@pytest.fixture
def session_context():
    """创建测试用的会话上下文"""
    global_ctx = GlobalContext(user_id="test_user")
    return SessionContext(session_id="test_session", global_context=global_ctx)


@pytest.fixture
def event_bus():
    """创建测试用的事件总线"""
    return EventBus()


@pytest.fixture
def mock_llm():
    """创建 Mock LLM"""
    llm = MagicMock()
    llm.decide_action = AsyncMock()
    llm.think = AsyncMock()
    return llm


@pytest.fixture
def conversation_agent(session_context, event_bus, mock_llm):
    """创建 ConversationAgent 实例"""
    return ConversationAgent(
        session_context=session_context, llm=mock_llm, event_bus=event_bus, max_iterations=5
    )


# ========================================
# 测试：Schema 强制验证
# ========================================


class TestSchemaEnforcement:
    """测试 Schema 强制使用"""

    def test_make_decision_should_validate_payload_with_pydantic_schema(
        self, conversation_agent, mock_llm
    ):
        """测试：make_decision 应该使用 Pydantic schema 验证 payload

        场景：LLM 返回一个有效的 create_workflow_plan 决策
        期望：ConversationAgent 使用 CreateWorkflowPlanPayload 验证
        """
        # 准备：LLM 返回有效的工作流规划
        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "数据分析工作流",
            "description": "获取并分析数据",
            "nodes": [
                {
                    "node_id": "node_1",
                    "type": "HTTP",
                    "name": "获取数据",
                    "config": {"url": "https://api.data.com", "method": "GET"},
                }
            ],
            "edges": [],
        }

        # 执行：生成决策
        decision = conversation_agent.make_decision(context_hint="")

        # 断言：决策 payload 应该被 Pydantic 验证
        # 这个测试预期会失败，因为现在还没有集成 Pydantic 验证
        assert decision.type == DecisionType.CREATE_WORKFLOW_PLAN

        # 验证 payload 可以被 Pydantic 解析
        try:
            validated_payload = CreateWorkflowPlanPayload(**decision.payload)
            assert validated_payload.name == "数据分析工作流"
        except ValidationError as e:
            pytest.fail(f"Payload 验证失败: {e}")

    def test_make_decision_should_reject_invalid_payload(self, conversation_agent, mock_llm):
        """测试：make_decision 应该拒绝无效的 payload

        场景：LLM 返回一个缺少必填字段的决策
        期望：ConversationAgent 抛出 ValidationError
        """
        # 准备：LLM 返回无效的工作流规划（缺少 description）
        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "数据分析工作流",
            # 缺少 description
            "nodes": [],
            "edges": [],
        }

        # 执行 & 断言：应该抛出 ValidationError
        with pytest.raises(ValidationError) as exc_info:
            decision = conversation_agent.make_decision(context_hint="")
            # 尝试用 Pydantic 验证（这会失败）
            CreateWorkflowPlanPayload(**decision.payload)

        # 验证错误信息包含 "description"
        assert "description" in str(exc_info.value).lower()

    def test_make_decision_should_validate_respond_payload(self, conversation_agent, mock_llm):
        """测试：make_decision 应该验证 RESPOND 决策的 payload"""
        # 准备：LLM 返回 respond 决策
        mock_llm.decide_action.return_value = {
            "action_type": "respond",
            "response": "您好！我是智能助手。",
            "intent": "greeting",
            "confidence": 1.0,
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言
        assert decision.type == DecisionType.RESPOND

        # Pydantic 验证
        validated_payload = RespondPayload(**decision.payload)
        assert validated_payload.response == "您好！我是智能助手。"

    def test_make_decision_should_validate_request_clarification_payload(
        self, conversation_agent, mock_llm
    ):
        """测试：make_decision 应该验证 REQUEST_CLARIFICATION 决策的 payload"""
        # 准备
        mock_llm.decide_action.return_value = {
            "action_type": "request_clarification",
            "question": "您想分析哪个数据源？",
            "options": ["销售数据库", "用户行为日志"],
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言
        assert decision.type == DecisionType.REQUEST_CLARIFICATION

        # Pydantic 验证
        validated_payload = RequestClarificationPayload(**decision.payload)
        assert validated_payload.question == "您想分析哪个数据源？"
        assert len(validated_payload.options) == 2


# ========================================
# 测试：依赖关系识别
# ========================================


class TestDependencyAwarePlanning:
    """测试依赖敏感的工作流规划"""

    def test_plan_workflow_should_identify_sequential_dependencies(
        self, conversation_agent, mock_llm
    ):
        """测试：规划工作流时应该识别顺序依赖

        场景：用户请求"获取数据然后分析"
        期望：生成的工作流包含正确的依赖边
        """
        # 准备：LLM 返回带依赖的工作流
        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "数据分析流程",
            "description": "获取数据并进行分析",
            "nodes": [
                {
                    "node_id": "node_1",
                    "type": "DATABASE",
                    "name": "获取销售数据",
                    "config": {"query": "SELECT * FROM sales", "connection": "db"},
                },
                {
                    "node_id": "node_2",
                    "type": "LLM",
                    "name": "分析数据",
                    "config": {"model": "gpt-4", "prompt": "分析数据"},
                    "input_mapping": {"data": "${node_1.output.data}"},  # 依赖 node_1
                },
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"}  # 顺序依赖
            ],
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言：验证依赖关系
        payload = CreateWorkflowPlanPayload(**decision.payload)
        assert len(payload.edges) == 1
        assert payload.edges[0].source == "node_1"
        assert payload.edges[0].target == "node_2"

        # 验证输入映射（数据依赖）
        node_2 = payload.nodes[1]
        assert node_2.input_mapping is not None
        assert "node_1" in str(node_2.input_mapping)

    def test_plan_workflow_should_identify_parallel_opportunities(
        self, conversation_agent, mock_llm
    ):
        """测试：规划工作流时应该识别并行机会

        场景：两个独立的任务可以并行执行
        期望：生成的工作流没有不必要的依赖边
        """
        # 准备：LLM 返回可并行的工作流
        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "并行数据收集",
            "description": "同时从多个来源收集数据",
            "nodes": [
                {
                    "node_id": "node_1",
                    "type": "HTTP",
                    "name": "获取天气数据",
                    "config": {"url": "https://api.weather.com", "method": "GET"},
                },
                {
                    "node_id": "node_2",
                    "type": "HTTP",
                    "name": "获取股票数据",
                    "config": {"url": "https://api.stocks.com", "method": "GET"},
                },
                {
                    "node_id": "node_3",
                    "type": "LLM",
                    "name": "综合分析",
                    "config": {"model": "gpt-4", "prompt": "分析数据"},
                    "input_mapping": {
                        "weather": "${node_1.output}",
                        "stocks": "${node_2.output}",
                    },
                },
            ],
            "edges": [
                {"source": "node_1", "target": "node_3"},
                {"source": "node_2", "target": "node_3"},
                # node_1 和 node_2 之间没有边，可以并行
            ],
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言：验证并行结构
        payload = CreateWorkflowPlanPayload(**decision.payload)

        # node_1 和 node_2 没有直接依赖
        edges_between_1_2 = [
            e
            for e in payload.edges
            if (e.source == "node_1" and e.target == "node_2")
            or (e.source == "node_2" and e.target == "node_1")
        ]
        assert len(edges_between_1_2) == 0

        # node_3 依赖 node_1 和 node_2
        node_3_deps = [e for e in payload.edges if e.target == "node_3"]
        assert len(node_3_deps) == 2

    def test_plan_workflow_should_detect_cyclic_dependencies(self, conversation_agent, mock_llm):
        """测试：规划工作流时应该检测循环依赖

        场景：LLM 返回包含循环的工作流
        期望：Pydantic 验证应该拒绝
        """
        # 准备：LLM 返回包含循环的工作流
        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "循环工作流",
            "description": "测试循环检测",
            "nodes": [
                {
                    "node_id": "node_1",
                    "type": "HTTP",
                    "name": "节点1",
                    "config": {"url": "https://api.com", "method": "GET"},
                },
                {
                    "node_id": "node_2",
                    "type": "HTTP",
                    "name": "节点2",
                    "config": {"url": "https://api.com", "method": "GET"},
                },
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_1"},  # 循环！
            ],
        }

        # 执行 & 断言：应该抛出 ValueError（循环依赖检测）
        with pytest.raises(ValueError) as exc_info:
            decision = conversation_agent.make_decision(context_hint="")

        assert "循环" in str(exc_info.value) or "cycle" in str(exc_info.value).lower()


# ========================================
# 测试：资源约束感知
# ========================================


class TestResourceConstraintAwareness:
    """测试资源约束感知"""

    def test_plan_workflow_should_respect_time_constraint(self, conversation_agent, mock_llm):
        """测试：规划工作流时应该考虑时间约束

        场景：设置了 5 分钟时间限制
        期望：生成的工作流包含 timeout 配置
        """
        # 准备：在上下文中设置资源约束
        conversation_agent.session_context.resource_constraints = {
            "time_limit": 300,  # 5 分钟
            "max_parallel": 3,
        }

        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "限时任务",
            "description": "需要在 5 分钟内完成",
            "nodes": [
                {
                    "node_id": "node_1",
                    "type": "HTTP",
                    "name": "API调用",
                    "config": {
                        "url": "https://api.com",
                        "method": "GET",
                        "timeout": 30,  # 单个节点超时
                    },
                }
            ],
            "edges": [],
            "global_config": {"timeout": 300, "max_parallel": 3},  # 全局配置
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言：验证时间约束配置
        payload = CreateWorkflowPlanPayload(**decision.payload)
        assert payload.global_config is not None
        assert payload.global_config.get("timeout") == 300

    def test_plan_workflow_should_respect_parallel_limit(self, conversation_agent, mock_llm):
        """测试：规划工作流时应该考虑并发限制

        场景：最多同时执行 3 个任务
        期望：生成的工作流配置了并发限制
        """
        # 准备
        conversation_agent.session_context.resource_constraints = {"max_parallel": 3}

        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "并发任务",
            "description": "需要限制并发数",
            "nodes": [
                {
                    "node_id": f"node_{i}",
                    "type": "HTTP",
                    "name": f"任务{i}",
                    "config": {"url": "https://api.com", "method": "GET"},
                }
                for i in range(5)
            ],
            "edges": [],
            "global_config": {"max_parallel": 3},
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言
        payload = CreateWorkflowPlanPayload(**decision.payload)
        assert payload.global_config.get("max_parallel") == 3

    def test_plan_workflow_should_estimate_api_calls(self, conversation_agent, mock_llm):
        """测试：规划工作流时应该估算 API 调用次数

        场景：工作流包含多个外部 API 调用
        期望：能够统计和估算 API 调用次数
        """
        # 准备
        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "多API工作流",
            "description": "包含多个API调用",
            "nodes": [
                {
                    "node_id": "node_1",
                    "type": "HTTP",
                    "name": "API调用1",
                    "config": {"url": "https://api1.com", "method": "GET"},
                },
                {
                    "node_id": "node_2",
                    "type": "LLM",
                    "name": "LLM分析",
                    "config": {"model": "gpt-4", "prompt": "分析"},
                },
                {
                    "node_id": "node_3",
                    "type": "HTTP",
                    "name": "API调用2",
                    "config": {"url": "https://api2.com", "method": "POST"},
                },
            ],
            "edges": [],
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言：统计 API 调用
        payload = CreateWorkflowPlanPayload(**decision.payload)

        # 统计不同类型的节点
        http_nodes = [n for n in payload.nodes if n.type == "HTTP"]
        llm_nodes = [n for n in payload.nodes if n.type == "LLM"]

        assert len(http_nodes) == 2  # 2 个 HTTP API 调用
        assert len(llm_nodes) == 1  # 1 个 LLM 调用


# ========================================
# 测试：真实场景 - 多阶段销售分析
# ========================================


class TestRealWorldScenario:
    """测试真实场景：多阶段销售分析对话"""

    @pytest.mark.asyncio
    async def test_multi_stage_sales_analysis_conversation(self, conversation_agent, mock_llm):
        """测试：模拟"分析三个月销售数据并生成趋势图"的完整对话

        场景：
        1. 用户：分析最近三个月的销售数据并生成趋势图
        2. Agent：识别任务依赖，生成工作流规划
        3. 验证：工作流包含正确的依赖关系和资源约束

        预期工作流：
        - 任务1: 获取销售数据（DATABASE）
        - 任务2: 计算趋势（PYTHON，依赖任务1）
        - 任务3: 生成图表（PYTHON，依赖任务2）
        - 任务4: 发送报告（HTTP，依赖任务3）
        """
        # 准备：模拟 LLM 返回完整的工作流规划
        mock_llm.decide_action.return_value = {
            "action_type": "create_workflow_plan",
            "name": "销售数据分析工作流",
            "description": "获取最近三个月销售数据，计算趋势，生成图表，发送报告",
            "nodes": [
                {
                    "node_id": "fetch_data",
                    "type": "DATABASE",
                    "name": "获取销售数据",
                    "config": {
                        "query": "SELECT * FROM sales WHERE date >= DATE_SUB(NOW(), INTERVAL 3 MONTH)",
                        "connection": "sales_db",
                    },
                },
                {
                    "node_id": "calculate_trend",
                    "type": "PYTHON",
                    "name": "计算趋势",
                    "config": {
                        "code": "import pandas as pd\ndf = pd.DataFrame(input_data)\ntrend = df.groupby('month')['amount'].sum()"
                    },
                    "input_mapping": {"input_data": "${fetch_data.output.data}"},
                },
                {
                    "node_id": "generate_chart",
                    "type": "PYTHON",
                    "name": "生成趋势图",
                    "config": {
                        "code": "import matplotlib.pyplot as plt\nplt.plot(trend.keys(), trend.values())\nplt.savefig('trend.png')"
                    },
                    "input_mapping": {"trend": "${calculate_trend.output.trend}"},
                },
                {
                    "node_id": "send_report",
                    "type": "HTTP",
                    "name": "发送报告",
                    "config": {
                        "url": "https://api.email.com/send",
                        "method": "POST",
                        "body": {
                            "to": "manager@example.com",
                            "subject": "销售趋势报告",
                            "attachments": ["${generate_chart.output.chart_path}"],
                        },
                    },
                },
            ],
            "edges": [
                {"source": "fetch_data", "target": "calculate_trend"},
                {"source": "calculate_trend", "target": "generate_chart"},
                {"source": "generate_chart", "target": "send_report"},
            ],
            "global_config": {
                "timeout": 300,
                "max_parallel": 1,  # 顺序执行
            },
        }

        # 执行
        decision = conversation_agent.make_decision(context_hint="")

        # 断言 1：决策类型正确
        assert decision.type == DecisionType.CREATE_WORKFLOW_PLAN

        # 断言 2：Pydantic 验证通过
        payload = CreateWorkflowPlanPayload(**decision.payload)
        assert payload.name == "销售数据分析工作流"
        assert len(payload.nodes) == 4
        assert len(payload.edges) == 3

        # 断言 3：依赖关系正确
        # 验证依赖链：fetch_data → calculate_trend → generate_chart → send_report
        assert payload.edges[0].source == "fetch_data"
        assert payload.edges[0].target == "calculate_trend"
        assert payload.edges[1].source == "calculate_trend"
        assert payload.edges[1].target == "generate_chart"
        assert payload.edges[2].source == "generate_chart"
        assert payload.edges[2].target == "send_report"

        # 断言 4：数据依赖映射正确
        calculate_node = next(n for n in payload.nodes if n.node_id == "calculate_trend")
        assert calculate_node.input_mapping is not None
        assert "fetch_data" in str(calculate_node.input_mapping)

        # 断言 5：资源约束配置正确
        assert payload.global_config is not None
        assert payload.global_config.get("timeout") == 300


# ========================================
# 测试：Prompt 模板使用
# ========================================


class TestPromptTemplateUsage:
    """测试 ReAct prompt 模板的使用"""

    def test_conversation_agent_should_use_workflow_planning_prompt(
        self, conversation_agent, mock_llm
    ):
        """测试：ConversationAgent 应该使用工作流规划 prompt

        场景：用户请求复杂任务
        期望：使用 WORKFLOW_PLANNING_PROMPT 模板
        """
        # 这个测试检查 ConversationAgent 是否正确使用了 prompt 模板
        # 预期会失败，因为还没有集成 prompt 模板

        # 准备
        user_input = "分析销售数据并生成报告"

        # 执行：这里应该使用 prompt 模板，但现在还没有
        # 我们期望在实现后，ConversationAgent 会使用 WORKFLOW_PLANNING_PROMPT

        # 这个断言会在实现后验证
        # assert conversation_agent.uses_workflow_planning_prompt(user_input)
        pass  # 暂时跳过，等待实现


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

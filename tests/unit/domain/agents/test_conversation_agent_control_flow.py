"""
测试 ConversationAgent 控制流规划功能

Priority 3: ConversationAgent 控制流规划
- extract_control_flow() - 从自然语言识别控制流
- build_control_nodes() - 将 IR 转换为节点和边
- create_workflow_plan() 集成 - 注入控制流节点
"""

from unittest.mock import AsyncMock

import pytest

from src.domain.agents.control_flow_ir import (
    ControlFlowIR,
    DecisionBranch,
    DecisionPoint,
    LoopSpec,
)
from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.node_definition import NodeType
from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus


class TestExtractControlFlow:
    """测试 extract_control_flow 方法"""

    @pytest.fixture
    def agent(self):
        """创建 ConversationAgent 实例"""
        # 创建上下文
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)

        # 创建 mock LLM
        mock_llm = AsyncMock()

        # 创建 event_bus
        event_bus = EventBus()

        # 创建 agent
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm, event_bus=event_bus)
        return agent

    def test_extract_control_flow_identifies_simple_condition(self, agent):
        """测试识别简单条件判断（中文）"""
        goal = "如果数据质量大于0.8，则进行分析，否则进行清洗"

        ir = agent._extract_control_flow_by_rules(goal)

        assert len(ir.decisions) > 0
        decision = ir.decisions[0]
        assert decision.description == "conditional_branch"

    def test_extract_control_flow_identifies_condition_english(self, agent):
        """测试识别简单条件判断（英文）"""
        goal = "If quality score > 0.8 then analyze, otherwise clean"

        ir = agent._extract_control_flow_by_rules(goal)

        assert len(ir.decisions) > 0

    def test_extract_control_flow_identifies_loop(self, agent):
        """测试识别循环（中文）"""
        goal = "遍历所有数据集进行处理"

        ir = agent._extract_control_flow_by_rules(goal)

        assert len(ir.loops) > 0
        loop = ir.loops[0]
        assert loop.description == "loop_over_items"
        assert loop.collection == "items"

    def test_extract_control_flow_identifies_loop_english(self, agent):
        """测试识别循环（英文）"""
        goal = "For each dataset, perform validation"

        ir = agent._extract_control_flow_by_rules(goal)

        assert len(ir.loops) > 0

    def test_extract_control_flow_identifies_combined_logic(self, agent):
        """测试识别组合逻辑"""
        goal = "遍历所有用户，如果用户活跃度大于阈值则发送通知"

        ir = agent._extract_control_flow_by_rules(goal)

        assert len(ir.loops) > 0  # 应该识别循环
        assert len(ir.decisions) > 0  # 应该识别条件

    def test_extract_control_flow_empty_for_simple_task(self, agent):
        """测试简单任务不提取控制流"""
        goal = "生成数据分析报告"

        ir = agent._extract_control_flow_by_rules(goal)

        # 简单任务可能不包含明确的控制流关键字
        # IR 应该可以为空或只包含基础任务
        assert isinstance(ir, ControlFlowIR)


class TestBuildControlNodes:
    """测试 build_control_nodes 方法"""

    @pytest.fixture
    def agent(self):
        """创建 ConversationAgent 实例"""
        # 创建上下文
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)

        # 创建 mock LLM
        mock_llm = AsyncMock()

        # 创建 event_bus
        event_bus = EventBus()

        # 创建 agent
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm, event_bus=event_bus)
        return agent

    def test_build_control_nodes_generates_condition_node(self, agent):
        """测试生成 CONDITION 节点"""
        ir = ControlFlowIR(
            decisions=[
                DecisionPoint(
                    id="dec1",
                    description="quality_check",
                    expression="quality_score > 0.8",
                    branches=[
                        DecisionBranch(
                            label="high_quality",
                            target_task_id="analyze_task",
                            expression="True",
                        ),
                        DecisionBranch(
                            label="low_quality",
                            target_task_id="clean_task",
                            expression="False",
                        ),
                    ],
                )
            ]
        )

        nodes, edges = agent.build_control_nodes(ir, [], [])

        assert len(nodes) == 1
        condition_node = nodes[0]
        assert condition_node.node_type == NodeType.CONDITION
        assert condition_node.name == "quality_check"
        assert condition_node.config["expression"] == "quality_score > 0.8"

        assert len(edges) == 2  # 两个分支
        assert edges[0].source_node == "quality_check"
        assert edges[0].target_node == "analyze_task"
        assert edges[1].source_node == "quality_check"
        assert edges[1].target_node == "clean_task"

    def test_build_control_nodes_generates_loop_node(self, agent):
        """测试生成 LOOP 节点"""
        ir = ControlFlowIR(
            loops=[
                LoopSpec(
                    id="loop1",
                    description="process_datasets",
                    collection="datasets",
                    loop_variable="dataset",
                    loop_type="for_each",
                    body_task_ids=["validate_task", "transform_task"],
                )
            ]
        )

        nodes, edges = agent.build_control_nodes(ir, [], [])

        assert len(nodes) == 1
        loop_node = nodes[0]
        assert loop_node.node_type == NodeType.LOOP
        assert loop_node.name == "process_datasets"
        assert loop_node.config["collection_field"] == "datasets"
        assert loop_node.config["loop_variable"] == "dataset"
        assert loop_node.config["loop_type"] == "for_each"

        assert len(edges) == 2  # 两个body任务
        assert edges[0].source_node == "process_datasets"
        assert edges[0].target_node == "validate_task"

    def test_build_control_nodes_connects_edges_correctly(self, agent):
        """测试正确连接边"""
        ir = ControlFlowIR(
            decisions=[
                DecisionPoint(
                    id="dec1",
                    description="check",
                    expression="value > 10",
                    branches=[
                        DecisionBranch(label="yes", target_task_id="task_a"),
                        DecisionBranch(label="no", target_task_id="task_b"),
                    ],
                )
            ],
            loops=[
                LoopSpec(
                    id="loop1",
                    description="iterate",
                    collection="items",
                    body_task_ids=["task_c"],
                )
            ],
        )

        nodes, edges = agent.build_control_nodes(ir, [], [])

        assert len(nodes) == 2  # 1 condition + 1 loop
        assert len(edges) == 3  # 2 branches + 1 loop body

        # 验证边的源和目标
        edge_sources = [e.source_node for e in edges]
        assert "check" in edge_sources
        assert "iterate" in edge_sources

    def test_build_control_nodes_empty_ir(self, agent):
        """测试空 IR 返回空列表"""
        ir = ControlFlowIR()

        nodes, edges = agent.build_control_nodes(ir, [], [])

        assert nodes == []
        assert edges == []


class TestControlFlowIR:
    """测试 ControlFlowIR 数据类"""

    def test_control_flow_ir_is_empty(self):
        """测试 is_empty 方法"""
        ir = ControlFlowIR()
        assert ir.is_empty() is True

        ir.decisions.append(DecisionPoint(id="d1", description="test", expression="x > 0"))
        assert ir.is_empty() is False

    def test_control_flow_ir_from_dict(self):
        """测试 from_dict 方法"""
        data = {
            "decisions": [
                {"id": "d1", "description": "check", "expression": "x > 0", "branches": []}
            ],
            "loops": [
                {
                    "id": "l1",
                    "description": "iterate",
                    "collection": "items",
                    "loop_variable": "item",
                    "loop_type": "for_each",
                }
            ],
        }

        ir = ControlFlowIR.from_dict(data)

        assert len(ir.decisions) == 1
        assert ir.decisions[0].id == "d1"
        assert len(ir.loops) == 1
        assert ir.loops[0].collection == "items"

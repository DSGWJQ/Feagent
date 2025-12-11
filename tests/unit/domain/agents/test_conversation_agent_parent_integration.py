"""ConversationAgent 父节点集成测试

测试 ConversationAgent 创建包含父子节点的工作流计划。
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.node_definition import NodeType
from src.domain.services.event_bus import EventBus


class TestConversationAgentParentNodeIntegration:
    """ConversationAgent 父节点集成测试"""

    @pytest.fixture
    def event_bus(self):
        """创建 EventBus"""
        return EventBus()

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM"""
        llm = Mock()
        llm.plan_workflow = AsyncMock()
        llm.decompose_to_nodes = AsyncMock()
        return llm

    @pytest.fixture
    def session_context(self):
        """创建 SessionContext"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="test_session", global_context=global_ctx)

    @pytest.fixture
    def conversation_agent(self, event_bus, mock_llm, session_context):
        """创建 ConversationAgent"""
        return ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_create_workflow_plan_with_parent_node(self, conversation_agent, mock_llm):
        """测试创建包含父节点的工作流计划"""
        # 模拟 LLM 返回包含父节点的规划
        mock_llm.plan_workflow.return_value = {
            "name": "数据处理流程",
            "description": "完整的数据处理流程",
            "nodes": [
                {
                    "type": "generic",
                    "name": "数据分析流水线",
                    "error_strategy": {
                        "on_failure": "abort",
                        "retry": {"max_attempts": 3},
                    },
                    "resource_limits": {
                        "cpu_limit": "2.0",
                        "memory_limit": "4Gi",
                        "timeout_seconds": 600,
                    },
                    "children": [
                        {
                            "type": "python",
                            "name": "加载数据",
                            "code": "df = pd.read_csv('data.csv')",
                        },
                        {
                            "type": "python",
                            "name": "清洗数据",
                            "code": "df = df.dropna()",
                        },
                        {
                            "type": "python",
                            "name": "分析数据",
                            "code": "result = df.describe()",
                        },
                    ],
                }
            ],
            "edges": [],
        }

        # 创建工作流计划
        plan = await conversation_agent.create_workflow_plan("创建数据分析流程")

        # 验证计划创建成功
        assert plan is not None
        assert plan.name == "数据处理流程"
        assert len(plan.nodes) == 1

        # 验证父节点
        parent_node = plan.nodes[0]
        assert parent_node.node_type == NodeType.GENERIC
        assert parent_node.name == "数据分析流水线"
        assert parent_node.error_strategy is not None
        assert parent_node.error_strategy["on_failure"] == "abort"
        assert parent_node.resource_limits["cpu_limit"] == "2.0"
        assert parent_node.resource_limits["memory_limit"] == "4Gi"

        # 验证子节点
        assert len(parent_node.children) == 3
        assert parent_node.children[0].name == "加载数据"
        assert parent_node.children[1].name == "清洗数据"
        assert parent_node.children[2].name == "分析数据"

        # 验证策略传播
        for child in parent_node.children:
            assert (
                child.error_strategy == parent_node.error_strategy
            ), f"子节点 {child.name} 未继承 error_strategy"
            assert (
                child.resource_limits == parent_node.resource_limits
            ), f"子节点 {child.name} 未继承 resource_limits"
            assert (
                child.inherited_strategy is True
            ), f"子节点 {child.name} inherited_strategy 标志未设置"

    @pytest.mark.asyncio
    async def test_decompose_to_nodes_with_parent_node(self, conversation_agent, mock_llm):
        """测试分解目标为包含父节点的节点列表"""
        # 模拟 LLM 返回包含父节点的节点列表
        mock_llm.decompose_to_nodes.return_value = [
            {
                "type": "generic",
                "name": "ETL 流程",
                "error_strategy": {"on_failure": "skip"},
                "resource_limits": {
                    "cpu_limit": "1.0",
                    "memory_limit": "2Gi",
                },
                "children": [
                    {
                        "type": "python",
                        "name": "提取数据",
                        "code": "data = extract()",
                    },
                    {
                        "type": "python",
                        "name": "转换数据",
                        "code": "data = transform(data)",
                    },
                    {
                        "type": "python",
                        "name": "加载数据",
                        "code": "load(data)",
                    },
                ],
            }
        ]

        # 分解目标
        nodes = await conversation_agent.decompose_to_nodes("创建 ETL 流程")

        # 验证节点列表
        assert len(nodes) == 1

        # 验证父节点
        parent_node = nodes[0]
        assert parent_node.node_type == NodeType.GENERIC
        assert parent_node.name == "ETL 流程"
        assert parent_node.error_strategy["on_failure"] == "skip"

        # 验证子节点
        assert len(parent_node.children) == 3
        assert parent_node.children[0].name == "提取数据"
        assert parent_node.children[1].name == "转换数据"
        assert parent_node.children[2].name == "加载数据"

        # 验证策略传播
        for child in parent_node.children:
            assert child.error_strategy == parent_node.error_strategy
            assert child.resource_limits == parent_node.resource_limits
            assert child.inherited_strategy is True

    @pytest.mark.asyncio
    async def test_create_plan_with_mixed_nodes(self, conversation_agent, mock_llm):
        """测试创建混合节点（父节点 + 普通节点）的计划"""
        mock_llm.plan_workflow.return_value = {
            "name": "混合工作流",
            "description": "包含父节点和普通节点",
            "nodes": [
                {
                    "type": "python",
                    "name": "初始化",
                    "code": "init()",
                },
                {
                    "type": "generic",
                    "name": "核心处理",
                    "error_strategy": {"on_failure": "continue"},
                    "resource_limits": {"timeout_seconds": 300},
                    "children": [
                        {
                            "type": "python",
                            "name": "步骤1",
                            "code": "step1()",
                        },
                        {
                            "type": "python",
                            "name": "步骤2",
                            "code": "step2()",
                        },
                    ],
                },
                {
                    "type": "python",
                    "name": "清理",
                    "code": "cleanup()",
                },
            ],
            "edges": [
                {"source": "初始化", "target": "核心处理"},
                {"source": "核心处理", "target": "清理"},
            ],
        }

        # 创建计划
        plan = await conversation_agent.create_workflow_plan("创建混合工作流")

        # 验证计划
        assert len(plan.nodes) == 3
        assert plan.nodes[0].name == "初始化"
        assert plan.nodes[1].name == "核心处理"
        assert plan.nodes[2].name == "清理"

        # 验证父节点
        parent_node = plan.nodes[1]
        assert parent_node.node_type == NodeType.GENERIC
        assert len(parent_node.children) == 2

        # 验证子节点继承策略
        for child in parent_node.children:
            assert child.error_strategy == parent_node.error_strategy
            assert child.resource_limits == parent_node.resource_limits
            assert child.inherited_strategy is True

        # 验证普通节点没有策略
        assert plan.nodes[0].error_strategy is None
        assert plan.nodes[2].error_strategy is None

    @pytest.mark.asyncio
    async def test_parent_node_without_strategy(self, conversation_agent, mock_llm):
        """测试没有策略的父节点（应该触发验证错误）"""
        mock_llm.plan_workflow.return_value = {
            "name": "无策略父节点",
            "description": "测试",
            "nodes": [
                {
                    "type": "generic",
                    "name": "父节点",
                    # 没有 error_strategy 和 resource_limits
                    "children": [
                        {
                            "type": "python",
                            "name": "子节点",
                            "code": "pass",
                        }
                    ],
                }
            ],
            "edges": [],
        }

        # 创建计划应该失败，因为父节点缺少必需的策略
        with pytest.raises(ValueError, match="父节点必须定义"):
            await conversation_agent.create_workflow_plan("测试")


__all__ = ["TestConversationAgentParentNodeIntegration"]

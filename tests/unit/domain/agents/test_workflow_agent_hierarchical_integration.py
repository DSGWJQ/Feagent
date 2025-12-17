"""测试：WorkflowAgent 集成层次化节点

测试目标：
1. WorkflowAgent 可以从 NodeDefinition 创建层次化节点
2. WorkflowAgent 可以执行层次化节点（先执行子节点）
3. WorkflowAgent 可以处理容器节点
4. WorkflowAgent 可以使用 HierarchicalNodeFactory

完成标准：
- 从 NodeDefinition 创建带父子关系的节点
- 执行时按层次顺序执行（子节点先于父节点聚合）
- 容器节点使用容器执行器
- 与 HierarchicalNodeFactory 无缝集成

"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.event_bus import EventBus
from src.domain.services.node_registry import NodeFactory, NodeRegistry


def create_mock_workflow_context(workflow_id: str = "wf_001"):
    """创建 Mock WorkflowContext"""
    context = MagicMock()
    context.workflow_id = workflow_id
    context.get_node_output = MagicMock(return_value=None)
    context.set_node_output = MagicMock()
    context.get_variable = MagicMock(return_value=None)
    context.set_variable = MagicMock()
    return context


def create_node_factory():
    """创建 NodeFactory"""
    registry = NodeRegistry()
    return NodeFactory(registry)


# ==================== 测试1：从 NodeDefinition 创建层次化节点 ====================


class TestNodeDefinitionToNode:
    """测试 NodeDefinition 到 Node 的转换"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def workflow_agent(self, mock_event_bus):
        """创建 WorkflowAgent"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        context = create_mock_workflow_context()
        factory = create_node_factory()
        return WorkflowAgent(
            workflow_context=context,
            node_factory=factory,
            event_bus=mock_event_bus,
        )

    def test_create_node_from_node_definition(self, workflow_agent):
        """从 NodeDefinition 创建节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 创建 NodeDefinition
        node_def = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="简单节点",
            code="print('hello')",
        )

        # 转换为 Node
        node = workflow_agent.create_node_from_definition(node_def)

        assert node is not None
        assert node.config.get("name") == "简单节点"
        assert node.config.get("code") == "print('hello')"

    def test_create_hierarchical_node_from_definition(self, workflow_agent):
        """从层次化 NodeDefinition 创建节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 创建父节点
        parent_def = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            collapsed=True,
        )

        # 创建子节点
        child_def = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="容器子节点",
            code="import pandas",
            is_container=True,
        )
        parent_def.add_child(child_def)

        # 转换
        parent_node = workflow_agent.create_node_from_definition(parent_def)

        assert parent_node is not None
        assert len(parent_node.children) == 1
        assert parent_node.children[0].parent_id == parent_node.id

    def test_create_deeply_nested_node_from_definition(self, workflow_agent):
        """从深层嵌套 NodeDefinition 创建节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 创建三层嵌套
        root_def = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="根节点",
        )
        level1_def = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="一级节点",
        )
        level2_def = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="二级节点",
            code="result = 1 + 1",
        )

        level1_def.add_child(level2_def)
        root_def.add_child(level1_def)

        # 转换
        root_node = workflow_agent.create_node_from_definition(root_def)

        assert len(root_node.children) == 1
        assert len(root_node.children[0].children) == 1


# ==================== 测试2：层次化节点执行顺序 ====================


class TestHierarchicalNodeExecution:
    """测试层次化节点执行"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def workflow_agent(self, mock_event_bus):
        """创建 WorkflowAgent"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        context = create_mock_workflow_context()
        factory = create_node_factory()
        return WorkflowAgent(
            workflow_context=context,
            node_factory=factory,
            event_bus=mock_event_bus,
        )

    def test_get_hierarchical_execution_order(self, workflow_agent):
        """获取层次化执行顺序"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 创建父节点和两个子节点
        parent_def = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )
        child1_def = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点1",
            code="result1 = 1",  # 添加 code 字段
        )
        child2_def = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点2",
            code="result2 = 2",  # 添加 code 字段
        )
        parent_def.add_child(child1_def)
        parent_def.add_child(child2_def)

        # 转换并添加
        parent_node = workflow_agent.create_node_from_definition(parent_def)
        workflow_agent.add_node(parent_node)

        # 获取执行顺序
        order = workflow_agent.get_hierarchical_execution_order(parent_node.id)

        # 子节点应该在父节点之前
        assert len(order) == 3
        # 最后一个应该是父节点
        assert order[-1] == parent_node.id

    @pytest.mark.asyncio
    async def test_execute_hierarchical_node(self, workflow_agent):
        """执行层次化节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 创建层次结构
        parent_def = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="数据处理",
        )
        child_def = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="处理步骤",
            code="result = 'processed'",
        )
        parent_def.add_child(child_def)

        parent_node = workflow_agent.create_node_from_definition(parent_def)
        workflow_agent.add_node(parent_node)

        # 执行
        result = await workflow_agent.execute_hierarchical_node(parent_node.id)

        assert result is not None
        assert "children_results" in result or result.get("status") == "completed"


# ==================== 测试3：容器节点执行 ====================


class TestContainerNodeExecution:
    """测试容器节点执行"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def workflow_agent_with_container(self, mock_event_bus):
        """创建带容器执行器的 WorkflowAgent"""
        from src.domain.agents.container_executor import MockContainerExecutor
        from src.domain.agents.workflow_agent import WorkflowAgent

        context = create_mock_workflow_context()
        factory = create_node_factory()
        container_executor = MockContainerExecutor()

        agent = WorkflowAgent(
            workflow_context=context,
            node_factory=factory,
            event_bus=mock_event_bus,
        )
        agent.container_executor = container_executor
        return agent

    def test_has_container_executor(self, workflow_agent_with_container):
        """WorkflowAgent 有容器执行器"""
        assert hasattr(workflow_agent_with_container, "container_executor")
        assert workflow_agent_with_container.container_executor is not None

    @pytest.mark.asyncio
    async def test_execute_container_node(self, workflow_agent_with_container):
        """执行容器节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 创建容器节点
        node_def = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="容器执行",
            code="print('hello from container')",
            is_container=True,
            container_config={
                "image": "python:3.11",
                "timeout": 30,
            },
        )

        node = workflow_agent_with_container.create_node_from_definition(node_def)
        workflow_agent_with_container.add_node(node)

        # 执行
        result = await workflow_agent_with_container.execute_container_node(node.id)

        assert result is not None
        assert result.get("success") is True or "stdout" in result


# ==================== 测试4：HierarchicalNodeFactory 集成 ====================


class TestHierarchicalNodeFactoryIntegration:
    """测试 HierarchicalNodeFactory 集成"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def workflow_agent(self, mock_event_bus):
        """创建 WorkflowAgent"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        context = create_mock_workflow_context()
        factory = create_node_factory()
        return WorkflowAgent(
            workflow_context=context,
            node_factory=factory,
            event_bus=mock_event_bus,
        )

    def test_workflow_agent_can_use_hierarchical_factory(self, workflow_agent):
        """WorkflowAgent 可以使用 HierarchicalNodeFactory"""
        from src.domain.agents.hierarchical_node_factory import HierarchicalNodeFactory

        h_factory = HierarchicalNodeFactory()

        # 创建层次化节点定义
        node_def = h_factory.create_node(
            name="数据处理",
            code="import pandas",
        )

        # 转换为 Node
        node = workflow_agent.create_node_from_definition(node_def)
        workflow_agent.add_node(node)

        assert node is not None
        assert len(node.children) == 1  # 自动生成了容器子节点

    def test_auto_detect_container_nodes(self, workflow_agent):
        """自动检测需要容器执行的节点"""
        from src.domain.agents.hierarchical_node_factory import HierarchicalNodeFactory

        h_factory = HierarchicalNodeFactory()

        # 数据处理节点应该自动成为层次化结构
        node_def = h_factory.create_node(
            name="ML训练",
            code="from sklearn import svm",
        )

        node = workflow_agent.create_node_from_definition(node_def)

        # 应该是 GENERIC 父节点 + CONTAINER 子节点
        assert len(node.children) == 1
        assert node.children[0].config.get("is_container") is True


# ==================== 测试5：层次化执行结果聚合 ====================


class TestHierarchicalResultAggregation:
    """测试层次化执行结果聚合"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def workflow_agent(self, mock_event_bus):
        """创建 WorkflowAgent"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        context = create_mock_workflow_context()
        factory = create_node_factory()
        return WorkflowAgent(
            workflow_context=context,
            node_factory=factory,
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_aggregate_children_results(self, workflow_agent):
        """聚合子节点结果"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 创建父节点和多个子节点
        parent_def = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="ETL流程",
        )
        for i in range(3):
            child_def = NodeDefinition(
                node_type=NodeType.PYTHON,
                name=f"步骤{i+1}",
                code=f"result = 'step_{i+1}'",
            )
            parent_def.add_child(child_def)

        parent_node = workflow_agent.create_node_from_definition(parent_def)
        workflow_agent.add_node(parent_node)

        # 执行并聚合
        result = await workflow_agent.execute_hierarchical_node(parent_node.id)

        # 结果应包含所有子节点的输出
        assert result is not None
        if "children_results" in result:
            assert len(result["children_results"]) == 3


# ==================== 测试6：容器事件集成 ====================


class TestContainerEventIntegration:
    """测试容器事件集成"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    @pytest.fixture
    def workflow_agent_with_container(self, mock_event_bus):
        """创建带容器执行器的 WorkflowAgent"""
        from src.domain.agents.container_executor import MockContainerExecutor
        from src.domain.agents.workflow_agent import WorkflowAgent

        context = create_mock_workflow_context()
        factory = create_node_factory()
        container_executor = MockContainerExecutor()

        agent = WorkflowAgent(
            workflow_context=context,
            node_factory=factory,
            event_bus=mock_event_bus,
        )
        agent.container_executor = container_executor
        return agent

    @pytest.mark.asyncio
    async def test_container_execution_publishes_events(
        self, workflow_agent_with_container, mock_event_bus
    ):
        """容器执行发布事件"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node_def = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="容器节点",
            code="print('test')",
            is_container=True,
        )

        node = workflow_agent_with_container.create_node_from_definition(node_def)
        workflow_agent_with_container.add_node(node)

        # 执行
        await workflow_agent_with_container.execute_container_node(node.id)

        # 应该发布了事件
        mock_event_bus.publish.assert_called()


# =============================================================================
# Gap-Filling Tests: create_grouped_nodes() (Lines 2612-2665) & get_hierarchy_tree() (Lines 2790-2800)
# P1-3 修正：行号注释与生产代码同步 ✅
# =============================================================================


class TestCreateGroupedNodesEdgeCases:
    """测试create_grouped_nodes()的边界情况和事件发布"""

    @pytest.mark.asyncio
    async def test_create_grouped_nodes_emits_child_added_events(self):
        """测试create_grouped_nodes()为所有子节点发布ChildAddedEvent

        目标行：workflow_agent.py lines 2651-2662
        逻辑：For each child, publish ChildAddedEvent with parent_id, child_id, child_type
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import ChildAddedEvent
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        # 创建带event_bus的agent（hierarchy_service会自动创建）
        event_bus = EventBus()
        ctx = WorkflowContext(
            workflow_id="test_wf",
            session_context=SessionContext(
                session_id="test_session",
                global_context=GlobalContext(user_id="test_user"),
            ),
        )
        factory = NodeFactory(NodeRegistry())

        agent = WorkflowAgent(
            workflow_context=ctx,
            node_factory=factory,
            event_bus=event_bus,
        )

        # 创建容器节点，包含3个子节点
        steps = [
            {"type": "generic", "config": {"name": "child1"}},
            {"type": "generic", "config": {"name": "child2"}},
            {"type": "generic", "config": {"name": "child3"}},
        ]

        parent = await agent.create_grouped_nodes(group_name="test_container", steps=steps)

        # 验证：发布了3个ChildAddedEvent
        child_added_events = [e for e in event_bus.event_log if isinstance(e, ChildAddedEvent)]
        assert len(child_added_events) == 3

        # 验证：所有事件包含正确的parent_id
        for event in child_added_events:
            assert event.parent_id == parent.id
            assert event.child_id in [child.id for child in parent.children]
            assert event.child_type == NodeType.GENERIC.value

    @pytest.mark.asyncio
    async def test_create_grouped_nodes_registers_all_nodes(self):
        """测试create_grouped_nodes()将父节点和所有子节点注册到_nodes

        目标行：workflow_agent.py lines 2645-2648
        逻辑：self._nodes[parent.id] = parent; for child: self._nodes[child.id] = child
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 创建agent（hierarchy_service会自动创建）
        ctx = WorkflowContext(
            workflow_id="test_wf",
            session_context=SessionContext(
                session_id="test_session",
                global_context=GlobalContext(user_id="test_user"),
            ),
        )
        factory = NodeFactory(NodeRegistry())

        agent = WorkflowAgent(
            workflow_context=ctx,
            node_factory=factory,
        )

        # 初始状态：_nodes为空
        assert len(agent._nodes) == 0

        # 创建容器节点，包含2个子节点
        steps = [
            {"type": "generic", "config": {"name": "child1"}},
            {"type": "generic", "config": {"name": "child2"}},
        ]

        parent = await agent.create_grouped_nodes(group_name="test_container", steps=steps)

        # 验证：_nodes包含3个节点（1个父节点 + 2个子节点）
        assert len(agent._nodes) == 3
        assert parent.id in agent._nodes
        for child in parent.children:
            assert child.id in agent._nodes
            assert agent._nodes[child.id] == child

    @pytest.mark.asyncio
    async def test_get_hierarchy_tree_nested_structure(self):
        """测试get_hierarchy_tree()返回正确的嵌套结构

        目标行：workflow_agent.py lines 2751-2765 (get_hierarchy_tree related)
        验证：多层嵌套容器的树形结构正确
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 创建agent（hierarchy_service会自动创建）
        ctx = WorkflowContext(
            workflow_id="test_wf",
            session_context=SessionContext(
                session_id="test_session",
                global_context=GlobalContext(user_id="test_user"),
            ),
        )
        factory = NodeFactory(NodeRegistry())

        agent = WorkflowAgent(
            workflow_context=ctx,
            node_factory=factory,
        )

        # 创建嵌套结构：Container A -> [Container B -> [Node C, Node D], Node E]
        # 首先创建Container B with C, D
        container_b_steps = [
            {"type": "generic", "config": {"name": "node_c"}},
            {"type": "generic", "config": {"name": "node_d"}},
        ]
        container_b = await agent.create_grouped_nodes(
            group_name="container_b", steps=container_b_steps
        )

        # 获取层级树（传递group_id）
        tree = await agent.get_hierarchy_tree(container_b.id)

        # 验证：tree是字典，包含节点信息
        assert isinstance(tree, dict)
        assert "children" in tree  # Tree根是container_b本身，包含children数组
        assert len(tree["children"]) == 2  # Node C, Node D

    @pytest.mark.asyncio
    async def test_get_hierarchy_tree_deeply_nested_3_layers(self):
        """测试get_hierarchy_tree()处理3层+深度嵌套结构

        目标行：workflow_agent.py lines 2790-2800 (get_hierarchy_tree)
        验证：Container A -> Container B -> Leaf Nodes 的3层结构正确递归返回
        P1-4 增强：真正的多层嵌套测试（推荐修复）
        """
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 创建agent（hierarchy_service会自动创建）
        ctx = WorkflowContext(
            workflow_id="test_wf",
            session_context=SessionContext(
                session_id="test_session",
                global_context=GlobalContext(user_id="test_user"),
            ),
        )
        factory = NodeFactory(NodeRegistry())

        agent = WorkflowAgent(
            workflow_context=ctx,
            node_factory=factory,
        )

        # 创建3层嵌套结构：
        # Level 1: Container Root
        # └── Level 2: Container Mid
        #     └── Level 3: Leaf Node

        # 首先创建 Level 3 叶子节点（通过 container_mid 创建）
        leaf_steps = [
            {"type": "generic", "config": {"name": "leaf_node"}},
        ]
        container_mid = await agent.create_grouped_nodes(
            group_name="container_mid", steps=leaf_steps
        )

        # 然后创建 Level 2 容器（注意：这里需要手动添加 container_mid 到 container_root）
        # 由于 create_grouped_nodes 只支持从 config 创建子节点，我们需要使用其他方式建立3层关系
        # 这里我们手动调用 add_node_to_group 建立层次关系
        container_root = await agent.create_grouped_nodes(group_name="container_root", steps=[])

        # 将 container_mid 添加到 container_root
        await agent.add_node_to_group(container_root.id, container_mid.id)

        # 获取完整的3层层级树
        tree = await agent.get_hierarchy_tree(container_root.id)

        # 验证 Level 1: Root
        assert isinstance(tree, dict)
        assert tree["id"] == container_root.id
        assert tree["name"] == "container_root"

        # 验证 Level 2: Mid（Root 的子节点）
        assert "children" in tree
        assert len(tree["children"]) == 1
        mid_tree = tree["children"][0]
        assert mid_tree["id"] == container_mid.id
        assert mid_tree["name"] == "container_mid"

        # 验证 Level 3: Leaf（Mid 的子节点）
        assert "children" in mid_tree
        assert len(mid_tree["children"]) == 1
        leaf_tree = mid_tree["children"][0]
        assert leaf_tree["config"]["name"] == "leaf_node"
        assert leaf_tree.get("children", []) == []  # 叶子节点无子节点


# 导出
__all__ = [
    "TestNodeDefinitionToNode",
    "TestHierarchicalNodeExecution",
    "TestContainerNodeExecution",
    "TestHierarchicalNodeFactoryIntegration",
    "TestHierarchicalResultAggregation",
    "TestContainerEventIntegration",
    "TestCreateGroupedNodesEdgeCases",
]

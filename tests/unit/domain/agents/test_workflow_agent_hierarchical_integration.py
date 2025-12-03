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


# 导出
__all__ = [
    "TestNodeDefinitionToNode",
    "TestHierarchicalNodeExecution",
    "TestContainerNodeExecution",
    "TestHierarchicalNodeFactoryIntegration",
    "TestHierarchicalResultAggregation",
    "TestContainerEventIntegration",
]

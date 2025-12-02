"""层级节点真实场景端到端测试 - Phase 9.5

TDD RED阶段：测试真实业务场景

业务场景：
- 用户说"帮我创建一个数据分析流程"
- ConversationAgent 规划出多个步骤
- WorkflowAgent 创建层级节点
- 用户可以折叠/展开查看细节
- 工作流可以执行
"""

import pytest


def create_workflow_agent_for_test(event_bus=None):
    """创建测试用的 WorkflowAgent"""
    from src.domain.agents.workflow_agent import WorkflowAgent
    from src.domain.services.context_manager import (
        GlobalContext,
        SessionContext,
        WorkflowContext,
    )
    from src.domain.services.node_registry import NodeFactory, NodeRegistry

    registry = NodeRegistry()
    factory = NodeFactory(registry)

    global_ctx = GlobalContext(user_id="test_user")
    session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)
    context = WorkflowContext(workflow_id="test_wf", session_context=session_ctx)

    return WorkflowAgent(
        workflow_context=context,
        node_factory=factory,
        event_bus=event_bus,
    )


class TestDataAnalysisScenario:
    """数据分析流程场景测试"""

    @pytest.mark.asyncio
    async def test_create_data_analysis_workflow(self):
        """用户说"帮我创建一个数据分析流程"的完整流程"""
        agent = create_workflow_agent_for_test()

        # 模拟 ConversationAgent 生成的规划
        plan = {
            "goal": "数据分析",
            "groups": [
                {
                    "name": "1. 数据加载",
                    "steps": [
                        {
                            "type": "code",
                            "config": {"code": "import pandas as pd", "description": "导入库"},
                        },
                        {
                            "type": "code",
                            "config": {
                                "code": "df = pd.read_csv('data.csv')",
                                "description": "读取数据",
                            },
                        },
                    ],
                },
                {
                    "name": "2. 数据清洗",
                    "steps": [
                        {
                            "type": "code",
                            "config": {"code": "df = df.dropna()", "description": "删除空值"},
                        },
                        {
                            "type": "code",
                            "config": {
                                "code": "df = df.drop_duplicates()",
                                "description": "删除重复",
                            },
                        },
                    ],
                },
                {
                    "name": "3. 数据分析",
                    "steps": [
                        {
                            "type": "code",
                            "config": {"code": "stats = df.describe()", "description": "统计分析"},
                        },
                        {
                            "type": "code",
                            "config": {"code": "print(stats)", "description": "输出结果"},
                        },
                    ],
                },
            ],
        }

        # 创建层级结构
        groups = await agent.create_hierarchy_from_plan(plan)

        # 验证创建了 3 个分组
        assert len(groups) == 3
        assert groups[0].config.get("name") == "1. 数据加载"
        assert groups[1].config.get("name") == "2. 数据清洗"
        assert groups[2].config.get("name") == "3. 数据分析"

        # 验证每个分组有 2 个步骤
        assert len(groups[0].children) == 2
        assert len(groups[1].children) == 2
        assert len(groups[2].children) == 2

    @pytest.mark.asyncio
    async def test_collapse_and_expand_groups(self):
        """测试折叠和展开分组"""
        agent = create_workflow_agent_for_test()

        # 创建一个分组
        group = await agent.create_grouped_nodes(
            group_name="测试分组",
            steps=[
                {"type": "code", "config": {"code": "step1"}},
                {"type": "code", "config": {"code": "step2"}},
            ],
        )

        # 默认折叠
        assert group.collapsed is True
        visible = await agent.get_group_visible_steps(group.id)
        assert len(visible) == 0

        # 展开
        await agent.toggle_group_collapse(group.id)
        assert group.collapsed is False
        visible = await agent.get_group_visible_steps(group.id)
        assert len(visible) == 2

        # 再次折叠
        await agent.toggle_group_collapse(group.id)
        assert group.collapsed is True

    @pytest.mark.asyncio
    async def test_add_step_to_existing_group(self):
        """测试向已有分组添加步骤"""
        agent = create_workflow_agent_for_test()

        # 创建分组
        group = await agent.create_grouped_nodes(
            group_name="可扩展分组",
            steps=[{"type": "code", "config": {"code": "initial"}}],
        )

        # 添加新步骤
        new_step = await agent.add_step_to_group(
            group_id=group.id,
            step={"type": "code", "config": {"code": "added_step"}},
        )

        # 验证
        assert len(group.children) == 2
        assert new_step.config.get("code") == "added_step"

    @pytest.mark.asyncio
    async def test_reorder_steps_in_group(self):
        """测试重排序步骤"""
        agent = create_workflow_agent_for_test()

        group = await agent.create_grouped_nodes(
            group_name="排序测试",
            steps=[
                {"type": "code", "config": {"code": "step_a"}},
                {"type": "code", "config": {"code": "step_b"}},
                {"type": "code", "config": {"code": "step_c"}},
            ],
        )

        # 获取步骤 ID
        step_ids = [c.id for c in group.children]

        # 反转顺序
        await agent.reorder_steps_in_group(group.id, list(reversed(step_ids)))

        # 验证顺序
        assert group.children[0].config.get("code") == "step_c"
        assert group.children[1].config.get("code") == "step_b"
        assert group.children[2].config.get("code") == "step_a"


class TestNestedHierarchyScenario:
    """嵌套层级场景测试"""

    @pytest.mark.asyncio
    async def test_create_nested_workflow(self):
        """测试创建嵌套工作流"""
        agent = create_workflow_agent_for_test()

        plan = {
            "goal": "复杂 ETL 流程",
            "groups": [
                {
                    "name": "ETL 主流程",
                    "steps": [
                        {"type": "code", "config": {"code": "init()"}},
                    ],
                    "subgroups": [
                        {
                            "name": "数据抽取 (Extract)",
                            "steps": [
                                {"type": "code", "config": {"code": "extract_from_db()"}},
                                {"type": "code", "config": {"code": "extract_from_api()"}},
                            ],
                        },
                        {
                            "name": "数据转换 (Transform)",
                            "steps": [
                                {"type": "code", "config": {"code": "clean_data()"}},
                                {"type": "code", "config": {"code": "transform_data()"}},
                            ],
                        },
                    ],
                },
            ],
        }

        groups = await agent.create_hierarchy_from_plan(plan)

        # 验证主分组
        assert len(groups) == 1
        main_group = groups[0]
        assert main_group.config.get("name") == "ETL 主流程"

        # 找到子分组
        from src.domain.services.node_registry import NodeType

        subgroups = [c for c in main_group.children if c.type == NodeType.GENERIC]
        assert len(subgroups) == 2

    @pytest.mark.asyncio
    async def test_expand_all_nested_groups(self):
        """测试展开所有嵌套分组"""
        agent = create_workflow_agent_for_test()

        # 创建嵌套结构
        from src.domain.services.node_registry import Node, NodeType

        root = Node(id="root", type=NodeType.GENERIC, config={"name": "根"})
        child = Node(id="child", type=NodeType.GENERIC, config={"name": "子"})
        grandchild = Node(id="grandchild", type=NodeType.GENERIC, config={"name": "孙"})

        root.add_child(child)
        child.add_child(grandchild)

        # 注册到层级服务
        agent.hierarchy_service.register_node(root)
        agent.hierarchy_service.register_node(child)
        agent.hierarchy_service.register_node(grandchild)

        # 默认都是折叠的
        assert root.collapsed is True
        assert child.collapsed is True
        assert grandchild.collapsed is True

        # 展开所有
        agent.hierarchy_service.expand_all("root")

        # 验证全部展开
        assert root.collapsed is False
        assert child.collapsed is False
        assert grandchild.collapsed is False


class TestHierarchySerialization:
    """层级序列化场景测试"""

    @pytest.mark.asyncio
    async def test_serialize_and_deserialize_workflow(self):
        """测试工作流序列化和反序列化"""
        from src.domain.services.node_registry import Node

        agent = create_workflow_agent_for_test()

        # 创建工作流
        group = await agent.create_grouped_nodes(
            group_name="可序列化分组",
            steps=[
                {"type": "code", "config": {"code": "step1"}},
                {"type": "code", "config": {"code": "step2"}},
            ],
        )

        # 展开分组
        await agent.toggle_group_collapse(group.id)

        # 序列化
        tree = await agent.get_hierarchy_tree(group.id)

        # 反序列化
        restored = Node.from_dict(tree)

        # 验证
        assert restored.id == group.id
        assert restored.collapsed is False
        assert len(restored.children) == 2

    @pytest.mark.asyncio
    async def test_serialize_preserves_all_data(self):
        """测试序列化保留所有数据"""
        from src.domain.services.node_registry import Node, NodeType

        # 创建带完整数据的节点
        parent = Node(
            id="parent",
            type=NodeType.GENERIC,
            config={
                "name": "测试分组",
                "description": "这是一个测试分组",
                "metadata": {"created_by": "test"},
            },
        )
        child = Node(
            id="child",
            type=NodeType.CODE,
            config={
                "code": "print('hello')",
                "language": "python",
            },
        )
        parent.add_child(child)

        # 序列化
        data = parent.to_dict()

        # 反序列化
        restored = Node.from_dict(data)

        # 验证
        assert restored.config.get("description") == "这是一个测试分组"
        assert restored.config.get("metadata") == {"created_by": "test"}
        assert restored.children[0].config.get("language") == "python"


class TestEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_empty_group(self):
        """测试空分组"""
        agent = create_workflow_agent_for_test()

        group = await agent.create_grouped_nodes(
            group_name="空分组",
            steps=[],
        )

        assert len(group.children) == 0
        assert group.collapsed is True

    @pytest.mark.asyncio
    async def test_delete_group_with_children(self):
        """测试删除包含子节点的分组"""
        agent = create_workflow_agent_for_test()

        group = await agent.create_grouped_nodes(
            group_name="将被删除",
            steps=[
                {"type": "code", "config": {"code": "step1"}},
                {"type": "code", "config": {"code": "step2"}},
            ],
        )

        group_id = group.id
        child_ids = [c.id for c in group.children]

        # 删除分组
        await agent.remove_group(group_id)

        # 验证分组和子节点都被删除
        assert await agent.get_group_by_id(group_id) is None
        for child_id in child_ids:
            assert agent.hierarchy_service.get_node(child_id) is None

    @pytest.mark.asyncio
    async def test_move_step_between_groups(self):
        """测试在分组间移动步骤"""
        agent = create_workflow_agent_for_test()

        # 创建两个分组
        group1 = await agent.create_grouped_nodes(
            group_name="源分组",
            steps=[{"type": "code", "config": {"code": "movable"}}],
        )
        group2 = await agent.create_grouped_nodes(
            group_name="目标分组",
            steps=[],
        )

        # 获取步骤 ID
        step_id = group1.children[0].id

        # 移动步骤
        await agent.move_step_to_group(step_id, group2.id)

        # 验证
        assert len(group1.children) == 0
        assert len(group2.children) == 1
        assert group2.children[0].id == step_id


class TestEventDrivenBehavior:
    """事件驱动行为测试"""

    @pytest.mark.asyncio
    async def test_events_on_group_creation(self):
        """测试分组创建时发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import ChildAddedEvent

        event_bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(ChildAddedEvent, handler)

        agent = create_workflow_agent_for_test(event_bus=event_bus)

        await agent.create_grouped_nodes(
            group_name="事件测试",
            steps=[
                {"type": "code", "config": {"code": "step1"}},
                {"type": "code", "config": {"code": "step2"}},
            ],
        )

        # 应该收到 2 个 ChildAddedEvent（每个子节点一个）
        assert len(received_events) == 2

    @pytest.mark.asyncio
    async def test_events_on_collapse_expand(self):
        """测试折叠/展开时发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import (
            NodeCollapsedEvent,
            NodeExpandedEvent,
        )

        event_bus = EventBus()
        expanded_events = []
        collapsed_events = []

        async def expanded_handler(event):
            expanded_events.append(event)

        async def collapsed_handler(event):
            collapsed_events.append(event)

        event_bus.subscribe(NodeExpandedEvent, expanded_handler)
        event_bus.subscribe(NodeCollapsedEvent, collapsed_handler)

        agent = create_workflow_agent_for_test(event_bus=event_bus)

        group = await agent.create_grouped_nodes(group_name="事件测试", steps=[])

        # 展开
        await agent.toggle_group_collapse(group.id)
        assert len(expanded_events) == 1

        # 折叠
        await agent.toggle_group_collapse(group.id)
        assert len(collapsed_events) == 1

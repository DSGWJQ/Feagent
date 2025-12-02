"""WorkflowAgent 层级节点集成测试 - Phase 9.3

TDD RED阶段：测试 WorkflowAgent 与 NodeHierarchyService 的集成

业务场景：
- ConversationAgent 规划出多步骤任务
- WorkflowAgent 创建父节点包含这些步骤
- 用户可以折叠/展开查看细节
"""

import pytest


def create_workflow_agent(event_bus=None):
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

    # 创建上下文层次结构
    global_ctx = GlobalContext(user_id="test_user")
    session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)
    context = WorkflowContext(workflow_id="test_wf", session_context=session_ctx)

    return WorkflowAgent(
        workflow_context=context,
        node_factory=factory,
        event_bus=event_bus,
    )


class TestWorkflowAgentHierarchyIntegration:
    """WorkflowAgent 层级集成测试"""

    def test_workflow_agent_has_hierarchy_service(self):
        """WorkflowAgent 应有层级服务"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService

        agent = create_workflow_agent()

        assert hasattr(agent, "hierarchy_service")
        assert isinstance(agent.hierarchy_service, NodeHierarchyService)

    @pytest.mark.asyncio
    async def test_create_grouped_nodes(self):
        """应能创建分组节点（父节点包含子节点）"""
        from src.domain.services.node_registry import NodeType

        agent = create_workflow_agent()

        # 创建分组节点
        parent = await agent.create_grouped_nodes(
            group_name="数据分析流程",
            steps=[
                {"type": "code", "config": {"code": "import pandas as pd"}},
                {"type": "code", "config": {"code": "df = pd.read_csv('data.csv')"}},
                {"type": "code", "config": {"code": "print(df.describe())"}},
            ],
        )

        assert parent.type == NodeType.GENERIC
        assert parent.config.get("name") == "数据分析流程"
        assert len(parent.children) == 3

    @pytest.mark.asyncio
    async def test_add_step_to_group(self):
        """应能向已有分组添加步骤"""

        agent = create_workflow_agent()

        # 先创建分组
        parent = await agent.create_grouped_nodes(
            group_name="流程",
            steps=[{"type": "code", "config": {"code": "step1"}}],
        )

        # 添加新步骤
        new_step = await agent.add_step_to_group(
            group_id=parent.id,
            step={"type": "code", "config": {"code": "step2"}},
        )

        assert len(parent.children) == 2
        assert new_step.parent_id == parent.id

    @pytest.mark.asyncio
    async def test_toggle_group_collapse(self):
        """应能切换分组的折叠状态"""
        agent = create_workflow_agent()

        parent = await agent.create_grouped_nodes(
            group_name="流程",
            steps=[{"type": "code", "config": {"code": "x"}}],
        )

        # 默认折叠
        assert parent.collapsed is True

        # 展开
        await agent.toggle_group_collapse(parent.id)
        assert parent.collapsed is False

        # 再次折叠
        await agent.toggle_group_collapse(parent.id)
        assert parent.collapsed is True

    @pytest.mark.asyncio
    async def test_get_group_visible_steps(self):
        """应能获取分组的可见步骤"""
        agent = create_workflow_agent()

        parent = await agent.create_grouped_nodes(
            group_name="流程",
            steps=[
                {"type": "code", "config": {"code": "x"}},
                {"type": "code", "config": {"code": "y"}},
            ],
        )

        # 折叠时无可见步骤
        visible = await agent.get_group_visible_steps(parent.id)
        assert len(visible) == 0

        # 展开后有可见步骤
        parent.expand()
        visible = await agent.get_group_visible_steps(parent.id)
        assert len(visible) == 2


class TestWorkflowAgentHierarchyFromPlan:
    """从规划创建层级结构测试"""

    @pytest.mark.asyncio
    async def test_create_hierarchy_from_plan(self):
        """应能从规划创建层级结构"""
        from src.domain.services.node_registry import NodeType

        agent = create_workflow_agent()

        # 模拟 ConversationAgent 的规划
        plan = {
            "goal": "数据分析",
            "groups": [
                {
                    "name": "数据加载",
                    "steps": [
                        {"type": "code", "config": {"code": "import pandas"}},
                        {"type": "code", "config": {"code": "df = pd.read_csv()"}},
                    ],
                },
                {
                    "name": "数据处理",
                    "steps": [
                        {"type": "code", "config": {"code": "df.dropna()"}},
                        {"type": "code", "config": {"code": "df.fillna(0)"}},
                    ],
                },
            ],
        }

        result = await agent.create_hierarchy_from_plan(plan)

        assert len(result) == 2
        assert result[0].type == NodeType.GENERIC
        assert result[0].config.get("name") == "数据加载"
        assert len(result[0].children) == 2
        assert result[1].config.get("name") == "数据处理"
        assert len(result[1].children) == 2

    @pytest.mark.asyncio
    async def test_create_nested_hierarchy_from_plan(self):
        """应能从规划创建嵌套层级"""
        from src.domain.services.node_registry import NodeType

        agent = create_workflow_agent()

        plan = {
            "goal": "复杂分析",
            "groups": [
                {
                    "name": "主流程",
                    "steps": [
                        {"type": "code", "config": {"code": "init"}},
                    ],
                    "subgroups": [
                        {
                            "name": "子流程A",
                            "steps": [
                                {"type": "code", "config": {"code": "sub_a"}},
                            ],
                        },
                    ],
                },
            ],
        }

        result = await agent.create_hierarchy_from_plan(plan)

        assert len(result) == 1
        main_group = result[0]
        assert main_group.config.get("name") == "主流程"

        # 找到子流程（它应该是 GENERIC 类型的子节点）
        subgroup = None
        for child in main_group.children:
            if child.type == NodeType.GENERIC:
                subgroup = child
                break

        assert subgroup is not None
        assert subgroup.config.get("name") == "子流程A"
        assert len(subgroup.children) == 1


class TestWorkflowAgentHierarchyQueries:
    """层级查询测试"""

    @pytest.mark.asyncio
    async def test_get_all_groups(self):
        """应能获取所有分组"""
        agent = create_workflow_agent()

        await agent.create_grouped_nodes(group_name="组1", steps=[])
        await agent.create_grouped_nodes(group_name="组2", steps=[])

        groups = await agent.get_all_groups()

        assert len(groups) == 2

    @pytest.mark.asyncio
    async def test_get_group_by_id(self):
        """应能通过ID获取分组"""
        agent = create_workflow_agent()

        parent = await agent.create_grouped_nodes(group_name="测试组", steps=[])

        group = await agent.get_group_by_id(parent.id)

        assert group is not None
        assert group.config.get("name") == "测试组"

    @pytest.mark.asyncio
    async def test_get_hierarchy_tree(self):
        """应能获取完整的层级树"""
        agent = create_workflow_agent()

        parent = await agent.create_grouped_nodes(
            group_name="主流程",
            steps=[
                {"type": "code", "config": {"code": "x"}},
            ],
        )

        tree = await agent.get_hierarchy_tree(parent.id)

        assert tree["id"] == parent.id
        assert tree["config"]["name"] == "主流程"
        assert len(tree["children"]) == 1


class TestWorkflowAgentHierarchyModification:
    """层级修改测试"""

    @pytest.mark.asyncio
    async def test_remove_step_from_group(self):
        """应能从分组移除步骤"""
        agent = create_workflow_agent()

        parent = await agent.create_grouped_nodes(
            group_name="流程",
            steps=[
                {"type": "code", "config": {"code": "x"}},
                {"type": "code", "config": {"code": "y"}},
            ],
        )

        child_id = parent.children[0].id
        await agent.remove_step_from_group(parent.id, child_id)

        assert len(parent.children) == 1

    @pytest.mark.asyncio
    async def test_move_step_between_groups(self):
        """应能在分组间移动步骤"""
        agent = create_workflow_agent()

        group1 = await agent.create_grouped_nodes(
            group_name="组1",
            steps=[{"type": "code", "config": {"code": "x"}}],
        )
        group2 = await agent.create_grouped_nodes(
            group_name="组2",
            steps=[],
        )

        step_id = group1.children[0].id
        await agent.move_step_to_group(step_id, group2.id)

        assert len(group1.children) == 0
        assert len(group2.children) == 1

    @pytest.mark.asyncio
    async def test_reorder_steps_in_group(self):
        """应能重排序分组内的步骤"""
        agent = create_workflow_agent()

        parent = await agent.create_grouped_nodes(
            group_name="流程",
            steps=[
                {"type": "code", "config": {"code": "a"}},
                {"type": "code", "config": {"code": "b"}},
                {"type": "code", "config": {"code": "c"}},
            ],
        )

        step_ids = [c.id for c in parent.children]
        # 反转顺序
        await agent.reorder_steps_in_group(parent.id, list(reversed(step_ids)))

        assert parent.children[0].config.get("code") == "c"
        assert parent.children[1].config.get("code") == "b"
        assert parent.children[2].config.get("code") == "a"

    @pytest.mark.asyncio
    async def test_remove_group_with_steps(self):
        """删除分组应同时删除所有步骤"""
        agent = create_workflow_agent()

        parent = await agent.create_grouped_nodes(
            group_name="流程",
            steps=[
                {"type": "code", "config": {"code": "x"}},
                {"type": "code", "config": {"code": "y"}},
            ],
        )

        parent_id = parent.id
        step_ids = [c.id for c in parent.children]

        await agent.remove_group(parent_id)

        # 验证分组和步骤都被删除
        assert await agent.get_group_by_id(parent_id) is None
        for step_id in step_ids:
            assert agent.hierarchy_service.get_node(step_id) is None


class TestWorkflowAgentHierarchyEvents:
    """层级事件测试"""

    @pytest.mark.asyncio
    async def test_emit_event_on_group_created(self):
        """创建分组时应发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import ChildAddedEvent

        event_bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(ChildAddedEvent, handler)

        agent = create_workflow_agent(event_bus=event_bus)

        await agent.create_grouped_nodes(
            group_name="流程",
            steps=[{"type": "code", "config": {"code": "x"}}],
        )

        # 应收到子节点添加事件
        assert len(received_events) >= 1

    @pytest.mark.asyncio
    async def test_emit_event_on_collapse_toggle(self):
        """切换折叠时应发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import (
            NodeCollapsedEvent,
            NodeExpandedEvent,
        )

        event_bus = EventBus()
        received_events = []

        async def expanded_handler(event):
            received_events.append(("expanded", event))

        async def collapsed_handler(event):
            received_events.append(("collapsed", event))

        event_bus.subscribe(NodeExpandedEvent, expanded_handler)
        event_bus.subscribe(NodeCollapsedEvent, collapsed_handler)

        agent = create_workflow_agent(event_bus=event_bus)

        parent = await agent.create_grouped_nodes(group_name="流程", steps=[])

        # 展开
        await agent.toggle_group_collapse(parent.id)
        assert any(e[0] == "expanded" for e in received_events)

        # 折叠
        await agent.toggle_group_collapse(parent.id)
        assert any(e[0] == "collapsed" for e in received_events)

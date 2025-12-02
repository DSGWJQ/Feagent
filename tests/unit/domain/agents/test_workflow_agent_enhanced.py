"""WorkflowAgent 增强测试 - Phase 10

TDD RED阶段：测试 WorkflowAgent 的完整层级支持和自定义节点功能

问题分析：
1. create_node 只创建单个节点，不处理父子关系和折叠状态
2. _nodes 结构是简单 dict，没有维护树状层级
3. 缺少自定义节点功能，只能创建预定义节点类型

业务场景：
- 用户说"在数据加载步骤下添加一个读取 CSV 的子步骤"
- create_node 应该能指定父节点，自动建立层级关系
- 用户说"创建一个自定义的 AI 摘要节点"
- 应该能运行时定义新的节点类型
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


# ============ Phase 10.1: create_node 增强 ============


class TestCreateNodeWithParent:
    """create_node 支持父节点测试"""

    def test_create_node_with_parent_id(self):
        """create_node 应支持指定父节点ID"""

        agent = create_workflow_agent_for_test()

        # 先创建父节点
        parent = agent.create_node(
            {
                "node_type": "generic",
                "config": {"name": "数据加载"},
            }
        )
        agent.add_node(parent)

        # 创建子节点，指定父节点
        child = agent.create_node(
            {
                "node_type": "code",
                "config": {"code": "pd.read_csv()"},
                "parent_id": parent.id,  # 新增：指定父节点
            }
        )
        agent.add_node(child)

        # 验证父子关系
        assert child.parent_id == parent.id
        assert child in parent.children

    def test_create_node_sets_collapsed_state(self):
        """create_node 应支持设置折叠状态"""
        agent = create_workflow_agent_for_test()

        # 创建节点并设置 collapsed
        node = agent.create_node(
            {
                "node_type": "generic",
                "config": {"name": "流程"},
                "collapsed": False,  # 新增：设置折叠状态
            }
        )

        assert node.collapsed is False

    def test_create_node_with_children_inline(self):
        """create_node 应支持内联创建子节点"""
        from src.domain.services.node_registry import NodeType

        agent = create_workflow_agent_for_test()

        # 一次性创建父节点和子节点
        node = agent.create_node(
            {
                "node_type": "generic",
                "config": {"name": "数据处理"},
                "children": [  # 新增：内联子节点
                    {"node_type": "code", "config": {"code": "step1"}},
                    {"node_type": "code", "config": {"code": "step2"}},
                ],
            }
        )

        assert node.type == NodeType.GENERIC
        assert len(node.children) == 2


class TestAddNodeWithHierarchy:
    """add_node 维护层级结构测试"""

    def test_add_node_registers_in_hierarchy(self):
        """add_node 应同时注册到层级服务"""
        agent = create_workflow_agent_for_test()

        node = agent.create_node(
            {
                "node_type": "generic",
                "config": {"name": "测试"},
            }
        )
        agent.add_node(node)

        # 应该在 _nodes 和 hierarchy_service 中都能找到
        assert agent.get_node(node.id) is not None
        assert agent.hierarchy_service.get_node(node.id) is not None

    def test_add_node_with_parent_updates_both(self):
        """add_node 带父节点时应更新两边的引用"""

        agent = create_workflow_agent_for_test()

        # 创建并添加父节点
        parent = agent.create_node(
            {
                "node_type": "generic",
                "config": {"name": "父"},
            }
        )
        agent.add_node(parent)

        # 创建并添加子节点
        child = agent.create_node(
            {
                "node_type": "code",
                "config": {"code": "x"},
                "parent_id": parent.id,
            }
        )
        agent.add_node(child)

        # 验证 _nodes 中两个节点都存在
        assert agent.get_node(parent.id) is not None
        assert agent.get_node(child.id) is not None

        # 验证层级关系
        assert child.parent_id == parent.id
        assert child in parent.children


class TestNodesTreeStructure:
    """_nodes 树状结构测试"""

    def test_get_root_nodes(self):
        """应能获取所有根节点（无父节点的节点）"""
        agent = create_workflow_agent_for_test()

        # 创建两个根节点
        root1 = agent.create_node({"node_type": "generic", "config": {"name": "根1"}})
        root2 = agent.create_node({"node_type": "code", "config": {"code": "x"}})
        agent.add_node(root1)
        agent.add_node(root2)

        # 在 root1 下创建子节点
        child = agent.create_node(
            {
                "node_type": "code",
                "config": {"code": "y"},
                "parent_id": root1.id,
            }
        )
        agent.add_node(child)

        # 获取根节点
        roots = agent.get_root_nodes()

        assert len(roots) == 2
        assert root1 in roots
        assert root2 in roots
        assert child not in roots

    def test_get_node_tree(self):
        """应能获取节点的完整树结构"""
        agent = create_workflow_agent_for_test()

        # 创建三层结构
        root = agent.create_node({"node_type": "generic", "config": {"name": "根"}})
        agent.add_node(root)

        child = agent.create_node(
            {
                "node_type": "generic",
                "config": {"name": "子"},
                "parent_id": root.id,
            }
        )
        agent.add_node(child)

        grandchild = agent.create_node(
            {
                "node_type": "code",
                "config": {"code": "x"},
                "parent_id": child.id,
            }
        )
        agent.add_node(grandchild)

        # 获取树结构
        tree = agent.get_node_tree(root.id)

        assert tree["id"] == root.id
        assert len(tree["children"]) == 1
        assert tree["children"][0]["id"] == child.id
        assert len(tree["children"][0]["children"]) == 1

    def test_flatten_nodes_with_hierarchy_info(self):
        """应能扁平化节点列表并保留层级信息"""
        agent = create_workflow_agent_for_test()

        root = agent.create_node({"node_type": "generic", "config": {"name": "根"}})
        agent.add_node(root)

        child = agent.create_node(
            {
                "node_type": "code",
                "config": {"code": "x"},
                "parent_id": root.id,
            }
        )
        agent.add_node(child)

        # 扁平化
        flat_nodes = agent.get_flat_nodes_with_hierarchy()

        assert len(flat_nodes) == 2
        # 每个节点应包含层级信息
        root_data = next(n for n in flat_nodes if n["id"] == root.id)
        child_data = next(n for n in flat_nodes if n["id"] == child.id)

        assert root_data["parent_id"] is None
        assert root_data["depth"] == 0
        assert child_data["parent_id"] == root.id
        assert child_data["depth"] == 1


# ============ Phase 10.2: 自定义节点功能 ============


class TestCustomNodeDefinition:
    """自定义节点定义测试"""

    def test_define_custom_node_type(self):
        """应能运行时定义自定义节点类型"""
        agent = create_workflow_agent_for_test()

        # 定义自定义节点类型
        agent.define_custom_node_type(
            type_name="ai_summarizer",
            schema={
                "input_text": {"type": "string", "required": True},
                "max_length": {"type": "integer", "default": 100},
            },
            executor_class=None,  # 可选的执行器
        )

        # 验证自定义类型已注册
        assert agent.has_node_type("ai_summarizer")

    def test_create_custom_node(self):
        """应能创建自定义类型的节点"""
        agent = create_workflow_agent_for_test()

        # 先定义
        agent.define_custom_node_type(
            type_name="data_validator",
            schema={
                "rules": {"type": "array", "required": True},
            },
        )

        # 再创建
        node = agent.create_node(
            {
                "node_type": "data_validator",
                "config": {"rules": ["not_null", "unique"]},
            }
        )

        assert node is not None
        assert node.config.get("rules") == ["not_null", "unique"]

    def test_custom_node_with_validation(self):
        """自定义节点应支持配置验证"""
        agent = create_workflow_agent_for_test()

        agent.define_custom_node_type(
            type_name="email_sender",
            schema={
                "to": {"type": "string", "required": True},
                "subject": {"type": "string", "required": True},
            },
        )

        # 缺少必填字段应报错
        with pytest.raises(ValueError, match="[Rr]equired|必填"):
            agent.create_node(
                {
                    "node_type": "email_sender",
                    "config": {"to": "test@example.com"},  # 缺少 subject
                }
            )


class TestCustomNodeExecution:
    """自定义节点执行测试"""

    @pytest.mark.asyncio
    async def test_custom_node_with_executor(self):
        """自定义节点应能指定执行器"""
        agent = create_workflow_agent_for_test()

        # 定义带执行器的自定义节点
        class MockExecutor:
            async def execute(self, config, inputs):
                return {"result": f"processed: {config.get('input')}"}

        agent.define_custom_node_type(
            type_name="mock_processor",
            schema={"input": {"type": "string"}},
            executor_class=MockExecutor,
        )

        # 创建并执行
        node = agent.create_node(
            {
                "node_type": "mock_processor",
                "config": {"input": "test_data"},
            }
        )
        agent.add_node(node)

        # 执行节点
        result = await agent.execute_node(node.id)

        assert result["result"] == "processed: test_data"


# ============ Phase 10.3: 决策与层级集成 ============


class TestDecisionWithHierarchy:
    """决策处理与层级集成测试"""

    @pytest.mark.asyncio
    async def test_handle_create_node_with_parent(self):
        """handle_decision 应支持创建带父节点的节点"""
        agent = create_workflow_agent_for_test()

        # 先创建父节点
        parent_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "父流程"},
            }
        )
        parent_id = parent_result["node_id"]

        # 创建子节点
        child_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "code",
                "config": {"code": "x=1"},
                "parent_id": parent_id,
            }
        )

        # 验证
        parent = agent.get_node(parent_id)
        child = agent.get_node(child_result["node_id"])

        assert child.parent_id == parent_id
        assert child in parent.children

    @pytest.mark.asyncio
    async def test_handle_toggle_collapse(self):
        """handle_decision 应支持折叠/展开决策"""
        agent = create_workflow_agent_for_test()

        # 创建节点
        result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "可折叠"},
            }
        )
        node_id = result["node_id"]

        # 默认折叠
        node = agent.get_node(node_id)
        assert node.collapsed is True

        # 展开
        await agent.handle_decision(
            {
                "decision_type": "toggle_collapse",
                "node_id": node_id,
            }
        )
        assert node.collapsed is False

    @pytest.mark.asyncio
    async def test_handle_move_node(self):
        """handle_decision 应支持移动节点"""
        agent = create_workflow_agent_for_test()

        # 创建两个父节点和一个子节点
        parent1_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "父1"},
            }
        )
        parent2_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "父2"},
            }
        )
        child_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "code",
                "config": {"code": "x"},
                "parent_id": parent1_result["node_id"],
            }
        )

        # 移动子节点到父2
        await agent.handle_decision(
            {
                "decision_type": "move_node",
                "node_id": child_result["node_id"],
                "new_parent_id": parent2_result["node_id"],
            }
        )

        # 验证
        parent1 = agent.get_node(parent1_result["node_id"])
        parent2 = agent.get_node(parent2_result["node_id"])
        child = agent.get_node(child_result["node_id"])

        assert len(parent1.children) == 0
        assert len(parent2.children) == 1
        assert child.parent_id == parent2_result["node_id"]


# ============ Phase 10.4: 真实场景集成测试 ============


class TestRealWorldScenarios:
    """真实场景集成测试"""

    @pytest.mark.asyncio
    async def test_data_pipeline_workflow(self):
        """测试数据管道工作流场景"""
        agent = create_workflow_agent_for_test()

        # 用户说：帮我创建一个数据管道，包含抽取、转换、加载三个阶段

        # 1. 创建 ETL 主流程节点
        etl_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "ETL 数据管道"},
            }
        )
        etl_id = etl_result["node_id"]

        # 2. 创建三个子阶段
        extract_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "1. 数据抽取 (Extract)"},
                "parent_id": etl_id,
            }
        )
        transform_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "2. 数据转换 (Transform)"},
                "parent_id": etl_id,
            }
        )
        load_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "3. 数据加载 (Load)"},
                "parent_id": etl_id,
            }
        )

        # 3. 在每个阶段添加具体步骤
        await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "code",
                "config": {"code": "df = pd.read_sql(query, conn)"},
                "parent_id": extract_result["node_id"],
            }
        )
        await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "code",
                "config": {"code": "df = df.dropna().fillna(0)"},
                "parent_id": transform_result["node_id"],
            }
        )
        await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "code",
                "config": {"code": "df.to_sql('target', conn)"},
                "parent_id": load_result["node_id"],
            }
        )

        # 验证结构
        etl = agent.get_node(etl_id)
        assert len(etl.children) == 3

        tree = agent.get_node_tree(etl_id)
        assert len(tree["children"]) == 3
        assert all(len(c["children"]) == 1 for c in tree["children"])

    @pytest.mark.asyncio
    async def test_custom_ai_node_scenario(self):
        """测试自定义 AI 节点场景"""
        agent = create_workflow_agent_for_test()

        # 用户说：我需要一个自定义的 AI 摘要节点

        # 1. 定义自定义节点类型
        agent.define_custom_node_type(
            type_name="ai_summarizer",
            schema={
                "model": {"type": "string", "default": "gpt-4"},
                "max_tokens": {"type": "integer", "default": 500},
                "prompt_template": {"type": "string", "required": True},
            },
        )

        # 2. 创建流程
        flow_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "文档处理流程"},
            }
        )

        # 3. 使用自定义节点
        summarizer_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "ai_summarizer",
                "config": {
                    "prompt_template": "请总结以下内容：{content}",
                    "max_tokens": 200,
                },
                "parent_id": flow_result["node_id"],
            }
        )

        # 验证
        summarizer = agent.get_node(summarizer_result["node_id"])
        assert summarizer.config.get("prompt_template") == "请总结以下内容：{content}"

    @pytest.mark.asyncio
    async def test_collapse_expand_user_interaction(self):
        """测试用户折叠展开交互场景"""
        agent = create_workflow_agent_for_test()

        # 创建嵌套结构
        root_result = await agent.handle_decision(
            {
                "decision_type": "create_node",
                "node_type": "generic",
                "config": {"name": "主流程"},
            }
        )

        for i in range(3):
            await agent.handle_decision(
                {
                    "decision_type": "create_node",
                    "node_type": "code",
                    "config": {"code": f"step_{i}"},
                    "parent_id": root_result["node_id"],
                }
            )

        # 默认折叠，用户看不到子节点
        root = agent.get_node(root_result["node_id"])
        assert root.collapsed is True
        assert root.get_visible_children() == []

        # 用户点击展开
        await agent.handle_decision(
            {
                "decision_type": "toggle_collapse",
                "node_id": root_result["node_id"],
            }
        )

        # 现在能看到子节点
        assert root.collapsed is False
        assert len(root.get_visible_children()) == 3

        # 用户再次点击折叠
        await agent.handle_decision(
            {
                "decision_type": "toggle_collapse",
                "node_id": root_result["node_id"],
            }
        )

        assert root.collapsed is True
        assert root.get_visible_children() == []

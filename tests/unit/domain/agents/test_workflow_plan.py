"""工作流规划测试 - Phase 8.2

TDD RED阶段：测试 WorkflowPlan 数据结构
"""

import pytest


class TestWorkflowPlan:
    """WorkflowPlan 基础测试"""

    def test_create_workflow_plan_with_multiple_nodes(self):
        """应支持创建包含多个节点的工作流规划"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(
                name="读取数据",
                code="data = read_file(input_file)",
            ),
            NodeDefinitionFactory.create_python_node(
                name="处理数据",
                code="result = process(data)",
            ),
            NodeDefinitionFactory.create_python_node(
                name="输出结果",
                code="save(result)",
            ),
        ]

        plan = WorkflowPlan(
            name="数据处理流程",
            description="读取、处理、输出数据",
            goal="处理输入文件并保存结果",
            nodes=nodes,
        )

        assert plan.name == "数据处理流程"
        assert len(plan.nodes) == 3
        assert plan.nodes[0].name == "读取数据"

    def test_workflow_plan_has_unique_id(self):
        """工作流规划应有唯一ID"""
        from src.domain.agents.workflow_plan import WorkflowPlan

        plan1 = WorkflowPlan(name="Plan1", goal="Goal1")
        plan2 = WorkflowPlan(name="Plan2", goal="Goal2")

        assert plan1.id is not None
        assert plan2.id is not None
        assert plan1.id != plan2.id

    def test_workflow_plan_with_edges(self):
        """工作流规划应支持边定义"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="A", code="pass"),
            NodeDefinitionFactory.create_python_node(name="B", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="A", target_node="B"),
        ]

        plan = WorkflowPlan(
            name="简单流程",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        assert len(plan.edges) == 1
        assert plan.edges[0].source_node == "A"
        assert plan.edges[0].target_node == "B"


class TestEdgeDefinition:
    """EdgeDefinition 测试"""

    def test_create_edge_definition(self):
        """创建边定义"""
        from src.domain.agents.workflow_plan import EdgeDefinition

        edge = EdgeDefinition(
            source_node="读取数据",
            target_node="处理数据",
        )

        assert edge.source_node == "读取数据"
        assert edge.target_node == "处理数据"
        assert edge.condition is None

    def test_create_edge_with_condition(self):
        """创建带条件的边"""
        from src.domain.agents.workflow_plan import EdgeDefinition

        edge = EdgeDefinition(
            source_node="判断节点",
            target_node="成功处理",
            condition="result.success == True",
        )

        assert edge.condition == "result.success == True"


class TestWorkflowPlanValidation:
    """WorkflowPlan 验证测试"""

    def test_workflow_plan_validates_edge_references(self):
        """边引用的节点必须存在"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="A", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="A", target_node="不存在的节点"),
        ]

        plan = WorkflowPlan(
            name="测试",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        errors = plan.validate()
        assert len(errors) > 0
        assert any("不存在" in err or "target" in err.lower() for err in errors)

    def test_workflow_plan_validates_node_definitions(self):
        """应验证所有节点定义"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_plan import WorkflowPlan

        # 创建一个无效的 Python 节点（缺少 code）
        invalid_node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="无效节点",
            # 缺少 code
        )

        plan = WorkflowPlan(
            name="测试",
            goal="测试",
            nodes=[invalid_node],
        )

        errors = plan.validate()
        assert len(errors) > 0
        assert any("code" in err.lower() for err in errors)

    def test_workflow_plan_detects_circular_dependency(self):
        """应检测循环依赖"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="A", code="pass"),
            NodeDefinitionFactory.create_python_node(name="B", code="pass"),
            NodeDefinitionFactory.create_python_node(name="C", code="pass"),
        ]
        # 创建循环: A → B → C → A
        edges = [
            EdgeDefinition(source_node="A", target_node="B"),
            EdgeDefinition(source_node="B", target_node="C"),
            EdgeDefinition(source_node="C", target_node="A"),  # 形成循环
        ]

        plan = WorkflowPlan(
            name="循环测试",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        assert plan.has_circular_dependency() is True

    def test_workflow_plan_no_circular_dependency(self):
        """无循环依赖时应返回 False"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="A", code="pass"),
            NodeDefinitionFactory.create_python_node(name="B", code="pass"),
            NodeDefinitionFactory.create_python_node(name="C", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="A", target_node="B"),
            EdgeDefinition(source_node="B", target_node="C"),
        ]

        plan = WorkflowPlan(
            name="无循环测试",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        assert plan.has_circular_dependency() is False

    def test_valid_workflow_plan_should_pass_validation(self):
        """有效的工作流规划应通过验证"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="读取", code="data = read()"),
            NodeDefinitionFactory.create_python_node(name="处理", code="result = process(data)"),
        ]
        edges = [
            EdgeDefinition(source_node="读取", target_node="处理"),
        ]

        plan = WorkflowPlan(
            name="有效流程",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        errors = plan.validate()
        assert len(errors) == 0


class TestWorkflowPlanExecutionOrder:
    """WorkflowPlan 执行顺序测试"""

    def test_workflow_plan_topological_order(self):
        """应返回正确的拓扑执行顺序"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="C", code="pass"),
            NodeDefinitionFactory.create_python_node(name="A", code="pass"),
            NodeDefinitionFactory.create_python_node(name="B", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="A", target_node="B"),
            EdgeDefinition(source_node="B", target_node="C"),
        ]

        plan = WorkflowPlan(
            name="顺序测试",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        order = plan.get_execution_order()

        # A 应该在 B 之前，B 应该在 C 之前
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_workflow_plan_parallel_nodes(self):
        """并行节点应都在依赖节点之后"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        #   A
        #  / \
        # B   C
        #  \ /
        #   D
        nodes = [
            NodeDefinitionFactory.create_python_node(name="A", code="pass"),
            NodeDefinitionFactory.create_python_node(name="B", code="pass"),
            NodeDefinitionFactory.create_python_node(name="C", code="pass"),
            NodeDefinitionFactory.create_python_node(name="D", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="A", target_node="B"),
            EdgeDefinition(source_node="A", target_node="C"),
            EdgeDefinition(source_node="B", target_node="D"),
            EdgeDefinition(source_node="C", target_node="D"),
        ]

        plan = WorkflowPlan(
            name="并行测试",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        order = plan.get_execution_order()

        # A 在 B 和 C 之前
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        # B 和 C 都在 D 之前
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_workflow_plan_execution_order_with_cycle_raises_error(self):
        """有循环依赖时获取执行顺序应抛出错误"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="A", code="pass"),
            NodeDefinitionFactory.create_python_node(name="B", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="A", target_node="B"),
            EdgeDefinition(source_node="B", target_node="A"),
        ]

        plan = WorkflowPlan(
            name="循环测试",
            goal="测试",
            nodes=nodes,
            edges=edges,
        )

        with pytest.raises(ValueError, match="[Cc]ircular|[Cc]ycle|循环"):
            plan.get_execution_order()


class TestWorkflowPlanSerialization:
    """WorkflowPlan 序列化测试"""

    def test_workflow_plan_to_dict(self):
        """to_dict 应序列化完整规划"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="节点A", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="节点A", target_node="节点B"),
        ]

        plan = WorkflowPlan(
            name="测试规划",
            description="测试用",
            goal="完成测试",
            nodes=nodes,
            edges=edges,
        )

        data = plan.to_dict()

        assert data["id"] == plan.id
        assert data["name"] == "测试规划"
        assert data["goal"] == "完成测试"
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1

    def test_workflow_plan_from_dict(self):
        """from_dict 应反序列化规划"""
        from src.domain.agents.workflow_plan import WorkflowPlan

        data = {
            "id": "plan_123",
            "name": "恢复的规划",
            "description": "从字典恢复",
            "goal": "测试目标",
            "nodes": [
                {
                    "id": "node_1",
                    "node_type": "python",
                    "name": "节点1",
                    "code": "return 42",
                }
            ],
            "edges": [
                {
                    "source_node": "节点1",
                    "target_node": "节点2",
                }
            ],
        }

        plan = WorkflowPlan.from_dict(data)

        assert plan.id == "plan_123"
        assert plan.name == "恢复的规划"
        assert plan.goal == "测试目标"
        assert len(plan.nodes) == 1
        assert plan.nodes[0].name == "节点1"
        assert len(plan.edges) == 1


class TestWorkflowPlanHelpers:
    """WorkflowPlan 辅助方法测试"""

    def test_get_node_by_name(self):
        """应能通过名称获取节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="读取", code="pass"),
            NodeDefinitionFactory.create_python_node(name="处理", code="pass"),
        ]

        plan = WorkflowPlan(name="测试", goal="测试", nodes=nodes)

        node = plan.get_node_by_name("处理")
        assert node is not None
        assert node.name == "处理"

    def test_get_node_by_name_returns_none_if_not_found(self):
        """节点不存在时返回 None"""
        from src.domain.agents.workflow_plan import WorkflowPlan

        plan = WorkflowPlan(name="测试", goal="测试", nodes=[])

        node = plan.get_node_by_name("不存在")
        assert node is None

    def test_get_root_nodes(self):
        """应返回没有入边的根节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="入口1", code="pass"),
            NodeDefinitionFactory.create_python_node(name="入口2", code="pass"),
            NodeDefinitionFactory.create_python_node(name="处理", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="入口1", target_node="处理"),
            EdgeDefinition(source_node="入口2", target_node="处理"),
        ]

        plan = WorkflowPlan(name="测试", goal="测试", nodes=nodes, edges=edges)

        roots = plan.get_root_nodes()
        root_names = [n.name for n in roots]

        assert "入口1" in root_names
        assert "入口2" in root_names
        assert "处理" not in root_names

    def test_get_leaf_nodes(self):
        """应返回没有出边的叶子节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        nodes = [
            NodeDefinitionFactory.create_python_node(name="入口", code="pass"),
            NodeDefinitionFactory.create_python_node(name="出口1", code="pass"),
            NodeDefinitionFactory.create_python_node(name="出口2", code="pass"),
        ]
        edges = [
            EdgeDefinition(source_node="入口", target_node="出口1"),
            EdgeDefinition(source_node="入口", target_node="出口2"),
        ]

        plan = WorkflowPlan(name="测试", goal="测试", nodes=nodes, edges=edges)

        leaves = plan.get_leaf_nodes()
        leaf_names = [n.name for n in leaves]

        assert "出口1" in leaf_names
        assert "出口2" in leaf_names
        assert "入口" not in leaf_names

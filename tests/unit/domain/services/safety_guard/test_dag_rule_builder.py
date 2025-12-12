"""DagRuleBuilder 单元测试 - Phase 35.2

TDD Red Phase: 测试 DagRuleBuilder 的DAG验证规则构建方法
"""

import pytest

from src.domain.services.safety_guard.dag_rule_builder import CycleDetector, DagRuleBuilder
from src.domain.services.safety_guard.rules import Rule


@pytest.fixture
def builder():
    """DagRuleBuilder fixture"""
    return DagRuleBuilder()


class TestBuildDagValidationRule:
    """测试：构建DAG验证规则"""

    def test_build_dag_validation_rule_returns_rule(self, builder):
        """测试：返回Rule对象"""
        rule = builder.build_dag_validation_rule()

        assert isinstance(rule, Rule)
        assert rule.id == "dag_validation"
        assert "DAG 结构验证" in rule.name

    def test_dag_validation_rule_passes_valid_dag(self, builder):
        """测试：有效DAG通过验证"""
        rule = builder.build_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "nodes": [
                {"node_id": "node1"},
                {"node_id": "node2"},
                {"node_id": "node3"},
            ],
            "edges": [
                {"source": "node1", "target": "node2"},
                {"source": "node2", "target": "node3"},
            ],
        }

        assert rule.condition(decision) is True

    def test_dag_validation_rule_fails_duplicate_node_ids(self, builder):
        """测试：节点ID重复时失败"""
        rule = builder.build_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "nodes": [
                {"node_id": "node1"},
                {"node_id": "node1"},  # 重复
            ],
            "edges": [],
        }

        assert rule.condition(decision) is False
        assert "_dag_errors" in decision
        assert any("节点 ID 重复" in err for err in decision["_dag_errors"])

    def test_dag_validation_rule_fails_missing_source_node(self, builder):
        """测试：边引用的源节点不存在时失败"""
        rule = builder.build_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "nodes": [{"node_id": "node1"}],
            "edges": [{"source": "node2", "target": "node1"}],  # node2 不存在
        }

        assert rule.condition(decision) is False
        assert "_dag_errors" in decision
        assert any("源节点 node2 不存在" in err for err in decision["_dag_errors"])

    def test_dag_validation_rule_fails_missing_target_node(self, builder):
        """测试：边引用的目标节点不存在时失败"""
        rule = builder.build_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "nodes": [{"node_id": "node1"}],
            "edges": [{"source": "node1", "target": "node2"}],  # node2 不存在
        }

        assert rule.condition(decision) is False
        assert "_dag_errors" in decision
        assert any("目标节点 node2 不存在" in err for err in decision["_dag_errors"])

    def test_dag_validation_rule_detects_cycle(self, builder):
        """测试：检测循环依赖"""
        rule = builder.build_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "nodes": [
                {"node_id": "node1"},
                {"node_id": "node2"},
                {"node_id": "node3"},
            ],
            "edges": [
                {"source": "node1", "target": "node2"},
                {"source": "node2", "target": "node3"},
                {"source": "node3", "target": "node1"},  # 循环
            ],
        }

        assert rule.condition(decision) is False
        assert "_dag_errors" in decision
        assert any("循环依赖" in err for err in decision["_dag_errors"])

    def test_dag_validation_rule_skips_other_decision_types(self, builder):
        """测试：非工作流决策跳过验证"""
        rule = builder.build_dag_validation_rule()

        decision = {
            "action_type": "other_action",
            # 缺少nodes/edges，但不会被检查
        }

        assert rule.condition(decision) is True


class TestCycleDetector:
    """测试：Kahn算法循环检测器"""

    def test_detect_cycle_returns_false_for_acyclic_graph(self):
        """测试：无环图返回False"""
        nodes = [
            {"node_id": "node1"},
            {"node_id": "node2"},
            {"node_id": "node3"},
        ]
        edges = [
            {"source": "node1", "target": "node2"},
            {"source": "node2", "target": "node3"},
        ]

        has_cycle, unvisited = CycleDetector.detect_cycle_kahn(nodes, edges)

        assert has_cycle is False
        assert unvisited == []

    def test_detect_cycle_returns_true_for_cyclic_graph(self):
        """测试：有环图返回True"""
        nodes = [
            {"node_id": "node1"},
            {"node_id": "node2"},
            {"node_id": "node3"},
        ]
        edges = [
            {"source": "node1", "target": "node2"},
            {"source": "node2", "target": "node3"},
            {"source": "node3", "target": "node1"},  # 循环
        ]

        has_cycle, unvisited = CycleDetector.detect_cycle_kahn(nodes, edges)

        assert has_cycle is True
        assert len(unvisited) == 3  # 所有节点都在循环中

    def test_detect_cycle_handles_self_loop(self):
        """测试：自环检测"""
        nodes = [{"node_id": "node1"}]
        edges = [{"source": "node1", "target": "node1"}]  # 自环

        has_cycle, unvisited = CycleDetector.detect_cycle_kahn(nodes, edges)

        assert has_cycle is True
        assert "node1" in unvisited

    def test_detect_cycle_handles_disconnected_components(self):
        """测试：处理不连通图"""
        nodes = [
            {"node_id": "node1"},
            {"node_id": "node2"},
            {"node_id": "node3"},
            {"node_id": "node4"},
        ]
        edges = [
            {"source": "node1", "target": "node2"},
            # node3 和 node4 独立
        ]

        has_cycle, unvisited = CycleDetector.detect_cycle_kahn(nodes, edges)

        assert has_cycle is False
        assert unvisited == []

    def test_detect_cycle_handles_partial_cycle(self):
        """测试：部分环路检测"""
        nodes = [
            {"node_id": "node1"},
            {"node_id": "node2"},
            {"node_id": "node3"},
            {"node_id": "node4"},
        ]
        edges = [
            {"source": "node1", "target": "node2"},
            {"source": "node2", "target": "node3"},
            {"source": "node3", "target": "node2"},  # node2-node3环路
            {"source": "node1", "target": "node4"},  # node4独立
        ]

        has_cycle, unvisited = CycleDetector.detect_cycle_kahn(nodes, edges)

        assert has_cycle is True
        assert "node2" in unvisited
        assert "node3" in unvisited
        assert "node1" not in unvisited  # node1不在环路中
        assert "node4" not in unvisited  # node4不在环路中

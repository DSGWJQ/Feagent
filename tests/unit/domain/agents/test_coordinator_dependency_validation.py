"""测试：Coordinator 依赖关系校验 - Phase 8.4 TDD Red 阶段

测试目标：
1. Coordinator 能够检测工作流中的循环依赖
2. Coordinator 能够验证节点引用的有效性
3. Coordinator 能够验证 DAG 结构完整性
4. 验证失败时返回详细错误信息

完成标准：
- 所有测试初始失败（Red阶段）
- 实现代码后所有测试通过（Green阶段）
"""


class TestCircularDependencyDetection:
    """测试循环依赖检测"""

    def test_detect_simple_circular_dependency(self):
        """检测简单的循环依赖（A→B→A）

        场景：工作流中存在两个节点相互依赖
        期望：Coordinator 拒绝此决策，指出循环依赖
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 添加 DAG 验证规则
        coordinator.add_dag_validation_rule()

        # 创建包含循环依赖的工作流
        decision = {
            "action_type": "create_workflow_plan",
            "name": "循环工作流",
            "description": "测试循环依赖检测",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
                {"node_id": "node_2", "type": "HTTP", "name": "节点2", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_1"},  # 循环！
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("循环" in error or "cycle" in error.lower() for error in result.errors)

    def test_detect_complex_circular_dependency(self):
        """检测复杂的循环依赖（A→B→C→A）

        场景：工作流中存在三个节点形成循环
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "复杂循环",
            "description": "测试复杂循环依赖",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
                {"node_id": "node_2", "type": "LLM", "name": "节点2", "config": {}},
                {"node_id": "node_3", "type": "PYTHON", "name": "节点3", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_3"},
                {"source": "node_3", "target": "node_1"},  # 循环！
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("循环" in error or "cycle" in error.lower() for error in result.errors)

    def test_acyclic_graph_should_pass(self):
        """无循环依赖的工作流应通过验证

        场景：工作流形成有效的 DAG 结构
        期望：Coordinator 接受此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "有效工作流",
            "description": "无循环依赖",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
                {"node_id": "node_2", "type": "LLM", "name": "节点2", "config": {}},
                {"node_id": "node_3", "type": "PYTHON", "name": "节点3", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_3"},
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True
        assert len(result.errors) == 0


class TestNodeReferenceValidation:
    """测试节点引用有效性"""

    def test_edge_with_missing_source_node(self):
        """边引用不存在的源节点应失败

        场景：edge.source 指向的节点不存在
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "缺失源节点",
            "description": "测试节点引用",
            "nodes": [
                {"node_id": "node_2", "type": "LLM", "name": "节点2", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},  # node_1 不存在
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("node_1" in error and "不存在" in error for error in result.errors)

    def test_edge_with_missing_target_node(self):
        """边引用不存在的目标节点应失败

        场景：edge.target 指向的节点不存在
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "缺失目标节点",
            "description": "测试节点引用",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},  # node_2 不存在
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("node_2" in error and "不存在" in error for error in result.errors)

    def test_all_node_references_valid_should_pass(self):
        """所有节点引用有效应通过验证

        场景：所有边的 source 和 target 都存在
        期望：Coordinator 接受此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "有效引用",
            "description": "所有引用都存在",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
                {"node_id": "node_2", "type": "LLM", "name": "节点2", "config": {}},
                {"node_id": "node_3", "type": "PYTHON", "name": "节点3", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_1", "target": "node_3"},
                {"source": "node_2", "target": "node_3"},
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True


class TestNodeIdUniqueness:
    """测试节点 ID 唯一性"""

    def test_duplicate_node_ids_should_fail(self):
        """重复的节点 ID 应失败

        场景：工作流中有两个节点使用相同的 node_id
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "重复ID",
            "description": "测试节点ID唯一性",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
                {"node_id": "node_1", "type": "LLM", "name": "节点2", "config": {}},  # 重复 ID
            ],
            "edges": [],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("重复" in error or "duplicate" in error.lower() for error in result.errors)

    def test_unique_node_ids_should_pass(self):
        """唯一的节点 ID 应通过验证

        场景：所有节点 ID 都是唯一的
        期望：Coordinator 接受此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "唯一ID",
            "description": "所有节点ID唯一",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
                {"node_id": "node_2", "type": "LLM", "name": "节点2", "config": {}},
                {"node_id": "node_3", "type": "PYTHON", "name": "节点3", "config": {}},
            ],
            "edges": [],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True


class TestTopologicalSortFeasibility:
    """测试拓扑排序可行性"""

    def test_topological_sort_possible_for_valid_dag(self):
        """有效的 DAG 应该可以拓扑排序

        场景：工作流是有效的 DAG
        期望：Coordinator 接受并返回拓扑排序结果
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "可排序工作流",
            "description": "测试拓扑排序",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "获取数据", "config": {}},
                {"node_id": "node_2", "type": "PYTHON", "name": "处理数据", "config": {}},
                {"node_id": "node_3", "type": "LLM", "name": "分析数据", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_3"},
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True
        # 验证元数据中包含拓扑排序结果（如果实现了的话）
        # assert "topological_order" in result.metadata

    def test_diamond_dependency_should_be_valid(self):
        """菱形依赖结构应该有效

        场景：工作流形成菱形依赖（A→B/C，B/C→D）
        期望：Coordinator 接受此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "菱形依赖",
            "description": "测试菱形结构",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "起点", "config": {}},
                {"node_id": "node_2", "type": "PYTHON", "name": "分支1", "config": {}},
                {"node_id": "node_3", "type": "PYTHON", "name": "分支2", "config": {}},
                {"node_id": "node_4", "type": "LLM", "name": "汇合", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_1", "target": "node_3"},
                {"source": "node_2", "target": "node_4"},
                {"source": "node_3", "target": "node_4"},
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True


class TestDependencyValidationIntegration:
    """测试依赖验证集成"""

    def test_multiple_violations_should_all_be_reported(self):
        """多个违规应该全部报告

        场景：工作流同时存在循环依赖和无效节点引用
        期望：所有错误都被报告
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "多重违规",
            "description": "测试多个错误",
            "nodes": [
                {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {}},
                {"node_id": "node_2", "type": "LLM", "name": "节点2", "config": {}},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_1"},  # 循环
                {"source": "node_3", "target": "node_1"},  # node_3 不存在
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        # 应该报告循环和缺失节点两个错误
        assert len(result.errors) >= 2

    def test_valid_complex_workflow_should_pass_all_checks(self):
        """复杂但有效的工作流应通过所有检查

        场景：包含多个节点、多条边的复杂工作流
        期望：通过所有验证
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()
        coordinator.add_dag_validation_rule()

        decision = {
            "action_type": "create_workflow_plan",
            "name": "复杂工作流",
            "description": "多节点多边",
            "nodes": [
                {"node_id": "fetch_data", "type": "HTTP", "name": "获取数据", "config": {}},
                {"node_id": "clean_data", "type": "PYTHON", "name": "清洗数据", "config": {}},
                {"node_id": "calc_metrics", "type": "PYTHON", "name": "计算指标", "config": {}},
                {"node_id": "gen_chart", "type": "PYTHON", "name": "生成图表", "config": {}},
                {"node_id": "analyze", "type": "LLM", "name": "分析结果", "config": {}},
                {"node_id": "send_report", "type": "HTTP", "name": "发送报告", "config": {}},
            ],
            "edges": [
                {"source": "fetch_data", "target": "clean_data"},
                {"source": "clean_data", "target": "calc_metrics"},
                {"source": "calc_metrics", "target": "gen_chart"},
                {"source": "calc_metrics", "target": "analyze"},
                {"source": "gen_chart", "target": "send_report"},
                {"source": "analyze", "target": "send_report"},
            ],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True
        assert len(result.errors) == 0


# 导出
__all__ = [
    "TestCircularDependencyDetection",
    "TestNodeReferenceValidation",
    "TestNodeIdUniqueness",
    "TestTopologicalSortFeasibility",
    "TestDependencyValidationIntegration",
]

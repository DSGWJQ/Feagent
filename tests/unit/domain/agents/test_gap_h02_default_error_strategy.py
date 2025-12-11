"""GAP-H02: 全局错误策略测试

测试目标：验证 WorkflowPlan 支持全局默认错误策略
- default_error_strategy 字段
- 节点级策略覆盖全局策略
- 策略合并逻辑

TDD 阶段：Red（测试先行）
"""

from src.domain.agents.node_definition import NodeDefinition, NodeType
from src.domain.agents.workflow_plan import WorkflowPlan


class TestWorkflowPlanDefaultErrorStrategy:
    """WorkflowPlan 默认错误策略测试"""

    def test_workflow_plan_has_default_error_strategy_field(self):
        """测试 WorkflowPlan 有 default_error_strategy 字段"""
        plan = WorkflowPlan(
            name="测试工作流",
            goal="测试目标",
            default_error_strategy={
                "retry": {"max_attempts": 3, "delay_seconds": 1.0},
                "on_failure": "skip",
            },
        )

        assert hasattr(
            plan, "default_error_strategy"
        ), "WorkflowPlan 应该有 default_error_strategy 字段"
        assert plan.default_error_strategy is not None, "default_error_strategy 应该被设置"

    def test_default_error_strategy_is_optional(self):
        """测试 default_error_strategy 是可选的"""
        plan = WorkflowPlan(name="测试工作流", goal="测试目标")

        # 应该有默认值 None 或空字典
        assert hasattr(
            plan, "default_error_strategy"
        ), "WorkflowPlan 应该有 default_error_strategy 字段"
        # 明确验证默认值
        assert (
            plan.default_error_strategy is None or plan.default_error_strategy == {}
        ), "未设置时 default_error_strategy 应该是 None 或空字典"

    def test_node_without_strategy_and_no_default_returns_none(self):
        """测试节点无策略且无默认策略时返回 None"""
        node = NodeDefinition(node_type=NodeType.PYTHON, name="test_node", code="print('hello')")

        plan = WorkflowPlan(
            name="测试工作流",
            goal="测试目标",
            nodes=[node],
            # 没有设置 default_error_strategy
        )

        effective_strategy = plan.get_effective_error_strategy(node.name)
        assert effective_strategy is None, "无默认策略且节点未配置时应返回 None"

    def test_default_error_strategy_structure(self):
        """测试默认错误策略的结构"""
        strategy = {
            "retry": {"max_attempts": 3, "delay_seconds": 1.0, "backoff_multiplier": 2.0},
            "on_failure": "abort",
            "fallback": {"node_name": "fallback_node", "default_value": {}},
        }

        plan = WorkflowPlan(name="测试工作流", goal="测试目标", default_error_strategy=strategy)

        assert plan.default_error_strategy["retry"]["max_attempts"] == 3
        assert plan.default_error_strategy["on_failure"] == "abort"


class TestErrorStrategyInheritance:
    """错误策略继承测试"""

    def test_node_inherits_default_strategy(self):
        """测试节点继承工作流默认策略"""
        default_strategy = {"retry": {"max_attempts": 3}, "on_failure": "retry"}

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test_node",
            code="print('hello')",
            # 没有设置 error_strategy
        )

        plan = WorkflowPlan(
            name="测试工作流",
            goal="测试目标",
            nodes=[node],
            default_error_strategy=default_strategy,
        )

        # 获取节点的有效错误策略
        effective_strategy = plan.get_effective_error_strategy(node.name)

        assert effective_strategy is not None, "应该返回有效策略"
        assert effective_strategy["retry"]["max_attempts"] == 3, "应该继承默认策略的重试次数"

    def test_node_strategy_overrides_default(self):
        """测试节点策略覆盖默认策略"""
        default_strategy = {"retry": {"max_attempts": 3}, "on_failure": "retry"}

        node_strategy = {"retry": {"max_attempts": 5}, "on_failure": "abort"}

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test_node",
            code="print('hello')",
            error_strategy=node_strategy,
        )

        plan = WorkflowPlan(
            name="测试工作流",
            goal="测试目标",
            nodes=[node],
            default_error_strategy=default_strategy,
        )

        effective_strategy = plan.get_effective_error_strategy(node.name)

        # 节点策略应该覆盖默认策略
        assert effective_strategy["retry"]["max_attempts"] == 5, "节点策略应该覆盖默认策略"
        assert effective_strategy["on_failure"] == "abort", "节点的 on_failure 应该覆盖默认"

    def test_partial_node_strategy_merges_with_default(self):
        """测试节点部分策略与默认策略合并"""
        default_strategy = {
            "retry": {"max_attempts": 3, "delay_seconds": 1.0},
            "on_failure": "retry",
        }

        # 节点只覆盖部分策略
        node_strategy = {
            "on_failure": "skip"  # 只覆盖 on_failure
        }

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test_node",
            code="print('hello')",
            error_strategy=node_strategy,
        )

        plan = WorkflowPlan(
            name="测试工作流",
            goal="测试目标",
            nodes=[node],
            default_error_strategy=default_strategy,
        )

        effective_strategy = plan.get_effective_error_strategy(node.name)

        # 应该合并：retry 从默认，on_failure 从节点
        assert effective_strategy["retry"]["max_attempts"] == 3, "retry 应该从默认策略继承"
        assert effective_strategy["on_failure"] == "skip", "on_failure 应该被节点策略覆盖"


class TestErrorStrategySerialization:
    """错误策略序列化测试"""

    def test_to_dict_includes_default_error_strategy(self):
        """测试 to_dict 包含默认错误策略"""
        strategy = {"retry": {"max_attempts": 3}, "on_failure": "abort"}

        plan = WorkflowPlan(name="测试工作流", goal="测试目标", default_error_strategy=strategy)

        data = plan.to_dict()

        assert "default_error_strategy" in data, "序列化结果应该包含 default_error_strategy"
        assert data["default_error_strategy"]["on_failure"] == "abort"

    def test_from_dict_restores_default_error_strategy(self):
        """测试 from_dict 恢复默认错误策略"""
        data = {
            "name": "测试工作流",
            "goal": "测试目标",
            "nodes": [],
            "edges": [],
            "default_error_strategy": {"retry": {"max_attempts": 5}, "on_failure": "skip"},
        }

        plan = WorkflowPlan.from_dict(data)

        assert plan.default_error_strategy is not None
        assert plan.default_error_strategy["retry"]["max_attempts"] == 5
        assert plan.default_error_strategy["on_failure"] == "skip"


class TestErrorStrategyValidation:
    """错误策略验证测试"""

    def test_invalid_on_failure_value(self):
        """测试无效的 on_failure 值"""
        strategy = {
            "on_failure": "invalid_action"  # 无效值
        }

        plan = WorkflowPlan(name="测试工作流", goal="测试目标", default_error_strategy=strategy)

        errors = plan.validate()

        assert any("on_failure" in err for err in errors), "应该报告无效的 on_failure 值"

    def test_valid_on_failure_values(self):
        """测试有效的 on_failure 值"""
        valid_values = ["retry", "skip", "abort", "replan", "fallback"]

        for value in valid_values:
            strategy = {"on_failure": value}
            plan = WorkflowPlan(name="测试工作流", goal="测试目标", default_error_strategy=strategy)

            errors = plan.validate()
            on_failure_errors = [e for e in errors if "on_failure" in e]
            assert len(on_failure_errors) == 0, f"'{value}' 应该是有效的 on_failure 值"

    def test_retry_max_attempts_range(self):
        """测试重试次数范围验证"""
        # 负数应该无效
        strategy = {"retry": {"max_attempts": -1}}
        plan = WorkflowPlan(name="测试", goal="测试", default_error_strategy=strategy)

        errors = plan.validate()
        assert any("max_attempts" in err for err in errors), "负数重试次数应该无效"

        # 超大数值应该无效
        strategy = {"retry": {"max_attempts": 100}}
        plan = WorkflowPlan(name="测试", goal="测试", default_error_strategy=strategy)

        errors = plan.validate()
        assert any("max_attempts" in err for err in errors), "超过10的重试次数应该无效"

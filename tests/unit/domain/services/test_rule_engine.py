"""规则引擎单元测试

TDD Phase: RED -> GREEN -> REFACTOR

测试规则引擎的核心功能：
1. 规则注册与管理
2. 规则评估与匹配
3. 规则优先级排序
4. 规则动作执行
5. 真实场景测试
"""

import tempfile
from pathlib import Path


class TestRuleType:
    """规则类型测试"""

    def test_static_rule_type(self):
        """测试：静态规则类型"""
        from src.domain.services.rule_engine import RuleType

        assert RuleType.STATIC.value == "static"

    def test_dynamic_rule_type(self):
        """测试：动态规则类型"""
        from src.domain.services.rule_engine import RuleType

        assert RuleType.DYNAMIC.value == "dynamic"


class TestRuleAction:
    """规则动作测试"""

    def test_log_warning_action(self):
        """测试：日志警告动作"""
        from src.domain.services.rule_engine import RuleAction

        assert RuleAction.LOG_WARNING.value == "log_warning"

    def test_suggest_correction_action(self):
        """测试：建议修正动作"""
        from src.domain.services.rule_engine import RuleAction

        assert RuleAction.SUGGEST_CORRECTION.value == "suggest"

    def test_reject_decision_action(self):
        """测试：拒绝决策动作"""
        from src.domain.services.rule_engine import RuleAction

        assert RuleAction.REJECT_DECISION.value == "reject"

    def test_force_terminate_action(self):
        """测试：强制终止动作"""
        from src.domain.services.rule_engine import RuleAction

        assert RuleAction.FORCE_TERMINATE.value == "terminate"


class TestRule:
    """规则实体测试"""

    def test_create_rule(self):
        """测试：创建规则"""
        from src.domain.services.rule_engine import Rule, RuleAction, RuleType

        rule = Rule(
            id="test_rule",
            name="测试规则",
            description="这是一个测试规则",
            type=RuleType.STATIC,
            priority=1,
            condition="value > 10",
            action=RuleAction.LOG_WARNING,
        )

        assert rule.id == "test_rule"
        assert rule.name == "测试规则"
        assert rule.priority == 1
        assert rule.enabled is True

    def test_rule_default_enabled(self):
        """测试：规则默认启用"""
        from src.domain.services.rule_engine import Rule, RuleAction, RuleType

        rule = Rule(
            id="test",
            name="test",
            description="test",
            type=RuleType.STATIC,
            priority=1,
            condition="x > 0",
            action=RuleAction.LOG_WARNING,
        )

        assert rule.enabled is True

    def test_rule_can_be_disabled(self):
        """测试：规则可以禁用"""
        from src.domain.services.rule_engine import Rule, RuleAction, RuleType

        rule = Rule(
            id="test",
            name="test",
            description="test",
            type=RuleType.STATIC,
            priority=1,
            condition="x > 0",
            action=RuleAction.LOG_WARNING,
            enabled=False,
        )

        assert rule.enabled is False


class TestRuleEngine:
    """规则引擎测试"""

    def test_create_rule_engine(self):
        """测试：创建规则引擎"""
        from src.domain.services.rule_engine import RuleEngine

        engine = RuleEngine()

        assert engine is not None
        assert len(engine.rules) == 0

    def test_add_rule(self):
        """测试：添加规则"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        rule = Rule(
            id="rule_1",
            name="规则1",
            description="测试规则",
            type=RuleType.STATIC,
            priority=1,
            condition="x > 10",
            action=RuleAction.LOG_WARNING,
        )

        engine.add_rule(rule)

        assert len(engine.rules) == 1
        assert engine.rules[0].id == "rule_1"

    def test_add_multiple_rules_sorted_by_priority(self):
        """测试：添加多个规则按优先级排序"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()

        # 添加优先级为3的规则
        engine.add_rule(
            Rule(
                id="low_priority",
                name="低优先级",
                description="",
                type=RuleType.STATIC,
                priority=3,
                condition="x > 0",
                action=RuleAction.LOG_WARNING,
            )
        )

        # 添加优先级为1的规则
        engine.add_rule(
            Rule(
                id="high_priority",
                name="高优先级",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="x > 0",
                action=RuleAction.FORCE_TERMINATE,
            )
        )

        # 验证按优先级排序（小的在前）
        assert engine.rules[0].id == "high_priority"
        assert engine.rules[1].id == "low_priority"

    def test_remove_rule(self):
        """测试：删除规则"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        rule = Rule(
            id="to_remove",
            name="待删除",
            description="",
            type=RuleType.STATIC,
            priority=1,
            condition="x > 0",
            action=RuleAction.LOG_WARNING,
        )
        engine.add_rule(rule)

        engine.remove_rule("to_remove")

        assert len(engine.rules) == 0

    def test_get_rule_by_id(self):
        """测试：根据ID获取规则"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        rule = Rule(
            id="find_me",
            name="查找我",
            description="",
            type=RuleType.STATIC,
            priority=1,
            condition="x > 0",
            action=RuleAction.LOG_WARNING,
        )
        engine.add_rule(rule)

        found = engine.get_rule("find_me")

        assert found is not None
        assert found.name == "查找我"

    def test_get_nonexistent_rule_returns_none(self):
        """测试：获取不存在的规则返回None"""
        from src.domain.services.rule_engine import RuleEngine

        engine = RuleEngine()

        found = engine.get_rule("nonexistent")

        assert found is None


class TestRuleEvaluation:
    """规则评估测试"""

    def test_evaluate_simple_condition_true(self):
        """测试：评估简单条件为真"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="check_value",
                name="检查值",
                description="值大于10时触发",
                type=RuleType.STATIC,
                priority=1,
                condition="value > 10",
                action=RuleAction.LOG_WARNING,
            )
        )

        context = {"value": 15}
        violations = engine.evaluate(context)

        assert len(violations) == 1
        assert violations[0].rule_id == "check_value"

    def test_evaluate_simple_condition_false(self):
        """测试：评估简单条件为假"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="check_value",
                name="检查值",
                description="值大于10时触发",
                type=RuleType.STATIC,
                priority=1,
                condition="value > 10",
                action=RuleAction.LOG_WARNING,
            )
        )

        context = {"value": 5}
        violations = engine.evaluate(context)

        assert len(violations) == 0

    def test_evaluate_multiple_rules(self):
        """测试：评估多个规则"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="rule_1",
                name="规则1",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="x > 5",
                action=RuleAction.LOG_WARNING,
            )
        )
        engine.add_rule(
            Rule(
                id="rule_2",
                name="规则2",
                description="",
                type=RuleType.STATIC,
                priority=2,
                condition="y < 10",
                action=RuleAction.SUGGEST_CORRECTION,
            )
        )

        context = {"x": 10, "y": 5}
        violations = engine.evaluate(context)

        assert len(violations) == 2

    def test_evaluate_skips_disabled_rules(self):
        """测试：评估跳过禁用的规则"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="disabled_rule",
                name="禁用规则",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="x > 0",
                action=RuleAction.FORCE_TERMINATE,
                enabled=False,
            )
        )

        context = {"x": 100}
        violations = engine.evaluate(context)

        assert len(violations) == 0

    def test_evaluate_with_complex_condition(self):
        """测试：评估复杂条件"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="complex",
                name="复杂规则",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="iteration_count > 10 and token_used > 5000",
                action=RuleAction.FORCE_TERMINATE,
            )
        )

        context = {"iteration_count": 15, "token_used": 8000}
        violations = engine.evaluate(context)

        assert len(violations) == 1

    def test_evaluate_handles_invalid_condition(self):
        """测试：处理无效条件不抛异常"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="invalid",
                name="无效规则",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="undefined_var > 10",
                action=RuleAction.LOG_WARNING,
            )
        )

        context = {"x": 5}
        violations = engine.evaluate(context)

        # 无效条件应该返回False，不触发违规
        assert len(violations) == 0


class TestRuleViolation:
    """规则违规测试"""

    def test_violation_contains_rule_info(self):
        """测试：违规包含规则信息"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="test_rule",
                name="测试规则",
                description="这是测试",
                type=RuleType.STATIC,
                priority=1,
                condition="x > 0",
                action=RuleAction.REJECT_DECISION,
            )
        )

        violations = engine.evaluate({"x": 10})

        assert violations[0].rule_id == "test_rule"
        assert violations[0].rule_name == "测试规则"
        assert violations[0].action == RuleAction.REJECT_DECISION

    def test_violation_contains_context(self):
        """测试：违规包含上下文"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="test",
                name="test",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="value > 100",
                action=RuleAction.LOG_WARNING,
            )
        )

        context = {"value": 150, "user": "test_user"}
        violations = engine.evaluate(context)

        assert violations[0].context == context


class TestRuleLoading:
    """规则加载测试"""

    def test_load_rules_from_yaml(self):
        """测试：从YAML加载规则"""
        from src.domain.services.rule_engine import RuleAction, RuleEngine

        # 创建临时YAML文件
        yaml_content = """
rules:
  - id: "max_iterations"
    name: "Max Iterations Limit"
    description: "Prevent too many ReAct iterations"
    type: "static"
    priority: 1
    condition: "iteration_count > 10"
    action: "terminate"
    enabled: true
  - id: "token_budget"
    name: "Token Budget Limit"
    description: "Prevent excessive token usage"
    type: "static"
    priority: 1
    condition: "token_used > 10000"
    action: "terminate"
    enabled: true
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            config_path = f.name

        try:
            engine = RuleEngine()
            engine.load_rules(config_path)

            assert len(engine.rules) == 2
            assert engine.rules[0].id == "max_iterations"
            assert engine.rules[0].action == RuleAction.FORCE_TERMINATE
        finally:
            Path(config_path).unlink()

    def test_load_rules_from_dict(self):
        """测试：从字典加载规则"""
        from src.domain.services.rule_engine import RuleEngine

        rules_config = {
            "rules": [
                {
                    "id": "test_rule",
                    "name": "测试规则",
                    "description": "测试",
                    "type": "static",
                    "priority": 1,
                    "condition": "x > 0",
                    "action": "log_warning",
                    "enabled": True,
                }
            ]
        }

        engine = RuleEngine()
        engine.load_rules_from_dict(rules_config)

        assert len(engine.rules) == 1
        assert engine.rules[0].id == "test_rule"


class TestDynamicRules:
    """动态规则测试"""

    def test_add_dynamic_rule_at_runtime(self):
        """测试：运行时添加动态规则"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()

        # 模拟运行时动态创建规则
        dynamic_rule = Rule(
            id="dynamic_1",
            name="动态规则",
            description="运行时创建",
            type=RuleType.DYNAMIC,
            priority=1,
            condition="error_count > 3",
            action=RuleAction.FORCE_TERMINATE,
        )

        engine.add_rule(dynamic_rule)

        assert len(engine.rules) == 1
        assert engine.rules[0].type == RuleType.DYNAMIC

    def test_dynamic_rule_can_be_updated(self):
        """测试：动态规则可以更新"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()
        engine.add_rule(
            Rule(
                id="updatable",
                name="可更新规则",
                description="",
                type=RuleType.DYNAMIC,
                priority=1,
                condition="x > 5",
                action=RuleAction.LOG_WARNING,
            )
        )

        # 更新规则
        engine.update_rule(
            "updatable",
            condition="x > 10",
            action=RuleAction.FORCE_TERMINATE,
        )

        updated = engine.get_rule("updatable")
        assert updated.condition == "x > 10"
        assert updated.action == RuleAction.FORCE_TERMINATE


class TestRealWorldScenarios:
    """真实场景测试"""

    def test_react_loop_protection(self):
        """测试：ReAct循环保护"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()

        # 添加迭代次数限制规则
        engine.add_rule(
            Rule(
                id="max_iterations",
                name="最大迭代次数限制",
                description="防止ReAct循环过多迭代",
                type=RuleType.STATIC,
                priority=1,
                condition="iteration_count > 10",
                action=RuleAction.FORCE_TERMINATE,
            )
        )

        # 添加Token预算规则
        engine.add_rule(
            Rule(
                id="token_budget",
                name="Token预算限制",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="token_used > 10000",
                action=RuleAction.FORCE_TERMINATE,
            )
        )

        # 模拟正常执行
        normal_context = {"iteration_count": 5, "token_used": 3000}
        violations = engine.evaluate(normal_context)
        assert len(violations) == 0

        # 模拟迭代过多
        too_many_iterations = {"iteration_count": 15, "token_used": 3000}
        violations = engine.evaluate(too_many_iterations)
        assert len(violations) == 1
        assert violations[0].rule_id == "max_iterations"
        assert violations[0].action == RuleAction.FORCE_TERMINATE

    def test_goal_alignment_monitoring(self):
        """测试：目标对齐监控"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()

        # 目标偏离检测规则
        engine.add_rule(
            Rule(
                id="goal_deviation",
                name="目标偏离检测",
                description="检测对话Agent是否偏离目标",
                type=RuleType.STATIC,
                priority=2,
                condition="alignment_score < 0.5",
                action=RuleAction.SUGGEST_CORRECTION,
            )
        )

        # 低置信度警告
        engine.add_rule(
            Rule(
                id="low_confidence",
                name="低置信度警告",
                description="决策置信度过低时警告",
                type=RuleType.STATIC,
                priority=3,
                condition="decision_confidence < 0.5",
                action=RuleAction.LOG_WARNING,
            )
        )

        # 正常对齐
        aligned_context = {"alignment_score": 0.8, "decision_confidence": 0.9}
        violations = engine.evaluate(aligned_context)
        assert len(violations) == 0

        # 偏离目标
        deviated_context = {"alignment_score": 0.3, "decision_confidence": 0.9}
        violations = engine.evaluate(deviated_context)
        assert len(violations) == 1
        assert violations[0].action == RuleAction.SUGGEST_CORRECTION

    def test_multi_rule_decision_validation(self):
        """测试：多规则决策验证"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()

        # 设置多个验证规则
        engine.add_rule(
            Rule(
                id="format_check",
                name="格式检查",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="not has_valid_format",
                action=RuleAction.REJECT_DECISION,
            )
        )

        engine.add_rule(
            Rule(
                id="permission_check",
                name="权限检查",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="not has_permission",
                action=RuleAction.REJECT_DECISION,
            )
        )

        engine.add_rule(
            Rule(
                id="resource_check",
                name="资源检查",
                description="",
                type=RuleType.STATIC,
                priority=2,
                condition="resource_usage > 0.9",
                action=RuleAction.SUGGEST_CORRECTION,
            )
        )

        # 所有检查通过
        valid_context = {
            "has_valid_format": True,
            "has_permission": True,
            "resource_usage": 0.5,
        }
        violations = engine.evaluate(valid_context)
        assert len(violations) == 0

        # 格式无效
        invalid_format = {
            "has_valid_format": False,
            "has_permission": True,
            "resource_usage": 0.5,
        }
        violations = engine.evaluate(invalid_format)
        assert len(violations) == 1
        assert violations[0].rule_id == "format_check"

    def test_coordinator_agent_integration(self):
        """测试：协调者Agent集成场景"""
        from src.domain.services.rule_engine import (
            Rule,
            RuleAction,
            RuleEngine,
            RuleType,
        )

        engine = RuleEngine()

        # 模拟协调者Agent的完整规则集
        rules = [
            Rule(
                id="iteration_limit",
                name="迭代限制",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="iteration_count > 10",
                action=RuleAction.FORCE_TERMINATE,
            ),
            Rule(
                id="token_limit",
                name="Token限制",
                description="",
                type=RuleType.STATIC,
                priority=1,
                condition="token_used > 10000",
                action=RuleAction.FORCE_TERMINATE,
            ),
            Rule(
                id="goal_alignment",
                name="目标对齐",
                description="",
                type=RuleType.STATIC,
                priority=2,
                condition="alignment_score < 0.5",
                action=RuleAction.SUGGEST_CORRECTION,
            ),
            Rule(
                id="confidence_warning",
                name="置信度警告",
                description="",
                type=RuleType.STATIC,
                priority=3,
                condition="confidence < 0.3",
                action=RuleAction.LOG_WARNING,
            ),
        ]

        for rule in rules:
            engine.add_rule(rule)

        # 模拟决策验证流程
        decision_context = {
            "iteration_count": 5,
            "token_used": 5000,
            "alignment_score": 0.85,
            "confidence": 0.75,
        }

        violations = engine.evaluate(decision_context)

        # 应该没有违规
        assert len(violations) == 0

        # 检查是否需要干预
        should_terminate = any(v.action == RuleAction.FORCE_TERMINATE for v in violations)
        should_suggest = any(v.action == RuleAction.SUGGEST_CORRECTION for v in violations)

        assert not should_terminate
        assert not should_suggest


class TestRuleEngineFactory:
    """规则引擎工厂测试"""

    def test_create_default_engine(self):
        """测试：创建默认引擎"""
        from src.domain.services.rule_engine import RuleEngineFactory

        engine = RuleEngineFactory.create_default()

        assert engine is not None
        # 默认引擎应该有预设规则
        assert len(engine.rules) > 0

    def test_create_engine_with_custom_rules(self):
        """测试：创建自定义规则引擎"""
        from src.domain.services.rule_engine import RuleEngineFactory

        custom_rules = [
            {
                "id": "custom_1",
                "name": "自定义规则1",
                "description": "",
                "type": "static",
                "priority": 1,
                "condition": "x > 0",
                "action": "log_warning",
            }
        ]

        engine = RuleEngineFactory.create_with_rules(custom_rules)

        assert len(engine.rules) == 1
        assert engine.rules[0].id == "custom_1"

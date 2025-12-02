"""增强规则库测试 - Phase 7.1

TDD RED阶段：先写测试，验证需求
"""

import pytest


class TestRuleCategory:
    """规则类别枚举测试"""

    def test_rule_category_should_have_behavior_type(self):
        """规则类别应包含行为边界类型"""
        from src.domain.services.enhanced_rule_repository import RuleCategory

        assert RuleCategory.BEHAVIOR.value == "behavior"

    def test_rule_category_should_have_tool_type(self):
        """规则类别应包含工具约束类型"""
        from src.domain.services.enhanced_rule_repository import RuleCategory

        assert RuleCategory.TOOL.value == "tool"

    def test_rule_category_should_have_data_type(self):
        """规则类别应包含数据访问类型"""
        from src.domain.services.enhanced_rule_repository import RuleCategory

        assert RuleCategory.DATA.value == "data"

    def test_rule_category_should_have_execution_type(self):
        """规则类别应包含执行策略类型"""
        from src.domain.services.enhanced_rule_repository import RuleCategory

        assert RuleCategory.EXECUTION.value == "execution"

    def test_rule_category_should_have_goal_type(self):
        """规则类别应包含目标对齐类型"""
        from src.domain.services.enhanced_rule_repository import RuleCategory

        assert RuleCategory.GOAL.value == "goal"


class TestRuleSource:
    """规则来源枚举测试"""

    def test_rule_source_should_have_user_type(self):
        """规则来源应包含用户定义类型"""
        from src.domain.services.enhanced_rule_repository import RuleSource

        assert RuleSource.USER.value == "user"

    def test_rule_source_should_have_system_type(self):
        """规则来源应包含系统预设类型"""
        from src.domain.services.enhanced_rule_repository import RuleSource

        assert RuleSource.SYSTEM.value == "system"

    def test_rule_source_should_have_tool_type(self):
        """规则来源应包含工具配置类型"""
        from src.domain.services.enhanced_rule_repository import RuleSource

        assert RuleSource.TOOL.value == "tool"

    def test_rule_source_should_have_generated_type(self):
        """规则来源应包含动态生成类型"""
        from src.domain.services.enhanced_rule_repository import RuleSource

        assert RuleSource.GENERATED.value == "generated"


class TestEnhancedRule:
    """增强规则数据类测试"""

    def test_create_enhanced_rule_with_required_fields(self):
        """创建增强规则应包含必需字段"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        rule = EnhancedRule(
            id="rule_1",
            name="最大迭代次数限制",
            category=RuleCategory.BEHAVIOR,
            description="防止ReAct循环过多迭代",
            condition="iteration_count > 10",
            action=RuleAction.FORCE_TERMINATE,
            priority=1,
            source=RuleSource.SYSTEM,
        )

        assert rule.id == "rule_1"
        assert rule.name == "最大迭代次数限制"
        assert rule.category == RuleCategory.BEHAVIOR
        assert rule.priority == 1
        assert rule.source == RuleSource.SYSTEM
        assert rule.enabled is True  # 默认启用

    def test_enhanced_rule_should_support_callable_condition(self):
        """增强规则应支持函数条件"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        def check_token_limit(ctx: dict) -> bool:
            return ctx.get("token_count", 0) > 10000

        rule = EnhancedRule(
            id="rule_2",
            name="Token预算限制",
            category=RuleCategory.BEHAVIOR,
            description="防止单次任务消耗过多token",
            condition=check_token_limit,
            action=RuleAction.FORCE_TERMINATE,
            priority=1,
            source=RuleSource.SYSTEM,
        )

        assert callable(rule.condition)
        assert rule.condition({"token_count": 15000}) is True
        assert rule.condition({"token_count": 5000}) is False

    def test_enhanced_rule_should_have_metadata_for_correction(self):
        """增强规则应包含用于修正的元数据"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        rule = EnhancedRule(
            id="rule_3",
            name="敏感字段过滤",
            category=RuleCategory.DATA,
            description="保护敏感数据",
            condition="'password' in fields",
            action=RuleAction.SUGGEST_CORRECTION,
            priority=2,
            source=RuleSource.SYSTEM,
            metadata={
                "correction_type": "field_filter",
                "sensitive_fields": ["password", "credit_card", "ssn"],
                "suggestion": "请移除敏感字段或使用脱敏处理",
            },
        )

        assert rule.metadata is not None
        assert "sensitive_fields" in rule.metadata
        assert "suggestion" in rule.metadata


class TestEnhancedRuleRepository:
    """增强规则库测试"""

    def test_add_rule_should_store_in_repository(self):
        """添加规则应存储到规则库"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()
        rule = EnhancedRule(
            id="rule_1",
            name="测试规则",
            category=RuleCategory.BEHAVIOR,
            description="测试",
            condition="True",
            action=RuleAction.LOG_WARNING,
            priority=1,
            source=RuleSource.SYSTEM,
        )

        repo.add_rule(rule)

        assert len(repo.get_all_rules()) == 1
        assert repo.get_rule("rule_1") is not None

    def test_add_rule_should_reject_duplicate_id(self):
        """添加重复ID的规则应抛出异常"""
        from src.domain.services.enhanced_rule_repository import (
            DuplicateRuleError,
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()
        rule1 = EnhancedRule(
            id="rule_1",
            name="规则1",
            category=RuleCategory.BEHAVIOR,
            description="",
            condition="True",
            action=RuleAction.LOG_WARNING,
            priority=1,
            source=RuleSource.SYSTEM,
        )
        rule2 = EnhancedRule(
            id="rule_1",  # 重复ID
            name="规则2",
            category=RuleCategory.TOOL,
            description="",
            condition="True",
            action=RuleAction.LOG_WARNING,
            priority=2,
            source=RuleSource.SYSTEM,
        )

        repo.add_rule(rule1)

        with pytest.raises(DuplicateRuleError):
            repo.add_rule(rule2)

    def test_get_rules_by_category_should_return_filtered_rules(self):
        """按类别获取规则应返回过滤后的规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        # 添加不同类别的规则
        repo.add_rule(
            EnhancedRule(
                id="behavior_1",
                name="行为规则1",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )
        repo.add_rule(
            EnhancedRule(
                id="tool_1",
                name="工具规则1",
                category=RuleCategory.TOOL,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )
        repo.add_rule(
            EnhancedRule(
                id="behavior_2",
                name="行为规则2",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=2,
                source=RuleSource.SYSTEM,
            )
        )

        behavior_rules = repo.get_rules_by_category(RuleCategory.BEHAVIOR)

        assert len(behavior_rules) == 2
        assert all(r.category == RuleCategory.BEHAVIOR for r in behavior_rules)

    def test_get_rules_by_category_should_return_sorted_by_priority(self):
        """按类别获取规则应按优先级排序"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        repo.add_rule(
            EnhancedRule(
                id="rule_low",
                name="低优先级",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=10,
                source=RuleSource.SYSTEM,
            )
        )
        repo.add_rule(
            EnhancedRule(
                id="rule_high",
                name="高优先级",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )
        repo.add_rule(
            EnhancedRule(
                id="rule_mid",
                name="中优先级",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=5,
                source=RuleSource.SYSTEM,
            )
        )

        rules = repo.get_rules_by_category(RuleCategory.BEHAVIOR)

        assert rules[0].id == "rule_high"
        assert rules[1].id == "rule_mid"
        assert rules[2].id == "rule_low"

    def test_get_rules_by_source_should_return_filtered_rules(self):
        """按来源获取规则应返回过滤后的规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        repo.add_rule(
            EnhancedRule(
                id="system_1",
                name="系统规则",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )
        repo.add_rule(
            EnhancedRule(
                id="user_1",
                name="用户规则",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.USER,
            )
        )

        system_rules = repo.get_rules_by_source(RuleSource.SYSTEM)
        user_rules = repo.get_rules_by_source(RuleSource.USER)

        assert len(system_rules) == 1
        assert system_rules[0].id == "system_1"
        assert len(user_rules) == 1
        assert user_rules[0].id == "user_1"

    def test_remove_rule_should_delete_from_repository(self):
        """移除规则应从规则库删除"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()
        rule = EnhancedRule(
            id="rule_1",
            name="测试规则",
            category=RuleCategory.BEHAVIOR,
            description="",
            condition="True",
            action=RuleAction.LOG_WARNING,
            priority=1,
            source=RuleSource.SYSTEM,
        )

        repo.add_rule(rule)
        result = repo.remove_rule("rule_1")

        assert result is True
        assert repo.get_rule("rule_1") is None

    def test_remove_nonexistent_rule_should_return_false(self):
        """移除不存在的规则应返回False"""
        from src.domain.services.enhanced_rule_repository import EnhancedRuleRepository

        repo = EnhancedRuleRepository()

        result = repo.remove_rule("nonexistent")

        assert result is False

    def test_update_rule_should_modify_existing_rule(self):
        """更新规则应修改现有规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()
        rule = EnhancedRule(
            id="rule_1",
            name="原始名称",
            category=RuleCategory.BEHAVIOR,
            description="原始描述",
            condition="True",
            action=RuleAction.LOG_WARNING,
            priority=1,
            source=RuleSource.SYSTEM,
        )

        repo.add_rule(rule)
        result = repo.update_rule(
            "rule_1",
            name="新名称",
            priority=5,
            enabled=False,
        )

        assert result is True
        updated = repo.get_rule("rule_1")
        assert updated.name == "新名称"
        assert updated.priority == 5
        assert updated.enabled is False

    def test_get_enabled_rules_should_filter_disabled(self):
        """获取启用规则应过滤禁用的规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        repo.add_rule(
            EnhancedRule(
                id="enabled_1",
                name="启用规则",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
                enabled=True,
            )
        )
        repo.add_rule(
            EnhancedRule(
                id="disabled_1",
                name="禁用规则",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
                enabled=False,
            )
        )

        enabled_rules = repo.get_enabled_rules()

        assert len(enabled_rules) == 1
        assert enabled_rules[0].id == "enabled_1"

    def test_clear_rules_should_remove_all(self):
        """清空规则应移除所有规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        for i in range(5):
            repo.add_rule(
                EnhancedRule(
                    id=f"rule_{i}",
                    name=f"规则{i}",
                    category=RuleCategory.BEHAVIOR,
                    description="",
                    condition="True",
                    action=RuleAction.LOG_WARNING,
                    priority=i,
                    source=RuleSource.SYSTEM,
                )
            )

        repo.clear()

        assert len(repo.get_all_rules()) == 0

    def test_load_default_rules_should_add_system_rules(self):
        """加载默认规则应添加系统预设规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )

        repo = EnhancedRuleRepository()
        repo.load_default_rules()

        all_rules = repo.get_all_rules()
        system_rules = repo.get_rules_by_source(RuleSource.SYSTEM)

        # 应该有预设的系统规则
        assert len(all_rules) > 0
        assert len(system_rules) > 0

        # 应该包含基本的行为边界规则
        behavior_rules = repo.get_rules_by_category(RuleCategory.BEHAVIOR)
        assert any("迭代" in r.name or "iteration" in r.name.lower() for r in behavior_rules)


class TestEnhancedRuleRepositoryEvaluation:
    """增强规则库评估功能测试"""

    def test_evaluate_should_return_violations_for_matching_rules(self):
        """评估应返回匹配规则的违规列表"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        repo.add_rule(
            EnhancedRule(
                id="max_iter",
                name="最大迭代次数",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="iteration_count > 10",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )

        violations = repo.evaluate({"iteration_count": 15})

        assert len(violations) == 1
        assert violations[0].rule_id == "max_iter"

    def test_evaluate_should_support_callable_condition(self):
        """评估应支持函数条件"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        def check_tool_allowed(ctx: dict) -> bool:
            allowed_tools = ctx.get("allowed_tools", [])
            requested_tool = ctx.get("requested_tool", "")
            return requested_tool not in allowed_tools

        repo.add_rule(
            EnhancedRule(
                id="tool_check",
                name="工具权限检查",
                category=RuleCategory.TOOL,
                description="",
                condition=check_tool_allowed,
                action=RuleAction.REJECT_DECISION,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )

        violations = repo.evaluate(
            {"allowed_tools": ["database", "http"], "requested_tool": "shell"}
        )

        assert len(violations) == 1
        assert violations[0].rule_id == "tool_check"

    def test_evaluate_should_only_check_enabled_rules(self):
        """评估应只检查启用的规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        repo.add_rule(
            EnhancedRule(
                id="disabled_rule",
                name="禁用规则",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",  # 总是触发
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.SYSTEM,
                enabled=False,
            )
        )

        violations = repo.evaluate({})

        assert len(violations) == 0

    def test_evaluate_by_category_should_only_check_specified_category(self):
        """按类别评估应只检查指定类别的规则"""
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        repo.add_rule(
            EnhancedRule(
                id="behavior_rule",
                name="行为规则",
                category=RuleCategory.BEHAVIOR,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )
        repo.add_rule(
            EnhancedRule(
                id="tool_rule",
                name="工具规则",
                category=RuleCategory.TOOL,
                description="",
                condition="True",
                action=RuleAction.LOG_WARNING,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )

        violations = repo.evaluate_by_category({}, RuleCategory.TOOL)

        assert len(violations) == 1
        assert violations[0].rule_id == "tool_rule"

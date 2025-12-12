"""PayloadRuleBuilder 单元测试 - Phase 35.2

TDD Red Phase: 测试 PayloadRuleBuilder 的4个构建方法
"""

import pytest

from src.domain.services.safety_guard.payload_rule_builder import PayloadRuleBuilder
from src.domain.services.safety_guard.rules import Rule


@pytest.fixture
def builder():
    """PayloadRuleBuilder fixture"""
    return PayloadRuleBuilder()


class TestBuildRequiredFieldsRule:
    """测试：构建必填字段验证规则"""

    def test_build_required_fields_rule_returns_rule(self, builder):
        """测试：返回Rule对象"""
        rule = builder.build_required_fields_rule(
            decision_type="test_action",
            required_fields=["field1", "field2"],
        )

        assert isinstance(rule, Rule)
        assert rule.id == "payload_required_test_action"
        assert "必填字段验证" in rule.name

    def test_required_fields_rule_passes_when_all_fields_present(self, builder):
        """测试：所有必填字段存在时通过"""
        rule = builder.build_required_fields_rule(
            decision_type="test_action",
            required_fields=["field1", "field2"],
        )

        decision = {
            "action_type": "test_action",
            "field1": "value1",
            "field2": "value2",
        }

        assert rule.condition(decision) is True

    def test_required_fields_rule_fails_when_fields_missing(self, builder):
        """测试：缺少必填字段时失败"""
        rule = builder.build_required_fields_rule(
            decision_type="test_action",
            required_fields=["field1", "field2"],
        )

        decision = {
            "action_type": "test_action",
            "field1": "value1",
            # field2 缺失
        }

        assert rule.condition(decision) is False
        assert "_missing_fields" in decision
        assert "field2" in decision["_missing_fields"]

    def test_required_fields_rule_fails_when_fields_empty(self, builder):
        """测试：字段为空列表/字典时失败（Phase 8.4增强）"""
        rule = builder.build_required_fields_rule(
            decision_type="test_action",
            required_fields=["nodes", "config"],
        )

        decision = {
            "action_type": "test_action",
            "nodes": [],  # 空列表
            "config": {},  # 空字典
        }

        assert rule.condition(decision) is False
        assert "_missing_fields" in decision
        assert "nodes" in decision["_missing_fields"]
        assert "config" in decision["_missing_fields"]

    def test_required_fields_rule_skips_other_decision_types(self, builder):
        """测试：不匹配的决策类型跳过验证"""
        rule = builder.build_required_fields_rule(
            decision_type="test_action",
            required_fields=["field1"],
        )

        decision = {
            "action_type": "other_action",
            # field1 缺失，但不会被检查
        }

        assert rule.condition(decision) is True


class TestBuildTypeValidationRule:
    """测试：构建类型验证规则"""

    def test_build_type_validation_rule_returns_rule(self, builder):
        """测试：返回Rule对象"""
        rule = builder.build_type_validation_rule(
            decision_type="test_action",
            field_types={"field1": str},
        )

        assert isinstance(rule, Rule)
        assert rule.id == "payload_type_test_action"

    def test_type_validation_rule_passes_correct_types(self, builder):
        """测试：类型正确时通过"""
        rule = builder.build_type_validation_rule(
            decision_type="test_action",
            field_types={"field1": str, "field2": int},
        )

        decision = {
            "action_type": "test_action",
            "field1": "text",
            "field2": 42,
        }

        assert rule.condition(decision) is True

    def test_type_validation_rule_fails_wrong_types(self, builder):
        """测试：类型错误时失败"""
        rule = builder.build_type_validation_rule(
            decision_type="test_action",
            field_types={"field1": str, "field2": int},
        )

        decision = {
            "action_type": "test_action",
            "field1": "text",
            "field2": "not_an_int",
        }

        assert rule.condition(decision) is False
        assert "_type_errors" in decision

    def test_type_validation_rule_supports_union_types(self, builder):
        """测试：支持联合类型（tuple表示或运算）"""
        rule = builder.build_type_validation_rule(
            decision_type="test_action",
            field_types={"field1": (str, int)},
        )

        decision1 = {"action_type": "test_action", "field1": "text"}
        decision2 = {"action_type": "test_action", "field1": 42}
        decision3 = {"action_type": "test_action", "field1": []}

        assert rule.condition(decision1) is True
        assert rule.condition(decision2) is True
        assert rule.condition(decision3) is False

    def test_type_validation_rule_supports_nested_fields(self, builder):
        """测试：支持嵌套字段类型验证"""
        rule = builder.build_type_validation_rule(
            decision_type="test_action",
            field_types={},
            nested_field_types={"config.timeout": int},
        )

        decision = {
            "action_type": "test_action",
            "config": {"timeout": 30},
        }

        assert rule.condition(decision) is True

        # 嵌套字段类型错误
        decision["config"]["timeout"] = "30"
        assert rule.condition(decision) is False


class TestBuildRangeValidationRule:
    """测试：构建范围验证规则"""

    def test_build_range_validation_rule_returns_rule(self, builder):
        """测试：返回Rule对象"""
        rule = builder.build_range_validation_rule(
            decision_type="test_action",
            field_ranges={"field1": {"min": 0, "max": 100}},
        )

        assert isinstance(rule, Rule)
        assert rule.id == "payload_range_test_action"

    def test_range_validation_rule_passes_in_range(self, builder):
        """测试：值在范围内时通过"""
        rule = builder.build_range_validation_rule(
            decision_type="test_action",
            field_ranges={"field1": {"min": 0, "max": 100}},
        )

        decision = {"action_type": "test_action", "field1": 50}

        assert rule.condition(decision) is True

    def test_range_validation_rule_fails_out_of_range(self, builder):
        """测试：值超出范围时失败"""
        rule = builder.build_range_validation_rule(
            decision_type="test_action",
            field_ranges={"field1": {"min": 0, "max": 100}},
        )

        decision = {"action_type": "test_action", "field1": 150}

        assert rule.condition(decision) is False
        assert "_range_errors" in decision

    def test_range_validation_rule_supports_min_only(self, builder):
        """测试：支持仅最小值验证"""
        rule = builder.build_range_validation_rule(
            decision_type="test_action",
            field_ranges={"field1": {"min": 0}},
        )

        assert rule.condition({"action_type": "test_action", "field1": 50}) is True
        assert rule.condition({"action_type": "test_action", "field1": -10}) is False

    def test_range_validation_rule_supports_max_only(self, builder):
        """测试：支持仅最大值验证"""
        rule = builder.build_range_validation_rule(
            decision_type="test_action",
            field_ranges={"field1": {"max": 100}},
        )

        assert rule.condition({"action_type": "test_action", "field1": 50}) is True
        assert rule.condition({"action_type": "test_action", "field1": 150}) is False


class TestBuildEnumValidationRule:
    """测试：构建枚举值验证规则"""

    def test_build_enum_validation_rule_returns_rule(self, builder):
        """测试：返回Rule对象"""
        rule = builder.build_enum_validation_rule(
            decision_type="test_action",
            field_enums={"method": ["GET", "POST", "PUT"]},
        )

        assert isinstance(rule, Rule)
        assert rule.id == "payload_enum_test_action"

    def test_enum_validation_rule_passes_valid_value(self, builder):
        """测试：值在枚举列表中时通过"""
        rule = builder.build_enum_validation_rule(
            decision_type="test_action",
            field_enums={"method": ["GET", "POST", "PUT"]},
        )

        decision = {"action_type": "test_action", "method": "GET"}

        assert rule.condition(decision) is True

    def test_enum_validation_rule_fails_invalid_value(self, builder):
        """测试：值不在枚举列表中时失败"""
        rule = builder.build_enum_validation_rule(
            decision_type="test_action",
            field_enums={"method": ["GET", "POST", "PUT"]},
        )

        decision = {"action_type": "test_action", "method": "DELETE"}

        assert rule.condition(decision) is False
        assert "_enum_errors" in decision

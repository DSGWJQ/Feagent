"""ExpressionEvaluator 增强功能测试

业务场景：
- 支持多层上下文（item/context/workflow_vars/global_vars）
- 支持返回值表达式（非布尔，用于Map操作）
- 支持安全/高级模式切换

测试策略：
- 测试多层上下文优先级
- 测试返回值表达式
- 测试安全模式限制
- 测试高级模式受限函数
- 测试向后兼容性
"""

import pytest

from src.domain.services.expression_evaluator import (
    ExpressionEvaluator,
    UnsafeExpressionError,
)


class TestMultiLayerContext:
    """多层上下文测试"""

    def setup_method(self):
        """测试前设置"""
        self.evaluator = ExpressionEvaluator()

    def test_context_only(self):
        """测试仅使用context"""
        result = self.evaluator.evaluate("score > 0.8", {"score": 0.9})
        assert result is True

    def test_workflow_vars_fallback(self):
        """测试workflow_vars作为降级上下文"""
        result = self.evaluator.evaluate("threshold > 0.5", {}, workflow_vars={"threshold": 0.7})
        assert result is True

    def test_global_vars_lowest_priority(self):
        """测试global_vars优先级最低"""
        result = self.evaluator.evaluate(
            "value == 3", {"value": 3}, workflow_vars={"value": 2}, global_vars={"value": 1}
        )
        assert result is True

    def test_item_highest_priority(self):
        """测试item优先级最高（覆盖其他层）"""
        result = self.evaluator.evaluate(
            "price > 100", {"price": 50}, workflow_vars={"price": 75}, item={"price": 150}
        )
        assert result is True

    def test_item_as_scalar(self):
        """测试item为标量时映射到特殊键"""
        result = self.evaluator.evaluate("item > 10", {}, item=15)
        assert result is True

        # 同时支持value和current别名
        result = self.evaluator.evaluate("value > 10", {}, item=15)
        assert result is True

        result = self.evaluator.evaluate("current > 10", {}, item=15)
        assert result is True


class TestReturnValueExpression:
    """返回值表达式测试（用于Map操作）"""

    def setup_method(self):
        """测试前设置"""
        self.evaluator = ExpressionEvaluator()

    def test_evaluate_expression_returns_number(self):
        """测试返回数值"""
        result = self.evaluator.evaluate_expression("price * 0.9", {"price": 100})
        assert result == 90.0

    def test_evaluate_expression_returns_string(self):
        """测试返回字符串"""
        result = self.evaluator.evaluate_expression("name + '_processed'", {"name": "order"})
        assert result == "order_processed"

    def test_evaluate_expression_returns_bool(self):
        """测试返回布尔值"""
        result = self.evaluator.evaluate_expression("score > 0.8", {"score": 0.9})
        assert result is True

    def test_evaluate_expression_with_dict_access(self):
        """测试字典访问返回值"""
        result = self.evaluator.evaluate_expression("user['age'] * 2", {"user": {"age": 25}})
        assert result == 50


class TestSafeMode:
    """安全模式测试（默认）"""

    def setup_method(self):
        """测试前设置"""
        self.evaluator = ExpressionEvaluator(mode="safe")

    def test_safe_mode_allows_basic_operations(self):
        """测试安全模式允许基础操作"""
        # 算术运算
        result = self.evaluator.evaluate("10 + 5 > 12", {})
        assert result is True

        # 比较运算
        result = self.evaluator.evaluate("'hello' == 'hello'", {})
        assert result is True

        # 逻辑运算
        result = self.evaluator.evaluate("True and False", {})
        assert result is False

    def test_safe_mode_blocks_function_calls(self):
        """测试安全模式禁止函数调用"""
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("len([1,2,3]) > 2", {})

        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("str(123) == '123'", {})

    def test_safe_mode_blocks_import(self):
        """测试安全模式禁止import"""
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("os.path.exists('/tmp')", {})


class TestAdvancedMode:
    """高级模式测试"""

    def setup_method(self):
        """测试前设置"""
        self.evaluator = ExpressionEvaluator(mode="advanced")

    def test_advanced_mode_allows_len(self):
        """测试高级模式允许len函数"""
        result = self.evaluator.evaluate("len(items) > 2", {"items": [1, 2, 3]})
        assert result is True

    def test_advanced_mode_allows_str_conversion(self):
        """测试高级模式允许str转换"""
        result = self.evaluator.evaluate_expression("str(value) + '_suffix'", {"value": 123})
        assert result == "123_suffix"

    def test_advanced_mode_allows_math_functions(self):
        """测试高级模式允许math函数"""
        result = self.evaluator.evaluate_expression("sqrt(value)", {"value": 16})
        assert result == 4.0

        result = self.evaluator.evaluate_expression("ceil(price)", {"price": 10.3})
        assert result == 11

    def test_advanced_mode_allows_min_max(self):
        """测试高级模式允许min/max"""
        result = self.evaluator.evaluate_expression("max(a, b)", {"a": 10, "b": 20})
        assert result == 20

        result = self.evaluator.evaluate_expression("min(prices)", {"prices": [100, 200, 50]})
        assert result == 50

    def test_advanced_mode_still_blocks_dangerous_functions(self):
        """测试高级模式仍禁止危险函数"""
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("open('/etc/passwd')", {})

        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("eval('1+1')", {})

    def test_advanced_mode_blocks_excessive_args(self):
        """测试高级模式禁止过多参数"""
        with pytest.raises(UnsafeExpressionError, match="函数参数过多"):
            self.evaluator.evaluate("max(1,2,3,4,5,6,7,8)", {})


class TestModeOverride:
    """模式覆盖测试"""

    def test_instance_mode_can_be_overridden(self):
        """测试实例模式可被调用时覆盖"""
        evaluator = ExpressionEvaluator(mode="safe")

        # 默认safe模式禁止函数调用
        with pytest.raises(UnsafeExpressionError):
            evaluator.evaluate("len([1,2,3]) > 2", {})

        # 调用时覆盖为advanced模式
        result = evaluator.evaluate("len(items) > 2", {"items": [1, 2, 3]}, mode="advanced")
        assert result is True


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_old_signature_still_works(self):
        """测试原有签名仍然有效"""
        evaluator = ExpressionEvaluator()

        # 原有用法：仅传expression和context
        result = evaluator.evaluate("score > 0.8", {"score": 0.9})
        assert result is True

    def test_evaluate_always_returns_bool(self):
        """测试evaluate方法总是返回布尔值"""
        evaluator = ExpressionEvaluator()

        # 即使表达式返回数值，evaluate也转换为布尔
        result = evaluator.evaluate("10 + 5", {})
        assert result is True
        assert isinstance(result, bool)

        result = evaluator.evaluate("0", {})
        assert result is False
        assert isinstance(result, bool)

    def test_empty_expression_returns_false(self):
        """测试空表达式返回False（保持原有行为）"""
        evaluator = ExpressionEvaluator()

        assert evaluator.evaluate("", {}) is False
        assert evaluator.evaluate("   ", {}) is False
        assert evaluator.evaluate(None, {}) is False


class TestSecurityRegression:
    """安全回归测试（防止函数劫持和可变参数绕过）"""

    def test_cannot_hijack_whitelisted_functions_in_advanced_mode(self):
        """测试不能通过上下文劫持白名单函数"""
        import os

        evaluator = ExpressionEvaluator(mode="advanced")

        # 尝试通过item劫持len函数
        malicious_item = {"len": os.system, "data": [1, 2, 3]}

        # 即使item中有len，也应该使用内置的len
        result = evaluator.evaluate_expression("len(data)", {}, item=malicious_item)
        # 应该返回3（正常的len函数），而不是执行os.system
        assert result == 3

    def test_cannot_use_kwargs_in_advanced_mode(self):
        """测试不能使用**kwargs可变参数"""
        evaluator = ExpressionEvaluator(mode="advanced")

        # Python 3.11+ 语法：max(**data)
        with pytest.raises(UnsafeExpressionError, match="不允许使用.*kwargs"):
            evaluator.evaluate("max(a=1, b=2, **other)", {"other": {"c": 3}})

    def test_cannot_use_star_args_in_advanced_mode(self):
        """测试不能使用*args可变参数"""
        evaluator = ExpressionEvaluator(mode="advanced")

        with pytest.raises(UnsafeExpressionError, match="不允许使用.*args"):
            evaluator.evaluate("max(*numbers)", {"numbers": [1, 2, 3]})


class TestComplexScenarios:
    """复杂场景测试"""

    def test_map_transformation_with_item(self):
        """测试Map转换场景（结合item和表达式求值）"""
        evaluator = ExpressionEvaluator(mode="advanced")

        # 模拟Map操作：price * discount
        items = [
            {"price": 100, "discount": 0.9},
            {"price": 200, "discount": 0.8},
            {"price": 50, "discount": 0.95},
        ]

        transformed = []
        for item in items:
            result = evaluator.evaluate_expression("price * discount", {}, item=item)
            transformed.append(result)

        assert transformed == [90.0, 160.0, 47.5]

    def test_filter_with_workflow_context(self):
        """测试Filter场景（结合工作流上下文）"""
        evaluator = ExpressionEvaluator()

        workflow_vars = {"min_quality": 0.8}
        items = [
            {"quality": 0.9},
            {"quality": 0.7},
            {"quality": 0.85},
        ]

        filtered = []
        for item in items:
            if evaluator.evaluate(
                "quality >= min_quality", {}, workflow_vars=workflow_vars, item=item
            ):
                filtered.append(item)

        assert len(filtered) == 2
        assert filtered[0]["quality"] == 0.9
        assert filtered[1]["quality"] == 0.85

    def test_conditional_branch_with_multilayer_context(self):
        """测试条件分支场景（多层上下文）"""
        evaluator = ExpressionEvaluator()

        # 全局配置
        global_vars = {"default_threshold": 0.5}

        # 工作流配置
        workflow_vars = {"quality_threshold": 0.8}

        # 节点输出
        node_output = {"data_quality": 0.85}

        # 条件：data_quality >= quality_threshold
        result = evaluator.evaluate(
            "data_quality >= quality_threshold",
            node_output,
            workflow_vars=workflow_vars,
            global_vars=global_vars,
        )

        assert result is True

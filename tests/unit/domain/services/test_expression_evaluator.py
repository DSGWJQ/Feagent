"""ExpressionEvaluator 单元测试

业务场景：
- 工作流条件分支需要评估表达式（如: quality_score > 0.8）
- 表达式基于节点输出或全局上下文变量
- 需要安全评估，防止代码注入

测试策略：
- 测试简单比较表达式（>, <, ==, !=）
- 测试逻辑表达式（and, or, not）
- 测试字段访问（node.output.field）
- 测试安全性（拒绝危险操作）
- 测试边界情况（空值、类型错误）
"""

import pytest

from src.domain.services.expression_evaluator import (
    ExpressionEvaluator,
    ExpressionEvaluationError,
    UnsafeExpressionError,
)


class TestExpressionEvaluator:
    """ExpressionEvaluator 测试套件"""

    def setup_method(self):
        """每个测试前的设置"""
        self.evaluator = ExpressionEvaluator()

    # ==================== 基础比较表达式 ====================

    def test_simple_greater_than_true(self):
        """测试简单的大于比较 - 结果为True"""
        context = {"score": 0.9}
        result = self.evaluator.evaluate("score > 0.8", context)
        assert result is True

    def test_simple_greater_than_false(self):
        """测试简单的大于比较 - 结果为False"""
        context = {"score": 0.7}
        result = self.evaluator.evaluate("score > 0.8", context)
        assert result is False

    def test_simple_less_than(self):
        """测试小于比较"""
        context = {"error_rate": 0.01}
        result = self.evaluator.evaluate("error_rate < 0.05", context)
        assert result is True

    def test_simple_equal(self):
        """测试相等比较"""
        context = {"status": "completed"}
        result = self.evaluator.evaluate("status == 'completed'", context)
        assert result is True

    def test_simple_not_equal(self):
        """测试不等比较"""
        context = {"status": "failed"}
        result = self.evaluator.evaluate("status != 'completed'", context)
        assert result is True

    # ==================== 字段访问 ====================

    def test_nested_field_access(self):
        """测试嵌套字段访问"""
        context = {
            "node_output": {
                "result": {
                    "quality_score": 0.95
                }
            }
        }
        result = self.evaluator.evaluate("node_output['result']['quality_score'] > 0.9", context)
        assert result is True

    def test_dot_notation_field_access(self):
        """测试点号字段访问（如果支持）"""
        context = {
            "node_output": {
                "quality_score": 0.95
            }
        }
        # 使用字典访问语法
        result = self.evaluator.evaluate("node_output['quality_score'] > 0.9", context)
        assert result is True

    # ==================== 逻辑表达式 ====================

    def test_logical_and_true(self):
        """测试逻辑AND - 结果为True"""
        context = {"score": 0.9, "count": 100}
        result = self.evaluator.evaluate("score > 0.8 and count >= 100", context)
        assert result is True

    def test_logical_and_false(self):
        """测试逻辑AND - 结果为False"""
        context = {"score": 0.9, "count": 50}
        result = self.evaluator.evaluate("score > 0.8 and count >= 100", context)
        assert result is False

    def test_logical_or_true(self):
        """测试逻辑OR - 结果为True"""
        context = {"score": 0.7, "priority": "high"}
        result = self.evaluator.evaluate("score > 0.8 or priority == 'high'", context)
        assert result is True

    def test_logical_not(self):
        """测试逻辑NOT"""
        context = {"is_valid": False}
        result = self.evaluator.evaluate("not is_valid", context)
        assert result is True

    def test_complex_logical_expression(self):
        """测试复杂逻辑表达式"""
        context = {"score": 0.85, "count": 120, "status": "completed"}
        result = self.evaluator.evaluate(
            "(score > 0.8 and count > 100) or status == 'completed'",
            context
        )
        assert result is True

    # ==================== 类型检查 ====================

    def test_numeric_comparison(self):
        """测试数值比较"""
        context = {"value": 42}
        assert self.evaluator.evaluate("value == 42", context) is True
        assert self.evaluator.evaluate("value > 40", context) is True
        assert self.evaluator.evaluate("value < 50", context) is True

    def test_string_comparison(self):
        """测试字符串比较"""
        context = {"name": "test"}
        assert self.evaluator.evaluate("name == 'test'", context) is True
        assert self.evaluator.evaluate("name != 'prod'", context) is True

    def test_boolean_comparison(self):
        """测试布尔值比较"""
        context = {"is_enabled": True}
        assert self.evaluator.evaluate("is_enabled == True", context) is True
        assert self.evaluator.evaluate("is_enabled", context) is True

    # ==================== 边界情况 ====================

    def test_missing_variable_raises_error(self):
        """测试缺失变量抛出异常"""
        context = {"score": 0.9}
        with pytest.raises(ExpressionEvaluationError) as exc_info:
            self.evaluator.evaluate("unknown_var > 0.8", context)
        assert "unknown_var" in str(exc_info.value).lower() or "name" in str(exc_info.value).lower()

    def test_empty_expression_returns_false(self):
        """测试空表达式返回False"""
        context = {}
        result = self.evaluator.evaluate("", context)
        assert result is False

    def test_none_expression_returns_false(self):
        """测试None表达式返回False"""
        context = {}
        result = self.evaluator.evaluate(None, context)
        assert result is False

    def test_empty_context_with_literal_expression(self):
        """测试空上下文与字面量表达式"""
        context = {}
        result = self.evaluator.evaluate("True", context)
        assert result is True

    def test_invalid_syntax_raises_error(self):
        """测试无效语法抛出异常"""
        context = {"score": 0.9}
        with pytest.raises(ExpressionEvaluationError):
            self.evaluator.evaluate("score > > 0.8", context)

    # ==================== 安全性测试 ====================

    def test_reject_import_statement(self):
        """测试拒绝import语句"""
        context = {}
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("import os", context)

    def test_reject_exec_call(self):
        """测试拒绝exec调用"""
        context = {}
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("exec('print(1)')", context)

    def test_reject_eval_call(self):
        """测试拒绝eval调用"""
        context = {}
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("eval('1+1')", context)

    def test_reject_file_operations(self):
        """测试拒绝文件操作"""
        context = {}
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("open('/etc/passwd')", context)

    def test_reject_dunder_methods(self):
        """测试拒绝双下划线方法"""
        context = {"obj": {}}
        with pytest.raises(UnsafeExpressionError):
            self.evaluator.evaluate("obj.__class__", context)

    # ==================== 性能测试 ====================

    def test_expression_caching(self):
        """测试表达式缓存（如果实现）"""
        context = {"score": 0.9}
        expr = "score > 0.8"

        # 多次评估同一表达式
        result1 = self.evaluator.evaluate(expr, context)
        result2 = self.evaluator.evaluate(expr, context)
        result3 = self.evaluator.evaluate(expr, context)

        assert result1 == result2 == result3 == True

    # ==================== 实际工作流场景 ====================

    def test_workflow_quality_check_scenario(self):
        """测试工作流质量检查场景

        场景：数据质量评分 > 0.8 则直接分析，否则需要清洗
        """
        # 高质量数据
        high_quality_context = {
            "data_quality_score": 0.95,
            "completeness": 0.98,
            "accuracy": 0.97
        }
        result = self.evaluator.evaluate(
            "data_quality_score > 0.8 and completeness > 0.9",
            high_quality_context
        )
        assert result is True  # 应该直接分析

        # 低质量数据
        low_quality_context = {
            "data_quality_score": 0.65,
            "completeness": 0.85,
            "accuracy": 0.70
        }
        result = self.evaluator.evaluate(
            "data_quality_score > 0.8 and completeness > 0.9",
            low_quality_context
        )
        assert result is False  # 需要清洗

    def test_workflow_error_handling_scenario(self):
        """测试工作流错误处理场景

        场景：错误率 < 5% 继续执行，否则终止
        """
        context = {
            "error_count": 3,
            "total_count": 100
        }
        # 计算错误率
        context["error_rate"] = context["error_count"] / context["total_count"]

        result = self.evaluator.evaluate("error_rate < 0.05", context)
        assert result is True  # 应该继续执行

    def test_workflow_multi_condition_routing(self):
        """测试工作流多条件路由场景

        场景：根据优先级和状态决定执行路径
        """
        # 高优先级且待处理
        context1 = {"priority": "high", "status": "pending"}
        result1 = self.evaluator.evaluate(
            "priority == 'high' and status == 'pending'",
            context1
        )
        assert result1 is True

        # 低优先级或已完成
        context2 = {"priority": "low", "status": "completed"}
        result2 = self.evaluator.evaluate(
            "priority == 'high' and status == 'pending'",
            context2
        )
        assert result2 is False


class TestExpressionEvaluatorWithNodeOutputs:
    """测试ExpressionEvaluator与节点输出的集成"""

    def setup_method(self):
        self.evaluator = ExpressionEvaluator()

    def test_evaluate_with_node_output_structure(self):
        """测试评估包含节点输出结构的表达式"""
        # 模拟工作流上下文：包含多个节点的输出
        context = {
            "node_a_output": {
                "score": 0.95,
                "count": 150
            },
            "node_b_output": {
                "status": "completed",
                "errors": []
            }
        }

        # 测试基于node_a输出的条件
        result = self.evaluator.evaluate(
            "node_a_output['score'] > 0.9 and node_a_output['count'] > 100",
            context
        )
        assert result is True

        # 测试基于node_b输出的条件
        result = self.evaluator.evaluate(
            "node_b_output['status'] == 'completed'",
            context
        )
        assert result is True

    def test_evaluate_cross_node_conditions(self):
        """测试跨节点条件评估"""
        context = {
            "validation_output": {
                "is_valid": True,
                "confidence": 0.92
            },
            "processing_output": {
                "result_count": 120
            }
        }

        # 跨节点条件：验证通过且结果数量充足
        result = self.evaluator.evaluate(
            "validation_output['is_valid'] and processing_output['result_count'] > 100",
            context
        )
        assert result is True

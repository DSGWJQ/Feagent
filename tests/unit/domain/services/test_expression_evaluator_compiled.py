"""
测试 ExpressionEvaluator 编译与复用功能

Priority 2: ExpressionEvaluator 增强
- compile_expression() - 预编译表达式为 AST
- evaluate_compiled() - 执行编译后的表达式
- resolve_variables() - 扁平化嵌套字典
"""

import ast

import pytest

from src.domain.services.expression_evaluator import (
    ExpressionEvaluationError,
    ExpressionEvaluator,
)


class TestCompileExpression:
    """测试 compile_expression 方法"""

    def test_compile_expression_returns_ast(self):
        """测试 compile_expression 返回 AST 节点"""
        evaluator = ExpressionEvaluator()
        expression = "score > 0.8"

        compiled = evaluator.compile_expression(expression)

        assert isinstance(compiled, ast.Expression)
        assert compiled.body is not None

    def test_compile_expression_caches_result(self):
        """测试 compile_expression 缓存编译结果"""
        evaluator = ExpressionEvaluator()
        expression = "count >= 100"

        # 第一次编译
        compiled1 = evaluator.compile_expression(expression)
        # 第二次应该返回缓存的结果
        compiled2 = evaluator.compile_expression(expression)

        assert compiled1 is compiled2  # 应该是同一个对象

    def test_compile_expression_invalid_syntax(self):
        """测试 compile_expression 处理语法错误"""
        evaluator = ExpressionEvaluator()
        expression = "invalid syntax !!!"

        with pytest.raises(ExpressionEvaluationError):
            evaluator.compile_expression(expression)

    def test_compile_expression_dangerous_keywords(self):
        """测试 compile_expression 检测危险关键字"""
        evaluator = ExpressionEvaluator()
        expression = "import os"

        with pytest.raises(ExpressionEvaluationError):
            evaluator.compile_expression(expression)


class TestEvaluateCompiled:
    """测试 evaluate_compiled 方法"""

    def test_evaluate_compiled_simple_comparison(self):
        """测试 evaluate_compiled 执行简单比较"""
        evaluator = ExpressionEvaluator()
        compiled = evaluator.compile_expression("score > 0.8")

        result = evaluator.evaluate_compiled(compiled_ast=compiled, context={"score": 0.9})

        assert result is True

    def test_evaluate_compiled_with_workflow_vars(self):
        """测试 evaluate_compiled 支持工作流变量"""
        evaluator = ExpressionEvaluator()
        compiled = evaluator.compile_expression("score > threshold")

        result = evaluator.evaluate_compiled(
            compiled_ast=compiled,
            context={"score": 0.85},
            workflow_vars={"threshold": 0.8},
        )

        assert result is True

    def test_evaluate_compiled_with_global_vars(self):
        """测试 evaluate_compiled 支持全局变量"""
        evaluator = ExpressionEvaluator()
        compiled = evaluator.compile_expression("count >= min_count")

        result = evaluator.evaluate_compiled(
            compiled_ast=compiled,
            context={"count": 150},
            global_vars={"min_count": 100},
        )

        assert result is True

    def test_evaluate_compiled_reuse_performance(self):
        """测试 evaluate_compiled 复用编译结果的性能优势"""
        evaluator = ExpressionEvaluator()
        compiled = evaluator.compile_expression("value * 2 > 100")

        # 多次执行同一个编译后的表达式
        results = []
        for value in [40, 50, 60]:
            result = evaluator.evaluate_compiled(compiled_ast=compiled, context={"value": value})
            results.append(result)

        assert results == [False, False, True]

    def test_evaluate_compiled_returns_any_type(self):
        """测试 evaluate_compiled 返回任意类型（非布尔）"""
        evaluator = ExpressionEvaluator()
        compiled = evaluator.compile_expression("price * 0.9")

        result = evaluator.evaluate_compiled(compiled_ast=compiled, context={"price": 100})

        assert result == 90.0
        assert isinstance(result, float)


class TestResolveVariables:
    """测试 resolve_variables 方法"""

    def test_resolve_variables_flattens_simple_dict(self):
        """测试 resolve_variables 扁平化简单字典"""
        evaluator = ExpressionEvaluator()
        output = {"quality_score": 0.9, "count": 100}

        resolved = evaluator.resolve_variables(output)

        assert resolved == {"quality_score": 0.9, "count": 100}

    def test_resolve_variables_flattens_nested_dict(self):
        """测试 resolve_variables 扁平化嵌套字典"""
        evaluator = ExpressionEvaluator()
        output = {"node1": {"quality": 0.9, "count": 100}, "node2": {"status": "ok"}}

        resolved = evaluator.resolve_variables(output)

        # 应该既包含原始嵌套结构，又包含扁平化的键
        assert "node1" in resolved
        assert "quality" in resolved
        assert "count" in resolved
        assert "node2" in resolved
        assert "status" in resolved
        assert resolved["quality"] == 0.9
        assert resolved["count"] == 100
        assert resolved["status"] == "ok"

    def test_resolve_variables_handles_key_conflicts(self):
        """测试 resolve_variables 处理键冲突"""
        evaluator = ExpressionEvaluator()
        # 两个节点都有 'value' 键
        output = {"node1": {"value": 10}, "node2": {"value": 20}}

        resolved = evaluator.resolve_variables(output)

        # 命名空间化的键应该存在
        assert "node1" in resolved
        assert "node2" in resolved
        assert resolved["node1"]["value"] == 10
        assert resolved["node2"]["value"] == 20
        # 扁平化的键可能被覆盖（后者优先）
        assert "value" in resolved

    def test_resolve_variables_empty_dict(self):
        """测试 resolve_variables 处理空字典"""
        evaluator = ExpressionEvaluator()
        output = {}

        resolved = evaluator.resolve_variables(output)

        assert resolved == {}

    def test_resolve_variables_non_dict_values(self):
        """测试 resolve_variables 处理非字典值"""
        evaluator = ExpressionEvaluator()
        output = {"node1": {"data": [1, 2, 3]}, "node2": "string_value"}

        resolved = evaluator.resolve_variables(output)

        assert "node1" in resolved
        assert "data" in resolved
        assert resolved["data"] == [1, 2, 3]
        assert "node2" in resolved
        assert resolved["node2"] == "string_value"

"""表达式求值器 (Expression Evaluator)

业务定义：
- 安全地评估条件表达式，用于工作流条件分支
- 支持基于节点输出和上下文变量的布尔表达式
- 防止代码注入和不安全操作

设计原则：
- 纯Python实现，不依赖外部框架（DDD要求）
- 使用受限的eval进行表达式求值
- 白名单机制确保安全性
- 支持常见比较和逻辑运算

使用示例：
    evaluator = ExpressionEvaluator()
    context = {"score": 0.95, "count": 100}

    # 简单比较
    result = evaluator.evaluate("score > 0.8", context)  # True

    # 逻辑运算
    result = evaluator.evaluate("score > 0.8 and count >= 100", context)  # True

    # 字段访问
    context = {"node_output": {"quality": 0.95}}
    result = evaluator.evaluate("node_output['quality'] > 0.9", context)  # True
"""

import ast
import math
import re
from typing import Any


class ExpressionEvaluationError(Exception):
    """表达式求值异常

    在表达式评估过程中发生错误时抛出，如：
    - 缺失变量
    - 类型错误
    - 语法错误
    """

    pass


class UnsafeExpressionError(Exception):
    """不安全表达式异常

    当检测到潜在危险操作时抛出，如：
    - import语句
    - exec/eval调用
    - 文件操作
    - 双下划线方法访问
    """

    pass


class ExpressionEvaluator:
    """表达式求值器

    安全地评估条件表达式，支持：
    - 比较运算符：>, <, ==, !=, >=, <=
    - 逻辑运算符：and, or, not
    - 字典访问：obj['key']
    - 数值、字符串、布尔值字面量

    安全机制：
    - 白名单AST节点类型
    - 禁止import、exec、eval等危险操作
    - 禁止双下划线方法访问
    - 禁止函数调用（除白名单函数）

    实现策略：
    1. 使用ast.parse解析表达式为AST
    2. 遍历AST检查是否包含危险节点
    3. 使用eval()在受限上下文中求值
    """

    # 危险关键字黑名单
    DANGEROUS_KEYWORDS = {
        "import",
        "exec",
        "eval",
        "compile",
        "open",
        "__import__",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "dir",
        "help",
        "input",
        "exit",
        "quit",
    }

    # 危险函数调用黑名单（函数名）
    DANGEROUS_FUNCTIONS = {
        "exec",
        "eval",
        "compile",
        "open",
        "input",
        "__import__",
        "breakpoint",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "dir",
    }

    def __init__(self, mode: str = "safe"):
        """初始化表达式求值器

        参数：
            mode: 求值模式，可选 "safe"（默认）或 "advanced"
                  - safe: 仅支持基础运算，禁止函数调用
                  - advanced: 允许受限函数（len, str, math等），仍禁I/O
        """
        # 缓存已编译的表达式（可选优化）
        self._compiled_cache: dict[str, ast.Expression] = {}
        # 默认求值模式
        self._mode = mode

    def evaluate(
        self,
        expression: str | None,
        context: dict[str, Any],
        *,
        workflow_vars: dict[str, Any] | None = None,
        global_vars: dict[str, Any] | None = None,
        item: Any = None,
        mode: str | None = None,
    ) -> bool:
        """评估布尔表达式

        参数：
            expression: 条件表达式字符串
            context: 主求值上下文（变量字典）
            workflow_vars: 工作流级别变量（可选）
            global_vars: 全局级别变量（可选）
            item: 集合元素（可选，优先级最高）
            mode: 覆盖实例默认模式（可选）

        返回：
            表达式求值结果（布尔值）

        上下文优先级：
            item > context > workflow_vars > global_vars

        异常：
            ExpressionEvaluationError: 求值失败
            UnsafeExpressionError: 表达式不安全

        示例：
            # 基础用法（向后兼容）
            evaluator.evaluate("score > 0.8", {"score": 0.9})  # True

            # 多层上下文
            evaluator.evaluate(
                "data_quality >= threshold",
                {"data_quality": 0.9},
                workflow_vars={"threshold": 0.8}
            )  # True

            # 集合元素
            evaluator.evaluate(
                "price > 100",
                {},
                item={"price": 150}
            )  # True
        """
        result = self.evaluate_expression(
            expression,
            context,
            workflow_vars=workflow_vars,
            global_vars=global_vars,
            item=item,
            mode=mode,
        )
        return bool(result)

    def evaluate_expression(
        self,
        expression: str | None,
        context: dict[str, Any],
        *,
        workflow_vars: dict[str, Any] | None = None,
        global_vars: dict[str, Any] | None = None,
        item: Any = None,
        mode: str | None = None,
    ) -> Any:
        """评估表达式并返回原始值

        用于非布尔场景（如Map操作），返回表达式的实际计算结果。

        参数：
            expression: 表达式字符串
            context: 主求值上下文
            workflow_vars: 工作流级别变量（可选）
            global_vars: 全局级别变量（可选）
            item: 集合元素（可选）
            mode: 覆盖实例默认模式（可选）

        返回：
            表达式计算结果（任意类型）

        示例：
            # 返回数值
            evaluator.evaluate_expression("price * 0.9", {"price": 100})  # 90.0

            # 返回字符串
            evaluator.evaluate_expression("name + '_suffix'", {"name": "test"})  # "test_suffix"
        """
        # 处理空表达式
        if not expression or not expression.strip():
            return False

        # 确定求值模式
        eval_mode = (mode or self._mode or "safe").lower()

        # 构建合并的求值上下文
        evaluation_context = self._build_evaluation_context(
            context=context,
            workflow_vars=workflow_vars,
            global_vars=global_vars,
            item=item,
        )

        # 检查是否包含危险关键字
        self._check_dangerous_keywords(expression)

        # 解析AST并检查安全性
        try:
            tree = ast.parse(expression, mode="eval")
            allowed_functions = self._get_allowed_functions(eval_mode)
            self._validate_ast(tree, eval_mode, allowed_functions)
        except SyntaxError as e:
            raise ExpressionEvaluationError(f"表达式语法错误: {expression}") from e

        # 在受限上下文中求值
        try:
            # 获取允许的函数白名单
            allowed_functions = self._get_allowed_functions(eval_mode)

            # 清理上下文：移除与白名单函数同名的变量（防止函数劫持）
            sanitized_context = self._sanitize_context_for_advanced_mode(
                evaluation_context, allowed_functions
            )

            # 创建安全的全局命名空间
            safe_globals = {
                "__builtins__": {},  # 禁用内置函数
                **allowed_functions,  # 添加白名单函数
            }

            # 使用清理后的上下文作为局部变量
            result = eval(compile(tree, "<expression>", "eval"), safe_globals, sanitized_context)

            return result

        except NameError as e:
            raise ExpressionEvaluationError(f"变量未定义: {e}") from e
        except (TypeError, AttributeError, KeyError) as e:
            raise ExpressionEvaluationError(f"表达式求值错误: {e}") from e
        except Exception as e:
            raise ExpressionEvaluationError(f"未知错误: {e}") from e

    def compile_expression(self, expression: str) -> ast.Expression:
        """预编译表达式为 AST 节点，供重复使用

        此方法将表达式字符串解析为 AST，并缓存结果以提升性能。
        适用于需要多次执行相同表达式的场景。

        参数：
            expression: 表达式字符串

        返回：
            编译后的 AST Expression 节点

        异常：
            ExpressionEvaluationError: 语法错误或包含危险关键字

        示例：
            evaluator = ExpressionEvaluator()
            compiled = evaluator.compile_expression("score > 0.8")
            # 可以多次复用 compiled 对象
        """
        # 检查缓存
        if expression in self._compiled_cache:
            return self._compiled_cache[expression]

        # 检查危险关键字
        try:
            self._check_dangerous_keywords(expression)
        except UnsafeExpressionError as e:
            raise ExpressionEvaluationError(f"表达式不安全: {e}") from e

        # 解析 AST
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise ExpressionEvaluationError(f"表达式语法错误: {expression}") from e

        # 缓存编译结果
        self._compiled_cache[expression] = tree

        return tree

    def evaluate_compiled(
        self,
        compiled_ast: ast.Expression,
        context: dict[str, Any],
        *,
        workflow_vars: dict[str, Any] | None = None,
        global_vars: dict[str, Any] | None = None,
        item: Any = None,
        mode: str | None = None,
    ) -> Any:
        """执行编译后的表达式

        使用预编译的 AST 节点进行求值，避免重复解析开销。
        支持多层上下文，与 evaluate_expression 保持一致。

        参数：
            compiled_ast: 预编译的 AST Expression 节点
            context: 主求值上下文
            workflow_vars: 工作流级别变量（可选）
            global_vars: 全局级别变量（可选）
            item: 集合元素（可选）
            mode: 覆盖实例默认模式（可选）

        返回：
            表达式计算结果（任意类型）

        异常：
            ExpressionEvaluationError: 求值失败

        示例：
            evaluator = ExpressionEvaluator()
            compiled = evaluator.compile_expression("value * 2")
            result = evaluator.evaluate_compiled(compiled, {"value": 10})  # 20
        """
        # 确定求值模式
        eval_mode = (mode or self._mode or "safe").lower()

        # 构建合并的求值上下文
        evaluation_context = self._build_evaluation_context(
            context=context,
            workflow_vars=workflow_vars,
            global_vars=global_vars,
            item=item,
        )

        # 验证 AST 安全性
        try:
            allowed_functions = self._get_allowed_functions(eval_mode)
            self._validate_ast(compiled_ast, eval_mode, allowed_functions)
        except UnsafeExpressionError as e:
            raise ExpressionEvaluationError(f"表达式不安全: {e}") from e

        # 执行求值
        try:
            # 清理上下文
            sanitized_context = self._sanitize_context_for_advanced_mode(
                evaluation_context, allowed_functions
            )

            # 创建安全的全局命名空间
            safe_globals = {
                "__builtins__": {},
                **allowed_functions,
            }

            # 执行编译后的 AST
            result = eval(
                compile(compiled_ast, "<compiled>", "eval"),
                safe_globals,
                sanitized_context,
            )

            return result

        except NameError as e:
            raise ExpressionEvaluationError(f"变量未定义: {e}") from e
        except (TypeError, AttributeError, KeyError) as e:
            raise ExpressionEvaluationError(f"表达式求值错误: {e}") from e
        except Exception as e:
            raise ExpressionEvaluationError(f"未知错误: {e}") from e

    def resolve_variables(self, output_dict: dict[str, Any]) -> dict[str, Any]:
        """扁平化节点输出字典供条件表达式使用

        此方法将嵌套的节点输出字典转换为扁平结构，同时保留原始嵌套结构。
        这样既支持直接访问键（如 quality），又支持命名空间访问（如 node1.quality）。

        处理策略：
        1. 保留所有顶层键（命名空间）
        2. 扁平化所有嵌套字典的键到顶层
        3. 键冲突时，后者覆盖前者（可通过命名空间访问原值）

        参数：
            output_dict: 节点输出字典，格式为 {node_id: {output_data}}

        返回：
            扁平化后的字典，既包含命名空间又包含扁平键

        示例：
            input = {
                "node1": {"quality": 0.9, "count": 100},
                "node2": {"status": "ok"}
            }
            output = {
                "node1": {"quality": 0.9, "count": 100},
                "quality": 0.9,
                "count": 100,
                "node2": {"status": "ok"},
                "status": "ok"
            }
        """
        if not output_dict:
            return {}

        resolved: dict[str, Any] = {}

        # 遍历所有节点输出
        for node_id, output in output_dict.items():
            # 保留命名空间化的键
            resolved[node_id] = output

            # 如果输出是字典，扁平化其键
            if isinstance(output, dict):
                for key, value in output.items():
                    # 扁平化到顶层（可能覆盖）
                    resolved[key] = value

        return resolved

    def _check_dangerous_keywords(self, expression: str) -> None:
        """检查表达式是否包含危险关键字

        参数：
            expression: 表达式字符串

        异常：
            UnsafeExpressionError: 包含危险关键字
        """
        # 简单的关键字检查（词法层面）
        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(rf"\b{keyword}\b", expression):
                raise UnsafeExpressionError(f"表达式包含危险操作: {keyword}")

        # 检查双下划线（dunder）方法
        if "__" in expression:
            raise UnsafeExpressionError("表达式不允许访问双下划线方法")

    def _validate_ast(
        self,
        tree: ast.Expression,
        mode: str,
        allowed_functions: dict[str, Any] | None = None,
    ) -> None:
        """验证AST安全性

        遍历AST，确保只包含允许的节点类型。

        参数：
            tree: AST表达式树
            mode: 求值模式（safe/advanced）
            allowed_functions: 允许的函数白名单（可选）

        异常：
            UnsafeExpressionError: AST包含不安全节点
        """
        # 允许的AST节点类型（白名单）
        allowed_node_types = {
            # 基础节点
            ast.Expression,
            ast.Constant,  # 字面量（数字、字符串、布尔等）
            ast.Name,  # 变量名
            ast.Load,  # 加载变量
            # 比较运算
            ast.Compare,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
            # 逻辑运算
            ast.BoolOp,
            ast.And,
            ast.Or,
            ast.UnaryOp,
            ast.Not,
            # 数据访问
            ast.Subscript,  # 下标访问 obj[key]
            ast.Index,  # 索引（旧版本Python）
            # 数值运算（可选，用于计算）
            ast.BinOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Mod,
        }

        # 函数调用仅在advanced模式下允许，且必须在白名单
        if mode == "advanced":
            allowed_node_types.update(
                {
                    ast.Call,
                    ast.keyword,
                }
            )

        # 遍历AST检查节点类型
        for node in ast.walk(tree):
            node_type = type(node)
            if node_type not in allowed_node_types:
                raise UnsafeExpressionError(f"表达式包含不允许的操作: {node_type.__name__}")

            # 函数调用检查
            if isinstance(node, ast.Call):
                # safe模式下禁止所有函数调用
                if mode != "advanced":
                    raise UnsafeExpressionError("safe 模式下不允许函数调用")

                # advanced模式下检查函数白名单
                if not isinstance(node.func, ast.Name):
                    raise UnsafeExpressionError("仅允许直接调用白名单函数")

                func_name = node.func.id
                if not allowed_functions or func_name not in allowed_functions:
                    raise UnsafeExpressionError(f"函数 {func_name} 不在允许列表中")

                # 禁止可变参数（兼容Python 3.11+）
                # Python 3.11+: ast.keyword.arg is None表示**kwargs
                # Python 3.8-3.10: node.keywords包含 ast.keyword(arg=None)
                for kw in node.keywords:
                    if kw.arg is None:
                        raise UnsafeExpressionError("不允许使用**kwargs可变参数")

                # 禁止*args（通过检测Starred节点）
                for arg in node.args:
                    if isinstance(arg, ast.Starred):
                        raise UnsafeExpressionError("不允许使用*args可变参数")

                # 限制参数数量
                if len(node.args) > 5:
                    raise UnsafeExpressionError("函数参数过多")

            # 禁止Starred（*解包）在其他上下文
            if isinstance(node, ast.Starred):
                raise UnsafeExpressionError("不允许使用*解包操作")

            # 额外检查：禁止属性访问（防止 obj.__class__ 等）
            if isinstance(node, ast.Attribute):
                attr_name = node.attr
                if attr_name.startswith("__"):
                    raise UnsafeExpressionError(f"表达式不允许访问双下划线属性: {attr_name}")

    def _build_evaluation_context(
        self,
        context: dict[str, Any],
        workflow_vars: dict[str, Any] | None = None,
        global_vars: dict[str, Any] | None = None,
        item: Any = None,
    ) -> dict[str, Any]:
        """合并多层上下文

        按照优先级合并：item > context > workflow_vars > global_vars

        安全机制：移除与白名单函数同名的变量，防止函数劫持

        参数：
            context: 主上下文
            workflow_vars: 工作流变量（可选）
            global_vars: 全局变量（可选）
            item: 集合元素（可选）

        返回：
            合并后的求值上下文
        """
        merged: dict[str, Any] = {}

        # 按优先级从低到高合并
        if global_vars:
            merged.update(global_vars)

        if workflow_vars:
            merged.update(workflow_vars)

        merged.update(context or {})

        # item优先级最高
        if item is not None:
            if isinstance(item, dict):
                # 字典类型：直接合并键值
                merged.update(item)
            else:
                # 标量类型：映射到特殊键
                merged.update(
                    {
                        "item": item,
                        "value": item,
                        "current": item,
                    }
                )

        return merged

    def _sanitize_context_for_advanced_mode(
        self,
        context: dict[str, Any],
        allowed_functions: dict[str, Any],
    ) -> dict[str, Any]:
        """移除上下文中与白名单函数同名的变量

        防止用户通过上下文劫持内置函数（如将len替换为恶意函数）

        参数：
            context: 原始上下文
            allowed_functions: 白名单函数

        返回：
            清理后的上下文
        """
        if not allowed_functions:
            return context

        # 过滤掉与白名单函数同名的变量
        sanitized = {k: v for k, v in context.items() if k not in allowed_functions}

        return sanitized

    def _get_allowed_functions(self, mode: str) -> dict[str, Any]:
        """根据模式返回可调用函数白名单

        参数：
            mode: 求值模式（safe/advanced）

        返回：
            函数名到函数对象的映射
        """
        if mode != "advanced":
            return {}

        # advanced模式下允许的受限函数
        return {
            # 类型转换
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            # 数值函数
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "round": round,
            # 集合函数
            "len": len,
            # math模块函数
            "sqrt": math.sqrt,
            "ceil": math.ceil,
            "floor": math.floor,
        }


# 导出
__all__ = [
    "ExpressionEvaluator",
    "ExpressionEvaluationError",
    "UnsafeExpressionError",
]

"""代码修复服务 - GAP-004

业务定义：
- 自动分析执行失败的代码
- 使用 LLM 辅助修复代码
- 验证修复后的代码安全性

设计原则：
- 支持多种错误类型分析
- 支持带验证的重试机制
- 支持没有 LLM 时的优雅降级

使用示例：
    service = CodeRepair(llm=my_llm)
    result = await service.repair_code_with_result(code, error)
    if result.success:
        print(result.repaired_code)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


class RepairLLMProtocol(Protocol):
    """修复 LLM 协议"""

    async def repair_code(
        self,
        code: str,
        error: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """修复代码

        参数：
            code: 原始代码
            error: 错误信息
            context: 上下文信息

        返回：
            修复后的代码，或 None
        """
        ...


@dataclass
class RepairResult:
    """修复结果

    属性：
        success: 是否成功
        repaired_code: 修复后的代码
        original_code: 原始代码
        error_analysis: 错误分析
        attempts: 尝试次数
        requires_manual_intervention: 是否需要手动干预
        error_message: 错误消息
    """

    success: bool = False
    repaired_code: str | None = None
    original_code: str = ""
    error_analysis: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    requires_manual_intervention: bool = False
    error_message: str | None = None


# 危险模块/函数列表
UNSAFE_IMPORTS = {
    "os",
    "subprocess",
    "sys",
    "shutil",
    "socket",
    "ctypes",
    "eval",
    "exec",
    "__import__",
}

UNSAFE_FUNCTIONS = {
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "__import__",
}


class CodeRepair:
    """代码修复服务

    提供以下功能：
    1. 分析代码错误
    2. 使用 LLM 修复代码
    3. 验证修复后的代码
    """

    def __init__(
        self,
        llm: RepairLLMProtocol | Any | None = None,
        max_repair_attempts: int = 3,
    ) -> None:
        """初始化代码修复服务

        参数：
            llm: LLM 实例（可选）
            max_repair_attempts: 最大修复尝试次数
        """
        self.llm = llm
        self.max_repair_attempts = max_repair_attempts

    def analyze_error(
        self,
        code: str,
        error: BaseException,
    ) -> dict[str, Any]:
        """分析代码错误

        参数：
            code: 代码字符串
            error: 错误实例

        返回：
            错误分析字典
        """
        error_type = self._get_error_type(error)
        analysis: dict[str, Any] = {
            "error_type": error_type,
            "error_message": str(error),
        }

        # 根据错误类型进行详细分析
        if isinstance(error, SyntaxError):
            analysis["location"] = {
                "line": getattr(error, "lineno", None),
                "offset": getattr(error, "offset", None),
            }
            analysis["line"] = getattr(error, "lineno", None)

        elif isinstance(error, NameError):
            # 提取未定义的变量名
            match = re.search(r"name '(\w+)' is not defined", str(error))
            if match:
                analysis["missing_name"] = match.group(1)

        elif isinstance(error, (ModuleNotFoundError, ImportError)):
            # 提取模块名
            match = re.search(r"No module named '(\w+)'", str(error))
            if match:
                analysis["module_name"] = match.group(1)

        elif isinstance(error, TypeError):
            analysis["type_info"] = str(error)

        return analysis

    def _get_error_type(self, error: BaseException) -> str:
        """获取错误类型标识

        参数：
            error: 错误实例

        返回：
            错误类型字符串
        """
        if isinstance(error, SyntaxError):
            return "syntax"
        if isinstance(error, NameError):
            return "name"
        if isinstance(error, TypeError):
            return "type"
        if isinstance(error, (ModuleNotFoundError, ImportError)):
            return "import"
        if isinstance(error, AttributeError):
            return "attribute"
        if isinstance(error, KeyError):
            return "key"
        if isinstance(error, IndexError):
            return "index"
        if isinstance(error, ValueError):
            return "value"
        return "unknown"

    def validate_syntax(self, code: str) -> bool:
        """验证代码语法

        检查语法是否有效，同时检测不完整的代码模式。

        参数：
            code: 代码字符串

        返回：
            True 如果语法有效且代码完整
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        # 检查不完整的代码模式
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检查函数体是否只有一个 bare return
                if len(node.body) == 1:
                    stmt = node.body[0]
                    if isinstance(stmt, ast.Return) and stmt.value is None:
                        # 检查代码是否显式写了 "return" 后面没有值
                        # 如果函数体只有一个 bare return，可能是不完整的代码
                        if "return" in code and not self._has_complete_return(code, node):
                            return False

        return True

    def _has_complete_return(self, code: str, func_node: ast.FunctionDef) -> bool:
        """检查函数是否有完整的 return 语句

        参数：
            code: 代码字符串
            func_node: 函数 AST 节点

        返回：
            True 如果 return 语句完整
        """
        # 使用正则检查 return 后面是否有值
        # 匹配 "return" 后面只有空白或行尾的情况
        import re

        # 提取函数代码
        lines = code.split("\n")
        for line in lines:
            stripped = line.strip()
            # 检查是否是单独的 return 语句（没有返回值）
            if stripped == "return" or stripped.endswith(": return"):
                return False
            # 检查 return 后面是否只有空白
            if re.match(r"^\s*return\s*$", stripped):
                return False

        return True

    def validate_safety(self, code: str) -> bool:
        """验证代码安全性

        检查是否包含危险的导入或函数调用。

        参数：
            code: 代码字符串

        返回：
            True 如果代码安全
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            # 检查危险导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in UNSAFE_IMPORTS:
                        return False

            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in UNSAFE_IMPORTS:
                    return False

            # 检查危险函数调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in UNSAFE_FUNCTIONS:
                        return False

                # 检查 os.system 等调用
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        module = node.func.value.id
                        method = node.func.attr
                        if module in UNSAFE_IMPORTS:
                            return False
                        if method in {"system", "popen", "spawn", "exec"}:
                            return False

        return True

    async def repair_code(
        self,
        code: str,
        error: BaseException,
        context: dict[str, Any] | None = None,
        validate: bool = False,
    ) -> str | None:
        """修复代码

        参数：
            code: 原始代码
            error: 错误实例
            context: 上下文信息
            validate: 是否验证修复结果

        返回：
            修复后的代码，或 None
        """
        if self.llm is None:
            return None

        # 分析错误
        analysis = self.analyze_error(code, error)

        # 构建修复上下文
        repair_context = context or {}
        repair_context["error_analysis"] = analysis

        attempts = 0
        while attempts < self.max_repair_attempts:
            attempts += 1

            # 调用 LLM 修复
            repaired = await self.llm.repair_code(
                code,
                str(error),
                repair_context,
            )

            if repaired is None:
                continue

            # 如果不需要验证，直接返回
            if not validate:
                return repaired

            # 验证修复结果
            if self.validate_syntax(repaired):
                return repaired

        return None

    async def repair_code_with_result(
        self,
        code: str,
        error: BaseException,
        context: dict[str, Any] | None = None,
    ) -> RepairResult:
        """修复代码并返回详细结果

        参数：
            code: 原始代码
            error: 错误实例
            context: 上下文信息

        返回：
            RepairResult 修复结果
        """
        result = RepairResult(
            original_code=code,
            error_analysis=self.analyze_error(code, error),
        )

        if self.llm is None:
            result.success = False
            result.error_message = "No LLM configured for code repair"
            result.requires_manual_intervention = True
            return result

        repair_context = context or {}
        repair_context["error_analysis"] = result.error_analysis

        attempts = 0
        while attempts < self.max_repair_attempts:
            attempts += 1
            result.attempts = attempts

            try:
                # 调用 LLM 修复
                repaired = await self.llm.repair_code(
                    code,
                    str(error),
                    repair_context,
                )

                if repaired is None:
                    continue

                # 验证修复结果
                if self.validate_syntax(repaired):
                    result.success = True
                    result.repaired_code = repaired
                    return result

            except Exception as e:
                result.error_message = str(e)

        # 修复失败
        result.success = False
        result.requires_manual_intervention = True
        if not result.error_message:
            result.error_message = f"Failed to repair after {attempts} attempts"

        return result


# 导出
__all__ = [
    "CodeRepair",
    "RepairResult",
    "RepairLLMProtocol",
]

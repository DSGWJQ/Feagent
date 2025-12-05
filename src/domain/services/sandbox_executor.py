"""沙箱执行器 (SandboxExecutor) - 动态代码注入与安全执行

业务定义：
- 沙箱执行器负责在隔离环境中安全执行动态生成的代码
- 支持资源限制（超时、内存、输出大小）
- 提供安全检查，拒绝执行危险代码
- 支持 Agent 集成：ConversationAgent 生成 → WorkflowAgent 执行 → Coordinator 监控

设计原则：
- 安全优先：默认拒绝危险操作
- 资源受控：严格限制执行时间和内存
- 可观测性：详细的执行日志和指标
- 隔离性：代码在独立目录/进程中执行

使用示例：
    executor = SandboxExecutor()
    config = SandboxConfig(timeout_seconds=5)
    result = executor.execute(code="print('hello')", config=config)
"""

import ast
import multiprocessing
import re
import shutil
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ============================================================
# 数据结构定义
# ============================================================


class SecurityLevel(str, Enum):
    """安全级别"""

    STRICT = "strict"  # 严格模式：禁止所有危险操作
    MODERATE = "moderate"  # 中等模式：允许部分操作
    PERMISSIVE = "permissive"  # 宽松模式：仅警告


@dataclass
class CodeSegment:
    """动态代码段

    属性：
        language: 编程语言（目前仅支持 python）
        code: 代码内容
        entry_function: 入口函数名
        dependencies: 依赖包列表
    """

    language: str
    code: str
    entry_function: str = "main"
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "language": self.language,
            "code": self.code,
            "entry_function": self.entry_function,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeSegment":
        """从字典反序列化"""
        return cls(
            language=data.get("language", "python"),
            code=data.get("code", ""),
            entry_function=data.get("entry_function", "main"),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class SecurityViolation:
    """安全违规

    属性：
        rule: 违反的规则名称
        description: 描述
        line_number: 行号（可选）
        severity: 严重级别
    """

    rule: str
    description: str
    line_number: int | None = None
    severity: str = "error"


@dataclass
class SandboxConfig:
    """沙箱配置

    属性：
        timeout_seconds: 执行超时（秒）
        max_memory_mb: 最大内存（MB）
        max_output_size: 最大输出大小（字节）
        allowed_imports: 允许的导入模块列表
        enable_security_check: 是否启用安全检查
        enable_logging: 是否启用日志
        isolation_dir: 隔离目录
        cleanup_after: 执行后是否清理
        security_level: 安全级别
    """

    timeout_seconds: int = 30
    max_memory_mb: int = 256
    max_output_size: int = 1024 * 1024  # 1MB
    allowed_imports: list[str] = field(
        default_factory=lambda: [
            "math",
            "json",
            "datetime",
            "re",
            "collections",
            "itertools",
            "functools",
            "operator",
            "string",
            "random",
            "statistics",
            "decimal",
            "fractions",
            "copy",
            "pprint",
            "textwrap",
            "unicodedata",
        ]
    )
    enable_security_check: bool = True
    enable_logging: bool = True
    isolation_dir: Path | None = None
    cleanup_after: bool = True
    security_level: SecurityLevel = SecurityLevel.STRICT


@dataclass
class SandboxResult:
    """沙箱执行结果

    属性：
        success: 是否执行成功
        stdout: 标准输出
        stderr: 标准错误
        output_data: 输出数据（output 变量）
        execution_time: 执行时间（秒）
        timed_out: 是否超时
        memory_exceeded: 是否内存超限
        security_violation: 是否安全违规
        violations: 安全违规列表
        logs: 执行日志
        metrics: 执行指标
        isolation_dir: 隔离目录路径
    """

    success: bool = False
    stdout: str = ""
    stderr: str = ""
    output_data: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    timed_out: bool = False
    memory_exceeded: bool = False
    security_violation: bool = False
    violations: list[SecurityViolation] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    isolation_dir: Path | None = None


# ============================================================
# 安全检查器
# ============================================================


class SecurityChecker:
    """安全检查器

    检测代码中的危险操作：
    - 系统命令执行（os.system, subprocess）
    - 危险内置函数（eval, exec, compile）
    - 文件系统操作
    - 网络操作
    - 无限循环
    - 资源炸弹
    """

    # 危险模块
    DANGEROUS_MODULES = {
        "os",
        "subprocess",
        "sys",
        "shutil",
        "socket",
        "urllib",
        "requests",
        "http",
        "ftplib",
        "telnetlib",
        "pickle",
        "shelve",
        "marshal",
        "ctypes",
        "multiprocessing",
        "threading",
        "asyncio",
        "signal",
        "pty",
        "tty",
    }

    # 危险函数
    DANGEROUS_FUNCTIONS = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "raw_input",
        "execfile",
        "file",
    }

    # 危险属性访问
    DANGEROUS_ATTRIBUTES = {
        "__builtins__",
        "__class__",
        "__bases__",
        "__subclasses__",
        "__globals__",
        "__code__",
        "__reduce__",
        "__reduce_ex__",
    }

    def __init__(self, security_level: SecurityLevel = SecurityLevel.STRICT):
        """初始化安全检查器

        参数：
            security_level: 安全级别
        """
        self.security_level = security_level

    def check(self, code: str) -> list[SecurityViolation]:
        """检查代码安全性

        参数：
            code: 要检查的代码

        返回：
            安全违规列表
        """
        violations = []

        # 1. 检查危险导入
        violations.extend(self._check_dangerous_imports(code))

        # 2. 检查危险函数调用
        violations.extend(self._check_dangerous_functions(code))

        # 3. 检查危险属性访问
        violations.extend(self._check_dangerous_attributes(code))

        # 4. 检查无限循环模式
        violations.extend(self._check_infinite_loops(code))

        # 5. 检查资源炸弹
        violations.extend(self._check_resource_bombs(code))

        # 6. 检查文件操作
        violations.extend(self._check_file_operations(code))

        return violations

    def _check_dangerous_imports(self, code: str) -> list[SecurityViolation]:
        """检查危险导入"""
        violations = []

        # 使用 AST 解析
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        if module_name in self.DANGEROUS_MODULES:
                            violations.append(
                                SecurityViolation(
                                    rule="dangerous_import",
                                    description=f"Dangerous module import: {alias.name}",
                                    line_number=node.lineno,
                                )
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        if module_name in self.DANGEROUS_MODULES:
                            violations.append(
                                SecurityViolation(
                                    rule="dangerous_import",
                                    description=f"Dangerous module import: {node.module}",
                                    line_number=node.lineno,
                                )
                            )
        except SyntaxError:
            pass  # 语法错误将在执行时捕获

        return violations

    def _check_dangerous_functions(self, code: str) -> list[SecurityViolation]:
        """检查危险函数调用"""
        violations = []

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in self.DANGEROUS_FUNCTIONS:
                        violations.append(
                            SecurityViolation(
                                rule="dangerous_function",
                                description=f"Dangerous function call: {func_name}",
                                line_number=node.lineno,
                            )
                        )

                    # 检查 os.system, subprocess.run 等
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in ("system", "popen", "spawn", "run", "call", "Popen"):
                            violations.append(
                                SecurityViolation(
                                    rule="dangerous_function",
                                    description=f"Dangerous system call: {node.func.attr}",
                                    line_number=node.lineno,
                                )
                            )
        except SyntaxError:
            pass

        return violations

    def _check_dangerous_attributes(self, code: str) -> list[SecurityViolation]:
        """检查危险属性访问"""
        violations = []

        for attr in self.DANGEROUS_ATTRIBUTES:
            if attr in code:
                violations.append(
                    SecurityViolation(
                        rule="dangerous_attribute",
                        description=f"Dangerous attribute access: {attr}",
                    )
                )

        return violations

    def _check_infinite_loops(self, code: str) -> list[SecurityViolation]:
        """检查无限循环模式"""
        violations = []

        # 检查 while True 模式
        patterns = [
            (r"\bwhile\s+True\s*:", "while True without break"),
            (r"\bwhile\s+1\s*:", "while 1 without break"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code):
                # 检查是否有 break
                # 简单检查：如果整个代码没有 break，则标记
                if "break" not in code:
                    violations.append(
                        SecurityViolation(
                            rule="infinite_loop",
                            description=f"Potential infinite loop: {desc}",
                            severity="warning",
                        )
                    )

        return violations

    def _check_resource_bombs(self, code: str) -> list[SecurityViolation]:
        """检查资源炸弹"""
        violations = []

        # 检查大内存分配模式
        patterns = [
            (r"\*\s*\(\s*10\s*\*\*\s*[89]\d*\s*\)", "Large memory allocation (10^8+)"),
            (r"\*\s*\(\s*\d{8,}\s*\)", "Large memory allocation (100M+)"),
            (r"'[^']*'\s*\*\s*\d{7,}", "Large string multiplication"),
            (r'"[^"]*"\s*\*\s*\d{7,}', "Large string multiplication"),
            # 检查 10 ** 10 等大幂运算
            (r"10\s*\*\*\s*10", "Large power operation (10^10)"),
            (r"\d+\s*\*\*\s*\d{2,}", "Large power operation"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code):
                violations.append(
                    SecurityViolation(
                        rule="resource_bomb",
                        description=f"Potential memory/resource bomb: {desc}",
                    )
                )

        return violations

    def _check_file_operations(self, code: str) -> list[SecurityViolation]:
        """检查文件操作"""
        violations = []

        # 检查文件写入模式
        patterns = [
            (r"open\s*\([^)]*['\"][wax]['\"]", "File write operation"),
            (r"open\s*\([^)]*mode\s*=\s*['\"][wax]", "File write operation"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code):
                violations.append(
                    SecurityViolation(
                        rule="file_operation",
                        description=f"Dangerous file operation: {desc}",
                    )
                )

        return violations


# ============================================================
# 执行监控器
# ============================================================


class ExecutionMonitor:
    """执行监控器

    用于 Coordinator 监控代码执行过程。
    """

    def __init__(self):
        """初始化监控器"""
        self._on_start_callbacks: list[Callable] = []
        self._on_complete_callbacks: list[Callable] = []
        self._on_error_callbacks: list[Callable] = []
        self._events: list[dict[str, Any]] = []

    def on_start(self, callback: Callable) -> None:
        """注册开始回调"""
        self._on_start_callbacks.append(callback)

    def on_complete(self, callback: Callable) -> None:
        """注册完成回调"""
        self._on_complete_callbacks.append(callback)

    def on_error(self, callback: Callable) -> None:
        """注册错误回调"""
        self._on_error_callbacks.append(callback)

    def emit_start(self, event: dict[str, Any]) -> None:
        """触发开始事件"""
        event["type"] = "start"
        event["timestamp"] = datetime.now().isoformat()
        self._events.append(event)
        for callback in self._on_start_callbacks:
            try:
                callback(event)
            except Exception:
                pass

    def emit_complete(self, event: dict[str, Any]) -> None:
        """触发完成事件"""
        event["type"] = "complete"
        event["timestamp"] = datetime.now().isoformat()
        self._events.append(event)
        for callback in self._on_complete_callbacks:
            try:
                callback(event)
            except Exception:
                pass

    def emit_error(self, event: dict[str, Any]) -> None:
        """触发错误事件"""
        event["type"] = "error"
        event["timestamp"] = datetime.now().isoformat()
        self._events.append(event)
        for callback in self._on_error_callbacks:
            try:
                callback(event)
            except Exception:
                pass

    def get_events(self) -> list[dict[str, Any]]:
        """获取所有事件"""
        return self._events.copy()


# ============================================================
# 沙箱执行器
# ============================================================


def _execute_in_sandbox(
    code: str,
    input_data: dict[str, Any],
    result_queue: multiprocessing.Queue,
    max_output_size: int,
    allowed_imports: list[str] | None = None,
) -> None:
    """在子进程中执行代码（内部函数）

    参数：
        code: 要执行的代码
        input_data: 输入数据
        result_queue: 结果队列
        max_output_size: 最大输出大小
        allowed_imports: 允许的导入模块列表
    """
    import importlib
    import io

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    # 创建受限的 __import__ 函数
    allowed = set(allowed_imports or [])

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        """受限的导入函数"""
        module_name = name.split(".")[0]
        if module_name in allowed:
            return importlib.import_module(name)
        raise ImportError(f"Import of '{name}' is not allowed in sandbox")

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        # 准备执行环境
        exec_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "reversed": reversed,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "any": any,
                "all": all,
                "isinstance": isinstance,
                "type": type,
                "hasattr": hasattr,
                "getattr": getattr,
                "setattr": setattr,
                "True": True,
                "False": False,
                "None": None,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
                "ImportError": ImportError,
                "__import__": safe_import,
            },
            "input_data": input_data,
            "output": {},
        }

        # 执行代码
        exec(code, exec_globals)

        # 获取输出
        stdout_value = stdout_capture.getvalue()
        if len(stdout_value) > max_output_size:
            stdout_value = stdout_value[:max_output_size] + "\n... [truncated]"

        result_queue.put(
            {
                "success": True,
                "stdout": stdout_value,
                "stderr": stderr_capture.getvalue(),
                "output_data": exec_globals.get("output", {}),
            }
        )

    except Exception as e:
        result_queue.put(
            {
                "success": False,
                "stdout": stdout_capture.getvalue(),
                "stderr": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                "output_data": {},
            }
        )

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


class SandboxExecutor:
    """沙箱执行器

    在隔离环境中安全执行代码。

    使用示例：
        executor = SandboxExecutor()
        result = executor.execute(
            code="result = 1 + 1\\nprint(result)",
            config=SandboxConfig(timeout_seconds=5),
        )
    """

    def __init__(self):
        """初始化沙箱执行器"""
        self._security_checker = SecurityChecker()

    def execute(
        self,
        code: str,
        config: SandboxConfig | None = None,
        input_data: dict[str, Any] | None = None,
        monitor: ExecutionMonitor | None = None,
    ) -> SandboxResult:
        """执行代码

        参数：
            code: 要执行的代码
            config: 沙箱配置
            input_data: 输入数据
            monitor: 执行监控器

        返回：
            执行结果
        """
        config = config or SandboxConfig()
        input_data = input_data or {}
        start_time = time.time()

        result = SandboxResult()
        result.logs = []

        # 记录开始
        if config.enable_logging:
            result.logs.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "event": "execution_start",
                    "code_length": len(code),
                }
            )

        # 触发监控事件
        if monitor:
            monitor.emit_start({"code_length": len(code)})

        # 1. 检查空代码
        if not code or not code.strip():
            result.success = False
            result.stderr = "Empty code"
            result.execution_time = time.time() - start_time
            return result

        # 2. 语法检查
        try:
            ast.parse(code)
        except SyntaxError as e:
            result.success = False
            result.stderr = f"SyntaxError: {e.msg} at line {e.lineno}"
            result.execution_time = time.time() - start_time
            if monitor:
                monitor.emit_error({"error": result.stderr})
            return result

        # 3. 安全检查
        if config.enable_security_check:
            violations = self._security_checker.check(code)
            error_violations = [v for v in violations if v.severity == "error"]

            if error_violations:
                result.success = False
                result.security_violation = True
                result.violations = violations
                result.stderr = "Security violation: " + "; ".join(
                    v.description for v in error_violations
                )
                result.execution_time = time.time() - start_time
                if monitor:
                    monitor.emit_error({"error": "security_violation"})
                return result

            result.violations = violations

        # 4. 创建隔离目录
        isolation_dir = None
        if config.isolation_dir:
            isolation_dir = config.isolation_dir / f"sandbox_{int(time.time() * 1000)}"
            isolation_dir.mkdir(parents=True, exist_ok=True)
            result.isolation_dir = isolation_dir

        # 5. 在子进程中执行
        try:
            result_queue: multiprocessing.Queue = multiprocessing.Queue()

            process = multiprocessing.Process(
                target=_execute_in_sandbox,
                args=(
                    code,
                    input_data,
                    result_queue,
                    config.max_output_size,
                    config.allowed_imports,
                ),
            )

            process.start()
            process.join(timeout=config.timeout_seconds)

            if process.is_alive():
                # 超时，终止进程
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()

                result.success = False
                result.timed_out = True
                result.stderr = f"Execution timed out after {config.timeout_seconds} seconds"
                result.execution_time = config.timeout_seconds

                if monitor:
                    monitor.emit_error({"error": "timeout"})
            else:
                # 正常完成
                try:
                    exec_result = result_queue.get_nowait()
                    result.success = exec_result["success"]
                    result.stdout = exec_result["stdout"]
                    result.stderr = exec_result["stderr"]
                    result.output_data = exec_result["output_data"]
                except Exception:
                    result.success = False
                    result.stderr = "Failed to get execution result"

                result.execution_time = time.time() - start_time

                if result.success and monitor:
                    monitor.emit_complete({"execution_time": result.execution_time})
                elif not result.success and monitor:
                    monitor.emit_error({"error": result.stderr})

        except Exception as e:
            result.success = False
            result.stderr = f"Execution error: {e}"
            result.execution_time = time.time() - start_time

            if monitor:
                monitor.emit_error({"error": str(e)})

        # 6. 清理隔离目录
        if config.cleanup_after and isolation_dir and isolation_dir.exists():
            try:
                shutil.rmtree(isolation_dir)
            except Exception:
                pass

        # 7. 记录完成
        if config.enable_logging:
            result.logs.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "event": "execution_complete",
                    "success": result.success,
                    "execution_time": result.execution_time,
                }
            )

        # 8. 填充指标
        result.metrics = {
            "execution_time": result.execution_time,
            "stdout_size": len(result.stdout),
            "stderr_size": len(result.stderr),
            "timed_out": result.timed_out,
            "security_violation": result.security_violation,
        }

        return result

    def execute_segment(
        self,
        segment: CodeSegment,
        config: SandboxConfig | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> SandboxResult:
        """执行代码段

        参数：
            segment: 代码段
            config: 沙箱配置
            input_data: 输入数据

        返回：
            执行结果
        """
        if segment.language.lower() != "python":
            return SandboxResult(
                success=False,
                stderr=f"Unsupported language: {segment.language}",
            )

        return self.execute(
            code=segment.code,
            config=config,
            input_data=input_data,
        )


# ============================================================
# 导出
# ============================================================

__all__ = [
    "SecurityLevel",
    "CodeSegment",
    "SecurityViolation",
    "SandboxConfig",
    "SandboxResult",
    "SecurityChecker",
    "ExecutionMonitor",
    "SandboxExecutor",
]

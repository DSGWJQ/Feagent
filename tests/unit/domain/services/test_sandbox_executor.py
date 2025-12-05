"""沙箱执行器测试 - 动态代码注入与安全执行

TDD Red Phase: 先编写失败测试用例，再实现功能

测试覆盖：
1. 动态代码段结构测试
2. 沙箱执行器基础功能测试
3. 安全检查器测试（恶意代码检测）
4. 资源限制测试（超时、内存）
5. Agent 集成流程测试
6. 执行日志与监控测试
"""

from pathlib import Path

# 导入待测试模块（TDD Red 阶段可能不存在）
# from src.domain.services.sandbox_executor import (
#     SandboxExecutor,
#     SandboxConfig,
#     SandboxResult,
#     CodeSegment,
#     SecurityChecker,
#     SecurityViolation,
# )


# ============================================================
# 测试 1: 动态代码段结构
# ============================================================


class TestCodeSegmentStructure:
    """动态代码段结构测试"""

    def test_code_segment_with_python_language(self):
        """测试：Python 语言代码段"""
        from src.domain.services.sandbox_executor import CodeSegment

        segment = CodeSegment(
            language="python",
            code="def main(data):\n    return data * 2",
            entry_function="main",
            dependencies=["numpy"],
        )

        assert segment.language == "python"
        assert segment.entry_function == "main"
        assert "numpy" in segment.dependencies

    def test_code_segment_default_entry_function(self):
        """测试：默认入口函数为 main"""
        from src.domain.services.sandbox_executor import CodeSegment

        segment = CodeSegment(
            language="python",
            code="result = 1 + 1",
        )

        assert segment.entry_function == "main"

    def test_code_segment_to_dict_serialization(self):
        """测试：代码段序列化"""
        from src.domain.services.sandbox_executor import CodeSegment

        segment = CodeSegment(
            language="python",
            code="print('hello')",
            entry_function="run",
            dependencies=["requests"],
        )

        data = segment.to_dict()
        assert data["language"] == "python"
        assert data["entry_function"] == "run"
        assert "requests" in data["dependencies"]

    def test_code_segment_from_dict_deserialization(self):
        """测试：代码段反序列化"""
        from src.domain.services.sandbox_executor import CodeSegment

        data = {
            "language": "python",
            "code": "x = 1",
            "entry_function": "process",
            "dependencies": ["pandas"],
        }

        segment = CodeSegment.from_dict(data)
        assert segment.language == "python"
        assert segment.entry_function == "process"


# ============================================================
# 测试 2: 安全检查器
# ============================================================


class TestSecurityChecker:
    """安全检查器测试"""

    def test_detect_import_os_system(self):
        """测试：检测 os.system 调用"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
import os
os.system('rm -rf /')
"""
        violations = checker.check(code)

        assert len(violations) > 0
        assert any(
            "os.system" in v.description.lower() or "dangerous" in v.description.lower()
            for v in violations
        )

    def test_detect_subprocess_call(self):
        """测试：检测 subprocess 调用"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
import subprocess
subprocess.run(['ls', '-la'])
"""
        violations = checker.check(code)

        assert len(violations) > 0
        assert any("subprocess" in v.description.lower() for v in violations)

    def test_detect_eval_exec(self):
        """测试：检测 eval/exec 调用"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
user_input = "print('hacked')"
eval(user_input)
"""
        violations = checker.check(code)

        assert len(violations) > 0
        assert any("eval" in v.description.lower() for v in violations)

    def test_detect_file_write_operations(self):
        """测试：检测文件写入操作"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
with open('/etc/passwd', 'w') as f:
    f.write('hacked')
"""
        violations = checker.check(code)

        assert len(violations) > 0
        assert any(
            "file" in v.description.lower() or "write" in v.description.lower() for v in violations
        )

    def test_detect_network_socket(self):
        """测试：检测网络 socket 操作"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
import socket
s = socket.socket()
s.connect(('evil.com', 80))
"""
        violations = checker.check(code)

        assert len(violations) > 0
        assert any(
            "socket" in v.description.lower() or "network" in v.description.lower()
            for v in violations
        )

    def test_safe_code_passes_check(self):
        """测试：安全代码通过检查"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
def calculate(x, y):
    return x + y

result = calculate(1, 2)
print(result)
"""
        violations = checker.check(code)

        assert len(violations) == 0

    def test_detect_infinite_loop_pattern(self):
        """测试：检测无限循环模式"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
while True:
    pass
"""
        violations = checker.check(code)

        # 无限循环应该被标记为警告
        assert len(violations) > 0
        assert any(
            "infinite" in v.description.lower() or "loop" in v.description.lower()
            for v in violations
        )

    def test_detect_memory_bomb(self):
        """测试：检测内存炸弹"""
        from src.domain.services.sandbox_executor import SecurityChecker

        checker = SecurityChecker()
        code = """
data = 'x' * (10 ** 10)
"""
        violations = checker.check(code)

        assert len(violations) > 0
        assert any(
            "memory" in v.description.lower()
            or "resource" in v.description.lower()
            or "bomb" in v.description.lower()
            or "power" in v.description.lower()
            for v in violations
        )


# ============================================================
# 测试 3: 沙箱配置
# ============================================================


class TestSandboxConfig:
    """沙箱配置测试"""

    def test_default_config_values(self):
        """测试：默认配置值"""
        from src.domain.services.sandbox_executor import SandboxConfig

        config = SandboxConfig()

        assert config.timeout_seconds > 0
        assert config.max_memory_mb > 0
        assert config.max_output_size > 0

    def test_config_with_custom_timeout(self):
        """测试：自定义超时配置"""
        from src.domain.services.sandbox_executor import SandboxConfig

        config = SandboxConfig(timeout_seconds=10)

        assert config.timeout_seconds == 10

    def test_config_with_allowed_imports(self):
        """测试：允许的导入列表"""
        from src.domain.services.sandbox_executor import SandboxConfig

        config = SandboxConfig(allowed_imports=["math", "json", "datetime"])

        assert "math" in config.allowed_imports
        assert "os" not in config.allowed_imports

    def test_config_isolation_directory(self):
        """测试：隔离目录配置"""
        from src.domain.services.sandbox_executor import SandboxConfig

        config = SandboxConfig(isolation_dir=Path("/tmp/sandbox"))

        assert config.isolation_dir == Path("/tmp/sandbox")


# ============================================================
# 测试 4: 沙箱执行器基础功能
# ============================================================


class TestSandboxExecutorBasic:
    """沙箱执行器基础功能测试"""

    def test_execute_simple_code(self):
        """测试：执行简单代码"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5)

        result = executor.execute(
            code="result = 1 + 1\nprint(result)",
            config=config,
        )

        assert result.success is True
        assert "2" in result.stdout

    def test_execute_with_input_data(self):
        """测试：带输入数据执行"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5)

        result = executor.execute(
            code="result = input_data['value'] * 2\nprint(result)",
            config=config,
            input_data={"value": 21},
        )

        assert result.success is True
        assert "42" in result.stdout

    def test_execute_returns_output_data(self):
        """测试：执行返回输出数据"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5)

        result = executor.execute(
            code="output = {'result': 100}",
            config=config,
        )

        assert result.success is True
        assert result.output_data.get("result") == 100

    def test_execute_captures_exception(self):
        """测试：捕获执行异常"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5)

        result = executor.execute(
            code="raise ValueError('test error')",
            config=config,
        )

        assert result.success is False
        assert "ValueError" in result.stderr or "test error" in result.stderr


# ============================================================
# 测试 5: 资源限制
# ============================================================


class TestSandboxResourceLimits:
    """资源限制测试"""

    def test_timeout_kills_infinite_loop(self):
        """测试：超时终止无限循环"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=2)

        result = executor.execute(
            code="while True: pass",
            config=config,
        )

        assert result.success is False
        assert result.timed_out is True
        assert result.execution_time <= config.timeout_seconds + 1

    def test_memory_limit_prevents_memory_bomb(self):
        """测试：内存限制阻止内存炸弹（通过安全检查）"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(
            timeout_seconds=5,
            max_memory_mb=50,  # 50MB 限制
            enable_security_check=True,  # 启用安全检查
        )

        # 使用包含大幂运算的代码，会被安全检查拒绝
        result = executor.execute(
            code="data = 'x' * (10 ** 10)",  # 10^10 会被检测为资源炸弹
            config=config,
        )

        # 应该因为安全检查失败
        assert result.success is False
        assert result.security_violation is True or "MemoryError" in result.stderr

    def test_output_size_limit(self):
        """测试：输出大小限制"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(
            timeout_seconds=5,
            max_output_size=1000,  # 1KB 限制
        )

        result = executor.execute(
            code="print('x' * 10000)",  # 尝试输出 10KB
            config=config,
        )

        # 输出应被截断
        assert len(result.stdout) <= config.max_output_size + 100


# ============================================================
# 测试 6: 安全执行（恶意代码拒绝）
# ============================================================


class TestSandboxSecurityExecution:
    """安全执行测试"""

    def test_reject_os_system_code(self):
        """测试：拒绝执行 os.system 代码"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(enable_security_check=True)

        result = executor.execute(
            code="import os\nos.system('ls')",
            config=config,
        )

        assert result.success is False
        assert result.security_violation is True

    def test_reject_subprocess_code(self):
        """测试：拒绝执行 subprocess 代码"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(enable_security_check=True)

        result = executor.execute(
            code="import subprocess\nsubprocess.run(['ls'])",
            config=config,
        )

        assert result.success is False
        assert result.security_violation is True

    def test_allow_safe_imports(self):
        """测试：允许安全导入"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(
            enable_security_check=True,
            allowed_imports=["math", "json"],
        )

        result = executor.execute(
            code="import math\nresult = math.sqrt(16)\nprint(result)",
            config=config,
        )

        assert result.success is True
        assert "4" in result.stdout


# ============================================================
# 测试 7: 隔离目录
# ============================================================


class TestSandboxIsolation:
    """隔离目录测试"""

    def test_code_written_to_isolation_dir(self):
        """测试：代码写入隔离目录"""
        import tempfile

        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = SandboxExecutor()
            config = SandboxConfig(
                isolation_dir=Path(tmpdir),
                timeout_seconds=5,
            )

            result = executor.execute(
                code="print('isolated')",
                config=config,
            )

            # 检查隔离目录中是否有执行痕迹
            assert result.success is True
            assert result.isolation_dir is not None

    def test_isolation_dir_cleaned_after_execution(self):
        """测试：执行后清理隔离目录"""
        import tempfile

        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = SandboxExecutor()
            config = SandboxConfig(
                isolation_dir=Path(tmpdir),
                cleanup_after=True,
            )

            result = executor.execute(
                code="print('test')",
                config=config,
            )

            # 执行目录应被清理
            if result.isolation_dir:
                assert (
                    not result.isolation_dir.exists()
                    or len(list(result.isolation_dir.iterdir())) == 0
                )


# ============================================================
# 测试 8: Agent 集成流程
# ============================================================


class TestAgentIntegration:
    """Agent 集成流程测试"""

    def test_conversation_agent_generates_code(self):
        """测试：ConversationAgent 生成代码"""
        from src.domain.services.sandbox_executor import CodeSegment

        # 模拟 ConversationAgent 生成的代码
        generated_code = """
def main(input_data):
    value = input_data.get('number', 0)
    return {'doubled': value * 2}
"""
        segment = CodeSegment(
            language="python",
            code=generated_code,
            entry_function="main",
        )

        assert segment.code is not None
        assert "def main" in segment.code

    def test_workflow_agent_executes_via_sandbox(self):
        """测试：WorkflowAgent 通过沙箱执行"""
        from src.domain.services.sandbox_executor import (
            CodeSegment,
            SandboxConfig,
            SandboxExecutor,
        )

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5)

        segment = CodeSegment(
            language="python",
            code="output = {'status': 'completed'}",
            entry_function="main",
        )

        result = executor.execute_segment(segment, config)

        assert result.success is True
        assert result.output_data.get("status") == "completed"

    def test_coordinator_monitors_execution(self):
        """测试：Coordinator 监控执行"""
        from src.domain.services.sandbox_executor import (
            ExecutionMonitor,
            SandboxConfig,
            SandboxExecutor,
        )

        executor = SandboxExecutor()
        monitor = ExecutionMonitor()
        config = SandboxConfig(timeout_seconds=5)

        # 注册监控回调
        events = []
        monitor.on_start(lambda e: events.append(("start", e)))
        monitor.on_complete(lambda e: events.append(("complete", e)))
        monitor.on_error(lambda e: events.append(("error", e)))

        result = executor.execute(
            code="print('monitored')",
            config=config,
            monitor=monitor,
        )

        assert result.success is True
        assert any(e[0] == "start" for e in events)
        assert any(e[0] == "complete" for e in events)


# ============================================================
# 测试 9: 执行日志
# ============================================================


class TestExecutionLogging:
    """执行日志测试"""

    def test_execution_logs_captured(self):
        """测试：执行日志被捕获"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5, enable_logging=True)

        result = executor.execute(
            code="print('step 1')\nprint('step 2')",
            config=config,
        )

        assert result.success is True
        assert len(result.logs) > 0

    def test_execution_logs_include_timestamps(self):
        """测试：执行日志包含时间戳"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5, enable_logging=True)

        result = executor.execute(
            code="print('timed')",
            config=config,
        )

        if result.logs:
            assert "timestamp" in result.logs[0] or "time" in result.logs[0]

    def test_execution_result_includes_metrics(self):
        """测试：执行结果包含指标"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5)

        result = executor.execute(
            code="x = sum(range(1000))",
            config=config,
        )

        assert result.execution_time >= 0
        assert hasattr(result, "memory_used") or result.metrics is not None


# ============================================================
# 测试 10: 边界条件
# ============================================================


class TestSandboxEdgeCases:
    """边界条件测试"""

    def test_empty_code_returns_error(self):
        """测试：空代码返回错误"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig()

        result = executor.execute(code="", config=config)

        assert result.success is False

    def test_syntax_error_captured(self):
        """测试：语法错误被捕获"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig()

        result = executor.execute(
            code="def broken(",
            config=config,
        )

        assert result.success is False
        assert "SyntaxError" in result.stderr

    def test_unicode_code_supported(self):
        """测试：支持 Unicode 代码"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(timeout_seconds=5)

        result = executor.execute(
            code="message = '你好世界'\nprint(message)",
            config=config,
        )

        assert result.success is True
        assert "你好世界" in result.stdout

    def test_large_output_handled(self):
        """测试：处理大输出"""
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        executor = SandboxExecutor()
        config = SandboxConfig(
            timeout_seconds=5,
            max_output_size=10000,
        )

        result = executor.execute(
            code="for i in range(100): print(f'line {i}')",
            config=config,
        )

        assert result.success is True
        assert len(result.stdout) > 0

"""GAP-004: 代码修复循环测试

测试目标：验证 CodeRepair 模块能够自动修复执行失败的代码
- 错误分析
- LLM 辅助修复
- 修复验证和重试

TDD 阶段：Red（测试先行）
"""

from unittest.mock import AsyncMock, Mock

import pytest


class TestCodeRepairService:
    """代码修复服务测试"""

    def test_code_repair_service_exists(self):
        """测试 CodeRepair 服务存在"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()
        assert service is not None

    def test_code_repair_has_repair_method(self):
        """测试 CodeRepair 有修复方法"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()
        assert hasattr(service, "repair_code"), "应该有 repair_code 方法"
        assert hasattr(service, "analyze_error"), "应该有 analyze_error 方法"


class TestErrorAnalysis:
    """错误分析测试"""

    def test_analyze_syntax_error(self):
        """测试分析语法错误"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()

        code = """
def process(data):
    return data +  # 语法错误：缺少操作数
"""
        error = SyntaxError("invalid syntax")

        analysis = service.analyze_error(code, error)

        assert analysis is not None
        assert analysis["error_type"] == "syntax"
        assert "location" in analysis or "line" in analysis

    def test_analyze_name_error(self):
        """测试分析未定义变量错误"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()

        code = """
def process(data):
    return undefined_variable
"""
        error = NameError("name 'undefined_variable' is not defined")

        analysis = service.analyze_error(code, error)

        assert analysis is not None
        assert analysis["error_type"] == "name"
        assert "undefined_variable" in analysis.get("missing_name", "")

    def test_analyze_type_error(self):
        """测试分析类型错误"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()

        code = """
def process(data):
    return "string" + 123
"""
        error = TypeError('can only concatenate str (not "int") to str')

        analysis = service.analyze_error(code, error)

        assert analysis is not None
        assert analysis["error_type"] == "type"

    def test_analyze_import_error(self):
        """测试分析导入错误"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()

        code = """
import nonexistent_module
"""
        error = ModuleNotFoundError("No module named 'nonexistent_module'")

        analysis = service.analyze_error(code, error)

        assert analysis is not None
        assert analysis["error_type"] == "import"
        assert "nonexistent_module" in analysis.get("module_name", "")


class TestCodeRepairWithLLM:
    """LLM 辅助代码修复测试"""

    @pytest.fixture
    def mock_llm(self):
        """创建模拟 LLM"""
        llm = Mock()
        llm.repair_code = AsyncMock(
            return_value="""
def process(data):
    return data + 1
"""
        )
        return llm

    @pytest.mark.asyncio
    async def test_repair_syntax_error_with_llm(self, mock_llm):
        """测试使用 LLM 修复语法错误"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair(llm=mock_llm)

        original_code = """
def process(data):
    return data +
"""
        error = SyntaxError("invalid syntax")

        repaired_code = await service.repair_code(original_code, error)

        assert repaired_code is not None
        assert repaired_code != original_code
        # 修复后的代码应该能解析
        compile(repaired_code, "<string>", "exec")

    @pytest.mark.asyncio
    async def test_repair_includes_context(self, mock_llm):
        """测试修复时包含上下文信息"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair(llm=mock_llm)

        original_code = "def f(): return x"
        error = NameError("name 'x' is not defined")
        context = {"available_variables": ["data", "config"], "expected_output_type": "int"}

        await service.repair_code(original_code, error, context=context)

        # LLM 应该收到包含上下文的提示
        call_args = mock_llm.repair_code.call_args
        assert call_args is not None


class TestRepairValidation:
    """修复验证测试"""

    def test_validate_repaired_code_syntax(self):
        """测试验证修复代码语法"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()

        valid_code = "def f(): return 1"
        invalid_code = "def f(): return"

        assert service.validate_syntax(valid_code) is True
        assert service.validate_syntax(invalid_code) is False

    def test_validate_repaired_code_safety(self):
        """测试验证修复代码安全性"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair()

        safe_code = "def f(x): return x + 1"
        unsafe_code = "import os; os.system('rm -rf /')"

        assert service.validate_safety(safe_code) is True
        assert service.validate_safety(unsafe_code) is False

    @pytest.mark.asyncio
    async def test_repair_with_validation(self):
        """测试修复后自动验证"""
        from src.domain.services.code_repair import CodeRepair

        mock_llm = Mock()
        mock_llm.repair_code = AsyncMock(return_value="def f(): return 1")

        service = CodeRepair(llm=mock_llm)

        result = await service.repair_code(
            "def f(): return", SyntaxError("invalid syntax"), validate=True
        )

        assert result is not None
        # 返回的代码应该通过验证
        assert service.validate_syntax(result) is True


class TestRepairRetry:
    """修复重试测试"""

    @pytest.mark.asyncio
    async def test_retry_on_invalid_repair(self):
        """测试修复无效时重试"""
        from src.domain.services.code_repair import CodeRepair

        # 第一次返回无效代码，第二次返回有效代码
        mock_llm = Mock()
        mock_llm.repair_code = AsyncMock(
            side_effect=[
                "def f(): return",  # 无效
                "def f(): return 1",  # 有效
            ]
        )

        service = CodeRepair(llm=mock_llm, max_repair_attempts=3)

        result = await service.repair_code(
            "def f(): return", SyntaxError("invalid syntax"), validate=True
        )

        assert result is not None
        assert service.validate_syntax(result) is True
        assert mock_llm.repair_code.call_count == 2

    @pytest.mark.asyncio
    async def test_max_repair_attempts(self):
        """测试最大重试次数"""
        from src.domain.services.code_repair import CodeRepair

        mock_llm = Mock()
        mock_llm.repair_code = AsyncMock(return_value="def f(): return")  # 始终无效

        service = CodeRepair(llm=mock_llm, max_repair_attempts=3)

        result = await service.repair_code(
            "def f(): return", SyntaxError("invalid syntax"), validate=True
        )

        # 达到最大重试次数后应该返回 None 或抛出异常
        assert result is None or mock_llm.repair_code.call_count == 3


class TestRepairResult:
    """修复结果测试"""

    @pytest.mark.asyncio
    async def test_repair_result_structure(self):
        """测试修复结果结构"""
        from src.domain.services.code_repair import CodeRepair, RepairResult

        mock_llm = Mock()
        mock_llm.repair_code = AsyncMock(return_value="def f(): return 1")

        service = CodeRepair(llm=mock_llm)

        result = await service.repair_code_with_result(
            "def f(): return", SyntaxError("invalid syntax")
        )

        assert isinstance(result, RepairResult)
        assert hasattr(result, "success")
        assert hasattr(result, "repaired_code")
        assert hasattr(result, "original_code")
        assert hasattr(result, "error_analysis")
        assert hasattr(result, "attempts")

    @pytest.mark.asyncio
    async def test_repair_result_success(self):
        """测试修复成功结果"""
        from src.domain.services.code_repair import CodeRepair

        mock_llm = Mock()
        mock_llm.repair_code = AsyncMock(return_value="def f(): return 1")

        service = CodeRepair(llm=mock_llm)

        result = await service.repair_code_with_result(
            "def f(): return", SyntaxError("invalid syntax")
        )

        assert result.success is True
        assert result.repaired_code is not None
        assert result.attempts >= 1


class TestCoordinatorIntegration:
    """CoordinatorAgent 集成测试"""

    @pytest.mark.asyncio
    async def test_coordinator_handles_code_failure(self):
        """测试 CoordinatorAgent 处理代码执行失败"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 模拟代码执行失败
        failure_context = {
            "node_id": "test_node",
            "code": "def f(): return undefined",
            "error": NameError("name 'undefined' is not defined"),
            "execution_context": {"input_data": [1, 2, 3]},
        }

        # Coordinator 应该能处理失败并尝试修复
        result = await coordinator.handle_code_execution_failure(**failure_context)

        assert result is not None
        assert "repair_attempted" in result or "action" in result

    @pytest.mark.asyncio
    async def test_coordinator_auto_repair_workflow(self):
        """测试 CoordinatorAgent 自动修复工作流"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 启用自动修复
        coordinator.enable_auto_repair(max_attempts=2)

        assert coordinator.auto_repair_enabled is True
        assert coordinator.max_repair_attempts == 2


class TestRepairFallback:
    """修复回退测试"""

    @pytest.mark.asyncio
    async def test_fallback_to_manual_intervention(self):
        """测试回退到手动干预"""
        from src.domain.services.code_repair import CodeRepair

        mock_llm = Mock()
        mock_llm.repair_code = AsyncMock(return_value=None)  # LLM 无法修复

        service = CodeRepair(llm=mock_llm, max_repair_attempts=1)

        result = await service.repair_code_with_result(
            "completely broken code @#$%", Exception("Unknown error")
        )

        assert result.success is False
        assert result.requires_manual_intervention is True

    @pytest.mark.asyncio
    async def test_fallback_without_llm(self):
        """测试没有 LLM 时的回退"""
        from src.domain.services.code_repair import CodeRepair

        service = CodeRepair(llm=None)  # 没有 LLM

        result = await service.repair_code_with_result(
            "def f(): return", SyntaxError("invalid syntax")
        )

        # 应该返回失败结果而不是抛出异常
        assert result.success is False
        assert result.error_message is not None

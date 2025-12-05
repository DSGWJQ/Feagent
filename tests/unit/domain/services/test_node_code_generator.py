"""节点代码生成器测试 (TDD Red Phase)

测试 ConversationAgent 代码生成与节点注册流程：
1. NodeGapAnalyzer - 分析现有节点是否满足需求
2. NodeCodeGenerator - 生成 YAML + 代码
3. NodeRegistrationService - 注册新节点到系统
4. ConversationAgent 集成 - 端到端测试
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ==================== 1. NodeGapAnalyzer 测试 ====================


class TestNodeGapAnalyzer:
    """测试节点缺口分析器"""

    def test_analyze_returns_no_gap_for_existing_node(self):
        """测试：现有节点能满足需求时返回无缺口"""
        from src.domain.services.node_code_generator import NodeGapAnalyzer

        analyzer = NodeGapAnalyzer()
        # 模拟现有节点列表
        existing_nodes = ["http_request", "json_parser", "data_transformer"]

        result = analyzer.analyze(
            task_description="发送 HTTP 请求获取数据",
            existing_nodes=existing_nodes,
        )

        assert result.has_gap is False
        assert result.missing_capabilities == []

    def test_analyze_detects_gap_for_new_capability(self):
        """测试：需要新功能时检测到缺口"""
        from src.domain.services.node_code_generator import NodeGapAnalyzer

        analyzer = NodeGapAnalyzer()
        existing_nodes = ["http_request", "json_parser"]

        result = analyzer.analyze(
            task_description="计算股票的移动平均线指标",
            existing_nodes=existing_nodes,
        )

        assert result.has_gap is True
        assert len(result.missing_capabilities) > 0
        assert (
            "moving_average" in result.suggested_node_name.lower()
            or "stock" in result.suggested_node_name.lower()
        )

    def test_analyze_extracts_required_parameters(self):
        """测试：从任务描述中提取所需参数"""
        from src.domain.services.node_code_generator import NodeGapAnalyzer

        analyzer = NodeGapAnalyzer()
        existing_nodes = []

        result = analyzer.analyze(
            task_description="根据输入的价格列表和周期数计算移动平均值",
            existing_nodes=existing_nodes,
        )

        assert result.has_gap is True
        # 应该推断出 prices 和 period 参数
        assert (
            "prices" in result.inferred_parameters
            or "price" in str(result.inferred_parameters).lower()
        )
        assert "period" in result.inferred_parameters or "周期" in str(result.inferred_parameters)

    def test_analyze_suggests_language_based_on_task(self):
        """测试：根据任务类型建议编程语言"""
        from src.domain.services.node_code_generator import NodeGapAnalyzer

        analyzer = NodeGapAnalyzer()

        # 数据计算任务 -> Python
        result1 = analyzer.analyze(
            task_description="使用 numpy 计算矩阵乘法",
            existing_nodes=[],
        )
        assert result1.suggested_language == "python"

        # 前端处理任务 -> JavaScript
        result2 = analyzer.analyze(
            task_description="处理 DOM 元素并更新页面",
            existing_nodes=[],
        )
        assert result2.suggested_language == "javascript"

    def test_analyze_with_context_from_coordinator(self):
        """测试：使用协调者上下文进行更精确分析"""
        from src.domain.services.node_code_generator import NodeGapAnalyzer

        analyzer = NodeGapAnalyzer()

        # 提供协调者上下文（可用工具、知识库等）
        coordinator_context = {
            "available_tools": ["calculator", "text_parser"],
            "knowledge_hints": ["金融领域", "技术指标"],
        }

        result = analyzer.analyze(
            task_description="计算 RSI 指标",
            existing_nodes=[],
            coordinator_context=coordinator_context,
        )

        assert result.has_gap is True
        assert "rsi" in result.suggested_node_name.lower()


# ==================== 2. NodeCodeGenerator 测试 ====================


class TestNodeCodeGenerator:
    """测试节点代码生成器"""

    def test_generate_yaml_for_python_node(self):
        """测试：生成 Python 节点的 YAML 定义"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        result = generator.generate_yaml(
            node_name="moving_average_calculator",
            description="计算移动平均值",
            language="python",
            parameters=[
                {"name": "prices", "type": "array", "description": "价格列表", "required": True},
                {
                    "name": "period",
                    "type": "integer",
                    "description": "周期",
                    "required": True,
                    "default": 5,
                },
            ],
            returns={"type": "object", "properties": {"average": {"type": "number"}}},
        )

        assert result.yaml_content is not None
        assert "name: moving_average_calculator" in result.yaml_content
        assert "kind: node" in result.yaml_content
        assert "parameters:" in result.yaml_content
        assert "prices" in result.yaml_content
        assert "period" in result.yaml_content

    def test_generate_yaml_with_valid_schema(self):
        """测试：生成的 YAML 符合节点定义 Schema"""
        import yaml

        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        result = generator.generate_yaml(
            node_name="test_node",
            description="测试节点",
            language="python",
            parameters=[{"name": "input", "type": "string", "required": True}],
            returns={"type": "string"},
        )

        # 解析 YAML 验证格式正确
        parsed = yaml.safe_load(result.yaml_content)
        assert parsed["name"] == "test_node"
        assert parsed["kind"] == "node"
        assert "parameters" in parsed
        assert "returns" in parsed

    def test_generate_code_for_python(self):
        """测试：生成 Python 代码"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        result = generator.generate_code(
            node_name="moving_average",
            language="python",
            description="计算移动平均值",
            parameters=[
                {"name": "prices", "type": "array"},
                {"name": "period", "type": "integer", "default": 5},
            ],
            logic_hint="对价格列表取最后 period 个值求平均",
        )

        assert result.code is not None
        assert "def main" in result.code or "def execute" in result.code
        assert "prices" in result.code
        assert "period" in result.code
        # 应该包含计算逻辑
        assert "return" in result.code

    def test_generate_code_for_javascript(self):
        """测试：生成 JavaScript 代码"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        result = generator.generate_code(
            node_name="dom_processor",
            language="javascript",
            description="处理 DOM 元素",
            parameters=[{"name": "selector", "type": "string"}],
            logic_hint="根据选择器查找元素",
        )

        assert result.code is not None
        assert "function" in result.code or "=>" in result.code
        assert "selector" in result.code

    def test_generate_code_includes_error_handling(self):
        """测试：生成的代码包含错误处理"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        result = generator.generate_code(
            node_name="safe_calculator",
            language="python",
            description="安全计算器",
            parameters=[{"name": "a", "type": "number"}, {"name": "b", "type": "number"}],
            logic_hint="计算 a 除以 b",
        )

        # 应该包含异常处理
        assert "try" in result.code or "except" in result.code or "if" in result.code

    def test_generate_code_with_sandbox_compliance(self):
        """测试：生成的代码符合沙箱安全要求"""
        from src.domain.services.node_code_generator import NodeCodeGenerator
        from src.domain.services.sandbox_executor import SecurityChecker

        generator = NodeCodeGenerator()
        checker = SecurityChecker()

        result = generator.generate_code(
            node_name="data_processor",
            language="python",
            description="数据处理器",
            parameters=[{"name": "data", "type": "object"}],
            logic_hint="处理输入数据",
        )

        # 生成的代码应该通过安全检查
        violations = checker.check(result.code)
        assert len(violations) == 0, f"Security violations: {violations}"

    def test_generate_complete_node_definition(self):
        """测试：生成完整的节点定义（YAML + 代码）"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        result = generator.generate_complete(
            node_name="stock_analyzer",
            description="股票分析节点",
            language="python",
            parameters=[
                {"name": "symbol", "type": "string", "description": "股票代码"},
                {"name": "days", "type": "integer", "default": 30},
            ],
            logic_hint="分析股票数据",
        )

        assert result.yaml_content is not None
        assert result.code is not None
        assert result.node_name == "stock_analyzer"
        assert result.is_valid is True

    def test_parameter_type_inference(self):
        """测试：参数类型推断"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        # 从描述推断参数类型
        params = generator.infer_parameters("计算价格列表的平均值，周期默认为5天")

        assert len(params) >= 2
        # 检查推断出的参数
        param_names = [p["name"] for p in params]
        assert any("price" in name.lower() or "价格" in name for name in param_names)

    def test_language_selection_heuristics(self):
        """测试：语言选择启发式规则"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        # 数据科学任务 -> Python
        lang1 = generator.suggest_language("使用 pandas 分析数据框")
        assert lang1 == "python"

        # 数学计算 -> Python
        lang2 = generator.suggest_language("计算标准差和方差")
        assert lang2 == "python"

        # 前端任务 -> JavaScript
        lang3 = generator.suggest_language("操作浏览器 localStorage")
        assert lang3 == "javascript"


# ==================== 3. NodeRegistrationService 测试 ====================


class TestNodeRegistrationService:
    """测试节点注册服务"""

    def test_write_yaml_to_definitions_directory(self):
        """测试：将 YAML 写入定义目录"""
        from src.domain.services.node_code_generator import NodeRegistrationService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = NodeRegistrationService(definitions_dir=tmpdir)

            yaml_content = """
name: test_node
kind: node
description: 测试节点
parameters:
  - name: input
    type: string
"""
            result = service.write_definition(
                node_name="test_node",
                yaml_content=yaml_content,
            )

            assert result.success is True
            assert result.file_path is not None
            assert Path(result.file_path).exists()
            assert Path(result.file_path).name == "test_node.yaml"

    def test_write_code_to_scripts_directory(self):
        """测试：将代码写入脚本目录"""
        from src.domain.services.node_code_generator import NodeRegistrationService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = NodeRegistrationService(definitions_dir=tmpdir, scripts_dir=tmpdir)

            code = """
def main(input_data):
    return {"result": input_data}
"""
            result = service.write_code(
                node_name="test_node",
                code=code,
                language="python",
            )

            assert result.success is True
            assert result.file_path is not None
            assert Path(result.file_path).exists()
            assert Path(result.file_path).suffix == ".py"

    def test_register_node_to_registry(self):
        """测试：注册节点到 NodeRegistry"""
        from src.domain.services.node_code_generator import NodeRegistrationService
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        service = NodeRegistrationService(registry=registry)

        # 注册新节点
        result = service.register_to_registry(
            node_name="custom_processor",
            node_type="code",
            schema={
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string", "default": "python"},
                },
                "required": ["code"],
            },
        )

        assert result.success is True
        # 验证注册成功
        all_types = registry.get_all_types()
        # 至少包含预定义类型
        assert len(all_types) > 0

    def test_rollback_on_failure(self):
        """测试：注册失败时回滚"""
        from src.domain.services.node_code_generator import NodeRegistrationService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = NodeRegistrationService(definitions_dir=tmpdir)

            yaml_content = """
name: rollback_test
kind: node
"""
            # 先写入文件
            service.write_definition(node_name="rollback_test", yaml_content=yaml_content)

            # 执行回滚
            service.rollback(node_name="rollback_test")

            # 验证文件被删除
            yaml_path = Path(tmpdir) / "rollback_test.yaml"
            assert not yaml_path.exists()

    def test_complete_registration_flow(self):
        """测试：完整注册流程"""
        from src.domain.services.node_code_generator import (
            NodeCodeGenerator,
            NodeRegistrationService,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = NodeCodeGenerator()
            service = NodeRegistrationService(definitions_dir=tmpdir, scripts_dir=tmpdir)

            # 生成完整定义
            gen_result = generator.generate_complete(
                node_name="integration_test_node",
                description="集成测试节点",
                language="python",
                parameters=[{"name": "value", "type": "number"}],
                logic_hint="返回输入值的两倍",
            )

            # 注册到系统
            reg_result = service.register_complete(
                node_name=gen_result.node_name,
                yaml_content=gen_result.yaml_content,
                code=gen_result.code,
                language="python",
            )

            assert reg_result.success is True
            assert reg_result.yaml_path is not None
            assert reg_result.code_path is not None

    def test_prevent_duplicate_registration(self):
        """测试：防止重复注册"""
        from src.domain.services.node_code_generator import NodeRegistrationService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = NodeRegistrationService(definitions_dir=tmpdir)

            yaml_content = "name: duplicate_test\nkind: node"

            # 第一次注册
            result1 = service.write_definition(
                node_name="duplicate_test", yaml_content=yaml_content
            )
            assert result1.success is True

            # 第二次注册应该失败或返回警告
            result2 = service.write_definition(
                node_name="duplicate_test", yaml_content=yaml_content, overwrite=False
            )
            assert result2.success is False or result2.already_exists is True


# ==================== 4. ConversationAgent 集成测试 ====================


class TestConversationAgentCodeGeneration:
    """测试 ConversationAgent 代码生成集成"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="分析用户需求...")
        llm.decide_action = AsyncMock(
            return_value={
                "action_type": "generate_node",
                "node_spec": {
                    "name": "custom_calculator",
                    "description": "自定义计算器",
                    "parameters": [{"name": "values", "type": "array"}],
                    "logic": "计算数组和",
                },
            }
        )
        llm.should_continue = AsyncMock(return_value=False)
        return llm

    @pytest.fixture
    def temp_definitions_dir(self):
        """创建临时定义目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_conversation_agent_detects_new_node_need(self, mock_llm, temp_definitions_dir):
        """测试：ConversationAgent 检测到需要新节点"""
        from src.domain.services.node_code_generator import NodeGapAnalyzer

        # 模拟 ConversationAgent 的规划阶段
        analyzer = NodeGapAnalyzer()

        # 用户请求一个不存在的功能
        user_request = "帮我创建一个能计算股票 MACD 指标的功能"

        result = analyzer.analyze(
            task_description=user_request,
            existing_nodes=["http_request", "json_parser"],
        )

        assert result.has_gap is True
        assert "macd" in result.suggested_node_name.lower()

    def test_conversation_agent_generates_node_on_gap(self, mock_llm, temp_definitions_dir):
        """测试：检测到缺口时自动生成节点"""
        from src.domain.services.node_code_generator import (
            NodeCodeGenerator,
            NodeGapAnalyzer,
            NodeRegistrationService,
        )

        analyzer = NodeGapAnalyzer()
        generator = NodeCodeGenerator()
        service = NodeRegistrationService(
            definitions_dir=temp_definitions_dir, scripts_dir=temp_definitions_dir
        )

        # 分析缺口
        gap_result = analyzer.analyze(
            task_description="计算数据的移动平均",
            existing_nodes=[],
        )

        assert gap_result.has_gap is True

        # 生成节点
        gen_result = generator.generate_complete(
            node_name=gap_result.suggested_node_name,
            description=gap_result.missing_capabilities[0]
            if gap_result.missing_capabilities
            else "计算功能",
            language=gap_result.suggested_language,
            parameters=gap_result.inferred_parameters,
            logic_hint="实现移动平均计算",
        )

        # 注册节点
        reg_result = service.register_complete(
            node_name=gen_result.node_name,
            yaml_content=gen_result.yaml_content,
            code=gen_result.code,
            language=gap_result.suggested_language,
        )

        assert reg_result.success is True

    def test_end_to_end_new_functionality_request(self, mock_llm, temp_definitions_dir):
        """端到端测试：请求新功能时不报错并生成节点"""
        from src.domain.services.node_code_generator import ConversationAgentCodeGenExtension

        extension = ConversationAgentCodeGenExtension(
            definitions_dir=temp_definitions_dir,
            scripts_dir=temp_definitions_dir,
        )

        # 模拟用户请求新功能
        user_request = "我需要一个能够计算斐波那契数列的节点"

        # 处理请求（不应报错）
        result = extension.handle_new_functionality_request(
            user_request=user_request,
            existing_nodes=["basic_math", "string_processor"],
        )

        assert result.success is True
        assert result.generated_node_name is not None
        assert Path(temp_definitions_dir).glob("*.yaml")

    def test_generated_node_is_executable(self, temp_definitions_dir):
        """测试：生成的节点可以被执行"""
        from src.domain.services.node_code_generator import NodeCodeGenerator
        from src.domain.services.sandbox_executor import SandboxConfig, SandboxExecutor

        generator = NodeCodeGenerator()
        executor = SandboxExecutor()

        # 生成代码
        result = generator.generate_code(
            node_name="sum_calculator",
            language="python",
            description="计算列表求和",
            parameters=[{"name": "numbers", "type": "array"}],
            logic_hint="计算 numbers 列表中所有数字的和",
        )

        # 在沙箱中执行
        config = SandboxConfig(timeout_seconds=5)
        exec_result = executor.execute(
            code=result.code,
            config=config,
            input_data={"numbers": [1, 2, 3, 4, 5]},
        )

        # 验证执行成功
        assert exec_result.success is True or exec_result.output is not None

    def test_rollback_on_generation_failure(self, temp_definitions_dir):
        """测试：生成失败时回滚"""
        from src.domain.services.node_code_generator import (
            NodeCodeGenerator,
            NodeRegistrationService,
        )

        generator = NodeCodeGenerator()
        service = NodeRegistrationService(
            definitions_dir=temp_definitions_dir, scripts_dir=temp_definitions_dir
        )

        # 先写入一个文件
        service.write_definition(
            node_name="to_rollback", yaml_content="name: to_rollback\nkind: node"
        )

        # 模拟生成失败
        try:
            # 触发异常（传入无效参数）
            generator.generate_complete(
                node_name="",  # 无效名称
                description="",
                language="invalid_language",
                parameters=[],
                logic_hint="",
            )
        except (ValueError, Exception):
            # 执行回滚
            service.rollback(node_name="to_rollback")

        # 验证文件被清理
        assert not (Path(temp_definitions_dir) / "to_rollback.yaml").exists()


# ==================== 5. Prompt 模板测试 ====================


class TestNodeGenerationPrompts:
    """测试节点生成的 Prompt 模板"""

    def test_prompt_includes_node_specification(self):
        """测试：Prompt 包含节点规范"""
        from src.domain.services.node_code_generator import NodeGenerationPrompts

        prompts = NodeGenerationPrompts()

        system_prompt = prompts.get_system_prompt()

        # 应包含节点规范说明
        assert "node" in system_prompt.lower()
        assert "yaml" in system_prompt.lower() or "定义" in system_prompt

    def test_prompt_includes_available_tools(self):
        """测试：Prompt 包含可用工具接口"""
        from src.domain.services.node_code_generator import NodeGenerationPrompts

        prompts = NodeGenerationPrompts()

        available_tools = ["http_request", "json_parser", "data_transformer"]
        prompt = prompts.get_analysis_prompt(
            task_description="处理数据",
            available_tools=available_tools,
        )

        # 应列出可用工具
        assert "http_request" in prompt
        assert "json_parser" in prompt

    def test_prompt_includes_sandbox_constraints(self):
        """测试：Prompt 包含沙箱约束"""
        from src.domain.services.node_code_generator import NodeGenerationPrompts

        prompts = NodeGenerationPrompts()

        code_gen_prompt = prompts.get_code_generation_prompt(
            node_name="test",
            language="python",
            parameters=[],
        )

        # 应包含安全约束提示
        assert (
            "安全" in code_gen_prompt
            or "sandbox" in code_gen_prompt.lower()
            or "禁止" in code_gen_prompt
        )

    def test_prompt_for_parameter_inference(self):
        """测试：参数推断的 Prompt"""
        from src.domain.services.node_code_generator import NodeGenerationPrompts

        prompts = NodeGenerationPrompts()

        prompt = prompts.get_parameter_inference_prompt(
            task_description="根据股票代码和日期范围查询历史价格"
        )

        assert "参数" in prompt or "parameter" in prompt.lower()
        assert "类型" in prompt or "type" in prompt.lower()


# ==================== 6. 边界情况测试 ====================


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_task_description(self):
        """测试：空任务描述"""
        from src.domain.services.node_code_generator import NodeGapAnalyzer

        analyzer = NodeGapAnalyzer()

        with pytest.raises(ValueError, match="任务描述不能为空|description"):
            analyzer.analyze(task_description="", existing_nodes=[])

    def test_invalid_language(self):
        """测试：无效的编程语言"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        with pytest.raises(ValueError, match="不支持的语言|language"):
            generator.generate_code(
                node_name="test",
                language="cobol",  # 不支持的语言
                description="测试",
                parameters=[],
                logic_hint="",
            )

    def test_node_name_sanitization(self):
        """测试：节点名称清理"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        # 包含特殊字符的名称应该被清理
        result = generator.generate_yaml(
            node_name="my-node@v1.0",  # 包含非法字符
            description="测试",
            language="python",
            parameters=[],
            returns={"type": "object"},
        )

        # 名称应该被规范化
        assert "@" not in result.yaml_content or "my_node" in result.yaml_content

    def test_very_long_code_generation(self):
        """测试：生成很长的代码"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        # 很多参数
        many_params = [{"name": f"param_{i}", "type": "string"} for i in range(20)]

        result = generator.generate_code(
            node_name="many_params_node",
            language="python",
            description="处理很多参数",
            parameters=many_params,
            logic_hint="处理所有输入参数",
        )

        assert result.code is not None
        # 代码应该包含所有参数
        for i in range(20):
            assert f"param_{i}" in result.code

    def test_unicode_in_description(self):
        """测试：描述中的 Unicode 字符"""
        from src.domain.services.node_code_generator import NodeCodeGenerator

        generator = NodeCodeGenerator()

        result = generator.generate_yaml(
            node_name="unicode_test",
            description="处理中文、日文（漢字）、韩文（한글）数据",
            language="python",
            parameters=[{"name": "text", "type": "string", "description": "输入文本 📝"}],
            returns={"type": "string"},
        )

        assert "中文" in result.yaml_content
        assert result.is_valid is True

"""提示词模板系统单元测试 (TDD)

测试四大模块的模板化设计：
1. 角色定义 (Role Definition)
2. 行为准则 (Behavior Guidelines)
3. 工具使用规范 (Tool Usage Specification)
4. 输出格式 (Output Format)

测试日期：2025-12-07
"""

from pathlib import Path

import pytest

# =============================================================================
# 第一部分：PromptModule 数据结构测试
# =============================================================================


class TestPromptModuleDataStructure:
    """测试 PromptModule 数据结构"""

    def test_prompt_module_has_required_fields(self) -> None:
        """测试：PromptModule 应该包含必需字段"""
        from src.domain.services.prompt_template_system import PromptModule

        module = PromptModule(
            name="role_definition",
            version="1.0.0",
            description="角色定义模块",
            template="你是一个{agent_name}，负责{responsibility}。",
            variables=["agent_name", "responsibility"],
            applicable_agents=["ConversationAgent", "WorkflowAgent"],
        )

        assert module.name == "role_definition"
        assert module.version == "1.0.0"
        assert module.description == "角色定义模块"
        assert "agent_name" in module.variables
        assert "ConversationAgent" in module.applicable_agents

    def test_prompt_module_extracts_variables_from_template(self) -> None:
        """测试：PromptModule 应该能从模板中提取变量"""
        from src.domain.services.prompt_template_system import PromptModule

        module = PromptModule(
            name="test",
            version="1.0.0",
            description="测试模块",
            template="Hello {name}, your task is {task_type}.",
            variables=[],  # 空列表，应该自动提取
            applicable_agents=[],
        )

        extracted = module.extract_variables()
        assert "name" in extracted
        assert "task_type" in extracted

    def test_prompt_module_validates_variables_match_template(self) -> None:
        """测试：声明的变量应该与模板中的变量匹配"""
        from src.domain.services.prompt_template_system import PromptModule

        module = PromptModule(
            name="test",
            version="1.0.0",
            description="测试模块",
            template="Hello {name}, your task is {task_type}.",
            variables=["name", "task_type"],
            applicable_agents=[],
        )

        assert module.validate_variables() is True

    def test_prompt_module_detects_missing_variables(self) -> None:
        """测试：检测模板中存在但未声明的变量"""
        from src.domain.services.prompt_template_system import PromptModule

        module = PromptModule(
            name="test",
            version="1.0.0",
            description="测试模块",
            template="Hello {name}, your task is {task_type}.",
            variables=["name"],  # 缺少 task_type
            applicable_agents=[],
        )

        missing = module.get_missing_variables()
        assert "task_type" in missing


# =============================================================================
# 第二部分：四大模块模板定义测试
# =============================================================================


class TestRoleDefinitionModule:
    """测试角色定义模块"""

    def test_role_definition_module_structure(self) -> None:
        """测试：角色定义模块应该有标准结构"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        module = registry.get_module("role_definition")
        assert module is not None
        assert module.name == "role_definition"
        assert "agent_name" in module.variables
        assert "responsibility" in module.variables
        assert "capabilities" in module.variables

    def test_role_definition_renders_correctly(self) -> None:
        """测试：角色定义模块应该正确渲染"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        result = registry.render_module(
            "role_definition",
            agent_name="智能助手",
            responsibility="帮助用户完成任务",
            capabilities="任务分解、工作流规划",
        )

        assert "智能助手" in result
        assert "帮助用户完成任务" in result
        assert "任务分解" in result


class TestBehaviorGuidelinesModule:
    """测试行为准则模块"""

    def test_behavior_guidelines_module_structure(self) -> None:
        """测试：行为准则模块应该有标准结构"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        module = registry.get_module("behavior_guidelines")
        assert module is not None
        assert "constraints" in module.variables
        assert "principles" in module.variables

    def test_behavior_guidelines_renders_correctly(self) -> None:
        """测试：行为准则模块应该正确渲染"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        result = registry.render_module(
            "behavior_guidelines",
            constraints="不执行危险操作",
            principles="安全第一、用户优先",
            forbidden_actions="删除系统文件、访问敏感数据",
        )

        assert "不执行危险操作" in result
        assert "安全第一" in result


class TestToolUsageModule:
    """测试工具使用规范模块"""

    def test_tool_usage_module_structure(self) -> None:
        """测试：工具使用规范模块应该有标准结构"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        module = registry.get_module("tool_usage")
        assert module is not None
        assert "allowed_tools" in module.variables
        assert "tool_descriptions" in module.variables

    def test_tool_usage_renders_correctly(self) -> None:
        """测试：工具使用规范模块应该正确渲染"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        result = registry.render_module(
            "tool_usage",
            allowed_tools="HTTP, LLM, DATABASE",
            tool_descriptions="HTTP: 发送请求; LLM: 调用模型; DATABASE: 查询数据",
            usage_examples="示例：使用 HTTP 工具获取 API 数据",
        )

        assert "HTTP" in result
        assert "LLM" in result
        assert "DATABASE" in result


class TestOutputFormatModule:
    """测试输出格式模块"""

    def test_output_format_module_structure(self) -> None:
        """测试：输出格式模块应该有标准结构"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        module = registry.get_module("output_format")
        assert module is not None
        assert "output_schema" in module.variables
        assert "format_type" in module.variables

    def test_output_format_renders_correctly(self) -> None:
        """测试：输出格式模块应该正确渲染"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        result = registry.render_module(
            "output_format",
            format_type="JSON",
            output_schema='{"type": "object", "properties": {...}}',
            examples='{"action": "execute", "node_id": "node_1"}',
        )

        assert "JSON" in result
        assert "action" in result


# =============================================================================
# 第三部分：模板组合与渲染测试
# =============================================================================


class TestPromptTemplateComposition:
    """测试模板组合功能"""

    def test_compose_multiple_modules(self) -> None:
        """测试：应该能组合多个模块生成完整提示词"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateComposer,
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        composer = PromptTemplateComposer(registry)
        result = composer.compose(
            modules=["role_definition", "behavior_guidelines"],
            variables={
                "agent_name": "ConversationAgent",
                "responsibility": "对话管理",
                "capabilities": "意图识别、目标分解",
                "constraints": "不执行危险操作",
                "principles": "用户优先",
                "forbidden_actions": "删除数据",
            },
        )

        assert "ConversationAgent" in result
        assert "对话管理" in result
        assert "不执行危险操作" in result

    def test_compose_all_four_modules(self) -> None:
        """测试：应该能组合全部四个模块"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateComposer,
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        composer = PromptTemplateComposer(registry)
        result = composer.compose(
            modules=[
                "role_definition",
                "behavior_guidelines",
                "tool_usage",
                "output_format",
            ],
            variables={
                # role_definition
                "agent_name": "WorkflowAgent",
                "responsibility": "工作流执行",
                "capabilities": "节点管理、DAG执行",
                # behavior_guidelines
                "constraints": "遵循DAG顺序",
                "principles": "可靠性优先",
                "forbidden_actions": "跳过必要节点",
                # tool_usage
                "allowed_tools": "HTTP, PYTHON, LLM",
                "tool_descriptions": "HTTP: API调用",
                "usage_examples": "示例代码",
                # output_format
                "format_type": "JSON",
                "output_schema": "{}",
                "examples": "{}",
            },
        )

        # 验证所有模块内容都被包含
        assert "WorkflowAgent" in result
        assert "遵循DAG顺序" in result
        assert "HTTP" in result
        assert "JSON" in result


# =============================================================================
# 第四部分：YAML 文件加载测试
# =============================================================================


class TestYAMLTemplateLoader:
    """测试 YAML 模板文件加载"""

    def test_load_template_from_yaml(self) -> None:
        """测试：应该能从 YAML 文件加载模板"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateLoader,
        )

        loader = PromptTemplateLoader()
        templates_dir = Path("docs/prompt_templates")

        if templates_dir.exists():
            module = loader.load_from_yaml(templates_dir / "role_definition.yaml")
            assert module is not None
            assert module.name == "role_definition"

    def test_load_all_templates_from_directory(self) -> None:
        """测试：应该能从目录加载所有模板"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateLoader,
        )

        loader = PromptTemplateLoader()
        templates_dir = Path("docs/prompt_templates")

        if templates_dir.exists():
            modules = loader.load_directory(templates_dir)
            assert len(modules) >= 4  # 至少四个模块


# =============================================================================
# 第五部分：模板验证测试
# =============================================================================


class TestPromptTemplateValidator:
    """测试模板验证器"""

    def test_validate_template_syntax(self) -> None:
        """测试：应该能验证模板语法"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateValidator,
        )

        validator = PromptTemplateValidator()

        # 有效模板
        valid_result = validator.validate_syntax("Hello {name}, task: {task}")
        assert valid_result.is_valid is True

        # 无效模板 - 未闭合的括号
        invalid_result = validator.validate_syntax("Hello {name, task: {task}")
        assert invalid_result.is_valid is False

    def test_validate_variables_completeness(self) -> None:
        """测试：应该能验证变量完整性"""
        from src.domain.services.prompt_template_system import (
            PromptModule,
            PromptTemplateValidator,
        )

        validator = PromptTemplateValidator()

        module = PromptModule(
            name="test",
            version="1.0.0",
            description="测试",
            template="Hello {name}, task: {task_type}",
            variables=["name", "task_type"],
            applicable_agents=[],
        )

        result = validator.validate_variables(module)
        assert result.is_valid is True
        assert len(result.missing_variables) == 0

    def test_detect_undeclared_variables(self) -> None:
        """测试：应该检测未声明的变量"""
        from src.domain.services.prompt_template_system import (
            PromptModule,
            PromptTemplateValidator,
        )

        validator = PromptTemplateValidator()

        module = PromptModule(
            name="test",
            version="1.0.0",
            description="测试",
            template="Hello {name}, task: {task_type}, extra: {extra}",
            variables=["name", "task_type"],  # 缺少 extra
            applicable_agents=[],
        )

        result = validator.validate_variables(module)
        assert result.is_valid is False
        assert "extra" in result.missing_variables

    def test_detect_unused_declared_variables(self) -> None:
        """测试：应该检测声明但未使用的变量"""
        from src.domain.services.prompt_template_system import (
            PromptModule,
            PromptTemplateValidator,
        )

        validator = PromptTemplateValidator()

        module = PromptModule(
            name="test",
            version="1.0.0",
            description="测试",
            template="Hello {name}",
            variables=["name", "unused_var"],  # unused_var 未使用
            applicable_agents=[],
        )

        result = validator.validate_variables(module)
        assert "unused_var" in result.unused_variables


# =============================================================================
# 第六部分：Agent 适用性测试
# =============================================================================


class TestAgentApplicability:
    """测试 Agent 适用性"""

    def test_get_modules_for_agent(self) -> None:
        """测试：应该能获取适用于特定 Agent 的模块"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        modules = registry.get_modules_for_agent("ConversationAgent")
        assert len(modules) > 0
        assert all("ConversationAgent" in m.applicable_agents for m in modules)

    def test_generate_prompt_for_agent(self) -> None:
        """测试：应该能为特定 Agent 生成完整提示词"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateComposer,
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        composer = PromptTemplateComposer(registry)
        result = composer.generate_for_agent(
            agent_type="ConversationAgent",
            variables={
                "agent_name": "ConversationAgent",
                "responsibility": "管理对话流程",
                "capabilities": "意图分类、目标分解、ReAct循环",
                "constraints": "遵循安全规则",
                "principles": "用户体验优先",
                "forbidden_actions": "泄露敏感信息",
                "allowed_tools": "LLM",
                "tool_descriptions": "LLM: 语言模型调用",
                "usage_examples": "调用 LLM 进行推理",
                "format_type": "JSON",
                "output_schema": "DecisionMadeEvent schema",
                "examples": '{"type": "respond", "content": "..."}',
            },
        )

        assert "ConversationAgent" in result
        assert "意图分类" in result


# =============================================================================
# 第七部分：版本管理测试
# =============================================================================


class TestTemplateVersioning:
    """测试模板版本管理"""

    def test_module_has_version(self) -> None:
        """测试：模块应该有版本号"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        module = registry.get_module("role_definition")
        assert module is not None
        assert module.version is not None
        assert len(module.version.split(".")) == 3  # 语义化版本

    def test_get_module_by_version(self) -> None:
        """测试：应该能按版本获取模块"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        module = registry.get_module("role_definition", version="1.0.0")
        assert module is not None
        assert module.version == "1.0.0"


# =============================================================================
# 第八部分：错误处理测试
# =============================================================================


class TestErrorHandling:
    """测试错误处理"""

    def test_render_with_missing_variable_raises_error(self) -> None:
        """测试：缺少必需变量时应该抛出错误"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
            TemplateRenderError,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        with pytest.raises(TemplateRenderError) as exc_info:
            registry.render_module(
                "role_definition",
                agent_name="Test",
                # 缺少 responsibility 和 capabilities
            )

        assert "responsibility" in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    def test_get_nonexistent_module_returns_none(self) -> None:
        """测试：获取不存在的模块应该返回 None"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        module = registry.get_module("nonexistent_module")
        assert module is None


# =============================================================================
# 第九部分：集成测试
# =============================================================================


class TestPromptTemplateIntegration:
    """集成测试"""

    def test_full_workflow_from_yaml_to_render(self) -> None:
        """测试：从 YAML 加载到渲染的完整流程"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateComposer,
            PromptTemplateRegistry,
        )

        # 1. 创建 registry 并加载内置模块
        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        # 2. 创建 composer
        composer = PromptTemplateComposer(registry)

        # 3. 组合并渲染
        result = composer.compose(
            modules=["role_definition", "output_format"],
            variables={
                "agent_name": "TestAgent",
                "responsibility": "测试",
                "capabilities": "测试能力",
                "format_type": "JSON",
                "output_schema": "{}",
                "examples": "{}",
            },
        )

        assert "TestAgent" in result
        assert "JSON" in result

    def test_validate_all_builtin_modules(self) -> None:
        """测试：验证所有内置模块的有效性"""
        from src.domain.services.prompt_template_system import (
            PromptTemplateRegistry,
            PromptTemplateValidator,
        )

        registry = PromptTemplateRegistry()
        registry.load_builtin_modules()

        validator = PromptTemplateValidator()

        for module_name in [
            "role_definition",
            "behavior_guidelines",
            "tool_usage",
            "output_format",
        ]:
            module = registry.get_module(module_name)
            assert module is not None, f"Module {module_name} not found"

            # 验证语法
            syntax_result = validator.validate_syntax(module.template)
            assert syntax_result.is_valid, f"Module {module_name} has invalid syntax"

            # 验证变量
            var_result = validator.validate_variables(module)
            assert (
                var_result.is_valid
            ), f"Module {module_name} has variable issues: {var_result.missing_variables}"

"""场景提示词与 Task Prompt 注入系统测试

测试覆盖：
1. ScenarioPrompt 数据结构
2. ScenarioPromptLoader 场景加载器
3. TaskPrompt 任务提示词
4. TaskPromptGenerator 生成器
5. 模板拼接与变量替换
6. YAML/JSON Schema 校验
7. ConversationAgent 集成
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml


class TestScenarioPromptDataStructure:
    """场景提示词数据结构测试"""

    def test_scenario_prompt_has_required_fields(self) -> None:
        """测试场景提示词包含必要字段"""
        from src.domain.services.scenario_prompt_system import ScenarioPrompt

        scenario = ScenarioPrompt(
            scenario_id="financial_analysis",
            name="金融分析场景",
            description="专业金融数据分析与报告生成",
            domain="finance",
            system_prompt="你是一位专业的金融分析师...",
            guidelines=["遵守金融法规", "数据准确性优先"],
            constraints=["不提供投资建议", "标注数据来源"],
            examples=[{"input": "分析股票走势", "output": "基于历史数据..."}],
        )

        assert scenario.scenario_id == "financial_analysis"
        assert scenario.name == "金融分析场景"
        assert scenario.domain == "finance"
        assert len(scenario.guidelines) == 2
        assert len(scenario.constraints) == 2
        assert len(scenario.examples) == 1

    def test_scenario_prompt_supports_variables(self) -> None:
        """测试场景提示词支持变量占位符"""
        from src.domain.services.scenario_prompt_system import ScenarioPrompt

        scenario = ScenarioPrompt(
            scenario_id="legal_compliance",
            name="法律合规场景",
            description="法律文书审核与合规检查",
            domain="legal",
            system_prompt="你是{company_name}的法律顾问，专注于{legal_domain}领域...",
            variables=["company_name", "legal_domain"],
        )

        assert "company_name" in scenario.variables
        assert "legal_domain" in scenario.variables

    def test_scenario_prompt_to_dict_and_from_dict(self) -> None:
        """测试场景提示词序列化与反序列化"""
        from src.domain.services.scenario_prompt_system import ScenarioPrompt

        original = ScenarioPrompt(
            scenario_id="customer_service",
            name="客服场景",
            description="客户服务与问题解答",
            domain="service",
            system_prompt="你是专业的客服代表...",
            guidelines=["友好礼貌", "解决问题"],
        )

        data = original.to_dict()
        restored = ScenarioPrompt.from_dict(data)

        assert restored.scenario_id == original.scenario_id
        assert restored.name == original.name
        assert restored.guidelines == original.guidelines


class TestScenarioPromptLoader:
    """场景提示词加载器测试"""

    def test_load_scenario_from_yaml(self) -> None:
        """测试从 YAML 文件加载场景"""
        from src.domain.services.scenario_prompt_system import ScenarioPromptLoader

        yaml_content = """
scenario_id: financial_analysis
name: 金融分析场景
description: 专业金融数据分析与报告生成
domain: finance
system_prompt: |
  你是一位专业的金融分析师，擅长：
  - 财务报表分析
  - 市场趋势预测
  - 风险评估
guidelines:
  - 遵守金融法规
  - 数据准确性优先
  - 使用专业术语
constraints:
  - 不提供具体投资建议
  - 标注所有数据来源
variables:
  - company_name
  - analysis_period
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = f.name

        try:
            loader = ScenarioPromptLoader()
            scenario = loader.load_from_file(temp_path)

            assert scenario.scenario_id == "financial_analysis"
            assert scenario.domain == "finance"
            assert "财务报表分析" in scenario.system_prompt
            assert len(scenario.guidelines) == 3
        finally:
            Path(temp_path).unlink()

    def test_load_scenario_from_json(self) -> None:
        """测试从 JSON 文件加载场景"""
        from src.domain.services.scenario_prompt_system import ScenarioPromptLoader

        json_content = {
            "scenario_id": "legal_compliance",
            "name": "法律合规场景",
            "description": "法律文书审核与合规检查",
            "domain": "legal",
            "system_prompt": "你是专业的法律顾问...",
            "guidelines": ["遵守法律法规", "保护客户隐私"],
            "constraints": ["不构成法律意见"],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f, ensure_ascii=False)
            f.flush()
            temp_path = f.name

        try:
            loader = ScenarioPromptLoader()
            scenario = loader.load_from_file(temp_path)

            assert scenario.scenario_id == "legal_compliance"
            assert scenario.domain == "legal"
        finally:
            Path(temp_path).unlink()

    def test_validate_scenario_schema(self) -> None:
        """测试场景 Schema 校验"""
        from src.domain.services.scenario_prompt_system import (
            ScenarioPromptLoader,
            ScenarioSchemaError,
        )

        # 缺少必要字段
        invalid_content = {
            "name": "测试场景",
            # 缺少 scenario_id, domain, system_prompt
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(invalid_content, f, ensure_ascii=False)
            f.flush()
            temp_path = f.name

        try:
            loader = ScenarioPromptLoader()
            with pytest.raises(ScenarioSchemaError):
                loader.load_from_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_scenarios_from_directory(self) -> None:
        """测试从目录批量加载场景"""
        from src.domain.services.scenario_prompt_system import ScenarioPromptLoader

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建多个场景文件
            scenarios = [
                {
                    "scenario_id": "finance",
                    "name": "金融",
                    "domain": "finance",
                    "system_prompt": "金融分析师...",
                },
                {
                    "scenario_id": "legal",
                    "name": "法律",
                    "domain": "legal",
                    "system_prompt": "法律顾问...",
                },
            ]

            for scenario in scenarios:
                file_path = Path(temp_dir) / f"{scenario['scenario_id']}.yaml"
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.dump(scenario, f, allow_unicode=True)

            loader = ScenarioPromptLoader()
            loaded = loader.load_from_directory(temp_dir)

            assert len(loaded) == 2
            assert "finance" in loaded
            assert "legal" in loaded


class TestTaskPrompt:
    """Task Prompt 数据结构测试"""

    def test_task_prompt_has_required_fields(self) -> None:
        """测试 Task Prompt 包含必要字段"""
        from src.domain.services.scenario_prompt_system import TaskPrompt

        task_prompt = TaskPrompt(
            task_id="task_001",
            task_type="data_analysis",
            objective="分析销售数据趋势",
            context="用户需要了解Q3销售情况",
            instructions=["提取关键指标", "生成可视化建议"],
            constraints=["使用中文回复", "数据脱敏处理"],
            expected_output="结构化的分析报告",
        )

        assert task_prompt.task_id == "task_001"
        assert task_prompt.task_type == "data_analysis"
        assert task_prompt.objective == "分析销售数据趋势"
        assert len(task_prompt.instructions) == 2

    def test_task_prompt_render_to_string(self) -> None:
        """测试 Task Prompt 渲染为字符串"""
        from src.domain.services.scenario_prompt_system import TaskPrompt

        task_prompt = TaskPrompt(
            task_id="task_002",
            task_type="summarization",
            objective="总结会议纪要",
            context="这是一个技术评审会议",
            instructions=["提取决策要点", "列出待办事项"],
            expected_output="会议摘要",
        )

        rendered = task_prompt.render()

        assert "总结会议纪要" in rendered
        assert "技术评审会议" in rendered
        assert "提取决策要点" in rendered

    def test_task_prompt_with_scenario_context(self) -> None:
        """测试带场景上下文的 Task Prompt"""
        from src.domain.services.scenario_prompt_system import TaskPrompt

        task_prompt = TaskPrompt(
            task_id="task_003",
            task_type="compliance_check",
            objective="检查合同合规性",
            context="这是一份商业合同",
            instructions=["检查条款完整性"],
            scenario_id="legal_compliance",
            scenario_context="法律合规场景下的审核任务",
        )

        assert task_prompt.scenario_id == "legal_compliance"
        assert "法律合规" in task_prompt.scenario_context


class TestTaskPromptGenerator:
    """Task Prompt 生成器测试"""

    def test_generate_task_prompt_for_analysis(self) -> None:
        """测试为分析任务生成 Task Prompt"""
        from src.domain.services.scenario_prompt_system import TaskPromptGenerator

        generator = TaskPromptGenerator()

        task_prompt = generator.generate(
            task_id="analysis_001",
            task_type="data_analysis",
            objective="分析用户行为数据",
            context={"data_source": "用户日志", "time_range": "过去30天"},
        )

        assert task_prompt.task_type == "data_analysis"
        assert "分析" in task_prompt.objective
        # 分析任务应有特定指令
        assert any("数据" in instr for instr in task_prompt.instructions)

    def test_generate_task_prompt_for_summarization(self) -> None:
        """测试为摘要任务生成 Task Prompt"""
        from src.domain.services.scenario_prompt_system import TaskPromptGenerator

        generator = TaskPromptGenerator()

        task_prompt = generator.generate(
            task_id="summary_001",
            task_type="summarization",
            objective="总结研究报告",
            context={"document_type": "技术报告", "length": "500字以内"},
        )

        assert task_prompt.task_type == "summarization"
        # 摘要任务应有提取要点的指令
        assert any(
            "要点" in instr or "摘要" in instr or "总结" in instr
            for instr in task_prompt.instructions
        )

    def test_generate_task_prompt_for_code_generation(self) -> None:
        """测试为代码生成任务生成 Task Prompt"""
        from src.domain.services.scenario_prompt_system import TaskPromptGenerator

        generator = TaskPromptGenerator()

        task_prompt = generator.generate(
            task_id="code_001",
            task_type="code_generation",
            objective="实现用户认证功能",
            context={"language": "Python", "framework": "FastAPI"},
        )

        assert task_prompt.task_type == "code_generation"
        # 代码生成任务应有代码质量相关指令
        assert any(
            "代码" in instr or "实现" in instr or "测试" in instr
            for instr in task_prompt.instructions
        )

    def test_generate_task_prompt_with_scenario(self) -> None:
        """测试结合场景生成 Task Prompt"""
        from src.domain.services.scenario_prompt_system import (
            ScenarioPrompt,
            TaskPromptGenerator,
        )

        scenario = ScenarioPrompt(
            scenario_id="financial_analysis",
            name="金融分析场景",
            description="专业金融数据分析",
            domain="finance",
            system_prompt="你是金融分析师...",
            guidelines=["使用专业术语", "引用数据来源"],
            constraints=["不提供投资建议"],
        )

        generator = TaskPromptGenerator()
        generator.set_scenario(scenario)

        task_prompt = generator.generate(
            task_id="finance_001",
            task_type="data_analysis",
            objective="分析公司财报",
            context={"company": "示例公司", "period": "2024Q3"},
        )

        assert task_prompt.scenario_id == "financial_analysis"
        # 场景约束应被包含
        assert any("投资建议" in c for c in task_prompt.constraints)

    def test_generate_different_prompts_for_different_tasks(self) -> None:
        """测试不同任务类型生成不同的 Task Prompt"""
        from src.domain.services.scenario_prompt_system import TaskPromptGenerator

        generator = TaskPromptGenerator()

        analysis_prompt = generator.generate(
            task_id="t1",
            task_type="data_analysis",
            objective="分析数据",
            context={},
        )

        summary_prompt = generator.generate(
            task_id="t2",
            task_type="summarization",
            objective="总结内容",
            context={},
        )

        code_prompt = generator.generate(
            task_id="t3",
            task_type="code_generation",
            objective="写代码",
            context={},
        )

        # 不同任务类型应有不同的指令
        assert analysis_prompt.instructions != summary_prompt.instructions
        assert summary_prompt.instructions != code_prompt.instructions


class TestTemplateComposition:
    """模板拼接测试"""

    def test_compose_generic_with_scenario(self) -> None:
        """测试通用模板与场景模板拼接"""
        from src.domain.services.scenario_prompt_system import (
            ScenarioPrompt,
            TemplateComposer,
        )

        generic_template = """
## 通用指南
- 保持专业态度
- 清晰表达
{scenario_content}

## 任务要求
{task_content}
"""

        scenario = ScenarioPrompt(
            scenario_id="finance",
            name="金融场景",
            description="金融分析",
            domain="finance",
            system_prompt="你是金融分析师，专注于市场分析和风险评估。",
            guidelines=["数据驱动决策", "风险提示"],
        )

        composer = TemplateComposer()
        composed = composer.compose(
            generic_template=generic_template,
            scenario=scenario,
            task_content="分析Q3财报数据",
        )

        assert "通用指南" in composed
        assert "金融分析师" in composed
        assert "分析Q3财报数据" in composed

    def test_variable_substitution(self) -> None:
        """测试变量替换"""
        from src.domain.services.scenario_prompt_system import (
            ScenarioPrompt,
            TemplateComposer,
        )

        scenario = ScenarioPrompt(
            scenario_id="custom",
            name="自定义场景",
            description="可配置场景",
            domain="general",
            system_prompt="你是{company_name}的{role}，负责{responsibility}。",
            variables=["company_name", "role", "responsibility"],
        )

        composer = TemplateComposer()
        result = composer.substitute_variables(
            scenario.system_prompt,
            {
                "company_name": "示例公司",
                "role": "数据分析师",
                "responsibility": "数据洞察",
            },
        )

        assert "示例公司" in result
        assert "数据分析师" in result
        assert "数据洞察" in result

    def test_missing_variable_handling(self) -> None:
        """测试缺失变量处理"""
        from src.domain.services.scenario_prompt_system import TemplateComposer

        template = "你好，{name}！欢迎来到{location}。"

        composer = TemplateComposer()

        # 部分变量缺失，应保留占位符或使用默认值
        result = composer.substitute_variables(
            template,
            {"name": "张三"},
            default_value="[未指定]",
        )

        assert "张三" in result
        assert "[未指定]" in result or "{location}" in result


class TestTaskTypeRegistry:
    """任务类型注册表测试"""

    def test_register_custom_task_type(self) -> None:
        """测试注册自定义任务类型"""
        from src.domain.services.scenario_prompt_system import (
            TaskPromptGenerator,
            TaskTypeConfig,
        )

        generator = TaskPromptGenerator()

        # 注册自定义任务类型
        generator.register_task_type(
            TaskTypeConfig(
                task_type="legal_review",
                name="法律审核",
                default_instructions=[
                    "检查法律条款完整性",
                    "标注潜在风险点",
                    "提供修改建议",
                ],
                default_constraints=[
                    "不构成正式法律意见",
                    "建议咨询专业律师",
                ],
            )
        )

        task_prompt = generator.generate(
            task_id="legal_001",
            task_type="legal_review",
            objective="审核合同条款",
            context={},
        )

        assert task_prompt.task_type == "legal_review"
        assert any("法律条款" in instr for instr in task_prompt.instructions)

    def test_list_available_task_types(self) -> None:
        """测试列出可用任务类型"""
        from src.domain.services.scenario_prompt_system import TaskPromptGenerator

        generator = TaskPromptGenerator()
        task_types = generator.list_task_types()

        # 应有默认任务类型
        assert "data_analysis" in task_types
        assert "summarization" in task_types
        assert "code_generation" in task_types


class TestScenarioRegistry:
    """场景注册表测试"""

    def test_register_and_get_scenario(self) -> None:
        """测试注册和获取场景"""
        from src.domain.services.scenario_prompt_system import (
            ScenarioPrompt,
            ScenarioRegistry,
        )

        registry = ScenarioRegistry()

        scenario = ScenarioPrompt(
            scenario_id="test_scenario",
            name="测试场景",
            description="用于测试",
            domain="test",
            system_prompt="测试提示词",
        )

        registry.register(scenario)
        retrieved = registry.get("test_scenario")

        assert retrieved is not None
        assert retrieved.scenario_id == "test_scenario"

    def test_list_scenarios_by_domain(self) -> None:
        """测试按领域列出场景"""
        from src.domain.services.scenario_prompt_system import (
            ScenarioPrompt,
            ScenarioRegistry,
        )

        registry = ScenarioRegistry()

        # 注册多个场景
        registry.register(
            ScenarioPrompt(
                scenario_id="finance_1",
                name="金融1",
                description="",
                domain="finance",
                system_prompt="",
            )
        )
        registry.register(
            ScenarioPrompt(
                scenario_id="finance_2",
                name="金融2",
                description="",
                domain="finance",
                system_prompt="",
            )
        )
        registry.register(
            ScenarioPrompt(
                scenario_id="legal_1",
                name="法律1",
                description="",
                domain="legal",
                system_prompt="",
            )
        )

        finance_scenarios = registry.list_by_domain("finance")
        legal_scenarios = registry.list_by_domain("legal")

        assert len(finance_scenarios) == 2
        assert len(legal_scenarios) == 1


class TestConversationAgentIntegration:
    """ConversationAgent 集成测试"""

    def test_generate_subtask_prompt(self) -> None:
        """测试为子任务生成提示词"""
        from src.domain.services.scenario_prompt_system import (
            ScenarioPrompt,
            SubtaskPromptService,
        )

        service = SubtaskPromptService()

        # 设置场景
        scenario = ScenarioPrompt(
            scenario_id="finance",
            name="金融场景",
            description="金融分析",
            domain="finance",
            system_prompt="金融分析师",
            guidelines=["数据准确"],
        )
        service.set_scenario(scenario)

        # 模拟子任务
        subtask = {
            "id": "subtask_001",
            "type": "data_analysis",
            "description": "分析销售数据",
            "context": {"data_type": "销售记录"},
        }

        prompt = service.generate_for_subtask(subtask)

        assert prompt is not None
        assert "分析销售数据" in prompt.objective
        assert prompt.scenario_id == "finance"

    def test_generate_prompts_for_multiple_subtasks(self) -> None:
        """测试为多个子任务生成提示词"""
        from src.domain.services.scenario_prompt_system import SubtaskPromptService

        service = SubtaskPromptService()

        subtasks = [
            {"id": "s1", "type": "data_analysis", "description": "分析数据", "context": {}},
            {"id": "s2", "type": "summarization", "description": "总结报告", "context": {}},
            {"id": "s3", "type": "code_generation", "description": "生成代码", "context": {}},
        ]

        prompts = service.generate_for_subtasks(subtasks)

        assert len(prompts) == 3
        assert prompts[0].task_type == "data_analysis"
        assert prompts[1].task_type == "summarization"
        assert prompts[2].task_type == "code_generation"


class TestYamlSchemaValidation:
    """YAML Schema 校验测试"""

    def test_valid_scenario_yaml_passes_validation(self) -> None:
        """测试有效的场景 YAML 通过校验"""
        from src.domain.services.scenario_prompt_system import ScenarioSchemaValidator

        valid_data = {
            "scenario_id": "test",
            "name": "测试场景",
            "description": "描述",
            "domain": "test",
            "system_prompt": "提示词",
            "guidelines": ["指南1"],
            "constraints": ["约束1"],
        }

        validator = ScenarioSchemaValidator()
        result = validator.validate(valid_data)

        assert result.is_valid

    def test_invalid_scenario_yaml_fails_validation(self) -> None:
        """测试无效的场景 YAML 校验失败"""
        from src.domain.services.scenario_prompt_system import ScenarioSchemaValidator

        invalid_data = {
            "name": "测试场景",
            # 缺少必要字段
        }

        validator = ScenarioSchemaValidator()
        result = validator.validate(invalid_data)

        assert not result.is_valid
        assert len(result.errors) > 0

    def test_validation_error_messages(self) -> None:
        """测试校验错误消息"""
        from src.domain.services.scenario_prompt_system import ScenarioSchemaValidator

        invalid_data = {
            "scenario_id": "",  # 空字符串
            "name": "测试",
            "domain": "test",
            "system_prompt": "提示",
        }

        validator = ScenarioSchemaValidator()
        result = validator.validate(invalid_data)

        assert not result.is_valid
        # 应有关于空 scenario_id 的错误
        assert any("scenario_id" in err for err in result.errors)

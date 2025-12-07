"""场景提示词与 Task Prompt 注入集成测试

测试完整的工作流程：
1. 从 YAML 文件加载场景
2. 注册场景到注册表
3. 为不同子任务生成 Task Prompt
4. 组合通用模板与场景模板
5. 变量替换与渲染
"""

from pathlib import Path

import pytest

from src.domain.services.scenario_prompt_system import (
    ScenarioPrompt,
    ScenarioPromptLoader,
    ScenarioRegistry,
    SubtaskPromptService,
    TaskPromptGenerator,
    TaskTypeConfig,
    TemplateComposer,
)


class TestScenarioPromptFullWorkflow:
    """完整工作流测试"""

    @pytest.fixture
    def scenarios_dir(self) -> Path:
        """获取场景配置目录"""
        return Path(__file__).parent.parent.parent / "config" / "scenarios"

    @pytest.fixture
    def loader(self) -> ScenarioPromptLoader:
        """创建加载器"""
        return ScenarioPromptLoader()

    @pytest.fixture
    def registry(self) -> ScenarioRegistry:
        """创建注册表"""
        return ScenarioRegistry()

    def test_load_and_register_scenarios_from_directory(
        self, scenarios_dir: Path, loader: ScenarioPromptLoader, registry: ScenarioRegistry
    ) -> None:
        """测试从目录加载并注册所有场景"""
        if not scenarios_dir.exists():
            pytest.skip("场景配置目录不存在")

        # 加载所有场景
        scenarios = loader.load_from_directory(scenarios_dir)

        # 注册到注册表
        for scenario in scenarios.values():
            registry.register(scenario)

        # 验证加载结果
        assert len(registry.list_all()) > 0
        assert len(registry.list_domains()) > 0

    def test_generate_task_prompt_with_loaded_scenario(
        self, scenarios_dir: Path, loader: ScenarioPromptLoader
    ) -> None:
        """测试使用加载的场景生成 Task Prompt"""
        if not scenarios_dir.exists():
            pytest.skip("场景配置目录不存在")

        # 尝试加载金融分析场景
        finance_file = scenarios_dir / "financial_analysis.yaml"
        if not finance_file.exists():
            pytest.skip("金融分析场景文件不存在")

        scenario = loader.load_from_file(finance_file)
        assert scenario.scenario_id == "financial_analysis"
        assert scenario.domain == "finance"

        # 使用场景生成 Task Prompt
        generator = TaskPromptGenerator()
        generator.set_scenario(scenario)

        task_prompt = generator.generate(
            task_id="analysis_001",
            task_type="data_analysis",
            objective="分析公司Q3财务报表",
            context={"company": "示例公司", "period": "2024Q3"},
        )

        assert task_prompt.scenario_id == "financial_analysis"
        assert "金融分析场景" in task_prompt.scenario_context
        assert len(task_prompt.instructions) > 0

    def test_subtask_prompt_service_workflow(
        self, scenarios_dir: Path, loader: ScenarioPromptLoader
    ) -> None:
        """测试 SubtaskPromptService 完整工作流"""
        if not scenarios_dir.exists():
            pytest.skip("场景配置目录不存在")

        # 加载技术支持场景
        tech_file = scenarios_dir / "technical_support.yaml"
        if not tech_file.exists():
            pytest.skip("技术支持场景文件不存在")

        scenario = loader.load_from_file(tech_file)

        # 使用 SubtaskPromptService
        service = SubtaskPromptService()
        service.set_scenario(scenario)

        # 模拟 ConversationAgent 的子任务列表
        subtasks = [
            {
                "id": "subtask_001",
                "type": "data_analysis",
                "description": "分析系统日志找出性能瓶颈",
                "context": {"log_type": "application", "time_range": "last_24h"},
            },
            {
                "id": "subtask_002",
                "type": "code_generation",
                "description": "生成性能优化脚本",
                "context": {"language": "Python", "target": "memory_usage"},
            },
            {
                "id": "subtask_003",
                "type": "summarization",
                "description": "总结排查过程和解决方案",
                "context": {"format": "report"},
            },
        ]

        # 批量生成 Task Prompt
        prompts = service.generate_for_subtasks(subtasks)

        assert len(prompts) == 3

        # 验证不同任务类型有不同的指令
        assert prompts[0].task_type == "data_analysis"
        assert prompts[1].task_type == "code_generation"
        assert prompts[2].task_type == "summarization"

        # 验证每个 prompt 都关联了场景
        for prompt in prompts:
            assert prompt.scenario_id == "technical_support"


class TestTemplateCompositionIntegration:
    """模板组合集成测试"""

    def test_compose_and_render_full_prompt(self) -> None:
        """测试组合并渲染完整提示词"""
        # 创建场景
        scenario = ScenarioPrompt(
            scenario_id="test_scenario",
            name="测试场景",
            description="用于集成测试",
            domain="test",
            system_prompt="你是一位专业的测试助手，帮助验证系统功能。",
            guidelines=["保持测试覆盖全面", "记录所有测试结果"],
            constraints=["不修改生产数据", "遵循测试规范"],
            variables=["test_target", "test_type"],
        )

        # 定义通用模板
        generic_template = """
## 通用指南
- 保持专业态度
- 清晰表达
{scenario_content}

## 任务要求
{task_content}
"""

        # 组合模板
        composer = TemplateComposer()
        composed = composer.compose(
            generic_template=generic_template,
            scenario=scenario,
            task_content="执行单元测试并生成报告",
        )

        # 验证组合结果
        assert "通用指南" in composed
        assert "专业的测试助手" in composed
        assert "执行单元测试" in composed
        assert "保持测试覆盖全面" in composed

    def test_variable_substitution_in_workflow(self) -> None:
        """测试工作流中的变量替换"""
        scenario = ScenarioPrompt(
            scenario_id="parameterized",
            name="参数化场景",
            description="支持动态参数",
            domain="general",
            system_prompt="你是{company_name}的{role}，负责{responsibility}。请在{deadline}前完成任务。",
            variables=["company_name", "role", "responsibility", "deadline"],
        )

        composer = TemplateComposer()

        # 完整变量替换
        result = composer.substitute_variables(
            scenario.system_prompt,
            {
                "company_name": "科技公司",
                "role": "项目经理",
                "responsibility": "项目交付",
                "deadline": "本周五",
            },
        )

        assert "科技公司" in result
        assert "项目经理" in result
        assert "项目交付" in result
        assert "本周五" in result

    def test_partial_variable_substitution(self) -> None:
        """测试部分变量替换（使用默认值）"""
        template = "用户：{username}，角色：{role}，部门：{department}"

        composer = TemplateComposer()

        # 只提供部分变量
        result = composer.substitute_variables(
            template,
            {"username": "张三"},
            default_value="[未指定]",
        )

        assert "张三" in result
        assert "[未指定]" in result


class TestTaskTypeRegistration:
    """任务类型注册集成测试"""

    def test_register_and_use_custom_task_type(self) -> None:
        """测试注册并使用自定义任务类型"""
        generator = TaskPromptGenerator()

        # 注册自定义任务类型
        generator.register_task_type(
            TaskTypeConfig(
                task_type="security_audit",
                name="安全审计",
                default_instructions=[
                    "检查代码安全漏洞",
                    "验证身份认证机制",
                    "审计数据访问权限",
                    "检测敏感信息泄露",
                ],
                default_constraints=[
                    "遵循OWASP安全标准",
                    "不执行破坏性测试",
                ],
                expected_output_format="安全审计报告",
            )
        )

        # 验证任务类型已注册
        assert "security_audit" in generator.list_task_types()

        # 使用自定义任务类型生成 prompt
        prompt = generator.generate(
            task_id="audit_001",
            task_type="security_audit",
            objective="审计用户认证模块的安全性",
            context={"module": "auth", "language": "Python"},
        )

        assert prompt.task_type == "security_audit"
        assert any("安全漏洞" in instr for instr in prompt.instructions)
        assert any("OWASP" in c for c in prompt.constraints)


class TestScenarioRegistryIntegration:
    """场景注册表集成测试"""

    def test_multi_domain_scenario_management(self) -> None:
        """测试多领域场景管理"""
        registry = ScenarioRegistry()

        # 注册多个领域的场景
        scenarios = [
            ScenarioPrompt(
                scenario_id="finance_1",
                name="财务分析",
                description="",
                domain="finance",
                system_prompt="财务分析师",
            ),
            ScenarioPrompt(
                scenario_id="finance_2",
                name="投资研究",
                description="",
                domain="finance",
                system_prompt="投资研究员",
            ),
            ScenarioPrompt(
                scenario_id="legal_1",
                name="合同审查",
                description="",
                domain="legal",
                system_prompt="法律顾问",
            ),
            ScenarioPrompt(
                scenario_id="tech_1",
                name="技术支持",
                description="",
                domain="technology",
                system_prompt="技术工程师",
            ),
        ]

        for scenario in scenarios:
            registry.register(scenario)

        # 验证按领域检索
        finance_scenarios = registry.list_by_domain("finance")
        legal_scenarios = registry.list_by_domain("legal")
        tech_scenarios = registry.list_by_domain("technology")

        assert len(finance_scenarios) == 2
        assert len(legal_scenarios) == 1
        assert len(tech_scenarios) == 1

        # 验证领域列表
        domains = registry.list_domains()
        assert "finance" in domains
        assert "legal" in domains
        assert "technology" in domains

    def test_scenario_lifecycle(self) -> None:
        """测试场景生命周期（注册、获取、注销）"""
        registry = ScenarioRegistry()

        scenario = ScenarioPrompt(
            scenario_id="temp_scenario",
            name="临时场景",
            description="用于生命周期测试",
            domain="test",
            system_prompt="临时提示词",
        )

        # 注册
        registry.register(scenario)
        assert registry.get("temp_scenario") is not None

        # 获取
        retrieved = registry.get("temp_scenario")
        assert retrieved.name == "临时场景"

        # 注销
        result = registry.unregister("temp_scenario")
        assert result is True
        assert registry.get("temp_scenario") is None


class TestEndToEndScenarioPromptWorkflow:
    """端到端场景提示词工作流测试"""

    def test_complete_conversation_agent_integration(self) -> None:
        """测试完整的 ConversationAgent 集成流程"""
        # 1. 创建场景
        scenario = ScenarioPrompt(
            scenario_id="customer_service",
            name="客服场景",
            description="客户服务与问题解答",
            domain="service",
            system_prompt="你是专业的客服代表，负责解答用户问题。",
            guidelines=["友好礼貌", "快速响应", "解决问题"],
            constraints=["不泄露客户隐私", "不承诺未经授权的优惠"],
        )

        # 2. 注册到注册表
        registry = ScenarioRegistry()
        registry.register(scenario)

        # 3. 创建 SubtaskPromptService
        service = SubtaskPromptService()
        service.set_scenario(registry.get("customer_service"))

        # 4. 模拟子任务列表（来自 ConversationAgent 的任务拆解）
        subtasks = [
            {
                "id": "understand",
                "type": "data_analysis",
                "description": "理解用户问题并分类",
                "context": {"user_message": "我的订单还没收到"},
            },
            {
                "id": "query",
                "type": "code_generation",
                "description": "查询订单物流信息",
                "context": {"order_id": "ORD123456"},
            },
            {
                "id": "respond",
                "type": "summarization",
                "description": "生成客服回复",
                "context": {"tone": "友好", "format": "简洁"},
            },
        ]

        # 5. 生成 Task Prompts
        prompts = service.generate_for_subtasks(subtasks)

        # 6. 验证结果
        assert len(prompts) == 3

        for prompt in prompts:
            # 所有 prompt 都应关联客服场景
            assert prompt.scenario_id == "customer_service"
            # 场景约束应被继承
            assert any("隐私" in c for c in prompt.constraints)

        # 7. 渲染第一个 prompt 并验证
        rendered = prompts[0].render()
        assert "理解用户问题" in rendered
        assert "data_analysis" in rendered


class TestYamlConfigValidation:
    """YAML 配置文件验证测试"""

    @pytest.fixture
    def scenarios_dir(self) -> Path:
        """获取场景配置目录"""
        return Path(__file__).parent.parent.parent / "config" / "scenarios"

    def test_all_yaml_files_pass_schema_validation(self, scenarios_dir: Path) -> None:
        """测试所有 YAML 配置文件都能通过 Schema 校验"""
        if not scenarios_dir.exists():
            pytest.skip("场景配置目录不存在")

        loader = ScenarioPromptLoader()
        yaml_files = list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml"))

        if not yaml_files:
            pytest.skip("没有找到 YAML 配置文件")

        for yaml_file in yaml_files:
            # 每个文件都应该能成功加载
            scenario = loader.load_from_file(yaml_file)
            assert scenario.scenario_id is not None
            assert scenario.name is not None
            assert scenario.domain is not None
            assert scenario.system_prompt is not None

    def test_scenario_yaml_content_quality(self, scenarios_dir: Path) -> None:
        """测试场景 YAML 内容质量"""
        if not scenarios_dir.exists():
            pytest.skip("场景配置目录不存在")

        loader = ScenarioPromptLoader()
        scenarios = loader.load_from_directory(scenarios_dir)

        for scenario_id, scenario in scenarios.items():
            # 基本字段不应为空
            assert len(scenario.name) > 0, f"场景 {scenario_id} 名称为空"
            assert len(scenario.system_prompt) > 10, f"场景 {scenario_id} 系统提示词过短"

            # 应有指南或约束
            has_guidelines = len(scenario.guidelines) > 0
            has_constraints = len(scenario.constraints) > 0
            assert has_guidelines or has_constraints, f"场景 {scenario_id} 缺少指南和约束"

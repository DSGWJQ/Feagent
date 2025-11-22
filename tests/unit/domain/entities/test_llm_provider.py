"""快速测试：LLMProvider 和 LLMUsage 实体"""

import pytest
from src.domain.entities.llm_provider import LLMProvider
from src.domain.entities.llm_usage import LLMUsage
from src.domain.exceptions import DomainError


class TestLLMProvider:
    """LLMProvider 实体测试"""

    def test_create_openai_provider(self):
        """测试创建 OpenAI 提供商"""
        provider = LLMProvider.create_openai(api_key="test-key")
        assert provider.name == "openai"
        assert provider.enabled is True
        assert "gpt-4" in provider.models

    def test_create_deepseek_provider(self):
        """测试创建 DeepSeek 提供商"""
        provider = LLMProvider.create_deepseek(api_key="test-key")
        assert provider.name == "deepseek"
        assert "deepseek-chat" in provider.models

    def test_create_qwen_provider(self):
        """测试创建 Qwen 提供商"""
        provider = LLMProvider.create_qwen(api_key="test-key")
        assert provider.name == "qwen"
        assert "qwen-turbo" in provider.models

    def test_create_ollama_provider(self):
        """测试创建 Ollama 本地提供商（无密钥）"""
        provider = LLMProvider.create_ollama()
        assert provider.name == "ollama"
        assert provider.api_key is None
        assert provider.enabled is True

    def test_enable_disable_provider(self):
        """测试启用/禁用提供商"""
        provider = LLMProvider.create_openai(api_key="test-key")
        provider.disable()
        assert provider.enabled is False
        provider.enable()
        assert provider.enabled is True

    def test_add_remove_model(self):
        """测试添加/移除模型"""
        provider = LLMProvider.create_openai(api_key="test-key")
        initial_count = len(provider.models)
        provider.add_model("gpt-5")
        assert len(provider.models) == initial_count + 1
        assert "gpt-5" in provider.models


class TestLLMUsage:
    """LLMUsage 成本追踪测试"""

    def test_calculate_openai_cost(self):
        """测试 OpenAI 成本计算"""
        cost = LLMUsage.calculate_cost("openai", "gpt-4", 100, 50)
        # GPT-4: $0.03/1K prompt, $0.06/1K completion
        # 100 * 0.03/1000 + 50 * 0.06/1000 = 0.003 + 0.003 = 0.006
        assert cost == pytest.approx(0.006, rel=1e-6)

    def test_calculate_deepseek_cost(self):
        """测试 DeepSeek 成本计算（便宜）"""
        cost = LLMUsage.calculate_cost("deepseek", "deepseek-chat", 1000, 500)
        # DeepSeek: $0.00014/1K prompt, $0.00028/1K completion
        # 1000 * 0.00014/1000 + 500 * 0.00028/1000 = 0.00014 + 0.00014 = 0.00028
        assert cost == pytest.approx(0.00028, rel=1e-6)

    def test_create_llm_usage(self):
        """测试创建 LLMUsage 记录"""
        usage = LLMUsage.create(
            provider="openai",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            run_id="run_123",
        )
        assert usage.provider == "openai"
        assert usage.total_tokens == 150
        assert usage.cost > 0

    def test_estimate_total_cost(self):
        """测试成本统计"""
        usages = [
            LLMUsage.create("openai", "gpt-4", 100, 50, "run_1"),
            LLMUsage.create("deepseek", "deepseek-chat", 1000, 500, "run_2"),
        ]
        total_cost = LLMUsage.estimate_total_cost(usages)
        assert total_cost > 0

    def test_estimate_cost_by_provider(self):
        """测试按提供商统计成本"""
        usages = [
            LLMUsage.create("openai", "gpt-4", 100, 50, "run_1"),
            LLMUsage.create("openai", "gpt-3.5-turbo", 200, 100, "run_2"),
            LLMUsage.create("deepseek", "deepseek-chat", 1000, 500, "run_3"),
        ]
        cost_by_provider = LLMUsage.estimate_cost_by_provider(usages)
        assert "openai" in cost_by_provider
        assert "deepseek" in cost_by_provider
        assert cost_by_provider["openai"] > cost_by_provider["deepseek"]


class TestClassifyTask:
    """任务分类测试"""

    def test_classify_data_analysis_task(self):
        """测试分类数据分析任务"""
        from src.application.use_cases.classify_task import (
            ClassifyTaskUseCase,
            ClassifyTaskInput,
        )
        from src.domain.value_objects.task_type import TaskType

        use_case = ClassifyTaskUseCase()
        result = use_case.execute(
            ClassifyTaskInput(
                start="我有一个销售数据CSV文件",
                goal="分析销售数据，找出增长趋势",
            )
        )
        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence > 0.5

    def test_classify_content_creation_task(self):
        """测试分类内容创建任务"""
        from src.application.use_cases.classify_task import (
            ClassifyTaskUseCase,
            ClassifyTaskInput,
        )
        from src.domain.value_objects.task_type import TaskType

        use_case = ClassifyTaskUseCase()
        result = use_case.execute(
            ClassifyTaskInput(
                start="我需要一篇博客文章",
                goal="写一篇关于人工智能的内容",
            )
        )
        assert result.task_type == TaskType.CONTENT_CREATION
        assert result.confidence > 0.5

    def test_classify_problem_solving_task(self):
        """测试分类问题解决任务"""
        from src.application.use_cases.classify_task import (
            ClassifyTaskUseCase,
            ClassifyTaskInput,
        )
        from src.domain.value_objects.task_type import TaskType

        use_case = ClassifyTaskUseCase()
        result = use_case.execute(
            ClassifyTaskInput(
                start="我的API返回500错误",
                goal="修复这个错误",
            )
        )
        assert result.task_type == TaskType.PROBLEM_SOLVING
        assert result.confidence > 0.5

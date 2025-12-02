"""LLM任务分类集成测试

真实的端到端LLM分类测试，验证：
1. LangChain LLM客户端正常工作
2. 任务分类Prompt模板有效
3. 分类结果格式正确
4. 置信度合理

注意：此测试需要真实的OPENAI_API_KEY配置
"""

import pytest

from src.application.use_cases.classify_task import (
    ClassifyTaskInput,
    ClassifyTaskUseCase,
)
from src.domain.value_objects.task_type import TaskType
from src.lc.llm_client import get_llm_for_classification


@pytest.mark.integration
class TestLLMClassificationIntegration:
    """LLM任务分类集成测试"""

    @pytest.fixture
    def use_case(self):
        """创建集成测试的UseCase"""
        try:
            llm_client = get_llm_for_classification()
            return ClassifyTaskUseCase(llm_client=llm_client)
        except ValueError as e:
            if "OPENAI_API_KEY" in str(e):
                pytest.skip("需要配置 OPENAI_API_KEY 环境变量")
            raise

    def test_classify_data_analysis_task_with_real_llm(self, use_case):
        """测试：使用真实LLM分类数据分析任务"""
        input_data = ClassifyTaskInput(
            start="我有销售数据CSV文件", goal="分析销售趋势并生成月度报表"
        )

        result = use_case.execute(input_data)

        # 验证基本结构
        assert isinstance(result.task_type, TaskType)
        assert isinstance(result.confidence, float)
        assert isinstance(result.reasoning, str)
        assert isinstance(result.suggested_tools, list)

        # 验证分类结果（应该识别为数据分析）
        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence >= 0.5  # 真实LLM的置信度可能较低
        assert len(result.reasoning) > 10
        assert "database" in result.suggested_tools

    def test_classify_content_creation_task_with_real_llm(self, use_case):
        """测试：使用真实LLM分类内容创建任务"""
        input_data = ClassifyTaskInput(start="需要发布新产品", goal="写产品介绍文案和营销内容")

        result = use_case.execute(input_data)

        # 验证分类结果
        assert result.task_type == TaskType.CONTENT_CREATION
        assert result.confidence >= 0.5
        assert len(result.reasoning) > 10
        assert "llm" in result.suggested_tools

    def test_classify_research_task_with_real_llm(self, use_case):
        """测试：使用真实LLM分类研究任务"""
        input_data = ClassifyTaskInput(start="准备开发新功能", goal="调研竞品功能和市场定位")

        result = use_case.execute(input_data)

        # 验证分类结果
        assert result.task_type == TaskType.RESEARCH
        assert result.confidence >= 0.5
        assert len(result.reasoning) > 10

    def test_classify_problem_solving_task_with_real_llm(self, use_case):
        """测试：使用真实LLM分类问题解决任务"""
        input_data = ClassifyTaskInput(start="API接口异常", goal="调试并���复500错误问题")

        result = use_case.execute(input_data)

        # 验证分类结果
        assert result.task_type == TaskType.PROBLEM_SOLVING
        assert result.confidence >= 0.5
        assert len(result.reasoning) > 10

    def test_classify_with_context_information(self, use_case):
        """测试：使用真实LLM分类带上下文的任务"""
        input_data = ClassifyTaskInput(
            start="查看最新数据",
            goal="分析业务趋势",
            context={"previous_tasks": ["数据分析", "报表生成"]},
        )

        result = use_case.execute(input_data)

        # 验证分类结果
        assert result.task_type == TaskType.DATA_ANALYSIS
        # 有上下文时置信度应该更高
        assert result.confidence >= 0.6
        assert len(result.reasoning) > 10

    def test_unknown_task_classification(self, use_case):
        """测试：使用真实LLM分类模糊任务"""
        input_data = ClassifyTaskInput(start="做点什么", goal="完成工作")

        result = use_case.execute(input_data)

        # 验证基本结构（可能是UNKNOWN或其他类型）
        assert isinstance(result.task_type, TaskType)
        assert isinstance(result.confidence, float)
        # 模糊任务应该被识别为UNKNOWN，但LLM的置信度判断可能不同
        # 关键是推理过程应该明确说明为什么是模糊的
        if result.task_type == TaskType.UNKNOWN:
            # 如果识别为UNKNOWN，推理应该包含模糊性说明
            assert any(
                kw in result.reasoning.lower() for kw in ["模糊", "不明确", "不够具体", "无法判断"]
            )
        assert len(result.reasoning) > 5

    @pytest.mark.parametrize(
        "task_description,expected_type",
        [
            (("有销售数据", "生成分析图表"), TaskType.DATA_ANALYSIS),
            (("新产品上线", "写推广文案"), TaskType.CONTENT_CREATION),
            (("系统报错", "排查问题原因"), TaskType.PROBLEM_SOLVING),
            (("每天早上", "自动发送邮件"), TaskType.AUTOMATION),
            (("学习新技术", "查找资料文档"), TaskType.RESEARCH),
        ],
    )
    def test_various_task_types_accuracy(self, use_case, task_description, expected_type):
        """测试：验证各种任务类型的分类准确率"""
        start, goal = task_description
        input_data = ClassifyTaskInput(start=start, goal=goal)

        result = use_case.execute(input_data)

        # 主要验证类型是否正确
        assert result.task_type == expected_type, (
            f"任务 {start} -> {goal} 分类错误: 期望 {expected_type}, 实际 {result.task_type}"
        )

        # 置信度应该合理
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.reasoning) > 5

    def test_classification_consistency(self, use_case):
        """测试：分类结果的一致性"""
        input_data = ClassifyTaskInput(start="分析用户数据", goal="生成业务报表")

        # 多次调用相同任务，结果应该一致
        results = []
        for _ in range(3):
            result = use_case.execute(input_data)
            results.append(result)

        # 验证一致性
        first_result = results[0]
        for result in results[1:]:
            assert result.task_type == first_result.task_type
            # 置信度可能略有差异，但应该接近
            assert abs(result.confidence - first_result.confidence) < 0.2

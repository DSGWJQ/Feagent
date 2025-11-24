"""测试：ClassifyTaskUseCase - 真实LLM集成

TDD RED阶段：首先编写测试用例，明确LLM分类的需求和验收标准

业务背景：
- ClassifyTaskUseCase当前使用关键词匹配（临时实现）
- 需要升级为真正的LLM调用，提高分类准确性
- V2验收标准：分类准确率≥85%

测试覆盖：
1. 真实LLM调用的分类功能
2. 不同任务类型的分类准确性
3. 分类结果的置信度和推理
4. 工具推荐功能
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.application.use_cases.classify_task import (
    ClassifyTaskInput,
    ClassifyTaskOutput,
    ClassifyTaskUseCase,
)
from src.domain.value_objects.task_type import TaskType


class TestClassifyTaskUseCaseWithLLM:
    """测试 ClassifyTaskUseCase 与真实 LLM 集成"""

    def test_classify_data_analysis_task_with_llm(self):
        """测试：LLM分类数据分析任务

        场景：
        - 用户输入包含数据分析相关描述
        - 系统调用 LLM 进行智能分类

        验收标准：
        - 分类为 DATA_ANALYSIS
        - 置信度 ≥ 0.7
        - 包含合理的推理说明
        - 推荐相关工具
        """
        # Arrange
        llm_client = Mock()
        llm_client.invoke.return_value.content = """
        {
            "task_type": "DATA_ANALYSIS",
            "confidence": 0.92,
            "reasoning": "用户提到'分析销售数据'和'生成报表'，这是典型的数据分析任务",
            "suggested_tools": ["database", "python", "http"]
        }
        """

        use_case = ClassifyTaskUseCase(llm_client=llm_client)

        input_data = ClassifyTaskInput(
            start="我有销售数据文件",
            goal="分析数据趋势并生成月度报表"
        )

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence >= 0.7
        assert "分析" in result.reasoning.lower() or "报表" in result.reasoning.lower()
        assert result.suggested_tools is not None
        assert "database" in result.suggested_tools

    def test_classify_content_creation_task_with_llm(self):
        """测试：LLM分类内容创建任务

        场景：
        - 用户输入包含内容创建相关描述
        - 系统调用 LLM 进行智能分类

        验收标准：
        - 分类为 CONTENT_CREATION
        - 置信度 ≥ 0.7
        - 包含合理的推理说明
        """
        # Arrange
        llm_client = Mock()
        llm_client.invoke.return_value.content = """
        {
            "task_type": "CONTENT_CREATION",
            "confidence": 0.88,
            "reasoning": "用户要求'写一篇产品介绍'和'生成文案'，这是内容创建任务",
            "suggested_tools": ["llm", "http"]
        }
        """

        use_case = ClassifyTaskUseCase(llm_client=llm_client)

        input_data = ClassifyTaskInput(
            start="需要发布新产品",
            goal="写产品介绍文案和营销内容"
        )

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.task_type == TaskType.CONTENT_CREATION
        assert result.confidence >= 0.7
        assert "写" in result.reasoning.lower() or "创建" in result.reasoning.lower()

    def test_classify_problem_solving_task_with_llm(self):
        """测试：LLM分类问题解决任务

        场景：
        - 用户输��包含问题解决相关描述
        - 系统调用 LLM 进行智能分类

        验收标准：
        - 分类为 PROBLEM_SOLVING
        - 置信度 ≥ 0.7
        - 包含合理的推理说明
        """
        # Arrange
        llm_client = Mock()
        llm_client.invoke.return_value.content = """
        {
            "task_type": "PROBLEM_SOLVING",
            "confidence": 0.85,
            "reasoning": "用户提到'API返回500错误'和'修复问题'，这是典型的问题解决任务",
            "suggested_tools": ["http", "database", "file"]
        }
        """

        use_case = ClassifyTaskUseCase(llm_client=llm_client)

        input_data = ClassifyTaskInput(
            start="系统出现异常",
            goal="调试并修复API错误"
        )

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.task_type == TaskType.PROBLEM_SOLVING
        assert result.confidence >= 0.7
        assert "错误" in result.reasoning.lower() or "修复" in result.reasoning.lower()

    def test_llm_classification_with_context(self):
        """测试：LLM分类考虑上下文信息

        场景：
        - 用户提供了历史任务上下文
        - LLM需要结合上下文进行更准确的分类

        验收标准：
        - 利用上下文信息提高分类准确性
        - 置信度更高
        """
        # Arrange
        llm_client = Mock()
        llm_client.invoke.return_value.content = """
        {
            "task_type": "DATA_ANALYSIS",
            "confidence": 0.95,
            "reasoning": "基于历史任务，用户经常处理数据分析，这次也提到'趋势分析'，高度匹配",
            "suggested_tools": ["database", "python", "http"]
        }
        """

        use_case = ClassifyTaskUseCase(llm_client=llm_client)

        input_data = ClassifyTaskInput(
            start="查看最新数据",
            goal="分析业务趋势",
            context={"previous_tasks": ["数据分析", "报表生成"]}
        )

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence >= 0.9  # 有上下文时置信度更高

    def test_llm_classification_fallback_to_keywords(self):
        """测试：LLM调用失败时回退到关键词匹配

        场景：
        - LLM 服务不可用或调用失败
        - 系统自动回退到关键词匹配

        验收标准：
        - 仍然能够返回分类结果
        - 使用关键词匹配逻辑
        """
        # Arrange
        llm_client = Mock()
        llm_client.invoke.side_effect = Exception("LLM service unavailable")

        use_case = ClassifyTaskUseCase(llm_client=llm_client)

        input_data = ClassifyTaskInput(
            start="分析销售数据",
            goal="生成报表"
        )

        # Act & Assert
        # 这里应该回退到关键词匹配，不会抛出异常
        result = use_case.execute(input_data)

        # 验证关键词匹配逻辑
        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence >= 0.5

    def test_llm_response_parsing_error_handling(self):
        """测试：LLM响应解析错误处理

        场景：
        - LLM 返回格式错误的响应
        - 系统应该优雅处理错误

        验收标准：
        - 不会崩溃
        - 返回默认分类
        - 包含错误说明
        """
        # Arrange
        llm_client = Mock()
        llm_client.invoke.return_value.content = "invalid json response"

        use_case = ClassifyTaskUseCase(llm_client=llm_client)

        input_data = ClassifyTaskInput(
            start="测试任务",
            goal="测试目标"
        )

        # Act
        result = use_case.execute(input_data)

        # Assert
        # 应该回退到关键词匹配
        assert result.task_type is not None
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_async_llm_classification(self):
        """测试：异步LLM分类调用

        场景：
        - 未来可能需要支持异步LLM调用
        - 验证异步接口的可用性

        验收标准：
        - 能够调用异步LLM方法
        - 返回正确的分类结果
        """
        # Arrange
        llm_client = AsyncMock()
        llm_client.ainvoke.return_value.content = """
        {
            "task_type": "RESEARCH",
            "confidence": 0.85,
            "reasoning": "用户提到'调研竞品'，这是研究类任务",
            "suggested_tools": ["http", "llm"]
        }
        """

        use_case = ClassifyTaskUseCase(llm_client=llm_client)

        input_data = ClassifyTaskInput(
            start="准备新产品开发",
            goal="调研竞品功能和市场定位"
        )

        # Act - 注意：这里我们需要实现异步版本的execute方法
        # result = await use_case.execute_async(input_data)

        # Assert - 暂时跳过，等实现异步方法后再测试
        pass
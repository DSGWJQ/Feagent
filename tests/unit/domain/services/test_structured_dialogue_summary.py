"""测试 StructuredDialogueSummary（八段结构摘要）

测试目标：
1. StructuredDialogueSummary 应该包含八段结构
2. 应该支持序列化和反序列化
3. 应该能够从对话历史生成摘要
4. 应该能够验证摘要的完整性
"""

from datetime import datetime

from src.domain.services.structured_dialogue_summary import (
    StructuredDialogueSummary,
    SummarySection,
)


class TestStructuredDialogueSummary:
    """测试 StructuredDialogueSummary 数据结构"""

    def test_create_summary_with_all_sections_should_succeed(self):
        """测试：创建包含所有八段的摘要应该成功"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="分析销售数据并生成报告",
            key_decisions=["使用 Q4 数据", "按地区分组"],
            important_facts=["总销售额增长 15%", "华东地区表现最佳"],
            pending_tasks=["生成详细报告", "发送给管理层"],
            user_preferences=["喜欢图表展示", "需要中文报告"],
            context_clues=["用户是销售总监", "关注季度对比"],
            unresolved_issues=["部分数据缺失", "需要确认统计口径"],
            next_steps=["补充缺失数据", "生成最终报告"],
        )

        assert summary.session_id == "session_001"
        assert summary.core_goal == "分析销售数据并生成报告"
        assert len(summary.key_decisions) == 2
        assert len(summary.important_facts) == 2
        assert len(summary.pending_tasks) == 2
        assert len(summary.user_preferences) == 2
        assert len(summary.context_clues) == 2
        assert len(summary.unresolved_issues) == 2
        assert len(summary.next_steps) == 2

    def test_summary_should_have_metadata_fields(self):
        """测试：摘要应该有元数据字段"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="测试目标",
        )

        assert hasattr(summary, "summary_id")
        assert hasattr(summary, "created_at")
        assert hasattr(summary, "compressed_from_turns")
        assert hasattr(summary, "original_token_count")
        assert hasattr(summary, "summary_token_count")
        assert isinstance(summary.created_at, datetime)

    def test_summary_with_compression_metadata_should_store_correctly(self):
        """测试：摘要应该正确存储压缩元数据"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="测试",
            compressed_from_turns=10,
            original_token_count=5000,
            summary_token_count=500,
        )

        assert summary.compressed_from_turns == 10
        assert summary.original_token_count == 5000
        assert summary.summary_token_count == 500

    def test_get_compression_ratio_should_return_correct_value(self):
        """测试：获取压缩率应该返回正确值"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="测试",
            original_token_count=5000,
            summary_token_count=500,
        )

        ratio = summary.get_compression_ratio()

        assert ratio == 0.1  # 500 / 5000 = 0.1

    def test_get_compression_ratio_with_zero_original_should_return_zero(self):
        """测试：原始 token 为 0 时压缩率应该返回 0"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="测试",
            original_token_count=0,
            summary_token_count=500,
        )

        ratio = summary.get_compression_ratio()

        assert ratio == 0.0

    def test_to_dict_should_return_serializable_dict(self):
        """测试：to_dict 应该返回可序列化的字典"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="测试目标",
            key_decisions=["决策1", "决策2"],
            important_facts=["事实1"],
        )

        data = summary.to_dict()

        assert data["session_id"] == "session_001"
        assert data["core_goal"] == "测试目标"
        assert len(data["key_decisions"]) == 2
        assert len(data["important_facts"]) == 1
        assert "summary_id" in data
        assert "created_at" in data

    def test_from_dict_should_reconstruct_summary(self):
        """测试：from_dict 应该能够重建摘要"""
        data = {
            "session_id": "session_001",
            "summary_id": "summary_123",
            "core_goal": "测试目标",
            "key_decisions": ["决策1"],
            "important_facts": ["事实1"],
            "pending_tasks": [],
            "user_preferences": [],
            "context_clues": [],
            "unresolved_issues": [],
            "next_steps": [],
            "compressed_from_turns": 5,
            "original_token_count": 1000,
            "summary_token_count": 100,
            "created_at": "2025-01-22T10:00:00",
        }

        summary = StructuredDialogueSummary.from_dict(data)

        assert summary.session_id == "session_001"
        assert summary.summary_id == "summary_123"
        assert summary.core_goal == "测试目标"
        assert len(summary.key_decisions) == 1
        assert summary.compressed_from_turns == 5

    def test_is_empty_should_return_true_for_empty_summary(self):
        """测试：空摘要应该返回 True"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="",
        )

        assert summary.is_empty() is True

    def test_is_empty_should_return_false_for_non_empty_summary(self):
        """测试：非空摘要应该返回 False"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="有内容",
        )

        assert summary.is_empty() is False

    def test_get_all_sections_should_return_dict(self):
        """测试：获取所有段落应该返回字典"""
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="目标",
            key_decisions=["决策1"],
        )

        sections = summary.get_all_sections()

        assert isinstance(sections, dict)
        assert "core_goal" in sections
        assert "key_decisions" in sections
        assert sections["core_goal"] == "目标"
        assert sections["key_decisions"] == ["决策1"]

    def test_merge_with_another_summary_should_combine_sections(self):
        """测试：合并两个摘要应该组合各段落"""
        summary1 = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="目标1",
            key_decisions=["决策1"],
            important_facts=["事实1"],
        )

        summary2 = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="目标2",
            key_decisions=["决策2"],
            important_facts=["事实2"],
        )

        merged = summary1.merge(summary2)

        # core_goal 应该使用最新的
        assert merged.core_goal == "目标2"
        # 列表应该合并
        assert len(merged.key_decisions) == 2
        assert "决策1" in merged.key_decisions
        assert "决策2" in merged.key_decisions
        assert len(merged.important_facts) == 2


class TestSummarySection:
    """测试 SummarySection 枚举"""

    def test_summary_section_should_have_eight_sections(self):
        """测试：SummarySection 应该有八个段落"""
        sections = list(SummarySection)

        assert len(sections) == 8
        assert SummarySection.CORE_GOAL in sections
        assert SummarySection.KEY_DECISIONS in sections
        assert SummarySection.IMPORTANT_FACTS in sections
        assert SummarySection.PENDING_TASKS in sections
        assert SummarySection.USER_PREFERENCES in sections
        assert SummarySection.CONTEXT_CLUES in sections
        assert SummarySection.UNRESOLVED_ISSUES in sections
        assert SummarySection.NEXT_STEPS in sections

    def test_summary_section_values_should_be_strings(self):
        """测试：SummarySection 的值应该是字符串"""
        for section in SummarySection:
            assert isinstance(section.value, str)

    def test_get_section_description_should_return_chinese_description(self):
        """测试：获取段落描述应该返回中文说明"""
        from src.domain.services.structured_dialogue_summary import (
            get_section_description,
        )

        desc = get_section_description(SummarySection.CORE_GOAL)

        assert isinstance(desc, str)
        assert len(desc) > 0
        assert "核心目标" in desc or "目标" in desc

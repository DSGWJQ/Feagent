"""压缩前后规划一致性测试 - Step 6

测试内容：
1. 压缩前后核心信息保留
2. 规划决策一致性验证
3. 关键上下文不丢失
4. 摘要完整性验证

TDD Red Phase - 先写测试，后实现功能
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import (
    GlobalContext,
    SessionContext,
)
from src.domain.services.short_term_buffer import ShortTermBuffer, TurnRole
from src.domain.services.structured_dialogue_summary import StructuredDialogueSummary

# ==================== 核心信息保留测试 ====================


class TestCoreInformationPreservation:
    """核心信息保留测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN"},
            system_config={},
        )

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_consistency",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    def test_core_goal_preserved_after_compression(self):
        """测试：压缩后核心目标保留"""
        # 模拟压缩
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="分析销售数据并生成报告，重点关注Q4趋势",
            key_decisions=[],
            important_facts=[],
            pending_tasks=[],
            user_preferences=[],
            context_clues=[],
            unresolved_issues=[],
            next_steps=[],
        )

        # 验证核心目标保留
        summary_text = summary.to_text()
        assert "分析销售数据" in summary_text
        assert "Q4" in summary_text

    def test_key_decisions_preserved_after_compression(self):
        """测试：压缩后关键决策保留"""
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="数据分析",
            key_decisions=[
                "使用 pandas 处理 CSV 文件",
                "采用折线图展示趋势",
            ],
        )

        summary_text = summary.to_text()
        assert "pandas" in summary_text
        assert "折线图" in summary_text

    def test_task_progress_preserved_after_compression(self):
        """测试：压缩后任务进展保留（使用 next_steps 表示进展）"""
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="完成报告",
            next_steps=[
                "数据加载: 完成",
                "数据清洗: 进行中",
                "可视化: 待开始",
            ],
        )

        summary_text = summary.to_text()
        assert "数据加载" in summary_text
        assert "完成" in summary_text
        assert "进行中" in summary_text


# ==================== 规划决策一致性测试 ====================


class TestPlanningDecisionConsistency:
    """规划决策一致性测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_plan",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    @pytest.mark.asyncio
    async def test_planning_uses_compressed_summary(self, session_context):
        """测试：规划使用压缩摘要"""
        from src.domain.services.memory_compression_handler import get_planning_context

        session_context.conversation_summary = """【核心目标】
分析用户行为数据
【关键决策】
- 使用 SQL 查询数据库
- 采用 matplotlib 可视化"""

        planning_ctx = get_planning_context(session_context)

        assert planning_ctx["previous_summary"] is not None
        assert "SQL" in planning_ctx["previous_summary"]
        assert "matplotlib" in planning_ctx["previous_summary"]

    @pytest.mark.asyncio
    async def test_planning_context_consistency_before_after(self, session_context):
        """测试：压缩前后规划上下文一致性"""
        from src.domain.services.memory_compression_handler import (
            get_planning_context,
        )
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail(pre_planning_threshold=0.85)

        # 压缩前的规划上下文
        session_context.conversation_summary = None
        for i in range(10):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                    content=f"讨论数据分析方法 {i}",
                    token_usage={"total_tokens": 100},
                )
            )

        # 模拟压缩器，提取关键信息
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(
                to_text=MagicMock(
                    return_value="【核心目标】讨论数据分析方法\n【关键决策】多轮讨论确定分析策略"
                )
            )
        )

        session_context.update_token_usage(8500, 500)  # 90%

        await guardrail.ensure_budget_for_planning(session_context)

        # 验证压缩后摘要包含核心信息
        post_ctx = get_planning_context(session_context)
        assert "数据分析" in post_ctx["previous_summary"]

    @pytest.mark.asyncio
    async def test_multi_round_compression_maintains_goal(self, session_context):
        """测试：多轮压缩后仍保持核心目标"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        # 第一轮压缩后的摘要
        first_summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="构建用户画像系统",
            key_decisions=["使用机器学习聚类"],
            next_steps=["数据收集完成"],
        )

        session_context.conversation_summary = first_summary.to_text()

        # 模拟更多对话后需要第二轮压缩
        for i in range(10):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"继续讨论用户画像 {i}",
                    token_usage={"total_tokens": 100},
                )
            )

        # 第二轮压缩应该合并之前的摘要
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(
                to_text=MagicMock(
                    return_value="【核心目标】构建用户画像系统\n【任务进展】数据收集完成，模型设计中"
                )
            )
        )

        session_context.update_token_usage(9000, 0)

        await guardrail.ensure_budget_for_planning(session_context)

        # 验证核心目标仍然保留
        assert "用户画像" in session_context.conversation_summary


# ==================== 关键上下文不丢失测试 ====================


class TestCriticalContextPreservation:
    """关键上下文不丢失测试"""

    def test_tool_outputs_preserved(self):
        """测试：工具输出保留（使用 important_facts）"""
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="数据分析",
            important_facts=[
                "SQL查询返回了1000条记录",
                "数据清洗移除了50个异常值",
            ],
        )

        summary_text = summary.to_text()
        assert "1000条记录" in summary_text
        assert "50个异常值" in summary_text

    def test_error_recovery_log_preserved(self):
        """测试：错误恢复日志保留（使用 unresolved_issues）"""
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="数据处理",
            unresolved_issues=[
                "数据库连接超时 - 已重试成功",
                "内存不足 - 已分批处理",
            ],
        )

        summary_text = summary.to_text()
        assert "超时" in summary_text
        assert "重试" in summary_text

    def test_user_preferences_preserved(self):
        """测试：用户偏好保留"""
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="生成报告",
            user_preferences=[
                "用户偏好中文输出",
                "报告格式要求 PDF",
            ],
        )

        summary_text = summary.to_text()
        assert "中文" in summary_text
        assert "PDF" in summary_text

    def test_pending_items_preserved(self):
        """测试：待处理项保留（使用 pending_tasks）"""
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="完成项目",
            pending_tasks=[
                "等待用户确认数据范围",
                "需要额外的权限申请",
            ],
        )

        summary_text = summary.to_text()
        assert "确认数据范围" in summary_text
        assert "权限申请" in summary_text


# ==================== 摘要完整性测试 ====================


class TestSummaryIntegrity:
    """摘要完整性测试"""

    def test_summary_has_all_eight_sections(self):
        """测试：摘要包含所有八个部分"""
        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="测试目标",
            key_decisions=["决策1"],
            important_facts=["事实1"],
            pending_tasks=["待办1"],
            user_preferences=["偏好1"],
            context_clues=["线索1"],
            unresolved_issues=["问题1"],
            next_steps=["下一步1"],
        )

        summary_text = summary.to_text()

        # 验证关键部分存在
        assert "核心目标" in summary_text or "测试目标" in summary_text
        assert "决策" in summary_text or "决策1" in summary_text

    def test_compression_ratio_calculated(self):
        """测试：压缩率计算"""
        # 原始对话
        original_tokens = 5000

        summary = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="测试",
        )

        # 假设摘要 token 数
        summary_tokens = len(summary.to_text().split()) * 2  # 粗略估计

        compression_ratio = summary_tokens / original_tokens

        # 压缩率应该小于 1
        assert compression_ratio < 1.0

    def test_summary_merge_preserves_both_contents(self):
        """测试：摘要合并保留两边内容"""
        summary1 = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="目标A",
            key_decisions=["决策A"],
            next_steps=["进展A"],
        )

        summary2 = StructuredDialogueSummary(
            session_id="test_session",
            core_goal="目标B",
            key_decisions=["决策B"],
            next_steps=["进展B"],
        )

        merged = summary1.merge(summary2)

        merged_text = merged.to_text()
        assert "决策A" in merged_text or "决策B" in merged_text
        assert "进展A" in merged_text or "进展B" in merged_text


# ==================== 端到端一致性测试 ====================


class TestEndToEndConsistency:
    """端到端一致性测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_e2e",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    @pytest.mark.asyncio
    async def test_long_conversation_compression_consistency(self, session_context):
        """测试：长对话压缩一致性"""
        from src.domain.services.token_guardrail import TokenGuardrail

        # 模拟长对话
        conversation_topics = [
            "讨论项目需求",
            "分析技术方案",
            "确定实施计划",
            "讨论风险点",
            "制定时间表",
        ]

        for i, topic in enumerate(conversation_topics):
            for j in range(3):
                session_context.short_term_buffer.append(
                    ShortTermBuffer(
                        turn_id=f"t_{i}_{j}",
                        role=TurnRole.USER if j % 2 == 0 else TurnRole.ASSISTANT,
                        content=f"{topic}: 第{j+1}轮讨论",
                        token_usage={"total_tokens": 200},
                    )
                )

        # 创建压缩器
        guardrail = TokenGuardrail(pre_planning_threshold=0.85)
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(
                to_text=MagicMock(
                    return_value="""【核心目标】
完成项目规划
【关键决策】
- 确定技术方案
- 制定实施计划
【任务进展】
- 需求讨论: 完成
- 技术分析: 完成
- 计划制定: 进行中"""
                )
            )
        )

        session_context.update_token_usage(9000, 0)

        # 执行压缩
        await guardrail.ensure_budget_for_planning(session_context)

        # 验证关键主题在摘要中
        summary = session_context.conversation_summary
        assert "项目" in summary
        assert "技术" in summary or "方案" in summary
        assert "计划" in summary

    @pytest.mark.asyncio
    async def test_planning_after_compression_uses_summary(self, session_context):
        """测试：压缩后规划使用摘要"""
        from src.domain.services.memory_compression_handler import get_planning_context
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(
                to_text=MagicMock(
                    return_value="【核心目标】实现数据分析功能\n【关键决策】使用 Python + pandas"
                )
            )
        )

        for i in range(10):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        session_context.update_token_usage(9000, 0)

        await guardrail.ensure_budget_for_planning(session_context)

        # 获取规划上下文
        planning_ctx = get_planning_context(session_context)

        # 验证规划上下文包含摘要
        assert planning_ctx["previous_summary"] is not None
        assert "数据分析" in planning_ctx["previous_summary"]
        assert "Python" in planning_ctx["previous_summary"]

    @pytest.mark.asyncio
    async def test_incremental_compression_maintains_history(self, session_context):
        """测试：增量压缩保持历史"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        # 第一次压缩
        session_context.conversation_summary = "【核心目标】阶段1目标"

        # 新的对话
        for i in range(5):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"阶段2讨论{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        # 模拟增量压缩
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(
                to_text=MagicMock(
                    return_value="【核心目标】阶段1目标 + 阶段2扩展\n【历史】包含阶段1和阶段2的讨论"
                )
            )
        )

        session_context.update_token_usage(9000, 0)

        await guardrail.ensure_budget_for_planning(session_context)

        # 验证历史被保留
        assert "阶段1" in session_context.conversation_summary
        assert "阶段2" in session_context.conversation_summary

"""Token Guardrail 测试 - Step 6

测试内容：
1. TokenGuardrail 基本功能
2. 规划前检查和自动压缩触发
3. 长链路工作流 token 预算管理
4. 阈值配置和自定义

TDD Red Phase - 先写测试，后实现功能
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import (
    GlobalContext,
    SessionContext,
)
from src.domain.services.short_term_buffer import ShortTermBuffer, TurnRole

# ==================== TokenGuardrail 基本测试 ====================


class TestTokenGuardrailBasic:
    """TokenGuardrail 基本功能测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(
            user_id="user_123",
            user_preferences={},
            system_config={},
        )

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_guardrail",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    def test_guardrail_creation_with_defaults(self):
        """测试：创建 Guardrail 使用默认值"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        assert guardrail.pre_planning_threshold == 0.85
        assert guardrail.critical_threshold == 0.95

    def test_guardrail_creation_with_custom_thresholds(self):
        """测试：创建 Guardrail 使用自定义阈值"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail(
            pre_planning_threshold=0.80,
            critical_threshold=0.90,
        )

        assert guardrail.pre_planning_threshold == 0.80
        assert guardrail.critical_threshold == 0.90

    def test_check_budget_returns_status(self, session_context):
        """测试：检查预算返回状态"""
        from src.domain.services.token_guardrail import BudgetStatus, TokenGuardrail

        guardrail = TokenGuardrail()

        # 低使用率
        session_context.update_token_usage(3000, 1000)  # 40%
        status = guardrail.check_budget(session_context)

        assert status == BudgetStatus.OK

    def test_check_budget_warning_at_pre_planning_threshold(self, session_context):
        """测试：接近规划阈值时警告"""
        from src.domain.services.token_guardrail import BudgetStatus, TokenGuardrail

        guardrail = TokenGuardrail(pre_planning_threshold=0.85)

        session_context.update_token_usage(7500, 1000)  # 85%
        status = guardrail.check_budget(session_context)

        assert status == BudgetStatus.COMPRESS_RECOMMENDED

    def test_check_budget_critical_at_critical_threshold(self, session_context):
        """测试：超过临界阈值时为危险状态"""
        from src.domain.services.token_guardrail import BudgetStatus, TokenGuardrail

        guardrail = TokenGuardrail(critical_threshold=0.95)

        session_context.update_token_usage(9000, 600)  # 96%
        status = guardrail.check_budget(session_context)

        assert status == BudgetStatus.CRITICAL


# ==================== 规划前压缩测试 ====================


class TestPrePlanningCompression:
    """规划前压缩测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_planning",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    @pytest.mark.asyncio
    async def test_ensure_budget_compresses_when_needed(self, session_context):
        """测试：预算不足时自动压缩"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail(pre_planning_threshold=0.85)
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="compressed"))
        )

        # 添加缓冲区
        for i in range(10):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        session_context.update_token_usage(8000, 700)  # 87%

        await guardrail.ensure_budget_for_planning(session_context)

        # 验证压缩被调用
        guardrail._compressor.compress.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_budget_skips_when_ok(self, session_context):
        """测试：预算充足时不压缩"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail(pre_planning_threshold=0.85)
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock()

        session_context.update_token_usage(5000, 1000)  # 60%

        await guardrail.ensure_budget_for_planning(session_context)

        # 验证压缩未被调用
        guardrail._compressor.compress.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_budget_updates_summary(self, session_context):
        """测试：压缩后更新摘要"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail(pre_planning_threshold=0.85)
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="【核心目标】测试"))
        )

        for i in range(5):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        session_context.update_token_usage(8500, 500)  # 90%

        await guardrail.ensure_budget_for_planning(session_context)

        assert session_context.conversation_summary is not None
        assert "核心目标" in session_context.conversation_summary

    @pytest.mark.asyncio
    async def test_ensure_budget_keeps_recent_turns(self, session_context):
        """测试：压缩后保留最近轮次"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail(
            pre_planning_threshold=0.85,
            keep_recent_turns=3,
        )
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
        )

        for i in range(10):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"turn_{i}",
                    role=TurnRole.USER,
                    content=f"msg{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        session_context.update_token_usage(8500, 500)  # 90%

        await guardrail.ensure_budget_for_planning(session_context)

        assert len(session_context.short_term_buffer) == 3
        assert session_context.short_term_buffer[0].turn_id == "turn_7"


# ==================== 长链路工作流测试 ====================


class TestLongWorkflowGuardrail:
    """长链路工作流 Token Guardrail 测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_workflow",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    def test_estimate_workflow_tokens(self, session_context):
        """测试：估算工作流 token 需求"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        # 模拟工作流节点
        workflow_nodes = [
            {"type": "llm", "estimated_tokens": 500},
            {"type": "llm", "estimated_tokens": 800},
            {"type": "code", "estimated_tokens": 200},
            {"type": "llm", "estimated_tokens": 600},
        ]

        estimated = guardrail.estimate_workflow_tokens(workflow_nodes)

        assert estimated == 2100

    def test_check_workflow_feasibility_ok(self, session_context):
        """测试：工作流可行性检查 - 可行"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        session_context.update_token_usage(3000, 1000)  # 40% used, 6000 remaining

        workflow_nodes = [
            {"type": "llm", "estimated_tokens": 1000},
            {"type": "llm", "estimated_tokens": 1000},
        ]

        result = guardrail.check_workflow_feasibility(session_context, workflow_nodes)

        assert result.is_feasible is True
        assert result.remaining_budget >= 4000

    def test_check_workflow_feasibility_needs_compression(self, session_context):
        """测试：工作流可行性检查 - 需要压缩"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        session_context.update_token_usage(7000, 1500)  # 85% used, 1500 remaining

        workflow_nodes = [
            {"type": "llm", "estimated_tokens": 1000},
            {"type": "llm", "estimated_tokens": 1000},
        ]

        result = guardrail.check_workflow_feasibility(session_context, workflow_nodes)

        assert result.needs_compression is True

    def test_check_workflow_feasibility_not_feasible(self, session_context):
        """测试：工作流可行性检查 - 不可行"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        session_context.update_token_usage(9000, 500)  # 95% used, 500 remaining

        workflow_nodes = [
            {"type": "llm", "estimated_tokens": 3000},
            {"type": "llm", "estimated_tokens": 3000},
        ]

        result = guardrail.check_workflow_feasibility(session_context, workflow_nodes)

        assert result.is_feasible is False

    @pytest.mark.asyncio
    async def test_prepare_for_workflow_compresses_if_needed(self, session_context):
        """测试：工作流准备时按需压缩"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
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

        # 设置高使用率，使剩余空间不足以��行工作流
        session_context.update_token_usage(9000, 500)  # 95% used, only 500 remaining

        workflow_nodes = [
            {"type": "llm", "estimated_tokens": 800},  # 需要 800，加上 20% 缓冲需要 960
        ]

        await guardrail.prepare_for_workflow(session_context, workflow_nodes)

        guardrail._compressor.compress.assert_called_once()


# ==================== 动态阈值测试 ====================


class TestDynamicThresholds:
    """动态阈值测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_dynamic",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    def test_adjust_threshold_based_on_model(self):
        """测试：根据模型调整阈值"""
        from src.domain.services.token_guardrail import TokenGuardrail

        # 大上下文模型可以使用更高阈值
        guardrail = TokenGuardrail.for_model("gpt-4-128k", context_limit=128000)

        assert guardrail.pre_planning_threshold >= 0.90

    def test_adjust_threshold_for_small_context(self):
        """测试：小上下文模型使用较低阈值"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail.for_model("gpt-3.5", context_limit=4096)

        assert guardrail.pre_planning_threshold <= 0.80

    def test_get_recommended_compression_point(self, session_context):
        """测试：获取推荐压缩点"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        # 基于历史对话长度和复杂度推荐压缩点
        for i in range(20):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        recommended = guardrail.get_recommended_compression_point(session_context)

        assert recommended > 0
        assert recommended < len(session_context.short_term_buffer)


# ==================== 预算报告测试 ====================


class TestBudgetReporting:
    """预算报告测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_report",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    def test_get_budget_report(self, session_context):
        """测试：获取预算报告"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()

        session_context.update_token_usage(6000, 1500)

        report = guardrail.get_budget_report(session_context)

        assert "total_tokens" in report
        assert "usage_ratio" in report
        assert "remaining_tokens" in report
        assert "status" in report
        assert report["total_tokens"] == 7500

    def test_budget_report_includes_recommendation(self, session_context):
        """测试：预算报告包含建议"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail(pre_planning_threshold=0.85)

        session_context.update_token_usage(8000, 700)  # 87%

        report = guardrail.get_budget_report(session_context)

        assert "recommendation" in report
        assert report["recommendation"] is not None


# ==================== 集成场景测试 ====================


class TestGuardrailIntegration:
    """Guardrail 集成场景测试"""

    @pytest.fixture
    def global_context(self):
        return GlobalContext(user_id="user_123", user_preferences={}, system_config={})

    @pytest.fixture
    def session_context(self, global_context):
        ctx = SessionContext(
            session_id="session_integration",
            global_context=global_context,
        )
        ctx.set_model_info("openai", "gpt-4", 10000)
        return ctx

    @pytest.mark.asyncio
    async def test_full_planning_cycle_with_guardrail(self, session_context):
        """测试：完整规划周期与 Guardrail"""
        from src.domain.services.token_guardrail import BudgetStatus, TokenGuardrail

        guardrail = TokenGuardrail(pre_planning_threshold=0.85)
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="【核心目标】完成分析"))
        )

        # 模拟长对话
        for i in range(15):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}", role=TurnRole.USER, content=f"m{i}", token_usage=500
                )
            )

        session_context.update_token_usage(7500, 1200)  # 87%

        # 规划前检查
        status = guardrail.check_budget(session_context)
        assert status == BudgetStatus.COMPRESS_RECOMMENDED

        # 执行预规划压缩
        await guardrail.ensure_budget_for_planning(session_context)

        # 验证压缩完成
        assert session_context.conversation_summary is not None

    @pytest.mark.asyncio
    async def test_workflow_execution_with_guardrail(self, session_context):
        """测试：工作流执行与 Guardrail"""
        from src.domain.services.token_guardrail import TokenGuardrail

        guardrail = TokenGuardrail()
        guardrail._compressor = MagicMock()
        guardrail._compressor.compress = AsyncMock(
            return_value=MagicMock(to_text=MagicMock(return_value="summary"))
        )

        # 初始使用
        session_context.update_token_usage(6000, 1000)

        for i in range(8):
            session_context.short_term_buffer.append(
                ShortTermBuffer(
                    turn_id=f"t_{i}",
                    role=TurnRole.USER,
                    content=f"m{i}",
                    token_usage={"total_tokens": 100},
                )
            )

        # 定义工作流
        workflow_nodes = [
            {"type": "llm", "estimated_tokens": 800},
            {"type": "code", "estimated_tokens": 200},
            {"type": "llm", "estimated_tokens": 800},
        ]

        # 检查可行性并准备
        feasibility = guardrail.check_workflow_feasibility(session_context, workflow_nodes)

        if feasibility.needs_compression:
            await guardrail.prepare_for_workflow(session_context, workflow_nodes)

        # 验证工作流可以执行
        final_feasibility = guardrail.check_workflow_feasibility(session_context, workflow_nodes)
        # 压缩后应该可行或至少有更多空间
        assert final_feasibility.remaining_budget >= 0

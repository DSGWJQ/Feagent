"""测试 SessionContext 的 usage_ratio 功能

测试目标：
1. SessionContext 应该能够记录和更新 usage_ratio
2. 应该能够记录每轮的 prompt_tokens 和 completion_tokens
3. 应该能够计算累计的 token 使用情况
4. 应该能够获取当前的上下文使用率
"""

from src.domain.services.context_manager import GlobalContext, SessionContext


class TestSessionContextUsageRatio:
    """测试 SessionContext 的 usage_ratio 功能"""

    def test_session_context_should_have_usage_ratio_field(self):
        """测试：SessionContext 应该有 usage_ratio 字段"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        assert hasattr(session_ctx, "usage_ratio")
        assert session_ctx.usage_ratio == 0.0

    def test_session_context_should_have_token_usage_fields(self):
        """测试：SessionContext 应该有 token 使用字段"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        assert hasattr(session_ctx, "total_prompt_tokens")
        assert hasattr(session_ctx, "total_completion_tokens")
        assert hasattr(session_ctx, "total_tokens")
        assert session_ctx.total_prompt_tokens == 0
        assert session_ctx.total_completion_tokens == 0
        assert session_ctx.total_tokens == 0

    def test_session_context_should_have_model_info_fields(self):
        """测试：SessionContext 应该有模型信息字段"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        assert hasattr(session_ctx, "llm_provider")
        assert hasattr(session_ctx, "llm_model")
        assert hasattr(session_ctx, "context_limit")
        assert session_ctx.llm_provider is None
        assert session_ctx.llm_model is None
        assert session_ctx.context_limit == 0

    def test_update_token_usage_should_accumulate_tokens(self):
        """测试：更新 token 使用应该累计 token 数"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 第一轮
        session_ctx.update_token_usage(prompt_tokens=100, completion_tokens=50)

        assert session_ctx.total_prompt_tokens == 100
        assert session_ctx.total_completion_tokens == 50
        assert session_ctx.total_tokens == 150

        # 第二轮
        session_ctx.update_token_usage(prompt_tokens=200, completion_tokens=100)

        assert session_ctx.total_prompt_tokens == 300
        assert session_ctx.total_completion_tokens == 150
        assert session_ctx.total_tokens == 450

    def test_update_token_usage_should_calculate_usage_ratio(self):
        """测试：更新 token 使用应该计算使用率"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 设置模型信息
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 更新 token 使用
        session_ctx.update_token_usage(prompt_tokens=4096, completion_tokens=0)

        assert session_ctx.usage_ratio == 0.5  # 4096 / 8192

    def test_set_model_info_should_update_model_fields(self):
        """测试：设置模型信息应该更新模型字段"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        assert session_ctx.llm_provider == "openai"
        assert session_ctx.llm_model == "gpt-4"
        assert session_ctx.context_limit == 8192

    def test_set_model_info_should_recalculate_usage_ratio(self):
        """测试：设置模型信息应该重新计算使用率"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 先累计一些 token
        session_ctx.update_token_usage(prompt_tokens=4096, completion_tokens=0)

        # 设置模型信息（应该触发使用率计算）
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        assert session_ctx.usage_ratio == 0.5

    def test_get_usage_ratio_should_return_current_ratio(self):
        """测试：获取使用率应该返回当前比率"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=2048, completion_tokens=0)

        ratio = session_ctx.get_usage_ratio()

        assert ratio == 0.25  # 2048 / 8192

    def test_is_approaching_limit_should_return_true_when_near_limit(self):
        """测试：接近限制时应该返回 True"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=7000, completion_tokens=0)

        is_approaching = session_ctx.is_approaching_limit()

        assert is_approaching is True

    def test_is_approaching_limit_should_return_false_when_far_from_limit(self):
        """测试：远离限制时应该返回 False"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=2000, completion_tokens=0)

        is_approaching = session_ctx.is_approaching_limit()

        assert is_approaching is False

    def test_is_approaching_limit_with_custom_threshold_should_work(self):
        """测试：自定义阈值应该生效"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=5000, completion_tokens=0)

        # 使用 0.6 阈值
        is_approaching = session_ctx.is_approaching_limit(threshold=0.6)

        assert is_approaching is True

    def test_get_remaining_tokens_should_return_correct_count(self):
        """测试：获取剩余 token 数应该返回正确值"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=3000, completion_tokens=1000)

        remaining = session_ctx.get_remaining_tokens()

        assert remaining == 4192  # 8192 - 4000

    def test_get_token_usage_summary_should_return_dict(self):
        """测试：获取 token 使用摘要应该返回字典"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=1000, completion_tokens=500)

        summary = session_ctx.get_token_usage_summary()

        assert summary["total_prompt_tokens"] == 1000
        assert summary["total_completion_tokens"] == 500
        assert summary["total_tokens"] == 1500
        assert summary["usage_ratio"] == 1500 / 8192
        assert summary["context_limit"] == 8192
        assert summary["remaining_tokens"] == 8192 - 1500
        assert summary["llm_provider"] == "openai"
        assert summary["llm_model"] == "gpt-4"

    def test_reset_token_usage_should_clear_counters(self):
        """测试：重置 token 使用应该清空计数器"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=1000, completion_tokens=500)

        # 重置
        session_ctx.reset_token_usage()

        assert session_ctx.total_prompt_tokens == 0
        assert session_ctx.total_completion_tokens == 0
        assert session_ctx.total_tokens == 0
        assert session_ctx.usage_ratio == 0.0

    def test_usage_ratio_should_be_zero_when_context_limit_is_zero(self):
        """测试：上下文限制为 0 时使用率应该为 0"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 不设置模型信息，context_limit 默认为 0
        session_ctx.update_token_usage(prompt_tokens=1000, completion_tokens=500)

        assert session_ctx.usage_ratio == 0.0

    def test_usage_ratio_should_exceed_one_when_over_limit(self):
        """测试：超过限制时使用率应该大于 1"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=10000, completion_tokens=0)

        assert session_ctx.usage_ratio > 1.0

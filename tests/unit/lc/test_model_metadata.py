"""测试 LLM 模型元数据配置

测试目标：
1. 模型元数据的加载和访问
2. 上下文窗口限制的获取
3. 未知模型的回退机制
4. 探针调用记录实际限额
"""

import pytest

from src.lc.model_metadata import (
    ModelMetadata,
    get_model_metadata,
    probe_model_context_limit,
    register_model_metadata,
)


class TestModelMetadata:
    """测试 ModelMetadata 数据类"""

    def test_create_model_metadata_with_valid_inputs_should_succeed(self):
        """测试：使用有效输入创建 ModelMetadata 应该成功"""
        metadata = ModelMetadata(
            provider="openai",
            model="gpt-4",
            context_window=8192,
            max_input_tokens=6144,
            max_output_tokens=2048,
        )

        assert metadata.provider == "openai"
        assert metadata.model == "gpt-4"
        assert metadata.context_window == 8192
        assert metadata.max_input_tokens == 6144
        assert metadata.max_output_tokens == 2048

    def test_model_metadata_with_only_context_window_should_calculate_limits(self):
        """测试：只提供 context_window 时应该自动计算输入输出限制"""
        metadata = ModelMetadata(
            provider="openai",
            model="gpt-3.5-turbo",
            context_window=4096,
        )

        # 默认：输入 75%，输出 25%
        assert metadata.max_input_tokens == 3072  # 4096 * 0.75
        assert metadata.max_output_tokens == 1024  # 4096 * 0.25


class TestGetModelMetadata:
    """测试 get_model_metadata 函数"""

    def test_get_metadata_for_known_openai_model_should_return_correct_metadata(self):
        """测试：获取已知 OpenAI 模型的元数据应该返回正确信息"""
        metadata = get_model_metadata("openai", "gpt-4")

        assert metadata.provider == "openai"
        assert metadata.model == "gpt-4"
        assert metadata.context_window == 8192
        assert metadata.max_input_tokens > 0
        assert metadata.max_output_tokens > 0

    def test_get_metadata_for_gpt4_turbo_should_return_128k_context(self):
        """测试：获取 GPT-4 Turbo 元数据应该返回 128K 上下文窗口"""
        metadata = get_model_metadata("openai", "gpt-4-turbo")

        assert metadata.context_window == 128000

    def test_get_metadata_for_gpt4o_should_return_128k_context(self):
        """测试：获取 GPT-4o 元数据应该返回 128K 上下文窗口"""
        metadata = get_model_metadata("openai", "gpt-4o")

        assert metadata.context_window == 128000

    def test_get_metadata_for_gpt4o_mini_should_return_128k_context(self):
        """测试：获取 GPT-4o-mini 元数据应该返回 128K 上下文窗口"""
        metadata = get_model_metadata("openai", "gpt-4o-mini")

        assert metadata.context_window == 128000

    def test_get_metadata_for_deepseek_should_return_correct_metadata(self):
        """测试：获取 DeepSeek 模型元数据应该返回正确信息"""
        metadata = get_model_metadata("deepseek", "deepseek-chat")

        assert metadata.provider == "deepseek"
        assert metadata.context_window == 32768

    def test_get_metadata_for_unknown_model_should_return_default_metadata(self):
        """测试：获取未知模型元数据应该返回默认值"""
        metadata = get_model_metadata("unknown_provider", "unknown_model")

        assert metadata.provider == "unknown_provider"
        assert metadata.model == "unknown_model"
        assert metadata.context_window == 4096  # 默认值
        assert metadata.max_input_tokens == 3072
        assert metadata.max_output_tokens == 1024

    def test_get_metadata_for_ollama_should_return_local_model_metadata(self):
        """测试：获取 Ollama 本地模型元数据应该返回正确信息"""
        metadata = get_model_metadata("ollama", "llama2")

        assert metadata.provider == "ollama"
        assert metadata.context_window == 4096


class TestRegisterModelMetadata:
    """测试 register_model_metadata 函数"""

    def test_register_new_model_metadata_should_be_retrievable(self):
        """测试：注册新模型元数据后应该可以获取"""
        # 注册自定义模型
        register_model_metadata(
            provider="custom",
            model="custom-model-v1",
            context_window=16384,
            max_input_tokens=12288,
            max_output_tokens=4096,
        )

        # 获取元数据
        metadata = get_model_metadata("custom", "custom-model-v1")

        assert metadata.provider == "custom"
        assert metadata.model == "custom-model-v1"
        assert metadata.context_window == 16384
        assert metadata.max_input_tokens == 12288
        assert metadata.max_output_tokens == 4096

    def test_register_model_with_only_context_window_should_calculate_limits(self):
        """测试：注册模型时只提供 context_window 应该自动计算限制"""
        register_model_metadata(
            provider="custom",
            model="custom-model-v2",
            context_window=8192,
        )

        metadata = get_model_metadata("custom", "custom-model-v2")

        assert metadata.context_window == 8192
        assert metadata.max_input_tokens == 6144  # 8192 * 0.75
        assert metadata.max_output_tokens == 2048  # 8192 * 0.25


class TestProbeModelContextLimit:
    """测试 probe_model_context_limit 函数"""

    @pytest.mark.asyncio
    async def test_probe_model_should_return_actual_context_limit(self, mocker):
        """测试：探针调用应该返回实际上下文限制"""
        # Mock LLM 客户端
        mock_llm = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }
        mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_response)

        # 执行探针调用
        result = await probe_model_context_limit(mock_llm, "openai", "gpt-4")

        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50
        assert result["total_tokens"] == 150
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_probe_model_should_register_metadata_if_successful(self, mocker):
        """测试：探针调用成功后应该注册元数据"""
        # Mock LLM 客户端
        mock_llm = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }
        mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_response)

        # 执行探针调用
        await probe_model_context_limit(mock_llm, "test_provider", "test_model")

        # 验证元数据已注册（使用默认值）
        metadata = get_model_metadata("test_provider", "test_model")
        assert metadata.provider == "test_provider"
        assert metadata.model == "test_model"

    @pytest.mark.asyncio
    async def test_probe_model_with_error_should_return_error_info(self, mocker):
        """测试：探针调用失败时应该返回错误信息"""
        # Mock LLM 客户端抛出异常
        mock_llm = mocker.Mock()
        mock_llm.ainvoke = mocker.AsyncMock(side_effect=Exception("API Error"))

        # 执行探针调用
        result = await probe_model_context_limit(mock_llm, "openai", "gpt-4")

        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"
        assert result["error"] is not None
        assert "API Error" in result["error"]

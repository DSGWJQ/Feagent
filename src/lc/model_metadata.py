"""LLM 模型元数据配置

职责：
1. 管理 LLM 模型的元数据（上下文窗口、token 限制等）
2. 提供模型元数据的查询接口
3. 支持动态注册新模型元数据
4. 提供探针调用功能，记录实际限额

设计原则：
- 配置分离：模型元数据与业务逻辑分离
- 可扩展：支持动态注册新模型
- 回退机制：未知模型使用默认值
- 探针机制：运行时探测实际限额

支持的模型：
- OpenAI: GPT-4, GPT-4 Turbo, GPT-4o, GPT-3.5-turbo
- DeepSeek: deepseek-chat, deepseek-coder
- Qwen: qwen-turbo, qwen-plus, qwen-max
- Ollama: llama2, mistral, codellama (本地模型)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ModelMetadata:
    """模型元数据

    属性：
    - provider: 提供商名称（openai, deepseek, qwen, ollama）
    - model: 模型名称
    - context_window: 上下文窗口大小（总 token 数）
    - max_input_tokens: 最大输入 token 数（可选，默认为 context_window * 0.75）
    - max_output_tokens: 最大输出 token 数（可选，默认为 context_window * 0.25）
    """

    provider: str
    model: str
    context_window: int
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None

    def __post_init__(self):
        """初始化后处理：计算默认的输入输出限制"""
        if self.max_input_tokens is None:
            self.max_input_tokens = int(self.context_window * 0.75)
        if self.max_output_tokens is None:
            self.max_output_tokens = int(self.context_window * 0.25)


# 预定义的模型元数据
# 数据来源：各 LLM 提供商官方文档
_MODEL_METADATA_REGISTRY: dict[tuple[str, str], ModelMetadata] = {
    # OpenAI 模型
    ("openai", "gpt-4"): ModelMetadata(
        provider="openai",
        model="gpt-4",
        context_window=8192,
        max_input_tokens=6144,
        max_output_tokens=2048,
    ),
    ("openai", "gpt-4-32k"): ModelMetadata(
        provider="openai",
        model="gpt-4-32k",
        context_window=32768,
        max_input_tokens=24576,
        max_output_tokens=8192,
    ),
    ("openai", "gpt-4-turbo"): ModelMetadata(
        provider="openai",
        model="gpt-4-turbo",
        context_window=128000,
        max_input_tokens=96000,
        max_output_tokens=32000,
    ),
    ("openai", "gpt-4o"): ModelMetadata(
        provider="openai",
        model="gpt-4o",
        context_window=128000,
        max_input_tokens=96000,
        max_output_tokens=32000,
    ),
    ("openai", "gpt-4o-mini"): ModelMetadata(
        provider="openai",
        model="gpt-4o-mini",
        context_window=128000,
        max_input_tokens=96000,
        max_output_tokens=32000,
    ),
    ("openai", "gpt-3.5-turbo"): ModelMetadata(
        provider="openai",
        model="gpt-3.5-turbo",
        context_window=4096,
        max_input_tokens=3072,
        max_output_tokens=1024,
    ),
    ("openai", "gpt-3.5-turbo-16k"): ModelMetadata(
        provider="openai",
        model="gpt-3.5-turbo-16k",
        context_window=16384,
        max_input_tokens=12288,
        max_output_tokens=4096,
    ),
    # DeepSeek 模型
    ("deepseek", "deepseek-chat"): ModelMetadata(
        provider="deepseek",
        model="deepseek-chat",
        context_window=32768,
        max_input_tokens=24576,
        max_output_tokens=8192,
    ),
    ("deepseek", "deepseek-coder"): ModelMetadata(
        provider="deepseek",
        model="deepseek-coder",
        context_window=32768,
        max_input_tokens=24576,
        max_output_tokens=8192,
    ),
    # Qwen 模型
    ("qwen", "qwen-turbo"): ModelMetadata(
        provider="qwen",
        model="qwen-turbo",
        context_window=8192,
        max_input_tokens=6144,
        max_output_tokens=2048,
    ),
    ("qwen", "qwen-plus"): ModelMetadata(
        provider="qwen",
        model="qwen-plus",
        context_window=32768,
        max_input_tokens=24576,
        max_output_tokens=8192,
    ),
    ("qwen", "qwen-max"): ModelMetadata(
        provider="qwen",
        model="qwen-max",
        context_window=8192,
        max_input_tokens=6144,
        max_output_tokens=2048,
    ),
    # Ollama 本地模型
    ("ollama", "llama2"): ModelMetadata(
        provider="ollama",
        model="llama2",
        context_window=4096,
        max_input_tokens=3072,
        max_output_tokens=1024,
    ),
    ("ollama", "mistral"): ModelMetadata(
        provider="ollama",
        model="mistral",
        context_window=8192,
        max_input_tokens=6144,
        max_output_tokens=2048,
    ),
    ("ollama", "codellama"): ModelMetadata(
        provider="ollama",
        model="codellama",
        context_window=16384,
        max_input_tokens=12288,
        max_output_tokens=4096,
    ),
}


def get_model_metadata(provider: str, model: str) -> ModelMetadata:
    """获取模型元数据

    参数：
        provider: 提供商名称
        model: 模型名称

    返回：
        ModelMetadata: 模型元数据

    说明：
        - 如果模型在注册表中，返回预定义的元数据
        - 如果模型未知，返回默认元数据（4K 上下文窗口）
    """
    key = (provider.lower(), model.lower())

    if key in _MODEL_METADATA_REGISTRY:
        return _MODEL_METADATA_REGISTRY[key]

    # 未知模型，返回默认元数据
    return ModelMetadata(
        provider=provider,
        model=model,
        context_window=4096,  # 默认 4K 上下文窗口
        max_input_tokens=3072,  # 75%
        max_output_tokens=1024,  # 25%
    )


def register_model_metadata(
    provider: str,
    model: str,
    context_window: int,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
) -> None:
    """注册新模型元数据

    参数：
        provider: 提供商名称
        model: 模型名称
        context_window: 上下文窗口大小
        max_input_tokens: 最大输入 token 数（可选）
        max_output_tokens: 最大输出 token 数（可选）

    说明：
        - 如果未提供 max_input_tokens 和 max_output_tokens，
          将自动计算为 context_window 的 75% 和 25%
    """
    metadata = ModelMetadata(
        provider=provider,
        model=model,
        context_window=context_window,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
    )

    key = (provider.lower(), model.lower())
    _MODEL_METADATA_REGISTRY[key] = metadata


async def probe_model_context_limit(
    llm: Any,
    provider: str,
    model: str,
) -> dict[str, Any]:
    """探针调用：测试模型实际上下文限制

    通过发送一个简单的请求，记录实际的 token 使用情况。

    参数：
        llm: LLM 客户端实例
        provider: 提供商名称
        model: 模型名称

    返回：
        探针结果字典，包含：
        - provider: 提供商名称
        - model: 模型名称
        - prompt_tokens: 提示词 token 数
        - completion_tokens: 完成词 token 数
        - total_tokens: 总 token 数
        - timestamp: 探针时间戳
        - error: 错误信息（如果失败）

    说明：
        - 探针调用会发送一个简单的测试请求
        - 如果成功，会自动注册模型元数据（使用默认值）
        - 如果失败，返回错误信息
    """
    result: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # 发送简单的测试请求
        response = await llm.ainvoke("Hello, this is a test message.")

        # 提取 token 使用信息
        if hasattr(response, "response_metadata"):
            token_usage = response.response_metadata.get("token_usage", {})
            result["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
            result["completion_tokens"] = token_usage.get("completion_tokens", 0)
            result["total_tokens"] = token_usage.get("total_tokens", 0)

        # 如果模型未注册，使用默认值注册
        key = (provider.lower(), model.lower())
        if key not in _MODEL_METADATA_REGISTRY:
            register_model_metadata(
                provider=provider,
                model=model,
                context_window=4096,  # 默认值
            )

    except Exception as e:
        result["error"] = str(e)

    return result


def get_context_limit(provider: str, model: str) -> int:
    """获取模型上下文限制（快捷方法）

    参数：
        provider: 提供商名称
        model: 模型名称

    返回：
        上下文窗口大小（token 数）
    """
    metadata = get_model_metadata(provider, model)
    return metadata.context_window


def get_max_input_tokens(provider: str, model: str) -> int:
    """获取模型最大输入 token 数（快捷方法）

    参数：
        provider: 提供商名称
        model: 模型名称

    返回：
        最大输入 token 数
    """
    metadata = get_model_metadata(provider, model)
    return metadata.max_input_tokens or 0


def get_max_output_tokens(provider: str, model: str) -> int:
    """获取模型最大输出 token 数（快捷方法）

    参数：
        provider: 提供商名称
        model: 模型名称

    返回：
        最大输出 token 数
    """
    metadata = get_model_metadata(provider, model)
    return metadata.max_output_tokens or 0

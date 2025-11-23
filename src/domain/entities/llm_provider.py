"""LLMProvider 实体 - LLM提供商配置

V2新功能：支持多LLM提供商管理

业务定义：
- LLMProvider 代表一个 LLM 服务提供商（OpenAI、DeepSeek、Qwen等）
- 包含 API 配置、可用模型列表、成本信息等
- 支持启用/禁用、配置更新等操作

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法创建预定义提供商
- API密钥需要加密存储（在 Infrastructure 层处理）
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.domain.exceptions import DomainError


@dataclass
class LLMProvider:
    """LLM提供商实体

    属性说明：
    - id: 唯一标识符（llm_provider_ 前缀）
    - name: 提供商标识（openai, deepseek, qwen, anthropic等）
    - display_name: 显示名称（用户可见）
    - api_base: API 基础 URL
    - api_key: API 密钥（Infrastructure层负责加密）
    - models: 支持的模型列表
    - enabled: 是否启用
    - config: 额外配置（超时、重试等）
    - created_at: 创建时间
    - updated_at: 最后更新时间

    为什么不是聚合根？
    - LLMProvider 相对简单，没有复杂的子实体
    - 主要是配置数据，而非业务逻辑载体
    """

    id: str
    name: str
    display_name: str
    api_base: str
    api_key: str | None
    models: list[str]
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        name: str,
        display_name: str,
        api_base: str,
        api_key: str | None,
        models: list[str],
    ) -> "LLMProvider":
        """创建 LLMProvider 的工厂方法

        参数：
            name: 提供商标识
            display_name: 显示名称
            api_base: API 基础 URL
            api_key: API 密钥（可选，本地模型可能不需要）
            models: 支持的模型列表

        返回：
            LLMProvider 实例

        抛出：
            DomainError: 当验证失败时
        """
        # 验证业务规则
        if not name or not name.strip():
            raise DomainError("提供商名称不能为空")

        if not models:
            raise DomainError("至少需要一个可用模型")

        # 使用 UUIDv4 生成 ID
        from uuid import uuid4

        return cls(
            id=f"llm_provider_{uuid4().hex[:8]}",
            name=name.strip().lower(),
            display_name=display_name.strip(),
            api_base=api_base.strip(),
            api_key=api_key,
            models=models,
            enabled=True,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def create_openai(api_key: str) -> "LLMProvider":
        """创建 OpenAI 提供商（预定义配置）

        参数：
            api_key: OpenAI API 密钥

        返回：
            配置好的 OpenAI LLMProvider
        """
        return LLMProvider.create(
            name="openai",
            display_name="OpenAI",
            api_base="https://api.openai.com/v1",
            api_key=api_key,
            models=["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"],
        )

    @staticmethod
    def create_deepseek(api_key: str) -> "LLMProvider":
        """创建 DeepSeek 提供商（预定义配置）

        参数：
            api_key: DeepSeek API 密钥

        返回：
            配置好的 DeepSeek LLMProvider
        """
        return LLMProvider.create(
            name="deepseek",
            display_name="DeepSeek",
            api_base="https://api.deepseek.com/v1",
            api_key=api_key,
            models=["deepseek-chat", "deepseek-coder"],
        )

    @staticmethod
    def create_qwen(api_key: str) -> "LLMProvider":
        """创建通义千问提供商（预定义配置）

        参数：
            api_key: 通义千问 API 密钥

        返回：
            配置好的 Qwen LLMProvider
        """
        return LLMProvider.create(
            name="qwen",
            display_name="通义千问 (Qwen)",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=api_key,
            models=["qwen-turbo", "qwen-plus", "qwen-max"],
        )

    @staticmethod
    def create_ollama(base_url: str = "http://localhost:11434/v1") -> "LLMProvider":
        """创建 Ollama 本地模型提供商（预定义配置）

        参数：
            base_url: Ollama API 地址（默认本地）

        返回：
            配置好的 Ollama LLMProvider

        说明：
            本地模型不需要 API 密钥
        """
        return LLMProvider.create(
            name="ollama",
            display_name="Ollama (本地)",
            api_base=base_url,
            api_key=None,
            models=["llama2", "mistral", "codellama"],
        )

    def enable(self) -> None:
        """启用提供商"""
        self.enabled = True
        self.updated_at = datetime.now(UTC)

    def disable(self) -> None:
        """禁用提供商"""
        self.enabled = False
        self.updated_at = datetime.now(UTC)

    def update_api_key(self, new_api_key: str) -> None:
        """更新 API 密钥

        参数：
            new_api_key: 新的 API 密钥
        """
        self.api_key = new_api_key
        self.updated_at = datetime.now(UTC)

    def add_model(self, model_name: str) -> None:
        """添加模型

        参数：
            model_name: 模型名称
        """
        if model_name not in self.models:
            self.models.append(model_name)
            self.updated_at = datetime.now(UTC)

    def remove_model(self, model_name: str) -> None:
        """移除模型

        参数：
            model_name: 模型名称

        抛出：
            DomainError: 当试图删除最后一个模型时
        """
        if len(self.models) <= 1:
            raise DomainError("至少需要保留一个可用模型")

        if model_name in self.models:
            self.models.remove(model_name)
            self.updated_at = datetime.now(UTC)

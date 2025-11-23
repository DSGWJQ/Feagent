"""LLMUsage 实体 - LLM 使用记录和成本追踪

V2新功能：记录每次 LLM 调用的成本

业务定义：
- LLMUsage 记录一次 LLM 调用的详细信息
- 包含 token 统计、成本计算等
- 用于预算控制和成本分析

设计原则：
- 纯 Python 实现
- 包含成本计算逻辑（不同提供商的定价不同）
- 支持成本统计和预算控制
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from src.domain.exceptions import DomainError


@dataclass
class LLMUsage:
    """LLM 使用记录实体

    属性说明：
    - id: 唯一标识符
    - provider: LLM 提供商（openai, deepseek等）
    - model: 使用的模型
    - prompt_tokens: 提示词 token 数
    - completion_tokens: 完成词 token 数
    - total_tokens: 总 token 数
    - cost: 成本（美元）
    - run_id: 所属运行 ID
    - task_id: 所属任务 ID（可选）
    - created_at: 创建时间

    成本定价参考：
    - OpenAI GPT-4: prompt $0.03/1K, completion $0.06/1K
    - DeepSeek: prompt $0.0007/1K, completion $0.002/1K
    - Qwen: prompt $0.0008/1K, completion $0.002/1K
    """

    id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    run_id: str
    task_id: str | None = None
    created_at: datetime = None

    # 定价表（美元）
    PRICING: ClassVar[dict[str, dict[str, dict[str, float]]]] = {
        "openai": {
            "gpt-4": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
            "gpt-4-turbo": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
            "gpt-3.5-turbo": {"prompt": 0.0005 / 1000, "completion": 0.0015 / 1000},
            "gpt-3.5-turbo-16k": {"prompt": 0.003 / 1000, "completion": 0.004 / 1000},
        },
        "deepseek": {
            "deepseek-chat": {"prompt": 0.00014 / 1000, "completion": 0.00028 / 1000},
            "deepseek-coder": {"prompt": 0.00014 / 1000, "completion": 0.00028 / 1000},
        },
        "qwen": {
            "qwen-turbo": {"prompt": 0.0008 / 1000, "completion": 0.002 / 1000},
            "qwen-plus": {"prompt": 0.004 / 1000, "completion": 0.008 / 1000},
            "qwen-max": {"prompt": 0.02 / 1000, "completion": 0.06 / 1000},
        },
        "ollama": {
            # 本地模型免费
            "llama2": {"prompt": 0, "completion": 0},
            "mistral": {"prompt": 0, "completion": 0},
            "codellama": {"prompt": 0, "completion": 0},
        },
    }

    @classmethod
    def create(
        cls,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        run_id: str,
        task_id: str | None = None,
    ) -> "LLMUsage":
        """创建 LLMUsage 的工厂方法

        参数：
            provider: LLM 提供商
            model: 使用的模型
            prompt_tokens: 提示词 token 数
            completion_tokens: 完成词 token 数
            run_id: 所属运行 ID
            task_id: 所属任务 ID（可选）

        返回：
            LLMUsage 实例

        抛出：
            DomainError: 当验证失败时
        """
        # 验证业务规则
        if not provider or not provider.strip():
            raise DomainError("提供商名称不能为空")

        if not model or not model.strip():
            raise DomainError("模型名称不能为空")

        if prompt_tokens < 0 or completion_tokens < 0:
            raise DomainError("Token 数不能为负数")

        # 计算成本
        cost = cls.calculate_cost(provider, model, prompt_tokens, completion_tokens)

        # 使用 UUIDv4 生成 ID
        from uuid import uuid4

        return cls(
            id=f"llm_usage_{uuid4().hex[:8]}",
            provider=provider.lower(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            run_id=run_id,
            task_id=task_id,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def calculate_cost(
        provider: str, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """计算 LLM 调用成本

        参数：
            provider: LLM 提供商
            model: 模型名称
            prompt_tokens: 提示词 token 数
            completion_tokens: 完成词 token 数

        返回：
            成本（美元），保留6位小数

        说明：
            - 如果提供商或模型不在定价表中，返回 0
            - 本地模型（ollama）成本为 0
        """
        provider_pricing = LLMUsage.PRICING.get(provider, {})
        model_pricing = provider_pricing.get(model, {"prompt": 0, "completion": 0})

        cost = (prompt_tokens * model_pricing["prompt"]) + (
            completion_tokens * model_pricing["completion"]
        )

        return round(cost, 6)

    @staticmethod
    def estimate_total_cost(usages: list["LLMUsage"]) -> float:
        """估算总成本

        参数：
            usages: LLMUsage 列表

        返回：
            总成本（美元）
        """
        return sum(usage.cost for usage in usages)

    @staticmethod
    def estimate_cost_by_provider(usages: list["LLMUsage"]) -> dict[str, float]:
        """按提供商统计成本

        参数：
            usages: LLMUsage 列表

        返回：
            {provider: total_cost} 字典
        """
        cost_by_provider = {}
        for usage in usages:
            if usage.provider not in cost_by_provider:
                cost_by_provider[usage.provider] = 0
            cost_by_provider[usage.provider] += usage.cost

        return cost_by_provider

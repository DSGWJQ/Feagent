"""LLMProvider DTO - LLM提供商数据传输对象

定义 LLMProvider 相关的 API 请求和响应格式

设计原则：
1. DTO 只负责数据传输，不包含业务逻辑
2. 使用 Pydantic 进行数据验证
3. 严格的类型提示
4. 与领域模型分离（解耦）
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegisterLLMProviderRequest(BaseModel):
    """注册 LLM 提供商请求

    用户提供的注册提供商所需的数据
    """

    name: str = Field(..., description="提供商标识（openai, deepseek, qwen等）", min_length=1)
    display_name: str = Field(..., description="显示名称", min_length=1)
    api_base: str = Field(..., description="API 基础 URL")
    api_key: str | None = Field(default=None, description="API 密钥（本地模型可选）")
    models: list[str] = Field(..., description="支持的模型列表", min_items=1)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "sk-...",
                "models": ["gpt-4", "gpt-3.5-turbo"],
            }
        }


class UpdateLLMProviderRequest(BaseModel):
    """更新 LLM 提供商请求

    允许更新提供商的部分字段
    """

    api_key: str | None = Field(default=None, description="新的 API 密钥")
    api_base: str | None = Field(default=None, description="新的 API 基础 URL")

    class Config:
        json_schema_extra = {
            "example": {
                "api_key": "sk-new-key",
            }
        }


class LLMProviderResponse(BaseModel):
    """LLM 提供商响应

    返回给客户端的提供商信息
    """

    id: str = Field(..., description="提供商 ID")
    name: str = Field(..., description="提供商标识")
    display_name: str = Field(..., description="显示名称")
    api_base: str = Field(..., description="API 基础 URL")
    api_key: str | None = Field(default=None, description="API 密钥（掩码）")
    models: list[str] = Field(..., description="支持的模型列表")
    enabled: bool = Field(..., description="是否启用")
    config: dict[str, Any] = Field(default={}, description="额外配置")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "llm_provider_a1b2c3d4",
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "sk-***",  # 掩码显示
                "models": ["gpt-4", "gpt-3.5-turbo"],
                "enabled": True,
                "config": {},
                "created_at": "2025-11-20T08:00:00Z",
                "updated_at": "2025-11-21T15:00:00Z",
            }
        }


class LLMProviderListResponse(BaseModel):
    """LLM 提供商列表响应"""

    providers: list[LLMProviderResponse] = Field(..., description="提供商列表")
    total: int = Field(..., description="总数量")

    class Config:
        json_schema_extra = {
            "example": {
                "providers": [
                    {
                        "id": "llm_provider_a1b2c3d4",
                        "name": "openai",
                        "display_name": "OpenAI",
                        "enabled": True,
                    }
                ],
                "total": 1,
            }
        }


class EnableLLMProviderRequest(BaseModel):
    """启用 LLM 提供商请求"""

    pass  # 无需额外参数


class DisableLLMProviderRequest(BaseModel):
    """禁用 LLM 提供商请求"""

    pass  # 无需额外参数

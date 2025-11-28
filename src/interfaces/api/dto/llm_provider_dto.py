"""LLM provider DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegisterLLMProviderRequest(BaseModel):
    """Request payload for registering a new provider."""

    name: str = Field(..., description="Provider identifier (openai, deepseek, qwen)", min_length=1)
    display_name: str = Field(..., description="Display name", min_length=1)
    api_base: str = Field(..., description="API base URL")
    api_key: str | None = Field(default=None, description="API key (optional for local models)")
    models: list[str] = Field(
        ...,
        description="Supported model names",
        min_length=1,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "openai",
                "display_name": "OpenAI",
                "api_base": "https://api.openai.com/v1",
                "api_key": "sk-***",
                "models": ["gpt-4", "gpt-3.5-turbo"],
            }
        }


class UpdateLLMProviderRequest(BaseModel):
    """Request payload for updating provider credentials."""

    api_key: str | None = Field(default=None, description="New API key")
    api_base: str | None = Field(default=None, description="New API base URL")


class LLMProviderResponse(BaseModel):
    """Provider info returned to clients."""

    id: str = Field(..., description="Provider ID")
    name: str = Field(..., description="Provider identifier")
    display_name: str = Field(..., description="Display name")
    api_base: str = Field(..., description="API base URL")
    api_key: str | None = Field(default=None, description="Masked API key")
    models: list[str] = Field(..., description="Supported model names")
    enabled: bool = Field(..., description="Whether the provider is enabled")
    config: dict[str, Any] = Field(default_factory=dict, description="Extra config")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")

    class Config:
        from_attributes = True


class LLMProviderListResponse(BaseModel):
    """Paginated provider list response."""

    providers: list[LLMProviderResponse] = Field(..., description="Providers")
    total: int = Field(..., description="Total count")


class EnableLLMProviderRequest(BaseModel):
    """Dummy request body for enable endpoint."""

    pass


class DisableLLMProviderRequest(BaseModel):
    """Dummy request body for disable endpoint."""

    pass

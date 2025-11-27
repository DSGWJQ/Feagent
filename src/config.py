"""应用配置模块 - 使用 Pydantic Settings 管理环境变量"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Agent Platform", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    env: Literal["development", "production", "test"] = Field(
        default="development", description="运行环境"
    )
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")

    # Server
    host: str = Field(default="0.0.0.0", description="服务器地址")
    port: int = Field(default=8000, description="服务器端口")
    reload: bool = Field(default=False, description="热重载")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./agent_platform.db",
        description="数据库连接 URL",
    )

    # LLM Provider
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI Base URL")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI 模型")

    # Security
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production",
        description="JWT 密钥",
    )
    algorithm: str = Field(default="HS256", description="JWT 算法")
    access_token_expire_minutes: int = Field(default=30, description="访问令牌过期时间（分钟）")

    # CORS
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        description="允许的跨域源",
    )

    # Retry & Timeout
    max_retries: int = Field(default=3, description="最大重试次数")
    request_timeout: int = Field(default=30, description="请求超时时间（秒）")
    retry_backoff_factor: int = Field(default=2, description="重试退避因子")

    # Task Execution
    max_concurrent_tasks: int = Field(default=5, description="最大并发任务数")
    task_timeout: int = Field(default=300, description="任务超时时间（秒）")

    # Logging
    log_format: Literal["json", "text"] = Field(default="json", description="日志格式")
    log_file: str = Field(default="logs/app.log", description="日志文件路径")


# 全局配置实例
settings = Settings()

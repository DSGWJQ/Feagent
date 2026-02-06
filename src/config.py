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

    # GitHub OAuth
    github_client_id: str = Field(default="", description="GitHub OAuth Client ID")
    github_client_secret: str = Field(default="", description="GitHub OAuth Client Secret")
    github_redirect_uri: str = Field(
        default="http://localhost:5173/auth/callback", description="GitHub OAuth回调地址"
    )

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

    # RAG / Knowledge Base Configuration
    # Vector Store
    vector_store_type: Literal["sqlite", "chroma", "qdrant", "faiss"] = Field(
        default="chroma", description="向量存储类型"
    )
    vector_store_url: str = Field(default="", description="外部向量存储URL（如Chroma、Qdrant）")
    vector_store_api_key: str = Field(default="", description="向量存储API密钥")

    # SQLite Vector DB (when vector_store_type = "sqlite")
    sqlite_vector_db_path: str = Field(
        default="data/knowledge_base.db", description="SQLite向量数据库路径"
    )
    sqlite_vector_extension: str = Field(default="sqlite-vec", description="SQLite向量扩展")

    # ChromaDB (when vector_store_type = "chroma")
    chroma_path: str = Field(default="data/chroma_db", description="ChromaDB存储路径")
    chroma_host: str = Field(default="localhost", description="ChromaDB主机地址")
    chroma_port: int = Field(default=8000, description="ChromaDB端口")

    # Embedding Model
    embedding_model: str = Field(default="text-embedding-3-small", description="嵌入模型")
    embedding_provider: Literal["openai", "cohere", "huggingface"] = Field(
        default="openai", description="嵌入模型提供商"
    )
    embedding_dimension: int = Field(default=1536, description="向量维度")
    embedding_batch_size: int = Field(default=100, description="嵌入批处理大小")

    # RAG Retrieval Settings
    rag_top_k: int = Field(default=5, description="检索返回的文档块数量")
    rag_similarity_threshold: float = Field(default=0.7, description="相似度阈值")
    rag_max_context_tokens: int = Field(default=4000, description="最大上下文Token数")
    rag_chunk_size: int = Field(default=1000, description="文档分块大小")
    rag_chunk_overlap: int = Field(default=200, description="文档分块重叠大小")

    # Document Processing
    max_document_size_mb: int = Field(default=50, description="最大文档大小（MB）")
    supported_document_types: list[str] = Field(
        default=["pdf", "docx", "doc", "md", "txt", "html", "htm"], description="支持的文档类型"
    )

    # Knowledge Base Management
    kb_global_enabled: bool = Field(default=True, description="是否启用全局知识库")
    kb_per_workflow_enabled: bool = Field(default=True, description="是否启���工作流专属知识库")
    kb_auto_indexing: bool = Field(default=True, description="是否自动索引文档")

    # Performance & Monitoring
    rag_cache_enabled: bool = Field(default=True, description="是否启用RAG缓存")
    rag_cache_ttl: int = Field(default=3600, description="RAG缓存TTL（秒）")
    rag_metrics_enabled: bool = Field(default=True, description="是否启用RAG指标收集")

    # Feature Flags / Rollback
    disable_run_persistence: bool = Field(
        default=False,
        description="回滚开关：忽略 run_id 且禁用 Runs API（切回 legacy execute/stream）。",
    )
    enable_decision_execution_bridge: bool = Field(
        default=False,
        description=(
            "Feature flag：是否启用 DecisionExecutionBridge（validated decision → executor）。"
            "默认关闭（灰度/回滚；关闭时不会通过 EventBus 自动执行 decision）。"
        ),
    )
    enable_internal_workflow_create_endpoints: bool = Field(
        default=False,
        description=(
            "Feature flag：是否启用内部 workflow 创建入口（/workflows/import、/workflows/generate-from-form）。"
            "默认关闭（fail-closed；对产品流量不可达）。"
        ),
    )

    # E2E Test Support
    enable_test_seed_api: bool = Field(
        default=False,
        description=(
            "Feature flag：是否启用测试 Seed API（/api/test/workflows/seed 等）。"
            "仅在测试/开发环境启用，生产环境必须保持 False。"
        ),
    )

    # E2E Test Mode Switching (A/B/C模式切换)
    e2e_test_mode: Literal["deterministic", "hybrid", "fullreal"] = Field(
        default="deterministic",
        description="E2E测试模式: deterministic(CI), hybrid(PR/Daily), fullreal(Nightly)",
    )
    llm_adapter: str = Field(
        default="stub",
        description="LLM适配器类型: stub(固定响应), replay(回放录制), openai(真实API)",
    )
    http_adapter: str = Field(
        default="mock",
        description="HTTP适配器类型: mock(本地mock), wiremock(WireMock服务器), httpx(真实HTTP)",
    )
    llm_replay_file: str = Field(
        default="",
        description="LLM回放文件路径(当llm_adapter=replay时必需)",
    )
    wiremock_url: str = Field(
        default="http://localhost:8080",
        description="WireMock服务器地址(当http_adapter=wiremock时使用)",
    )


# 全局配置实例
settings = Settings()

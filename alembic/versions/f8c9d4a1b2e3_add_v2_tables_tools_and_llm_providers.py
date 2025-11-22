"""add v2 tables: tools and llm_providers

Revision ID: f8c9d4a1b2e3
Revises: 230439fc292d
Create Date: 2025-11-22 12:00:00.000000

V2阶段数据库迁移：
1. 创建 tools 表（工具管理）
2. 创建 llm_providers 表（LLM提供商管理）
3. 更新 workflows 表（添加 source 和 source_id 字段）
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8c9d4a1b2e3"
down_revision: str | None = "230439fc292d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """升级数据库 schema

    创建 V2 新增的表和字段
    """
    # ==================== 1. 创建 tools 表 ====================
    op.create_table(
        "tools",
        sa.Column("id", sa.String(length=36), nullable=False, comment="Tool ID（tool_ 前缀）"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="工具名称"),
        sa.Column("description", sa.Text(), nullable=False, comment="工具描述"),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            comment="工具分类（http, database, file等）",
        ),
        sa.Column("status", sa.String(length=20), nullable=False, comment="工具状态"),
        sa.Column("version", sa.String(length=50), nullable=False, comment="版本号"),
        # 工具定义
        sa.Column("parameters", sa.JSON(), nullable=True, comment="参数列表（JSON）"),
        sa.Column("returns", sa.JSON(), nullable=True, comment="返回值 schema（JSON）"),
        # 实现方式
        sa.Column("implementation_type", sa.String(length=50), nullable=False, comment="实现类型"),
        sa.Column("implementation_config", sa.JSON(), nullable=True, comment="实现配置（JSON）"),
        # 元数据
        sa.Column("author", sa.String(length=255), nullable=False, comment="创建者"),
        sa.Column("tags", sa.JSON(), nullable=True, comment="标签列表（JSON）"),
        sa.Column("icon", sa.Text(), nullable=True, comment="图标 URL"),
        # 使用统计
        sa.Column("usage_count", sa.Integer(), nullable=False, comment="使用次数"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True, comment="最后使用时间"),
        # 时间戳
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.Column("published_at", sa.DateTime(), nullable=True, comment="发布时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    # 创建索引
    op.create_index("idx_tools_status", "tools", ["status"], unique=False)
    op.create_index("idx_tools_category", "tools", ["category"], unique=False)
    op.create_index("idx_tools_created_at", "tools", ["created_at"], unique=False)

    # ==================== 2. 创建 llm_providers 表 ====================
    op.create_table(
        "llm_providers",
        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
            comment="LLMProvider ID（llm_provider_ 前缀）",
        ),
        sa.Column(
            "name",
            sa.String(length=50),
            nullable=False,
            comment="提供商标识（openai, deepseek等）",
        ),
        sa.Column("display_name", sa.String(length=255), nullable=False, comment="显示名称"),
        sa.Column("api_base", sa.Text(), nullable=False, comment="API 基础 URL"),
        sa.Column("api_key", sa.Text(), nullable=True, comment="API 密钥"),
        sa.Column("models", sa.JSON(), nullable=False, comment="支持的模型列表（JSON）"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("config", sa.JSON(), nullable=True, comment="额外配置（JSON）"),
        # 时间戳
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),  # name 字段唯一
    )
    # 创建索引
    op.create_index("idx_llm_providers_name", "llm_providers", ["name"], unique=False)
    op.create_index("idx_llm_providers_enabled", "llm_providers", ["enabled"], unique=False)

    # ==================== 3. 更新 workflows 表 ====================
    # 添加 source 和 source_id 字段
    op.add_column(
        "workflows",
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            server_default="feagent",
            comment="工作流来源（feagent/coze/user等）",
        ),
    )
    op.add_column(
        "workflows",
        sa.Column(
            "source_id",
            sa.String(length=255),
            nullable=True,
            comment="原始来源的ID（如Coze workflow_id）",
        ),
    )


def downgrade() -> None:
    """降级数据库 schema

    删除 V2 新增的表和字段
    """
    # ==================== 3. 移除 workflows 表的 V2 字段 ====================
    op.drop_column("workflows", "source_id")
    op.drop_column("workflows", "source")

    # ==================== 2. 删除 llm_providers 表 ====================
    op.drop_index("idx_llm_providers_enabled", table_name="llm_providers")
    op.drop_index("idx_llm_providers_name", table_name="llm_providers")
    op.drop_table("llm_providers")

    # ==================== 1. 删除 tools 表 ====================
    op.drop_index("idx_tools_created_at", table_name="tools")
    op.drop_index("idx_tools_category", table_name="tools")
    op.drop_index("idx_tools_status", table_name="tools")
    op.drop_table("tools")
